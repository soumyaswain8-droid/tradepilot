"""Candlestick pattern detectors, written from the five lessons in ../lessons.

Every detector works on plain numpy arrays (o, h, l, c) and returns a boolean
array `sig` where sig[i] is True when the pattern COMPLETES on bar i, plus the
stop level the lesson prescribes for that bar. Direction is +1 long / -1 short.

Conventions (from the lessons):
- body = |c - o|, range = h - l, upper wick = h - max(o,c), lower wick = min(o,c) - l
- "long body" = body >= 0.6 * range and range >= median range of the last 20 bars
- "small body" = body <= 0.3 * range
- doji = body <= 0.1 * range
- trend run = at least N consecutive same-colour bars before the pattern (lesson 1's
  "only important when trending"); N defaults to 3
"""
from __future__ import annotations
import numpy as np


def _parts(o, h, l, c):
    body = np.abs(c - o)
    rng = np.maximum(h - l, 1e-9)
    up = h - np.maximum(o, c)
    lo = np.minimum(o, c) - l
    green = c > o
    red = c < o
    return body, rng, up, lo, green, red


def _roll_median(x, n=20):
    out = np.full_like(x, np.nan, dtype=float)
    for i in range(len(x)):
        s = x[max(0, i - n + 1):i + 1]
        out[i] = np.median(s) if len(s) else np.nan
    return out


def _run_before(green, red, i, n):
    """+1 if bars i-n..i-1 are all green, -1 if all red, else 0. n == 0 means
    'no trend filter' and matches either direction (returns the caller's want via 2)."""
    if n == 0:
        return 2
    if i - n < 0:
        return 0
    g = green[i - n:i]
    r = red[i - n:i]
    if g.all():
        return 1
    if r.all():
        return -1
    return 0


def _shift(a, k):
    out = np.zeros_like(a, dtype=bool)
    if k < len(a):
        out[k:] = a[:-k] if k else a
    return out


# ---------------------------------------------------------------- single candles
def hammer(o, h, l, c, run=3):
    """Lesson 1/2/3: small body near the top, lower wick >= 2x body, after a red run.
    Signal completes when the NEXT bar breaks the hammer high (candle over candle).
    Returns (sig, stop, direction=+1)."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    shape = (lo >= 2 * body) & (up <= 0.35 * rng) & (body <= 0.4 * rng)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if shape[i - 1] and _run_before(green, red, i - 1, run) in (-1, 2) and h[i] > h[i - 1]:
            sig[i] = True
            stop[i] = l[i - 1]
    return sig, stop, 1


def shooting_star(o, h, l, c, run=3):
    """Lesson 1/3 (inverted hammer / shooting star / gravestone): small body near the
    bottom, upper wick >= 2x body, after a green run. Completes when the next bar
    breaks the star low. Short."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    shape = (up >= 2 * body) & (lo <= 0.35 * rng) & (body <= 0.4 * rng)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if shape[i - 1] and _run_before(green, red, i - 1, run) in (1, 2) and l[i] < l[i - 1]:
            sig[i] = True
            stop[i] = h[i - 1]
    return sig, stop, -1


def doji_top(o, h, l, c, run=3):
    """Lesson 1: doji at the top of a run, exit/short when the next bar breaks its low."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    shape = body <= 0.1 * rng
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if shape[i - 1] and _run_before(green, red, i - 1, run) in (1, 2) and l[i] < l[i - 1]:
            sig[i] = True
            stop[i] = h[i - 1]
    return sig, stop, -1


def doji_bottom(o, h, l, c, run=3):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    shape = body <= 0.1 * rng
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if shape[i - 1] and _run_before(green, red, i - 1, run) in (-1, 2) and h[i] > h[i - 1]:
            sig[i] = True
            stop[i] = l[i - 1]
    return sig, stop, 1


def pin_bar_bull(o, h, l, c, run=0):
    """Lesson 2: green pin bar (lower wick >= 2x body, body in top third) then one
    confirming green bar. Enter at the confirming bar's close. Stop at pin wick."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    pin = green & (lo >= 2 * body) & (np.minimum(o, c) >= l + 0.66 * rng)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if pin[i - 1] and green[i] and (run == 0 or _run_before(green, red, i - 1, run) == -1):
            sig[i] = True
            stop[i] = l[i - 1]
    return sig, stop, 1


