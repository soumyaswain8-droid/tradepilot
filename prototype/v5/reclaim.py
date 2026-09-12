"""Swept-level reclaim: the single definition used by scripts/eod-veto-shadow.py and
prototype/v5/risk_gate.py.

For a SHORT: in the last `lookback` completed bars, some bar's low went BELOW the
session low as it stood before that window, and that bar CLOSED back above it.
That is "the low just got bought"; shorting into it lost ₹-2,226 on 66 trades
over 08-11 Sep 2026 (docs/research/floor/2026-09-11-floor-assessment.md §3).
For a LONG the mirror: a high above the prior session high that closed back below.
"""
from __future__ import annotations


def swept_level_reclaimed(o, h, l, c, i, side, lookback=3):
    """o,h,l,c: equal-length sequences for one session in time order.
    i: index of the first bar NOT yet completed at decision time; the window is
    bars i-lookback .. i-1 and the reference extreme is over bars 0 .. i-lookback-1."""
    start = i - lookback
    if start < 1 or i > len(o):
        return False
    side = (side or "").upper()
    if side == "SHORT":
        ref_low = min(l[:start])
        for k in range(start, i):
            if l[k] < ref_low and c[k] > ref_low:
                return True
        return False
    if side == "LONG":
        ref_high = max(h[:start])
        for k in range(start, i):
            if h[k] > ref_high and c[k] < ref_high:
                return True
        return False
    return False


def _hms(s):
    s = str(s)
    try:
        hh, mm = int(s[0:2]), int(s[3:5])
        ss = int(s[6:8]) if len(s) >= 8 else 0
        return hh * 3600 + mm * 60 + ss
    except (TypeError, ValueError):
        return None


def tag_from_bars(bars, entry_hhmm, side, lookback=3):
    """bars: replay-shaped dicts {t,o,h,l,c} for one session. Returns 'reclaim',
    'clean', or None when fewer than lookback+1 bars precede the entry bar."""
    t_entry = _hms(entry_hhmm)
    if t_entry is None or not bars:
        return None
    idx = [k for k, b in enumerate(bars) if (_hms(b.get("t")) or -1) <= t_entry]
    if not idx:
        return None
    i = idx[-1]                     # bar containing the entry; not completed at entry time
    if i - lookback < 1:
        return None
    o = [float(b["o"]) for b in bars]; h = [float(b["h"]) for b in bars]
    l = [float(b["l"]) for b in bars]; c = [float(b["c"]) for b in bars]
    return "reclaim" if swept_level_reclaimed(o, h, l, c, i, side, lookback) else "clean"
