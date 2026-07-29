"""TradePilot v5 — Per-Pool Risk Manager
Comprehensive risk controls: drawdown limits, 5-tier circuit breakers,
VIX-based sizing, correlation guards, drawdown recovery ladder.
Born from the April 9 loss of Rs 30,816 — never again without risk gates.
CLI: python3 -m prototype.v5.risk_manager --status | --simulate-losses 10
"""

import json, argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from collections import defaultdict

try:
    from .pool_manager import PoolManager, PERSIST_DIR, POOL_NAMES
except ImportError:
    # Standalone mock for testing
    PERSIST_DIR = Path.home() / "Documents/tinker/projects/tradepilot/docs/paper-trades/v5"
    POOL_NAMES = ["INTRADAY", "SWING", "POSITIONAL", "INVESTMENT", "RESERVE"]
    class _MockPool:
        def __init__(self, name, capital=1_000_000):
            self.name, self.capital, self.deployed = name, capital, 0.0
            self.daily_pnl = self.weekly_pnl = self.monthly_pnl = 0.0
            self.positions, self.paused, self.reduced = [], False, False
        @property
        def cash(self): return self.capital - self.deployed
    class PoolManager:
        def __init__(self, total_capital=5_000_000):
            self.total_capital = total_capital
            self.pools = {n: _MockPool(n, total_capital * 0.2) for n in POOL_NAMES}
        def get_status(self): return {"total_capital": self.total_capital}

# --- Drawdown limit configs ---
POOL_LIMITS = {
    "INTRADAY":    {"daily": 0.02, "weekly": 0.05, "monthly": 0.10},
    "SWING":       {"daily": None, "weekly": 0.03, "monthly": 0.08},
    "POSITIONAL":  {"daily": None, "weekly": None, "monthly": 0.10},
    "INVESTMENT":  {"daily": None, "weekly": None, "monthly": 0.15},
}
PORTFOLIO_LIMITS = {"daily": 0.01, "weekly": 0.03, "monthly": 0.07}

# --- VIX tiers (used as fallback; formula: min(15/vix, 1.0)) ---
VIX_TIERS = [(13, 1.0), (18, 0.85), (25, 0.60), (999, 0.40)]

# --- Recovery ladder ---
RECOVERY_LADDER = [(3, 0.25), (7, 0.50), (14, 0.75)]  # (day_threshold, mult)
RECOVERY_EARLY_RESTORE_DAYS = 5  # consecutive profitable days to skip to 100%

MAX_POSITIONS_TOTAL = 20
MAX_SAME_SECTOR = 3
KELLY_CAP = 0.25  # max 25% of pool per position
CORRELATION_THRESHOLD = 0.7


@dataclass
class BreakerState:
    active: bool = False
    tier: int = 0
    triggered_at: str = ""
    reason: str = ""
    paused_until: str = ""


@dataclass
class RecoveryState:
    active: bool = False
    day: int = 0
    size_mult: float = 1.0
    started: str = ""
    consecutive_profit_days: int = 0


