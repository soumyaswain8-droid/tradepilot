# TradePilot — Detailed EOD Report + Full Watchdog Findings: 2026-06-30

*Everything found today — the full intraday trajectories, every watchdog's complete output, the long/short attribution evolution, exit-reason and trade-quality fields, the cost analysis, and the findings — embedded so nothing is lost.*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot (NSE intraday, paper) |
| **Session** | 2026-06-30 (Tuesday) — a mild-down red day |
| **Tape** | NIFTY 24,032 open → ~−0.5% close; brief −0.73% morning dip, recovered to −0.23%, no afternoon green reversal |
| **Regime tag (engine)** | SIDEWAYS all day |
| **Active roster** | v5 · v5_classic · v5_long · v5_cut (v5_flip applies next launch) |
| **Watchdogs run** | red-day · profit · missed-opps · EOD-profile · engine-compare |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

---

# 1. Result — five-way, net and gross

::: {.metrics-table}

| Engine | Net P&L | Gross P&L | Cost | Trades | WR | L/S |
|:--|--:|--:|--:|--:|--:|:--|
| **v5_long** (long-only) | **−₹872** | — | — | 48 | 52% | L48 / S0 |
| v5_cut | −₹1,470 | — | — | 58 | 50% | L20/S38 |
| v5_classic (frozen) | −₹2,161 | −₹2,161* | (gross-reported) | 58 | 48% | L18/S40 |
| v5 (live) | **−₹2,303** | **−₹1,181** | **−₹1,122** | **77** | 44% | L31/S46 |
| v5_flip | not run (next launch) | — | — | — | — | — |

:::

\* v5_classic reports gross (no cost field); v5 reports both. **Key live finding:** on a *gross* basis v5's picks were the *best* of the day (−₹1,181, better than classic's −₹2,161) — but v5 **over-traded (77 trades)** and **₹1,122 of transaction cost** flipped it to the *worst* net (−₹2,303). The over-trading tax from the root-cause investigation, visible in a single session.

**Cumulative (last 8 sessions, net):** v5_classic **+₹7,959** (leads) · v5_cut +₹6,159 · v5 −₹1,916 · v5_long −₹3,566 · v5_flip ₹0 (pending).

# 2. NIFTY intraday path (30-min, ✅ verified)

::: {.metrics-table}

| IST time | NIFTY | vs open |
|:--|--:|--:|
| 09:00 (open) | 24,032 | — |
| 09:00–09:30 | ~23,897–23,918 | −0.56% to −0.47% |
| ~10:30–11:00 | ~23,977 | **−0.23%** (recovery high) |
| 11:30–13:00 | ~23,933–23,946 | −0.36% to −0.42% |
| 13:30–14:30 | ~23,935 | −0.40% |
| 14:30–15:00 | ~23,905–23,952 | −0.33% to −0.53% |
| Close | ~23,905 | **~−0.5%** |

:::

Mild-down, choppy, never green, never sustained past −0.64%. The brief morning −0.73% touch is what matters for the v5_flip trigger analysis (§9).

# 3. Profit-watchdog — 30-min P&L trajectory (the day's shape)

::: {.metrics-table}

| Time | v5 | v5_classic | Note |
|:--|--:|--:|:--|
| 09:20 | **+₹180** (1t, 100%) | ₹0 | green open |
| 09:50 | −₹1,174 (8t, 25%) | −₹1,879 (7t, 14%) | morning bleed begins |
| 10:20 | −₹1,424 (10t) | −₹2,129 (9t) | |
| 10:50 | −₹2,173 (21t) | −₹2,950 (20t) | |
| 11:50 | −₹2,448 (25t) | −₹3,176 (26t) | |
| 12:20 | **−₹2,776** (27t) | **−₹3,444** (31t) | **midday low** |
| 12:50 | −₹2,659 (31t) | −₹3,313 (33t) | |
| 13:50 | −₹2,647 (50t) | −₹3,348 (34t) | |
| 14:20 | −₹2,650 (53t) | −₹3,046 (36t) | recovery starting |
| 14:50 | −₹2,728 (55t) | −₹3,000 (37t) | |
| **15:20** | **−₹1,181** (77t, 44%) | **−₹2,161** (58t, 48%) | **strong late recovery** |

:::

**The arc:** green open → bled to a **midday low (~−₹2,800 v5 / −₹3,400 classic at 12:20)** → choppy afternoon → **strong final-30-min recovery** (v5 +₹1,547 from 14:50→15:20; classic +₹839). The longs recovered late — the 2nd-half effect, live.

# 4. Red-day watchdog — long/short attribution evolution

The new watchdog (built today) tracked every 5 min. Key snapshots showing how the **shorts decayed** while longs stayed the bleed:

::: {.metrics-table}

| Time | NIFTY | v5 LONG | v5 SHORT | v5_classic SHORT |
|:--|--:|--:|--:|--:|
| 09:50 | −0.73% | −1,671 (17t) | **+497** (10t) | **+497** (10t) |
| 10:15 | −0.61% | −1,671 | +247 (13t) | +247 |
| 10:35 | −0.56% | −1,980 | +47 (13t) | +40 |
| 12:00 | −0.42% | −2,210 (23t) | −238 (20t) | −115 (27t) |
| **15:21 (EOD)** | −0.47% | **−1,097** (37t) | **−84** (46t) | **+424** (40t) |

:::

**Reading:** the shorts were green in the morning (+₹497) and **decayed through the day** to roughly flat/red as NIFTY chopped sideways and recovered. v5_classic's shorts ended green (+₹424) on a more concentrated book; v5's shorts ended slightly red (−₹84). The morning "shorts are green, flip short" signal **faded** — exactly why the morning panic-flip would have backfired.

