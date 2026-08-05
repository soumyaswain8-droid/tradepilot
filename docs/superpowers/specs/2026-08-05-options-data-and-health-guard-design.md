# Options Data via Kite + Data-Health Guard

*Design spec — replacing the dead NSE options feed and preventing silent data failure*

::: {.report-meta}

| | |
|:--|:--|
| **Project** | TradePilot |
| **Version** | `v1.0.0` |
| **Status** | Draft — awaiting review |
| **Created** | 2026-08-05 |
| **Updated** | 2026-08-05 |

:::

::: {.doc-author}

| | |
|:--|:--|
| **Author** | Soumya Swain |
| **Email** | soumya@suryaai.co.in |

:::

---

## 1. Background

On 2026-08-05 `www.nseindia.com` began returning **403 Access Denied** to this network
(Akamai edge deny, reference `18.aa952317`). Investigating the cause surfaced a larger,
older problem.

### 1.1 What was found

| Finding | Evidence |
|:--|:--|
| The options feed has **never** worked | 22,837 cached option-chain files, **zero** containing real data, earliest 2026-04-08 |
| Failure was silent | `get_options_chain` returns placeholders; `composite_scorer.py:522` wraps the call in `except Exception: pass` |
| The dead feed caused the ban | 457 symbols swept every ~5 min, each preceded by a cookie handshake — roughly 34,000 requests/session |
| Over half the sweep was impossible | **248 of 457** swept symbols have no options contracts in existence |
| The placeholder is **not** neutral | Zero-filled data yields `short_covering` (+0.0866) for any riser, `long_unwinding` (+0.0467) for any faller |

### 1.2 Why the existing guard missed it

`scripts/sarathi/verify.py` runs SARATHI-DAT twice daily with two rules:

- **DAT-001** — NaN rate. The options files contain no NaNs; they are full of clean zeros.
- **DAT-002** — cache TTL. The files are never stale; the broken loop rewrites them every 5 minutes.

> The guard checks whether data is **fresh** and **complete**. It never checks whether it is
> **true**. A file rewritten every five minutes, full of perfect zeros, passes both rules.
> The harder the feed failed, the healthier it looked.

### 1.3 Independent verification

The bug was confirmed against a second, unrelated source (Kite Connect, 2026-08-05 live):

::: {.metrics-table}

| Symbol | Real PCR | Value system used |
|:--|--:|--:|
| HDFCBANK | 0.482 | 1.000 |
| RELIANCE | 0.765 | 1.000 |
| TCS | 0.891 | 1.000 |
| INFY | 0.967 | 1.000 |
| SBIN | 0.973 | 1.000 |

:::

Real values vary per stock across a wide range. The system used a flat 1.000 for every
stock, every day, for four months.

---

## 2. Goals and non-goals

**Goals**

1. Source options data from Kite Connect — an authenticated feed, no bot-blocking.
2. Make silent data fabrication structurally impossible to repeat.
3. Surface data-health state on the existing dashboard and Telegram, without alert fatigue.
4. Change live trading behaviour only behind an A/B switch.

**Non-goals**

- Redesigning the composite scorer beyond the absent-ingredient rule in §3.1.
- Backfilling historical options data (possible via Kite historical OI — deferred to a
  follow-up; see §6).
- Changing engine, risk, or execution alerting, which `api_system_health()` already covers.

---

## Section A — Kite options feed

### A.1 Feasibility (verified, not assumed)

All capability checks were run live against the account on 2026-08-05:

::: {.spec-table}

| Capability | Result |
|:--|:--|
| `instruments('NFO')` | 33,045 contracts returned |
| Option-bearing names | 213 |
| Live OI via `quote()` | `oi`, `oi_day_high`, `oi_day_low` present |
| Daily OI history | `historical_data(..., oi=True)` returns a daily OI series |
| Token | Alive — `Soumyaranjan Swain (TCM486)` |

:::

Everything `compute_oi_buildup` consumes is obtainable. No capability gap.

### A.2 New module: `prototype/v4/kite_options.py`

Sits alongside `kite_data.py` and follows its established conventions — in particular its
rule that missing symbols are **omitted, never zero-filled**, and that every fallback is
recorded and shouted via `note_fallback()`.

### A.3 Universe

Only the **213 names that actually have contracts** are queried. Names with no
derivatives market return `absent` — a first-class state, not a placeholder.

Of the 200 stocks the engines trade (`TRADING_UNIVERSE = "NIFTY_200"`):

