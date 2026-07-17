# v5_chop Chop-Filter Engine Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v5_chop shadow engine: a TrendScore sensor (tape efficiency + breadth + regime) driving an entry ladder and capital throttle so the engine trades less and smaller in chop, full-size in confirmed trend.

**Architecture:** Pure sensor/ladder math lives in a new `prototype/v5/trend_mode.py` (unit-testable, no network). A Gate-1 backtest script validates the sensor against June-July realized P&L BEFORE any engine change. Engine integration is a single env-gated (`CHOP_FILTER=1`) block at the `deploy_signals` choke-point of `scripts/v5-paper-trade.py` (same seam as DATA-GUARD), shipped via a `scripts/v5_chop-paper-trade.py` wrapper (v5_cut pattern) so live v5 is untouched.

**Tech Stack:** Python 3.11 (anaconda), pandas, yfinance (reuses existing fetch patterns), pytest/unittest (importlib pattern from `tests/test_track_a.py`).

## Global Constraints

- Spec: `docs/superpowers/specs/2026-07-17-v5chop-chop-filter-design.md` — thresholds CHOP<35≤NEUTRAL<65≤TREND are priors; Gate 1 calibrates.
- No new pip dependencies.
- `CHOP_FILTER` defaults **off** — live v5 behavior must be byte-identical when the env var is unset.
- **Exits are never gated** — all throttling applies to new entries only.
- Fail closed: missing tape/breadth data ⇒ mode CHOP (never TREND).
- v5_chop is **ML-free**: wrapper sets `ML_SCORE_WEIGHT=0`.
- Mode changes require 2 consecutive scans (hysteresis).
- **HARD GATE after Task 3:** engine-integration tasks (4-5) must not start until the Gate-1 backtest passes (≥70% profit capture on TREND days, ≥70% of losses on CHOP days) and Soumya signs off.

---

### Task 1: TrendScore sensor — pure functions

**Files:**
- Create: `prototype/v5/trend_mode.py`
- Test: `tests/test_trend_mode.py`

**Interfaces:**
- Consumes: nothing (pure functions).
- Produces (later tasks rely on these exact signatures):
  - `tape_efficiency(closes: list[float]) -> float` — 0–100; |net move| ÷ Σ|bar moves| × 100; `< 2` bars ⇒ 0.0.
  - `breadth_strength(pct_20_today: float, pct_20_prev: float) -> float` — 0–100; `min(100, abs(pct_20_today-50)*2 + abs(pct_20_today-pct_20_prev)*5)`; any input None ⇒ 0.0.
  - `trend_score(tape: float, breadth: float, regime_score: int) -> float` — `0.4*tape + 0.4*breadth + 0.2*(abs(regime_score)/6*100)`, clamped 0–100.
  - `mode_for(score: float, prev_pending: str|None, cur_mode: str, chop_th=35.0, trend_th=65.0) -> tuple[str, str|None]` — returns `(new_mode, pending)`; a raw mode different from `cur_mode` must be seen 2 consecutive calls (tracked via `pending`) before `new_mode` changes; raw mode: `score<chop_th ⇒ "CHOP"`, `score>=trend_th ⇒ "TREND"`, else `"NEUTRAL"`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_trend_mode.py
"""TrendScore sensor — pure-function tests (spec §1).
Run: python3 -m pytest tests/test_trend_mode.py -v
"""
import sys, unittest
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score, mode_for


class TestTapeEfficiency(unittest.TestCase):
    def test_pure_trend_is_100(self):
        self.assertAlmostEqual(tape_efficiency([100, 101, 102, 103, 104]), 100.0)

    def test_pure_whipsaw_near_zero(self):
        closes = [100, 101, 100, 101, 100]  # net 0, path 4
        self.assertAlmostEqual(tape_efficiency(closes), 0.0)

    def test_half_efficient(self):
        closes = [100, 102, 101, 103]  # net 3, path 2+1+2=5
        self.assertAlmostEqual(tape_efficiency(closes), 60.0)

    def test_too_few_bars_is_zero(self):
        self.assertEqual(tape_efficiency([100]), 0.0)
        self.assertEqual(tape_efficiency([]), 0.0)

    def test_flat_tape_is_zero(self):
        self.assertEqual(tape_efficiency([100, 100, 100]), 0.0)


