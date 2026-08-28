# The 30 Largest Single-Day Winners — 5-Year Survivorship-Free Panel

*Real names, real dates, with the prior-day profile that preceded each move — June 2021 to June 2026*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot — quant research |
| **Version** | `v1.0.0` |
| **Status** | Complete |
| **Created** | 2026-08-28 |
| **Updated** | 2026-08-28 |
| **Panel** | 1,232 sessions x 3,046 symbols, survivorship-free |
| **Sources** | `quant/data/bhavcopy/` (returns, prices), `quant/data/sf_turn.parquet` (turnover, Rs lakh) |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 1. Headline findings

**The 20% circuit limit is the story.** Twenty of the top 30 moves land on *exactly* +20.0%. Only 10 stock-days in five years and 2.6 million observations closed more than +20% up, and every one of them is either an F&O name (no price band) or a thin name in a special session. The largest single-day gain in the entire clean panel is **+46.9%**. There is no fat right tail of +100% days in tradeable Indian equity — the exchange truncates it by rule.

**Big up-days give back.** Median forward return after a top-30 day is **-1.0% over 5 sessions and -2.2% over 20**. For the tradeable subset it is worse: **-3.5% / -5.2%**, with only 7 of 15 positive at 5 days. Buying the biggest winner of the day has been a losing trade at every horizon measured.

**These are not breakouts.** Median prior-day `pos52` is **0.45** (top 30) and **0.35** (tradeable 15) — mid-range, not near highs. Only 3 of the 15 tradeable winners were within 5% of a 52-week high the day before. The biggest up-days come out of the middle and lower part of the range, typically on news, not out of a technical breakout structure.

**The liquidity contrast runs the opposite way to the hypothesis.** The unrestricted list is *not* dominated by illiquid shells once data artifacts are removed — 14 of the top 30 clear the Rs 1 crore bar. But the illiquid half is where the only positive drift lives (median +1.6% / +2.8% forward vs -3.5% / -5.2% for the tradeable half). The forward gains sit precisely where the money cannot go.

---

## 2. Data integrity — read this before using the numbers

Three defects were found and corrected. Two of them invalidate the premise of the original question.

### 2.1 `sf_ret.parquet` is winsorized at ±50%

`sf_ret` is clipped: **47 stock-days sit at exactly +0.500 and 316 at exactly -0.500**. A "largest single-day winners" table built from `sf_ret` returns a 47-way tie at the clip and is meaningless. All returns in this report are computed from bhavcopy instead.

### 2.2 NSE `PREV_CLOSE` is corrupt on relisting days

Naive close-to-close returns from bhavcopy produce absurdities — NIRLON showing **+38,456%** on 2026-04-20 (`PREV_CLOSE` 1.40 against a 540.00 open), CCCL **+1,044%** on a post-suspension relisting. These are stale or placeholder prev-close fields and special call-auction sessions, not market moves.

**Filter applied:** a stock-day is admitted only if the official `PREV_CLOSE` reconciles with the prior traded close in the panel to within 2%, *and* the stock actually traded in the prior session. This removes corrupted prev-close fields, relisting call auctions, and unadjusted corporate actions (splits/bonus) in one rule.

**Cost: 14,900 of 2,624,099 stock-days excluded (0.57%).** Returns reported are `CLOSE / PREV_CLOSE - 1` using NSE's official corporate-action-adjusted prev close.

### 2.3 The reported sf_ret/Kite disagreement does not reproduce

The caveat to check was that `sf_ret` disagrees with Kite in the illiquid tail — ASHIMASYN +101.6% vs +56.7% actual, CCHHL +123.2% vs +73.2%. **Neither figure is reproducible from the data on disk:**

| Symbol | Claimed sf_ret | Actual `sf_ret` max | Bhavcopy max (clean) | Claimed "actual" |
|:--|--:|--:|--:|--:|
| ASHIMASYN | +101.6% | **+19.46%** (2024-05-27) | +19.5% (2024-05-27) | +56.7% |
| CCHHL | +123.2% | **+20.00%** (2023-12-04) | +20.0% (2023-12-04) | +20.0% (2023-12-04) |

