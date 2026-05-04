# TradePilot Observation Journal — Phase 2 (2026-04-29 → 2026-05-25)

Per `docs/IMPLEMENTATION_BRIEF_2026-04-27.md` §3, this is a 4-week observation
window with **NO engine code changes** allowed. Bug fixes that don't touch
trading behavior (logging, docs, infra) are still allowed.

Update weekly (Mondays after `weekly-stats-tracker.py` runs). 1-2 lines per week.

---

## Week 1 — 2026-04-28 (Tuesday) — first day under Track A logic

(to be filled by Soumya / next Claude session after Tuesday EOD)

Look for:
- `[SHORT_BLOCK]` log line in first 60 min if Tuesday opens with bullish gap up
- `[RE-ARM]` log lines after any TARGET hits
- `FLAT_FORCE_EXIT` reason in 13:30-14:00 window
- Net P&L vs gross P&L gap (~12 bps × 50 trades ~= ~Rs 600/day)

---

## Week 2 — 2026-05-04

(to be filled)

---

## Week 3 — 2026-05-11

(to be filled)

---

## Week 4 — 2026-05-18

(to be filled)

---

## Decision Gate — 2026-05-25

(to be filled with the 4-criteria check from brief §4)
- 2026-04-29: v4 Rs  +47,354, v5(Fix#1) Rs  +18,044, v6 Rs   +4,833. Verdict: Track A is hurting v4. SHORT_BLOCK or RE-ARM mis-firing on v4 signal mix.
- 2026-04-30 mid-day: ⚠️ DATA HYGIENE BUG SURFACED. VEDL went ex-date for 4-way demerger (price 773.60 → 277.70 in SPOS = ratable value distribution, not market loss). All 7 engines took stoploss on VEDL within an hour, contributing −Rs 93,571 (79%) of apparent −Rs 1,18,681 combined loss. REAL combined loss ~−Rs 25K (normal SIDEWAYS bleed). Action: corporate-action ex-date filter is now top-priority Phase 1 hygiene fix, scheduled weekend May 3-4. See FUTURE_PLANS.md TOP PRIORITY section.
