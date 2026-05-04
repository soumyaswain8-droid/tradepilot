# Tomorrow Morning Checklist — Thursday 2026-04-30
> **04-29 EOD update**: 7th engine **v5.8** added tonight after the 04-29 RCA
> identified v5's regime-aware slot partition as the v5-vs-v4 bottleneck (v5
> blocked 175 LONG signals on a green-tape day labelled BEAR; v4 took those
> signals and made +Rs 47K vs v5's +Rs 18K). v5.8 is v5 with the slot partition
> disabled — LONG and SHORT each get up to 20 slots in any regime, the 20-total
> cap still applies. Everything else identical to v5.
>
> **Tomorrow's roster (7)**: v4 (control), v5 (Fix #1 + slot partition active),
> v5_classic, v5_6, v5_7, v6 (v4 raw + Track A), **v5.8 (v5 with no slot cap)**.
>
> **Pre-market commands** (run in this order before 9:15 IST):
> 1. `caffeinate -di -t 28800 &` — keep laptop awake 8 hours through close (or `disown` after)
> 2. `./scripts/launch-market.sh` — fires all 7 engines + monitors
> 3. `./scripts/launch-market.sh --status` — verify 7/7 engines + 4/4 monitors
>
> **Tonight pre-prep done**: ML model retrained at 22:45 IST (will be ~10h fresh tomorrow), 7-engine roster wired in all 3 registries, all compile checks pass, 16/16 unit tests OK, daily research watchdog now firing 07:00 IST.
>
> **The two-way test tomorrow**:
> 1. v5.8 vs v5: does removing the slot partition close the gap to v4? If v5.8 ≈ v4 → partition was the bottleneck.
> 2. v5.8 vs v4: does v5's wrapper still hurt even without the slot cap? If v5.8 < v4 → there's another bottleneck (likely H2 re-emission debounce).

---

# Tomorrow Morning Checklist — Wednesday 2026-04-29 (yesterday's plan, kept for reference)

> **Read this first when you wake up.** Tonight's changes target the structural
> v5-vs-v4 gap (Rs 21,282 on 04-28) by isolating the signal layer from the
> Track A bolt-on. Total time before 9:15 IST market open: ~10 minutes.

---

## v6 vs v6.1 — don't get these confused

| Name | What it is | Trades tomorrow? |
|---|---|---|
| **v6** | A Python script (scripts/v6-paper-trade.py). The 6th paper-trading engine. v4 signals + Track A bolt-on. | **Yes** — alongside v4, v5, v5_classic, v5_6, v5_7 |
| **v6.1** | A 24-page roadmap document for the production system we plan to build over 36-40 weeks. Zero lines of code exist yet. | **No** — it's just a plan |

Tomorrow's runner is **6 engines** (v4, v5, v5_classic, v5_6, v5_7, v6). v6.1 sits on the shelf.

---

## What was shipped overnight (TL;DR)

The 04-28 EOD post-mortem identified that v5's `signal_engine` wrapper
mechanically converts the bottom 10/20% of v4-scored stocks into SHORTs based on
regime — even when those stocks aren't actually weak. On a green tape (Nifty
+0.81%) this bled v5 by Rs ~21K vs v4. Two fixes ship tonight, both as
**experiments** rather than commits.

| What | Where | Purpose |
|---|---|---|
| **Fix #1**: SHORT requires absolute weakness | `prototype/v5/signal_engine.py` (lines 50-51, 182-229) | Stops v5 forcing SHORTs in green tape: now requires `change_pct < -0.5%` AND `score < 35` to emit a SHORT |
| **v6 engine NEW**: "v4 raw signals + Track A bolt-on" | `scripts/v6-paper-trade.py` | Bypasses v5's wrapper entirely. Calls v4's `composite_scorer` directly with absolute thresholds (BUY ≥60, SHORT ≤35 + change_pct < -0.5%). Inherits all Track A from v5 base. |
| v4 stays in active observation | (unchanged) | Control. 04-28 made +Rs 26,179 — retirement was wrong. |
| 6-engine roster everywhere | `launch-market.sh`, `crash-watchdog.sh`, `status-digest.py` | All three registries updated |

