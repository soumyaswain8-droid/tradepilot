# Outage Review, v5_flip Red-Day Verdict & DATA-GUARD — 2026-07-12 (Sunday)

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Status** | Complete |
| **Created** | 2026-07-12 |
| **Updated** | 2026-07-12 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@sidewall.in |

:::

## A. What actually happened last week (corrected timeline)

| Day | Market | Engines | Root cause |
|:--|:--|:--|:--|
| **07-08 Wed** | NIFTY **−2.1% crash** | **BLIND** — DNS dead from 09:00; 12 entries off cached CSVs, zero exits | Router online-but-no-internet; `curl (6) could not resolve query1.finance.yahoo.com` |
| **07-09 Thu** | Index **+0.34%** but breadth-bear (350/618 AVOID, DRREDDY −5.9%) | Ran normally, 106 trades, net −₹2.4k | — |
| **07-10 Fri** | Mild green | **BLIND** again from 09:31; 3 entries, zero exits | Same DNS failure |
| **07-11 Sat** | — | wifi-watchdog still cycling at 09:08; fallback SSID `Pro` (hotspot) not broadcasting | Hotspot physically absent — watchdog config is fine |

**Consequences:**

- The roster **missed the single best short day** (07-08 crash) since the strategy work began — and the 07-08/07-10 audit reports (₹0 / `exit=None` everywhere) are outage artifacts, not trading results.
- 5 SWING positions entered 07-09 (KALYANKJIL ×3 engines, PNB, PAYTM) carried through the blind Friday into Monday — legitimate carries, engines will manage them at Monday open.
- The `Error fetching FII/DII data: name 'logger' is not defined` lines are **nsepython's internal bug** on network failure — cosmetic; if seen, check connectivity first.

## B. v5_flip red-day verdict (roadmap decision point — answered with a caveat)

The roadmap asked: *does fast activation of the 8/12 tilt cut red-day losses without false-triggering on green days?*

**The test remains incomplete** — both true red days (07-08, 07-10) were outage days. What 07-09 (breadth-bear, index-green) did show:

| Engine | Trades | L/S | Net | WR |
|:--|--:|:--|--:|--:|
| v5 | 52 | 23/29 | −₹2,433 | 42.3% |
| **v5_classic** | 51 | 17/34 | **−₹522** | **51.0%** |
| v5_long | 24 | 24/0 | −₹1,048 | 45.8% |
| v5_cut | 44 | 37/7 | −₹3,188 | 27.3% |
| v5_flip | 73 | 44/29 | −₹2,393 | 43.8% |

1. **No false hard-down trigger** — the tape never crossed −0.6%, and none fired. ✅
2. **The un-tilt leg fired correctly but hurt**: at 10:22 tape read +0.48% (≥ +0.15% GREEN threshold ×2 reads) → BEAR→SIDEWAYS → flip took 44 longs vs v5's 23 into a breadth-bear afternoon. The index sensor was *right about the index* and *wrong about the portfolio*.
3. **Sensor mismatch is the real finding**: 07-09's damage (−₹3,783 of LONG_IN_BEAR) happened while ^NSEI was green. An index-level tape cannot see a breadth-bear day. Candidate upgrade for discussion: breadth tape (advancers/decliners or % of universe below VWAP) instead of / alongside ^NSEI %.
4. Flip's extra churn (73 vs 52 trades) cost ~₹580 more in costs with no offsetting edge.
5. **v5_classic beat everything again** (−₹522, 51% WR) — consistent with the June root-cause finding.

**Decision:** keep v5_flip running as shadow; the hard-down leg is still untested on a true index-red day. Do not promote. Consider the breadth-tape sensor before the next iteration.

## C. Changes shipped this session

| Change | File | Why |
|:--|:--|:--|
| **DATA-GUARD** — block new entries when live 1-min NIFTY tape is missing/stale (>15 min); exits untouched; `DATA_GUARD=0` kill-switch | `scripts/v5-paper-trade.py` (`_tape_is_fresh`, `_live_tape_ok`, gate in `deploy_signals`) | 07-08/07-10: engines opened positions off cached data they could never price again. Covers all 5 roster engines (wrappers) |
| Unit tests (TDD, red→green) | `tests/test_data_guard.py` (5 tests; 21/21 suite green) | Pure-function freshness logic testable without network |
| battle-ready-check: Rust binary hard-FAIL → INFO | `scripts/battle-ready-check.sh` | Rust layer optional since 2026-06-05; check had drifted, gave false NOT READY |
| **Market Intelligence feed fix** — Business topic feed replaces worst search feed; `when:1d` on remaining searches; 48h pubDate filter; HTML stripped from summaries | `prototype/app.py`, `prototype/news_utils.py`, `tests/test_news_feed.py` (9 tests) | Google News search RSS re-stamps old articles with fresh pubDates — April "Good Friday" story showed as "4h ago"; raw `<a href>` leaked into UI. Verified live: feed now all-current |

Live verification (Sunday): guard returns **False** (would block — market closed, tape stale ✅); `DATA_GUARD=0` returns True ✅.

## D. Monday-open readiness (2026-07-13)

- **battle-ready-check: 43/43 PASS — BATTLE READY**
- launchd `com.soumya.tradepilot-launch` scheduled weekdays 08:50 ✅; network currently online ✅; nightly backup ran clean today ✅
- Flask dashboard restarted (was down — weekend auto-stop is by design): http://localhost:5050 ✅
- Carried SWING positions from 07-09 will be managed at open

## E. Open items (user decision needed)

1. **Network failover**: the only wifi fallback is the `Pro` hotspot, which wasn't broadcasting during a 2-day router outage. Options: keep hotspot on during market hours; add a second fallback SSID (`WIFI_TARGET_SSID` in `scripts/wifi-watchdog.sh`); or accept the risk — DATA-GUARD now caps the damage (no blind entries).
2. **Breadth-tape sensor for v5_flip** (see §B.3) — design change, needs sign-off.
3. 07-08/07-10 audit reports are artifacts — exclude those dates from any engine-comparison stats.
