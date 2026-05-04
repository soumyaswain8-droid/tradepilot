# TradePilot Future Plans

> Living roadmap. Source of truth for "what's next" across all timeframes.
> Updated nightly when something changes. Last updated: 2026-04-30 11:25 IST.

---

## TOP PRIORITY (added 2026-04-30 mid-day) — CORPORATE-ACTION FILTER

**Severity**: Critical. **Status**: Spec'd, awaiting weekend implementation.

### Why this jumped to #1

On 2026-04-30, VEDL (Vedanta) went ex-date for a 4-way demerger (1:1 into Vedanta Aluminium + Talwandi Sabo + Malco Energy + Vedanta Iron & Steel + residual). Price went from Rs 773.60 → Rs 277.70 in the special pre-open session — a −64% "drop" that was actually ratable value distribution, not a market loss. All 7 engines took stop-losses on VEDL within an hour, contributing −Rs 93,571 (79%) of today's apparent −Rs 1,18,681 combined loss.

The engines are not currently aware of corporate-action ex-dates. Without this filter, EVERY engine bleeds the same fake loss on every demerger / split / bonus / special-dividend ex-date. This is the only failure mode the observation window has surfaced that corrupts ALL engines simultaneously (because they share the same data feed).

### What the fix is

A pre-trade gate added to the v5 risk_manager (and parallel to v4's deploy logic):

| Component | Spec |
|---|---|
| Data source | NSE corporate-actions API (`https://www.nseindia.com/api/corporates-corporateActions`), refreshed daily at 08:00 IST |
| Storage | `prototype/v5/corporate_actions.json` — `{symbol: [{ex_date, action_type, ratio, ...}]}` |
| Pre-trade gate | If `today` is in `corporate_actions[symbol].ex_dates` → reject the signal with reason `"CORP_ACTION_EX_DATE"` |
| Action types to filter | DEMERGER, SPLIT, BONUS, SPECIAL_DIVIDEND, RIGHTS, MERGER, BUYBACK |
| Lookahead window | Block 1 day before ex-date too (T-1) to avoid race conditions in price discovery |
| Lookback window | Block 2 days after ex-date (T+1, T+2) to let the price settle |
| Logging | Log every rejection at INFO level for audit |

### Where to put the code

- New file: `prototype/utils/corporate_actions.py` — fetch, cache, query helper
- Daily cache: `data/corporate_actions/YYYY-MM-DD.json`
- Pre-trade gate hook: `prototype/v5/risk_manager.py` `check_can_trade()` — add at the very top, before slot-cap check
- v4 integration: `scripts/v4-paper-trade.py` deploy_signals — same gate inline
- LaunchAgent: daily 08:00 IST run of the fetcher

### Why this is Phase 1, not Phase 2

This is a *data hygiene* fix, not a strategy change. It doesn't violate the no-engine-code-changes rule because:
1. It's purely defensive (only adds rejections, never new positions)
2. It corrects a known data-feed gap, not a strategy parameter
3. It cannot make any engine perform worse — only filter out fake losses

### Acceptance test

After ship, run a dry replay of 2026-04-30:
- Without filter: VEDL contributes −Rs 93,571 across 7 engines
- With filter: VEDL is rejected pre-trade, contributes Rs 0 across 7 engines

### Owner / timeline

Soumya / Claude — this weekend (May 3-4) parallel to the SEBI compliance research agent.

---

---

## Active observation window (now → 2026-05-25)

| Item | Owner | Status |
|---|---|---|
| 7-engine paper trading (v4, v5+Fix#1, v5_classic, v5_6, v5_7, v6, v5.8) | engines (auto) | Active |
| Daily EOD comparison (16:11 IST) | LaunchAgent + cron | Active |
| 4-week observation freeze — no engine code changes | Soumya / rules | Active |
| Daily regime-switching research watchdog (07:00 IST) | LaunchAgent + cron | **NEW 2026-04-29** |
| Track v5 vs v5.8 head-to-head (does removing slot partition close gap?) | EOD reports | Day 1 = 04-30 |
| Track v6 vs v4 head-to-head (does Track A help v4 signals?) | EOD reports | Day 2 = 04-30 |
| Track Fix #1 firing count in v5 logs | Watchdog | Active |
| Statistical gate G1 — at least one engine: deflated Sharpe ≥ 1.0, 95% CI > 0 | gate evaluator | Pending data |

---

## v6.1 production roadmap (recap, refreshed for regime-switching findings)

Full roadmap: `docs/reports/2026-04-29/PRODUCTION_ROADMAP_v6.1.pdf` (24 pages)

### Phase 1 — Foundation (now → May 25)

Original scope unchanged. Plus one new item that does NOT violate the no-engine-code rule (because the regime detector is upstream of engines):

| Item | Status |
|---|---|
| 20-session paper validation | In progress |
| Statistical gate G1 (May 25) | Pending |
| **Daily regime-switching research** to inform Phase 2 design | NEW — daily watchdog |
| **Phase 1 detector fix research** — deeper read on `prototype/v5/regime_detector.py` look-ahead bug | NEW — to spec next week |

### Phase 2 — Intelligence (May 26 → July 21) — REFRESHED

The "Intelligence" phase was originally listed as "LLM sentiment + FII/DII + pairs trading + multi-agent orchestrator". The regime-switching deep research (`docs/research/2026-04-29/regime-switching-master.pdf`) gives this concrete order:

| Sub-phase | Time | Deliverable |
|---|---|---|
| 2.1 Detector fix | 1 week (May 26 → Jun 1) | Replace v5 vote-counting detector with 2-state Gaussian HMM + dwell time + hysteresis + TRANSITIONING band. **Single biggest win identified by research** — would have prevented 04-29's 175 blocked LONGs. |
| 2.2 Regime as a feature | 2 weeks (Jun 2 → Jun 15) | Inject `P_bull`, `P_bear`, `P_sideways` + 6 cheap macro features (`vix_india_level`, `fii_dii_flow_z`, `usd_inr_change`, `is_expiry_*`, `mins_to_expiry`, `is_event_day`) into v4 LightGBM. CPCV validation. Acceptance: DSR > 1.0, PBO < 30%. |
| 2.3 Per-regime exits + sizing | 2 weeks (Jun 16 → Jun 29) | Map `(regime, signal_strength) → (SL_mult, TP_mult, trail_type, size_mult)`. BULL = trailing 3×ATR; BEAR = tight 0.5-1×ATR + time stop; SIDEWAYS = Bollinger bracket. |
| 2.4 LLM sentiment layer | 2 weeks (Jun 30 → Jul 13) | Claude API for news headline scoring. Was original Phase 2 lead — now positioned as Phase 2.4. |
| 2.5 FII/DII + insider data | 1 week (Jul 14 → Jul 21) | NSE bhavcopy + SEBI insider filings as alpha source. |

### Phase 3 — Execution (Jul 22 → Oct 13)

Unchanged from original v6.1 roadmap.

| Item |
|---|
| Zerodha Kite Connect dev account |
| Kite execution agent + smart order routing |
| Shadow mode (4 weeks — extended from original 2) |
| **SEBI algo registration** (research scheduled for Mon 2026-05-04 by research agent) |
| AWS Mumbai deployment |
| Kill switch + audit trail |
| Live with 1 lot (4 weeks) |

### Phase 4 — Scale (Oct 14 → Feb 2 2027)

Unchanged. Adds one DEFERRED item:

| Item | Status |
|---|---|
| 1 lot → full personal capital | Original |
| Grafana dashboards + tax optimisation | Original |
| **Specialised engines + meta-router** | **DEFERRED** (only if Phase 2.1-2.3 plateau for 60 days OR a structural BEAR persists 3+ months without alpha capture) |

---

## Settled decisions (do not re-debate)

From the 5-agent regime-switching deep research, 2026-04-29:

| Question | Settled answer | Source |
|---|---|---|
| Should regime detection be probabilistic, not hard-label? | Yes | All 5 agents |
| Should detector have dwell time + hysteresis + cooldown? | Yes | All 5 agents |
| Should engines hard-switch on regime flip? | No (mathematically infeasible at 60-120 bps/day friction) | All 5 agents |
| Should we train separate ML models per regime on hard-sliced data? | No (Indian BEAR data <2,000 intraday rows = below LightGBM floor) | Agent D |
| Where should specialisation actually happen? | Exit rules + sizing, not the scorer | Agents B, D |
| Is v5's regime detector the bottleneck? | Yes (no dwell, no hysteresis, vote-counting, lagging votes, possible look-ahead bug) | Agent C |

---

## Open architectural decisions (Soumya's call)

| Decision | Default recommendation | When to decide |
|---|---|---|
| Phase 2.1 detector fix — ship inside May 25 window or after? | After May 25 (preserve observation purity) | Before May 26 |
| Phase 2 timeline — parallel to Phase 1 or strictly after? | Strictly after | Before May 26 |
| DSR threshold for promotion | 1.0 (literature standard) | Before Phase 2.2 |
| Phase 4 trigger | "Phase 2.1-2.3 plateau for 60 days" | After Phase 2.3 ships |
| RIA license route — apply or stay personal-only Y1? | Compliance research arrives Mon May 4 | After May 4 research |

---

## Open items by category

### Engine-side (uncommitted, all in working tree)

- v5 with Fix #1 (Apr 28)
- v5 with all 10 tune-ups including slot partition (Apr 24)
- v6 = v4 + Track A (Apr 28)
- **v5.8 = v5 with slot partition disabled** (Apr 29 — NEW)
- ML staging + 4-gate promotion system (Apr 27)
- All commits gated by May 25 statistical decision

### Tooling

- LaunchAgent TCC fix — script paths in ~/Documents are blocked. Move scripts to `~/Library/Application Support/tradepilot/` for launchd-fired tasks.
- launch-market.sh verify counter ("5/7" misleading) — fix regex post-market
- status-digest.py engine count fix

### Research

- **Daily regime-switching research watchdog** (NEW — see below)
- SEBI April 2026 algo trading rules + RIA roadmap (scheduled Mon May 4)
- v6.1 paper-trade feasibility (scheduled Mon May 4)

### Compliance (Phase 3 prerequisite)

- SEBI algo registration process (depends on May 4 research)
- RIA license decision (depends on May 4 research)
- Audit trail design

---

## Daily research watchdog — regime-switching domain

Starting 2026-04-30 morning, a daily LaunchAgent picks one regime-switching research topic from a rotation list of ~30 topics, fires a Claude research agent at 07:30 IST, and stores findings at `docs/research/regime-switching-daily/YYYY-MM-DD.md`. After 7-30 days we have a comparison corpus of how the literature / industry / markets have evolved on this question.

Stored data structure:
```
docs/research/regime-switching-daily/
  _topics.md              # rotation list (30+ topics)
  _README.md              # how the watchdog works
  2026-04-30.md           # tomorrow's first finding
  2026-05-01.md
  ...
```

Each daily file has the same shape (topic, key findings, sources, comparison notes), so they're trivially diff-able week over week.

---

## How to use this doc

- Read it at the start of every Claude session in this project.
- Update it whenever a future plan changes (don't let it rot).
- Items move from "Open" → "In progress" → "Shipped" → "Closed" as they progress.
- Decisions move from "Open" → "Settled" only when grounded in research or live data.
- The v6.1 PDF stays the long-form source of truth; this doc is the always-current hub.

**Next planned update**: 2026-04-30 EOD after v5.8 vs v5 first comparison.