- **184** have options → receive real data
- **16** do not (ATGL, COROMANDEL, EXIDEIND, IRCTC, GROWW, HUDCO, LENSKART, …) → `absent`

All 200 remain fully tradable. Options is one ingredient of six; the 16 are scored on the
other five, per §3.1.

### A.4 Fetch strategy

| Concern | Design |
|:--|:--|
| Batching | Nearest expiry only, all names — 13,394 contracts across **27 `quote()` calls** |
| Cadence | One batched refresh on a fixed interval, not 457 per-symbol calls every 5 minutes |
| PCR / OI totals | Sum call and put OI per name from the batch |
| max pain | Computed from the OI distribution across strikes |
| Rate limits | 27 calls per refresh sits far inside Kite's quote limits |

### A.5 OI change

`quote()` exposes current OI but no prior-day value, and per-contract `historical_data`
would need ~13,000 calls — far beyond rate limits.

**Design:** persist one **aggregate** CE/PE OI snapshot per name per day at EOD.
`oi_change = today_aggregate − yesterday_aggregate`. Cost: one extra small file per day,
zero extra API calls.

**Cold start:** until a prior snapshot exists, `oi_change` reports **`absent`**, never 0.
Under §B rules an absent value is visible, so the cold start is observable rather than
silent.

### A.6 Output contract

Returns the schema `compute_oi_buildup` already expects — `pcr`, `max_pain`,
`total_ce_oi`, `total_pe_oi`, `ce_oi_change`, `pe_oi_change` — plus a mandatory
`source` field (§B.1). No consumer changes required beyond §3.1.

### A.7 Retiring the NSE path

The `nsepython` options route is **deleted, not demoted to a fallback.** A fallback to a
blocked endpoint reproduces the original bug: it fails, returns placeholders, and retries
forever. Removing it also ends the traffic that triggered the Akamai deny, allowing it to
age out.

The 22,837 placeholder cache files are deleted as part of this work.

---

## Section B — The data-health guard

### B.1 Provenance (the backbone)

Every data value carries a label:

::: {.metrics-table}

| Label | Meaning | Severity |
|:--|:--|:--|
| `live` | Fetched from the primary source this cycle | — |
| `cache` | Recent cached value, within TTL | info |
| `fallback` | Primary failed; a backup source supplied it | warn |
| `default` | **A value was invented** | critical |
| `absent` | Genuinely unavailable, correctly reported | info |

:::

A single generic monitor then asks one question — *did any ingredient arrive as
`default`?* — instead of guessing what fabricated data looks like. This generalises the
pattern `kite_data.py` already proves with `note_fallback()` / `health()`.

### B.2 Detector rules (the independent cross-check)

Provenance depends on a developer remembering to label a new feed. These two rules do
not, and would each have caught this bug on day one:

**DAT-003 — identical across the universe.**
If one field holds the same value for more than 90% of symbols, flag it. A real market
never produces one PCR for 200 different stocks.

**DAT-004 — impossible value.**
Zero OI on a contract with traded volume; PCR exactly 1.000 universally; all-zero OI
totals on a name known to have contracts.

The two layers fail in opposite directions and cross-cover: B.1 is complete but needs
discipline; B.2 needs no discipline but only catches known shapes.

### B.3 Surfacing

Events are emitted into the existing `api_system_health()` structure
(`{ts, severity, code, source, message}`), which already drives the `/dashboard` status
banner and System Health panel.

::: {.metrics-table}

| Event code | Meaning | Severity |
|:--|:--|:--|
| `DATA_FABRICATED` | A feed returned invented values | critical |
| `DATA_FALLBACK` | Running on a backup source | warn |
| `DATA_STALE` | Real but beyond TTL | warn |
| `DATA_ABSENT` | Genuinely unavailable, correctly reported | info |

:::

### B.4 Notification cadence

- **On state change only** — one Telegram alert when a feed breaks, one when it recovers.
- **Daily morning digest** — a short list of anything still broken, so a long-running
  issue cannot be forgotten.
- **Dashboard** — always current truth, with `broken since <date>` on each item.

This is what prevents alert fatigue: the options bug would have fired every 5 minutes for
four months; under these rules it produces one alert plus one line each morning.

### B.5 Authority

- **Warn always** — dashboard and Telegram, in every case.
- **Block pre-market** — a severe failure found before the open can stop engines starting,
  via the DAT `BLOCK` path that already exists.
- **Never halt mid-session** — stopping engines with open positions creates a worse
  problem than degraded data.

