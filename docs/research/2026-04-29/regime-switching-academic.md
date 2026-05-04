# Regime-Switching Trading Systems — Academic Literature Review

## Bottom line (3 sentences max)

The academic literature firmly establishes that asset returns exhibit statistically distinct regimes (typically 2–4 states: bull/bear, or crash/slow-growth/bull/recovery) and that conditioning portfolio choice on the inferred regime delivers economically significant out-of-sample welfare gains over a single unconditional strategy (Ang-Bekaert 2002, Guidolin-Timmermann 2007). However, the gains are critically sensitive to **regime-detection latency** (1-day vs 5-day lag in 2020 = 2.5% vs 12.5% drawdown absorbed) and to **look-ahead bias** in regime labelling — a large fraction of published Sharpe gains evaporate under strict walk-forward validation (Kirby 2022). For Indian markets, Markov-switching evidence on Nifty/Sensex is published but sparse; bull regimes are highly persistent (transition prob ~0.99) which reduces the *frequency* of switching benefit relative to US data.

## Seminal papers

| Year | Author | Paper | Takeaway |
|---|---|---|---|
| 1989 | Hamilton | "A New Approach to the Economic Analysis of Nonstationary Time Series and the Business Cycle" (Econometrica 57:357-384) | Foundational two-state Markov-switching model; matches NBER recession dating from price data alone. The mathematical engine the entire field uses. |
| 2002 | Ang & Bekaert | "International Asset Allocation With Regime Shifts" (RFS 15(4):1137-87) | Cross-country equity correlations rise from ~0.45 (bull) to ~0.65 (bear); regime-aware portfolios still beat static diversification. Cited 4000+ times. |
| 2007 | Guidolin & Timmermann | "Asset Allocation under Multivariate Regime Switching" (JEDC 31:3503-44) | **Four** regimes (crash / slow-growth / bull / recovery) needed for joint stock-bond returns; ignoring regimes has a measurable welfare cost even after parameter-uncertainty haircut. |
| 2011 | Ang & Timmermann | "Regime Changes and Financial Markets" (NBER WP 17182) | Survey: regimes are real, persistent, and economically priced; pure linear models systematically mis-state tail risk. |
| 2022 | Kirby | "A Closer Look at the Regime-Switching Evidence of Bull and Bear Markets" (Finance Research Letters / SSRN 4183191) | **Critical caveat paper**: much of the apparent regime-switching alpha disappears once you correct for in-sample regime labelling and use real-time inference only. |

## What the literature says works

- **Specialization beats unconditional** when the unconditional model has high parameter instability across regimes (Guidolin-Timmermann: optimal stock weight differs by 30-60 ppts between crash and bull states).
- **2-state at minimum, 4-state often better** for stock-bond joint distributions; more than 4 states overfits (G-T 2007).
- **Regime-conditional CAPM betas** are statistically different from unconditional betas — strategies trained on a single beta misprice tail risk (Ang-Bekaert).
- **Pairs-trading + regime filter** is one of the few robust applications: Sharpe up to 3.92 reported on S&P 500 high-frequency data after costs (Bui-Slepaczuk 2018).
- **Jump models** (recent: Nystrup et al, arXiv 2402.05272) outperform classical HMMs because they penalize rapid switching and are more robust to detection lag.

## Known failure modes

- **Look-ahead bias in regime labels** — regimes are typically labelled using the smoothed Hamilton filter, which uses *future* data; real-time filtered probabilities have weaker signal (Hamilton 1989; Kirby 2022).
- **Detection latency cost** — empirical: Feb-Mar 2020 transition cost ~2.5%/day for first 5 days; a 5-day-lag detector eats 12.5% before switching. ML detectors 0-2 day lag, simple VIX rules 3-5 day lag.
- **Regime-count overfitting** — Guidolin-Timmermann show BIC selects 4 states; naive maximum-likelihood selects 6+ which fail OOS.
- **In-sample Sharpe inflation** — Quant practitioner literature (Man Group; QuantConnect "Rage Against the Regimes") argues most "regime-aware" results are post-hoc rationalization of which sub-period the strategy worked in.
- **Persistence trap** — if `p_ii` ≈ 0.99 (Indian Nifty bull regime), the model rarely switches, so the regime-switching layer adds parameters without adding decision events. The conditional gain ≈ 0 in the long run.
- **Selection bias on multiple tests** — CFA Institute model-validation guide flags that published regime-switching backtests are filtered for the ones that "worked".

