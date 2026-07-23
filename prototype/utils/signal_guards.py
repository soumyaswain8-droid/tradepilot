"""Shared defensive guards used by all paper-trade engines.

Rationale: The same copy-pasted `if price <= 0: continue` guard existed in 5
engine scripts. It silently passed NaN through (NaN <= 0 is False in Python),
crashing engines at `int(NaN)`. On 2026-04-17, this bug killed v5, v5.6, v5.7.
Centralizing the guards here means one fix applies everywhere.

Usage:
    from prototype.utils.signal_guards import safe_qty, atomic_write_json, check_model_freshness

    # Instead of: qty = int(min(sized, budget) / price)
    qty = safe_qty(budget, price, sized=sized)
    if qty is None: continue

    # Instead of: path.write_text(json.dumps(data))
    atomic_write_json(path, data)

    # Add to engine main():
    check_model_freshness(max_age_days=3)  # aborts + alerts if stale
"""
from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Optional


def is_finite_positive(x) -> bool:
    """True iff x is a finite positive number. Catches None, NaN, inf, 0, negative."""
    try:
        return x is not None and math.isfinite(x) and x > 0
    except (TypeError, ValueError):
        return False


def safe_qty(budget, price, sized=None, min_qty: int = 1) -> Optional[int]:
    """Compute position quantity defensively.

    Returns None if any input is invalid (NaN, None, 0, negative, infinite).
    This replaces the broken `if price <= 0: continue` pattern which let NaN through.

    Args:
        budget: total capital available for this position
        price: entry price per share
        sized: optional risk-adjusted position size (bounded by budget)
        min_qty: minimum quantity to return (default 1)

    Returns:
        int quantity, or None if inputs invalid / computed qty would be 0
    """
    if not is_finite_positive(price):
        return None
    if not is_finite_positive(budget):
        return None
    effective = min(sized, budget) if is_finite_positive(sized) else budget
    qty = int(effective / price)
    if qty < min_qty:
        return None
    return qty


