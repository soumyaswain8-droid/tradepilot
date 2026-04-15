"""TradePilot v5 — Multi-Horizon Pool Manager
Capital allocation: 4 pools + reserve, regime shifts, circuit breakers, profit waterfall.
CLI: python3 -m prototype.v5.pool_manager --status | --regime BEAR | --rebalance | --waterfall
"""

import json, argparse
from pathlib import Path
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from typing import Dict, List, Optional

POOL_NAMES = ["INTRADAY", "SWING", "POSITIONAL", "INVESTMENT", "RESERVE"]
DEFAULT_ALLOC = {"INTRADAY": 0.30, "SWING": 0.25, "POSITIONAL": 0.25,
                 "INVESTMENT": 0.15, "RESERVE": 0.05}
REGIME_ALLOC = {
    "BULL":     {"INTRADAY": 0.30, "SWING": 0.30, "POSITIONAL": 0.25, "INVESTMENT": 0.15, "RESERVE": 0.00},
    "SIDEWAYS": {"INTRADAY": 0.35, "SWING": 0.20, "POSITIONAL": 0.20, "INVESTMENT": 0.15, "RESERVE": 0.10},
    "BEAR":     {"INTRADAY": 0.25, "SWING": 0.15, "POSITIONAL": 0.10, "INVESTMENT": 0.20, "RESERVE": 0.30},
}
WATERFALL = {  # source -> [(dest, fraction)]
    "INTRADAY":   [("INTRADAY", 0.50), ("SWING", 0.30), ("POSITIONAL", 0.20)],
    "SWING":      [("SWING", 0.60), ("INVESTMENT", 0.40)],
    "POSITIONAL": [("POSITIONAL", 0.70), ("INVESTMENT", 0.30)],
    "INVESTMENT": [("INVESTMENT", 1.00)],
}
PERSIST_DIR = Path.home() / "Documents/tinker/projects/tradepilot/docs/paper-trades/v5"

@dataclass
class Pool:
    name: str
    target_pct: float
    capital: float          # total assigned capital
    deployed: float = 0.0   # capital in open positions
    positions: List[dict] = field(default_factory=list)
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0
    paused: bool = False
    reduced: bool = False
    reduced_until: str = ""
    consecutive_profit_days: int = 0

    @property
    def cash(self) -> float:
        return self.capital - self.deployed