**Engines tomorrow (6)**: v4 (control), v5 (Fix #1 + Track A), v5_classic, v5_6, v5_7, v6 (raw v4 + Track A).

**Nothing committed.** All code stays in working tree per the no-commit-during-observation rule.

---

## The experiment: what tomorrow's EOD answers

| Compare | Question |
|---|---|
| v6 vs v4 | Does Track A (SHORT_BLOCK + RE-ARM + FLAT_EXIT + cost modeling) add value when sitting on a v4-quality signal layer? Today watchdog said Track A was worth +Rs 7,132 to v5. |
| v5 (Fix #1) vs v5 (yesterday) | Did Fix #1 close the SHORT-bleed leak? Watch for fewer "actually_weak=False filtered" entries in the log. |
| v5 (Fix #1) vs v6 | Is v5's wrapper still hurting even after Fix #1? If v6 > v5 by significant margin, the wrapper has more bugs. If v5 ≈ v6, Fix #1 was sufficient. |
| v4 vs v6 vs v5 | Three-way race. Pick the winner over the next 4 weeks. |

Full spec: `docs/learning/2026-04-29-v5-vs-v6-experiment.md`

---

## Pre-Market (before 9:15 IST) — ~10 min

Run these in order:

```bash
cd ~/Documents/tinker/projects/tradepilot

# 1. Confirm 6 engines configured
./scripts/launch-market.sh --status

# 2. Verify ML model still fresh (best_iter ≥ 100)
python3 -m prototype.v4.ml_engine --info | head -5

# 3. Run Track A unit tests
python3 tests/test_track_a.py 2>&1 | tail -5

# 4. Verify Fix #1 + v6 compile cleanly
python3 -c "
import importlib.util
for f in ['prototype/v5/signal_engine.py', 'scripts/v6-paper-trade.py']:
    code = open(f).read()
    compile(code, f, 'exec')
    print(f'  OK {f}')
"

# 5. Launch the full battle stack
./scripts/launch-market.sh
```

**Expected output**:
- `--status` should list 6 engines (v4, v5, v5_classic, v5_6, v5_7, v6), all "NOT RUNNING" pre-launch
- `ml_engine --info` should show `best_iter ≥ 100`
- Tests print "OK" with 16/16 passing
- `launch-market.sh` reports "Engines: 6/6" in the verify step

---

## During Market (9:15 - 15:35 IST) — passive watch

**The four-week observation freeze continues.** No engine code changes during
this window per `docs/IMPLEMENTATION_BRIEF_2026-04-27.md` §3.

What to watch in v5's log (`tail -F logs/v5-2026-04-29.log`):

| Log marker | Meaning |
|---|---|
| `(Fix#1 filtered N bottom-ranked-but-not-weak SHORTs)` | New today. Fix #1 actively rejecting forced SHORTs. |
| `[SHORT_BLOCK]` near 9:15-10:15 | Track A still suppressing SHORTs first 60 min if bullish gap up. |
| `[RE-ARM]` after TARGET hits | Winner re-deploying. |
| `FLAT_FORCE_EXIT` at 13:30-14:00 | Flat positions auto-closed. |

What to watch in v6's log (`tail -F logs/v6-paper-trade.log`):

| Log marker | Meaning |
|---|---|
| `[v6] BUY signals: N, SHORT signals: M` per scan | Direct count of how many absolute-threshold qualifiers each scan |
| `[RE-ARM]` after TARGET hits | Track A's re-arm working on v4-quality signals |

If anything looks wrong: just observe. **Do NOT touch code mid-day.**

If a single engine crashes: kill its PID and let others continue. The crash
watchdog will attempt one restart. DO NOT restart with code changes.

---

## EOD (after 15:35 IST) — ~30 min

```bash
cd ~/Documents/tinker/projects/tradepilot

# 1. Final P&L per engine
python3 scripts/status-digest.py

# 2. Watchdog insights for v5 (compare to 04-28's findings)
cat docs/learning/v5-2026-04-29-insights.md

# 3. Diff v6 vs v5 vs v4 closed-trade counts/pnl
python3 -c "
import json, pathlib
for e in ['v4','v5','v5_classic','v5_6','v5_7','v6']:
    fp = pathlib.Path(f'docs/paper-trades/{e}/2026-04-29.json')
    if not fp.exists(): print(f'{e:12s} NO REPORT'); continue
    d = json.loads(fp.read_text())
    if e == 'v4':
        cl = d.get('closed_trades') or [p for p in d.get('positions',[]) if p.get('status')=='closed']
        pnl = d.get('realized_pnl', sum(t.get('pnl',0) for t in cl))
    else:
        cl = d.get('pools',{}).get('INTRADAY',{}).get('closed',[]) + d.get('pools',{}).get('SWING',{}).get('closed',[])
        pnl = sum(t.get('net_pnl', t.get('pnl',0)) for t in cl)
    wins = sum(1 for t in cl if t.get('net_pnl', t.get('pnl',0)) > 0)
    wr = (100*wins/len(cl)) if cl else 0
    print(f'{e:12s} P&L Rs {pnl:>8,.0f}  trades {len(cl):3d}  WR {wr:4.1f}%')
"

# 4. How often did Fix #1 fire?
grep -c "Fix#1 filtered" logs/v5-paper-trade.log

# 5. Add 1-2 line entry to docs/observation_journal.md
```

**Decision matrix for tomorrow night's writeup**:

| Outcome | Read as |
|---|---|
| v6 > v4 by ≥ Rs 3K | Track A is genuinely helpful. Keep v6 in observation, retire v5. |
| v6 ≈ v4 (±Rs 2K) | Track A neutral on v4 signals; the gain we saw on v5 came from compensating for v5's bugs. Drop Track A complexity. |
| v6 < v4 by ≥ Rs 3K | Track A is hurting v4. Investigate which Track A rule (SHORT_BLOCK most likely) is mis-firing on v4's signal mix. |
| v5 (Fix #1) ≈ v6 | Fix #1 closed the gap. v5 wrapper viable with this patch. |
| v5 (Fix #1) << v6 | Wrapper has more bugs beyond Fix #1. Suspect: re-emission of recently-traded symbols (the WINNER_RE_ARM-via-v4 pattern). |

One day is one sample. Don't decide on Wednesday alone — feed all three into
the May 25 gate.

---

## What is NOT happening (intentionally)

- ❌ No commit yet — code stays in working tree until weekend / Thursday review
- ❌ No ML training work for 4 weeks (gated to 2026-05-25 decision)
- ❌ No further new engine variants (v6 is the last for this round)
- ❌ No parameter tuning during observation window
- ❌ No code changes if a single bad day happens

---

## If something is broken when you wake up

| Symptom | Quick fix |
|---|---|
| `launch-market.sh` won't start, module error | `python3 tests/test_track_a.py` to see if v5 broke. If syntax issue in signal_engine.py, comment out the Fix #1 block (lines 196-208) and let v5 run unfixed for the day. |
| v6 fails to import on launch | Engine starts background-decoupled. Check `logs/v6-paper-trade.log` for stack trace. Common: missing v4 module path. Fallback: skip v6 today, run other 5 engines. |
| `[Fix#1 filtered]` never appears in v5 log | Either no candidate SHORTs hit the bottom rank (rare on a green tape — possible on a bear tape), or the filter is firing but stocks all pass. Check by adding `print(actually_weak, stock_change, stock_score)` in signal_engine.py:198. |
| v6 log shows BUY signals: 0 across all scans | v4 score threshold (V6_BUY_MIN_SCORE=60) too tight for today's regime. Lower to 55 only IF a full half-day passes with zero v6 trades. |
| Single engine crashes mid-day | Crash watchdog will restart once. If repeats, pkill it and let others run. |

Worst case rollback: `git checkout prototype/v5/signal_engine.py scripts/v6-paper-trade.py scripts/launch-market.sh scripts/crash-watchdog.sh scripts/status-digest.py`. All changes are uncommitted.

---

## Reference docs

| Doc | When to read |
|---|---|
| `docs/learning/2026-04-28-eod-summary.md` | Yesterday's full RCA — why v4 won, why v5 lost |
| `docs/learning/2026-04-29-v5-vs-v6-experiment.md` | Tonight's experiment design + measurement plan |
| `docs/IMPLEMENTATION_BRIEF_2026-04-27.md` | Authoritative plan. Source of truth. |
| `docs/RETIRED_ENGINES.md` | What was retired tonight and why (v4 strikethrough = re-instated) |
| `docs/observation_journal.md` | Weekly journal — fill every EOD |

---

**Sleep well.** When you wake up the engines are ready: v4 untouched as control,
v5 with Fix #1 tightening SHORT emission, v6 testing the cleanest hypothesis
(v4 signals + Track A only). Tomorrow you observe. You don't code.