class TestBreadthStrength(unittest.TestCase):
    def test_neutral_breadth_is_zero(self):
        self.assertEqual(breadth_strength(50.0, 50.0), 0.0)

    def test_strong_breadth_level(self):
        # 80% above 20-SMA, unchanged: |80-50|*2 = 60
        self.assertAlmostEqual(breadth_strength(80.0, 80.0), 60.0)

    def test_breadth_delta_contributes(self):
        # 55 today from 45 yesterday: |55-50|*2 + |10|*5 = 60
        self.assertAlmostEqual(breadth_strength(55.0, 45.0), 60.0)

    def test_caps_at_100(self):
        self.assertEqual(breadth_strength(100.0, 0.0), 100.0)

    def test_none_inputs_fail_closed(self):
        self.assertEqual(breadth_strength(None, 50.0), 0.0)
        self.assertEqual(breadth_strength(50.0, None), 0.0)


class TestTrendScore(unittest.TestCase):
    def test_weights(self):
        # 0.4*50 + 0.4*50 + 0.2*(3/6*100) = 20+20+10 = 50
        self.assertAlmostEqual(trend_score(50.0, 50.0, 3), 50.0)

    def test_regime_sign_ignored(self):
        self.assertEqual(trend_score(0, 0, -6), trend_score(0, 0, 6))

    def test_clamped(self):
        self.assertLessEqual(trend_score(100, 100, 6), 100.0)
        self.assertGreaterEqual(trend_score(0, 0, 0), 0.0)


class TestModeHysteresis(unittest.TestCase):
    def test_no_flip_on_single_scan(self):
        mode, pending = mode_for(80.0, None, "CHOP")
        self.assertEqual(mode, "CHOP")       # not yet
        self.assertEqual(pending, "TREND")

    def test_flip_on_second_consecutive_scan(self):
        mode, pending = mode_for(80.0, "TREND", "CHOP")
        self.assertEqual(mode, "TREND")
        self.assertIsNone(pending)

    def test_pending_resets_on_disagreement(self):
        mode, pending = mode_for(20.0, "TREND", "CHOP")  # pending TREND, raw now CHOP
        self.assertEqual(mode, "CHOP")
        self.assertIsNone(pending)

    def test_stable_mode_keeps_no_pending(self):
        mode, pending = mode_for(20.0, None, "CHOP")
        self.assertEqual(mode, "CHOP")
        self.assertIsNone(pending)

    def test_thresholds(self):
        self.assertEqual(mode_for(34.9, None, "NEUTRAL")[1], "CHOP")
        self.assertEqual(mode_for(35.0, "X", "NEUTRAL")[0], "NEUTRAL")
        self.assertEqual(mode_for(65.0, None, "NEUTRAL")[1], "TREND")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_trend_mode.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'prototype.v5.trend_mode'`

- [ ] **Step 3: Write minimal implementation**

```python
# prototype/v5/trend_mode.py
"""TrendScore sensor + mode ladder for v5_chop (spec 2026-07-17).

Pure functions only — no network, no file IO — so tests run without market
data. TrendScore measures trend STRENGTH (direction-neutral); direction is
the signal engine's job. Fail-closed: missing inputs score 0 (=> CHOP).
"""

CHOP_TH = 35.0
TREND_TH = 65.0


def tape_efficiency(closes) -> float:
    """|net move| / sum(|bar moves|) * 100 over 5-min closes since open."""
    if closes is None or len(closes) < 2:
        return 0.0
    path = sum(abs(closes[i] - closes[i - 1]) for i in range(1, len(closes)))
    if path == 0:
        return 0.0
    return abs(closes[-1] - closes[0]) / path * 100.0


def breadth_strength(pct_20_today, pct_20_prev) -> float:
    """Directional breadth strength from %-above-20SMA level + day delta."""
    if pct_20_today is None or pct_20_prev is None:
        return 0.0
    return min(100.0, abs(pct_20_today - 50.0) * 2 + abs(pct_20_today - pct_20_prev) * 5)


def trend_score(tape: float, breadth: float, regime_score: int) -> float:
    s = 0.4 * tape + 0.4 * breadth + 0.2 * (abs(regime_score or 0) / 6.0 * 100.0)
    return max(0.0, min(100.0, s))


def _raw_mode(score: float, chop_th: float, trend_th: float) -> str:
    if score < chop_th:
        return "CHOP"
    if score >= trend_th:
        return "TREND"
    return "NEUTRAL"


