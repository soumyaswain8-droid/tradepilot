# Floor Steps: Swept-Level Reclaim Veto (Shadow) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the "swept low reclaimed" pattern (the one candle-adjacent signal with evidence: ₹-2,226 on 66 engine shorts over four sessions) visible every day without changing a single trade: a nightly shadow score, a live tag in each engine verdict, and the Agent Floor pointed at the stocks the engines actually trade.

**Architecture:** One pure detector module `prototype/v5/reclaim.py` (numpy in, bool out) is the only place the pattern is defined. The nightly script `scripts/eod-veto-shadow.py` applies it to the candle replay the EOD driver already produces and writes a per-day JSON plus a running ledger. The live engine calls the same detector for each candidate at verdict time and appends a `note:` reason string that never affects the verdict. The Floor change is a universe file plus an environment override in `scouts.py`.

**Tech Stack:** Python 3, numpy, pandas (only in the EOD script), pytest via `python3 -m pytest`, Kite candles through `prototype/v4/kite_data.get_candles`, yfinance fallback through `prototype/v4/data_nse.get_intraday_candles`.

**Spec:** `docs/research/floor/2026-09-11-floor-assessment.md` sections 3 to 5 (the detector definition, the "shadow first, block after 2026-09-19" rule, the universe mismatch). Supporting evidence: `docs/research/candles/report/where-the-money-was.pdf` section 2 (turning points follow a climax bar and a rejection wick).

## Global Constraints

- **No trade may change.** Until 2026-09-19 the shadow experiments replay v5's actual entries; anything that alters v5's entry set contaminates them. The live tag is a `note:` string appended to `reasons[]`; it must never set `soft_hit`, never change `result.verdict`, and never raise. A test asserts the verdict is identical with and without the flag.
- **One detector.** `prototype/v5/reclaim.py` is imported by both the EOD script and the risk gate. No second copy of the rule anywhere.
- **Detector definition (from the assessment, section 3):** for a SHORT candidate, look at the last `lookback=3` completed 5-minute bars; the pattern is present if any of them made a low **below the session low as it stood before that window** and **closed back above** that prior session low. For a LONG candidate the mirror: a high above the prior session high that closed back below it. The session is bars from 09:15 on the same day.
- Git under Rosetta: prefix every git command with `arch -arm64`. Commit messages end with:
  ```
  Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>
  Claude-Session: https://claude.ai/code/session_01FVyFt7SkQR8LnFHHN6twrP
  ```
- Tests run from the repo root as `python3 -m pytest tests/<file> -q`. Never `git stash` (shared stash stack).
- Engine files (`scripts/v5-paper-trade.py`, `prototype/v5/risk_gate.py`) are edited only outside market hours (this plan is dated Saturday 2026-09-12). The running Floor and engines are not restarted by this plan.
- Data shapes, verified 2026-09-12: replay JSON is `{"date", "engines": {eng: {"trades": [{symbol, dir, qty, entry, entry_time "HH:MM:SS", exit, exit_time, pnl, reason, ...}]}}, "candles": {SYM: [{"t": "HH:MM:SS", "o", "h", "l", "c"}]}}` (written by `scripts/eod-replay-candles.py`, copied to `docs/watchdog/reports/<date>_eod/left-on-table.json`). Verdict items are built in `scripts/v5-paper-trade.py::_log_risk_gate_verdicts` (line ~586) from `RiskGate.evaluate(plan, position_type=...)` whose `reasons` list is built in `prototype/v5/risk_gate.py::_run_soft_checks` (line ~207). `scouts.py` loads its universe at `ScoutTeam.__init__` (line ~436) from `UNIVERSE_F = ROOT / "quant" / "universe_full.txt"` (one bare symbol per line).

---

### Task 1: The detector

**Files:**
- Create: `prototype/v5/reclaim.py`
- Test: `tests/test_reclaim.py`

**Interfaces:**
- Produces: `swept_level_reclaimed(o, h, l, c, i, side, lookback=3) -> bool` where `o,h,l,c` are equal-length sequences of floats for one session in time order, `i` is the index of the **first bar not yet completed** at decision time (so the window is bars `i-lookback .. i-1`), `side` is `"SHORT"` or `"LONG"`. Returns `False` when `i - lookback < 1` (no prior session extreme to sweep).
- Produces: `tag_from_bars(bars, entry_hhmm, side, lookback=3) -> str | None` where `bars` is a list of dicts `{"t": "HH:MM:SS", "o", "h", "l", "c"}` (the replay shape); returns `"reclaim"` when the pattern is present in the window before the bar containing `entry_hhmm`, `"clean"` otherwise, `None` when fewer than `lookback+1` bars precede the entry.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_reclaim.py
"""The swept-level reclaim detector: the one definition shared by the EOD shadow
script and the live risk gate."""
import sys, os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from prototype.v5.reclaim import swept_level_reclaimed, tag_from_bars