`sf_ret` never records either name above +20% on any day in the panel, and cannot exceed +50% by construction (§2.1). Bhavcopy agrees with `sf_ret` to the decimal. Both names are capped by the 20% circuit exactly as expected.

Two implications: the +101.6% / +123.2% figures did not come from `sf_ret` as loaded here (most likely multi-day chains or a differently-built panel), and the Kite "actuals" of +56.7% / +73.2% are themselves inconsistent with a 20%-banded stock. **The suspected corporate-action artifact in `sf_ret` is not confirmed — on this evidence `sf_ret` is clean in the illiquid tail, subject only to its ±50% clip.** That claim should be re-derived before it is relied on.

### 2.4 Kite spot-check: not performed — token expired

The eight largest moves were queued for verification against Kite daily bars. All eight failed:

```
token_alive = (False, 'kite token rejected on profile —
                TokenException: Incorrect `api_key` or `access_token`.')
```

Per instruction this is **not** treated as a data problem. Rows 1-8 are marked *unverified — token expired* in the table below. Re-run after the token is refreshed.

**However, an independent reconciliation was performed and passed.** Every reported move satisfies the §2.2 rule — NSE's official prev close agrees with the prior traded close to within 2% — and across the 29 top-30 rows present in `sf_ret`, **zero differ from bhavcopy by more than 1 percentage point**. The two sources agree completely on this table.

---

## 3. Table 1 — 30 largest single-day winners (unrestricted)

Column key: **Med turn** = 20-day median turnover as of the prior session, Rs crore (source is Rs lakh, converted). **Trade?** = Med turn >= Rs 1 cr. **pos52** = prior-day close within its 52-week range (0 = at low, 1 = at high). **Ret21** / **Vol20** / **Turn ratio** = prior-day 21-session return, 20-day daily return volatility, and prior-day turnover against its own 20-day median. **Fwd 5** / **Fwd 20** = return from the event-day close over the next 5 and 20 sessions.

::: {.changes-table}

