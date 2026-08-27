# Cost engineering — lowering the toll

**VERDICT: viable (partially).** The intraday toll can be cut from **0.107% → 0.0355%** round trip, a **3.0x reduction**, at *every* position size, by moving to a genuinely zero-brokerage broker. That is the statutory floor and cannot be reduced further. It is still not enough to revive any strategy we have measured.

**THE NUMBER:** cheapest intraday round trip = **0.0355%** (Flattrade, all sizes). Cheapest delivery round trip = **0.2331%** at Rs1L / **0.5765%** at Rs3k (Shoonya, DP fee Rs10.62). Best measured intraday edge 0.030% → net **−0.0055%** per trade. Still negative.

---

## 1. Broker comparison (verified Aug 2026, primary sources where possible)

| Broker | Delivery brok. | Intraday brok. | **DP fee (incl GST)** | AMC | Acct opening |
|---|---|---|---|---|---|
| **Flattrade** | NIL | **NIL** | Rs20 + GST = **23.60** | NIL | Rs200 one-time |
| **Shoonya** (Finvasia) | NIL | 0.03% or Rs5, lower | Rs9 + GST = **10.62** | NIL | NIL |
| **Dhan** | NIL | 0.03% or Rs20, lower | Rs12.50 + GST = **14.75** | NIL | NIL |
| **Zerodha** | NIL | 0.03% or Rs20, lower | **15.34** (3.50 CDSL + 9.50 broker + GST) | Rs300+GST | NIL |
| **Upstox** | NIL | Rs20/order | Rs20 + GST = **23.60** | NIL | NIL |
| **Groww** | NIL | Rs20/order | Rs20 + GST = **23.60** | NIL | NIL |
| **Angel One** | 0.1% or Rs20, min Rs5 | Rs20/order | Rs20 + GST = **23.60** | Rs240+GST | NIL |

Two findings that matter:
- **Flattrade is the only broker with literally zero brokerage on intraday.** Its charges page lists "NIL" for equity delivery, equity intraday, futures and options. This removes both the brokerage *and* the 18% GST that rides on it — GST is levied on (brokerage + txn + SEBI), so killing brokerage kills most of the GST too.
- **Flattrade has the *worst* DP fee (Rs23.60) and Shoonya the best (Rs10.62)** — a 2.2x spread. So the optimal setup is **two accounts**: Flattrade for intraday, Shoonya for delivery. Both have zero AMC, so carrying both costs nothing.
- Dhan and Zerodha both give female first-holders a discount (Dhan 50% off, Zerodha Rs0.25 off CDSL) — relevant only if an account can be opened in a female family member's name.

Statutory components used throughout (Zerodha charges page, verified directly):
NSE equity txn 0.00307% per side · BSE 0.00375% · SEBI Rs10/cr · GST 18% on (brokerage+txn+SEBI) ·
delivery STT 0.1% both sides, stamp 0.015% buy · intraday STT 0.025% sell, stamp 0.003% buy.

## 2. DP fee avoidance — what actually works

| Question | Answer |
|---|---|
| Per what? | **Per ISIN, per day** — not per transaction. Selling one scrip in 20 tranches on the same day = **one** DP charge. This is a real and free saving: scale out freely. |
| NSE vs BSE separately? | No. The debit is from the **demat account**, which sits with one depository (CDSL or NSDL). Exchange is irrelevant. Claims that "CDSL charges for BSE and NSDL for NSE" are wrong — the depository is determined by the DP, not the exchange. |
| Intraday (MIS)? | **No DP charge.** Shares never enter demat. |
| BTST? | **DP charge applies** (Zerodha support confirms). Under T+1 the shares hit demat and are debited next day. BTST gets delivery STT *and* the DP fee — worst of both. Avoid. |
| Practical lever | **Concentrate exits.** N positions exited on one day costs N × DP. Exiting the *same* N positions across N days also costs N × DP. But splitting one position across days costs extra. Rule: never exit a scrip on two different days. |

At Rs3,000 the DP fee is 0.35% (Shoonya) to 0.79% (Flattrade) of the position — it dominates everything else. **Minimum viable delivery position size is ~Rs25,000**, below which the flat fee eats more than a third of a typical monthly edge.

## 3. STT structure — the futures assumption in the brief is STALE

Union Budget 2026 raised derivatives STT effective **1 April 2026**. The brief's "futures 0.0125% sell" is two hikes out of date.

| Instrument | STT | On what | Per unit of *exposure* |
|---|---|---|---|
| Delivery equity | 0.1% both sides = 0.2% RT | turnover | 0.2% |
| Intraday equity | 0.025% sell | turnover | 0.025% |
| **Futures** | **0.05% sell** (was 0.02%, was 0.0125%) | notional | **0.05%** |
| Options (sell) | **0.15%** (was 0.1%) | premium | ~0.006% at ATM |
| Options (exercise) | 0.15% | intrinsic value | punitive on ITM |

**Futures are no longer the cheap route.** After the hike, a Rs15L single-stock futures round trip costs **0.0563%** of notional at Flattrade — *worse* than the 0.0355% intraday equity route, and futures need Rs15L notional per lot (SEBI minimum contract value since Nov 2024). Futures are strictly dominated for us.

**Options are the only structurally cheap instrument per unit of exposure** — because STT falls on premium, not notional. ATM option, premium 2% of notional, delta 0.5: taxes + exchange charges = **0.0094% per unit of delta exposure**, 3.8x cheaper than intraday equity. But that advantage is destroyed by the bid-ask spread: at a 2%-of-premium spread the all-in cost is 0.0894%, worse than intraday equity. Options only win if we can trade inside a ≤0.5%-of-premium spread, i.e. only the most liquid ATM strikes on index/top-10 names, and they carry gamma/theta risk that equity does not.