class RiskManager:
    def __init__(self, pool_manager: PoolManager, regime: str = "SIDEWAYS", vix: float = 15.0):
        self.pm = pool_manager
        self.regime = regime.upper()
        self.vix = vix

        # Per-pool consecutive loss tracking
        self.pool_consec_losses: Dict[str, int] = defaultdict(int)
        # Per-stock consecutive loss tracking
        self.stock_consec_losses: Dict[str, int] = defaultdict(int)
        # Stock bans {symbol: {"reason": str, "until": str}}
        self.stock_bans: Dict[str, dict] = {}
        # Pool breaker states
        self.pool_breakers: Dict[str, BreakerState] = {
            n: BreakerState() for n in POOL_NAMES if n != "RESERVE"}
        # Portfolio-level breaker
        self.portfolio_breaker = BreakerState()
        # Recovery mode
        self.recovery = RecoveryState()
        # Sector tracking {symbol: sector}
        self.symbol_sectors: Dict[str, str] = {}
        # Event log
        self.risk_events: List[dict] = []
        # Daily stats
        self.daily_stats = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "max_dd": 0.0}

    # --- Core decision functions ---

    def check_can_trade(self, pool_name: str, symbol: str) -> Tuple[bool, str]:
        """Pre-trade gate. Returns (allowed, reason)."""
        # ALL-STOP check
        if self.portfolio_breaker.active:
            return False, f"ALL-STOP active (tier {self.portfolio_breaker.tier}): {self.portfolio_breaker.reason}"

        # Pool breaker check
        pb = self.pool_breakers.get(pool_name)
        if pb and pb.active:
            return False, f"Pool {pool_name} breaker active (tier {pb.tier}): {pb.reason}"

        # Pool paused in pool_manager
        pool = self.pm.pools.get(pool_name)
        if pool and pool.paused:
            return False, f"Pool {pool_name} is paused by pool_manager"

        # Stock ban
        ban = self.stock_bans.get(symbol)
        if ban:
            until = ban.get("until", "")
            if until and until > date.today().isoformat():
                return False, f"{symbol} banned until {until}: {ban.get('reason', '')}"
            else:
                del self.stock_bans[symbol]  # expired

        # Max total positions
        total_pos = sum(len(p.positions) for p in self.pm.pools.values())
        if total_pos >= MAX_POSITIONS_TOTAL:
            return False, f"Max {MAX_POSITIONS_TOTAL} total positions reached ({total_pos})"

        # Same-sector guard
        if symbol in self.symbol_sectors:
            sector = self.symbol_sectors[symbol]
            sector_count = sum(
                1 for s, sec in self.symbol_sectors.items()
                if sec == sector and any(
                    pos["symbol"] == s
                    for p in self.pm.pools.values() for pos in p.positions
                )
            )
            if sector_count >= MAX_SAME_SECTOR:
                return False, f"Max {MAX_SAME_SECTOR} stocks from sector '{sector}' already held"

        return True, "OK"

    def get_position_size(self, pool_name: str, base_size: float) -> float:
        """Apply all risk multipliers to base position size."""
        pool = self.pm.pools.get(pool_name)
        if not pool:
            return 0.0

        eff_mult = self.get_effective_multiplier()
        sized = base_size * eff_mult

        # Kelly cap: max 25% of pool capital
        kelly_max = pool.capital * KELLY_CAP
        sized = min(sized, kelly_max)

        # Pool reduced flag halves again
        if pool.reduced:
            sized *= 0.50

        return round(max(0.0, sized), 2)

    def record_trade_result(self, pool_name: str, symbol: str, pnl: float):
        """Update all risk counters after a trade closes."""
        self.daily_stats["trades"] += 1
        self.daily_stats["pnl"] += pnl
        self.daily_stats["max_dd"] = min(self.daily_stats["max_dd"], self.daily_stats["pnl"])

        if pnl >= 0:
            self.daily_stats["wins"] += 1
            self.pool_consec_losses[pool_name] = 0
            self.stock_consec_losses[symbol] = 0
            if self.recovery.active:
                self.recovery.consecutive_profit_days += 1
                if self.recovery.consecutive_profit_days >= RECOVERY_EARLY_RESTORE_DAYS:
                    self._end_recovery("5 consecutive profitable trades")
        else:
            self.daily_stats["losses"] += 1
            self.pool_consec_losses[pool_name] += 1
            self.stock_consec_losses[symbol] += 1
            if self.recovery.active:
                self.recovery.consecutive_profit_days = 0

        self._check_tier_1(pool_name)
        self._check_tier_2(symbol)
        self._check_portfolio_breakers()

        self.risk_events.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": "TRADE_RESULT", "pool": pool_name,
            "symbol": symbol, "pnl": round(pnl, 2),
        })

    def check_all_breakers(self) -> dict:
        """Run comprehensive drawdown checks across all pools. Returns alerts dict."""
        alerts = {}
        today_str = date.today().isoformat()

        # Per-pool drawdown limits
        for name, limits in POOL_LIMITS.items():
            pool = self.pm.pools.get(name)
            if not pool:
                continue
            cap = pool.capital if pool.capital > 0 else 1

            if limits["daily"] and pool.daily_pnl < -limits["daily"] * cap:
                self._fire_pool_breaker(name, 1, f"Daily loss {pool.daily_pnl:,.0f} > {limits['daily']*100}% of pool")
                alerts[name] = f"Daily drawdown limit hit"

            if limits["weekly"] and pool.weekly_pnl < -limits["weekly"] * cap:
                msg = f"Weekly loss {pool.weekly_pnl:,.0f} > {limits['weekly']*100}% of pool"
                if name == "SWING":
                    pool.reduced = True
                    alerts[name] = f"Reduced 50%: {msg}"
                else:
                    self._fire_pool_breaker(name, 1, msg)
                    alerts[name] = msg

            if limits["monthly"] and pool.monthly_pnl < -limits["monthly"] * cap:
                msg = f"Monthly loss > {limits['monthly']*100}%"
                if name == "POSITIONAL":
                    alerts[name] = f"Exit weakest 50%: {msg}"
                elif name == "INVESTMENT":
                    alerts[name] = f"Review only: {msg}"
                else:
                    self._fire_pool_breaker(name, 1, msg)
                    alerts[name] = msg

        # Portfolio-level
        total_daily = sum(p.daily_pnl for p in self.pm.pools.values())
        total_weekly = sum(p.weekly_pnl for p in self.pm.pools.values())
        total_monthly = sum(p.monthly_pnl for p in self.pm.pools.values())
        tc = self.pm.total_capital if self.pm.total_capital > 0 else 1

        if total_daily < -PORTFOLIO_LIMITS["daily"] * tc:
            self._fire_portfolio_breaker(3, "Portfolio daily loss > 1%")
            alerts["PORTFOLIO_DAILY"] = "Tier 3: reduce ALL pools to 50%"

        if total_weekly < -PORTFOLIO_LIMITS["weekly"] * tc:
            self._fire_portfolio_breaker(4, "Portfolio weekly loss > 3%")
            alerts["PORTFOLIO_WEEKLY"] = "Tier 4: pause INTRADAY + SWING 2 days"

        if total_monthly < -PORTFOLIO_LIMITS["monthly"] * tc:
            self._fire_portfolio_breaker(5, "Portfolio monthly loss > 7%")
            alerts["PORTFOLIO_MONTHLY"] = "Tier 5: ALL-STOP"

        return alerts

    def get_effective_multiplier(self) -> float:
        """Combined VIX * recovery * regime multiplier."""
        vix_mult = min(15.0 / max(self.vix, 1.0), 1.0)
        recovery_mult = self.recovery.size_mult if self.recovery.active else 1.0
        regime_mult = {"BULL": 1.0, "SIDEWAYS": 0.85, "BEAR": 0.60}.get(self.regime, 0.85)
        return round(vix_mult * recovery_mult * regime_mult, 4)

    def set_vix(self, vix: float):
        self.vix = max(0.1, vix)

    def set_sector(self, symbol: str, sector: str):
        self.symbol_sectors[symbol] = sector

    def get_risk_dashboard(self) -> dict:
        """Full risk state snapshot for display."""
        return {
            "pool_breakers": {n: vars(b) for n, b in self.pool_breakers.items()},
            "stock_bans": dict(self.stock_bans),
            "portfolio_breaker": vars(self.portfolio_breaker),
            "recovery_mode": vars(self.recovery),
            "vix": self.vix,
            "vix_multiplier": round(min(15.0 / max(self.vix, 1.0), 1.0), 4),
            "effective_size_mult": self.get_effective_multiplier(),
            "regime": self.regime,
            "risk_events": self.risk_events[-20:],
            "daily_stats": dict(self.daily_stats),
            "pool_consec_losses": dict(self.pool_consec_losses),
            "stock_consec_losses": {k: v for k, v in self.stock_consec_losses.items() if v > 0},
        }

    def reset_daily(self):
        """Call at start of each trading day."""
        self.daily_stats = {"trades": 0, "wins": 0, "losses": 0, "pnl": 0.0, "max_dd": 0.0}
        self.pool_consec_losses.clear()
        self.stock_consec_losses.clear()
        # Clear expired stock bans
        today_str = date.today().isoformat()
        self.stock_bans = {s: b for s, b in self.stock_bans.items()
                          if b.get("until", "") > today_str}
        # Clear expired pool breakers (day-only ones)
        for name, pb in self.pool_breakers.items():
            if pb.active and pb.paused_until and pb.paused_until <= today_str:
                pb.active, pb.tier, pb.reason = False, 0, ""
        # Advance recovery day
        if self.recovery.active:
            self.recovery.day += 1
            self.recovery.size_mult = self._recovery_mult(self.recovery.day)
            if self.recovery.day > 14:
                self._end_recovery("15-day ladder complete")

    # --- Internal helpers ---

    def _check_tier_1(self, pool_name: str):
        """Tier 1: 5 consecutive losses in any pool -> pause pool rest of day."""
        if self.pool_consec_losses[pool_name] >= 5:
            self._fire_pool_breaker(pool_name, 1, "5 consecutive losses")

    def _check_tier_2(self, symbol: str):
        """Tier 2: 3 consecutive losses on same stock -> ban stock for the day."""
        if self.stock_consec_losses[symbol] >= 3:
            self.stock_bans[symbol] = {
                "reason": "3 consecutive losses",
                "until": (date.today() + timedelta(days=1)).isoformat(),
            }
            self.risk_events.append({
                "time": datetime.now().strftime("%H:%M:%S"),
                "event": "TIER_2_STOCK_BAN", "symbol": symbol,
                "detail": "3 consecutive losses",
            })

    def _check_portfolio_breakers(self):
        """Check tier 3-5 portfolio-level breakers."""
        tc = self.pm.total_capital if self.pm.total_capital > 0 else 1
        total_daily = sum(p.daily_pnl for p in self.pm.pools.values())
        total_weekly = sum(p.weekly_pnl for p in self.pm.pools.values())
        total_monthly = sum(p.monthly_pnl for p in self.pm.pools.values())

        if total_monthly < -PORTFOLIO_LIMITS["monthly"] * tc:
            self._fire_portfolio_breaker(5, "Portfolio monthly loss > 7% — ALL-STOP")
        elif total_weekly < -PORTFOLIO_LIMITS["weekly"] * tc:
            self._fire_portfolio_breaker(4, "Portfolio weekly loss > 3%")
        elif total_daily < -PORTFOLIO_LIMITS["daily"] * tc:
            self._fire_portfolio_breaker(3, "Portfolio daily loss > 1%")

    def _fire_pool_breaker(self, pool_name: str, tier: int, reason: str):
        pb = self.pool_breakers.get(pool_name)
        if not pb or (pb.active and pb.tier >= tier):
            return
        now_str = datetime.now().strftime("%H:%M:%S")
        pause_until = (date.today() + timedelta(days=1)).isoformat()
        pb.active, pb.tier, pb.triggered_at, pb.reason = True, tier, now_str, reason
        pb.paused_until = pause_until
        # Also pause in pool_manager
        pool = self.pm.pools.get(pool_name)
        if pool:
            pool.paused = True
        self._start_recovery_if_needed()
        self.risk_events.append({
            "time": now_str, "event": f"TIER_{tier}_POOL",
            "pool": pool_name, "detail": reason,
        })

    def _fire_portfolio_breaker(self, tier: int, reason: str):
        if self.portfolio_breaker.active and self.portfolio_breaker.tier >= tier:
            return
        now_str = datetime.now().strftime("%H:%M:%S")
        self.portfolio_breaker = BreakerState(
            active=True, tier=tier, triggered_at=now_str, reason=reason)

        if tier == 3:  # Reduce all to 50%
            for pool in self.pm.pools.values():
                pool.reduced = True
        elif tier == 4:  # Pause INTRADAY + SWING 2 days
            for name in ["INTRADAY", "SWING"]:
                p = self.pm.pools.get(name)
                if p:
                    p.paused = True
                pb = self.pool_breakers.get(name)
                if pb:
                    pb.active = True
                    pb.paused_until = (date.today() + timedelta(days=2)).isoformat()
        elif tier >= 5:  # ALL-STOP
            for pool in self.pm.pools.values():
                pool.paused = True

        self._start_recovery_if_needed()
        self.risk_events.append({
            "time": now_str, "event": f"TIER_{tier}_PORTFOLIO", "detail": reason,
        })

    def _start_recovery_if_needed(self):
        if not self.recovery.active:
            self.recovery = RecoveryState(
                active=True, day=0, size_mult=0.25,
                started=date.today().isoformat(), consecutive_profit_days=0)

    def _end_recovery(self, reason: str):
        self.recovery = RecoveryState()
        self.risk_events.append({
            "time": datetime.now().strftime("%H:%M:%S"),
            "event": "RECOVERY_END", "detail": reason,
        })

    @staticmethod
    def _recovery_mult(day: int) -> float:
        for threshold, mult in RECOVERY_LADDER:
            if day <= threshold:
                return mult
        return 1.0

    # --- Persistence (alongside pool state) ---

    def save(self, path: Optional[Path] = None) -> str:
        if path is None:
            PERSIST_DIR.mkdir(parents=True, exist_ok=True)
            path = PERSIST_DIR / f"{date.today().isoformat()}.json"
        # Load existing file to merge with pool_manager state
        existing = {}
        if path.exists():
            try:
                existing = json.loads(path.read_text())
            except (json.JSONDecodeError, OSError):
                pass
        existing["risk_state"] = {
            "saved_at": datetime.now().isoformat(),
            "regime": self.regime, "vix": self.vix,
            "pool_breakers": {n: vars(b) for n, b in self.pool_breakers.items()},
            "portfolio_breaker": vars(self.portfolio_breaker),
            "stock_bans": self.stock_bans,
            "recovery": vars(self.recovery),
            "pool_consec_losses": dict(self.pool_consec_losses),
            "stock_consec_losses": dict(self.stock_consec_losses),
            "symbol_sectors": self.symbol_sectors,
            "risk_events": self.risk_events[-50:],
            "daily_stats": self.daily_stats,
        }
        path.write_text(json.dumps(existing, indent=2))
        return str(path)

    def load(self, path: Optional[Path] = None):
        if path is None:
            files = sorted(PERSIST_DIR.glob("*.json"))
            if not files:
                return
            path = files[-1]
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError, FileNotFoundError):
            return
        rs = data.get("risk_state")
        if not rs:
            return
        self.regime = rs.get("regime", self.regime)
        self.vix = rs.get("vix", self.vix)
        self.stock_bans = rs.get("stock_bans", {})
        self.symbol_sectors = rs.get("symbol_sectors", {})
        self.risk_events = rs.get("risk_events", [])
        self.daily_stats = rs.get("daily_stats", self.daily_stats)
        self.pool_consec_losses = defaultdict(int, rs.get("pool_consec_losses", {}))
        self.stock_consec_losses = defaultdict(int, rs.get("stock_consec_losses", {}))
        # Restore breakers
        for name, bdata in rs.get("pool_breakers", {}).items():
            if name in self.pool_breakers:
                self.pool_breakers[name] = BreakerState(**bdata)
        pb = rs.get("portfolio_breaker", {})
        if pb:
            self.portfolio_breaker = BreakerState(**pb)
        rec = rs.get("recovery", {})
        if rec:
            self.recovery = RecoveryState(**rec)


