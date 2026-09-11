# Operator Terminal redesign: four pages for one trading day

Date: 2026-09-11. Status: approved by Soumya (canvas reviewed, page map reviewed).
Canvas: https://claude.ai/code/artifact/cd255046-da8d-4731-9c2e-bf90564d00b0 · working files `docs/design/2026-09-11-operator-redesign/` · data map `docs/design/2026-09-11-operator-redesign/existing-page-map.md`.

## Why
The operator tier has ten pages for one person, three visual languages, two nav lists that drift, a Decisions page with hand-typed numbers, and duplicated panels (Desk vs Dashboard, Fleet vs Portfolio). Soumya's actual day asks four questions. The Terminal should answer exactly those four, on four pages, and nothing else.

## Decisions
- **Blank slate, not a reskin.** Four new templates. Old operator pages stay reachable under a "Legacy" menu until Soumya retires them. `/classic` untouched.
- **One question per page.** Ready ("do I need to fix something before open"), Market ("what is the world doing and what are we missing"), Book ("what do we hold, is it safe, are the agents working"), Review ("what happened, why did we lose, what did we learn").
- **Cheap wins ship first.** Five pieces of data already exist on disk or in a function but no route serves them. They are Phase 1 and are named individually in the Data section. Nothing in Phase 1 changes engine code.
- **Screens never fake engine fields.** Trend-at-entry, loss cause and candle-at-entry do not exist yet. Until the engine stamps them, the column shows "Not yet" in `--dim`, never a guess and never a blank.
- **Skin is the existing Terminal.** `static/desk.css` tokens are the source of truth. Green and red mean profit and loss only. Amber means warning or stale. Indigo means selection or action. Direction chips (LONG/SHORT), regime, and trend-at-entry are neutral or amber, never green or red. Chart markers keep Soumya's report standard: green entry arrow, purple exit arrow.
- **Panels are composable units.** Every panel is one Jinja include with its own fetch, skeleton and failure line, so a future per-user dashboard composer can reuse them. The composer itself is out of scope.
- **Nav has one source.** The four tabs plus Legacy and "Client app ↗" render from `_operator_nav.html` on every page including Ready. `static/desk/router.js` `SECTIONS` is retired with the old Desk.

## Pages

### 1. Ready (`/ready`, default landing before 09:15 IST)
Answers: do I need to fix something before open.

| Panel | Content | Data |
|---|---|---|
| Verdict banner | "Good to go" (green-bg) or "Fix N things before open" (amber-bg). Countdown to 09:15. | Computed client-side from the check rows: any `bad` row makes the verdict amber. |
| Pre-open checks | One row per check: dot, name, detail, optional action button. Re-fetches every 60 s. | `/api/ready` (new, Phase 2) aggregating: engines up (`/api/system-health` `ENGINE_DOWN`), last log line (`/api/recent-scans`), NaN count, ML model age (model file mtime), data link (`/api/health/datalinks`, Phase 1), regime (engine JSON), disk free, launch fired (Phase 3). |
| Yesterday in one line | Fleet net, trades, worst pattern. Link to Review for that date. | `/api/desk` `fleet`; pattern line from `learnings/daily/<date>.yaml` `insights[0]`. |
| Today's setup | Engine, capital, pool, state chip. | `/api/engine-status` `engines[]`. |
| Shadow experiments | Day N of M, per-experiment delta vs live. | `/api/shadows` (new, Phase 1). |

Action buttons call existing scripts only: "Start <engine>" posts to `/api/engine/<name>/start` (new, Phase 2, wraps `scripts/launch-market.sh` per-engine start). "Clean logs" is Phase 3.

### 2. Market (`/market`)
Answers: what is the world doing, what is running that we are not in.

