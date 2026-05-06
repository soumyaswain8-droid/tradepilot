# Revival Mechanics Research — 2026-05-06

Background: v4 made 0 trades on 2026-05-05 because VIX > 18 cut capital
to 50% and 40 BUYs all fell below the Rs 20K position-sizer floor. User
asked for behavioral risk management instead of structural capital cuts:
per-stock -10% loss cap, watch period with candle analysis, smart re-entry,
and reconsidering the daily kill switch.

This doc captures the 4 parallel sub-agent research findings + the design
decisions that became `prototype/v4/candle_patterns.py` and the v4
revival mechanics in `scripts/v4-paper-trade.py`.

## Agent A — Candlestick Reversal Patterns

7 codable patterns ranked by published hit rate after a 5-10% intraday drop:

| # | Pattern | Bars | Hit Rate | Source |
|---|---------|:---:|:---:|---|
| 1 | Bullish Hammer | 1 | 50–63% | Bulkowski 1997 |
| 2 | Bullish Engulfing | 2 | 63–66% | UMich 2018 / altFINS |
| 3 | Piercing Line | 2 | 64–75% | Quantified Strategies |
| 4 | Morning Star | 3 | 65–78% | Quantified Strategies |
| 5 | Bullish Harami | 2 | 55–60% | LiteFinance |
| 6 | Tweezer Bottom | 2 | ~55% | TradesViz |
| 7 | Three White Soldiers | 3 | 70–82% | Quantified Strategies |

**Volume rules** (lift accuracy 15-20pp per LuxAlgo):
- Hard filter: signal-bar volume ≥ 1.5× 20-bar SMA. Below = reject.
- Strong confirm: ≥ 2.0× SMA on the trigger candle.

**Time-of-day windows** (NSE / IST):
- 09:15–09:45: SKIP (opening volatility creates fakes)
- 09:45–11:15: weaker, requires 2.0× volume
- **11:15–12:30**: SWEET SPOT (highest hit rates documented)
- 12:30–14:00: lunch lull, low validity
- 14:00–14:45: secondary window
- 14:45–15:30: SKIP (closing-auction unwind)

**Ship-first recommendation**: Bullish Engulfing + 1.5× volume +
11:15–14:45 IST + price within 0.5% of post-drop low. Highest
signal-to-complexity ratio: 2-bar geometry, single volume check,
~65% raw hit rate, trivial to vectorize.

## Agent B — ML Approaches to Revival Prediction

| Rank | Model Family | Practicality | Notes |
|:-:|---|:-:|---|
| 1 | LightGBM / XGBoost (tabular) | 9/10 | Best for small data, fast, interpretable |
| 2 | Logistic Regression (indicator panel) | 8/10 | Ship-tonight baseline, regulator-friendly |
| 3 | Random Forest | 7/10 | Robust but worse than GBM in published studies |
| 4 | LSTM / GRU | 4/10 | Needs >50K labeled events, GPU |
| 5 | Transformers | 2/10 | Overkill at this sample size |

**Top features** (most → least predictive):
1. Market regime (Nifty 1m return, India VIX level/delta) — strongest
2. Volume features (relative vs 20-day intraday avg)
3. Drawdown microstructure (speed of fall, wick ratio of stoploss bar)
4. Momentum oscillators (RSI, MACD divergence)
5. Candle OHLCV ratios

**Realistic accuracy bound**: 57-62% AUC for single-stock retail data.
Published 80%+ numbers are on **index** reversals with clean labels and
look-ahead protection — single-stock retail caps at ~62-65%.

**#1 pitfall**: Look-ahead bias via random k-fold splits. Intraday bars
are autocorrelated; same-day events share regime. Random splits leak
future bars into training. **Always use time-based split + purge/embargo
+ walk-forward validation.**

**Phase 2 ship plan**: Build labeled dataset of historical drawdowns
(target = +5% within 45 min without -3% intermediate leg). Train
LightGBM with `scale_pos_weight` (revivals are 30-40% of drawdowns; do
NOT use SMOTE). Walk-forward refit monthly. Threshold at p > 0.65 for
re-entry.

Sources: IJISAE 2024, ScienceDirect 2021, arXiv 2501.16772 (Safari &
Schmidhuber), Wharton thesis (Fan Zhang), CS229 Stanford.

## Agent C — How Pros Handle Losing Positions

**Institutional pattern**: Size small, stop systematic, never debate.
Citadel/Two Sigma/Renaissance public risk doctrine = portfolio-level
VaR + per-trade sizing cap (~1% of portfolio) so no single position
breaching -10% is consequential. Risk engineered out at sizing, not at
the stop.

**Retail-pro voices**:
- **Linda Raschke**: "Losers are subject to hitting the initial stop —
  no debate." Never add to a loser.
