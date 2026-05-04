# Regime Detection — Best Practices for TradePilot

## Bottom line (3 sentences)
TradePilot v5's BEAR-all-day on a +0.81% green tape is the textbook failure mode of a **static, lagging, vote-aggregating detector with no hysteresis** — half its indicators (200-DMA, 5d FII, 5d momentum) only flip days after the tape turns, so they pin BEAR through any 1-day reversal. The fix is not "better indicators" but **architecture**: probabilistic state (HMM/BOCPD posterior), explicit **dwell time + asymmetric hysteresis**, and **multi-resolution** (slow daily bias + fast intraday confirm). For Indian intraday equities, a **2-state Gaussian HMM on (Nifty 5d-return, India VIX, breadth) at daily cadence** plus a **5-min Kaufman Efficiency Ratio confirm** with **3-bar dwell + posterior > 0.70** is the sweet spot between latency and stability.

## Detection methods comparison
| Method | Pros | Cons | Suited to TradePilot? |
|---|---|---|---|
| **Threshold / vote-count (v5 current)** | Simple, explainable | No memory, flips daily, weights all indicators equally, no confidence | NO — this is exactly what failed 04-29 |
| **2/3-state Gaussian HMM** | Probabilistic posterior, persistence baked into transition matrix, well-studied | Needs ≥250 days, retrains can change state labels, slow on intraday | YES as **daily layer** |
| **BOCPD (Bayesian Online Change-Point Detection)** | True online, hazard rate λ tunable, no fixed regime count, robust to S&P/HSI in literature | Detects *changes* not labels — needs a labeller on top | YES as **shift-alarm**, not primary |
| **CUSUM / Page-Hinkley** | O(1) memory, ultra-low latency, strong theory | Single-stat, prone to drift, threshold tuning is fragile | NO as primary, OK as **safety alarm** |
| **Kaufman Efficiency Ratio (ER)** | Cheap, intraday-friendly, trend-vs-chop dichotomy | Doesn't distinguish bull-trend from bear-trend | YES as **intraday sub-regime** confirm |
| **ML classifier (XGBoost / RF on labeled regimes)** | Flexible, multi-feature | Needs labeled history (circular — who labels?), look-ahead-bias-prone | Maybe, only after HMM baseline works |
| **Ensemble (HMM + BOCPD + ER)** | Disagreement = low confidence = stay in current regime | More moving parts | YES — recommended end-state |

## Feature engineering recommendations
**Tier 1 (must-have):**
- **Nifty log-returns at multiple horizons** (1d, 5d, 20d) — captures trend
- **India VIX level + 5-day delta** — fear gauge; level alone is too slow
- **Realised volatility** (20-day Parkinson or Garman-Klass on Nifty)
- **Market breadth**: % of Nifty 500 above 50-DMA (NOT just Nifty-50; 50-stock breadth is noisy)
- **Nifty vs 50-DMA % distance** (continuous, not binary above/below)

**Tier 2 (nice-to-have):**
- **FII/DII cash net flow** — but use **same-day NSE provisional**, not lagged 5d aggregate. Lagged FII is exactly why v5 stayed BEAR
- **Sector rotation breadth** (defensive-vs-cyclical leadership swing)
- **PCR / options skew** on Nifty options (NSE FO bhav)
- **USD/INR 5-day change** (FII flow proxy, leads cash-market action)
- **Advance-decline line on NSE total** (not just Nifty-50)
- **Bank-Nifty / Nifty ratio momentum** (financials lead in bull regimes in India)

## Anti-whipsaw techniques
| Technique | What it does | Implementation note |
|---|---|---|
| **Dwell time** | Require N consecutive bars in new regime before switch | Start with 3 bars at 30-min cadence (= 90 min). Critical: store last_regime + bars_in_new_regime in state file |
| **Hysteresis bands** | Asymmetric thresholds: enter BEAR at score ≤ −3, exit BEAR only at score ≥ −1 (not 0) | Prevents oscillation around the boundary. Make exit-from-defensive *easier* than entry — false BEAR is more costly than false BULL after a drawdown |
| **Confidence threshold** | Switch only when posterior P(new_regime) > τ | τ = 0.70 for HMM. If 0.50 < P < 0.70 → label "TRANSITIONING", keep previous regime, halve allocation |
| **Multi-resolution** | Slow daily regime (HMM) + fast intraday sub-regime (gap-up morning / mid-day chop / power-hour) | Daily sets *bias*; intraday sets *aggression*. Daily flips weekly; intraday flips hourly. Don't let intraday override daily direction — only size |
| **Regime "soft hold"** | When confidence < τ, freeze regime + reduce position size 50% rather than flip | Avoids the binary "all-in / all-out" trap |
| **Cooldown after flip** | After any switch, lock regime for K bars regardless of new evidence | K = 6 bars (3 hours) prevents same-day flip-back |

## Indian market specific tips
- **India VIX is regime-asymmetric**: <13 = complacent bull, 13–18 = normal, >18 = stress, >25 = panic. Don't use linear thresholds — VIX *spike* (1d Δ > +15%) is a stronger BEAR signal than absolute level
- **Opening 30 min (09:15–09:45) is unreliable for regime classification** — gap-fill, F&O expiry pin, MTM unwinds. **Wait until 10:00 IST for first regime read**
- **Lunch lull (12:00–13:30)** is mean-reverting; don't trust regime flips during this window
- **Last hour (14:30–15:30)** has highest signal-to-noise; institutional flows confirm/deny morning's tone — weight it 1.5× in any rolling regime score
- **FII net flow is a leading indicator only at weekly cadence**, not daily. Daily FII number is published EOD, so using it intraday is structurally lagged. Use **USD/INR + GIFT-Nifty premium** as FII proxies during the day
- **Settlement weeks (last Thursday)** see artificial volatility — exclude from regime training data or add expiry-week dummy
- **Bank-Nifty leads Nifty in regime transitions** — when BankNifty/Nifty ratio breaks 5-day trend, regime change is often 1–2 days away

