# Swing cost correction — multi-day pools re-costed at delivery rates

Date: 2026-09-10. Scope: M0 WP-1 (spec `docs/superpowers/specs/2026-09-10-m0-truth-first-design.md`, decision 2).
Status: applied to disk once, idempotent (second run adds 0, skips 13,847).

## The bug

Every closed trade in the fleet's SWING / POSITIONAL / INVESTMENT pools was costed by
`cost_for_trade` at the INTRADAY model — 12 bps of average notional — although a
position held overnight is a delivery (CNC) trade and pays the Zerodha delivery
schedule: brokerage 0; STT 0.1% on buy value **and** 0.1% on sell value; NSE exchange
transaction 0.00297% of turnover; SEBI 0.0001% of turnover; stamp duty 0.015% of buy
value; 18% GST on (brokerage + exchange + SEBI); DP charge Rs 15.34 + 18% GST per sell.
On a Rs 1.2 lakh position that is ~Rs 290 per round trip (≈24 bps), not ~Rs 145.

## What changed

- `scripts/v5-paper-trade.py`: `cost_for_trade(qty, entry, exit, pool="INTRADAY")`.
  INTRADAY and unknown pools return the old formula unchanged (intraday history stays
  byte-identical); SWING/POSITIONAL/INVESTMENT return the delivery round trip, 2 dp.
  `close_position` passes `pool_name`. Backup: `scripts/v5-paper-trade.py.bak-2026-09-10`.
- `scripts/recost-swing-ledgers.py`: for every closed multi-day trade in
  `docs/paper-trades/<engine>/YYYY-MM-DD.json` it **adds** `cost_delivery` and
  `pnl_net_delivery` (= `pnl` − `cost_delivery`). No existing key is modified; trades
  already carrying the keys are skipped; writes are atomic. 580 files touched.
- `tests/test_cost_model.py`: intraday == old formula (Rs 12.06 on 10 × 1000→1010),
  swing == hand-computed Rs 40.43, pool default stays intraday.

"Old cost" below is what the fleet accounting charged before the correction: the trade's
own `cost` field where the engine wrote one beside `pnl_net` (v5-family engines), else
the same 12-bps formula applied now. Note the `v5_swing` ledger (written by
`scripts/swing-engine.py`) never carried a fee at all — its `cost` key is the entry
notional, and its `pnl` is gross — so its "old net" is the 12-bps-equivalent number the
fleet reporters implied, not a figure the engine ever wrote.

## Before / after, per engine (closed multi-day trades, all dates on disk)

```
multi-day pools re-costed at Zerodha delivery schedule
engine           n      old cost      new cost       old net       new net  added  skip
---------------------------------------------------------------------------------------
v10            578      7,631.74     24,596.48     -1,825.53    -18,790.27    578     0
v5            2391     35,261.74    108,569.40    187,757.74    114,450.08   2391     0
v5_1L          241        414.96      5,130.95       -496.23     -5,212.22    241     0
v5_4           174      1,662.32      6,225.06     41,255.24     36,692.50    174     0
v5_5            56        703.34      2,315.00     16,743.06     15,131.40     56     0
v5_6           857     12,799.26     39,205.35    148,626.70    122,220.61    857     0
v5_7           737     10,041.94     31,927.68    136,740.55    114,854.81    737     0
v5_8           593      6,693.65     23,126.56     52,113.58     35,680.67    593     0
v5_apr         186      2,958.00      8,844.68      2,664.31     -3,222.37    186     0
v5_chop        228      1,363.87      6,652.96        643.62     -4,645.47    228     0
v5_classic    1564     24,352.41     73,405.25     64,251.50     15,198.66   1564     0
v5_cut        1106     15,519.05     48,760.29      3,494.62    -29,746.62   1106     0
v5_cut_1L      280        414.11      5,835.42       -721.40     -6,142.71    280     0
v5_deploy       18        421.64      1,106.76       -773.13     -1,458.25     18     0
v5_flip        969     13,212.53     42,008.80      4,126.99    -24,669.28    969     0
v5_gate        228      3,667.58     10,919.44     -2,002.59     -9,254.45    228     0
v5_hold        235      2,976.45      9,766.54     -3,797.86    -10,587.95    235     0
v5_kite        233      3,402.83     10,519.60     -3,546.18    -10,662.95    233     0
v5_long       1049     13,346.07     43,705.08     -7,491.61    -37,850.62   1049     0
v5_long_1L     302        451.21      6,302.11       -455.47     -6,306.37    302     0
v5_noml        220      3,455.06     10,380.89      1,818.26     -5,107.57    220     0
v5_pick         18        255.73        799.43       -107.42       -651.12     18     0
v5_rrg         223      1,377.29      6,587.27      1,878.43     -3,331.55    223     0
v5_swing        21      3,059.36      6,046.21     -3,280.86     -6,267.71     21     0
v5_time          2         72.65        170.75        -64.95       -163.05      2     0
v5_wide        526      8,584.33     25,415.92     42,683.67     25,852.08    526     0
v6             299      4,472.45     13,692.86     27,988.00     18,767.59    299     0
v7_regime      474      6,713.68     21,013.67     -1,524.21    -15,824.20    474     0
v8              39      1,070.66      2,688.98     -2,827.32     -4,445.64     39     0
---------------------------------------------------------------------------------------
FLEET        13847    186,355.92    595,719.39    703,871.50    294,508.03  13847     0
gross P&L 890,227.42 | files written: 580
```

