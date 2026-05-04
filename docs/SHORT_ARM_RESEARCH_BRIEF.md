# SHORT-Arm Dormancy — Research Brief (2026-04-24)

## The Problem

Every v5-family engine (v5, v5_6, v5_7, v5_classic, v5_3) produces SHORT signals daily, but **zero SHORT positions are ever deployed**. Confirmed across 3 trading days (04-22, 04-23, 04-24).

Today's signal log (identical pattern on every rescore):
```
[09:06:47] v5 signals: BUY=40 SELL=20 HOLD=140 | regime=SIDEWAYS
[09:37:44] v5 signals: BUY=40 SELL=20 HOLD=140 | regime=SIDEWAYS
```

**20 SELL signals generated → 0 SHORT positions opened.** All day. Every engine.

Impact: in BEAR tapes v5 has no offset → morning bleed (v5 was −₹2,188 at 11:26 today before afternoon reversal saved it).

## Engines Confirming the Pattern

| Engine | Banner says | SHORT deployed today | 
|---|---|---|
| v5 | "Multi-Pool + Short" | 0 (out of 20 SELL signals × 3 rescores = 60 chances) |
| v5_6 | "Multi-Pool + Short" | 0 |
| v5_7 | "Multi-Pool + Short" | 0 |
| v5_classic | "Multi-Pool + Short" | 0 |

## Investigation Scope — Where Is the SHORT Being Rejected?

Trace the signal path from generation → deployment and find where SHORTs die:

### Path to trace
```
v5.signal_engine (generates BUY=40, SELL=20, HOLD=140)
   ↓
v5-paper-trade.py (consumes signals, creates position requests)
   ↓
prototype/v5/rust_bridge.py (sends to Rust risk layer)
   ↓
engine/src/risk/mod.rs (Rust risk checks — position caps, daily loss, etc.)
   ↓
engine/src/main.rs (execution)
```

### Candidate rejection points

1. **Python-side filter** — does `v5-paper-trade.py` iterate only over BUY signals and drop SELLs silently? Check the signal-consumption loop.

2. **Rust risk gate** — is there a `cfg.allow_shorts` or similar flag defaulting to `false`? Check `engine/src/risk/mod.rs` and `.env` for `RUST_ALLOW_SHORTS` or equivalent.

3. **Position sizer** — does the sizer require margin/collateral for SHORTs that isn't wired up (paper account only has cash, no margin)?

4. **Symbol eligibility** — SEBI has F&O-only-shorts for most equities. Does the engine correctly filter the SELL universe to shortable symbols? Or does it try to SELL cash equities and get rejected?

5. **Gateway adapter** — `rust_bridge.py` may translate only BUY → LONG and have no SELL → SHORT path.

## Expected Findings

Likely one or more of:
- Hardcoded `if signal.action == "BUY":` loop that skips SELL entirely
- Missing Rust risk flag (`allow_short_positions = false`)
- Missing symbol-shortability check (all SELL signals flagged as "not shortable")
- No paper-trade SHORT simulation logic (all shorts return "rejected: not implemented")

## Deliverable

A single diagnosis doc at `docs/SHORT_ARM_DIAGNOSIS.md` containing:
1. **Exact file + line number** where SHORT signals die
2. **Root cause** (missing flag / missing branch / missing adapter / all of the above)
3. **Minimum-invasive fix** (one-line flag flip? new branch? new module?)
4. **Impact simulation** — using today's snapshot JSONL, estimate what P&L v5 would have had if the 20 SELL signals had deployed as SHORTs this morning (pick a reasonable position size)
5. **Risk caveats** — what could break (margin calc, unlimited-loss potential on naked shorts, SL semantics inverted for SELL, etc.)

## Constraints

- **Do NOT modify engine code.** Research + diagnosis only. Implementation happens in main window after weekend review.
- **Per agent-safety rules**: 20-min hard limit, 15 tool calls max. Break into smaller subagents if you need more.
- **Time box**: spend max 5 min on any one file. Use grep/find aggressively.

## Starter Commands

```bash
cd /Users/soumyaswain/Documents/tinker/projects/tradepilot

# Grep for all SHORT/SELL handling
grep -rn "SHORT\|SELL\|short_\|allow_short" scripts/v5-paper-trade.py prototype/v5/ engine/src/ | head -40

# Check Rust config flags
grep -rn "allow_short\|max_short\|RUST_MAX" engine/src/ .env

# Check the bridge
cat prototype/v5/rust_bridge.py | head -100

# Check signal engine output
grep -n "SELL\|generate_signals" prototype/v5/signal_engine.py | head -20
```

## Reference Reading

- Today's EOD summary (with all 10 tune-up items): main Claude window
- Memory: `~/.claude/projects/-Users-soumyaswain/memory/feedback_v5_no_change_until_apr24.md`
- v5 engine banner: `logs/v5-2026-04-24.log` line 1-2
- Signal counts: `logs/v5-2026-04-24.log` grep "signal_engine.*signals:"

Good hunting.
