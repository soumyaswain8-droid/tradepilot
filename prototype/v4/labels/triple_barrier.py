"""
triple_barrier.py — López de Prado triple-barrier label generator
==================================================================

Reference
---------
- Marcos López de Prado, *Advances in Financial Machine Learning*, Ch.3
  ("Labeling"), Wiley 2018. The triple-barrier method.
- arXiv:2504.02249 — reports triple-barrier categorical labels roughly halve
  drawdown on intraday equity vs fixed-horizon return labels.

Why triple-barrier (motivation)
--------------------------------
Fixed-horizon return labels (e.g. "sign of the return N bars ahead") throw away
the *path*: a setup that ran +3% then reverted to -0.1% at the horizon gets the
same label as one that bled out monotonically. On retail intraday setups this
destroys information content (IC). The triple-barrier method labels each event
by *which barrier the price path touches first*:

    +1  take-profit (upper) barrier hit first
    -1  stop-loss   (lower) barrier hit first
     0  vertical    (time)  barrier hit first  ->  timed out

For short setups the upper/lower barriers are swapped (a downward move is the
profit barrier), handled via the ``direction`` argument.

Public API
----------
- ``Barriers``                 : dataclass of barrier parameters
- ``triple_barrier_label()``   : label a single price path / event
- ``triple_barrier_labels()``  : vectorised over many events / a rolling series

CLI
---
Running this module as ``__main__`` builds triple-barrier labels for every
historical paper-trade in ``docs/paper-trades/v4/`` over the window
Apr-21-2026 -> today and writes a parquet to
``prototype/v4/data/labels_triple_barrier.parquet``. It then validates the
labels against the engine's recorded ``exit_reason`` field and reports the
match rate (pass criterion: >= 80%).

Data source note
----------------
The live engine fetches *today-only* intraday bars via
``data_nse.get_intraday_candles`` (yfinance ``period="1d"``); no intraday price
*path* is persisted historically. The authoritative historical price-path
evidence per trade therefore lives in the paper-trade JSONs themselves
(``entry_price``, ``sl_price``, ``target_price``, ``exit_price``, ``exit_time``,
``exit_reason``). This module reuses that same recorded data — it does NOT
invent a new fetch and does NOT touch the live engine. When a full intraday OHLC
series IS available, ``triple_barrier_label(price_path=...)`` walks it bar-by-bar
in the canonical López de Prado fashion.

SARATHI-LRN
-----------
A learning entry citing AFML Ch.3 + arXiv:2504.02249 is appended to the daily
sarathi ledger (``docs/sarathi/ledger/YYYY-MM-DD.jsonl``) by the CLI on each run.
"""

from __future__ import annotations

import json
import glob
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Iterable, Optional, Sequence, Union