def atomic_write_json(path: Path | str, data: Any, indent: int = 2) -> None:
    """Atomically write JSON to a file path.

    Writes to a temp file in the same directory then renames it over the
    target. On POSIX + APFS, rename() is atomic — readers always see either
    the old file or the new one, never a half-written file.

    This prevents the failure mode that hit v5 on 2026-04-17: crash mid-save
    left positions_active.json in an inconsistent state, losing Rs 487 of
    realized wins.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Use tempfile in the same directory so rename is atomic (no cross-fs copy)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=indent, default=str)
            f.flush()
            os.fsync(f.fileno())  # Force to disk before rename
        os.replace(tmp, path)  # atomic rename on POSIX
    except Exception:
        # Clean up temp file on error
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def send_telegram_alert(msg: str) -> bool:
    """Best-effort Telegram notification. Returns True if sent."""
    try:
        env_file = Path(__file__).resolve().parents[2] / ".env"
        if not env_file.exists():
            return False
        env = dict(
            line.split("=", 1)
            for line in env_file.read_text().splitlines()
            if "=" in line and not line.startswith("#")
        )
        token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
        chat = env.get("TELEGRAM_CHAT_ID", "").strip()
        if not token or not chat:
            return False
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"https://api.telegram.org/bot{token}/sendMessage",
             "--data-urlencode", f"chat_id={chat}",
             "--data-urlencode", f"text={msg}"],
            timeout=5, check=False, capture_output=True,
        )
        return True
    except Exception:
        return False


class ReentryBlocker:
    """Per-day tracker that blocks re-entries in (symbol, direction) after N stoplosses.

    Learning #003 (accepted 2026-04-20): backtest showed 2-SL threshold is net
    positive across all engines (+Rs 1,722 across Apr 10-17 historical data)
    and has 0 false positives (vs 14 for strict 1-SL rule).

    Usage in engines:
        blocker = ReentryBlocker(max_sl=2)  # Create fresh each day
        # In deploy_signals:
        if blocker.is_blocked(sym, direction): continue
        # When SL hits:
        blocker.record_stoploss(sym, direction)
        # Serialize for state file:
        state["reentry_blocker"] = blocker.to_dict()
        # Restore:
        blocker = ReentryBlocker.from_dict(state.get("reentry_blocker", {}))
    """
    __slots__ = ("sl_count", "max_sl")

    def __init__(self, max_sl: int = 2):
        self.sl_count: dict[tuple[str, str], int] = {}
        self.max_sl = max_sl

    def is_blocked(self, symbol: str, direction: str) -> bool:
        """Return True if this (symbol, direction) has hit the SL threshold."""
        return self.sl_count.get((symbol, direction), 0) >= self.max_sl

    def record_stoploss(self, symbol: str, direction: str) -> int:
        """Increment SL count. Returns new count."""
        key = (symbol, direction)
        self.sl_count[key] = self.sl_count.get(key, 0) + 1
        return self.sl_count[key]

    def reset(self) -> None:
        """Clear all blocks (call at start of new trading day)."""
        self.sl_count.clear()

    def to_dict(self) -> dict:
        """Serializable form for state JSON."""
        return {
            "max_sl": self.max_sl,
            "sl_count": {f"{s}|{d}": c for (s, d), c in self.sl_count.items()},
        }

    @classmethod
    def from_dict(cls, data: dict) -> "ReentryBlocker":
        """Rebuild from serialized form."""
        obj = cls(max_sl=data.get("max_sl", 2))
        for key, count in data.get("sl_count", {}).items():
            if "|" in key:
                s, d = key.split("|", 1)
                obj.sl_count[(s, d)] = count
        return obj


def is_reentry_blocked(state: dict, symbol: str, direction: str, max_sl: int = 2) -> bool:
    """Check if (symbol, direction) has hit the SL threshold on the state dict directly.

    This is the functional wrapper around ReentryBlocker for use inside engine loops
    where we work with the state dict (JSON-serializable) rather than class instances.
    """
    rb = state.get("reentry_blocker") or {}
    return rb.get("sl_count", {}).get(f"{symbol}|{direction}", 0) >= max_sl


def record_reentry_sl(state: dict, symbol: str, direction: str) -> int:
    """Increment SL count for (symbol, direction) in the state dict. Returns new count.

    Call this ONLY when a position closed with reason == STOPLOSS.
    """
    rb = state.setdefault("reentry_blocker", {"max_sl": 2, "sl_count": {}})
    if "sl_count" not in rb:
        rb["sl_count"] = {}
    key = f"{symbol}|{direction}"
    rb["sl_count"][key] = rb["sl_count"].get(key, 0) + 1
    return rb["sl_count"][key]


def check_model_freshness(
    model_path: Path | str = None,
    max_age_days: int = 3,
    alert: bool = True,
    abort: bool = True,
) -> bool:
    """Verify ML model file is recent enough to trust.

    Returns True if fresh, False if stale (regardless of abort setting).
    If abort=True and stale, raises SystemExit after sending Telegram alert.

    Rationale: on 2026-04-17 we discovered the ML model had been stale for 7
    days because the retrain was silently failing. v5's daily P&L degraded
    from +40,480 to -1,482 over that period. A freshness guard would have
    caught this on day 2.
    """
    if model_path is None:
        model_path = Path(__file__).resolve().parents[1] / "v4" / "models" / "lgbm_intraday.txt"
    model_path = Path(model_path)
    if not model_path.exists():
        msg = f"⚠️ ML model MISSING at {model_path} — refusing to trade"
        if alert:
            send_telegram_alert(msg)
        if abort:
            raise SystemExit(msg)
        return False
    # Retirement check (2026-07-23, ML-001 closed): a "retired" marker in
    # verification_report.json means this model is no longer loaded by
    # anything, so the age/CEO-override dance below is moot. Skip straight
    # to a single info line and report fresh (no alert, no abort).
    try:
        import json as _json
        vr_path = model_path.parent / "verification_report.json"
        if vr_path.exists():
            vr = _json.loads(vr_path.read_text(encoding="utf-8"))
            if vr.get("retired"):
                print(f"  [check_model_freshness] model retired "
                      f"{vr['retired'].get('ts', '?')} — freshness check skipped")
                return True
    except Exception as _e:
        print(f"  [check_model_freshness] retirement check error: {_e}")

    age_days = (datetime.now() - datetime.fromtimestamp(model_path.stat().st_mtime)).days
    if age_days > max_age_days:
        # Sprint 1 (2026-05-15): check for a CEO override in verification_report.json
        # next to the model. If override is active + scoped + unexpired, the override
        # wins — the CEO has explicitly accepted the stale model for a bounded period
        # (e.g. legacy mode during a rebuild). Logs the bypass so it's visible.
        try:
            import json
            from datetime import date as _date
            vr_path = model_path.parent / "verification_report.json"
            if vr_path.exists():
                vr = json.loads(vr_path.read_text(encoding="utf-8"))
                override = vr.get("override") or {}
                expires = override.get("expires")
                if expires and _date.fromisoformat(expires) >= _date.today():
                    print(f"  [check_model_freshness] Model is {age_days}d old "
                          f"(max {max_age_days}d) — BYPASSED by CEO override "
                          f"({override.get('by','?')}, expires {expires})")
                    return True
        except Exception as _e:
            print(f"  [check_model_freshness] override check error: {_e}")

        msg = (f"⚠️ ML model is {age_days} days old (max allowed: {max_age_days}). "
               f"Retrain likely failing silently. Check logs/ml-retrain.log. "
               f"Refusing to trade with stale model.")
        if alert:
            send_telegram_alert(msg)
        if abort:
            raise SystemExit(msg)
        return False
    return True