def mode_for(score: float, prev_pending, cur_mode: str,
             chop_th: float = CHOP_TH, trend_th: float = TREND_TH):
    """2-consecutive-scan hysteresis. Returns (mode, pending)."""
    raw = _raw_mode(score, chop_th, trend_th)
    if raw == cur_mode:
        return cur_mode, None
    if raw == prev_pending:
        return raw, None
    return cur_mode, raw
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_trend_mode.py -v`
Expected: all PASS (15 tests)

- [ ] **Step 5: Commit**

```bash
git add prototype/v5/trend_mode.py tests/test_trend_mode.py
git commit -m "feat(v5_chop): TrendScore sensor pure functions (tape efficiency, breadth strength, mode hysteresis)"
```

---

### Task 2: Ladder policy — pure function

**Files:**
- Modify: `prototype/v5/trend_mode.py` (append)
- Test: `tests/test_trend_mode.py` (append)

**Interfaces:**
- Consumes: nothing new.
- Produces: `apply_ladder(signals: list[dict], mode: str) -> tuple[list[dict], float, float]` — returns `(allowed_signals, size_mult, alloc_mult)`. Signals are dicts with a `"score"` key (float-able). Policy per spec §2/§3: CHOP ⇒ top-quartile floor, max 3, 0.40, 0.5; NEUTRAL ⇒ median floor, max 8, 0.70, 0.8; TREND ⇒ unfiltered, 1.0, 1.0. Ordering of returned signals: score descending. Unknown mode behaves as CHOP (fail closed).

- [ ] **Step 1: Write the failing tests** (append to `tests/test_trend_mode.py`)

```python
from prototype.v5.trend_mode import apply_ladder

def _sigs(scores):
    return [{"symbol": f"S{i}", "score": s} for i, s in enumerate(scores)]


class TestApplyLadder(unittest.TestCase):
    def test_trend_passes_through(self):
        sigs = _sigs([1, 2, 3, 4, 5, 6, 7, 8, 9, 10])
        allowed, size_m, alloc_m = apply_ladder(sigs, "TREND")
        self.assertEqual(len(allowed), 10)
        self.assertEqual((size_m, alloc_m), (1.0, 1.0))

    def test_chop_top_quartile_max3(self):
        sigs = _sigs(list(range(1, 13)))  # scores 1..12, quartile floor = 9.25
        allowed, size_m, alloc_m = apply_ladder(sigs, "CHOP")
        self.assertLessEqual(len(allowed), 3)
        self.assertTrue(all(float(s["score"]) >= 9.25 for s in allowed))
        self.assertEqual((size_m, alloc_m), (0.40, 0.5))
        self.assertEqual([s["score"] for s in allowed], sorted([s["score"] for s in allowed], reverse=True))

    def test_neutral_median_max8(self):
        sigs = _sigs(list(range(1, 21)))  # 1..20, median 10.5
        allowed, size_m, alloc_m = apply_ladder(sigs, "NEUTRAL")
        self.assertLessEqual(len(allowed), 8)
        self.assertTrue(all(float(s["score"]) >= 10.5 for s in allowed))
        self.assertEqual((size_m, alloc_m), (0.70, 0.8))

    def test_unknown_mode_fails_closed_as_chop(self):
        sigs = _sigs([5, 6, 7, 8])
        allowed, size_m, alloc_m = apply_ladder(sigs, "???")
        self.assertEqual((size_m, alloc_m), (0.40, 0.5))

    def test_empty_signals_ok(self):
        allowed, _, _ = apply_ladder([], "CHOP")
        self.assertEqual(allowed, [])
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_trend_mode.py -k Ladder -v`
Expected: FAIL — `ImportError: cannot import name 'apply_ladder'`

- [ ] **Step 3: Implement** (append to `prototype/v5/trend_mode.py`)

```python
# mode -> (max_new_entries, size_mult, alloc_mult, floor_percentile)
LADDER = {
    "CHOP":    (3,    0.40, 0.5, 75),
    "NEUTRAL": (8,    0.70, 0.8, 50),
    "TREND":   (None, 1.00, 1.0, 0),
}


def _percentile(sorted_vals, pct):
    """Linear-interpolation percentile (matches numpy default)."""
    if not sorted_vals:
        return 0.0
    k = (len(sorted_vals) - 1) * pct / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)


