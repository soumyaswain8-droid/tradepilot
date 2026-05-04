# Tonight's Tune-Ups — 2026-04-23 (post-market)

Scheduled for: after market close (15:35 IST) once EOD comparison report is reviewed.
Owner: Soumya.
Status: queued · local-only · do not commit engine code until weekend review.
Trigger context: 09:55 IST regression analysis surfaced shared-signal architecture + box-theory regime mismatch.

## Item #1 — Box theory regime-override (research + spec, no engine code tonight)

**Trigger:** v5_7's box filter rejected JIOFIN at 09:45 today ("ML says BUY but at box top — SKIP"); JIOFIN went to TARGET hit (+Rs 711 for v5, +Rs 734 for v5_6 who entered late). v5_7 also reduced position size 30-50% on ADANIENSOL/ENRIN/LTM in SCAN #1 ("middle of box — reduced size") which cost ~Rs 4-5K of profit on the morning trend day.

**Hypothesis:** Box theory is range/reversion logic. It should STAND DOWN when regime is detected as STRONG-TREND.

**Tonight's deliverable:**
- `docs/research/box-theory-regime-aware-spec.md` covering:
  - Reproduce the JIOFIN miss + size reductions with exact log timestamps
  - Define "strong-trend" detection rule (e.g., NIFTY moves > X% in first 30 min, OR > Y stocks at +5% within 15 min, OR ATR > Z)
  - Propose env var `BOX_THEORY_DISABLE_IF_TREND=true` (default false to preserve current behavior)
  - Estimate impact: replay last 5 days' trades with override on/off, show win rate + P&L delta per regime
- No engine code changes. Spec only.

**Estimated time:** 45 min.

## Item #2 — Telegram 404 fix (research only tonight, fix on weekend)

**Trigger:** Every trade across v5/v5_6/v5_7 attempts a Telegram alert and gets HTTP 404 ("Not Found"). Today's count by 09:55: v5=28, v5_6=21, v5_7=16 errors. Doesn't break trading but burns curl calls + slows logging + loses notifications.

**Tonight's deliverable:**
- Identify the obsolete chat ID / bot token in the alert path
- Document where it's hardcoded vs env-driven
- Spec a fix: either update the chat ID to a working one, or add a circuit-breaker that disables alerts after N consecutive 404s
- `docs/research/telegram-alert-fix-spec.md`
- No code change tonight (engine code freeze still active).

**Estimated time:** 20 min.

## Item #3 — Continue observation: does box theory catch up after trend exhausts? (live observation, all day)

**Hypothesis:** Today's 09:13 gap-up was a strong trend day. v5 (no box filter) captured ~Rs 8.7K in the first 45 min by hitting TARGETs immediately. v5_6/v5_7 took fewer/smaller positions because box filter correctly skipped trending setups. **If the diversification thesis is right**, v5_6/v5_7 should outperform later in the day when the trend exhausts and the market enters range-bound mode.

**How to validate:**
- Capture watchdog snapshots through the day (already running every 30 min)
- At lunch (~13:00), check if v5_6/v5_7 trade count + P&L is catching up
- At EOD, document the regime shift (if any) and compare engine performance per phase

**Tonight's deliverable:**
- `docs/research/regime-shift-observation-2026-04-23.md` with:
  - Time-series chart of v5 vs v5_6 vs v5_7 P&L through the day
  - Identification of regime transition points (strong-trend → range / range → trend)
  - Per-engine performance per regime phase
  - Verdict: does diversification work as designed, OR are box engines structurally broken?

**Auto-feeds Item #1**: this observation directly informs the regime-detection threshold proposal.

**Estimated time:** 30 min (during day) + 20 min (write-up at EOD).

---

## Constraints (carry-over from yesterday)

- Local-only, no DevPilot DB push
- v5 engine code OFF-LIMITS until 2026-04-24 EOD decision gate
- No engine code commits until weekend review (Apr 27)
- Research docs / spec files CAN be committed if user explicitly requests