def pin_bar_bear(o, h, l, c, run=0):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    pin = red & (up >= 2 * body) & (np.maximum(o, c) <= h - 0.66 * rng)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if pin[i - 1] and red[i] and (run == 0 or _run_before(green, red, i - 1, run) == 1):
            sig[i] = True
            stop[i] = h[i - 1]
    return sig, stop, -1


# ---------------------------------------------------------------- two candles
def engulfing_bull(o, h, l, c, run=0):
    """Lesson 2/3: red bar then a green bar whose BODY covers the prior body.
    Enter at the engulfing bar's close; stop at its low."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if red[i - 1] and green[i] and o[i] <= c[i - 1] and c[i] >= o[i - 1] and body[i] > body[i - 1]:
            if run == 0 or _run_before(green, red, i - 1, run) == -1:
                sig[i] = True
                stop[i] = l[i]
    return sig, stop, 1


def engulfing_bear(o, h, l, c, run=0):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(1, len(o)):
        if green[i - 1] and red[i] and o[i] >= c[i - 1] and c[i] <= o[i - 1] and body[i] > body[i - 1]:
            if run == 0 or _run_before(green, red, i - 1, run) == 1:
                sig[i] = True
                stop[i] = h[i]
    return sig, stop, -1


# ---------------------------------------------------------------- three candles
def three_bar_cont_bull(o, h, l, c, run=0):
    """Lesson 2: big green, small red (<= half the first body), big green closing
    above bar 2's close. Enter at bar 3 close; stop at bar 2 low."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    big = (body >= 0.6 * rng) & (rng >= med)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(2, len(o)):
        if big[i - 2] and green[i - 2] and red[i - 1] and body[i - 1] <= 0.5 * body[i - 2] \
                and big[i] and green[i] and c[i] > c[i - 1] and c[i] > c[i - 2]:
            sig[i] = True
            stop[i] = l[i - 1]
    return sig, stop, 1


def three_bar_cont_bear(o, h, l, c, run=0):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    big = (body >= 0.6 * rng) & (rng >= med)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(2, len(o)):
        if big[i - 2] and red[i - 2] and green[i - 1] and body[i - 1] <= 0.5 * body[i - 2] \
                and big[i] and red[i] and c[i] < c[i - 1] and c[i] < c[i - 2]:
            sig[i] = True
            stop[i] = h[i - 1]
    return sig, stop, -1


def three_bar_rev_bull(o, h, l, c, run=0):
    """Lesson 2: big red, smaller red, big green with body >= first body (strong).
    Enter at bar 3 close; stop at bar 2 low."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    big = (body >= 0.6 * rng) & (rng >= med)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(2, len(o)):
        if big[i - 2] and red[i - 2] and red[i - 1] and body[i - 1] < body[i - 2] \
                and green[i] and body[i] >= body[i - 2]:
            sig[i] = True
            stop[i] = l[i - 1]
    return sig, stop, 1


def three_bar_rev_bear(o, h, l, c, run=0):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    big = (body >= 0.6 * rng) & (rng >= med)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(2, len(o)):
        if big[i - 2] and green[i - 2] and green[i - 1] and body[i - 1] < body[i - 2] \
                and red[i] and body[i] >= body[i - 2]:
            sig[i] = True
            stop[i] = h[i - 1]
    return sig, stop, -1


def breakout_bull(o, h, l, c, run=0, n_small=3):
    """Lesson 2: >= 3 small-bodied bars then a large green bar closing above the
    consolidation high. Enter at breakout close; stop at breakout open."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    small = rng <= 0.6 * np.nan_to_num(med, nan=np.inf)
    big = green & (body >= 0.6 * rng) & (rng >= 1.5 * np.nan_to_num(med, nan=np.inf))
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(n_small, len(o)):
        if big[i] and small[i - n_small:i].all() and c[i] > h[i - n_small:i].max():
            sig[i] = True
            stop[i] = o[i]
    return sig, stop, 1


def breakout_bear(o, h, l, c, run=0, n_small=3):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    small = rng <= 0.6 * np.nan_to_num(med, nan=np.inf)
    big = red & (body >= 0.6 * rng) & (rng >= 1.5 * np.nan_to_num(med, nan=np.inf))
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(n_small, len(o)):
        if big[i] and small[i - n_small:i].all() and c[i] < l[i - n_small:i].min():
            sig[i] = True
            stop[i] = o[i]
    return sig, stop, -1