def apply_ladder(signals, mode):
    """Filter+cap signals per mode. Returns (allowed, size_mult, alloc_mult)."""
    max_new, size_mult, alloc_mult, floor_pct = LADDER.get(mode, LADDER["CHOP"])
    ranked = sorted(signals, key=lambda s: -float(s.get("score", 0)))
    if floor_pct:
        scores = sorted(float(s.get("score", 0)) for s in signals)
        floor_val = _percentile(scores, floor_pct)
        ranked = [s for s in ranked if float(s.get("score", 0)) >= floor_val]
    if max_new is not None:
        ranked = ranked[:max_new]
    return ranked, size_mult, alloc_mult
```

- [ ] **Step 4: Run full test file**

Run: `python3 -m pytest tests/test_trend_mode.py -v`
Expected: all PASS (20 tests)

- [ ] **Step 5: Commit**

```bash
git add prototype/v5/trend_mode.py tests/test_trend_mode.py
git commit -m "feat(v5_chop): apply_ladder mode policy (entry cap + size + alloc multipliers)"
```

---

### Task 3: Gate-1 sensor backtest

**Files:**
- Create: `scripts/backtest-trend-sensor.py`

**Interfaces:**
- Consumes: `trend_mode.tape_efficiency/breadth_strength/trend_score/mode_for` (Task 1); daily jsons `docs/paper-trades/v5/2026-*.json` (fields: `summary.total_pnl_net`, `regime`); `prototype/v5/market_breadth.compute_breadth_indicators(date=...)` for pct_20 (verify the returned dict's key by running it once for one date — it is the value passed to `_classify_breadth(pct_20, ...)` in that module; adapt the key name in `_pct20()` below if it differs).
- Produces: `docs/research/2026-07-17_gate1-trend-sensor-backtest.md` report; exit code 0 if PASS criteria met, 1 if FAIL.

- [ ] **Step 1: Write the backtest script**

```python
#!/usr/bin/env python3
"""Gate-1 backtest: does TrendScore separate green days from bleed days?

PASS (spec §5): TREND-flagged (any point intraday) days contain >=70% of gross
positive P&L AND all-day-CHOP days contain >=70% of gross losses, over
2026-06-16..2026-07-16 (excluding outage artifacts 07-08, 07-10).
Also sweeps thresholds (chop_th in 25..45, trend_th in 55..75, step 5).

Usage: python3 scripts/backtest-trend-sensor.py
"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import yfinance as yf
from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score, mode_for
from prototype.v5.market_breadth import compute_breadth_indicators

START, END = "2026-06-16", "2026-07-16"
EXCLUDE = {"2026-07-08", "2026-07-10"}
REGIME_SCORE = {"BULL": 4, "BEAR": -4, "SIDEWAYS": 0}


def _sessions():
    out = []
    for f in sorted((ROOT / "docs/paper-trades/v5").glob("2026-0[67]-*.json")):
        d = f.name[:10]
        if d < START or d > END or d in EXCLUDE:
            continue
        data = json.loads(f.read_text())
        s = data.get("summary", {})
        if not s.get("trades"):
            continue
        out.append({"date": d, "net": s.get("total_pnl_net", s.get("total_pnl", 0)),
                    "regime": data.get("regime", "SIDEWAYS")})
    return out


def _pct20(date):
    try:
        ind = compute_breadth_indicators(date=date)
        return ind.get("pct_20")  # adapt key if module names it differently
    except Exception:
        return None


def _intraday_modes(date, regime, chop_th, trend_th, pct20_today, pct20_prev):
    """Walk the day's 5-min bars in 10-min steps; return set of modes seen."""
    n = yf.download("^NSEI", start=date, end=None, interval="5m", progress=False)
    n = n.loc[str(date)] if len(n) else n
    if len(n) < 6:
        return None  # no intraday data -> exclude day from scoring, report it
    closes = [float(c) for c in n["Close"].dropna().values]
    modes, cur, pending = set(), "CHOP", None
    b = breadth_strength(pct20_today, pct20_prev)
    for i in range(6, len(closes), 2):          # ~every 10 min after first 30 min
        t = tape_efficiency(closes[:i])
        s = trend_score(t, b, REGIME_SCORE.get(regime, 0))
        cur, pending = mode_for(s, pending, cur, chop_th, trend_th)
        modes.add(cur)
    return modes


