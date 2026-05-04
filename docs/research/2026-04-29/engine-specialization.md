# Engine Specialisation — How to Train Per-Regime Engines

## Bottom line (3 sentences)

Do **not** train three fully-separated LightGBM models on hard-sliced BULL/BEAR/SIDEWAYS data — bear regimes in Indian equity are too rare (~30% of trading days but concentrated in clusters; for intraday F&O the "bear" feature distribution is even narrower) to support a robust standalone bear scorer, and pure slicing leaks the future-regime label into training. The best-supported pattern from recent literature (MDPI 2026 *Regime-Aware LightGBM* and López de Prado's purged-CV work) is **one base model with a regime feature plus a small head/specialised exit-rule layer per regime**, validated with rolling/expanding walk-forward and combinatorial purged CV (CPCV). For TradePilot v5/v6 this means: keep the v4 LightGBM scorer, add a regime-detector probability vector as features, and specialise only the **position-sizing and exit-rule layers** per regime — not the scorer itself.

## Data partitioning options

| Strategy | What it does | Pros | Cons |
|---|---|---|---|
| Pure regime slice | Train BULL model only on BULL-labeled days, ditto BEAR, SIDEWAYS | Cleanest specialisation; each model "sees" only its regime | **Label leakage** (the regime label depends on future returns); BEAR slice ~30% of days, often <500 intraday samples after embargoing — too small for LightGBM stability; cold-start problem at regime transitions |
| Weighted sampling | Single model, sample weights boosted on rare regimes (e.g. 3× weight on BEAR rows) | Uses full dataset; LightGBM `sample_weight` native; reduces class imbalance | Subtle leak via weight = regime label; weight tuning becomes a hyperparam to overfit |
| Continuous regime feature | One model; regime probability vector (P_bull, P_bear, P_sideways) injected as input features | No leakage if HMM/detector is **rolling/online**; full-sample efficiency; tree splits learn regime-conditional logic naturally | Model may underweight rare regimes; harder to inspect per-regime behaviour without SHAP-by-regime slicing |
| Hybrid (recommended) | Shared base scorer with regime feature, **plus** thin per-regime heads (calibration + exit rules + sizing) | Combines sample efficiency with specialisation where it matters most (exits, sizing, not scoring); matches MDPI 2026 framework | More moving parts; needs disciplined ablation per layer |

## The sample-size problem

- Indian bear days are **clustered, not uniformly distributed**. Across 35 years, drawdowns of 20%+ have occurred ~6–8 times, and most "bear" days bunch into 3–9 month windows (2008, 2011, 2015–16, 2020-Mar, 2024-Q4). For an **intraday** TradePilot training window of e.g. 2019–2025 with ~1,500 trading days, BEAR-regime intraday minutes might be only 15–20% of the dataset — and even less per-symbol after F&O liquidity filtering.
- MDPI 2026 reports ~30% bear days, but that is **daily**, on developed-market data with a 2-decade window. For Indian intraday on a 5-year window the effective BEAR sample for a per-symbol model is often <2,000 rows — below LightGBM's reliable training floor (~5–10k rows for stable trees).
- **Mitigations**: (1) train at the **universe level** (pool all 451 assets), not per symbol; (2) use **synthetic minority oversampling (SMOTE-Time)** carefully — only on engineered features, never raw OHLCV; (3) **transfer learning from US bear data** (2008, 2020, 2022 SPX) as a warm-start, fine-tune on Indian data; (4) **regime feature** approach (single model) sidesteps the problem entirely.

## Feature selection per regime

(MDPI 2026 SHAP findings + ML4Trading patterns)

| Regime | Top features | Avoid |
|---|---|---|
| BULL | 3-month momentum, breakout-of-range, volume-thrust, ADX trend strength, sector relative strength, IV-rank low | Mean-reversion oscillators (RSI<30 buy fails in trends), narrow Bollinger band signals |
| BEAR | Distance-from-200-SMA (negative), VIX level + VIX slope, USD/INR, FII flow Z-score, PUT/CALL ratio, gap-down magnitude, 3-month momentum (negative side) | Naïve momentum-long features; trend-following crossovers (whipsaw); breakouts (false in capitulation) |
| SIDEWAYS | RSI(2)/RSI(14), Bollinger %B, ATR-normalised distance from VWAP, Hurst exponent <0.5, PIN bar / reversal candles | Trend-strength features (ADX); breakout features; long-horizon momentum |

Empirical evidence: MDPI 2026 SHAP analysis on a regime-aware LightGBM showed the **same model** auto-shifts feature importance — yield-curve proxy and gold/equity ratio dominate in BEAR; market beta and 3-mo momentum dominate in BULL — strong evidence that the **regime feature** approach allows tree splits to do per-regime feature gating without separate models.

## ML model choices

| Regime | Recommended model | Why |
|---|---|---|
| BULL | LightGBM (same as base) | Trending data is well-modeled by tree boosting; momentum non-linearities captured |
| BEAR | LightGBM **+ macro feature pack** | Don't switch families; just add macro features (VIX, FII, USD/INR) — non-stationarity in BEAR is a feature problem, not a model-family problem |
| SIDEWAYS | LightGBM **with shorter horizon target** (15–30 min next-bar) | Mean-reversion lives at shorter horizons; same family, different label |
| All | One LightGBM + regime features (preferred) | Tree splits naturally do regime gating; fewer overfitting surfaces; CPCV-friendly |

Avoid LSTM-per-regime: under-data and over-engineered for tabular features TradePilot already has.

## Exit rules per regime

| Regime | Exit philosophy |
|---|---|
| BULL | Trailing stop (Chandelier 3×ATR), let winners run, partial book at 1R/2R, no fixed TP |
| BEAR | **Tight SL (0.5–1×ATR)**, fixed TP at 1R, time-stop after 30 min, no overnight, smaller size |
| SIDEWAYS | TP/SL bracket at Bollinger bands, 1:1 risk-reward, fade extremes, exit at VWAP touch |

This is where specialisation **must** happen — the scorer can be shared, the exit logic cannot. TradePilot already has a sizer; needs a per-regime exit-rule table.

## Overfitting prevention

- **Walk-forward with regime labels computed online.** The regime label at time t must use only data ≤ t. Use a **rolling HMM** (re-fit every N days on trailing window) — never a global HMM fit on the whole history. MDPI 2026 used rolling fit specifically for this reason.
- **Block CV preserving regime structure.** Use López de Prado's **Combinatorial Purged Cross-Validation (CPCV)** with embargo ≥ label horizon. Standard k-fold leaks across regime boundaries.
- **Out-of-sample regime validation.** Hold out *entire regime episodes* (e.g. all of 2020-Mar, all of 2024-Q4) — not random days within them. If model trained on 2019–2023 fails on held-out 2024-Q4 bear, you have regime-specific overfit, not noise.
- **Probability of Backtest Overfitting (PBO) + Deflated Sharpe Ratio (DSR).** MDPI 2026 reports both — make these mandatory acceptance gates for any regime-specialised variant before promotion.
- **Ablation: regime-feature ON vs OFF.** If adding regime features doesn't beat the no-regime baseline by ≥10% on DSR, the specialisation is noise.

## Indian-market specific calls

- **F&O expiry days** (Nifty Thu, Bank Nifty Tue post-Nov-2024): treat as a **sub-regime feature flag** (`is_expiry`, `mins_to_expiry`), not a separate engine. Theta-decay and pin-risk dominate the last 90 min — encode as features. Sample size per year is ~104 expiries — enough for feature-level learning, not enough for a standalone scorer.
- **Budget day, RBI policy days, election days**: treat as **event flags** with sample weights. ~15–20 such days/year — far too sparse for standalone engines. A `days_to_event` countdown feature plus `is_event_day` boolean is sufficient.
- **Election cycle**: A 5-year cycle with ~60 trading days of pre/post-election volatility per cycle = ~12 days/year — feature, not engine.
- **Stock-specific corporate action regimes** (results day, dividend, bonus): per-symbol event features.

Rule of thumb: **<50 days/year of a sub-regime → feature; >100 days/year → consider its own exit-rule layer; >300 days/year → consider its own scorer head.** Only the 3 macro regimes (BULL/BEAR/SIDEWAYS) clear the third bar.

## Concrete recommendation for TradePilot

**Do not split v4 LightGBM into 3 hard-sliced engines.** Instead, in this order:

1. **Phase 1 (week 1) — Regime features.** Add the C-agent's regime detector output as 3 continuous features (`P_bull`, `P_bear`, `P_sideways`) plus one categorical (`regime_argmax`) into the existing `prototype/v4/composite_scorer.py` LightGBM input matrix. Re-train with CPCV. Acceptance: DSR improvement ≥ 0.15 vs no-regime baseline.
2. **Phase 2 (week 2) — Per-regime exit & sizing layer.** Keep the scorer; add a `regime_policy` table that maps `(regime, signal_strength) → (SL_mult, TP_mult, trail_type, size_mult)`. This is where 80% of the regime-specialisation alpha lives in practice (per Numerai/QuantConnect tutorials).
3. **Phase 3 (week 3, only if Phase 1+2 underperform) — Per-regime calibration heads.** Train a tiny per-regime isotonic-regression calibrator on top of the shared LightGBM scorer (López-de-Prado-style). Cheap, low-overfit risk.
4. **Phase 4 (defer) — Fully separated engines.** Only if Phases 1–3 plateau and BEAR data has been augmented (US transfer + 2024-Q4 + 2020-Mar). Until then, the 3-engine approach has worse expected Sharpe than the regime-feature approach due to BEAR sample starvation.

**Validation protocol (mandatory for every variant):**
- Rolling HMM (252-day window) for regime labels — never global.
- CPCV with 6 splits, 2 test groups, embargo = max label horizon (15 min for intraday, 1 day for swing).
- Hold-out entire regime episodes (2020-Mar, 2024-Q4) as final OOS.
- Promote only if DSR > 1.0 AND PBO < 30% AND held-out regime-episode Sharpe > 0.5× in-sample Sharpe.

**Indian-market features to add now (cheap, high-leverage):**
- `vix_india_level`, `vix_india_5d_change`
- `fii_dii_flow_z` (NSE bhavcopy, T-1)
- `usd_inr_change`
- `is_expiry_nifty`, `is_expiry_banknifty`, `mins_to_expiry`
- `days_to_rbi_policy`, `is_event_day` (budget/RBI/election)

These move the regime-feature approach 80% of the way to "specialised engines" without paying the BEAR sample-starvation cost.

## Sources

- [Regime-Aware LightGBM for Stock Market Forecasting (MDPI Electronics 2026)](https://www.mdpi.com/2079-9292/15/6/1334) — primary blueprint: rolling HMM + LightGBM + walk-forward + DSR/PBO. Reports 32.5% bull / 36.8% sideways / 30.7% bear day distribution.
- [Step-by-Step Python Guide for Regime-Specific Trading Using HMM and Random Forest (QuantInsti)](https://blog.quantinsti.com/regime-adaptive-trading-python/) — implementation-level patterns, regime-feature vs separate-model tradeoffs.
- [Cross Validation in Finance: Purging, Embargoing, Combinatorial (QuantInsti)](https://blog.quantinsti.com/cross-validation-embargo-purging-combinatorial/) — CPCV mechanics for regime-conditional training.
- [Purged cross-validation (Wikipedia)](https://en.wikipedia.org/wiki/Purged_cross-validation) — López de Prado method, embargo rules.
- [Traditional Backtesting is Outdated. Use CPCV Instead (InsightBig)](https://www.insightbig.com/post/traditional-backtesting-is-outdated-use-cpcv-instead) — PBO and DSR as overfitting gates.
- [Backtest overfitting in the ML era (ScienceDirect)](https://www.sciencedirect.com/science/article/abs/pii/S0950705124011110) — quantifies overfit risk per CV method.
- [Autonomous Trading Across Bull, Bear, and Sideways Markets with RL (ResearchGate)](https://www.researchgate.net/publication/400349572) — RL alternative; useful as upper-bound benchmark.
- [Stefan Jansen — Machine Learning for Trading (GitHub)](https://github.com/stefan-jansen/machine-learning-for-trading) — reference code for LightGBM + walk-forward + regime features.
- [What History Tells Us About Indian Stock Market Corrections (Wright Research)](https://www.wrightresearch.in/blog/what-history-tells-us-about-indian-stock-market-corrections/) — Indian bear-regime frequency and clustering.
- [How many bear markets have we seen in India? (Arthgyaan)](https://arthgyaan.com/blog/bear-markets-in-india.html) — sample-size baseline for BEAR engine.
- [Bank Nifty Expiry Day Explained 2026 (AlgoTest)](https://algotest.in/blog/bank-nifty-expiry-day/) — expiry-day microstructure for sub-regime feature engineering.
- [Share Market Expiry Days in India 2026 (Lemonn)](https://lemonn.co.in/blog/fno/understanding-share-market-expiry-days-guide/) — current Nifty Thu / Bank Nifty Tue schedule.
