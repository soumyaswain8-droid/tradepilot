# Anvitra.ai, the competitive field, and what is actually evidence-backed

**Researched:** 2026-08-02 (building on the 2026-07-22 Agentic Summit findings)

---

## Anvitra — the short version

**There is nothing verifiable to benchmark against.**

- Both `anvitra.ai` and `indexfusion.anvitra.ai` returned **HTTP 403 to automated fetches again
  today**, exactly as on 2026-07-22. Could be a Cloudflare bot-block rather than a dead site —
  **we cannot distinguish the two from here.**
- Corporate facts re-confirmed via Tracxn: incorporated **2026-01-29**, CIN U62099KA2026PTC215048,
  **unfunded**, paid-up capital **₹30,000**, HSR Layout Bengaluru.
- **Zero independent signal**: no Product Hunt listing, no press, no demo video, no third-party
  review, no traction indicator of any kind.
- **Unreconciled discrepancy:** Tracxn describes the business as *"intent based data retrieval
  software for artificial agents"* — an AI-infrastructure pitch, **not** a stock-picking product.
  That does not obviously match IndexFusion's consumer "stop investing on FOMO" positioning. Either
  IndexFusion is a vertical demo on a broader retrieval platform, or the categorisation is stale.

**How to treat them:** a 6-month-old, unfunded, pre-traction company with a blocked site and no
published methodology. Their "engine ingests filings + news + fundamentals + technicals" line is
**marketing copy we have never been able to verify**. Do not repeat it as fact, and do not treat
them as a technical benchmark. They are a positioning data point, nothing more.

## The field that actually matters

| Player | Method | Independently verified? | Price |
|---|---|---|---|
| **Seeking Alpha Quant / Alpha Picks** | "Quantamental" — 100+ metrics: value, growth, profitability, momentum, EPS revisions | **Yes — the only one.** A Univ. of Kentucky paper (Apr 2024) found Quant Ratings "strongly predict" returns; Alpha Picks returns reported **GIPS-verified by S&P Global** | Subscription |
| **Zacks Rank** | Earnings-estimate revisions + agreement + surprise history | Vendor's own 34-yr backtest (claims +13.8%/yr over S&P). Not third-party audited — **but the underlying anomaly (post-earnings-announcement drift) is genuinely well-replicated** | Premium |
| Danelfin | "AI Score" 1–10, ~900 indicators, 3-month horizon | No audit. A "70% win rate" figure traces to review sites restating the vendor | ~$49/mo |
| Kavout | "K Score" ML on technical + fundamental + alt data | No audit found | ~$16–20/mo |
| Tickeron | AI "Robots" emitting buy/sell signals | No audit found | Free + ~$60/yr |
| Composer | **Not** an AI picker — rules-based ETF strategy builder. Honest positioning | N/A | Subscription |
| QuantConnect | Infrastructure, bring your own model | N/A | Free + paid |
| Numerai | Crowdsourced ML tournament, meta-model | Forward-tested and published — stronger than backtests, still self-reported | Free to enter |

**The pattern:** exactly one player in this category has a named academic paper plus a recognised
performance standard behind it. Every "AI Score" product — the shape Anvitra is pitching — rests on
vendor-published win rates. *(And note GIPS verifies that returns were calculated correctly, not
that a strategy will keep working.)*

## What is actually evidence-backed

Replicated across 30+ years and multiple markets — Fama-French (1992/93), Carhart (1997),
Novy-Marx (2013), Frazzini-Pedersen (2014):

- **Quality / profitability** — among the most durable out-of-sample
- **Momentum** — heavily replicated, *but see the regime warning below*
- **Value** — real, though a rough decade-plus
- **Low volatility** — real historically; per J.P. Morgan's Mar-2026 commentary, defensive and
  valuation factors have been **lagging significantly YTD**
- **Size** — weakest and most contested; largely considered decayed

### The finding we should actually act on

**Momentum is regime-conditional, and the effect is getting stronger, not weaker.**

| Period | Avg monthly momentum return after a volatility spike | In calm periods |
|---|---:|---:|
| 1994–2024 | **−0.73%** | **+0.54%** |
| 2014–2024 | **−0.96%** | **+0.65%** |

Momentum also carries the worst tail risk of any factor — documented crashes as deep as **−88%**.

This is directly relevant to us: **a momentum signal that ignores volatility regime is walking into
a known, documented failure mode.** It is also a precise description of what just happened to our
own April engine — brilliant in a calm training window, collapsed when conditions changed.

### What does not work

- Short-horizon ML "prediction" of price direction from mixed technical + fundamental + sentiment
  features is the setup **most prone to overfitting**, because features and labels come from the
  same noisy, non-stationary series. This is exactly what Danelfin, Kavout and (apparently) Anvitra
  pitch — and exactly what our v10 investigation suggests produced April's phantom 77%.
- **"Explainable AI" validates the model, not the edge.** Interpretability is not evidence.
- Any claimed edge that **cannot name its factor exposure** should be assumed to be in-sample
  memorisation until forward-tested live.

## What this means for our US module

1. **Do not build another opaque ML scorer.** We have first-hand evidence of where that leads.
2. **Start with named, testable factors** — quality, momentum, value — so every signal has a
   hypothesis attached and can be attributed after the fact.
3. **Condition momentum on volatility regime from day one.** The literature says the naive version
   has negative expectancy after vol spikes. We already have regime-detection machinery.
4. **Post-earnings-announcement drift is the most defensible mechanical edge available** — and SEC
   EDGAR gives us the filings data free. That is a genuine opportunity the "AI" crowd is largely
   ignoring because it is boring.
5. **Forward-test only.** Our own backtests just proved they can lie. Paper trading with an honest
   audit trail is the differentiator — and it is what TradePilot already does better than any
   product in the table above.

## Where we could genuinely be better than Anvitra

Not on model sophistication — on **honesty infrastructure**. We already have per-trade audit trails,
mistake-class attribution (`SHORTED_RISER`, `WRONG_DIRECTION`, `EXIT_TOO_EARLY`), left-on-the-table
accounting, and a fleet of A/B shadow engines. Nobody in that table publishes an audited daily
"here is what we got wrong and what it cost" report. That, not a proprietary score, is the defensible
position.

## Open

Retry Anvitra with a real browser (Playwright) rather than WebFetch — the 403 may be a bot
fingerprint, not a dead site · founders' LinkedIn *posts* for demo screenshots · effect sizes for
momentum/quality **net of transaction costs** for a US large-cap universe.
