# RED TEAM — adversarial review of all agent findings

Reviewed 8 lanes. **6 self-reported negative and I confirm them.** Two carried positive
claims. I re-derived both from raw data with my own code. One survives partially with a
fatal caveat; one **fails to replicate and contradicts another agent on the same dataset.**

Scripts: `scratchpad/rt_opt.py`, `scratchpad/rt_mom.py`.

---

## KILL 1 — mom_12_1 t=2.46 does not replicate. Two agents contradict each other.

`regime-filter.md` reports, as a by-product: mom_12_1 top-decile long-only, market-demeaned,
**net of costs: +0.76%/mo, t=2.46 (Rs10L), +0.85%/mo t=2.74 (Rs1cr), n=47.**
`momentum-validation.md`, same `sf_ret.parquet`, same 47 months, reports **alpha +0.6pp/yr,
t=0.05** and calls it dead. Both cannot be right.

I rebuilt it independently (own eligibility, own signal, own demeaning). Top-10% decile,
excess over equal-weight eligible universe, **GROSS, no costs charged at all**:

| N held | excess %/mo | t | ann % | H1 t | H2 t |
|---|---|---|---|---|---|
| 5 | −0.590 | −0.47 | −6.85 | 0.13 | −0.84 |
| 10 | −0.029 | −0.03 | −0.34 | 0.27 | −0.29 |
| 20 | +0.472 | 0.70 | +5.81 | 0.78 | 0.25 |
| 50 | +0.882 | 1.72 | +11.11 | 1.04 | 1.35 |
| 115 | +0.618 | 1.62 | +7.68 | 1.18 | 1.11 |
| 200 | +0.623 | **2.02** | +7.73 | 1.86 | 1.10 |
| 300 | +0.512 | **2.02** | +6.33 | 2.41 | 0.82 |
| top-10% decile | +0.638 | **1.80** | +7.93 | 1.43 | 1.12 |

**The exact portfolio regime-filter claims gets t=2.46 net, I get t=1.80 gross.** A net
number cannot exceed the gross number of the same portfolio. Either their demeaning
benchmark differs from equal-weight-universe (making "market-demeaned" a different and
weaker control), or their eligibility screen is narrower. **regime-filter must publish its
universe definition before that t=2.46 is quoted again.** Until then treat it as unreplicated.

Two things I will say in momentum's favour, because they are true:
- The N-curve is **smooth**, not zig-zag: monotone rise 5→50, flat plateau 50→300. This is
  not the noise signature momentum-validation found at N≤50. momentum-validation's kill is
  right in conclusion but its method was too narrow — it never tested N>50, which is where
  every academic momentum decile lives, and where the t is 4x higher.
- Long–short top-vs-bottom decile: +14.86%/yr gross, t=1.90.

**Why it still dies — the arithmetic neither agent ran.** The only versions reaching t≈2
need **150–300 names**. Against our capital:

| capital | N=200 → per position | Rs18.80 DP on ~59 sells/mo | annual DP drag |
|---|---|---|---|
| Rs25,000 | **Rs125** | not executable | — |
| Rs3,00,000 | Rs1,500 | Rs1,109/mo = 0.370% | **4.53%/yr** |
| Rs10,00,000 | Rs5,000 | Rs1,109/mo = 0.111% | 1.33%/yr |

At Rs25,000 a 200-name book means Rs125 per name — **below the share price of most eligible
NSE stocks. The strategy is not executable at all below roughly Rs10 lakh.** At Rs3L, DP +
STT ≈ 5.3%/yr against a 7.7%/yr gross excess, leaving ~2.4%/yr at t well under 1. The
t≈2.0 is also already cherry-picked across 9 values of N, and the second half decays to
t=0.82–1.10 in every specification. Bar is |t|≥4. **Confirmed dead — but for the size
reason, not the reason momentum-validation gave.**

---

## KILL 2 — short straddle: I reproduce it exactly, and it still fails its own bar.

`options-selling.md` is the only lane with a positive t. I re-implemented the whole thing
from `nv.json` with my own Black-Scholes and cost model and **matched every number**:
n=427, mean Rs2,551/wk, t=3.13; OOS t=2.01. The code is correct. Three attacks:

**(a) Serial correlation — does NOT kill it.** Bad weeks cluster, so I expected the t to be
inflated. Newey-West (6 lags): ALL 3.27, IS 2.38, **OOS 2.29** — slightly *higher*, not
lower. Block bootstrap (8-week blocks, 20k draws): OOS p=0.0102. The statistics are honest.
Credit where due.