**EOD long/short split (15:21), all four engines:**

::: {.metrics-table}

| Engine | LONG | SHORT | Net |
|:--|--:|--:|--:|
| v5 | −1,097 (37t) | −84 (46t) | −2,303 |
| v5_classic | **−2,585** (19t) | **+424** (40t) | −2,161 |
| v5_long | **−221** (63t) | 0 | **−872** |
| v5_cut | −910 (27t) | +146 (38t) | −1,470 |

:::

The red-day watchdog also fired its **one-shot Telegram REGIME-MISMATCH alert** at 09:50 (red tape, shorts green, long-heavy).

# 5. EOD-profile watchdog — full trade-quality fields

::: {.metrics-table}

| Field | v5 | v5_classic |
|:--|--:|--:|
| Total P&L (gross) | −₹1,181 | −₹2,161 |
| Trades / Wins / Losses | 77 / 34 / 43 | 58 / 28 / 30 |
| Win rate | 44.2% | 48.3% |
| Longs / Shorts | 31 / 46 | 18 / 40 |
| Best trade | +₹869.2 | +₹869.2 |
| Worst trade | −₹1,029.6 | −₹1,123.2 |
| **Avg win** | **+₹108.82** | +₹92.05 |
| **Avg loss** | **−₹116.20** | **−₹157.97** |
| Open at EOD | 6 | 1 |

:::

**Negative payoff ratio both engines:** avg loss > avg win (v5 −116 vs +109; classic −158 vs +92). At a sub-50% win rate, a negative payoff ratio *guarantees* a red day — the structural reason today was red.

**Exit-reason breakdown:**

::: {.metrics-table}

| Engine | TARGET | STOPLOSS | FLAT_FORCE | TIME_EXIT | SIGNAL_FLIP |
|:--|--:|--:|--:|--:|--:|
| v5 | 2 | 31 | 17 | 14 | 13 |
| v5_classic | 1 | 29 | — | 19 | 9 |

:::

v5 took 77 trades and hit TARGET only **twice** — the same low-target-hit pattern as the whole root-cause window. v5_classic holds more to TIME_EXIT (19) and churns less (no FLAT_FORCE).

# 6. Missed-opportunities watchdog

By close the book was **flat — 0 winners held, 0 losers held, 0 missed gainers >3%, 0 on-table >2%** (the intraday engines force-flatten by EOD). No major opportunity left on the table at the close.

# 7. Findings

## 7.1 Validating — mild-down favours longs; the morning "flip short" call was correctly walked back
Validation 3 (per-trade by severity) said mild-down days favour longs for v5 (+₹123/trade vs +₹11 shorts). Today confirmed it precisely: **v5_long (all-long) was the least-bad engine, its longs only −₹221**, while the short-heavy engines (S38–S46) all lost more net. Shorts were green on a couple of engines but decayed all day and couldn't offset the long damage on the concentrated books. **Flipping short-heavy at 09:48 would have deepened the loss** — the disciplined "hold longs, don't panic-flip" read (Sarathi Rule 2) was correct.

## 7.2 The over-trading tax — live
v5's *gross* P&L (−₹1,181) was the **best** of the day, but its **77 trades** cost **₹1,122** and flipped it to the **worst** net (−₹2,303). The over-trading drag from the root-cause investigation, demonstrated in one session.

## 7.3 The 2nd-half recovery — live
Both engines hit their low at midday (~12:20) and **recovered strongly in the final 30–45 min** (v5 +₹1,547, classic +₹839). The longs that bled in the morning recovered late — consistent with the "2nd-half is where the profit/recovery is" validation, and another reason a morning panic-flip is wrong.

## 7.4 Complicating — a v5_flip trigger flaw caught before launch
The morning briefly hit −0.73% (past the −0.6% hard-down trigger), so v5_flip *would* have flipped to BEAR. But NIFTY recovered to mild-down (−0.5%) and **never went green**, so v5_flip's revert condition (needs NIFTY ≥ +0.15%) would **never fire** — it would sit short-heavy all day on a longs-favoured day. **Fix needed before live:** revert to baseline on "back above −0.6% / above VWAP", not require full green. No backtest caught this — the validations bucketed days by their *close*, hiding the intraday spike-then-recover path. The A/B shadow surfaced it with zero capital at risk.

## 7.5 n=1 confirmed
v5_long was the *worst* engine yesterday (06-29) and the *best* today (06-30) — opposite rankings on consecutive days. Single sessions are noise; judge on the full window.

# 8. Cumulative standings (8 sessions)

::: {.metrics-table}

| Engine | Cumulative net |
|:--|--:|
| v5_classic (frozen) | **+₹7,959** |
| v5_cut | +₹6,159 |
| v5 (live) | −₹1,916 |
| v5_long (RC-1) | −₹3,566 |
| v5_flip | ₹0 (pending) |

:::

The frozen original continues to lead. The live rebuild and the long-only experiment both lag.

# 9. Next steps (no action taken — owner decides)

1. **Patch v5_flip's revert logic** (revert when NIFTY climbs back above −0.6% / above VWAP, not only on full green) before it goes live — today's exact edge case.
2. **Address the over-trading tax** — v5's 77 trades / ₹1,122 cost vs the win it gave up; trade-count reduction is the cheapest lever.
3. **Keep watching the window** — v5_classic's cumulative lead and the now-logging conviction data are the threads that decide the strategy, not one red day.