## Backtesting pitfalls
- **Look-ahead bias**: v5's `nifty_df.tail(300)` likely includes today's close when called intraday. Always filter `df[df.Date < today]` or use `df[df.timestamp <= as_of_time]`. **Re-run backtest with strict point-in-time slicing**
- **Regime label leakage**: Don't train HMM on the full history then classify *within* that window — the labels are partly a function of future returns (HMM's Viterbi is bidirectional). Use **filtered (causal) state probabilities, not smoothed**
- **Survivorship bias**: If breadth uses current Nifty-50 constituents, you're using the post-2026 winners as the baseline for 2020. Use **point-in-time index membership**
- **Transition matrix instability**: HMM trained on 2020–2024 sees a different transition matrix than one trained through 2026. **Re-fit monthly, walk-forward**, never use one global fit
- **"Optimal" hazard rate / dwell time tuning** is the most overfit knob — fix it on logic (e.g., 3 bars = ~half session) and don't grid-search it on the same data you evaluate on

## Concrete recommendation for TradePilot
**Layer 1 — Daily bias (replace v5 vote system):**
- **2-state Gaussian HMM** on `[Nifty 5d log-return, India VIX level, Nifty-500 % above 50-DMA]`, fit on **rolling 250 trading days, walk-forward refit every Monday**
- Output: `{regime, P(BULL), P(BEAR), P(SIDEWAYS)}` — for 2-state, derive SIDEWAYS when |P(BULL)−P(BEAR)| < 0.20
- **Switch rule**: `new_regime` accepted only if `P(new_regime) > 0.70` AND it has been the argmax for **3 consecutive daily reads**
- **Hysteresis**: exit BEAR at P(BULL) > 0.55 (not 0.70) — easier to leave defensive than to enter it, given India's structural drift up

**Layer 2 — Intraday confirm (every 30 min):**
- **Kaufman Efficiency Ratio** on 5-min Nifty (lookback 20) + **Bank-Nifty/Nifty ratio slope**
- ER > 0.4 + slope > 0 → "trend-aligned with daily bias" → full size
- ER < 0.2 → "chop" → size × 0.5 regardless of daily regime
- **Never flip the daily regime intraday** — only modulate aggression

**Configuration to ship:**
- `dwell_bars = 3` (daily); `intraday_dwell = 2` × 30-min bars
- `confidence_threshold = 0.70` (entry), `0.55` (exit defensive)
- `cooldown_bars_after_switch = 6` (no flip-back for 3 hours)
- `intraday_first_read = 10:00 IST` (skip opening 30 min)
- `weekly_refit = Monday 08:00 IST` on 250-day rolling window, point-in-time only
- **Soft-hold band**: 0.50 < P < 0.70 → label `TRANSITIONING`, hold previous regime, allocation × 0.5

**Why this fixes 04-29:** The HMM posterior on a +0.81% Nifty day with breadth >55% would have been P(BEAR) ≈ 0.40–0.55, not >0.70 — so the regime would NOT have switched away from prior days' read, but **also would not have stayed locked in BEAR with full conviction**. The 175 LONG signals would have run at allocation × 0.5 (TRANSITIONING) instead of being blocked entirely.

## Sources
- [QuantStart — HMM Regime Detection in QSTrader](https://www.quantstart.com/articles/market-regime-detection-using-hidden-markov-models-in-qstrader/) — canonical 2-state Gaussian HMM walk-through
- [QuantConnect — Intraday Application of HMMs](https://www.quantconnect.com/research/17900/intraday-application-of-hidden-markov-models/) — multi-resolution daily-HMM + intraday-ER architecture
- [Volatility Box — Regime Detection from Rules to ML](https://volatilitybox.com/research/volatility-regime-detection/) — detection-lag vs whipsaw tradeoff (0–2d for day traders, 2–5d for swing)
- [LSEG Devportal — Statistical & ML Regime Detection](https://developers.lseg.com/en/article-catalog/article/market-regime-detection) — feature-engineering + ensemble guidance
- [arXiv 0710.3742 — Adams & MacKay, BOCPD original](https://arxiv.org/abs/0710.3742) — hazard-rate parametrisation
- [arXiv 2307.02375 — Online order-flow change-point detection](https://arxiv.org/abs/2307.02375) — BOCPD on real market data
- [Gregory Gundersen — BOCPD blog with code](https://gregorygundersen.com/blog/2019/08/13/bocd/) — clean reference implementation
- [TandF — BOCPD in HK Stock Market 2019–2025](https://dl.acm.org/doi/10.1145/3778450.3778502) — Asian-market empirical validation closer to NSE behaviour
- [Kritzman Regime Detection (GitHub)](https://github.com/tianyu-z/Kritzman-Regime-Detection) — turbulence + absorption-ratio features (alternative to VIX-only)
- [TradingView — Deadband Hysteresis Filter](https://www.tradingview.com/script/TPvNyPwv-Deadband-Hysteresis-Filter-BackQuant/) — practical asymmetric-band implementation pattern
