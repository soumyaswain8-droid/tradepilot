# DAYGAIN Phase 0 — holdout backtest verdict (2026-09-07)

Pre-registered spec: `~/Downloads/2026-09-05-daygain-lane-spec.md` (rule FROZEN, no parameter changed). Harness: `scripts/daygain-phase0.py`. Data: real Kite Connect 5-minute bars.

**Window:** holdout only, 2026-07-01 → 2026-09-04, 48 trading days (first session in the cache, 2026-05-29, has no prior close and is outside the window anyway). The 2021 → 2026-06 train window was **not run** — no local minute bars exist for it and Kite's 5-minute history is served ~100 days per request; it is out of scope for this run.

## Gates (all three must pass)

| # | Gate | Value | Result |
|--:|---|---:|:--:|
| 1 | Net edge per basket-day > 0 after full costs + slippage | ₹-3,117/day (all 48 days); ₹-3,117/day on 48 traded days | **FAIL** |
| 2 | t-stat of daily net returns ≥ 2.0 | -1.62 | **FAIL** |
| 3 | Max drawdown of daily equity curve ≤ 15% of ₹1,125,000 | 18.34% (₹206,317) | **FAIL** |

**Verdict: FAIL — lane dies here.**

## Totals

| Metric | Value |
|---|---:|
| Trading days | 48 |
| Days with a basket | 48 |
| Days killed by Nifty < −1.0% at 09:35 | 0 |
| Positions taken | 480 |
| Stopped out (−3%) | 181 |
| Gross P&L | ₹-108,020 |
| Costs (real_cost schedule) | ₹41,573 |
| **Net P&L** | **₹-149,593** |
| Net return on ₹11.25L | -13.30% over 48 days; -0.277%/day |
| Daily net σ | 1.184% |
| Win days (net > 0) | 20/48 (42%) |
| Avg cost per position (round trip) | ₹87 |
| Avg gross per position | ₹-225 |
| Mean 09:35 %chg of picks | 6.32% |

## Per-day

| date | n_pos | gross | costs | net | nifty_0935 | killed |
|---|--:|--:|--:|--:|--:|:--:|
| 2026-07-01 | 10 | -4,876 | 866 | -5,742 | +0.01% |  |
| 2026-07-02 | 10 | -6,305 | 865 | -7,170 | +0.57% |  |
| 2026-07-03 | 10 | -6,309 | 866 | -7,176 | +0.78% |  |
| 2026-07-06 | 10 | -7,441 | 865 | -8,306 | +0.40% |  |
| 2026-07-07 | 10 | 4,960 | 869 | 4,091 | +0.01% |  |
| 2026-07-08 | 10 | -23,287 | 861 | -24,148 | -0.55% |  |
| 2026-07-09 | 10 | 13,361 | 871 | 12,490 | +0.59% |  |
| 2026-07-10 | 10 | -12,466 | 864 | -13,331 | +0.85% |  |
| 2026-07-13 | 10 | -12,231 | 864 | -13,096 | -0.76% |  |
| 2026-07-14 | 10 | -11,723 | 864 | -12,588 | -0.32% |  |
| 2026-07-15 | 10 | 2,228 | 868 | 1,360 | +0.69% |  |
| 2026-07-16 | 10 | -1,160 | 863 | -2,024 | +0.15% |  |
| 2026-07-17 | 10 | -8,290 | 865 | -9,155 | +0.52% |  |
| 2026-07-20 | 10 | 9,684 | 871 | 8,813 | -0.68% |  |
| 2026-07-21 | 10 | -11,118 | 865 | -11,982 | -0.06% |  |
| 2026-07-22 | 10 | -2,637 | 864 | -3,501 | -0.70% |  |
| 2026-07-23 | 10 | -23,056 | 861 | -23,917 | -0.31% |  |
| 2026-07-24 | 10 | -12,204 | 864 | -13,068 | -0.77% |  |
| 2026-07-27 | 10 | -8,972 | 863 | -9,835 | +0.63% |  |
| 2026-07-28 | 10 | -6,449 | 863 | -7,312 | -0.04% |  |
| 2026-07-29 | 10 | 10,971 | 871 | 10,101 | +0.83% |  |
| 2026-07-30 | 10 | -19,508 | 862 | -20,370 | +0.13% |  |
| 2026-07-31 | 10 | -5,599 | 863 | -6,462 | +0.06% |  |
| 2026-08-03 | 10 | 12,871 | 871 | 12,000 | +0.77% |  |
| 2026-08-04 | 10 | -4,132 | 866 | -4,999 | -0.74% |  |
| 2026-08-05 | 10 | 1,368 | 868 | 500 | -0.02% |  |
| 2026-08-06 | 10 | 12,148 | 866 | 11,281 | -0.00% |  |
| 2026-08-07 | 10 | 14,092 | 863 | 13,228 | -0.14% |  |
| 2026-08-10 | 10 | -14,499 | 859 | -15,357 | -0.15% |  |
| 2026-08-11 | 10 | 3,721 | 867 | 2,854 | -0.39% |  |
| 2026-08-12 | 10 | -18,619 | 862 | -19,481 | -0.13% |  |
| 2026-08-13 | 10 | -15,495 | 863 | -16,357 | -0.46% |  |
| 2026-08-14 | 10 | 2,330 | 867 | 1,463 | -0.29% |  |
| 2026-08-17 | 10 | -14,475 | 862 | -15,337 | -0.32% |  |
| 2026-08-18 | 10 | 20,494 | 873 | 19,622 | -0.23% |  |
| 2026-08-19 | 10 | -16,644 | 863 | -17,507 | -0.34% |  |
| 2026-08-20 | 10 | -5,559 | 866 | -6,424 | +0.50% |  |
| 2026-08-21 | 10 | 23,401 | 874 | 22,527 | -0.10% |  |
| 2026-08-24 | 10 | -8,127 | 865 | -8,991 | +0.10% |  |
| 2026-08-25 | 10 | -22,150 | 861 | -23,011 | -0.12% |  |
| 2026-08-26 | 10 | 15,749 | 872 | 14,876 | +0.04% |  |
| 2026-08-27 | 10 | 5,393 | 869 | 4,524 | +0.01% |  |
| 2026-08-28 | 10 | 28,044 | 875 | 27,169 | +0.23% |  |
| 2026-08-31 | 10 | 2,671 | 868 | 1,804 | -0.49% |  |
| 2026-09-01 | 10 | -25,237 | 860 | -26,097 | -0.06% |  |
| 2026-09-02 | 10 | 12,191 | 870 | 11,321 | -0.88% |  |
| 2026-09-03 | 10 | 17,579 | 872 | 16,707 | +0.33% |  |
| 2026-09-04 | 10 | 7,290 | 870 | 6,420 | +0.14% |  |