def _bars(rows):
    """rows: list of (o,h,l,c). Returns four lists."""
    return [list(x) for x in zip(*rows)]


def test_short_reclaim_detected():
    # session low before the window is 100 (bar 1). Bar 3 sweeps to 98 and closes 101.
    o, h, l, c = _bars([(102, 103, 100, 101), (101, 102, 100, 100.5), (100.5, 101, 100.2, 100.4),
                        (100.4, 101.5, 98.0, 101.0), (101, 102, 100.8, 101.5)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is True


def test_short_no_reclaim_when_close_stays_below():
    o, h, l, c = _bars([(102, 103, 100, 101), (101, 102, 100, 100.5), (100.5, 101, 100.2, 100.4),
                        (100.4, 100.6, 98.0, 99.0), (99, 99.5, 98.5, 99.2)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is False


def test_short_no_reclaim_when_low_not_swept():
    o, h, l, c = _bars([(102, 103, 100, 101), (101, 102, 100.5, 101), (101, 101.5, 100.7, 101.2),
                        (101.2, 101.6, 100.9, 101.4), (101.4, 102, 101, 101.8)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is False


def test_long_mirror_rejected_high():
    # session high before the window is 105 (bar 0). Bar 3 spikes to 107 and closes 104.
    o, h, l, c = _bars([(103, 105, 102, 104), (104, 104.8, 103, 104.2), (104.2, 104.9, 103.8, 104.5),
                        (104.5, 107.0, 104, 104.0), (104, 104.5, 103, 103.5)])
    assert swept_level_reclaimed(o, h, l, c, i=5, side="LONG") is True
    assert swept_level_reclaimed(o, h, l, c, i=5, side="SHORT") is False


def test_too_early_returns_false():
    o, h, l, c = _bars([(100, 101, 99, 100), (100, 101, 98, 100.5)])
    assert swept_level_reclaimed(o, h, l, c, i=2, side="SHORT") is False


def test_window_uses_last_completed_bars_only():
    # the sweep is at bar 0 (outside a 3-bar window ending before i=5) -> not detected
    o, h, l, c = _bars([(100, 101, 95, 100.5), (100.5, 101, 100, 100.2), (100.2, 100.8, 100, 100.4),
                        (100.4, 100.9, 100.1, 100.6), (100.6, 101, 100.2, 100.7), (100.7, 101, 100.3, 100.8)])
    assert swept_level_reclaimed(o, h, l, c, i=6, side="SHORT") is False


def test_tag_from_bars_replay_shape():
    bars = [{"t": "09:15:00", "o": 102, "h": 103, "l": 100, "c": 101},
            {"t": "09:20:00", "o": 101, "h": 102, "l": 100, "c": 100.5},
            {"t": "09:25:00", "o": 100.5, "h": 101, "l": 100.2, "c": 100.4},
            {"t": "09:30:00", "o": 100.4, "h": 101.5, "l": 98.0, "c": 101.0},
            {"t": "09:35:00", "o": 101, "h": 102, "l": 100.8, "c": 101.5}]
    assert tag_from_bars(bars, "09:36:10", "SHORT") == "reclaim"     # entry inside the 09:35 bar; window 09:20-09:30 holds the sweep
    assert tag_from_bars(bars, "09:31:00", "SHORT") is None          # entry inside the 09:30 bar: only 3 bars before it, need lookback+1
    assert tag_from_bars(bars, "09:22:00", "SHORT") is None          # too few bars before entry
    assert tag_from_bars(bars, "09:36:10", "LONG") == "clean"
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_reclaim.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'prototype.v5.reclaim'`.

- [ ] **Step 3: Implement**

```python
# prototype/v5/reclaim.py
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
```

- [ ] **Step 4: Run to verify they pass**

Run: `python3 -m pytest tests/test_reclaim.py -q`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
arch -arm64 git add prototype/v5/reclaim.py tests/test_reclaim.py
arch -arm64 git commit -m "feat(v5): swept-level reclaim detector, one definition for EOD shadow and live tag"
```

---

### Task 2: Nightly veto-shadow script

**Files:**
- Create: `scripts/eod-veto-shadow.py`
- Modify: `scripts/eod-experiments.sh` (add step 6)
- Test: `tests/test_eod_veto_shadow.py`

**Interfaces:**
- Consumes: `prototype.v5.reclaim.tag_from_bars(bars, entry_hhmm, side)`.
- Produces: `score_replay(replay: dict, engines: list[str]) -> dict` with shape `{"date", "engines": {eng: {"trades": [{symbol, side, entry_time, pnl, tag}], "buckets": {"reclaim": {"n", "pnl", "win"}, "clean": {...}, "untagged": {...}}}}, "fleet": {"reclaim": {...}, "clean": {...}, "untagged": {...}}}`. `pnl` values are the replay's `pnl` (gross, as the arm-band script uses).
- Produces: files `docs/research/shadows/veto/<date>.json`, `docs/research/shadows/veto/<date>.md`, and a running `docs/research/shadows/veto/veto-ledger.csv` with header `date,engine,tag,n,pnl,win_pct` (one row per engine per tag per day; re-running a date replaces its rows).
- CLI: `python3 scripts/eod-veto-shadow.py <date> [replay.json] [engines]`, defaulting the replay to `docs/watchdog/reports/<date>_eod/left-on-table.json` and engines to `v5,v5_wide`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_eod_veto_shadow.py
import sys, os, json, importlib.util
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def _load():
    spec = importlib.util.spec_from_file_location("eod_veto_shadow", os.path.join(ROOT, "scripts", "eod-veto-shadow.py"))
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m); return m


BARS = [{"t": "09:15:00", "o": 102, "h": 103, "l": 100, "c": 101},
        {"t": "09:20:00", "o": 101, "h": 102, "l": 100, "c": 100.5},
        {"t": "09:25:00", "o": 100.5, "h": 101, "l": 100.2, "c": 100.4},
        {"t": "09:30:00", "o": 100.4, "h": 101.5, "l": 98.0, "c": 101.0},
        {"t": "09:35:00", "o": 101, "h": 102, "l": 100.8, "c": 101.5},
        {"t": "09:40:00", "o": 101.5, "h": 102, "l": 101, "c": 101.2}]
REPLAY = {"date": "2026-09-11", "candles": {"AAA": BARS, "BBB": BARS},
          "engines": {"v5": {"trades": [
              {"symbol": "AAA", "dir": "SHORT", "entry_time": "09:36:10", "pnl": -85.6, "reason": "STOPLOSS"},
              {"symbol": "BBB", "dir": "SHORT", "entry_time": "09:22:00", "pnl": 40.0, "reason": "TARGET"},
              {"symbol": "AAA", "dir": "LONG", "entry_time": "09:41:00", "pnl": 10.0, "reason": "TIME_EXIT"},
              {"symbol": "ZZZ", "dir": "SHORT", "entry_time": "10:00:00", "pnl": -5.0, "reason": "STOPLOSS"}]}}}


def test_score_replay_buckets():
    m = _load()
    out = m.score_replay(REPLAY, ["v5"])
    e = out["engines"]["v5"]
    tags = {(t["symbol"], t["entry_time"]): t["tag"] for t in e["trades"]}
    assert tags[("AAA", "09:36:10")] == "reclaim"
    assert tags[("BBB", "09:22:00")] == "untagged"      # too few bars before entry
    assert tags[("AAA", "09:41:00")] == "clean"          # LONG, no rejected high
    assert tags[("ZZZ", "10:00:00")] == "untagged"       # no candles
    assert e["buckets"]["reclaim"] == {"n": 1, "pnl": -85.6, "win": 0}
    assert e["buckets"]["clean"] == {"n": 1, "pnl": 10.0, "win": 100}
    assert e["buckets"]["untagged"]["n"] == 2
    assert out["fleet"]["reclaim"]["n"] == 1


def test_ledger_replaces_rows_for_same_date(tmp_path):
    m = _load()
    led = tmp_path / "veto-ledger.csv"
    out = m.score_replay(REPLAY, ["v5"])
    m.write_ledger(led, out)
    m.write_ledger(led, out)
    rows = led.read_text().strip().splitlines()
    assert rows[0] == "date,engine,tag,n,pnl,win_pct"
    assert len(rows) == 1 + 3            # header + 3 tags for one engine, no duplicates
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_eod_veto_shadow.py -q`
Expected: FAIL (file not found when loading the module).

- [ ] **Step 3: Implement the script**

```python
#!/usr/bin/env python3
"""eod-veto-shadow — score the swept-level-reclaim veto against today's engine trades
WITHOUT changing anything. Reads the candle replay the EOD driver already makes.

    python3 scripts/eod-veto-shadow.py <date> [replay.json] [engines]

Writes docs/research/shadows/veto/<date>.json + .md and appends to veto-ledger.csv.
Buckets per engine: reclaim (entered against a swept-and-reclaimed level), clean,
untagged (no candles or fewer than 4 bars before entry).
"""
import sys, json, csv
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v5.reclaim import tag_from_bars  # noqa: E402

OUT = ROOT / "docs" / "research" / "shadows" / "veto"
TAGS = ("reclaim", "clean", "untagged")


def _bucket(trades):
    b = {}
    for tag in TAGS:
        xs = [t for t in trades if t["tag"] == tag]
        b[tag] = {"n": len(xs), "pnl": round(sum(float(t["pnl"] or 0) for t in xs), 2),
                  "win": (round(100 * sum(1 for t in xs if float(t["pnl"] or 0) > 0) / len(xs)) if xs else 0)}
    return b


def score_replay(replay, engines):
    cand = replay.get("candles") or {}
    out = {"date": replay.get("date"), "engines": {}}
    all_trades = []
    for eng in engines:
        e = (replay.get("engines") or {}).get(eng) or {}
        rows = []
        for t in e.get("trades") or []:
            side = str(t.get("dir") or t.get("position_type") or "LONG").upper()
            bars = cand.get(t.get("symbol"))
            tag = tag_from_bars(bars, t.get("entry_time"), side) if bars else None
            rows.append({"symbol": t.get("symbol"), "side": side, "entry_time": t.get("entry_time"),
                         "pnl": t.get("pnl"), "reason": t.get("reason"), "tag": tag or "untagged"})
        out["engines"][eng] = {"trades": rows, "buckets": _bucket(rows)}
        all_trades += rows
    out["fleet"] = _bucket(all_trades)
    return out


def write_ledger(path, scored):
    path = Path(path)
    rows = []
    if path.exists():
        with open(path) as f:
            rows = [r for r in csv.DictReader(f) if r["date"] != scored["date"]]
    for eng, e in scored["engines"].items():
        for tag in TAGS:
            b = e["buckets"][tag]
            rows.append({"date": scored["date"], "engine": eng, "tag": tag, "n": b["n"], "pnl": b["pnl"], "win_pct": b["win"]})
    rows.sort(key=lambda r: (r["date"], r["engine"], r["tag"]))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["date", "engine", "tag", "n", "pnl", "win_pct"])
        w.writeheader(); w.writerows(rows)


def write_md(path, scored):
    lines = [f"# Veto shadow — {scored['date']}", "",
             "Engine SHORTs entered within 3 bars of a swept-and-reclaimed session low (LONGs: rejected session high).",
             "Nothing was blocked; this is the score the veto WOULD have had.", "",
             "| Engine | Tag | n | P&L | Win |", "|---|---|---:|---:|---:|"]
    for eng, e in scored["engines"].items():
        for tag in TAGS:
            b = e["buckets"][tag]
            lines.append(f"| {eng} | {tag} | {b['n']} | {b['pnl']:,.0f} | {b['win']}% |")
    f = scored["fleet"]
    lines += ["", f"Fleet: reclaim {f['reclaim']['n']} trades ₹{f['reclaim']['pnl']:,.0f} · clean {f['clean']['n']} trades ₹{f['clean']['pnl']:,.0f} · untagged {f['untagged']['n']}"]
    Path(path).write_text("\n".join(lines) + "\n")


def main():
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(2)
    date = sys.argv[1]
    replay_path = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "docs" / "watchdog" / "reports" / f"{date}_eod" / "left-on-table.json"
    engines = (sys.argv[3] if len(sys.argv) > 3 else "v5,v5_wide").split(",")
    if not replay_path.exists():
        print(f"no replay at {replay_path}"); sys.exit(1)
    replay = json.load(open(replay_path))
    scored = score_replay(replay, engines)
    OUT.mkdir(parents=True, exist_ok=True)
    json.dump(scored, open(OUT / f"{date}.json", "w"), indent=1)
    write_md(OUT / f"{date}.md", scored)
    write_ledger(OUT / "veto-ledger.csv", scored)
    f = scored["fleet"]
    print(f"veto shadow {date}: reclaim n={f['reclaim']['n']} pnl={f['reclaim']['pnl']:,.0f} | clean n={f['clean']['n']} pnl={f['clean']['pnl']:,.0f} | untagged {f['untagged']['n']} -> {OUT / (date + '.md')}")


if __name__ == "__main__":
    main()
```

Make it executable: `chmod +x scripts/eod-veto-shadow.py`.

- [ ] **Step 4: Run the tests**

Run: `python3 -m pytest tests/test_eod_veto_shadow.py tests/test_reclaim.py -q`
Expected: 9 passed.

- [ ] **Step 5: Wire into the EOD driver**

In `scripts/eod-experiments.sh`, change the two `[5/5]` labels to `[5/6]` and insert before the final `echo "now: ..."` line:

```bash
echo "[6/6] veto shadow"; python3 scripts/eod-veto-shadow.py "$D" "$S/replay.json" v5,v5_wide 2>&1 | tail -1
```

- [ ] **Step 6: Backfill the four sessions that have replays**

Run from the repo root:
```bash
for d in 2026-09-08 2026-09-09 2026-09-10 2026-09-11; do python3 scripts/eod-veto-shadow.py $d; done
cat docs/research/shadows/veto/veto-ledger.csv
```
Expected: four dated JSON/MD files and a 25-line ledger (header + 4 days × 2 engines × 3 tags). The reclaim buckets should be negative on most engine-days, consistent with the assessment (₹-2,226 over 66 shorts; the exact totals differ slightly because this detector uses the entry bar's window rather than the "3 bars before entry bar" window used in the one-off check; report the numbers you get).

- [ ] **Step 7: Commit**

```bash
arch -arm64 git add scripts/eod-veto-shadow.py scripts/eod-experiments.sh tests/test_eod_veto_shadow.py docs/research/shadows/veto
arch -arm64 git commit -m "feat(eod): veto-shadow scorer for swept-level reclaim, wired into eod-experiments, backfilled 08-11 Sep"
```

---

### Task 3: The live tag in the risk gate (note only, never a verdict change)

**Files:**
- Modify: `prototype/v5/risk_gate.py` (`evaluate` signature around line 119; `_run_soft_checks` around line 207)
- Test: `tests/test_risk_gate.py` (append)

**Interfaces:**
- Consumes: nothing from `reclaim.py` here; the flag is computed by the caller (Task 4) and passed in, so the gate stays free of data access.
- Produces: `RiskGate.evaluate(plan, position_type=..., data_guard_ok=..., reclaim=None)` where `reclaim` is `True`, `False` or `None`. The reasons list gains exactly one string: `"note:swept_level_reclaimed: fired"`, `"note:swept_level_reclaimed: clear"`, or `"note:swept_level_reclaimed: not evaluable"`. The verdict is unaffected.

- [ ] **Step 1: Write the failing tests** (append to `tests/test_risk_gate.py`, reusing its `_StubRiskManager` and `_plan` helpers)

```python
def test_reclaim_note_is_appended_and_never_changes_verdict():
    rm = _StubRiskManager()
    gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
    base = gate.evaluate(_plan(score=90.0), position_type="SHORT")
    fired = gate.evaluate(_plan(score=90.0), position_type="SHORT", reclaim=True)
    clear = gate.evaluate(_plan(score=90.0), position_type="SHORT", reclaim=False)
    unknown = gate.evaluate(_plan(score=90.0), position_type="SHORT", reclaim=None)
    assert fired.verdict == base.verdict == clear.verdict == unknown.verdict
    assert "note:swept_level_reclaimed: fired" in fired.reasons
    assert "note:swept_level_reclaimed: clear" in clear.reasons
    assert "note:swept_level_reclaimed: not evaluable" in unknown.reasons
    assert sum(1 for r in fired.reasons if r.startswith("note:swept_level_reclaimed")) == 1


def test_reclaim_note_does_not_touch_soft_verdict():
    # a soft check that fires (score inside the band) gives 'watchlist'; the note must not add to or remove that
    rm = _StubRiskManager()
    gate = RiskGate(rm, score_threshold=50.0, soft_band=5.0)
    a = gate.evaluate(_plan(score=52.0), position_type="LONG")
    b = gate.evaluate(_plan(score=52.0), position_type="LONG", reclaim=True)
    assert a.verdict == b.verdict
```

Read the existing tests first to match the exact way `_StubRiskManager` is constructed and how the verdict enum is compared (e.g. `result.verdict.value == "watchlist"`), and adjust the assertions to that convention.

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_risk_gate.py -q -k reclaim`
Expected: FAIL with `TypeError: evaluate() got an unexpected keyword argument 'reclaim'`.

- [ ] **Step 3: Implement**

In `prototype/v5/risk_gate.py`:

a) Add `reclaim=None` as the last keyword parameter of `evaluate(...)` (keep every existing parameter and default untouched) and pass it through to `_run_soft_checks(...)` the same way `data_guard_ok` is passed.

b) At the **end** of `_run_soft_checks`, after the last existing soft block and before the function returns, append:

```python
        # note: swept-level reclaim. Observation only until 2026-09-19 (shadow window):
        # this string never sets soft_hit and never changes the verdict.
        if reclaim is None:
            reasons.append("note:swept_level_reclaimed: not evaluable")
        elif reclaim:
            reasons.append("note:swept_level_reclaimed: fired")
        else:
            reasons.append("note:swept_level_reclaimed: clear")
```

Add `reclaim=None` to `_run_soft_checks`'s signature. Do not touch `soft_hit`.

- [ ] **Step 4: Run the whole gate test file**

Run: `python3 -m pytest tests/test_risk_gate.py -q`
Expected: all passed (existing tests unaffected because the new reason string is additive and the default is `None`).

- [ ] **Step 5: Commit**

```bash
arch -arm64 git add prototype/v5/risk_gate.py tests/test_risk_gate.py
arch -arm64 git commit -m "feat(risk-gate): note:swept_level_reclaimed reason string, observation only, verdict unchanged"
```

---

### Task 4: Compute the flag per candidate in the engine and pass it in

**Files:**
- Modify: `scripts/v5-paper-trade.py` (`_log_risk_gate_verdicts`, around line 586-628)
- Test: `tests/test_v5_reclaim_flags.py`

**Interfaces:**
- Consumes: `prototype.v5.reclaim.swept_level_reclaimed`; `prototype.v4.kite_data.get_candles(symbol, "5minute", days=1)` (DataFrame `Open, High, Low, Close, Volume`, or `None`); fallback `prototype.v4.data_nse.get_intraday_candles(symbol, interval="5m")` (DataFrame, empty on error).
- Produces: a module-level function in `scripts/v5-paper-trade.py`: `reclaim_flags(symbols, sides, fetch=None) -> dict[str, bool | None]` keyed by symbol. `fetch(symbol) -> DataFrame | None` defaults to `_fetch_today_5m`. A symbol with no bars, fewer than 4 bars, or a fetch exception maps to `None`. The decision index `i` is `len(bars)` (all fetched bars are treated as completed; the bar in progress is not included by Kite for a closed 5-minute window, and treating the newest bar as complete is the conservative choice for a note).
- Produces: `_log_risk_gate_verdicts` computes `flags = reclaim_flags([...], [...])` once per call and passes `reclaim=flags.get(plan.symbol)` into `gate.evaluate(...)`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_v5_reclaim_flags.py
"""reclaim_flags in scripts/v5-paper-trade.py: per-candidate swept-level flag with an
injected bar fetcher, so no network is touched."""
import sys, os, importlib.util
import pandas as pd
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def _mod():
    # the engine script has module-level side effects; import it with the guard env the
    # script honours (read the top of scripts/v5-paper-trade.py: if it lacks a dry/import
    # guard, load only the function source via the helper below)
    spec = importlib.util.spec_from_file_location("v5pt", os.path.join(ROOT, "scripts", "v5-paper-trade.py"))
    m = importlib.util.module_from_spec(spec)
    os.environ["V5_IMPORT_ONLY"] = "1"
    spec.loader.exec_module(m)
    return m


def _df(rows):
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"])


def test_reclaim_flags_with_injected_fetch():
    m = _mod()
    bars = {"AAA": _df([(102, 103, 100, 101), (101, 102, 100, 100.5), (100.5, 101, 100.2, 100.4),
                        (100.4, 101.5, 98.0, 101.0), (101, 102, 100.8, 101.5)]),
            "BBB": _df([(100, 101, 99, 100)]),
            "CCC": None}
    def fetch(sym):
        if sym == "DDD":
            raise RuntimeError("feed down")
        return bars.get(sym)
    out = m.reclaim_flags(["AAA", "BBB", "CCC", "DDD"], ["SHORT", "SHORT", "SHORT", "SHORT"], fetch=fetch)
    assert out == {"AAA": True, "BBB": None, "CCC": None, "DDD": None}
    out2 = m.reclaim_flags(["AAA"], ["LONG"], fetch=fetch)
    assert out2 == {"AAA": False}
```

- [ ] **Step 2: Make the engine script importable without side effects**

Read the top of `scripts/v5-paper-trade.py` and its `if __name__ == "__main__":` block. If module import already performs no network or file writes (only definitions and constants), skip this step. If it does (for example it starts the engine or loads state at import), wrap that startup in `if __name__ == "__main__" and not os.environ.get("V5_IMPORT_ONLY"):` so a test can import the definitions. Keep the change minimal and do not move any function.

- [ ] **Step 3: Run to verify the test fails**

Run: `python3 -m pytest tests/test_v5_reclaim_flags.py -q`
Expected: FAIL with `AttributeError: module 'v5pt' has no attribute 'reclaim_flags'`.

- [ ] **Step 4: Implement the helper and the wiring**

Add near the other helpers in `scripts/v5-paper-trade.py` (above `_log_risk_gate_verdicts`):

```python
def _fetch_today_5m(symbol):
    """Today's completed 5-minute bars for one symbol: Kite first, yfinance cache second.
    Returns a DataFrame with Open/High/Low/Close or None."""
    try:
        from prototype.v4 import kite_data as kd
        df = kd.get_candles(symbol, "5minute", days=1)
        if df is not None and len(df):
            return df
    except Exception:
        pass
    try:
        from prototype.v4 import data_nse
        df = data_nse.get_intraday_candles(symbol, interval="5m")
        return df if df is not None and len(df) else None
    except Exception:
        return None


def reclaim_flags(symbols, sides, fetch=None):
    """{symbol: True|False|None} — swept-level reclaim flag per candidate, for the
    note: reason string. None means not evaluable (no bars, <4 bars, or fetch error).
    Observation only until 2026-09-19; the gate never acts on it."""
    from prototype.v5.reclaim import swept_level_reclaimed
    fetch = fetch or _fetch_today_5m
    out = {}
    for sym, side in zip(symbols, sides):
        if sym in out:
            continue
        try:
            df = fetch(sym)
        except Exception:
            out[sym] = None; continue
        if df is None or len(df) < 4:
            out[sym] = None; continue
        try:
            o = df["Open"].astype(float).tolist(); h = df["High"].astype(float).tolist()
            l = df["Low"].astype(float).tolist(); c = df["Close"].astype(float).tolist()
            out[sym] = bool(swept_level_reclaimed(o, h, l, c, len(o), side))
        except Exception:
            out[sym] = None
    return out
```

In `_log_risk_gate_verdicts`, before the loop that calls `gate.evaluate(plan, position_type=pos_type)`, compute the flags once from the candidate list you already iterate (the same `plan.symbol` and `pos_type` values), for example:

```python
    _syms = [c.get("symbol") for c in candidates]
    _sides = [(c.get("position_type") or ("SHORT" if str(c.get("direction", "")).upper() in ("SELL", "SHORT") else "LONG")) for c in candidates]
    _flags = reclaim_flags(_syms, _sides)
```

and change the evaluate call to `gate.evaluate(plan, position_type=pos_type, reclaim=_flags.get(plan.symbol))`. Read how `pos_type` is derived in that function and reuse exactly that expression for `_sides` rather than the sketch above if it differs.

Then verify with grep that the verdict is never used to decide deployment: `grep -n "verdict" scripts/v5-paper-trade.py` must show the verdict only being written into the verdicts file (and `inline_outcome` computed from `deployed_syms`). If any deployment decision reads `result.verdict`, STOP and report BLOCKED: the note design assumes verdicts are logging only.

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest tests/test_v5_reclaim_flags.py tests/test_risk_gate.py tests/test_reclaim.py -q`
Expected: all passed.

- [ ] **Step 6: Dry-run the engine script's import and a smoke of the helper against the real feed (Saturday: the feed returns Friday's bars; a live Kite token is not required because the yfinance fallback exists)**

```bash
cd /Users/soumyaswain/Documents/tinker/projects/tradepilot
V5_IMPORT_ONLY=1 python3 -c "
import importlib.util; s=importlib.util.spec_from_file_location('v5pt','scripts/v5-paper-trade.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m)
print(m.reclaim_flags(['RELIANCE','ADANIPORTS'], ['SHORT','SHORT']))"
```
Expected: a dict with `True`/`False`/`None` values and no traceback.

- [ ] **Step 7: Commit**

```bash
arch -arm64 git add scripts/v5-paper-trade.py tests/test_v5_reclaim_flags.py
arch -arm64 git commit -m "feat(v5): compute swept-level reclaim flag per candidate and record it as a verdict note (no behaviour change)"
```

---

### Task 5: Point the Floor's scouts at the engine universe

**Files:**
- Create: `quant/build_universe_engine.py`, `quant/universe_engine.txt` (generated)
- Modify: `prototype/agents/scouts.py` (`UNIVERSE_F` at line ~73)
- Test: `tests/test_scouts_universe.py`

**Interfaces:**
- Produces: `quant/universe_engine.txt`, one bare NSE symbol per line, derived from `prototype/data_engine.NIFTY_STOCKS` by stripping `.NS` and dropping `.BO` entries, sorted, de-duplicated.
- Produces: `scouts.py` resolves the universe file as `ROOT / "quant" / os.environ.get("FLOOR_UNIVERSE", "universe_engine.txt")`, falling back to `universe_full.txt` if the chosen file does not exist, and logs which file it used.
- `ENTRY_MODE` in `floor.py` stays `"shadow"`. Not touched.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_scouts_universe.py
import sys, os, importlib
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)


