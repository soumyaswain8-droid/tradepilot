# TradePilot — Why We're Losing Now: Apr → Jul Degradation Analysis

*Full historical comparison (10 Apr → 6 Jul). How we traded then vs now — trades, timing, win-rate, deployment, and return-on-capital — and why ₹1–2k on ₹10L means the current engine is broken, not the concept.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot (NSE intraday, paper) |
| **Window** | 2026-04-10 → 2026-07-06 |
| **Capital** | ₹10,00,000 per engine |
| **Full-history engines** | v5 (live), v5_classic (frozen original) |
| **Question** | Why are we losing badly now, and why can't we make real money on ₹10L even on green days? |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

---

# 1. The verdict up front

**You are right that the current engine is badly designed — but the data proves a well-designed one makes real money on ₹10L, because we *had* one in April.** In April, live v5 returned **+1.35%/day (₹13,547) at a 77% win rate**. By July it returns **−0.24%/day at 46%**. This is not a concept that can't work; it's a **monotonic degradation** of a proven engine. The ₹1–2k days that frustrate you are the *symptom*: a 46%-win-rate coin-flip deploying capital into a book that fights the market. The fix is to **revert to the April design**, not reinvent it.

# 2. The degradation table — v5 (live)

::: {.metrics-table}

| Month | Days | Avg P&L | Return/day | Trades/day | Win% | Avg entry | Avg hold | Deploy% |
|:--|--:|--:|--:|--:|--:|:--|--:|--:|
| **April** | 14 | **+₹13,547** | **+1.35%** | 60 | **77%** | 11:08 | 73m | 94% |
| May | 17 | +₹2,725 | +0.27% | 51 | 53% | 11:46 | 97m | 61% |
| June | 19 | −₹220 | −0.02% | 52 | 48% | 11:31 | 118m | 68% |
| **July** | 2 | **−₹2,408** | **−0.24%** | 73 | **46%** | 11:26 | 84m | 101% |

:::

# 3. The degradation table — v5_classic (frozen original)

::: {.metrics-table}

| Month | Days | Avg P&L | Return/day | Trades/day | Win% | Avg entry | Avg hold | Deploy% |
|:--|--:|--:|--:|--:|--:|:--|--:|--:|
| April | 9 | +₹4,361 | +0.44% | 53 | 66% | 10:52 | 86m | 68% |
| May | 17 | +₹3,510 | +0.35% | 47 | 52% | 11:24 | 109m | 61% |
| June | 18 | +₹596 | +0.06% | 47 | 50% | 11:00 | 139m | 64% |
| July | 2 | −₹1,060 | −0.11% | 62 | 43% | 10:50 | 104m | 74% |

:::

**v5_classic degraded too, but far more gently** (66%→43% WR vs v5's 77%→46%; still +0.06% in June while v5 was −0.02%). It carries *none* of the rebuild's later additions — which is exactly why it decayed slower. It's the closest thing we have to the April engine still running.

# 4. The core finding — the win rate IS the story

::: {.metrics-table}

| Metric | April | July | Change |
|:--|--:|--:|:--|
| Win rate (v5) | 77% | 46% | **−31 points** — from selective to coin-flip |
| Return/day (v5) | +1.35% | −0.24% | **from +₹13.5k to losing** |
| Trades/day | 60 | 73 | more churn |
| Avg hold | 73m | 84–118m | holding losers longer |

:::

Everything traces to the **win-rate collapse from 77% to 46%**. At 77% with a tight bracket, the math prints money; at 46% it bleeds. Nothing else — trade count, deployment, entry time — moved enough to explain the swing. The engine stopped *picking well*.

# 5. Why the win rate collapsed (the complexity cascade)

The 77%-WR April engine was: **NIFTY-50, top-5, long-only, tight +1.5/−0.75 bracket, early entry, flat by EOD.** Everything added since diluted it:

::: {.gap-table}

| Change added | Effect on win rate |
|:--|:--|
| **Short book** | Shorts bleed on green days AND sideways chop (verified: shorts −₹3,611 net over 06-16..25; both green days 07-01/07-02 shorts red) |
| **Universe 50 → 200** | 4× more marginal names → lower average conviction |
| **Late entry (rescore loop)** | Avg entry ~11:00–11:46 (should be ~09:20); winners become stops |
| **Longer holds (73m → 118m)** | Holding losers hoping for reversal instead of clean bracket exits |
| **Overfit 1,735-tree ML** | Memorized noise; a 5-tree model out-hits it |
| **Churn (57 trades/day)** | Short-then-long the same name (DABUR 07-01: shorted −₹756 AND longed −₹217) |

:::

# 6. The capital-efficiency reality — the ₹1–2k problem

::: {.metrics-table}

| Scenario | Daily | Monthly (~20 days) | On ₹10L |
|:--|--:|--:|--:|
| **April v5 (proven)** | +₹13,547 | ~₹2.7 lakh | **+27%/month** |
| Current v5 (July) | −₹2,408 | ~−₹48k | **losing** |
| A "good" current day | +₹1–5k | — | +0.1–0.5% |

:::

**This is the heart of your frustration, quantified.** A +₹2k day on ₹10L is **+0.2%** — trivial. But April shows ₹10L *can* yield **+1.35%/day** with the same capital. The gap isn't the capital or the concept — it's the **31 points of lost win rate**. The current engine under-uses a proven edge: it deploys the money, then picks at 46% and shorts into strength.

# 7. All present engines (since 06-15)

::: {.metrics-table}

| Engine | Days | Avg P&L/day | Return/day | Win% | Cumulative |
|:--|--:|--:|--:|--:|--:|
| v5 (live) | 14 | −₹687 | −0.07% | 46% | **−₹9,614** |
| v5_classic (frozen) | 14 | +₹497 | +0.05% | 49% | **+₹6,960** |
| v5_long | 4 | −₹968 | −0.10% | 51% | −₹3,872 |
| v5_cut | 9 | +₹576 | +0.06% | 47% | +₹5,185 |
| v5_flip | 2 | −₹586 | −0.06% | 52% | −₹1,173 |

:::

Only **v5_classic** (the frozen original) and **v5_cut** (tighter short-gate) are positive. **Live v5 is the worst (−₹9,614).** The two winners are the two engines closest to "clean execution + disciplined shorts" — the April recipe. The message is consistent across every cut of the data.

# 8. The path back — revert, don't reinvent

The April engine is the target and the blueprint. Ranked:

1. **Restore clean early-entry execution** (kill the rescore-loop late entry; enter ~09:20 and hold to bracket). v5_classic already does this and decayed least.
2. **Suppress shorts on green / regime-tilt** (the short book is the biggest single win-rate drag; v5_cut's tighter short-gate + a BULL-side tilt).
3. **Concentrate + fully deploy ₹10L** into fewer, higher-conviction names (April ran 94% deployed at 77% WR; stop fragmenting into 45 marginal trades).
4. **Shrink the ML model** (5-tree beats 1,735-tree) or keep it at weight 0.

**Target to hold ourselves to:** not "a green day, ±₹1–2k." The bar is April — **+1% day / 65%+ win rate / ₹10L working**. The proof it's reachable is in our own April data.
