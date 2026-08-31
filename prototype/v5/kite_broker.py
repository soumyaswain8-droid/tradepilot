#!/usr/bin/env python3
"""
kite_broker — Zerodha Kite Connect adapter for TradePilot (India).

CURRENT MODE: LIVE DATA + SIMULATED ORDERS. No real order can be placed.

Three states, and you cannot reach the third by accident:

  1. DATA_ONLY   (default, no credentials)  — nothing works, everything degrades to
                 the existing yfinance path. Safe to import anywhere.
  2. PAPER       (credentials present)      — real Kite market data, real order
                 VALIDATION against Kite's rules, but orders are simulated locally
                 and never submitted. This is where we start.
  3. LIVE        (credentials + KITE_LIVE_ORDERS=1 + live_confirm token)
                 — real money. Requires TWO independent env flags plus an explicit
                 per-session confirmation string. See _live_allowed().

WHY THE TRIPLE GATE: every engine in this repo is paper-only and has never placed a
real order. The failure modes of live execution (partial fills, rejected orders,
stale positions, double-submits on retry) are entirely untested here. A single
boolean would be one typo away from real money.

SAFETY RAILS, enforced in this module rather than trusted to strategy code:
  - MAX_ORDER_VALUE      per-order rupee cap
  - MAX_DAILY_LOSS       cumulative realised loss that halts trading for the day
  - MAX_OPEN_POSITIONS   hard position count cap
  - kill switch file     presence of KILL_SWITCH halts everything immediately

Setup (once you have Kite Connect):
    pip install kiteconnect
    # in .env:
    KITE_API_KEY=...
    KITE_API_SECRET=...
    KITE_ACCESS_TOKEN=...     # regenerated daily via the login flow
Then: python3 scripts/kite-check.py
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)
ROOT = Path(__file__).resolve().parents[2]
KILL_SWITCH = ROOT / "KILL_SWITCH"

# ── safety rails (rupees) ───────────────────────────────────────────────────
# Read .env as well as the process environment. These were os.environ-only until
# 2026-08-31, and NOTHING in this codebase loads .env into the environment — so a rail
# written to .env was silently inert and the hardcoded defaults stayed in force. The
# caps are the last thing standing between a bug and the account, and a cap that
# quietly ignores its own configuration is worse than no cap, because it reports a
# number it is not enforcing. Found while sizing a Rs25,000 book: .env said 3200/1250/8
# and the broker was still reporting 5000/1000/5.
#
# os.environ wins over the file, so an operator can still override for one run.
def _rail(name: str, default: str) -> str:
    if os.environ.get(name):
        return os.environ[name]
    envf = ROOT / ".env"
    if envf.exists():
        for ln in envf.read_text().splitlines():
            if ln.startswith(f"{name}=") and "=" in ln:
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return default


MAX_ORDER_VALUE = float(_rail("KITE_MAX_ORDER_VALUE", "5000"))
MAX_DAILY_LOSS = float(_rail("KITE_MAX_DAILY_LOSS", "1000"))
MAX_OPEN_POSITIONS = int(_rail("KITE_MAX_OPEN_POSITIONS", "5"))


class KillSwitchActive(Exception):
    """KILL_SWITCH file exists — all trading halted."""


class SafetyRailBreached(Exception):
    """An order exceeded a configured limit. Never downgrade this to a warning."""


class LiveOrdersBlocked(Exception):
    """A real order was attempted without passing the full triple gate."""


def _env(name: str) -> Optional[str]:
    v = os.environ.get(name)
    if v:
        return v
    envf = ROOT / ".env"
    if envf.exists():
        for ln in envf.read_text().splitlines():
            ln = ln.strip()
            if ln.startswith(f"{name}="):
                return ln.split("=", 1)[1].strip().strip('"').strip("'")
    return None


def credentials() -> dict:
    return {"api_key": _env("KITE_API_KEY"),
            "api_secret": _env("KITE_API_SECRET"),
            "access_token": _env("KITE_ACCESS_TOKEN")}


def sdk_available() -> bool:
    try:
        import kiteconnect  # noqa: F401
        return True
    except ImportError:
        return False


def mode() -> str:
    """DATA_ONLY | PAPER | LIVE — the single source of truth for what is enabled."""
    c = credentials()
    if not (c["api_key"] and c["access_token"] and sdk_available()):
        return "DATA_ONLY"
    return "LIVE" if _live_allowed() else "PAPER"


def _live_allowed() -> bool:
    """Real orders require ALL THREE. Any one missing => simulated.

    Deliberately verbose: a reader should be able to see at a glance that reaching
    LIVE is a decision, not a default.
    """
    if os.environ.get("KITE_LIVE_ORDERS") != "1":
        return False
    if os.environ.get("KITE_LIVE_CONFIRM") != "I_UNDERSTAND_REAL_MONEY":
        return False
    if KILL_SWITCH.exists():
        return False
    return True


@dataclass
class Order:
    symbol: str
    side: str
    qty: int
    price: float
    ts: str
    simulated: bool = True
    order_id: Optional[str] = None
    note: str = ""


@dataclass
class KiteBroker:
    """Kite adapter. Defaults to the safest possible behaviour."""
    _kite: object = None
    daily_realised: float = 0.0
    open_positions: int = 0
    orders: list = field(default_factory=list)

    # ── connection ──────────────────────────────────────────────────────────
    def connect(self):
        c = credentials()
        missing = [k for k, v in c.items() if not v and k != "api_secret"]
        if missing:
            raise RuntimeError(f"Kite not configured — missing {missing}. "
                               f"Run scripts/kite-check.py for setup steps.")
        if not sdk_available():
            raise RuntimeError("kiteconnect not installed — pip install kiteconnect")
        from kiteconnect import KiteConnect
        k = KiteConnect(api_key=c["api_key"])
        k.set_access_token(c["access_token"])
        self._kite = k
        return k

    # ── market data (safe: read-only) ───────────────────────────────────────
    def quotes(self, symbols) -> dict:
        """Live quotes from Kite. Returns {} rather than raising, so a data failure
        degrades to the existing yfinance path instead of stopping an engine."""
        try:
            if self._kite is None:
                self.connect()
            keys = [f"NSE:{s}" for s in symbols]
            raw = self._kite.quote(keys)
            out = {}
            for k, v in raw.items():
                sym = k.split(":", 1)[1]
                last = v.get("last_price", 0)
                prev = (v.get("ohlc") or {}).get("close", 0)
                if last <= 0 or prev <= 0:
                    continue                      # omit, never fabricate a price
                out[sym] = {"price": round(last, 2), "prev_close": round(prev, 2),
                            "change_pct": round((last - prev) / prev * 100, 2)}
            return out
        except Exception as e:
            logger.error(f"kite quotes failed: {type(e).__name__}: {e}")
            return {}

    # ── safety ──────────────────────────────────────────────────────────────
    def _check_rails(self, symbol: str, qty: int, price: float) -> None:
        if KILL_SWITCH.exists():
            raise KillSwitchActive(f"KILL_SWITCH present at {KILL_SWITCH} — halted")
        value = qty * price
        if value > MAX_ORDER_VALUE:
            raise SafetyRailBreached(
                f"order value Rs {value:,.0f} exceeds MAX_ORDER_VALUE Rs {MAX_ORDER_VALUE:,.0f}")
        if self.daily_realised <= -abs(MAX_DAILY_LOSS):
            raise SafetyRailBreached(
                f"daily realised Rs {self.daily_realised:,.0f} breached "
                f"MAX_DAILY_LOSS Rs {MAX_DAILY_LOSS:,.0f} — trading halted for the day")
        if self.open_positions >= MAX_OPEN_POSITIONS:
            raise SafetyRailBreached(
                f"open positions {self.open_positions} at cap {MAX_OPEN_POSITIONS}")

    # ── orders ──────────────────────────────────────────────────────────────
    def place_order(self, symbol: str, side: str, qty: int, price: float) -> Order:
        """Validate against the rails, then EITHER simulate (default) or submit.

        Submission requires the full triple gate. Everything else is simulated and
        recorded identically, so the engine code path is the same in both modes —
        which is the point: when we do go live, nothing about the caller changes.
        """
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError(f"unsupported side {side!r}")
        self._check_rails(symbol, qty, price)

        if not _live_allowed():
            o = Order(symbol=symbol, side=side, qty=qty, price=round(price, 2),
                      ts=datetime.now().isoformat(timespec="seconds"),
                      simulated=True, note=f"SIMULATED (mode={mode()})")
            self.orders.append(o)
            return o

        # ── real money past this point ──
        if self._kite is None:
            self.connect()
        logger.warning(f"LIVE ORDER {side} {qty} {symbol} @ {price}")
        oid = self._kite.place_order(
            variety="regular", exchange="NSE", tradingsymbol=symbol,
            transaction_type=side.upper(), quantity=qty,
            product="CNC", order_type="MARKET")
        o = Order(symbol=symbol, side=side, qty=qty, price=round(price, 2),
                  ts=datetime.now().isoformat(timespec="seconds"),
                  simulated=False, order_id=str(oid), note="LIVE")
        self.orders.append(o)
        return o

    def status(self) -> dict:
        c = credentials()
        return {
            "mode": mode(),
            "sdk_installed": sdk_available(),
            "has_api_key": bool(c["api_key"]),
            "has_access_token": bool(c["access_token"]),
            "live_orders_env": os.environ.get("KITE_LIVE_ORDERS") == "1",
            "live_confirm_env": os.environ.get("KITE_LIVE_CONFIRM") == "I_UNDERSTAND_REAL_MONEY",
            "kill_switch": KILL_SWITCH.exists(),
            "rails": {"max_order_value": MAX_ORDER_VALUE,
                      "max_daily_loss": MAX_DAILY_LOSS,
                      "max_open_positions": MAX_OPEN_POSITIONS},
        }