# --- CLI ---

def _fmt_inr(val: float) -> str:
    if abs(val) >= 1_00_000:
        return f"Rs {val / 1_00_000:,.2f}L"
    return f"Rs {val:,.0f}"

def _print_dashboard(rm: RiskManager):
    d = rm.get_risk_dashboard()
    print(f"\n{'='*64}")
    print(f"  TradePilot v5 Risk Manager Dashboard")
    print(f"  VIX: {d['vix']:.1f}  |  Regime: {d['regime']}  |  "
          f"Eff. Mult: {d['effective_size_mult']:.2f}")
    print(f"{'='*64}")

    ds = d["daily_stats"]
    wr = ds["wins"] / ds["trades"] * 100 if ds["trades"] else 0
    print(f"  Today: {ds['trades']} trades, {ds['wins']}W/{ds['losses']}L "
          f"({wr:.0f}%), PnL: {_fmt_inr(ds['pnl'])}, MaxDD: {_fmt_inr(ds['max_dd'])}")

    # Portfolio breaker
    pb = d["portfolio_breaker"]
    if pb["active"]:
        print(f"\n  ** PORTFOLIO BREAKER ** Tier {pb['tier']}: {pb['reason']}")

    # Recovery
    rec = d["recovery_mode"]
    if rec["active"]:
        print(f"  ** RECOVERY MODE ** Day {rec['day']}, Size: {rec['size_mult']*100:.0f}%, "
              f"Consec profits: {rec['consecutive_profit_days']}")

    # Pool breakers
    print(f"\n  {'Pool':<13} {'Breaker':<8} {'Tier':>5} {'Reason':<30}")
    print(f"  {'-'*13} {'-'*8} {'-'*5} {'-'*30}")
    for name, b in d["pool_breakers"].items():
        status = "ACTIVE" if b["active"] else "clear"
        tier = str(b["tier"]) if b["active"] else "-"
        reason = b["reason"][:30] if b["active"] else ""
        print(f"  {name:<13} {status:<8} {tier:>5} {reason:<30}")

    # Stock bans
    if d["stock_bans"]:
        print(f"\n  Stock Bans:")
        for sym, info in d["stock_bans"].items():
            print(f"    {sym}: {info.get('reason', '')} (until {info.get('until', '?')})")

    # Recent events
    events = d["risk_events"]
    if events:
        print(f"\n  Recent Risk Events (last {len(events)}):")
        for e in events[-5:]:
            print(f"    [{e.get('time','')}] {e.get('event','')} "
                  f"{e.get('pool', e.get('symbol', ''))} — {e.get('detail', e.get('pnl', ''))}")
    print()