| Panel | Content | Data |
|---|---|---|
| World, filtered for India | Time, headline, source, impact chip. Items without an impact tag are hidden behind "show untagged". | `/api/news` joined with `docs/sarathi/knowledge/news_impact.jsonl` (Phase 2). Until the join exists, show `catalyst` as the chip in `--dim`. |
| Mood | NIFTY, BANK NIFTY, VIX with sparkline; breadth; FII/DII; regime chip with detection time. | `/api/indices`, `/api/index/<x>/intraday`. Breadth and FII/DII render "Not yet" until Phase 3 sources exist. Regime from engine JSON. |
| Sectors now | Sector, % move. | Phase 3. Panel hidden until its route exists. |
| Running today, and we are not in | Stock, move, volume ratio, why we skipped it. Pattern line below. | `/api/missed-opportunities` joined with `/api/verdicts/<date>` (Phase 1). Reason text comes from `verdicts[].reasons[]`. A mover with no verdict shows "never scored". |

### 3. Book (`/book`, default landing 09:15 to 15:30 IST)
Answers: what do we hold, is it safe, are the agents working.

| Panel | Content | Data |
|---|---|---|
| KPIs | Net after costs; open count and capital deployed; loss if every stop hits; hit rate today with count. | `/api/desk` `fleet`, `open_positions[]` with `sl_price` (Phase 1), marks from `/api/positions-live` (Phase 1 fix). |
| Engine pods | One per engine: dot, state (picking/holding/recording/down), last scan, trades, P&L. | `/api/desk` `engines[]`, `/api/system-health`, `last_rescore_time`. "Next scan" is Phase 3, hidden until then. |
| Open positions | Sorted by distance to stop. Columns: stock/engine, side, entry, now, P&L, to stop, in trade, trend at entry. | `/api/desk` `open_positions[]` (with stop/target/mark after Phase 1). Trend at entry: "Not yet" until engine stamps it. |
| Bleeding line | Count and sum of losing positions that were entered against trend. | Client-side from the table. Hidden while trend-at-entry is "Not yet". |
| Exits today | Time, stock, reason, duration, net. Summary line: stops in first hour, short-lived stops. | `/api/desk` `recent_exits[]`; duration derived from `entry_time`/`exit_time` (Phase 1). |

### 4. Review (`/review?date=YYYY-MM-DD`, default landing after 15:30 IST)
Answers: what happened, why did we lose, what did we learn.

| Panel | Content | Data |
|---|---|---|
| Day by engine | Engine, net, hits/trades, fleet row. | `/api/desk?date=` `engines[]`. |
| Trades | Losers first. Stock/engine, in → out, net, cause chip. Click selects. | `/api/tradelab/trades/<date>` `closed[]`. Cause chip: exit `reason` today; taxonomy in Phase 3. |
| Trade chart | 5-minute candles for the session, entry and exit arrows with time and price, stop and entry dashed lines, trend band. Footer: entered, exited, net and cost, candle at entry. | `/api/stock/<sym>/chart?range=1d&date=` (needs `date` for past sessions, Phase 2). Candle at entry: "Not yet". |
| What the engine saw | `reasons[]` with sign, score and gate. Verdict line. | `closed[].reasons[]`, `closed[].score`. Verdict line is Phase 3 (needs cause taxonomy). |
| Losses by cause | Cause, sum, bar, count and wins. | Phase 2 aggregates by exit `reason`; Phase 3 re-groups by cause taxonomy. |
| Learnings recorded | Chip new/repeat, text. | `learnings/daily/<date>.yaml` `insights[]`. Repeat detection is Phase 3; chip hidden until then. |
| ML loop | Last trained, learnings used, not yet used, next retrain, "Retrain now" button. | Last trained from model mtime (Phase 1). Other rows say "Not wired" in amber until the learnings-fed retrain exists (engine work, separate spec). The panel is deliberately honest. |
| Experiment ledger | This week we are testing; closed, measured and killed; standing rules. | Copy lifted from `decisions.html`, numbers from `/api/shadows` and `/api/lab`. |

## Data