## 4. Total round-trip cost curves

**INTRADAY (MIS), % of position value:**

| Broker | Rs3,000 | Rs25,000 | Rs1,00,000 |
|---|---:|---:|---:|
| **Flattrade** | **0.0355%** | **0.0355%** | **0.0355%** |
| Shoonya | 0.1063% | 0.0827% | 0.0473% |
| Zerodha / Dhan / Upstox / Groww / Angel | 0.1063% | 0.1063% | 0.0827% |

Note the brief's "flat 0.107% below Rs66,667" is correct *for Zerodha* — the Rs20 cap binds at Rs66,667. Shoonya's Rs5 cap binds at Rs16,667, so Shoonya is size-sensitive in the range we care about. **Flattrade is flat at the statutory floor at all sizes — capital size is irrelevant, confirming the earlier finding by a different route.**

**DELIVERY (CNC), % of position value:**

| Broker | Rs3,000 | Rs25,000 | Rs1,00,000 |
|---|---:|---:|---:|
| **Shoonya** (DP 10.62) | **0.5765%** | **0.2650%** | **0.2331%** |
| Dhan (14.75) | 0.7141% | 0.2815% | 0.2372% |
| Zerodha (15.34) | 0.7338% | 0.2838% | 0.2378% |
| Flattrade / Upstox / Groww (23.60) | 1.0091% | 0.3169% | 0.2461% |
| Angel One (brokerage + 23.60) | 1.4025% | 0.5057% | 0.2933% |

**Cheapest viable route: Flattrade for intraday (0.0355% flat) + Shoonya for delivery (0.2331% at Rs1L).** Both zero AMC, so running both accounts is free.

## 5. What revives, what stays dead

| Strategy | Old toll | New toll | Verdict |
|---|---|---|---|
| Order-book imbalance (edge 0.0049%, t=17.9) | 0.106% (21.6x) | 0.0355% (**7.2x**) | **STAYS DEAD.** Real edge, still an order of magnitude too small. Would need the toll at 0.005% — impossible, STT alone is 0.025%. |
| Best measured intraday rule (edge 0.030%) | −0.077% net | **−0.0055% net** | **STILL DEAD, but only just.** Went from hopeless to marginal. A genuine 0.036%+ edge would now clear. Caution: 0.030% is the *best of 1,104 rules* — it is a selection-biased maximum, not an expectation. |
| 1,104 intraday rules (best t=0.61) | dead | dead | **STAYS DEAD.** No statistical edge exists; cost is not the binding constraint here. |
| Ridge / GBM on price features (holdout inverts) | dead | dead | **STAYS DEAD.** Negative gross. |
| Cross-sectional price-feature ranking | dead | dead | **STAYS DEAD.** Negative gross. |
| **mom_12_1, monthly rebalance, delivery** | ~26% gross/yr | ~1.4–2.8%/yr toll | **COST WAS NEVER THE PROBLEM.** At Rs1L positions and 50–100% monthly turnover, the toll is 1.4–2.8%/yr against 26% gross. It dies on t=0.91–1.82 and −55% DD, not on cost. Do not spend more time cost-optimising it. |

**The load-bearing conclusion:** the toll is the binding constraint *only for intraday*, and we have now taken it as low as Indian law permits (0.0355% — STT 0.025% + stamp 0.003% + exchange 0.0061% + SEBI + GST). There is no further cost lever. **From here, intraday only works if we find an edge above ~0.05% per trade** (0.0355% toll + spread). For anything held overnight, cost was never the binding constraint, so cost work is finished and effort should move to statistical significance.

**Caveat that must not be lost:** every number above is *charges only*. Bid-ask spread and slippage sit on top and are unchanged by broker choice — for NSE mid-caps that is another 0.03–0.10% round trip, which can be larger than the entire statutory toll. Cutting brokerage to zero does not cut the spread. The true intraday floor is closer to **0.07–0.14%**, not 0.0355%.

---

### Actions
1. Open **Flattrade** (Rs200 one-time) — 3x intraday cost cut, immediate, no downside.
2. Open **Shoonya** for delivery — DP fee Rs10.62 vs Zerodha's Rs15.34, saves 31% of the flat fee.
3. Re-charge every intraday backtest at **0.0355% + measured spread**, not 0.107%. Some marginal results will shift; none of the ones above will cross zero.
4. Rule for the delivery engine: **never split a scrip's exit across two days** (doubles the DP fee); splitting *within* a day is free.

### Sources
- [Zerodha charges (primary)](https://zerodha.com/charges/) · [Zerodha — DP charges on BTST](https://support.zerodha.com/category/account-opening/resident-individual/ri-charges/articles/dp-charges-for-btst-trades)
- [Shoonya pricing (primary)](https://shoonya.com/pricing) · [Flattrade charges (primary)](https://flattrade.in/charges/) · [Flattrade — how DP charges are levied](https://flattrade.in/support/knowledge-base/how-dp-charges-are-charged-in-flattrade/)
- [Dhan charges](https://www.chittorgarh.com/brokerage_charges/dhan/176/) · [Upstox charges](https://upstox.com/brokerage-charges/) · [Angel One charges](https://www.angelone.in/exchange-transaction-charges) · [Groww charges](https://comparesharebrokers.com/brokerage-charges/groww)
- [STT rates 2026](https://cleartax.in/s/securities-transaction-tax) · [New STT rates from April 2026](https://www.caclubindia.com/articles/new-rates-of-stt-for-options-futures-trading-starting-from-april-26-54721.asp) · [SEBI Rs15L minimum contract size](https://www.business-standard.com/markets/news/new-f-o-rule-to-come-into-effect-from-thursday-nov-21-here-s-what-changes-124112000292_1.html)
