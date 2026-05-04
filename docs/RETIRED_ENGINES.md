# TradePilot — Retired Engines

This file tracks engines that have been removed from the daily launch but whose
code, models, and trade history remain in the repository for reference.

To re-enable any retired engine, uncomment its entry in `scripts/launch-market.sh`
ENGINES array (and re-load any LaunchAgent if disabled).

---

## Retired 2026-04-27 (post-market)

| Engine | Reason | Cumulative P&L at retirement | Code preserved | Re-enable |
|---|---|---:|---|---|
| ~~**v4** (ML composite)~~ — **RE-INSTATED 2026-04-28** | Original retirement was based on only 2 days of data (mean Rs -2,981/day). Day 3 (2026-04-28) v4 made +Rs 15,330 in 4 hours with 82% WR, including aggressive winner re-entries (IDEA, GLENMARK, WAAREEENER all re-entered). 2-day sample is statistically too small per the validation framework we ourselves agreed on. v4 stays in active observation through 2026-05-25 for honest evaluation. | (re-instated active) | `scripts/v4-paper-trade.py` + `prototype/v4/` (intact) | RE-ACTIVE in launch-market.sh + crash-watchdog.sh + status-digest.py |
| **v5_2** (F&O straddle experiment) | Cycle-based, not continuous — runs single straddle cycles and exits. Insights logged. Not appropriate for the v5-lineage observation discipline. | +Rs 9,720 (single experimental day) | `scripts/v5_2-paper-trade.py` (intact) | uncomment `v5_2|...` in launch-market.sh |
| **v5_3** (over-filtered variant) | 1/10 win days, mean Rs -19/day, 95% CI contains zero. Empty model dir at `prototype/v5/models/`. Statistically dead. | -Rs 52,864 cumulative | `scripts/v5_3-paper-trade.py` (intact) | uncomment `v5_3|...` in launch-market.sh |

**Active set as of 2026-04-28:** v4 (re-instated), v5, v5_classic, v5_6, v5_7 (5 engines)
**Still retired:** v5_2 (F&O cycle), v5_3 (over-filtered)

---

## Learning Note — 2026-04-30 VEDL Demerger Incident

**What happened:** Every active variant (v4, v5, v5_2, v5_3, v5_6, v5_7, v5_8, v6) booked a paper-trading loss of Rs 11K–15K. A single LONG SWING in VEDL accounted for Rs 6.5K–14K of that loss in EACH variant.

**Root cause:** Today was Vedanta's ex-date for a 1:1 demerger into 5 entities (Vedanta Ltd residual + Aluminium + Talwandi Sabo Power + Malco Energy + Iron & Steel). Price feed showed Rs 773 → Rs 277 (−64%), which the engines treated as a market crash and stoplossed. Real economic impact for a holder is ~zero — value moved to four newly-issued ISINs.

**Adjusted P&L** (VEDL stripped, see `docs/paper-trades/<variant>/2026-04-30_adjusted.md`):
- v5: −Rs 2,462 · v5_6: −Rs 244 · v5_7: −Rs 1,460 · v5_8: −Rs 5,090 · v5_classic: −Rs 1,757 · v6: −Rs 1,217
- True combined day: ~−Rs 12K, not −Rs 1.18L. Routine sideways-day chop.

**Why no defense triggered:**
- No portfolio-wide intraday cap (only monthly: 8% SWING / 10% INTRADAY).
- Portfolio-daily 1% cap (Rs 50K) — VEDL was 0.28% of portfolio.
- v5_2's per-trade kill-switch (Rs 5K) lived only inside `scripts/v5_2-paper-trade.py`, never inherited.
- Zero corporate-action ex-date filter anywhere in the pipeline.

**Fixes shipped 2026-05-01 (before next market open):**
1. `prototype/data/blacklist.json` — VEDL banned through 2026-05-07.
2. `prototype/data/corp_actions.json` — ex-date calendar; auto-bans symbols within ex-date ± 7 days.
3. `prototype/v5/risk_manager.py` — promoted v5_2's kill-switch to module-level: `BASELINE_DAILY_LOSS_KILL_RS=-5000`, `BASELINE_MAX_POSITION_PCT=0.10`. Auto-loads blacklist + corp_actions on init.
4. `RiskManager.check_can_trade()` now auto-polls pool aggregate and refuses entries when threshold breached — every variant inherits with zero script changes.
5. `scripts/fetch_corp_actions.py` — NSE auto-fetcher (run nightly).
6. Adjusted EOD reports under `docs/paper-trades/<variant>/2026-04-30_adjusted.{json,md}`.

**Why all 7 engines lost on the same stock:** They share `v4.composite_scorer` as the entry signal source. Same scorer + no per-stock cool-off = 7 wrappers around one opinion. This is now a known limitation; per-stock cool-off is a weekend Phase-2 fix.

**Bigger lesson:** Strategy losses look different across variants; data losses bleed identically. Today's identical loss across 7 variants is a hygiene-layer signal, not a strategy signal — and that pattern is only visible because we ran a side-by-side observation.