### Phase 1: cheap wins (routes only, no engine change). All five ship before any page.
1. **Stops and targets on open positions.** `/api/desk` `open_positions[]` gains `sl_price`, `target_price`, `peak_price`, `trough_price`, `trailing_activated`, read from `positions_active.json`. Enables distance-to-stop and loss-if-all-stops.
2. **Verdicts route.** New `GET /api/verdicts/<date>?engine=` reads `docs/paper-trades/<eng>/<date>_verdicts.json` and returns `verdicts[]` with `symbol`, `plan`, `verdict`, `reasons[]`. Market's "why we skipped it" column.
3. **Data-link health route.** New `GET /api/health/datalinks` calls `v4/kite_data.health()` and `/api/indices` per-index `source`/`stale`, returns one row per link with ok/stale/down and last error.
4. **Shadows route.** New `GET /api/shadows?date=` reads `docs/research/shadows/armband/<date>.json` and `/api/lab` deltas, returns per-experiment delta vs live and the day counter (days since the pre-registered start on 2026-09-08 out of 10).
5. **Live P&L fix.** `/api/live-trades` and `/api/desk` compute `unrealized_pnl` from `/api/positions-live` marks (`(mark − entry) × qty × side`) instead of reading a key the engine never writes. Missing mark renders "price unavailable", never ₹0.

Also in Phase 1: `duration` on `recent_exits[]` and `closed[]` derived from `entry_time`/`exit_time`; `trained_at` on `/api/model` from the model file mtime.

### Phase 2: the four pages, bound to Phase 1 plus existing routes.
New aggregating routes: `/api/ready`, `/api/engine/<name>/start`, news-impact join on `/api/news`, `date` on the chart route, exit-reason aggregation for Review.

### Phase 3: engine fields and new sources (separate spec each; listed so the pages are designed for them).
Trend-at-entry, loss-cause taxonomy, candle-shape-at-entry stamped on positions and closed trades; breadth; FII/DII; sector moves; next-scan time; launch-fired and disk checks; learning repeat detection; learnings-fed nightly retrain with a launchd plist.

## Components
Jinja includes under `templates/panels/`, one per panel, each with: a heading, a skeleton, a failure line, an empty state with a one-line explanation. Panel JS lives in `static/panels/<panel>.js`, one fetch per panel, no panel blocks another (the rule from `desk.css`). Shared: `_operator_nav.html` (four tabs, Legacy menu, Client app link), `desk.css` unchanged plus a `panels.css` for the new banner, pod, check-row and chart styles. The trade chart is inline SVG rendered from `candles[]`, no chart library.

## Routing
`/ready`, `/market`, `/book`, `/review`. `/` redirects by IST clock: before 09:15 → `/ready`, 09:15 to 15:30 → `/book`, after → `/review`. Old routes keep working and gain the Legacy nav. Legacy menu lists: Desk (old `/`, moved to `/desk-legacy`), Live, Lab, Decisions, Portfolio, Dashboard, Team, Floor, Fleet, Classic.

## Error handling
A failed fetch shows that panel's failure line and nothing else changes. A 401 or 5xx on `/api/ready` shows the verdict banner as amber "Could not run checks" with the error. Past-date Review with no artifacts shows "No session recorded for <date>". Every number has a unit and a source timestamp on hover.

## Testing
- Phase 1 routes: pytest per route with a fixture day (`docs/paper-trades/v5/2026-09-10*.json`) asserting the new fields, the verdicts shape, and that `unrealized_pnl` is computed not read.
- Existing `tests/` stay green.
- Playwright at 1366×900 on all four pages: nav present with current tab marked, no horizontal scroll, no console errors, every panel either has data or shows its failure/empty line, "Not yet" appears where an engine field is missing, no green/red on direction or regime chips.
- Flask restart after template edits (Jinja cache).

## Out of scope
The dashboard composer for end users; the client tier; engine changes (Phase 3 specs); Kite live trading; the :5051 mobile server; `/classic`.