def test_engine_universe_file_matches_data_engine():
    from prototype.data_engine import NIFTY_STOCKS
    want = sorted({s.replace(".NS", "") for s in NIFTY_STOCKS if s.endswith(".NS")})
    got = [l.strip() for l in open(os.path.join(ROOT, "quant", "universe_engine.txt")) if l.strip() and not l.startswith("#")]
    assert got == want
    assert len(got) > 350


def test_scouts_universe_env_override(tmp_path, monkeypatch):
    f = tmp_path / "u.txt"; f.write_text("RELIANCE\nINFY\n")
    monkeypatch.setenv("FLOOR_UNIVERSE", str(f))
    import prototype.agents.scouts as sc
    importlib.reload(sc)
    assert sc.UNIVERSE_F == f


def test_scouts_universe_default_is_engine_file(monkeypatch):
    monkeypatch.delenv("FLOOR_UNIVERSE", raising=False)
    import prototype.agents.scouts as sc
    importlib.reload(sc)
    assert sc.UNIVERSE_F.name == "universe_engine.txt"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_scouts_universe.py -q`
Expected: FAIL (no `universe_engine.txt`, and `UNIVERSE_F` fixed to `universe_full.txt`).

- [ ] **Step 3: Build script and universe file**

```python
#!/usr/bin/env python3
# quant/build_universe_engine.py — the Floor's universe = the engines' universe.
# Rebuild whenever prototype/data_engine.py's stock lists change:
#     python3 quant/build_universe_engine.py
import os, sys
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)
from prototype.data_engine import NIFTY_STOCKS  # noqa: E402