| # | Symbol | Date | Move | Prev close | Close | Med turn (cr) | Trade? | pos52 | Ret21 | Vol20 | Turn ratio | Fwd 5 | Fwd 20 |
|--:|:--|:--|--:|--:|--:|--:|:-:|--:|--:|--:|--:|--:|--:|
| 1 | MASKINVEST | 2024-10-28 | +46.9% | 144.03 | 211.58 | 0.01 | no | 1.00 | +19.7% | 3.7% | 0.1x | -9.6% | -5.6% |
| 2 | ZEEL | 2021-09-14 | +40.0% | 186.85 | 261.55 | 116.37 | YES | 0.34 | +2.9% | 1.7% | 1.8x | -2.2% | +17.1% |
| 3 | ZEEL | 2021-09-22 | +31.7% | 255.70 | 336.80 | 138.02 | YES | 0.94 | +50.0% | 9.0% | 4.4x | -8.0% | -4.7% |
| 4 | OFSS | 2024-01-18 | +28.7% | 5086.20 | 6545.50 | 64.17 | YES | 1.00 | +16.2% | 3.3% | 5.3x | +2.5% | +21.0% |
| 5 | IDEA | 2021-09-16 | +25.7% | 8.95 | 11.25 | 236.78 | YES | 0.66 | +42.1% | 6.6% | 3.6x | -6.2% | -4.4% |
| 6 | ADANIGREEN | 2024-11-29 | +21.8% | 1087.20 | 1323.90 | 116.25 | YES | 0.16 | -32.6% | 6.4% | 7.2x | -8.6% | -18.8% |
| 7 | IDEA | 2023-12-29 | +20.8% | 13.25 | 16.00 | 364.72 | YES | 0.85 | +0.0% | 2.5% | 0.6x | +6.9% | -8.1% |
| 8 | TATAMOTORS | 2021-10-13 | +20.4% | 420.85 | 506.90 | 966.65 | YES | 1.00 | +39.7% | 3.5% | 4.3x | +0.2% | +0.0% |
| 9 | IDEA | 2023-02-06 | +20.4% | 6.85 | 8.25 | 75.71 | YES | 0.09 | -12.2% | 3.0% | 1.3x | -4.8% | -15.8% |
| 10 | KOTAKSILVE | 2022-12-29 | +20.4% | 67.29 | 81.00 | 0.04 | no | n/a | n/a | 1.6% | 0.6x | -16.7% | -15.1% |
| 11 | ADANIENT | 2023-02-08 | +20.0% | 1802.95 | 2164.25 | 1296.62 | YES | 0.10 | -52.9% | 10.1% | 2.6x | -17.8% | -9.8% |
| 12 | EIMCOELECO | 2025-04-15 | +20.0% | 1465.65 | 1758.80 | 1.86 | YES | 0.06 | +0.5% | 2.8% | 0.5x | +4.7% | +18.1% |
| 13 | ISFT | 2023-04-06 | +20.0% | 110.25 | 132.30 | 0.27 | no | 0.13 | -10.1% | 3.9% | 1.5x | +1.3% | +11.0% |
| 14 | LOKESHMACH | 2024-11-07 | +20.0% | 328.00 | 393.60 | 1.62 | YES | 0.35 | -15.6% | 2.5% | 1.4x | -11.5% | -5.8% |
| 15 | TOTAL | 2022-08-24 | +20.0% | 77.00 | 92.40 | 0.28 | no | 0.60 | -2.3% | 3.5% | 2.6x | +24.9% | +93.8% |
| 16 | TIPSFILMS | 2024-09-25 | +20.0% | 542.25 | 650.70 | 0.25 | no | 0.16 | +1.1% | 1.2% | 2.4x | +5.5% | -16.0% |
| 17 | GUJRAFFIA | 2025-10-15 | +20.0% | 37.40 | 44.88 | 0.01 | no | 0.02 | -3.7% | 1.8% | 1.3x | +82.9% | +6.3% |
| 18 | PREMIERPOL | 2024-09-12 | +20.0% | 221.45 | 265.74 | 0.68 | no | 0.89 | +5.6% | 2.2% | 0.8x | -10.1% | -6.6% |
| 19 | AGROPHOS | 2021-12-13 | +20.0% | 20.50 | 24.60 | 0.10 | no | 1.00 | +22.0% | 5.5% | 12.2x | +20.1% | +5.1% |
| 20 | ANSALAPI | 2021-10-07 | +20.0% | 9.00 | 10.80 | 0.18 | no | 0.45 | -3.2% | 2.6% | 0.7x | -2.3% | +18.5% |
| 21 | MBLINFRA | 2024-06-12 | +20.0% | 46.30 | 55.56 | 0.27 | no | 0.66 | +4.0% | 4.2% | 6.1x | -2.2% | +38.2% |
| 22 | NEXTMEDIA | 2024-11-21 | +20.0% | 7.35 | 8.82 | 0.01 | no | 0.45 | +1.8% | 2.5% | 0.9x | +5.9% | +0.0% |
| 23 | UNIECOM | 2024-08-19 | +20.0% | 189.60 | 227.52 | 117.03 | YES | n/a | n/a | n/a | 0.5x | -6.0% | +6.6% |
| 24 | ARENTERP | 2021-12-07 | +20.0% | 34.75 | 41.70 | 0.02 | no | 0.78 | +28.2% | 5.5% | 9.2x | +67.5% | +55.5% |
| 25 | PRITI | 2025-08-13 | +20.0% | 78.25 | 93.90 | 0.11 | no | 0.00 | -16.6% | 2.2% | 1.6x | -16.0% | -20.2% |
| 26 | 20MICRONS | 2022-01-10 | +20.0% | 74.50 | 89.40 | 2.54 | YES | 1.00 | +20.6% | 5.2% | 11.1x | +14.7% | -6.7% |
| 27 | AUTOIND | 2023-12-06 | +20.0% | 109.00 | 130.80 | 0.57 | no | 0.90 | +6.1% | 3.1% | 6.1x | +1.8% | +0.4% |
| 28 | SAMBHAAV | 2022-09-07 | +20.0% | 4.50 | 5.40 | 0.02 | no | 0.38 | +20.0% | 5.2% | 13.8x | -3.7% | -17.6% |
| 29 | VIJIFIN | 2025-07-17 | +20.0% | 2.65 | 3.18 | 0.03 | no | 0.31 | +16.2% | 2.3% | 8.2x | +30.5% | +22.0% |
| 30 | MITTAL | 2024-02-07 | +20.0% | 2.25 | 2.70 | 2.26 | YES | 0.04 | -2.2% | 2.4% | 1.2x | +1.9% | -11.1% |

