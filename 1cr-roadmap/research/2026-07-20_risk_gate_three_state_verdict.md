# Risk Gate + Three-State Verdict — Research & Implementation Spec

**Date:** 2026-07-20 | **Author:** Soumya Swain | **Status:** Research → ready to implement
**Source:** Aide capture #102 — Instagram @seb.ai, "24/7 AI trading agent" (https://www.instagram.com/p/Da6C_ajgZ2B/)
**Full research artifacts:** `~/Documents/tinker/projects/aide/data/items/102/` (report.md, report.pdf, mindmap.mmd, research.json)

---

## 1. Source & Credibility

The post shows a continuously running Claude-based trading agent with a six-stage
pipeline: **SCAN → SIGNALS → PLAN → RISK → MONITOR → DECISION**. Human review
required; decision-support, not autonomous execution.

**Credibility: medium-low as a system, medium-high as a pattern.** It is
engagement-bait (no backtest, no performance data, no costs). We adopt the
*architecture shape only* — it matches institutional practice (separation of
signal generation from risk approval) and our own root-cause finding that
TradePilot's edge is **execution discipline, not ML**.

## 2. The Two Ideas Worth Adopting

### Idea A — Risk as a pipeline *gate*, not inline checks

The risk stage sits **between** plan generation and the decision. A
good-looking setup can still be rejected purely on exposure / drawdown /
volatility grounds, and the rejection is recorded with a reason.

### Idea B — Three-state verdict: APPROVED / WATCHLIST / REJECTED

Binary trade/no-trade forces marginal setups into one of two wrong buckets.
The WATCHLIST middle state lets the engine *defer* — structurally suppressing
overtrading (our classic failure mode: chop-day churn, see v5_chop work).

Plus one schema upgrade that falls out of the pattern:

### Idea C — Explicit `invalidation_condition`, distinct from the stop

The stop is a *price*; the invalidation is a *thesis falsifier* ("close below
20DMA", "sector RRG quadrant flips", "news catalyst reversed"). A position can
be thesis-dead long before the stop is hit. Today we hold to stop/target/aging
— this is measurable dead-capital time.

## 3. Current State (what v5/v8 already has)

| Pattern element | TradePilot today | Gap |
|---|---|---|
| SCAN / SIGNALS | `run_premarket` + scorer in `scripts/v5-paper-trade.py` | none — keep |
| PLAN (entry/target/stop/size) | built inline at entry time | no invalidation field, plan not a first-class object |
| RISK | `prototype/v5/risk_manager.py` — `check_can_trade`, `check_position_size`, `check_all_breakers`, tier breakers, VIX multiplier | called **inline during entry scan**, binary pass/fail, reasons not systematically logged per-candidate |
| MONITOR | `scan_positions` + aging + DATA-GUARD | monitors price vs stop/target, not thesis invalidation |
| DECISION | implicit (whatever passes checks gets entered) | no WATCHLIST state, no per-candidate verdict artifact |

So this is a **refactor + two features**, not a new engine.

## 4. Proposed Design

### 4.1 `TradePlan` — first-class plan object

```python
@dataclass
class TradePlan:
    symbol: str
    side: str                    # LONG / SHORT
    entry: float
    target: float
    stop: float
    invalidation: str            # machine-checkable thesis falsifier, e.g.
                                 # "close_below:20DMA", "rrg_quadrant_exit:sector",
                                 # "score_drop_below:55"
    size_rs: float
    pool: str
    score: float                 # scorer output that produced this plan
    rationale: str               # one line, for audit trail
```

Every candidate that clears the signal threshold becomes a `TradePlan`
**before** any risk logic runs.

### 4.2 `RiskGate.evaluate(plan) -> Verdict`

New module `prototype/v5/risk_gate.py`, wrapping the existing `RiskManager`
(no logic rewrite — the gate *orchestrates* existing checks and adds the
verdict layer):

```python
class Verdict(Enum):
    APPROVED = "approved"
    WATCHLIST = "watchlist"
    REJECTED = "rejected"

@dataclass
class GateResult:
    verdict: Verdict
    reasons: list[str]           # every check that fired, pass or fail
    checked_at: str
```

Decision rule (first cut — tune in shadow):

- **REJECTED** — any hard fail: breaker tripped (`check_all_breakers`),
  blacklist, position-size fail, pool cash fail, session-loss limit.
- **WATCHLIST** — no hard fail, but any *soft* signal: score within 5 points
  of threshold, VIX multiplier < 1.0, sector already at exposure cap,
  DATA-GUARD degraded feed, or breaker in warning tier.
- **APPROVED** — clean pass on all checks.

WATCHLIST items are re-evaluated on each scan cycle for N cycles (start: rest
of session), promoted to APPROVED only if the soft condition clears; logged
either way.

### 4.3 Pipeline placement

```
premarket scan → score → build TradePlans → RiskGate → APPROVED → execute
                                              ├→ WATCHLIST → re-check next cycle
                                              └→ REJECTED  → log with reasons
```

`scan_positions` (MONITOR) gains one check: evaluate each open position's
`invalidation` condition; on trigger, exit with reason `INVALIDATED`
(distinct from `STOP`/`TARGET`/`AGED` in the audit trail).

### 4.4 Audit artifact

Per session, write `docs/paper-trades/<variant>/YYYY-MM-DD_verdicts.json`:
every plan + gate result. This is the dataset that later answers "does the
WATCHLIST state actually reduce churn?" and feeds the EOD audit reports.

## 5. Implementation Plan (Gate-style, per house convention)

**Phase 0 — Schema + gate module (no behavior change)**
`risk_gate.py` + `TradePlan`; wire into v5 wrapper in *log-only* mode: gate
runs and records verdicts, but execution still follows today's inline path.
Zero risk; produces the comparison dataset immediately.

**Phase 1 — Shadow variant (Gate-2 style, like v5_chop)**
New wrapper `scripts/v5_gate-paper-trade.py` (roster + watchdog + compare,
`TELEGRAM_DISABLE=1`) where the gate *drives* execution. Run ≥2 weeks
alongside live v5. Pass criteria (mirror v5_chop conventions):
- Fewer trades on chop days with equal-or-better P&L capture ratio
- Zero APPROVED trades that inline logic would have blocked (gate is never *looser*)
- `INVALIDATED` exits show better avg exit price than the eventual stop would have

**Phase 2 — Invalidation monitor**
Add invalidation checks to `scan_positions` in the shadow first. Measure
dead-capital days recovered.

**Phase 3 — Promote**
If shadow passes, flip live v5 (and port to v8 April-recipe engine) to
gate-driven execution. The verdict JSON becomes a permanent audit artifact.

## 6. What We Explicitly Do NOT Adopt

- 24/7 operation — NSE hours only; no overnight agent loop.
- Autonomous execution — paper/alert discipline stays; human review stands.
- The post's prompts — unverified engagement bait; our scorer stays.

## 7. Open Questions (decide before Phase 1)

1. WATCHLIST re-check cadence and expiry — every cycle vs every 15 min; expire EOD?
2. Should WATCHLIST items reserve pool capital, or compete fresh each re-check? (Lean: compete fresh — reserving reintroduces overtrading pressure.)
3. Invalidation DSL — start with 3 machine-checkable forms (`close_below:<ind>`, `score_drop_below:<n>`, `rrg_quadrant_exit:<sector>`) or free-text with manual audit? (Lean: 3 forms; free-text is unenforceable.)
4. Does v8 get the gate simultaneously or after v5 shadow passes? (Lean: after — one experiment at a time.)
