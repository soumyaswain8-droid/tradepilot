# US equities — broker & API landscape for an Indian resident

**Researched:** 2026-08-02 · **Question:** which platform can TradePilot drive programmatically?
**Confidence key:** VERIFIED (official source read) · REPORTED (secondary) · UNCERTAIN / CONTRADICTED

---

## The decision, up front

**For paper trading: Alpaca.** Its paper API is free, needs **no funded account and no KYC**, and
anyone globally can sign up with just an email (VERIFIED). That is the only option found with zero
account friction, which makes it the right target for a first integration.

**IBKR is the strongest API but has a real barrier:** paper trading requires a **fully open and
funded live IBKR Pro account first** (VERIFIED). You cannot get a standalone paper account. So IBKR
is the likely *eventual* live-trading home, but it cannot deliver a paper demo quickly.

**Live trading from India is unresolved and must not be assumed.** See the contradictions section.

## Comparison

| Platform | Public trading API | India resident can open? | Paper/sandbox API | Confidence |
|---|---|---|---|---|
| **Alpaca** | Yes — REST + WebSocket, `alpaca-py` | Live: **CONTRADICTED**. Paper: **yes, anyone** | **Yes — free, no funding, no KYC** | VERIFIED (paper) / UNCERTAIN (live) |
| **IBKR** | Yes — TWS API + Client Portal Web API | Yes, dedicated India onboarding | Yes, but **needs funded live account** | VERIFIED |
| **INDmoney (INDstocks)** | **Yes** — REST, ~₹5/order | Yes (India-domestic) | Not confirmed | VERIFIED API exists / scope UNCERTAIN |
| Vested Finance | None found | Yes | — | UNCERTAIN |
| Stockal / Borderless | None found | Yes | — | UNCERTAIN |
| ICICI Direct Global | No retail API (IBKR is backend clearing only) | Yes | — | REPORTED |
| Tradier | Yes, API-first | **CONTRADICTED** — see below | Not confirmed | UNCERTAIN |
| TradeStation Global | API scope for non-US accounts unclear | Yes, with extra fees | Not confirmed | UNCERTAIN |
| Schwab / thinkorswim | **Could not verify** | Unclear — India not confirmed | Not confirmed | COULD NOT VERIFY |
| Groww US | Not researched this pass | — | — | **OPEN** |

## Contradictions and open questions — resolve before committing

1. **Alpaca live eligibility for India.** Alpaca's own copy says "195+ countries" but its worked
   example is *"A UK resident who is an Indian citizen may open a live account while residing in
   the UK"* — implying **tax residency in India may not qualify**, even though citizenship isn't
   the blocker. A secondary source (BrokerChooser) claims India is supported. **Unresolved.**
   Confirm with Alpaca support before treating Alpaca as a live path. Paper is unaffected.
2. **Tradier directly contradicts itself** across sources — a press release describes onboarding
   for 75+ countries, another states account holders must be US citizens or permanent residents.
   Unresolved; moot if India is disqualifying.
3. **INDmoney has a real API**, which overturns the working assumption that India-facing platforms
   have none. Docs at `api-docs.indstocks.com`, and a connector exists in the OpenAlgo project.
   **Unverified whether it covers US-listed tickers or only NSE/BSE** — that single fact decides
   whether it belongs in this table at all.
4. **Schwab's eligibility page returned an authorization error** (geo/bot gated). That is weakly
   suggestive but proves nothing. Treat the whole platform as an open question.
5. **Groww US** was not researched — budget exhausted. There is an unverified recollection that the
   US-investing feature was paused or discontinued; **do not repeat that as fact** until checked.

## What this means for TradePilot

- **Build the paper integration against Alpaca.** Free, instant, global, REST + WebSocket, official
  Python SDK, sandbox host `paper-api.alpaca.markets`. Nothing else clears KYC-free.
- **Keep the broker behind an interface.** Given live eligibility is unresolved for every candidate,
  the execution layer must be swappable — exactly how `data_us.py` hides the data source.
- **Do not design around IBKR yet.** Its API is the best, but funding a live account to get paper
  access is a decision, not a technicality.
- **Nothing here authorises real orders.** See `04-regulatory-lrs-tax.md` — LRS, TCS and the
  day-trading question sit upstream of any broker choice.

## Not verified (carry forward)

IBKR API rate limits · whether INDmoney's API covers US tickers · Tradier eligibility · Schwab
retail API existence · TradeStation Global API scope · Vested/Stockal FX markup and minimums ·
Groww US current status.