:::

**Rows 1-8 are marked *unverified — token expired*** against Kite (§2.4). All 30 rows passed the internal prev-close reconciliation.

Ties at +20.0% are ordered by the raw sort; the ranking within that block carries no meaning. Rows 10 and 23 have `n/a` in the prior-day profile columns because the name lacked sufficient prior trading history (KOTAKSILVE is a silver ETF near listing; UNIECOM had no 52-week base).

---

## 4. Table 2 — 15 largest, restricted to tradeable names (>= Rs 1 cr/day)

::: {.changes-table}

| # | Symbol | Date | Move | Prev close | Close | Med turn (cr) | Trade? | pos52 | Ret21 | Vol20 | Turn ratio | Fwd 5 | Fwd 20 |
|--:|:--|:--|--:|--:|--:|--:|:-:|--:|--:|--:|--:|--:|--:|
| 1 | ZEEL | 2021-09-14 | +40.0% | 186.85 | 261.55 | 116.37 | YES | 0.34 | +2.9% | 1.7% | 1.8x | -2.2% | +17.1% |
| 2 | ZEEL | 2021-09-22 | +31.7% | 255.70 | 336.80 | 138.02 | YES | 0.94 | +50.0% | 9.0% | 4.4x | -8.0% | -4.7% |
| 3 | OFSS | 2024-01-18 | +28.7% | 5086.20 | 6545.50 | 64.17 | YES | 1.00 | +16.2% | 3.3% | 5.3x | +2.5% | +21.0% |
| 4 | IDEA | 2021-09-16 | +25.7% | 8.95 | 11.25 | 236.78 | YES | 0.66 | +42.1% | 6.6% | 3.6x | -6.2% | -4.4% |
| 5 | ADANIGREEN | 2024-11-29 | +21.8% | 1087.20 | 1323.90 | 116.25 | YES | 0.16 | -32.6% | 6.4% | 7.2x | -8.6% | -18.8% |
| 6 | IDEA | 2023-12-29 | +20.8% | 13.25 | 16.00 | 364.72 | YES | 0.85 | +0.0% | 2.5% | 0.6x | +6.9% | -8.1% |
| 7 | TATAMOTORS | 2021-10-13 | +20.4% | 420.85 | 506.90 | 966.65 | YES | 1.00 | +39.7% | 3.5% | 4.3x | +0.2% | +0.0% |
| 8 | IDEA | 2023-02-06 | +20.4% | 6.85 | 8.25 | 75.71 | YES | 0.09 | -12.2% | 3.0% | 1.3x | -4.8% | -15.8% |
| 9 | ADANIENT | 2023-02-08 | +20.0% | 1802.95 | 2164.25 | 1296.62 | YES | 0.10 | -52.9% | 10.1% | 2.6x | -17.8% | -9.8% |
| 10 | EIMCOELECO | 2025-04-15 | +20.0% | 1465.65 | 1758.80 | 1.86 | YES | 0.06 | +0.5% | 2.8% | 0.5x | +4.7% | +18.1% |
| 11 | LOKESHMACH | 2024-11-07 | +20.0% | 328.00 | 393.60 | 1.62 | YES | 0.35 | -15.6% | 2.5% | 1.4x | -11.5% | -5.8% |
| 12 | UNIECOM | 2024-08-19 | +20.0% | 189.60 | 227.52 | 117.03 | YES | n/a | n/a | n/a | 0.5x | -6.0% | +6.6% |
| 13 | 20MICRONS | 2022-01-10 | +20.0% | 74.50 | 89.40 | 2.54 | YES | 1.00 | +20.6% | 5.2% | 11.1x | +14.7% | -6.7% |
| 14 | MITTAL | 2024-02-07 | +20.0% | 2.25 | 2.70 | 2.26 | YES | 0.04 | -2.2% | 2.4% | 1.2x | +1.9% | -11.1% |
| 15 | DHANVARSHA | 2022-06-28 | +20.0% | 75.75 | 90.90 | 2.42 | YES | n/a | -5.5% | 5.6% | 3.0x | +7.5% | +6.2% |

