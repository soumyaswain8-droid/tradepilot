# Operator redesign: what exists, what to wire, what is new

Date: 2026-09-11. Companion to the approved canvas (`tradepilot-operator-terminal.html`).
Sources verified by reading `prototype/app.py` routes, engine artifacts under `docs/paper-trades/`, and scripts.

## Legend
- **Reuse**: a Flask route already returns it. Bind the new panel to it.
- **Wire**: the data exists on disk or in a Python function, but no route serves it. Add a route, no engine change.
- **New**: the engine does not record it. Engine work, then a route.

## Page 1: Ready

| Field | Status | Source |
|---|---|---|
| Engines running, which is down | Reuse | `/api/system-health` events `ENGINE_DOWN` (real pgrep); `/api/engine-status` |
| Last log line per engine | Reuse | `/api/recent-scans` |
| Yesterday fleet net + trades | Reuse | `/api/desk` `fleet.net`, `fleet.trades` |
| Per-engine capital | Reuse | `/api/engine-status` `engines[].capital` |
| Regime picked | Reuse | engine `<date>.json` `regime`; also in `/api/live-trades` |
| NaN count | Wire | `/api/system-health` `DATA_NAN` event carries it as text; expose as a number |
| ML model last trained | Wire | mtime of `prototype/models/xgb_v3.pkl`; add `trained_at` to `model_meta_v3.json` |
| Data link NSE / yfinance / Kite | Wire | `v4/kite_data.py::health()` exists, not routed; `/api/indices` has per-index `source`/`stale` |
| Shadow experiment deltas | Wire | `docs/research/shadows/armband/<date>.json`, file only; `/api/lab` has `experiments[].delta` |
| Launch fired on time | New | launchd writes only to logs; record scheduled vs actual fire time |
| Price feed last tick time | New | only an indirect `STALE_SCAN` event today |
| Cache cleared | New | in-process caches, nothing exposed |
| Disk free | New | `scripts/disk-watch.py` exists; `/api/desk` `guards.disk_gate` is a static string |
| Shadow day counter | New | `/api/desk` `experiment` counts trades, not days |

## Page 2: Market

| Field | Status | Source |
|---|---|---|
| News list | Reuse | `/api/news` items with `catalyst`, `theme`, `symbols`, `region` |
| Index quotes + sparkline | Reuse | `/api/indices`, `/api/index/<x>/intraday`, `/api/stock/<sym>/spark` |
| Top movers we are not in | Reuse | `/api/missed-opportunities` (`top_movers[]`, `summary.on_table`) |
| Regime | Reuse | engine `<date>.json` |
| News impact tag | Wire | `docs/sarathi/knowledge/news_impact.jsonl` from `scripts/news-impact.py`, not joined to `/api/news` |
| Reason we skipped a stock | Wire | `docs/paper-trades/<eng>/<date>_verdicts.json`: `verdict` approved/rejected + `reasons[]` (position size, pool cash, kill switch, score near threshold). No route reads it. Does not cover ASM, not-in-universe, regime-blocks-side |
| Sector moves | Partial | keyword sector labels only; no sector index % |
| Breadth (advance/decline) | New | nothing in app.py |
| FII / DII numbers | New | only a news keyword bucket |
| Regime detection time | New | only `started_at`, `last_rescore_time` stored |

## Page 3: Book

| Field | Status | Source |
|---|---|---|
| Net after costs, per-engine trades/pnl/win% | Reuse | `/api/desk` `fleet.net`, `engines[]` |
| Open positions: entry, qty, side, pool, entry time | Reuse | `/api/desk` `open_positions[]` |
| Exits feed with reason | Reuse | `/api/desk` `recent_exits[]` |
| Engine alive, last scan | Reuse | `/api/system-health`; `<date>.json` `last_rescore_time` |
| Live price and unrealised P&L | Wire | `/api/positions-live` has marks; `/api/live-trades` reads a key that does not exist (`unrealized_pnl`), renders null today. Fix the join |
| Distance to stop | Wire | `positions_active.json` stores `sl_price`, `target_price`, `peak_price`, `trailing_activated`; `/api/desk` drops them. Pass them through |
| Time in trade, exit duration | Wire | derive from `entry_time` / `exit_time` |
| Loss if every stop hits | Wire | sum of (`sl_price` − mark) × `qty` once stops are exposed |
| Next scan time | New | no schedule field anywhere |
| Trend at entry | New | positions store `score`, `direction`, `reasons[]`; `last_signals[]` has `trend` but only for the latest rescore, not at entry. Engine must stamp it on the position |

## Page 4: Review

| Field | Status | Source |
|---|---|---|
| Per-engine net + hit | Reuse | `/api/desk` `engines[]` |
| Trade list with times, net, cost, exit reason | Reuse | `closed[]` via `/api/live-trades`, `/api/tradelab/trades/<date>` |
| Per-trade 5-minute candles | Reuse | `/api/stock/<sym>/chart?range=1d` returns 5-min OHLC; `scripts/eod-replay-candles.py` already replays per trade |
| Scorer reasons at entry | Reuse | `closed[].reasons[]`, `closed[].score` |
| Learnings recorded today | Reuse | `learnings/daily/<date>.yaml` `insights[]`, `per_engine` |
| ML last trained | Wire | model file mtime |
| Losses grouped by cause | Partial | `closed[].reason` is the raw exit reason; no cause taxonomy. Aggregate what exists, add the taxonomy with trend-at-entry |
| Candle shape at entry | New | no body/wick field anywhere |
| New vs repeat learning | New | no dedup flag in the YAML |
| Learnings consumed by ML | New | `scripts/retrain-ml.sh` trains on yfinance OHLCV only. Learnings are never an input today |
| Next retrain | New | retrain is manual; no launchd plist |

## Existing templates

| Template | Decision | What carries over |
|---|---|---|
| `desk.html` | Lift panels | Exit Feed, Closed Trades, Guards, Size Experiment. Already bound to `/api/desk` |
| `decisions.html` | Lift copy | "This week we are testing", "Closed, measured and killed", "Standing rules" become Review's experiment ledger, fed by data instead of typed numbers |
| `dashboard.html` | Lift 3 panels, retire rest | index tiles, AI scan panel, positions panel. The other ~2,800 lines are legacy consumer UI |
| `fleet.html` | Lift strip | compact per-engine pod row for Book |
| `lab.html` | Lift cards | challenger-vs-baseline delta cards for Ready's shadow block |
| `live.html` | Retire | duplicates desk + recent-scans, no unique panel |
| `team.html`, `floor.html` | Retire | agent roster and escalation stream, no source in the four pages |
| `portfolio.html` | Retire from operator nav | owner-facing book; candidate for the client tier |
| `index.html` (`/classic`) | Untouched | frozen, under Legacy |

## Honest findings for the engine side
1. The ML retrain script never reads learnings. The "learn every day" loop Soumya wants does not exist yet; the Review page's ML panel would show that plainly.
2. Positions already carry stop and target prices; the desk API throws them away. Cheapest high-value wire in the whole list.
3. The verdicts file is the missing "why we skipped it" and already exists per engine per day; it needs a route and three more reason types.
