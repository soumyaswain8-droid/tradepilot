# Review — RRG Directional Bias Design Draft

**Reviews:** `docs/research/2026-07-24_rrg-directional-bias-design-DRAFT.md`
**Date:** 2026-07-28
**Verdict:** Direction of travel is right. **Do not implement option (b) as currently
specified** — it contains a threshold-reuse flaw that would make it a near-permanent
long-block rather than a targeted veto. Two blocking items, one sizing item, below.

---

## What the draft gets right

§3 is the load-bearing section and it is correct: Gate-1 validated a **binary
CHOP/TREND classifier scored against loss-capture**, i.e. "is today risky enough to
throttle." It never scored the signal's *sign* against realized direction. Treating
the passed gate as license for directional use is an unvalidated extrapolation, and the
draft says so plainly rather than riding the 2-day anecdote. The §2 self-corrections
(Rs 1,036 not Rs 532; "18" was v5_classic's long leg, not a short book; "Rs 4.4k" is the
on-the-table column, not realized) are the right instinct — figures were re-derived from
artifacts instead of inherited from the prompt.

The rollout plan in §6 is also right: a new `v5_rrg_dir` shadow with `v5_rrg` as the
A/B control keeps the already-validated CHOP throttle unconfounded.

---

## BLOCKING 1 — option (b) reuses a throttle threshold as a directional divider

§4(b) proposes reusing `THRESHOLD = -0.2143` to split days into cyclical-leadership
(veto shorts) and defensive-leadership (veto longs), justified as avoiding "a second
calibration surface."

**This repeats the exact error §3 identifies.** From `prototype/v5/rrg_regime.py`:

- The statistic is `pos_def - pos_cyc` (line 100-102) — its natural neutral point,
  where defensives and cyclicals lead equally, is **`signal = 0`**.
- `THRESHOLD = -0.2143` is a **one-sided trigger** fitted so that `signal >= th` → CHOP
  (line 21-22, `rrg_score()` line 105-113). It answers "throttle or not," and it is
  deliberately offset *below* zero to make the throttle fire readily.

Using an intentionally-conservative throttle trigger as a two-sided directional divider
means every genuinely neutral day (signal between −0.2143 and 0) is classified as
**defensive leadership** and would fire "block fresh LONG adds."

Live `v5_rrg` sessions confirm the skew:

| Session | signal | (b) branch under −0.2143 |
|---|---:|---|
| 2026-07-21 | +0.2857 | defensive → block longs |
| 2026-07-22 | +0.1429 | defensive → block longs |
| 2026-07-23 | −0.3571 | cyclical → block bottom-pct shorts |
| 2026-07-24 | +0.1429 | defensive → block longs |

**3 of 4 sessions block longs.** That is not a targeted veto against LONG_IN_BEAR; it is
a standing long-suppression regime that happens to switch off occasionally.

**Required change:** a directional split needs its own zero-crossing plus a dead-zone —
i.e. `signal > +d` = defensive-lead, `signal < -d` = cyclical-lead, `|signal| <= d` =
neutral/no veto, centred on 0, with `d` fitted by the §5 backtest. Option (b) cannot
inherit −0.2143 and must accept that it opens a calibration surface. That is not a
reason to prefer (a) or (c) — it just means (b)'s stated cost advantage is illusory and
its threshold must go through the same gate discipline §4's TrendScore lesson demands.

## BLOCKING 2 — the proposed pass bar is inside the noise band at the proposed sample size

§5 proposes "≥65% day-call accuracy" over "~21-30 sessions." Against a coin-flip null:

| n | 65% bar | p-value | accuracy needed for p<0.05 |
|---:|---:|---:|---:|
| 25 | 17/25 | **0.054 — not significant** | 72% |
| 30 | 20/30 | 0.049 — marginal | 67% |
| 40 | 26/40 | 0.040 | 65% |
| 60 | 39/60 | 0.014 | 62% |

At the draft's own suggested sample size, a "PASS" is indistinguishable from luck. The
draft flags the thin sample qualitatively (§5, §7 Q3) but then sets a bar that the
sample cannot support.

**Required change:** either hold the 65% bar and set the session floor at **n ≥ 40**, or
keep n≈25-30 and raise the bar to ~72%. Given §5's own argument that wrong-side
leverage costs more than a missed throttle, **n ≥ 40 at 65%** is the better trade.

Separately: scoring two metrics (day-call accuracy AND P&L differential) is two chances
to pass. Pre-register both bars before running, and treat passing only one as a FAIL.

## SIZING — the backtest must report suppression rate, not just skill

Neither §5 metric measures **how much of the book the veto removes**. On 2026-07-23 the
fleet ran 85 shorts of 111 trades; "block bottom-percentile SHORT allocation" on
cyclical-lead days could remove a large share of the book with nothing replacing it.
A veto that suppresses 40% of trades is a different instrument from one that trims 5%,
even at identical day-call accuracy — the first is a de-facto exposure cut whose P&L
effect is dominated by being flat, not by being right.

**Add metric 3:** for each veto branch, report trades suppressed / total trades, and the
counterfactual P&L of the suppressed set. A directional veto should be judged on the P&L
of what it *blocked*, not only on the P&L of what it let through.

## Minor — ambiguity in the §5 ground-truth timing

"For each session, label RRG's sign ... compare against **next-session** ^NSEI
close-to-close return sign." The sensor scores session `t` using closes strictly before
`t`. The veto then acts during session `t`, so the realized direction that matters is
**session `t`'s own** return. If "each session" means the data session `t-1`, then
"next-session" resolves to `t` and is correct — but as written it can equally be read as
`t+1`, which would test a longer-horizon claim the veto never makes. Pin this down
explicitly in the harness spec; an off-by-one here silently invalidates metric 1.

---

## Answers to §7 open questions

1. **Which option first?** Agree: **(b)**. But see BLOCKING 1 — it needs its own
   centred dead-zone, so its "no new calibration surface" advantage does not hold.
2. **Threshold?** **Disagree with the lean.** Do not start from −0.2143. Centre on
   `signal = 0` and fit a dead-zone `d` in the backtest.
3. **Sessions before promotion?** Raise to **≥40** directionally-labeled sessions
   (BLOCKING 2), not 20-30.
4. **Stack or replace?** Agree: **stack**, veto inert on days the throttle already
   suppresses. Note this shrinks the effective directional sample further — days where
   both fire cannot discriminate between them, so count only throttle-inactive days
   toward the n≥40 floor.
5. **Ground truth?** Agree: fleet long-vs-short realized P&L split as primary, ^NSEI
   sign as cross-check. Fix the timing ambiguity above.

---

## Recommended next step

Run the §5 backtest **on direction only** — no code changes to any engine, no new shadow
yet — with the corrected threshold parameterization (centred dead-zone) and the n≥40
floor. If the archive cannot yet supply 40 sessions, that is itself the answer: keep
`v5_rrg` collecting and revisit. Spinning up `v5_rrg_dir` before the backtest would put
an unvalidated directional rule on live capital-equivalent paper flow, which is the
thing §3 was written to prevent.