def evaluate(chop_th, trend_th, sessions, pct20):
    trend_profit = chop_loss = tot_profit = tot_loss = 0.0
    rows = []
    prev_p = None
    for i, sess in enumerate(sessions):
        p_today = pct20.get(sess["date"])
        modes = _intraday_modes(sess["date"], sess["regime"], chop_th, trend_th, p_today, prev_p)
        prev_p = p_today
        if modes is None:
            rows.append((sess["date"], "NO-DATA", sess["net"])); continue
        day_class = "TREND" if "TREND" in modes else ("CHOP" if modes == {"CHOP"} else "NEUTRAL")
        rows.append((sess["date"], day_class, sess["net"]))
        if sess["net"] > 0:
            tot_profit += sess["net"]
            if day_class == "TREND": trend_profit += sess["net"]
        else:
            tot_loss += -sess["net"]
            if day_class == "CHOP": chop_loss += -sess["net"]
    pc = 100 * trend_profit / tot_profit if tot_profit else 0
    lc = 100 * chop_loss / tot_loss if tot_loss else 0
    return pc, lc, rows


def main():
    sessions = _sessions()
    pct20 = {s["date"]: _pct20(s["date"]) for s in sessions}
    report = ["# Gate-1 TrendScore backtest — generated by scripts/backtest-trend-sensor.py", ""]
    best = None
    for ct in (25, 30, 35, 40, 45):
        for tt in (55, 60, 65, 70, 75):
            pc, lc, rows = evaluate(ct, tt, sessions, pct20)
            report.append(f"| chop<{ct} trend>={tt} | profit-capture {pc:.0f}% | loss-capture {lc:.0f}% |")
            if best is None or min(pc, lc) > min(best[0], best[1]):
                best = (pc, lc, ct, tt, rows)
    pc, lc, ct, tt, rows = best
    report.insert(1, f"**Best: chop_th={ct}, trend_th={tt} -> profit-capture {pc:.0f}%, loss-capture {lc:.0f}% "
                     f"({'PASS' if pc >= 70 and lc >= 70 else 'FAIL'} vs 70/70 gate)**\n")
    report.append("\n## Per-day (best thresholds)\n\n| date | class | v5 net |\n|---|---|---:|")
    report += [f"| {d} | {c} | {n:+,.0f} |" for d, c, n in rows]
    out = ROOT / "docs/research/2026-07-17_gate1-trend-sensor-backtest.md"
    out.write_text("\n".join(report))
    print("\n".join(report[:3])); print(f"report: {out}")
    sys.exit(0 if pc >= 70 and lc >= 70 else 1)


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Sanity-run the breadth key assumption**

Run: `python3 -c "import sys; sys.path.insert(0,'.'); from prototype.v5.market_breadth import compute_breadth_indicators; d=compute_breadth_indicators(); print(sorted(d.keys()))"`
Expected: key list printed — confirm the %-above-20SMA key; if it is not `pct_20`, update `_pct20()` accordingly and note it in the commit message.

- [ ] **Step 3: Run the backtest**

Run: `python3 scripts/backtest-trend-sensor.py` (allow ~5-10 min: ~21 days × yf 5m fetches; 5m history covers ~60 days so the whole window is fetchable)
Expected: report written to `docs/research/2026-07-17_gate1-trend-sensor-backtest.md` with PASS/FAIL line and per-day table. NO-DATA days must be < 4 or the run is inconclusive — investigate fetches before judging.

- [ ] **Step 4: Commit (regardless of PASS/FAIL — the evidence is the artifact)**

```bash
git add scripts/backtest-trend-sensor.py docs/research/2026-07-17_gate1-trend-sensor-backtest.md
git commit -m "feat(v5_chop): Gate-1 TrendScore sensor backtest + report"
```

- [ ] **Step 5: HARD GATE — stop and review with Soumya**

If FAIL: stop here; re-spec the sensor (weights/inputs) before any engine work. If PASS: record the calibrated `chop_th`/`trend_th` — Task 4 uses them (update `CHOP_TH`/`TREND_TH` constants in `trend_mode.py` in the same commit as Task 4 Step 3 if they differ from 35/65).

---

### Task 4: Engine integration — mode update + ladder + capital throttle (env-gated)

**Files:**
- Modify: `scripts/v5-paper-trade.py` (two locations: new `_update_trend_mode()` helper next to `_fast_flip()`; gate block at top of `deploy_signals` directly after the DATA-GUARD block)
- Test: `tests/test_chop_ladder.py`