**(b) It fails the pre-registered bar.** Their own count is ~20 variants → Bonferroni |t|≥2.8
and α=0.0025. OOS t=2.01 (NW 2.29), bootstrap p=0.0102. **Both miss.** The full-sample t=3.13
includes the window the search ran on and cannot be quoted. The honest verdict is not
"needs more data" — by the rule agreed before the search, this is a fail.

**(c) The out-of-sample confirmation is one and a half years.**

| year | n | mean/wk | total | t |
|---|---|---|---|---|
| 2023 | 49 | Rs243 | 11,898 | 0.12 |
| 2024 | 50 | Rs1,844 | 92,206 | 0.71 |
| 2025 | 48 | Rs4,511 | 216,539 | 1.84 |
| 2026 (part) | 31 | Rs4,453 | 138,056 | 1.22 |

**No single year is significant. 77% of the entire OOS profit (Rs354,595 of Rs458,699) comes
from 2025–26.** The first two holdout years earned Rs1,052/wk — already below the level that
survives any IV haircut. The holdout did not confirm the in-sample result; it confirmed it
for 20 months out of 44.

**(d) The break-even is unchanged and the unknown points the wrong way.** I solved it
directly by bisection: break-even IV multiplier = **0.887 all / 0.8765 IS / 0.8987 OOS**.
So on the holdout alone you have **10.1% of margin for error in one unobserved input.**
India VIX is a model-free variance-swap measure integrated across strikes; with NIFTY's
steep put skew it is **structurally above ATM IV** (Jensen + skew), and 30-day VIX sits
above 7-day IV whenever the term structure is in contango, which is most of the time.
**Both known biases are same-signed and against the trade.** OOS-only sensitivity:
VIX×0.97 → t=1.41; ×0.95 → t=1.02; ×0.92 → t=0.42; ×0.90 → t=0.03. This is not a symmetric
"needs more data" — it is a result whose one missing input is known to lean the killing way.

**What would break it / save it:** NSE F&O bhavcopy (`fo*bhav.csv`, free) for expired NIFTY
weeklies. If observed ATM weekly IV averages ≥0.90× same-day India VIX, the edge is real and
this becomes the best lead we have. If it averages <0.89×, it is zero. **That single download
settles it and nothing else will.** Do not trade it before that file exists — and never naked:
their own worst week is −69% of margin and max DD −136% of margin, which is not a drawdown,
it is a closed account.

**One thing I could not break:** the Rs136/lot = **0.60% of premium** cost measurement. I
re-derived it line by line and it holds. That is a genuine, reusable structural fact.

---

## Claims I am flagging as under-supported (not yet worth a full re-run)

- **`futures.md`: "top-200 turnover universe is cleaner, worth keeping as a filter"** —
  built on comparing two in-sample point estimates (+9.81% vs +7.88%, n=48) with **no t-test
  on the difference** and no OOS check. My N-curve above shows ±11pp sampling bands on
  numbers like these. Do not adopt this as a filter on this evidence. (Its main verdict —
  futures not viable, Rs1.1L/lot margin floor — is solid and independently arithmetic.)
- **`cost-engineering.md`: "Flattrade 0.0355% flat at all sizes"** — this is the one finding
  that would change other conclusions, and it rests on a vendor page promising *zero*
  brokerage. Verify by placing one live round trip and reading the contract note before any
  backtest is re-charged at 0.0355%. Its own closing caveat is the right one: spread and
  slippage (0.03–0.10%) are untouched by broker choice, so the true floor is ~0.07–0.14%,
  which leaves the order-book-imbalance edge (0.0049%) dead by 15–29x regardless.
- **`cost-engineering.md` vs `options-selling.md` disagree on options STT**: 0.15% vs 0.1%
  of premium. If 0.15% is right, the straddle cost rises ~50% and every t above drops.
  Resolve before quoting either.

## Confirmed dead, no further work warranted
`pairs-arb` (t=7.34 IS → −0.68 OOS, textbook selection bias, correctly self-identified),
`index-flows` (turn-of-month sign-inverts OOS; underperformed buy-and-hold 6.2% vs 14.8%
even in-sample), `loss-forensics` (3.91 bps gross vs 6.86 bps toll; 56 filters, train/holdout
correlation −0.037 — that number alone is conclusive), `regime-filter` (day-level p=0.17;
its own catch that 20,789 trades across 15 engines have effective n=58 is the single most
valuable methodological point produced today and should be applied retroactively to every
per-trade t-stat in the repo).

## Standing instruction
Two agents produced contradictory t-stats on the same file today. Every lane must publish its
**universe definition and eligibility filter** alongside its t-stat, or the number is not
checkable and should not be acted on.