---

## Section C — Rollout

### C.1 Why this needs an A/B

Real options data **will change which stocks the engines pick**. Two effects combine:

1. The phantom momentum tilt is removed — today every rising stock receives a fixed
   **0.04** advantage over every falling stock, derived entirely from fabricated data,
   blind to magnitude (+0.1% scores identically to +3%).
2. Genuine dispersion is introduced — real PCR spans 0.482–0.973 (§1.3) where the system
   previously saw 1.000 everywhere.

A secondary benefit: the current placeholder duplicates signal already captured by
`rs_score` and `orb_score`, so removing it restores their intended relative influence.

**This spec does not claim the change improves returns.** That is an empirical question.
The A/B measures it.

### C.2 Method

Follow the migration discipline `kite_data.py` already documents — *"a migration that
flips eleven live engines at once has no control group, and a bad next session would have
eleven candidate causes."*

- Behind a per-engine switch, mirroring `NSE_DATA_SOURCE=kite`.
- One engine first; the remainder run unchanged as the control.
- Compare selection overlap and outcome before widening.

### C.3 Order of work

1. **Section B guard** — so it is watching before anything changes.
2. **Section A feed** — built behind the switch, not yet live.
3. **C.2 A/B** — one engine, measured against control.
4. **Retire** the NSE path and delete placeholder caches once A/B concludes.

The guard ships first deliberately: it is the component that makes every later step
observable.

---

## 3. Cross-cutting design decisions

### 3.1 Absent ingredients must renormalise

Scoring an absent ingredient as "neutral 0.5" is **not** neutral. It drags stocks toward
the middle of the distribution:

::: {.metrics-table}

| Quality on other 5 | Absent = neutral | Renormalised | Distortion |
|:--|--:|--:|--:|
| 0.9 | 0.8467 | 0.9000 | −0.0533 |
| 0.7 | 0.6733 | 0.7000 | −0.0267 |
| 0.5 | 0.5000 | 0.5000 | 0.0000 |
| 0.3 | 0.3267 | 0.3000 | +0.0267 |
| 0.1 | 0.1533 | 0.1000 | +0.0533 |

:::

A genuinely excellent non-F&O stock could never score as highly as an equally excellent
F&O stock — capped 0.053 lower purely for lacking a derivatives market.

**Rule:** when an ingredient is `absent`, rescale the remaining weights so the stock is
judged only on the ingredients it actually has:
`score = Σ(wᵢ·fᵢ) / Σ(wᵢ present)`.

This applies to any absent ingredient, not only options.

### 3.2 Error handling

- No consumer may silently substitute a value for a failed fetch. Failure returns `absent`
  with provenance attached.
- `except Exception: pass` around a data fetch is prohibited; failures are recorded.
- A feed that fails repeatedly stops retrying (circuit breaker) and reports its state,
  rather than looping — this is what turned a broken feed into an IP ban.

### 3.3 Testing

::: {.spec-table}

| Layer | Test |
|:--|:--|
| `kite_options` | Real PCR for a known symbol is within a plausible band and is **not** exactly 1.000 |
| Universe | A non-F&O symbol returns `absent`, never a zero-filled dict |
| Provenance | Every returned dict carries a `source`; a forced failure yields `absent`, not `default` |
| DAT-003 | Synthetic input with one value repeated across 200 symbols is flagged |
| DAT-004 | Zero OI with non-zero volume is flagged |
| Renormalisation | A stock missing one ingredient scores identically to the same stock with that ingredient removed from the weight set |
| Cold start | Absent `oi_change` on day one produces `DATA_ABSENT`, not a zero |

:::

---

## 4. Open questions

None blocking. Section C.2's comparison window (how many sessions before widening the
A/B) is a judgement call to be made when the A/B starts, not now.

## 5. Success criteria

1. No cached data file anywhere contains an invented value.
2. A deliberately broken feed produces a dashboard flag and one Telegram alert within one
   cycle.
3. Real PCR values reach the scorer and vary per stock.
4. NSE `www` traffic from this machine drops to zero.
5. The A/B produces a measured comparison rather than an assumption.

## 6. Deferred follow-up

**Historical backfill.** `historical_data(..., oi=True)` returns daily OI history, so real
options data can plausibly be reconstructed for contracts still listed — covering much of
the window in which v5 was validated. This would allow backtests to be re-run with the
ingredient that never worked. Scope and expiry-coverage limits to be assessed separately.