**Interfaces:**
- Consumes: `trend_mode.tape_efficiency/breadth_strength/trend_score/mode_for/apply_ladder` (Tasks 1-2), calibrated thresholds from Task 3.
- Produces: `state["trend_mode"]`, `state["trend_pending"]`, `state["trend_score_last"]` keys on engine state (visible in daily json for Gate-2 mode-distribution reporting); env flag `CHOP_FILTER=1` activates; `_update_trend_mode(state)` callable.

- [ ] **Step 1: Write the failing integration test**

```python
# tests/test_chop_ladder.py
"""CHOP_FILTER integration: deploy_signals honors ladder + budget throttle.
Uses the importlib pattern from tests/test_track_a.py. Network-touching
helpers are monkeypatched; deploy_signals is exercised with a stub pool
manager to observe filtering and sizing.
Run: python3 -m pytest tests/test_chop_ladder.py -v
"""
import os, sys, unittest
from unittest import mock
from pathlib import Path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT)); sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import importlib.util
_spec = importlib.util.spec_from_file_location(
    "v5_paper_trade", str(PROJECT_ROOT / "scripts" / "v5-paper-trade.py"))
v5 = importlib.util.module_from_spec(_spec)
sys.modules["v5_paper_trade"] = v5
try:
    _spec.loader.exec_module(v5)
except Exception as e:
    print(f"[warn] partial module load: {e}")


class StubPool:
    def __init__(self): self.deployed = []
    def deploy(self, pool, sym, qty, price, sl, tgt):
        self.deployed.append((sym, qty)); return True
    def get_pool_budget(self, pool): return 100_000
    @property
    def pools(self): return {"INTRADAY": self}


def _state():
    return {"pools": {"INTRADAY": {"positions": []}}, "trend_mode": "CHOP",
            "trend_pending": None, "premarket": {}, "regime": "SIDEWAYS",
            "summary": {"rescore_count": 0}}


def _signals(n):
    return [{"symbol": f"S{i}", "direction": "BUY", "score": i, "pool": "INTRADAY",
             "entry_price": 100.0, "position_type": "LONG"} for i in range(1, n + 1)]


class TestChopFilter(unittest.TestCase):
    def setUp(self):
        os.environ["CHOP_FILTER"] = "1"
        os.environ["DATA_GUARD"] = "0"          # isolate: not testing the tape guard here
        self.addCleanup(os.environ.pop, "CHOP_FILTER", None)
        self.addCleanup(os.environ.pop, "DATA_GUARD", None)

    def test_chop_mode_caps_entries_at_3(self):
        pm = StubPool()
        with mock.patch.object(v5, "_update_trend_mode", lambda state: None):  # keep CHOP
            n = v5.deploy_signals(_state(), pm, None, _signals(12))
        self.assertLessEqual(len(pm.deployed), 3)

    def test_flag_off_is_vanilla(self):
        os.environ["CHOP_FILTER"] = "0"
        pm = StubPool()
        n = v5.deploy_signals(_state(), pm, None, _signals(12))
        self.assertGreater(len(pm.deployed), 3)   # no ladder cap applied

    def test_chop_reduces_qty(self):
        pm_chop, pm_off = StubPool(), StubPool()
        sigs = _signals(3)
        with mock.patch.object(v5, "_update_trend_mode", lambda state: None):
            v5.deploy_signals(_state(), pm_chop, None, [dict(s) for s in sigs])
        os.environ["CHOP_FILTER"] = "0"
        v5.deploy_signals(_state(), pm_off, None, [dict(s) for s in sigs])
        got = dict(pm_chop.deployed); base = dict(pm_off.deployed)
        for sym in got:
            self.assertLess(got[sym], base[sym])  # 0.4 size × 0.5 alloc < 1.0


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run to verify failure**

Run: `python3 -m pytest tests/test_chop_ladder.py -v`
Expected: FAIL — `AttributeError: module 'v5_paper_trade' has no attribute '_update_trend_mode'` (and/or cap assertions fail because no ladder exists).

- [ ] **Step 3: Implement in `scripts/v5-paper-trade.py`**

3a. Add `_update_trend_mode` beside `_fast_flip` (after it):

```python
def _update_trend_mode(state):
    """v5_chop sensor (spec 2026-07-17): recompute TrendScore + mode each scan.

    CHOP_FILTER=1 only. Breadth (daily-granularity) cached in state; tape from
    the same 5-min ^NSEI fetch pattern as _fast_flip. Fail-closed: any missing
    input contributes 0 -> mode decays toward CHOP.
    """
    if os.environ.get("CHOP_FILTER") != "1":
        return
    from prototype.v5.trend_mode import tape_efficiency, breadth_strength, trend_score, mode_for
    tape = 0.0
    try:
        import yfinance as yf
        n = yf.download("^NSEI", period="1d", interval="5m", progress=False)
        if len(n):
            tape = tape_efficiency([float(c) for c in n["Close"].dropna().values])
    except Exception as e:
        log(f"  [chop] tape fetch failed (fail-closed): {e}")
    b = state.get("_breadth_cache")
    if b is None:
        try:
            from prototype.v5.market_breadth import compute_breadth_indicators
            ind = compute_breadth_indicators()
            b = {"today": ind.get("pct_20"), "prev": state.get("_pct20_prev")}
        except Exception as e:
            log(f"  [chop] breadth failed (fail-closed): {e}")
            b = {"today": None, "prev": None}
        state["_breadth_cache"] = b
    breadth = breadth_strength(b["today"], b["prev"])
    regime_score = int(state.get("premarket", {}).get("regime_score", 0) or 0)
    s = trend_score(tape, breadth, regime_score)
    cur = state.get("trend_mode", "CHOP")
    mode, pending = mode_for(s, state.get("trend_pending"), cur)
    if mode != cur:
        log(f"  [chop] mode {cur} -> {mode} (TrendScore {s:.0f})")
    state["trend_mode"], state["trend_pending"], state["trend_score_last"] = mode, pending, round(s, 1)