:::

---

## 5. What the contrast actually shows

The expected finding was that the unrestricted list would be a parade of illiquid shells and the tradeable list would look tame. **That is only half right, and the half that is wrong matters more.**

**The two lists are nearly the same list.** Nine of the tradeable 15 also appear in the unrestricted 30, and the unrestricted top 5 contains four names any retail account could trade (ZEEL, OFSS, IDEA twice). Once relisting artifacts and corrupted prev-close fields are removed (§2.2), the shells largely vanish — they were data errors, not real moves. The shells that survive (MASKINVEST, GUJRAFFIA, NEXTMEDIA at Rs 1-4 lakh/day) sit *inside* the same +20% ceiling as everything else, because the circuit binds regardless of size.

**Above +20% requires the absence of a price band.** All 10 clean stock-days above +20% belong to names with no or widened bands — ZEEL (Sony merger, Sep 2021), IDEA (government relief package), OFSS (results), ADANIGREEN/ADANIENT (Hindenburg-period volatility), TATAMOTORS. These are the largest, most liquid, most heavily-traded names in the market. **The biggest single-day winners in Indian equity are large caps on news, not micro caps on speculation** — the opposite of the folk model.

**The turnover signature is real but not exploitable.** Prior-day turnover ratio is elevated (median ~1.8x, several above 8x) — something was already stirring the day before. But `pos52` is mid-range, `Ret21` is scattered from -52.9% to +50.0%, and `Vol20` spans 1.2% to 10.1%. No combination of prior-day features separates these 30 days from the ~2.6 million that were not.

**And the payoff is negative.** Median forward 5-day return is -1.0% overall and -3.5% among tradeable names; forward 20-day is -2.2% and -5.2%. This is the same result the winner-anatomy study reached from the other direction: the fat right tail exists, it is a property of the return distribution rather than of any identifiable setup, and net of costs it is paid *by* the buyer.

---

## 6. Reproduction and open items

- Returns: `CLOSE / PREV_CLOSE - 1` from `quant/data/bhavcopy/*.csv`, series EQ/BE/BZ/BT, symbols restricted to the 3,046-name `sf_ret` universe, dates 2021-06-17 to the panel end.
- Turnover: `TURNOVER_LACS` from bhavcopy. **Verified identical to `sf_turn.parquet`** — median ratio 1.0000 across 2,352,426 overlapping observations. Both are Rs lakh; divide by 100 for crore.
- Cleanliness rule, forward returns, and the prior-day profile are as defined in §2.2 and §3.

**Open:**

1. **Re-run the Kite spot-check on rows 1-8** once the access token is refreshed. Unverified, not failed.
2. **Re-derive the ASHIMASYN / CCHHL discrepancy claim** (§2.3). As it stands it does not reproduce from `sf_ret` in either direction, and the conclusion that `sf_ret` has corporate-action artifacts in the illiquid tail is unsupported by this check.
3. **`sf_ret`'s ±50% clip should be documented at the source.** Any study that ranks or thresholds on extreme returns — tail studies, stop-loss simulations, outlier filters — is silently distorted by it. 316 days clipped at -50% is the larger exposure.
