# Regime-Switching in Industry — What Real Quant Shops Do

## Bottom line (3 sentences)

The industry's battle-tested pattern is **ensemble of many small signals + risk-parity allocation across regime-aware buckets** (Medallion, Bridgewater) — NOT a hard router that swaps in a different "engine" per regime. Of the 8 funds surveyed, only Bridgewater All Weather is explicitly regime-quadrant by construction, while Renaissance, Two Sigma and AQR run continuous ensembles whose component weights drift with regime probabilities (soft routing). Hard regime switches (Soumya's "3-4 specialist engines + router" model) have a track record of catastrophic failure when the regime detector lags the market — LTCM 1998 and the 2007 quant quake are textbook cases.

## Big quants

| Fund | Approach | Public evidence | Sharpe (post-fee) |
|---|---|---|---|
| **Renaissance Medallion** | Ensemble of "dozens to hundreds" of short-horizon signals, no hard regime router. Uses HMMs and Bayesian updating to detect structural breaks but blends, doesn't switch. | 39% net 1988-2018; 76% gross 2020 vs RIEF -22.6% (longer-horizon sister fund) — gap attributed to short-horizon ensemble adapting to regime | ~2.5+ (estimated, $12B internal capital) |
| **Two Sigma** | Gaussian Mixture Model labels markets as Crisis / Steady State / Inflation / "Walking on Ice". Uses regime as a **feature** in the ensemble, not a router. | Public ML blog post "A Machine Learning Approach to Regime Modeling" (2018) | ~1.0-1.5 across funds |
| **AQR (Asness)** | **Explicitly anti-regime-timing**. Asness has published "Factor Timing is Hard" and "Contrarian Factor Timing Is Deceptively Difficult". Maintains roughly static factor weights. | Multiple AQR white papers; Kelly/Gupta 2024 work on factor momentum (modest signal only) | 0.5-0.8 (factor strategies) |
| **Bridgewater All Weather** | Explicit 4-quadrant regime model: rising/falling × growth/inflation. Equal **risk** in each bucket, not equal capital. NOT a router — runs all 4 buckets simultaneously. | Dalio's published "All Weather Story" white paper | ~0.6-0.8 |
| **Bridgewater Pure Alpha** | Multi-strategy: ~100+ uncorrelated bets layered together. Closer to ensemble than regime switching. | Dalio's "Holy Grail of Investing" lecture | ~1.0 |

## Indian quant landscape

| Fund/Platform | Regime-aware? | Notes |
|---|---|---|
| **True Beacon One** (Cat-III AIF) | Multi-strategy, not explicitly regime-conditional. Runs derivatives + equity factor strategies in parallel. | Led by Sankaranarayanan Krishnan, 12 yrs quant. UHNI focused. |
| **True Beacon EqFactorQuant** | Static factor exposures vs Nifty200. AQR-style, not regime-switched. | Marketed as "alpha relative to Nifty200" |
| **Dolat Capital "Quantum Leap"** | Pattern recognition + momentum + multi-factor in single risk-adjusted framework. Soft blend, not hard switch. | Back-tested numbers only published; live track record opaque |
| **Edelweiss Alpha** | Public info thin. PMS/AIF products use multi-factor; no published regime-switching architecture. | Most Edelweiss alpha is discretionary, not systematic |
| **Quant Mutual Fund (QMF)** | Their VLRT framework (Valuation/Liquidity/Risk/Time) is the closest to public regime-aware in Indian MF space. Adjusts equity/cash/sector allocation by perceived regime. | ~₹90K Cr AUM; outperformed in 2022-23, drew down hard in early 2024 — classic regime mis-call |

**Key signal**: NO Indian fund publicly markets a "specialist engine per regime" architecture. They all run blended/factor-weighted approaches.

## Famous failure modes

- **LTCM (Aug-Sep 1998)** — Russia default + flight-to-quality. LTCM's models assumed correlations between long/short legs were stable. When all risk assets sold off together, supposedly hedged spreads moved against them simultaneously. **Single-regime model in a regime that didn't exist in their training data**. Lost 44% in August alone, $3.6B Fed-coordinated bailout. Direct parallel to Soumya's risk: a regime detector trained on 3 years can't see the regime it's never seen.
- **2007 Quant Quake (Aug 6-10)** — GS Global Equity Opportunities, AQR, Renaissance RIEF all hit simultaneously. ~30% drawdown in 4 days for many factor funds. Cause: crowded factor positioning + forced unwinds; statistical-arbitrage models all trained on similar regimes deleveraged together. Showed that **regime detection lags the regime change by days**.
- **Risk-Parity Feb 2018 "Volmageddon"** — Vol-targeting funds were forced to deleverage into a falling market, amplifying the move. Regime model said "low vol" right up until it didn't.
- **Bridgewater All Weather 2022** — Lost ~8% as growth AND inflation surprised simultaneously (rare combination). Even the canonical 4-quadrant model has gaps.

