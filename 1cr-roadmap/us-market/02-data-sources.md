# US market data sources

**Researched:** 2026-08-02 · Pricing shifts constantly — every figure carries the date it was seen.

---

## Recommendation

| Source | Cost (Aug 2026) | History | Free rate limit | Use for | Confidence |
|---|---|---|---|---|---|
| **SEC EDGAR** (`data.sec.gov`) | **Free, no key** | Full filing history | **10 req/sec** | Fundamentals, filings — zero ToS risk | VERIFIED |
| **Tiingo** | Free tier; **$30/mo** indiv | **30+ years** (paid) | 50/hr, 1,000/day, 500 symbols/mo | **Corporate actions** — documented `splitFactor` | VERIFIED (pricing page) |
| **Finnhub** | Free + paid | Multi-year | **60 calls/min** — most generous free tier | High-volume prototyping | REPORTED |
| **Alpaca market data** | Free w/ account | 6+ years | 200 req/min | Pairs with the paper-trading API | REPORTED |
| **yfinance** | Free, unofficial | Decades | Undocumented | **v1 prototyping only** | REPORTED |
| Polygon.io → **"Massive"** | Free tier; paid from **$199/mo** | EOD on free | 5 calls/min | Production, once paid | REPORTED |
| Alpha Vantage | Free + paid | Full daily | **25/day, 5/min**(?) | Light use only | UNCERTAIN — conflicts with older 500/day |
| Nasdaq Data Link | **Unverified** | WIKI dataset **discontinued** | 50k/day authenticated | Macro, not equity OHLC anymore | PARTIALLY VERIFIED |
| ~~IEX Cloud~~ | — | — | — | **DEAD — do not use** | VERIFIED |

## Things that would have bitten us

**IEX Cloud is shut down.** Retired 2024-05-31, off 2024-08-31 — under 2% of IEX Group revenue and
loss-making since inception. Any doc or vendor comparison still listing it is stale. *(VERIFIED)*

**Polygon.io is now "Massive"** (rebranded 2025-10-30); `polygon.io/pricing` redirects to
`massive.com/pricing`. Bookmarked docs, base URLs and auth flows all need re-validation before use.

**Nasdaq's free WIKI US-equity dataset is discontinued.** You asked specifically to check Nasdaq —
the answer is that Nasdaq Data Link is no longer a primary source for US equity OHLC; current US
equities sit behind the paid XNAS database. Exact pricing **could not be verified** — a direct fetch
404'd (page moved) and a second timed out. **Do not quote a Nasdaq price until re-checked.**

**yfinance changed its adjustment semantics.** With `auto_adjust=True` (now default in some
versions) the `Close` column *is* the adjusted close — code written against the old separate
`Adj Close` silently produces wrong numbers *(VERIFIED — yfinance GitHub issue #1749)*.

> Our `prototype/us/data_us.py` already passes **`auto_adjust=False`**, which keeps raw closes and a
> separate Adj Close. That was the right call and this is the citation for why it must stay.

## Corporate actions — our known weak spot

The India stack has an unresolved corp-action adjustment problem (`eod-comparison-daily.py` still
carries a hardcoded `KNOWN_CORP_ACTIONS` stopgap list). Do not inherit it.

**Tiingo is the strongest candidate**: adjusted close accounts for both splits and dividends, with a
*documented* `splitFactor` keyed to ex-date — a verifiable mechanism rather than a marketing claim.
One reported comparison had Tiingo handling a spin-off correctly where IEX Cloud did not *(single
aggregated source — REPORTED, not independently confirmed)*.

**Proposed empirical test before trusting any of it:** pull 2–3 known recent US splits from Tiingo,
yfinance and Finnhub, diff the outputs. That converts a vendor claim into evidence, and directly
targets the failure mode we already have on the India side.

## Universe construction

- `github.com/datasets/s-and-p-500-companies` — **Public Domain Dedication**, legally clean for
  constituent lists *(VERIFIED licence)*
- **iShares ETF holdings CSVs** (IVV = S&P 500, QQQ = Nasdaq-100) — free, index-provider-sanctioned,
  cleaner footing than scraping Wikipedia. **Not fetched this pass — recommended next step.**
- Wikipedia's S&P 500 page is widely used but is a scrape; fine for research, gray for redistribution
- **Survivorship bias:** today's constituent list is not point-in-time membership. Backtesting on
  current members overstates returns. Same trap the India backtests face.

## Decision for v1

**yfinance now, migrate deliberately.** It is already a dependency, verified to return 3y × 753
trading days with zero NaNs for US large caps, and costs nothing. It is also unofficial and
undocumented — so `data_us.py` hides it behind `get_history()`/`get_quotes()` and the migration to
Tiingo (corp actions) + SEC EDGAR (fundamentals) is a swap of one module, not a rewrite.

**Do not use yfinance for real-money execution decisions** without licensing a proper feed.

## Not verified

Nasdaq Data Link current pricing · Alpha Vantage's real free-tier limit · whether the Polygon→Massive
rebrand changed auth/base URLs · Tiingo free-tier history depth · iShares CSV licence terms.