- **Brett Steenbarger**: Mentally rehearse the stop-out *before* entry
  so the exit is muscle memory.
- **Tom Sosnoff (tastytrade)**: Size small, defend losers (options
  only). Critics note tastytrade's "let losers run to 100%" requires
  4:1 win rate to break even — works for premium-sellers, NOT
  directional intraday.
- **SMB Capital**: Hybrid — distant hard stop (catastrophe) + closer
  soft stop (managed exit) + wait for confirmed re-entry signal
  before re-deploying.

**Academic verdict**: Stop-loss overlay on momentum strategies converts
worst crash months from -49.79% to +1.69% (Han et al., "Taming
Momentum Crashes"). **Hold-and-hope at -10% intraday has negative
expected value.** Cutting is the dominant strategy.

**Indian retail context**: Vivek Bajaj, Kunal Saraogi, Zerodha Varsity
all converge on 1-2% capital risk per trade. -10% on a single position
is already 3-5× the canonical capital-risk rule.

**Recommendation**: Hard stop at 1.5-2% of capital per position; on
stop-out, blacklist the symbol for N minutes, require an INDEPENDENT
re-entry signal (higher low + volume) before re-deploying — never
average down, never widen a stop intraday.

## Agent D — Kill-Switch Design

**Industry table**:
| Platform | Trigger | Action |
|---|---|---|
| IBKR TWS | User-defined | Per-position only |
| Zerodha Streak | Per-strategy SL/TP + capital cap | SOFT halt (entry block) |
| AlgoTest / Tradetron | MaxLoss / MaxProfit per strategy | SOFT halt |
| QuantConnect | Drawdown%, Liquidate button | Per-asset; full kill is opt-in |
| FTMO/Topstep | 5% daily loss | Account flagged (no engine flatten) |

**Hard halt vs soft halt**: Industry default is **SOFT halt** (block new
entries, let per-trade stops handle existing positions). Forced mid-day
liquidation crystallizes slippage. Hard liquidate is reserved for
fat-finger / runaway-bot scenarios.

**Static vs dynamic**: SOTA is dynamic. ATR-scaled, trailing daily
limit, regime-conditional. Static Rs caps are legacy retail.

**SEBI/NSE 2025-26**: Mandatory broker-level kill switch from Apr 2026.
**No mandatory portfolio-level Rs/% kill is prescribed for the
trader's own engine** — discretionary.

**Recommendation for retail with per-stock caps already in place**:
3-tier WARN/SOFT/HARD model. Per-stock and portfolio kills are
complementary (one stops outliers, other stops correlated meltdowns).
Hard kill at -2% (true "something is wrong" level), not at -1% (a
normal bad day).

## Design Decisions (Implemented 2026-05-06)

| Decision | Choice | Reasoning |
|---|---|---|
| Capital cut on VIX > 18 | REMOVED | Caused the 0-trades bug; behavioral risk replaces it |
| Per-stock loss cap | -10% from entry (in addition to scorer's 1% SL + trailing) | User-spec; layered with existing 1% trailing SL |
| Re-entry cap counter | LOSING exits only (winners unrestricted) | User-spec; profitable stocks shouldn't be capped |
| Max losses per stock | 2 | User-spec; matches existing MAX_REENTRY_PER_STOCK |
| Re-entry gate (after loss) | Bullish Engulfing + 1.5× volume + 11:15-14:45 IST + price within 0.5% of post-drop low | Highest signal-to-complexity per Agent A |
| ML revival classifier | Phase 2 (deferred) | Needs labeled historical drawdowns; multi-day data project |
| Kill switch | 3-tier WARN -Rs 2.5K / SOFT_HOLD -Rs 5K / HARD_KILL -Rs 10K or 3+ pct-SL exits | Per Agent D research |
| Position sizer wrapper | REVERTED | Behavioral risk replaces structural patch |

## Files Touched

- `prototype/v4/position_sizer.py` — reverted to pre-2026-05-06 (no iterative drop)
- `prototype/v4/candle_patterns.py` — NEW (Bullish Engulfing + volume + window + near-low gates)
- `scripts/v4-paper-trade.py` — revival mechanics + 3-tier kill + loss-count gate

## Phase 2 Roadmap (Next Sprint)

1. Build labeled drawdown-recovery dataset from `prototype/data/intraday/` historical bars
2. Train LightGBM with time-based split + purge + walk-forward
3. Replace rule-based `revival_signal()` with ML probabilistic decision (threshold p > 0.65)
4. Add Morning Star + Hammer to the rule-based fallback (when ML is uncertain)
5. ATR-scaled kill-switch thresholds once 30+ trading days of live data accumulate