## Data caveats

- **Bar convention:** Kite labels 5-min bars by START time (first bar 09:15). The 09:35 signal price is the Close of the bar labelled 09:30 (covers 09:30–09:35). Fill is the Open of the bar labelled 09:35 (first print after 09:35) × 1.001. Square-off is the Close of the bar labelled 15:10 (the bar that ends 15:15). Stop is checked on every bar from the fill bar through the 15:10 bar inclusive on Low ≤ stop, filled at the stop price (no gap slippage).
- **Bar coverage (equities):** share of symbol-days by last-bar label — before 2026-08-03: 15:25 99.6%, 15:10 0.0%, earlier 0.4%; from 2026-08-03: 15:25 90.5%, 15:10 8.7%, earlier 0.9%. From 2026-08-03 onward a minority of equity symbol-days (incl. RELIANCE on 2026-09-04) carry 72 bars with the last bar labelled 15:10 — the 15:15, 15:20 and 15:25 bars are absent from Kite's 5-minute history for those symbol-days (the NIFTY 50 index frame has all 75 bars every day); Kite also omits bars with zero trades, which is why illiquid names end earlier still. Consequence: the exit bar (15:10) is always present, but the **prior close** used for %chg is the Close of the previous session's last available bar — 15:25 bar before Aug 3, 15:10 bar from Aug 3 — not the official settlement close. NIFTY 50 prior close = its 15:25 bar close.
- **Coverage:** universe 2,634 symbols; 2041 have a cached 5-min frame and were evaluated; 593 not covered (6 with no NSE instrument token today — delisted/renamed, so survivorship is NOT clean for those; 0 fetch errors/empties; the rest not attempted: the fetch stopped at its 12-minute budget, so the cache is a file-order prefix of the universe (alphabetical, last cached symbol SARVESHWAR), not a random sample — the uncovered tail is the S–Z range).
- **ADV filter:** real 20-session average turnover from the NSE bhavcopy (`quant/data/bhavcopy_daily.parquet`, `turnover_lakh`), as of the previous session — not a close×volume proxy. The bhavcopy ends 2026-08-31, so 2026-09-01..04 reuse the window ending 08-31 (≤4 sessions stale). Symbols absent from the bhavcopy were skipped (3888 symbol-days).
- **ASM/GSM stage ≥ 2 filter: NOT applied** — no historical ASM/GSM list is available locally. This can only make the backtest look better than live, never worse.
- **Upper-circuit filter:** proxied as (09:35 price == day high so far AND chg ≥ 9.5%), as instructed; exact band data is not in the bars.
- **Index kill:** real NIFTY 50 index bars (instrument token 256265), same bar convention; no proxy was needed.
- **'Gainer' definition:** only symbols with chg > 0 at 09:35 are ranked; this bound on 20636 symbol-days and never reduced a basket below 10 on a non-killed day.
- **Filter tallies (symbol-days):** {"no_prev": 4414, "no_bar": 4507, "price": 19097, "adv": 23007, "adv_missing": 3888, "chg_gt15": 6, "uc_proxy": 4, "not_gainer": 20636}.
- **Costs:** `real_cost()` copied verbatim from `scripts/v5_god-paper-trade.py` (brokerage min(0.03%, ₹20)/order, STT 0.025% sell, NSE txn 0.00297%, SEBI ₹10/cr, stamp 0.003% buy, 18% GST). Not imported via importlib because that file executes a paper-trading CLI at import.
- **Holdout-only.** Nothing was tuned; the rule was run once as written. No train window.

## Falsification sentence — outcome

Phase 0 holdout FAILS on: net edge > 0, t-stat ≥ 2.0, MDD ≤ 15%. In plain words: on real 5-minute bars, buying the top-10 09:35 gainers and holding to 15:15 with a −3% stop made ₹-149,593 net over 48 sessions (t=-1.62, MDD 18.3%). Day-gainer persistence at this horizon is not a net edge after honest costs on clean data; the +₹172k ledger number was truncation bias plus one hot regime, and the lane is dead. No parameter search follows. The reusable residue is this harness, the 5-min cache and the cost math.