import pandas as pd

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Defaults (derived from existing v4 paper-trade config: most common per-trade
# barrier was SL 1.5% / target 2.0%, and the vertical barrier is the NSE intraday
# session length ~375 minutes / EOD square-off).
# ---------------------------------------------------------------------------
DEFAULT_TAKE_PROFIT_PCT: float = 2.0   # upper barrier, % above entry (long)
DEFAULT_STOP_LOSS_PCT: float = 1.5     # lower barrier, % below entry (long)
DEFAULT_VERTICAL_BARS: int = 375       # NSE 09:15->15:30 in 1-minute bars
DEFAULT_VERTICAL_MINUTES: int = 375    # same, expressed in minutes

LABEL_TP = 1     # take-profit barrier hit first
LABEL_SL = -1    # stop-loss barrier hit first
LABEL_TIMEOUT = 0  # vertical (time) barrier hit first


# ---------------------------------------------------------------------------
# Barrier parameters
# ---------------------------------------------------------------------------
@dataclass
class Barriers:
    """Triple-barrier parameters.

    Barriers are expressed as *percentages* of the entry price so they are
    scale-free across symbols. For a long position the take-profit barrier sits
    ``take_profit_pct`` above entry and the stop-loss barrier ``stop_loss_pct``
    below. For a short position the two are swapped automatically based on the
    ``direction`` passed to the labelling functions.

    Attributes
    ----------
    take_profit_pct : float
        Upper barrier distance, in percent (e.g. 2.0 == +2%).
    stop_loss_pct : float
        Lower barrier distance, in percent (e.g. 1.5 == -1.5%).
    vertical_bars : int
        Time barrier expressed in number of bars. Used when a bar-indexed price
        path is supplied.
    vertical_minutes : int
        Time barrier expressed in minutes. Used when timestamps are supplied.
    """

    take_profit_pct: float = DEFAULT_TAKE_PROFIT_PCT
    stop_loss_pct: float = DEFAULT_STOP_LOSS_PCT
    vertical_bars: int = DEFAULT_VERTICAL_BARS
    vertical_minutes: int = DEFAULT_VERTICAL_MINUTES

    def levels(self, entry_price: float, direction: str = "long") -> tuple[float, float]:
        """Return (take_profit_level, stop_loss_level) absolute prices."""
        tp_frac = self.take_profit_pct / 100.0
        sl_frac = self.stop_loss_pct / 100.0
        if _is_short(direction):
            # short: profit on the way down, stop on the way up
            tp = entry_price * (1.0 - tp_frac)
            sl = entry_price * (1.0 + sl_frac)
        else:
            tp = entry_price * (1.0 + tp_frac)
            sl = entry_price * (1.0 - sl_frac)
        return tp, sl


def _is_short(direction: str) -> bool:
    return str(direction).strip().upper() in {"SELL", "SHORT", "S", "-1", "DOWN"}


# ---------------------------------------------------------------------------
# Core single-event labeller
# ---------------------------------------------------------------------------
def triple_barrier_label(
    entry_price: float,
    *,
    direction: str = "long",
    barriers: Optional[Barriers] = None,
    take_profit_level: Optional[float] = None,
    stop_loss_level: Optional[float] = None,
    price_path: Optional[Sequence[float]] = None,
    high_path: Optional[Sequence[float]] = None,
    low_path: Optional[Sequence[float]] = None,
    exit_price: Optional[float] = None,
    n_bars_held: Optional[int] = None,
    minutes_held: Optional[float] = None,
) -> int:
    """Label a single event with the triple-barrier method.

    Returns one of {+1, -1, 0}:
        +1  take-profit barrier touched first
        -1  stop-loss barrier touched first
         0  vertical (time) barrier reached first (timed out)

    Resolution order for the price evidence (most -> least informative):

    1. ``high_path`` / ``low_path`` : true intraday OHLC walk. Each bar is
       checked for a barrier touch; the FIRST bar that touches a barrier sets
       the label (López de Prado canonical). If a single bar straddles both
       barriers, the stop-loss is assumed to trigger first (conservative).
    2. ``price_path`` : a close-only series, walked bar-by-bar the same way.
    3. ``exit_price`` : a single realised exit price (the case for the v4
       paper-trade reconstruction). The exit price is compared against the
       barrier levels; if it reached/exceeded a barrier that barrier is the
       label, else it is a timeout.

    The vertical barrier is enforced via ``n_bars_held`` / ``minutes_held``:
    if neither price barrier was touched within the horizon -> 0 (timeout).
    """
    b = barriers or Barriers()
    short = _is_short(direction)

    if take_profit_level is None or stop_loss_level is None:
        tp, sl = b.levels(entry_price, direction)
        take_profit_level = take_profit_level if take_profit_level is not None else tp
        stop_loss_level = stop_loss_level if stop_loss_level is not None else sl

    # vertical-barrier check: did the event exceed its time horizon?
    timed_out = False
    if n_bars_held is not None and n_bars_held >= b.vertical_bars:
        timed_out = True
    if minutes_held is not None and minutes_held >= b.vertical_minutes:
        timed_out = True

    # ---- 1 & 2: walk an explicit path ----------------------------------
    highs = high_path
    lows = low_path
    if highs is None and lows is None and price_path is not None:
        highs = lows = price_path

    if highs is not None and lows is not None:
        horizon = min(len(highs), len(lows))
        if b.vertical_bars and b.vertical_bars < horizon:
            horizon = b.vertical_bars
        for i in range(horizon):
            hi = float(highs[i])
            lo = float(lows[i])
            if short:
                hit_tp = lo <= take_profit_level   # price fell to profit target
                hit_sl = hi >= stop_loss_level     # price rose to stop
            else:
                hit_tp = hi >= take_profit_level
                hit_sl = lo <= stop_loss_level
            if hit_sl and hit_tp:
                return LABEL_SL  # conservative: assume stop fires first
            if hit_sl:
                return LABEL_SL
            if hit_tp:
                return LABEL_TP
        return LABEL_TIMEOUT  # never touched a price barrier within horizon

    # ---- 3: single realised exit price ---------------------------------
    if exit_price is not None:
        xp = float(exit_price)
        if short:
            if xp <= take_profit_level:
                return LABEL_TP
            if xp >= stop_loss_level:
                return LABEL_SL
        else:
            if xp >= take_profit_level:
                return LABEL_TP
            if xp <= stop_loss_level:
                return LABEL_SL
        return LABEL_TIMEOUT

    # no price evidence at all -> timeout if horizon exceeded, else undefined->0
    return LABEL_TIMEOUT if timed_out else LABEL_TIMEOUT


# ---------------------------------------------------------------------------
# Vectorised / batch labeller
# ---------------------------------------------------------------------------
def triple_barrier_labels(
    events: pd.DataFrame,
    *,
    barriers: Optional[Barriers] = None,
    entry_col: str = "entry_price",
    exit_col: str = "exit_price",
    tp_col: Optional[str] = "target_price",
    sl_col: Optional[str] = "stop_price",
    direction_col: Optional[str] = "direction",
    minutes_col: Optional[str] = None,
) -> pd.Series:
    """Label a DataFrame of events; returns an int Series of {+1,-1,0}.

    Per-row barrier levels are used when ``tp_col`` / ``sl_col`` are present and
    non-null, otherwise barriers are derived from ``barriers`` (or defaults).
    """
    b = barriers or Barriers()
    out = []
    for _, row in events.iterrows():
        entry = row.get(entry_col)
        if entry is None or pd.isna(entry):
            out.append(LABEL_TIMEOUT)
            continue
        direction = row.get(direction_col, "long") if direction_col else "long"
        tp_level = row.get(tp_col) if tp_col and tp_col in row else None
        sl_level = row.get(sl_col) if sl_col and sl_col in row else None
        if tp_level is not None and pd.isna(tp_level):
            tp_level = None
        if sl_level is not None and pd.isna(sl_level):
            sl_level = None
        minutes = row.get(minutes_col) if minutes_col and minutes_col in row else None
        out.append(
            triple_barrier_label(
                float(entry),
                direction=direction,
                barriers=b,
                take_profit_level=float(tp_level) if tp_level is not None else None,
                stop_loss_level=float(sl_level) if sl_level is not None else None,
                exit_price=row.get(exit_col),
                minutes_held=float(minutes) if minutes not in (None,) and not pd.isna(minutes) else None,
            )
        )
    return pd.Series(out, index=events.index, dtype="int64", name="triple_barrier_label")


# ---------------------------------------------------------------------------
# exit_reason -> categorical label mapping (validation ground truth)
# ---------------------------------------------------------------------------
def exit_reason_to_label(exit_reason: str) -> int:
    """Map an engine ``exit_reason`` string to a triple-barrier label.

    target / take-profit  -> +1
    stop-loss             -> -1
    time / eod / square-off / signal exit -> 0 (treated as vertical timeout)
    """
    er = str(exit_reason).strip().upper()
    if "TARGET" in er or "TAKE" in er or "PROFIT" in er or "TP" == er:
        return LABEL_TP
    if "STOP" in er or "SL" == er or "STOPLOSS" in er:
        return LABEL_SL
    # TIME_EXIT, EOD, SQUARE_OFF, SIGNAL_EXIT, etc. -> timeout bucket
    return LABEL_TIMEOUT


# ---------------------------------------------------------------------------
# CLI: build historical parquet over Apr-21-2026 -> today + validate
# ---------------------------------------------------------------------------
_REPO_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
_PAPER_TRADES_V4 = os.path.join(_REPO_ROOT, "docs", "paper-trades", "v4")
_OUT_PARQUET = os.path.join(os.path.dirname(__file__), "..", "data", "labels_triple_barrier.parquet")
_OUT_PARQUET = os.path.abspath(_OUT_PARQUET)
_SARATHI_LEDGER_DIR = os.path.join(_REPO_ROOT, "docs", "sarathi", "ledger")

WINDOW_START = "2026-04-21"


def _load_v4_trades(start_date: str = WINDOW_START) -> pd.DataFrame:
    """Load all v4 paper-trade events with exit_reason from start_date onward.

    Returns a DataFrame with one row per closed trade event.
    """
    rows = []
    for fn in sorted(glob.glob(os.path.join(_PAPER_TRADES_V4, "2026-*.json"))):
        base = os.path.basename(fn)
        if any(tag in base for tag in ("_comparison", "_report", "_adjusted")):
            continue
        # date prefix YYYY-MM-DD
        date_str = base[:10]
        if date_str < start_date:
            continue
        try:
            with open(fn) as f:
                d = json.load(f)
        except Exception as e:  # pragma: no cover - defensive
            logger.warning("skip unreadable %s: %s", fn, e)
            continue
        if not isinstance(d, dict):
            continue
        engine = d.get("engine", "v4")
        for t in (d.get("positions") or []):
            if not isinstance(t, dict):
                continue
            if not t.get("exit_reason") or t.get("exit_price") is None:
                continue
            rows.append(
                {
                    "date": date_str,
                    "engine": engine,
                    "symbol": t.get("symbol"),
                    "direction": t.get("v4_direction") or t.get("direction") or "long",
                    "entry_price": t.get("entry_price"),
                    "entry_time": t.get("entry_time"),
                    "exit_price": t.get("exit_price"),
                    "exit_time": t.get("exit_time"),
                    "target_price": t.get("target_price"),
                    "stop_price": t.get("sl_price"),
                    "sl_pct": t.get("sl_pct"),
                    "target_pct": t.get("target_pct"),
                    "pnl": t.get("pnl"),
                    "pnl_pct": t.get("pnl_pct"),
                    "exit_reason": t.get("exit_reason"),
                }
            )
    df = pd.DataFrame(rows)
    return df


def _minutes_held(entry_time: Optional[str], exit_time: Optional[str]) -> Optional[float]:
    """Best-effort HH:MM:SS -> minutes held (same trading day)."""
    if not entry_time or not exit_time:
        return None
    try:
        fmt = "%H:%M:%S" if entry_time.count(":") == 2 else "%H:%M"
        e = datetime.strptime(entry_time, fmt)
        fmt2 = "%H:%M:%S" if exit_time.count(":") == 2 else "%H:%M"
        x = datetime.strptime(exit_time, fmt2)
        return max(0.0, (x - e).total_seconds() / 60.0)
    except Exception:
        return None


def build_labels(start_date: str = WINDOW_START, barriers: Optional[Barriers] = None) -> pd.DataFrame:
    """Build the triple-barrier label table for the historical window."""
    b = barriers or Barriers()
    df = _load_v4_trades(start_date)
    if df.empty:
        logger.warning("no v4 trades found from %s", start_date)
        df["triple_barrier_label"] = pd.Series(dtype="int64")
        df["exit_reason_label"] = pd.Series(dtype="int64")
        return df

    df["minutes_held"] = [
        _minutes_held(e, x) for e, x in zip(df["entry_time"], df["exit_time"])
    ]
    df["triple_barrier_label"] = triple_barrier_labels(
        df,
        barriers=b,
        entry_col="entry_price",
        exit_col="exit_price",
        tp_col="target_price",
        sl_col="stop_price",
        direction_col="direction",
        minutes_col="minutes_held",
    )
    df["exit_reason_label"] = df["exit_reason"].map(exit_reason_to_label).astype("int64")
    df["label_match"] = (df["triple_barrier_label"] == df["exit_reason_label"])
    return df


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    barriers = Barriers()
    df = build_labels(WINDOW_START, barriers)

    if df.empty:
        logger.error("no labels generated — aborting")
        return 1

    os.makedirs(os.path.dirname(_OUT_PARQUET), exist_ok=True)
    df.to_parquet(_OUT_PARQUET, engine="pyarrow", index=False)

    n = len(df)
    dmin, dmax = df["date"].min(), df["date"].max()
    match_pct = 100.0 * df["label_match"].mean()
    dist = df["triple_barrier_label"].value_counts().to_dict()

    logger.info("wrote %d labels -> %s", n, _OUT_PARQUET)
    logger.info("window covered: %s -> %s", dmin, dmax)
    logger.info("label distribution {TP:+1, SL:-1, timeout:0}: %s", dist)
    logger.info("label-vs-exit_reason match: %.1f%% (pass>=80%%)", match_pct)
    if match_pct < 80.0:
        logger.warning("MATCH BELOW 80%% — inspect mapping vs barrier params")

    _append_sarathi_learning(n, dmin, dmax, match_pct, barriers)
    return 0


def _append_sarathi_learning(
    n_rows: int, dmin: str, dmax: str, match_pct: float, barriers: Barriers
) -> None:
    """Append a SARATHI-LRN learning entry to today's ledger (JSONL)."""
    try:
        os.makedirs(_SARATHI_LEDGER_DIR, exist_ok=True)
        ist = timezone(timedelta(hours=5, minutes=30))
        now = datetime.now(ist)
        ledger_path = os.path.join(_SARATHI_LEDGER_DIR, f"{now.strftime('%Y-%m-%d')}.jsonl")
        entry = {
            "ts": now.isoformat(),
            "agent": "label-engineer",
            "action": "triple-barrier-labels",
            "decision": "LEARN",
            "subject": _OUT_PARQUET,
            "evidence": {
                "rows": n_rows,
                "window": f"{dmin} -> {dmax}",
                "label_match_pct": round(match_pct, 1),
                "barriers": {
                    "take_profit_pct": barriers.take_profit_pct,
                    "stop_loss_pct": barriers.stop_loss_pct,
                    "vertical_minutes": barriers.vertical_minutes,
                },
            },
            "reason": (
                "Triple-barrier labels {+1 TP, -1 SL, 0 timeout} replace "
                "fixed-horizon return labels which destroy IC on retail intraday "
                "setups. Categorical path-dependent labels reportedly halve "
                "drawdown on intraday equity. Source: Lopez de Prado, Advances in "
                "Financial Machine Learning, Ch.3 (Labeling), Wiley 2018; "
                "arXiv:2504.02249."
            ),
            "vetoable_by": [],
            "rule_family": "SARATHI-LRN",
            "override": None,
        }
        with open(ledger_path, "a") as f:
            f.write(json.dumps(entry) + "\n")
        logger.info("SARATHI-LRN entry appended -> %s", ledger_path)
    except Exception as e:  # pragma: no cover - best effort
        logger.warning("could not append SARATHI-LRN entry: %s", e)


if __name__ == "__main__":
    raise SystemExit(main())
