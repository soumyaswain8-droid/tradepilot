# Agent Floor assessment — 2026-09-11

Sources: `docs/sarathi/knowledge/shadow/settled.jsonl` (985 settled shadow trades, 28 Aug to 11 Sep),
`docs/sarathi/knowledge/escalations/<day>.jsonl`, engine day files, and the 5-min candle replays in
`docs/watchdog/reports/<day>_eod/left-on-table.json` (08 to 11 Sep). All read-only.

## 1. The Floor's own trade rule loses

Shadow entries (LONG only, SWEEP_RECLAIM rule, 0.5% risk, 1.5R target), settled net of costs, rupees at the Floor's own ~₹2,850 notional per trade:

| Day | n | Win | Net ₹ | Stops | Targets |
|---|---:|---:|---:|---:|---:|
| 2026-09-04 | 122 | 20% | -884 | 93 | 24 |
| 2026-09-07 | 138 | 14% | -1,434 | 115 | 20 |
| 2026-09-08 | 188 | 18% | -1,791 | 151 | 33 |
| 2026-09-09 | 136 | 18% | -1,419 | 110 | 24 |
| 2026-09-10 | 112 | 18% | -1,010 | 88 | 20 |
| 2026-09-11 | 140 | 24% | -1,138 | 103 | 33 |
| **All 10 days** | **985** | **20%** | **-8,291** | 764 | 197 |

Every level (ROUND, DAY_LOW, DAY_HIGH, PDH, PDL) and every agreement count (2, 3, 4 scouts) loses. A 1.5R target at a 20% hit rate cannot pay: breakeven needs 40%. The stop at 0.5% is inside normal 5-minute noise for these names. Conclusion: the detection is not the problem, the entry rule is.

## 2. The Floor and the engines do not share a universe

Symbols traded by v5 / v5_wide that the Floor also watched, per day: 0/41, 1/44, 0/43, 1/59, 2/36, 0/11, 2/42, 0/65. Engine shorts entered within 10 minutes of a Floor SWEEP_RECLAIM event: **zero in four days.** The Floor scouts the full market (`quant/universe_full.txt`) and settles on small and mid caps; the engines trade the 451-name scored universe. As built, the Floor cannot veto anything the engines do.

## 3. But the pattern the Floor detects is exactly the engines' loss

Offline detector on the engines' own 5-minute candles: a SHORT is tagged **reclaim** if, in the 15 minutes before entry, a bar broke below the session low so far and closed back above it. Tagged **hammer** if a bar had a lower wick of at least half its range and closed in the top half. Otherwise **clean**.

| Tag | Shorts | Gross ₹ | Avg ₹ | Win |
|---|---:|---:|---:|---:|
| reclaim | 66 | **-2,226** | -33.7 | 30% |
| hammer | 101 | +512 | +5.1 | 52% |
| clean | 96 | -710 | -7.4 | 50% |

Per engine-day the reclaim bucket was negative on 7 of 8 (the exception is one trade on 10 Sep). A hammer alone predicts nothing; a swept-and-reclaimed low does. Shorting into it cost ₹2,226 gross over four sessions, roughly a quarter of all short losses, from a quarter of the shorts.

## 4. What this means

- **Keep the Floor's detection, drop its trade rule.** Its SWEEP_RECLAIM has lift over random (+0.11pp on 248 events today per `floor-eod.py`) and the same shape predicts engine losses. Its LONG entries at 0.5% stop do not.
- **Point it at the engine universe** so its events land on stocks the engines actually trade. Today they never coincide.
- **The veto is worth building, as a shadow first.** Tag every engine SHORT at entry with `swept_low_reclaimed_15m` (computable from the same 5-min bars the engine already has), log it in the verdicts file as a soft reason, and score it at EOD. Do not block until the 08 to 19 Sep shadow-experiment window closes, because blocking changes v5's entry set and contaminates the arm-band and regime replays.
- **Retire the "team" surface.** Only the model gate and the launch gate are load-bearing; both become Ready-page check rows.

## 5. Proposed next steps

1. `scripts/eod-veto-shadow.py <date>`: the section-3 detector, run from `eod-experiments.sh`, writing `docs/research/shadows/veto/<date>.json` with per-trade tags and the three-bucket totals. Adds a line to the EOD commit body.
2. Engine-side tag only (no block): in the v5 family entry path, compute the reclaim flag from the last three 5-min bars and append `soft:swept_low_reclaimed: fired` to the verdict reasons. Visible on Market's "why we skipped it" and Review's cause chips. Flip to a hard block after 2026-09-19 if the shadow holds.
3. Floor: set the scout universe to the engine universe file and keep `ENTRY_MODE = "shadow"`; leave the trade rule alone until step 1 shows whether a wider stop fixes it.

## Status 2026-09-12
- Detector: `prototype/v5/reclaim.py` (tests `tests/test_reclaim.py`).
- Nightly shadow: `scripts/eod-veto-shadow.py`, step 6 of `scripts/eod-experiments.sh`, output `docs/research/shadows/veto/`, ledger `veto-ledger.csv`. Backfilled 08 to 11 Sep.
- Live tag: `note:swept_level_reclaimed: fired|clear|not evaluable` in every verdict's `reasons[]`; verdict unchanged. Visible via `/api/verdicts/<date>`.
- Floor: scouts default to `quant/universe_engine.txt` (env `FLOOR_UNIVERSE` overrides); `ENTRY_MODE` still `shadow`.
- Decision point: after 2026-09-19, if the ledger's reclaim bucket stays negative, promote the note to a hard check in `risk_gate.py` (one block, `soft_hit` semantics decided then).