def _simulate_losses(rm: RiskManager, count: int):
    """Simulate consecutive losses to demo breaker tiers."""
    print(f"\nSimulating {count} consecutive losses across INTRADAY pool...")
    pool = rm.pm.pools.get("INTRADAY")
    if pool:
        per_loss = pool.capital * 0.004  # 0.4% per loss
    else:
        per_loss = 5000

    for i in range(1, count + 1):
        symbol = f"SIM_STOCK_{(i-1) % 3 + 1}"  # rotate 3 stocks
        rm.record_trade_result("INTRADAY", symbol, -per_loss)
        # Also update pool PnL in pool_manager
        if pool:
            pool.daily_pnl -= per_loss
            pool.weekly_pnl -= per_loss
            pool.monthly_pnl -= per_loss
            pool.capital -= per_loss
            rm.pm.total_capital -= per_loss

        allowed, reason = rm.check_can_trade("INTRADAY", symbol)
        alerts = rm.check_all_breakers()
        tier_str = ""
        if rm.portfolio_breaker.active:
            tier_str = f" [PORTFOLIO TIER {rm.portfolio_breaker.tier}]"
        pb = rm.pool_breakers.get("INTRADAY")
        if pb and pb.active:
            tier_str += f" [POOL TIER {pb.tier}]"
        status = "BLOCKED" if not allowed else "allowed"
        print(f"  Loss #{i}: -{_fmt_inr(per_loss)} | Can trade: {status} "
              f"| Consec: {rm.pool_consec_losses['INTRADAY']}{tier_str}")
        if reason != "OK":
            print(f"           Reason: {reason}")
        if alerts:
            for k, v in alerts.items():
                print(f"           Alert [{k}]: {v}")

    print(f"\nFinal effective multiplier: {rm.get_effective_multiplier():.4f}")
    _print_dashboard(rm)


def main():
    ap = argparse.ArgumentParser(description="TradePilot v5 Risk Manager")
    ap.add_argument("--status", action="store_true", help="Show risk dashboard")
    ap.add_argument("--simulate-losses", type=int, metavar="N",
                    help="Simulate N consecutive losses to test breakers")
    ap.add_argument("--vix", type=float, default=15.0, help="Current VIX level")
    ap.add_argument("--regime", type=str, default="SIDEWAYS", help="BULL/SIDEWAYS/BEAR")
    ap.add_argument("--capital", type=float, default=5_000_000)
    a = ap.parse_args()

    # Try loading existing pool state
    try:
        from .pool_manager import PoolManager as PM
        files = sorted(PERSIST_DIR.glob("*.json"))
        if files:
            pm = PM.load(files[-1])
        else:
            pm = PM(total_capital=a.capital)
    except (ImportError, Exception):
        pm = PoolManager(total_capital=a.capital)

    rm = RiskManager(pm, regime=a.regime, vix=a.vix)
    rm.load()

    if a.simulate_losses:
        _simulate_losses(rm, a.simulate_losses)
        rm.save()
    elif a.status:
        _print_dashboard(rm)
    else:
        _print_dashboard(rm)


if __name__ == "__main__":
    main()
