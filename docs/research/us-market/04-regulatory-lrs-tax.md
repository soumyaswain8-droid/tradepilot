# Regulatory & tax reality — Indian resident trading US equities

**Researched:** 2026-08-02 · **NOT tax or legal advice.** Several points are REPORTED, not
VERIFIED against primary text. Get CA / FEMA-counsel sign-off before any user-facing claim.

---

## The finding that shapes the architecture

**RBI explicitly prohibits, under LRS (VERIFIED — rbi.org.in FAQ):**
1. *"remittance for trading in foreign exchange abroad"*
2. *"remittance from India for margins or margin calls to overseas exchanges/overseas counterparty"*

**Therefore the only clearly-safe lane is long-only, cash-settled, unleveraged US equity.**
The moment the system uses margin, shorts via margin, or touches FX speculation, it crosses from
"gray" into explicitly prohibited. This is a hard design constraint, not a preference.

Note the irony worth flagging: that is the same shape as the April recipe now frozen in v10 —
long-only cash. The India fleet's heavy short book (v5 ran 38 shorts of 56 trades on 07-30) is
**not portable to a US LRS-funded account.**

## The unresolved gray zone — do not paper over it

**Is day-trading US cash equities permitted under LRS?** Genuinely ambiguous.

- The RBI bans above are about **forex** and **margin** — neither is an explicit ban on intraday
  buying and selling of *unleveraged cash equity*.
- In practice Indian residents do day-trade US equities through LRS-funded cash accounts, with no
  publicly reported enforcement action against retail cash-account day trading.
- But **absence of prohibition is not permission.** There is no RBI carve-out blessing it, and RBI
  has at times signalled discomfort with LRS being used for speculative purposes.

**Position to take:** "not explicitly barred for unleveraged cash equity, not explicitly sanctioned
either; margin/leveraged day trading is more clearly prohibited via the margin-remittance ban."
Do **not** ship copy claiming day trading via LRS is RBI-approved.

## The numbers

| Item | Value | Confidence |
|---|---|---|
| LRS cap | **USD 250,000** per person per FY, shared across all purposes | VERIFIED (RBI) |
| Unused limit | Does not carry forward; repatriation does not refill it | REPORTED |
| TCS on investment remittance | **20% above ₹10 lakh**/FY (threshold raised from ₹7L on 2025-04-01) | REPORTED, cross-checked |
| TCS recoverability | Fully creditable against income-tax liability; refundable if excess | REPORTED |
| Holding period for LTCG | **24 months** — foreign shares are treated as *unlisted*, not the 12 months Indian listed equity gets | REPORTED (high confidence) |
| LTCG rate | **12.5% flat, no indexation** | REPORTED |
| STCG | Added to income, taxed at **slab rate** | REPORTED |
| US dividend withholding | **25%** under India-US DTAA with W-8BEN on file (30% without) | REPORTED |
| Foreign Tax Credit | Claim via **Form 67**; deadline rules have been litigated — do not hard-code | REPORTED |
| Schedule FA | Mandatory for any foreign asset, **regardless of value** | REPORTED |
| Black Money Act penalty | **₹10 lakh per assessment year** for non-disclosure — even with zero income | REPORTED |
| Relief threshold | Penalty reportedly waived if aggregate foreign assets (ex-immovable) **under ₹20 lakh**, from 2024-10-01 | REPORTED — verify before relying on |

## US-side: the PDT rule is being eliminated

The FINRA Pattern Day Trader rule — 4+ day trades in 5 business days requiring **$25,000** minimum
equity — **is being scrapped**. SEC approved 2026-04-14; FINRA effective date 2026-06-04; replaced
by a risk-based intraday margin framework. Broker rollout is staggered, with a final compliance
deadline reported as **2027-10-20**, so not every broker has dropped the gate yet. *(REPORTED —
the primary SEC order SR-FINRA-2025-017 returned 403 and could not be read directly.)*

Historically PDT keyed off **margin account status, not residency**. Since our safe lane is cash-only
and unleveraged, PDT was never the binding constraint for us anyway — the **RBI margin ban is.**

## What this means for the build

1. **Long-only, cash, no margin, no FX.** Enforce it in code, not documentation.
2. **Do not port the India short logic.** The US engine is structurally different for regulatory
   reasons, independent of whether shorting is profitable.
3. **Track LRS headroom and warn, don't assume.** The system cannot see the user's other LRS usage
   (travel, education), so it must warn rather than compute remaining headroom as fact.
4. **Model 24-month LTCG**, not 12 — a P&L view copied from the India side would be wrong.
5. **Surface Schedule FA and Form 67 as annual obligations**, with the ₹10 lakh penalty visible.
6. **Paper trading is entirely outside all of this.** No remittance, no LRS, no TCS, no disclosure.
   Which is a further argument for staying on paper until the gray zone is resolved with a CA.

## Must verify before any real-money step

Full RBI Master Direction on LRS (not just the FAQ) for the exact portfolio-investment clause and
any language on trading frequency · bare Finance Act text for the current TCS table · India-US DTAA
Article 10 · the SEC PDT order · **any RBI statement treating "day trading" as distinct from
"investment" under LRS** — that last one is the biggest open question in this entire document.