class PoolManager:
    def __init__(self, total_capital: float = 5_000_000):
        self.total_capital = total_capital
        self.regime = "SIDEWAYS"
        self.alloc = dict(DEFAULT_ALLOC)
        self.pools: Dict[str, Pool] = {}
        self._init_pools()
        self.trade_log: List[dict] = []
        self.last_rebalance = date.today().isoformat()

    def _init_pools(self):
        for name in POOL_NAMES:
            pct = self.alloc[name]
            self.pools[name] = Pool(name=name, target_pct=pct,
                                    capital=self.total_capital * pct)

    def set_regime(self, regime: str):
        regime = regime.upper()
        if regime not in REGIME_ALLOC:
            raise ValueError(f"Unknown regime: {regime}. Use BULL/SIDEWAYS/BEAR")
        self.regime = regime
        self.alloc = dict(REGIME_ALLOC[regime])
        for name, pool in self.pools.items():
            pool.target_pct = self.alloc[name]

    def get_pool_budget(self, pool_name: str) -> float:
        pool = self.pools[pool_name]
        if pool.paused:
            return 0.0
        available = pool.cash
        if pool.reduced:
            available *= 0.75
        return max(0.0, available)

    def deploy(self, pool_name: str, symbol: str, qty: int, price: float,
               sl: float, target: float) -> bool:
        pool = self.pools[pool_name]
        cost = qty * price
        if pool.paused:
            return False
        if cost > self.get_pool_budget(pool_name):
            return False
        pos = {"symbol": symbol, "qty": qty, "entry_price": price,
               "sl": sl, "target": target, "pool": pool_name,
               "entry_time": datetime.now().isoformat()}
        pool.positions.append(pos)
        pool.deployed += cost
        self.trade_log.append({**pos, "action": "OPEN"})
        return True

    def close_position(self, pool_name: str, symbol: str,
                       exit_price: float, reason: str = "manual") -> dict:
        pool = self.pools[pool_name]
        pos = next((p for p in pool.positions if p["symbol"] == symbol), None)
        if pos is None:
            return {"error": f"{symbol} not found in {pool_name}"}
        pnl = (exit_price - pos["entry_price"]) * pos["qty"]
        cost = pos["qty"] * pos["entry_price"]
        pool.deployed -= cost
        pool.capital += pnl
        pool.daily_pnl += pnl
        pool.weekly_pnl += pnl
        pool.monthly_pnl += pnl
        self.total_capital += pnl
        pool.positions = [p for p in pool.positions if p["symbol"] != symbol]
        result = {"symbol": symbol, "pool": pool_name, "pnl": round(pnl, 2),
                  "exit_price": exit_price, "reason": reason,
                  "exit_time": datetime.now().isoformat()}
        self.trade_log.append({**result, "action": "CLOSE"})
        return result

    def check_circuit_breakers(self) -> dict:
        alerts = {}
        # Portfolio-level ALL-STOP
        total_monthly = sum(p.monthly_pnl for p in self.pools.values())
        if total_monthly < -0.07 * self.total_capital:
            for p in self.pools.values():
                p.paused = True
            alerts["PORTFOLIO"] = "ALL-STOP: monthly loss > 7%"
            return alerts

        p = self.pools["INTRADAY"]
        if p.daily_pnl < -0.02 * p.capital and not p.paused:
            p.paused = True
            alerts["INTRADAY"] = "Paused: daily loss > 2%"

        p = self.pools["SWING"]
        if p.weekly_pnl < -0.03 * p.capital and not p.reduced:
            p.reduced = True
            p.reduced_until = (date.today() + timedelta(weeks=2)).isoformat()
            alerts["SWING"] = "Reduced 50%: weekly loss > 3%"

        p = self.pools["POSITIONAL"]
        if p.monthly_pnl < -0.10 * p.capital and p.positions:
            # Exit weakest 50% by unrealised PnL (mark-to-market not available,
            # flag for review — real exit needs market price)
            n_exit = max(1, len(p.positions) // 2)
            alerts["POSITIONAL"] = f"Review: exit weakest {n_exit} positions"

        if self.pools["INVESTMENT"].monthly_pnl < -0.10 * self.pools["INVESTMENT"].capital:
            alerts["INVESTMENT"] = "Review only: monthly loss > 10%"

        return alerts

    def rebalance(self) -> dict:
        result = {"drift": {}, "actions": []}
        for name, pool in self.pools.items():
            target_cap = self.total_capital * pool.target_pct
            drift_pct = (pool.capital - target_cap) / target_cap * 100 if target_cap else 0
            result["drift"][name] = round(drift_pct, 2)
            if abs(drift_pct) > 5:
                delta = target_cap - pool.capital
                pool.capital += delta
                result["actions"].append(
                    f"{name}: {'added' if delta > 0 else 'removed'} "
                    f"Rs {abs(delta):,.0f} (drift was {drift_pct:+.1f}%)")
        self.last_rebalance = date.today().isoformat()
        return result

    def apply_profit_waterfall(self) -> dict:
        flows = {}
        for src_name, rules in WATERFALL.items():
            pool = self.pools[src_name]
            profit = pool.monthly_pnl
            if profit <= 0:
                continue
            flows[src_name] = []
            for dest_name, frac in rules:
                amount = profit * frac
                if dest_name != src_name:
                    pool.capital -= amount
                    self.pools[dest_name].capital += amount
                flows[src_name].append(
                    {"to": dest_name, "amount": round(amount, 2)})
        # Reset monthly PnL after waterfall
        for p in self.pools.values():
            p.monthly_pnl = 0.0
        return flows

    def end_of_day(self):
        """Reset daily PnL, check consecutive profit days for reduced pools."""
        for p in self.pools.values():
            if p.daily_pnl > 0:
                p.consecutive_profit_days += 1
            else:
                p.consecutive_profit_days = 0
            # Restore from reduced after 5 consecutive profit days
            if p.reduced and p.consecutive_profit_days >= 5:
                p.reduced = False
                p.reduced_until = ""
                p.consecutive_profit_days = 0
            p.daily_pnl = 0.0

    def end_of_week(self):
        for p in self.pools.values():
            p.weekly_pnl = 0.0

    def get_status(self) -> dict:
        pools_status = {}
        for name, p in self.pools.items():
            pools_status[name] = {
                "target_pct": p.target_pct, "capital": round(p.capital, 2),
                "deployed": round(p.deployed, 2), "cash": round(p.cash, 2),
                "positions": len(p.positions), "daily_pnl": round(p.daily_pnl, 2),
                "weekly_pnl": round(p.weekly_pnl, 2),
                "monthly_pnl": round(p.monthly_pnl, 2),
                "paused": p.paused, "reduced": p.reduced,
            }
        return {
            "total_capital": round(self.total_capital, 2),
            "regime": self.regime,
            "last_rebalance": self.last_rebalance,
            "pools": pools_status,
            "open_positions": sum(len(p.positions) for p in self.pools.values()),
        }

    def save(self, path: Optional[Path] = None):
        if path is None:
            PERSIST_DIR.mkdir(parents=True, exist_ok=True)
            path = PERSIST_DIR / f"{date.today().isoformat()}.json"
        state = {
            "saved_at": datetime.now().isoformat(),
            "total_capital": self.total_capital,
            "regime": self.regime,
            "alloc": self.alloc,
            "last_rebalance": self.last_rebalance,
            "pools": {},
            "trade_log": self.trade_log[-100:],   # keep last 100 trades
        }
        for name, p in self.pools.items():
            state["pools"][name] = {
                "capital": p.capital, "deployed": p.deployed,
                "target_pct": p.target_pct, "positions": p.positions,
                "daily_pnl": p.daily_pnl, "weekly_pnl": p.weekly_pnl,
                "monthly_pnl": p.monthly_pnl, "paused": p.paused,
                "reduced": p.reduced, "reduced_until": p.reduced_until,
                "consecutive_profit_days": p.consecutive_profit_days,
            }
        path.write_text(json.dumps(state, indent=2))
        return str(path)

    @classmethod
    def load(cls, path: Optional[Path] = None) -> "PoolManager":
        if path is None:
            files = sorted(PERSIST_DIR.glob("*.json"))
            if not files:
                return cls()
            path = files[-1]
        state = json.loads(path.read_text())
        mgr = cls.__new__(cls)
        mgr.total_capital = state["total_capital"]
        mgr.regime = state["regime"]
        mgr.alloc = state["alloc"]
        mgr.last_rebalance = state.get("last_rebalance", date.today().isoformat())
        mgr.trade_log = state.get("trade_log", [])
        mgr.pools = {}
        for name in POOL_NAMES:
            ps = state["pools"][name]
            mgr.pools[name] = Pool(
                name=name, target_pct=ps["target_pct"], capital=ps["capital"],
                deployed=ps["deployed"], positions=ps.get("positions", []),
                daily_pnl=ps.get("daily_pnl", 0), weekly_pnl=ps.get("weekly_pnl", 0),
                monthly_pnl=ps.get("monthly_pnl", 0), paused=ps.get("paused", False),
                reduced=ps.get("reduced", False),
                reduced_until=ps.get("reduced_until", ""),
                consecutive_profit_days=ps.get("consecutive_profit_days", 0),
            )
        return mgr

def _fmt_inr(val: float) -> str:
    """Format as Indian Rupees with lakhs notation."""
    if abs(val) >= 1_00_000:
        return f"Rs {val / 1_00_000:,.2f}L"
    return f"Rs {val:,.0f}"

def _print_status(mgr: PoolManager):
    s = mgr.get_status()
    print(f"\n{'='*60}")
    print(f"  TradePilot v5 Pool Manager")
    print(f"  Capital: {_fmt_inr(s['total_capital'])}  |  "
          f"Regime: {s['regime']}  |  Positions: {s['open_positions']}")
    print(f"{'='*60}")
    print(f"{'Pool':<13} {'Target':>7} {'Capital':>12} {'Deployed':>12} "
          f"{'Cash':>12} {'DayPnL':>10} {'Status':<10}")
    print(f"{'-'*13} {'-'*7} {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*10}")
    for name, p in s["pools"].items():
        status = "PAUSED" if p["paused"] else ("REDUCED" if p["reduced"] else "ACTIVE")
        pnl_str = f"{p['daily_pnl']:+,.0f}"
        print(f"{name:<13} {p['target_pct']*100:>6.0f}% "
              f"{_fmt_inr(p['capital']):>12} {_fmt_inr(p['deployed']):>12} "
              f"{_fmt_inr(p['cash']):>12} {pnl_str:>10} {status:<10}")
    print()

def main():
    ap = argparse.ArgumentParser(description="TradePilot v5 Pool Manager")
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--regime", type=str, help="BULL/SIDEWAYS/BEAR")
    ap.add_argument("--rebalance", action="store_true")
    ap.add_argument("--waterfall", action="store_true")
    ap.add_argument("--breakers", action="store_true")
    ap.add_argument("--capital", type=float, default=None)
    ap.add_argument("--fresh", action="store_true", help="Ignore saved state")
    a = ap.parse_args()

    if a.fresh or not list(PERSIST_DIR.glob("*.json")):
        mgr = PoolManager(total_capital=a.capital or 5_000_000)
    else:
        mgr = PoolManager.load()
        if a.capital: mgr.total_capital = a.capital

    if a.regime:
        mgr.set_regime(a.regime); print(f"Regime set to {mgr.regime}")
    if a.rebalance:
        r = mgr.rebalance()
        for act in r["actions"]: print(f"  {act}")
        if not r["actions"]: print("No rebalance needed (within 5% drift)")
    if a.waterfall:
        flows = mgr.apply_profit_waterfall()
        for src, dests in flows.items():
            for d in dests: print(f"  {src} -> {d['to']}: {_fmt_inr(d['amount'])}")
        if not flows: print("No profits to redistribute")
    if a.breakers:
        alerts = mgr.check_circuit_breakers()
        for pool, msg in alerts.items(): print(f"  [{pool}] {msg}")
        if not alerts: print("All circuit breakers clear")
    if a.status or not any([a.regime, a.rebalance, a.waterfall, a.breakers]):
        _print_status(mgr)
    print(f"State saved: {mgr.save()}")

if __name__ == "__main__":
    main()