syms = sorted({s.replace(".NS", "") for s in NIFTY_STOCKS if s.endswith(".NS")})
out = os.path.join(ROOT, "quant", "universe_engine.txt")
with open(out, "w") as f:
    f.write("\n".join(syms) + "\n")
print(f"wrote {out}: {len(syms)} symbols")
```

Run it: `python3 quant/build_universe_engine.py`.

- [ ] **Step 4: Scouts override**

In `prototype/agents/scouts.py`, replace the line `UNIVERSE_F = ROOT / "quant" / "universe_full.txt"` with:

```python
# 2026-09-12: the Floor watches the ENGINE universe by default, so its escalations land
# on stocks the engines trade (docs/research/floor/2026-09-11-floor-assessment.md §2).
# Override with FLOOR_UNIVERSE=<path or quant/ filename>; falls back to the full universe.
_uni = os.environ.get("FLOOR_UNIVERSE", "universe_engine.txt")
UNIVERSE_F = Path(_uni) if os.path.isabs(_uni) else ROOT / "quant" / _uni
if not UNIVERSE_F.exists():
    UNIVERSE_F = ROOT / "quant" / "universe_full.txt"
```

Make sure `os` and `Path` are imported at the top of `scouts.py` (add `import os` if missing; `Path` is already used for `ROOT`). Where `ScoutTeam.__init__` reads the file (line ~436), add one verbose log line after loading: `if self.verbose: print(f"scouts: universe {UNIVERSE_F.name} ({len(raw)} symbols)")` following the module's existing logging style.

- [ ] **Step 5: Run the tests**

Run: `python3 -m pytest tests/test_scouts_universe.py -q`
Expected: 3 passed.

- [ ] **Step 6: Dry-run the Floor's scout sweep (no Kite needed on Saturday? it IS needed for quotes; if `kite_data.enabled()` is false or the token is dead the sweep will report the feed error, which is acceptable for this check)**

```bash
python3 -c "
import sys; sys.path.insert(0,'.')
from prototype.agents import scouts as sc
print(sc.UNIVERSE_F)
t = sc.ScoutTeam(verbose=True)
print('universe size', len(t.universe))"
```
Expected: prints the `universe_engine.txt` path and a universe size around 380 to 410 after the ETF filter.

- [ ] **Step 7: Commit**

```bash
arch -arm64 git add quant/build_universe_engine.py quant/universe_engine.txt prototype/agents/scouts.py tests/test_scouts_universe.py
arch -arm64 git commit -m "feat(floor): scouts watch the engine universe by default (FLOOR_UNIVERSE override), so escalations land on traded stocks"
```

---

### Task 6: Full suite, notes, wrap

**Files:**
- Modify: `docs/research/floor/2026-09-11-floor-assessment.md` (append a "Status" section)
- Test: whole suite

- [ ] **Step 1: Full suite**

Run: `python3 -m pytest tests/ -q --ignore=tests/js`
Expected: everything green except the known pre-existing failure `tests/test_engine_discovery.py::test_real_tree_roster_for_2026_09_09`. Any other failure is a stop.

- [ ] **Step 2: Append status to the assessment**

Add at the end of `docs/research/floor/2026-09-11-floor-assessment.md`:

```markdown
## Status 2026-09-12
- Detector: `prototype/v5/reclaim.py` (tests `tests/test_reclaim.py`).
- Nightly shadow: `scripts/eod-veto-shadow.py`, step 6 of `scripts/eod-experiments.sh`, output `docs/research/shadows/veto/`, ledger `veto-ledger.csv`. Backfilled 08 to 11 Sep.
- Live tag: `note:swept_level_reclaimed: fired|clear|not evaluable` in every verdict's `reasons[]`; verdict unchanged. Visible via `/api/verdicts/<date>`.
- Floor: scouts default to `quant/universe_engine.txt` (env `FLOOR_UNIVERSE` overrides); `ENTRY_MODE` still `shadow`.
- Decision point: after 2026-09-19, if the ledger's reclaim bucket stays negative, promote the note to a hard check in `risk_gate.py` (one block, `soft_hit` semantics decided then).
```

- [ ] **Step 3: Commit**

```bash
arch -arm64 git add docs/research/floor/2026-09-11-floor-assessment.md
arch -arm64 git commit -m "docs(floor): status of the veto shadow, live tag and universe change"
```

- [ ] **Step 4: Report** the backfilled ledger numbers (Task 2 step 6) and the dry-run outputs (Task 4 step 6, Task 5 step 6) in the wrap-up. The Floor and engines are not restarted; the universe change takes effect at the next 09:16 launch and the live tag at the next engine start on Monday 2026-09-14.
