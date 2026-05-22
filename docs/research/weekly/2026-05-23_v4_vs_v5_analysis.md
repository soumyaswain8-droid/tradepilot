# v4 vs v5 Family · Week of 2026-05-18 · Deep Dive

## TL;DR
- **v4 is high-variance long-only**: weekly +₹18,374 / Sharpe 0.74 vs v5 +₹1,498 / 0.24 vs v5c +₹1,604 / 0.16. The "v4 wins" model holds on net, but it survives Thursday only because Mon/Wed/Fri are strong; remove any one of those and v4 trails v5 family.
- **Thursday inversion is a stock-pick divergence, not opposite directions**: v4 took 46 mostly-mid-cap LONGS (ADANIENSOL, ADANIENT, SAIL, 360ONE, FORTIS = ₹3,278 of the ₹3,856 loss). v5/v5c skipped all of those and concentrated in large-cap defensives (PIIND, POWERINDIA, BOSCHLTD, GRASIM) — different baskets, same LONG direction.
- **Sprint 3: ship `sector_relative_strength` first.** v4's Thu losers were all cyclicals (metals/realty/utilities) in a BEAR regime where v5's quality filter routed it to defensives. A sector RS gate would have killed 30+ of v4's 46 Thu trades before entry.

## Thursday Inversion
Regime was BEAR (premarket confirmed). All three engines ran 100% LONG-only on Thursday — there is no direction inversion. The inversion is **selection**:

- **v4** took 46 LONGs across mid-cap cyclicals (Adani complex, SAIL, FORTIS, 360ONE). Win rate 4.3% (2W/12L/32 TIME_EXIT zero-pnl). STOPLOSS exits = ₹-3,927 alone. v4_score average 59.6 — lowest of the week (vs 63.8 Mon when WR was 69%).
- **v5_classic** took 30 LONGs (21 INTRADAY + 9 SWING) heavily tilted to large-cap defensives & quality industrials. Top winners POWERINDIA +1,175, PIIND +1,017, BOSCHLTD +745.
- **v5** took 25 LONGs (fewer trades because WINNER_RE_ARM blocked re-entries on GVT&D/PIIND/GRASIM after wins).
- **Overlap is tiny** — only 7 symbols traded by both v4 & v5c (ADANIENT, ENRIN, GRASIM, LODHA, MANKIND, POWERINDIA, TIINDIA), and where they overlap, sides match. The damage is in the **non-overlap**: v4 took 39 symbols v5c refused to touch.

## Trade-Count Patterns
| Day | v4 (n/W%) | v5 (n/W%) | v5c (n/W%) | Hypothesis support |
|-----|-----------|-----------|------------|--------------------|
| Mon 18 | 68 / 69% | 58 / 34% | 39 / 23% | v5 staleness incident (known) — refutes filter quality this day |
| Tue 19 | 38 / 47% | 36 / 56% | 29 / 59% | Filter helps WR slightly |
| Wed 20 | 76 / 54% | 40 / 48% | 39 / 44% | v5 filters out ~50% of v4 trades |
| Thu 21 | 46 / 4% | 25 / 16% | 30 / 23% | Filter helps on bad days |
| Fri 22 | 53 / 49% | 69 / 46% | 54 / 44% | v5 has more trades — re-arm + new signals |

v4 takes **~1.5× more trades than v5c** on average. Hypothesis confirmed: v5 family gates filter v4's lower-conviction signals — most visible Wed-Thu where v4's count is 1.5-1.9× v5's. The filter is doing what it should.

## "v4 wins" — Verified or Refuted?
**Verified at the portfolio level, refuted at the risk-adjusted level.** v4 banks the week (+₹18.4K), but its daily Sharpe (0.74) is propped up by three high-WR days. Strip Mon's outlier (-₹9,296) and v4 = +₹9,078 over 4 days, still beating v5/v5c. But Thursday alone is a -2.0σ event on v4's daily distribution; v5_classic on the same day is +₹3,228 — a +1.4σ event. The model is "v4 wins on net but bleeds disproportionately on regime-stress days". On any single bad day, you want v5c. Across 5 days, you want v4.

## Re-Arm Contribution
On days where both v5 and v5c finished positive (Tue/Wed/Thu), v5_classic outperformed v5 on 2 of 3 — most dramatically Thursday where **v5c = +₹3,228 vs v5 = +₹1,606 (delta -₹1,622)**. v5's rearmable map on Thu locked out GVT&D, PIIND, GRASIM after first wins — v5c re-entered them and captured the continuation. **WINNER_RE_ARM is currently a drag on positive days**, not a booster. On Fri (both negative), v5c lost more (-₹1,220 vs -₹157) — re-arm protected v5. Net: re-arm reduces variance but caps upside; on a strong-trend day like Thursday it cost ~₹1.6K.

## Feed Degradation Impact
Wed-Fri all three engines share the v4 scorer / quote cache. If feed degradation hit equally, we'd expect proportional WR drops. Observed: Wed v4=54%/v5=48%/v5c=44% (3-6pt spread), Thu v4=4%/v5=16%/v5c=23% (large spread favouring v5c), Fri v4=49%/v5=46%/v5c=44% (3-5pt spread). **v4 was hit hardest only on Thursday**, and the cause is selection (cyclicals), not feed. Slippage records were actually LOWEST on Thursday (55 vs 79/123 Wed/Fri) — fewer fills, not bad fills. Feed degradation is real but not the Thursday driver.

## Sprint 3 Recommendation
**`sector_relative_strength`.** v4's Thursday loss is 100% explained by sector concentration — metals, realty, utilities, infra — in a BEAR regime where v5's signal_engine percentile gate implicitly routed capital to defensive sectors (pharma/cement/FMCG/cap-goods). A sector RS gate that blocks LONGs in the bottom-quartile sector for the day would have prevented ~30 of v4's 46 Thu trades and likely turned -₹3,856 into a flat-to-positive day. OFI/Kyle's lambda are valuable but address microstructure noise, not the regime-vs-basket mismatch that defined this week.