## Indian-market specific findings

Limited but published research:

- **MPRA Working Paper 37174** (Kannan & Aravind, applying Hamilton's 2-state model to NSE-Nifty and BSE-Sensex): Bull-regime transition probability `p_bull,bull` ≈ 0.97-0.99, bear `p_bear,bear` ≈ 0.94-0.97. **Bull regimes are dominant and persistent** — Sensex spent ~70-80% of 1991-2010 in the bull state.
- Longest observed bull run in Sensex: 481 days (Jun 2004 - May 2006). Sub-prime contagion bear regime: ~280 days for Sensex, ~229 days for Nifty (Aug 2008 - Jul 2009).
- Implication for TradePilot: with `p_bull,bull` ≈ 0.99 daily, expect ~1 regime switch per ~100 trading days. A specialized bear engine will be cold-started often. Side-by-side observation (a la TradePilot v5 plan) is mandatory because pure historical bear-data is scarce post-2009.

Indian Markov-switching literature is genuinely thin — most Indian quant papers use GARCH, not regime-switching, and almost none publish out-of-sample Sharpe.

## Gaps the literature has not answered

- **No consensus on optimal switching threshold** — when does posterior `P(bear|data) > θ` justify flipping engines? Most papers use θ=0.5 with no sensitivity analysis.
- **Transition-cost-aware regime switching** is barely studied — literature usually assumes frictionless rebalancing on regime change.
- **Ensemble vs winner-take-all routing** — almost no papers compare a soft mixture (weight by posterior regime probability) against hard switching. The Sharpe-decomposition argument suggests soft mixtures dominate when regime posteriors are uncertain, but this is empirically underexplored.
- **Multi-asset specialization** in Indian context — no published work runs separate models per Nifty sector under regime switching.
- **Online/streaming HMM recalibration** — academic models typically refit monthly; intraday regime drift handling is a research gap.

## Sources

- [Hamilton 1989 — original Econometrica paper PDF](https://users.ssc.wisc.edu/~behansen/718/Hamilton1989.pdf)
- [Hamilton 2005 — Regime-Switching Models survey](https://econweb.ucsd.edu/~jhamilto/palgrav1.pdf)
- [Ang & Bekaert 2002 — International Asset Allocation With Regime Shifts](https://business.columbia.edu/sites/default/files-efs/pubfiles/1971/1137.pdf)
- [Guidolin & Timmermann 2007 — Asset Allocation under Multivariate Regime Switching (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=940652)
- [Ang & Timmermann 2011 — Regime Changes and Financial Markets (NBER 17182)](https://www.nber.org/system/files/working_papers/w17182/w17182.pdf)
- [Kirby 2022 — A Closer Look at the Regime-Switching Evidence (SSRN)](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=4183191)
- [Nystrup et al 2024 — Statistical Jump Model for regime-switching (arXiv 2402.05272)](https://arxiv.org/abs/2402.05272)
- [MPRA 37174 — Identifying regime shifts in Indian stock market (Markov-switching Nifty/Sensex)](https://mpra.ub.uni-muenchen.de/37174/1/MPRA_paper_37174.pdf)
- [Bull and Bear Phases NSE/BSE — empirical regime study](https://www.academia.edu/38125624/Bull_and_Bear_Phases_An_Empirical_Perusal_of_Indian_Stock_Market_NSE_and_BSE_Stock_Markets)
- [QuantConnect — "Rage Against the Regimes" critique of regime-specific strategies](https://www.quantconnect.com/forum/discussion/14818/rage-against-the-regimes-the-illusion-of-market-specific-strategies/)
- [CFA Institute — Investment Model Validation Guide for Practitioners](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/article/rf-brief/investment-model-validation.pdf)