```

3b. In `deploy_signals`, directly after the DATA-GUARD block, insert:

```python
    # CHOP-FILTER (spec 2026-07-17): trade less + smaller in chop. Entries only.
    _chop_on = os.environ.get("CHOP_FILTER") == "1"
    _size_mult = _alloc_mult = 1.0
    if _chop_on:
        _update_trend_mode(state)
        from prototype.v5.trend_mode import apply_ladder
        signals, _size_mult, _alloc_mult = apply_ladder(signals, state.get("trend_mode", "CHOP"))
        log(f"  [chop] mode={state.get('trend_mode')} score={state.get('trend_score_last')} "
            f"-> {len(signals)} signals, size x{_size_mult}, alloc x{_alloc_mult}")
```

3c. In the same function, apply the multipliers at the two consumption points:

- budget line: `budget = pm.get_pool_budget(pool_name) * _alloc_mult` (replaces the bare call)
- sizing line: `sized = (rm.get_position_size(pool_name, base) if rm else base) * _size_mult`

3d. If Task 3 calibrated thresholds ≠ 35/65, update `CHOP_TH`/`TREND_TH` in `prototype/v5/trend_mode.py` in this commit.

- [ ] **Step 4: Run new + full suite**

Run: `python3 -m pytest tests/test_chop_ladder.py tests/test_trend_mode.py tests/ -q`
Expected: all PASS, incl. pre-existing 43. `test_flag_off_is_vanilla` is the no-regression proof for live v5.

- [ ] **Step 5: Commit**

```bash
git add scripts/v5-paper-trade.py tests/test_chop_ladder.py prototype/v5/trend_mode.py
git commit -m "feat(v5_chop): env-gated trend-mode ladder + capital throttle in deploy_signals"
```

---

### Task 5: Wrapper + roster wiring + smoke

**Files:**
- Create: `scripts/v5_chop-paper-trade.py`
- Modify: `scripts/launch-market.sh` (ENGINES array), `scripts/crash-watchdog.sh` (ENGINES list), `scripts/engine-compare.py` (engine roster list — locate the engine-names list at top of file and append `"v5_chop"`)

**Interfaces:**
- Consumes: `CHOP_FILTER` env flag (Task 4), wrapper pattern from `scripts/v5_cut-paper-trade.py`.
- Produces: running `python3 scripts/v5_chop-paper-trade.py` starts a full engine with `ENGINE_NAME=v5_chop`, state in `docs/paper-trades/v5_chop/`.

- [ ] **Step 1: Write the wrapper** (mirror `scripts/v5_flip-paper-trade.py` structure)

```python
#!/usr/bin/env python3
"""v5_chop — chop-filter shadow (spec 2026-07-17).

Same v5 code with CHOP_FILTER=1: TrendScore (tape efficiency 40% + breadth 40%
+ premarket regime 20%) drives a CHOP/NEUTRAL/TREND ladder — top-quartile-only
max-3 entries at 0.4x size in 0.5x budget in CHOP, vanilla v5 in confirmed
TREND (2-scan hysteresis). ML-free (proven selection-neutral, IC 0.006).
WHY: Jun16-Jul16 v5 lost Rs766/day on the 19 SIDEWAYS days and made money only
on trend days; Rs211k of Rs359k on-table was symmetric whipsaw. Gate 2: 2-week
shadow vs v5 — promote only on better net AND lower cost drag AND no worse DD.
Runs alongside the roster; own state/log; re-comment in launch-market to end.
"""
import os, sys, runpy
from pathlib import Path

