"""
TradePilot Rust Bridge — Python -> Rust Execution Engine
=========================================================
Sends trade signals to the Rust engine (localhost:8080) for validation
and execution. Falls back to Python-only mode if Rust engine is down.

The Rust engine enforces:
  - Mandatory stop-loss on every order
  - SL direction validation (below entry for LONG, above for SHORT)
  - Daily loss kill switch
  - Max order size limits
  - Max position limits
  - Time-based trading restrictions

Usage:
    from prototype.v5.rust_bridge import RustBridge

    bridge = RustBridge()
    if bridge.is_alive():
        result = bridge.execute_signal(signal_dict)
        if result["success"]:
            print(f"Order placed: {result['data']['order_id']}")
        else:
            print(f"Rejected: {result['message']}")
"""

import json
import os
from datetime import datetime

import requests

RUST_ENGINE_URL = os.environ.get("RUST_ENGINE_URL", "http://localhost:8080")
TIMEOUT_SECS = 5


class RustBridge:
    """Bridge between Python scoring layer and Rust execution engine."""

    def __init__(self, url=None):
        self.url = url or RUST_ENGINE_URL
        self._alive = None
        self._last_check = None

    def is_alive(self):
        """Check if Rust engine is running. Caches for 30 seconds."""
        now = datetime.now()
        if self._last_check and (now - self._last_check).total_seconds() < 30:
            return self._alive

        try:
            r = requests.get(f"{self.url}/health", timeout=2)
            self._alive = r.status_code == 200
        except Exception:
            self._alive = False

        self._last_check = now
        return self._alive

    def execute_signal(self, signal):
        """
        Send a trade signal to the Rust engine for validation + execution.

        Args:
            signal: dict with keys:
                symbol, direction (BUY/SELL), score, entry_price,
                sl_price, target_price, quantity, pool

        Returns:
            dict with keys: success (bool), message (str), data (optional dict)
        """
        payload = {
            "symbol": signal.get("symbol", ""),
            "direction": signal.get("direction", "BUY"),
            "score": float(signal.get("score", 0)),
            "entry_price": float(signal.get("entry_price", signal.get("price", 0))),
            "stop_loss": float(signal.get("sl_price", 0)),
            "target": float(signal.get("target_price", 0)),
            "quantity": int(signal.get("qty", signal.get("quantity", 1))),
            "pool": signal.get("pool", "INTRADAY"),
            "tag": f"{signal.get('pool', 'UNK')}-{signal.get('symbol', 'UNK')}",
        }

        try:
            r = requests.post(
                f"{self.url}/api/execute",
                json=payload,
                timeout=TIMEOUT_SECS,
            )
            return r.json()
        except requests.exceptions.ConnectionError:
            return {"success": False, "message": "Rust engine not reachable"}
        except requests.exceptions.Timeout:
            return {"success": False, "message": "Rust engine timeout"}
        except Exception as e:
            return {"success": False, "message": f"Bridge error: {e}"}

    def get_risk_status(self):
        """Get current risk manager state from Rust engine."""
        try:
            r = requests.get(f"{self.url}/api/risk", timeout=TIMEOUT_SECS)
            return r.json()
        except Exception:
            return None

    def get_positions(self):
        """Get open positions and closed trades from Rust engine."""
        try:
            r = requests.get(f"{self.url}/api/positions", timeout=TIMEOUT_SECS)
            return r.json()
        except Exception:
            return None

    def kill_switch(self):
        """Activate emergency kill switch on Rust engine."""
        try:
            r = requests.post(f"{self.url}/api/kill", timeout=TIMEOUT_SECS)
            return r.json()
        except Exception as e:
            return {"success": False, "message": f"Kill switch failed: {e}"}

    def sync_positions(self, total_positions, positions_by_symbol, total_deployed):
        """Reconcile Rust's internal position count with Python's authoritative state.

        Prevents drift — if Python closes a position without telling Rust, Rust's
        count could creep up and eventually lock trading permanently. Call this
        periodically (e.g., start of each scan cycle).

        Args:
            total_positions: int, total open positions tracked by Python
            positions_by_symbol: dict of {symbol: count}
            total_deployed: float, rupees currently deployed

        Returns:
            dict with success, message, data (previous_count, new_count, drift_corrected)
        """
        payload = {
            "total_positions": int(total_positions),
            "positions_by_symbol": {k: int(v) for k, v in positions_by_symbol.items()},
            "total_deployed": float(total_deployed),
        }
        try:
            r = requests.post(
                f"{self.url}/api/risk/sync",
                json=payload,
                timeout=TIMEOUT_SECS,
            )
            return r.json()
        except Exception as e:
            return {"success": False, "message": f"Sync failed: {e}"}


# ═══════════════════════════════════════════════════════════
# Convenience functions for use in paper trading scripts
# ═══════════════════════════════════════════════════════════

_bridge = None


def get_bridge():
    """Get or create the singleton bridge instance."""
    global _bridge
    if _bridge is None:
        _bridge = RustBridge()
    return _bridge


def validate_signal_via_rust(signal):
    """
    Validate a signal through the Rust engine before Python deploys it.

    Returns:
        (ok: bool, message: str)
        - ok=True: Rust engine approved the order
        - ok=False: Rust engine rejected with reason
        - ok=None: Rust engine is down, fall back to Python-only
    """
    bridge = get_bridge()

    if not bridge.is_alive():
        return None, "Rust engine offline — Python-only mode"

    result = bridge.execute_signal(signal)

    if result.get("success"):
        return True, result.get("message", "Approved")
    else:
        return False, result.get("message", "Rejected")


def check_rust_risk():
    """Get risk status from Rust engine, or None if offline."""
    bridge = get_bridge()
    if not bridge.is_alive():
        return None
    return bridge.get_risk_status()


def sync_positions_from_state(state):
    """Sync Rust's position count from Python state dict (silent if Rust offline).

    Call at the start of each scan cycle. Reads positions from state["pools"][*]["positions"]
    and posts to Rust /api/risk/sync.

    Returns True if drift was corrected, False if no drift / Rust offline.
    """
    bridge = get_bridge()
    if not bridge.is_alive():
        return False

    # Aggregate positions from all pools
    total = 0
    by_symbol = {}
    total_deployed = 0.0
    for pool_name, pool in state.get("pools", {}).items():
        for p in pool.get("positions", []):
            total += 1
            sym = p.get("symbol", "?")
            by_symbol[sym] = by_symbol.get(sym, 0) + 1
            total_deployed += p.get("cost", p.get("qty", 0) * p.get("entry_price", 0))

    result = bridge.sync_positions(total, by_symbol, total_deployed)
    data = result.get("data") or {}
    return bool(data.get("drift_corrected", False))
