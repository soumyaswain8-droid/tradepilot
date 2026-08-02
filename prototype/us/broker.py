#!/usr/bin/env python3
"""
broker — execution adapters for the US module.

Two implementations behind one interface:

  SimBroker    (default) — internal simulated fills against the data layer's prices.
                Needs no account, no keys, no network beyond price data. This is how
                the India engines already paper-trade, and it is what makes a US
                paper session possible tonight.

  AlpacaBroker (optional) — real paper orders via Alpaca's paper API. Alpaca is the
                only broker found whose paper API needs NO funding and NO KYC
                (VERIFIED 2026-08-02); IBKR's paper requires a funded live account.
                Unconfigured by default: without ALPACA_API_KEY/ALPACA_SECRET_KEY it
                raises a clear error rather than silently doing nothing.

WHY AN INTERFACE AT ALL: every live-trading path is legally unresolved for an Indian
resident right now (Alpaca's own docs contradict themselves on India residency;
Tradier contradicts itself on US-citizen requirements; Schwab could not be verified).
Committing the engine to one broker would be a bet on an unanswered question.

HARD CONSTRAINT: place_order() rejects any side other than "buy"/"sell" of an
existing long. RBI bars LRS remittance for margin and margin calls, so shorting is
not merely unprofitable here — it is outside the permitted lane. The rejection is in
code so no strategy change can accidentally cross it.
"""
from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)


class ShortSellingBlocked(Exception):
    """Raised on any attempt to open a short. See module docstring — this is a
    regulatory boundary (RBI LRS margin ban), not a strategy preference."""


@dataclass
class Fill:
    symbol: str
    side: str          # "buy" | "sell"
    qty: int
    price: float
    ts: str
    commission: float = 0.0
    note: str = ""


@dataclass
class BrokerBase:
    name: str = "base"
    orders_enabled: bool = False

    def place_order(self, symbol: str, side: str, qty: int, price: float) -> Optional[Fill]:
        raise NotImplementedError

    def _guard(self, side: str, qty: int, holding_qty: int) -> None:
        side = side.lower()
        if side not in ("buy", "sell"):
            raise ValueError(f"unsupported side {side!r} — long-only cash lane")
        if side == "sell" and qty > holding_qty:
            raise ShortSellingBlocked(
                f"sell {qty} of {holding_qty} held would open a short. Blocked: RBI bars "
                f"LRS remittance for margin/margin calls, so the permitted lane is "
                f"long-only cash. See docs/research/us-market/04-regulatory-lrs-tax.md"
            )


@dataclass
class SimBroker(BrokerBase):
    """Internal simulator. Fills at the supplied price with a configurable slippage
    and commission so paper P&L is not flattered by assuming perfect fills."""
    name: str = "sim"
    orders_enabled: bool = True
    slippage_bps: float = 2.0        # 2bps — US large-cap spreads are tight
    commission_per_share: float = 0.0  # most US retail brokers are $0 commission
    fills: list = field(default_factory=list)

    def place_order(self, symbol: str, side: str, qty: int, price: float,
                    holding_qty: int = 0) -> Optional[Fill]:
        self._guard(side, qty, holding_qty)
        if qty <= 0 or price <= 0:
            return None
        slip = price * (self.slippage_bps / 10_000.0)
        fill_px = price + slip if side.lower() == "buy" else price - slip
        f = Fill(symbol=symbol, side=side.lower(), qty=int(qty), price=round(fill_px, 4),
                 ts=datetime.now().isoformat(timespec="seconds"),
                 commission=round(self.commission_per_share * qty, 4),
                 note=f"sim fill, {self.slippage_bps}bps slippage")
        self.fills.append(f)
        return f


@dataclass
class AlpacaBroker(BrokerBase):
    """Alpaca paper-trading adapter. NOT configured until keys exist.

    To enable:
      1. sign up at alpaca.markets (paper needs no funding and no KYC)
      2. generate paper API keys
      3. put ALPACA_API_KEY / ALPACA_SECRET_KEY in .env
      4. pip install alpaca-py
    Base URL is the paper host; this adapter never points at live.
    """
    name: str = "alpaca_paper"
    orders_enabled: bool = False
    base_url: str = "https://paper-api.alpaca.markets"
    _client: object = None

    def configured(self) -> tuple:
        key = os.environ.get("ALPACA_API_KEY")
        sec = os.environ.get("ALPACA_SECRET_KEY")
        missing = [n for n, v in (("ALPACA_API_KEY", key), ("ALPACA_SECRET_KEY", sec)) if not v]
        try:
            import alpaca  # noqa: F401
            sdk = True
        except ImportError:
            sdk = False
        return (not missing and sdk), {"missing_env": missing, "sdk_installed": sdk}

    def connect(self):
        ok, detail = self.configured()
        if not ok:
            raise RuntimeError(
                f"Alpaca paper not configured: {detail}. "
                f"Paper access needs no funding and no KYC — sign up at alpaca.markets, "
                f"generate paper keys, add them to .env, and `pip install alpaca-py`."
            )
        from alpaca.trading.client import TradingClient
        self._client = TradingClient(os.environ["ALPACA_API_KEY"],
                                     os.environ["ALPACA_SECRET_KEY"], paper=True)
        self.orders_enabled = True
        return self._client

    def place_order(self, symbol: str, side: str, qty: int, price: float,
                    holding_qty: int = 0) -> Optional[Fill]:
        self._guard(side, qty, holding_qty)
        if self._client is None:
            self.connect()
        from alpaca.trading.requests import MarketOrderRequest
        from alpaca.trading.enums import OrderSide, TimeInForce
        req = MarketOrderRequest(
            symbol=symbol, qty=qty,
            side=OrderSide.BUY if side.lower() == "buy" else OrderSide.SELL,
            time_in_force=TimeInForce.DAY)
        o = self._client.submit_order(req)
        return Fill(symbol=symbol, side=side.lower(), qty=int(qty),
                    price=float(price), ts=datetime.now().isoformat(timespec="seconds"),
                    note=f"alpaca paper order {getattr(o, 'id', '?')}")


def get_broker(name: str = "sim") -> BrokerBase:
    """Factory. Defaults to the simulator so a paper session never depends on an
    external account being configured."""
    if name == "alpaca":
        return AlpacaBroker()
    return SimBroker()