os.environ["ENGINE_NAME"] = "v5_chop"
os.environ["CHOP_FILTER"] = "1"
os.environ["ML_SCORE_WEIGHT"] = "0"

sys.argv[0] = str(Path(__file__).resolve().parent / "v5-paper-trade.py")
runpy.run_path(sys.argv[0], run_name="__main__")
```

Before writing, diff against `scripts/v5_cut-paper-trade.py` / `scripts/v5_flip-paper-trade.py` and copy their exact runpy/env idiom if it differs from the above (the roster wrappers are the source of truth for this pattern).

- [ ] **Step 2: Smoke-test the wrapper standalone (off-hours safe)**

Run: `timeout 90 python3 scripts/v5_chop-paper-trade.py --status || true`
Expected: engine banner with `v5_chop`, state dir `docs/paper-trades/v5_chop/` created, no traceback. Then `grep -m2 "\[chop\]" logs/v5_chop-$(date +%F).log || echo "no scan yet (market closed) — OK"`.

- [ ] **Step 3: Wire the roster** — in `scripts/launch-market.sh` ENGINES array add (with comment):

```bash
  # SHADOW (spec 2026-07-17): v5_chop = TrendScore chop filter (trade less +
  # smaller in chop, full-size on confirmed trend). ML-free. Gate 2: 2 weeks
  # vs v5 -> promote on better net + lower cost drag + no worse DD.
  "v5_chop|scripts/v5_chop-paper-trade.py"
```

In `scripts/crash-watchdog.sh` ENGINES list add:

```bash
  "v5_chop|scripts/v5_chop-paper-trade.py|docs/paper-trades/v5_chop/${TODAY}.json|python3 scripts/v5_chop-paper-trade.py"
```

In `scripts/engine-compare.py` append `"v5_chop"` to the engine list.

- [ ] **Step 4: Verify wiring + full suite**

Run: `bash -n scripts/launch-market.sh && bash -n scripts/crash-watchdog.sh && python3 -m pytest tests/ -q && grep -c v5_chop scripts/launch-market.sh scripts/crash-watchdog.sh scripts/engine-compare.py`
Expected: both shell files parse, all tests PASS, each file greps ≥1.

- [ ] **Step 5: Commit + record Gate-2 start**

```bash
git add scripts/v5_chop-paper-trade.py scripts/launch-market.sh scripts/crash-watchdog.sh scripts/engine-compare.py
git commit -m "feat(v5_chop): wrapper + roster wiring (launch, watchdog, compare) — Gate-2 shadow starts next session"
```

Then store the learning: `dp learn "v5_chop shadow live from <next trading day>: Gate-2 ends +2 weeks; promote criteria = better net AND lower cost drag AND max DD no worse than v5; early-kill if trailing v5 by >Rs5k after week 1." --project tradepilot`

---

## Self-Review (done at write time)

1. **Spec coverage:** sensor §1→Task 1; ladder §2→Tasks 2,4; capital §3→Task 4 (3c); packaging §4→Task 5; Gate 1 §5→Task 3 (hard gate); tests §6→Tasks 1,2,4; ML workstream §8 is explicitly a separate spec/plan — not covered here by design.
2. **Placeholders:** none; the one runtime unknown (breadth dict key) has an explicit verification step (Task 3 Step 2) with a defined adaptation path.
3. **Type consistency:** `mode_for(score, prev_pending, cur_mode) -> (mode, pending)` used identically in Tasks 1/3/4; `apply_ladder(signals, mode) -> (list, float, float)` identical in Tasks 2/4; state keys `trend_mode`/`trend_pending`/`trend_score_last` consistent across Tasks 4/5.