Fleet total: **13,847** multi-day closed trades; modelled cost rises from
**Rs 1,86,356 to Rs 5,95,719** (3.2×); fleet multi-day net falls from
**Rs 7,03,872 to Rs 2,94,508** on Rs 8,90,227 gross. Six engines flip from net positive to net negative (v5_apr, v5_chop, v5_cut, v5_flip,
v5_noml, v5_rrg); the ones already negative (v10, v5_1L, v5_cut_1L, v5_long_1L,
v5_deploy, v5_gate, v5_hold, v5_kite, v5_long, v5_pick, v5_swing, v5_time, v7_regime,
v8) get worse. The three that keep a clearly positive multi-day net are v5 (+1.14 L),
v5_6 (+1.22 L) and v5_7 (+1.15 L), followed by v5_4, v5_5, v5_8, v5_wide, v6.

## The 0.62%/deployment claim (ENGINE-GRAVEYARD.md, v5_swing row)

**Method.** The graveyard figure is reproduced exactly from the v5_swing ledger as
gross P&L ÷ Σ(qty × entry price) over the 7 trades closed through 2026-08-21:
Rs 5,308.40 ÷ Rs 8,53,457.50 = **0.622%**. So the claim was a *gross* return on
deployed capital with no cost deducted at all. Recomputed the same way with
`cost_delivery` read from the ledger:

| Window | n | Deployed (Rs) | Gross (Rs) | Gross % | Delivery cost (Rs) | Cost % | Net delivery (Rs) | **Net %/deployment** |
|:--|--:|--:|--:|--:|--:|--:|--:|--:|
| Through 08-21 (the graveyard's 7) | 7 | 8,53,457.50 | 5,308.40 | 0.622% | 2,028.98 | 0.238% | 3,279.42 | **0.384%** |
| All closed to date (08-20 → 09-03) | 21 | 25,49,575.81 | −221.50 | −0.009% | 6,046.21 | 0.237% | −6,267.71 | **−0.246%** |

What the claim becomes:

- On its own 7 trades, "0.62%/deployment" is **0.38%/deployment net of delivery costs**
  (the intraday-costed equivalent would have shown ~0.50%). The direction of the
  argument survives on that window; the number does not.
- On the full 21-trade sample now on disk the engine is **−0.25%/deployment net**:
  Rs 221 gross loss became Rs 6,268 net loss once each round trip pays ~Rs 290. The
  "move-to-cost ratio 40:1" framing was built on the 12-bps cost; at 24 bps it is ~20:1,
  and the realised moves (median |pnl_pct| = 1.36% across the 21) have not been large enough to clear
  it. The graveyard's own gate ("~60 closed swings vs random-dip control at 0.24% CNC")
  was already priced at the right cost; the survivor row's headline was not.
- The graveyard file is left as written (historical record). This document is the
  correction; the ledger fields are the evidence.

## Reproduce

```
python3 scripts/recost-swing-ledgers.py --dry-run     # summary, no writes
python3 -m pytest tests/test_cost_model.py -q
```