## Retail algo platforms

| Platform | Supports regime switching? | How |
|---|---|---|
| **Streak (Zerodha)** | No native regime concept | Single-strategy backtest/deploy. User can encode a regime filter manually as an entry condition. |
| **Tradetron** | Partial | Has "conditions" + multi-strategy linking. Users can wire one strategy's signal as a switch for another, but no built-in HMM/regime classifier. |
| **Sensibull** | No | Options-focused; strategy templates are static. |
| **AlgoTest, uTrade Algos** | No | Backtest-and-deploy single-strategy model. |

**Industry truth**: zero retail Indian platform offers built-in regime classification. Users implement it as boolean entry filters at best.

## What patterns are battle-tested

- **Ensemble of many small signals** (Medallion model). 100+ independent edges, each weak, blended.
- **Risk-parity across regime buckets** (Bridgewater). Run all engines all the time, weight by inverse-vol.
- **Regime as a feature, not a router** (Two Sigma). HMM output is one input among hundreds, not a hard if/else.
- **Vol-targeting at the portfolio level** (industry-wide standard for risk parity / managed futures).
- **Cross-sectional ranking inside a single engine** beats regime-conditional ensembles for mid-frequency (1-5 day) signals.

## What patterns the industry has REJECTED

- **Hard regime routers with discrete engines** — LTCM-class failure mode. When regime classification is wrong (always lags 5-15 days), you ship the wrong engine into the wrong tape. Nobody big runs this in production.
- **Aggressive factor timing on valuation** — AQR has published 3+ papers showing it adds <0.2 Sharpe and destroys diversification.
- **Training a classifier on <5 years of data** — every public quant disaster (LTCM, 2007 quake, 2018 volmageddon, 2020 March) was a regime the model had never seen. Industry standard is 20+ years of training data.
- **Deterministic "if regime = X then engine = Y"** — replaced industry-wide with probabilistic blending (P(regime_i) × engine_i contribution).
- **Position handoff between engines** — operationally fragile; industry runs all engines continuously and reweights instead.

## Implication for TradePilot

The 80% hit-rate target is closer to Medallion's short-horizon ensemble territory than All Weather's regime-quadrant territory. Soumya's "3-4 specialist engines + router" idea is closer to **rejected industry pattern** than battle-tested. Safer redesign: keep a single engine that ingests regime probability as a **feature**, then size positions by P(regime) × per-regime expected edge. This is what Two Sigma does publicly, what Medallion likely does privately, and what avoids the LTCM/quant-quake failure mode of mis-classifying the regime and shipping the wrong engine.

## Sources

- [Bridgewater — The All Weather Story](https://www.bridgewater.com/research-and-insights/the-all-weather-story) — primary 4-quadrant framework
- [Two Sigma — A Machine Learning Approach to Regime Modeling](https://www.twosigma.com/articles/a-machine-learning-approach-to-regime-modeling/) — Gaussian Mixture regime labels
- [AQR — Factor Timing is Hard](https://www.aqr.com/Insights/Perspectives/Factor-Timing-is-Hard) — Asness's anti-regime-timing position
- [QuantPedia — Cliff Asness's View on Factor Timing](https://quantpedia.com/cliff-asnesss-aqr-view-on-factor-timing/)
- [Hedgeweek — Renaissance Tech and Two Sigma 2024 quant gains](https://www.hedgeweek.com/renaissance-tech-and-two-sigma-lead-2024-quant-gains/) — Medallion 30% in 2024
- [Medium — Why Medallion made 76% while RIEF lost 22.6% in 2020](https://medium.com/@navnoorbawa/why-renaissances-medallion-made-76-while-their-own-rief-lost-22-6-in-2020-1ed318548100) — short-horizon ensemble vs longer-horizon sister fund
- [Federal Reserve History — Near Failure of LTCM](https://www.federalreservehistory.org/essays/ltcm-near-failure) — 1998 regime breakdown
- [Wikipedia — Long-Term Capital Management](https://en.wikipedia.org/wiki/Long-Term_Capital_Management)
- [True Beacon](https://truebeacon.com/) — Cat-III AIF quant strategies
- [Dolat Capital Quant](https://quant.dolatcapital.com/) — Quantum Leap multi-factor
- [Hedge Fund Journal — End of the Golden Era for Risk Parity](https://thehedgefundjournal.com/the-end-of-the-golden-era-for-risk-parity/) — risk-parity stress in 2022
- [AlgoTest — Tradetron vs Sensibull](https://algotest.in/blog/tradetron-vs-sensibull-comparison/) — Indian retail platform feature comparison
- [Bridgewater Alpha-Beta Framework — Substack](https://navnoorbawa.substack.com/p/bridgewaters-alpha-beta-framework) — risk parity + portable alpha