def shrinking_bull(o, h, l, c, run=0):
    """Lesson 2: three red bars each smaller than the last, then a green bar closing
    above bar 2's close. Enter at bar 4 close; stop at bar 3 low."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(3, len(o)):
        if red[i - 3] and red[i - 2] and red[i - 1] and body[i - 3] > body[i - 2] > body[i - 1] \
                and green[i] and c[i] > c[i - 2] and body[i] > body[i - 1]:
            sig[i] = True
            stop[i] = l[i - 1]
    return sig, stop, 1


def shrinking_bear(o, h, l, c, run=0):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(3, len(o)):
        if green[i - 3] and green[i - 2] and green[i - 1] and body[i - 3] > body[i - 2] > body[i - 1] \
                and red[i] and c[i] < c[i - 2] and body[i] > body[i - 1]:
            sig[i] = True
            stop[i] = h[i - 1]
    return sig, stop, -1


def bull_flag(o, h, l, c, run=0):
    """Lesson 1: two long green bars, 1-3 small red bars, then the first bar to
    break the previous bar's high. Stop at the pullback low."""
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    long_g = green & (body >= 0.6 * rng) & (rng >= np.nan_to_num(med, nan=0))
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(4, len(o)):
        for k in (1, 2, 3):                     # k pullback bars
            j = i - k                            # first pullback bar index is j..i-1
            if j - 2 < 0:
                continue
            if long_g[j - 2] and long_g[j - 1] and red[j:i].all() and (body[j:i] <= 0.6 * body[j - 1]).all() \
                    and h[i] > h[i - 1] and l[j:i].min() > l[j - 2]:
                sig[i] = True
                stop[i] = l[j:i].min()
                break
    return sig, stop, 1


def bear_flag(o, h, l, c, run=0):
    body, rng, up, lo, green, red = _parts(o, h, l, c)
    med = _roll_median(rng, 20)
    long_r = red & (body >= 0.6 * rng) & (rng >= np.nan_to_num(med, nan=0))
    sig = np.zeros(len(o), bool)
    stop = np.full(len(o), np.nan)
    for i in range(4, len(o)):
        for k in (1, 2, 3):
            j = i - k
            if j - 2 < 0:
                continue
            if long_r[j - 2] and long_r[j - 1] and green[j:i].all() and (body[j:i] <= 0.6 * body[j - 1]).all() \
                    and l[i] < l[i - 1] and h[j:i].max() < h[j - 2]:
                sig[i] = True
                stop[i] = h[j:i].max()
                break
    return sig, stop, -1


PATTERNS = {
    # name: (fn, lesson, kind)
    "hammer":            (hammer,              "L1/L2/L3", "reversal"),
    "shooting_star":     (shooting_star,       "L1/L3",    "reversal"),
    "doji_top":          (doji_top,            "L1",       "reversal"),
    "doji_bottom":       (doji_bottom,         "L1",       "reversal"),
    "pin_bar_bull":      (pin_bar_bull,        "L2",       "reversal"),
    "pin_bar_bear":      (pin_bar_bear,        "L2",       "reversal"),
    "engulfing_bull":    (engulfing_bull,      "L2/L3",    "reversal"),
    "engulfing_bear":    (engulfing_bear,      "L2/L3",    "reversal"),
    "three_bar_rev_bull": (three_bar_rev_bull, "L2",       "reversal"),
    "three_bar_rev_bear": (three_bar_rev_bear, "L2",       "reversal"),
    "shrinking_bull":    (shrinking_bull,      "L2",       "reversal"),
    "shrinking_bear":    (shrinking_bear,      "L2",       "reversal"),
    "three_bar_cont_bull": (three_bar_cont_bull, "L2",     "continuation"),
    "three_bar_cont_bear": (three_bar_cont_bear, "L2",     "continuation"),
    "breakout_bull":     (breakout_bull,       "L2",       "continuation"),
    "breakout_bear":     (breakout_bear,       "L2",       "continuation"),
    "bull_flag":         (bull_flag,           "L1",       "continuation"),
    "bear_flag":         (bear_flag,           "L1",       "continuation"),
}
