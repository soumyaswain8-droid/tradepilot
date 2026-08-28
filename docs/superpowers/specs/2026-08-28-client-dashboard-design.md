# Client Dashboard — /app

**Design spec · 2026-08-28 · Project C of three**

## Why this exists

TradePilot's operator surface is the terminal at `/`. `/classic` is a
7,173-line dashboard carrying fourteen views that mix operator tooling with
client-facing browsing — it serves neither audience well.

This spec designs a separate client-facing product at `/app`: a paying customer
sees today's calls, their own book, and the track record that justifies the
subscription. It shares data with the operator surface and nothing else — not
its design language, not its vocabulary, not its navigation.

## Scope boundary

| | Sub-project | Status | Depends on |
|:--|:--|:--|:--|
| A | Terminal — Agent Floor and detail restoration | **shipped** (merged `66ebf1f`) | — |
| B | Accounts — identity and per-user state | deferred, not designed | — |
| **C0** | **Calls capture pipeline** | **this spec, Phase 0 — ships first** | — |
| **C** | **Client dashboard `/app`** | **this spec** | C0; a stubbed `current_user()` stands in for B |

Out of scope: authentication (B), Kite broker connection (designed-for, not
built), billing, notifications, and the operator terminal.

## The ordering decision, and why C0 ships alone

Track record value is purely a function of elapsed time. Nothing currently
persists what was published — `/api/picks` computes live and stores nothing, so
every day the capture job is not running is a day of proof that cannot be
recovered without the retroactive labelling this design deliberately rejects.

The capture pipeline has no dependency on the dashboard: no auth, no screens, no
client. It is therefore split out as **Phase 0** and ships on its own, ahead of
any UI work. By the time `/app` is built the track record page has real data
instead of eleven calls.

## Decisions taken

| Decision | Choice | Rationale |
|:--|:--|:--|
| Product shape | Calls above, book below, on one home scroll | The reason they pay, above the proof it works |
| The book | Broker-linked via Kite as the **end state**; manual position log in v1 | One schema, two ingest sources — Kite becomes an adapter, not a rewrite |
| Build shape | Greenfield at `/app`; `/classic` untouched until complete | No fighting 7,173 lines of accumulated assumptions |
| Visual direction | Light, white cards, indigo accent — the Groww language | Indian retail already trusts it; reads as regulated fintech |
| Shell | Sidebar ≥900px, bottom tab bar below | Both audiences; cost is one duplicated component |
| What is a "call" | Only what the publish job persisted | A single writer is what makes the record defensible |
| Auth boundary | Calls and record public; book and account gated | Public half is the acquisition surface and the proof |
| Accounts (B) | Deferred; C builds against a stubbed `current_user()` | B's requirements are better learned from a working product |

## Audience and content rules

`/app` is for a paying customer, not an operator. These are binding:

- **No engine names, no strategy internals, no agent vocabulary.** `v5_size`,
  `alpha-hunter`, "regime flip" are operator language and must never appear.
- **A call states what and why in plain terms** — "reclaimed VWAP on 2.1×
  volume" — never which engine produced it.
- **Every position carries provenance.** `call_id` present renders "from a
  TradePilot call"; absent renders "your own idea". The P&L split between those
  two is the most valuable number in the product and is free once the column
  exists.
- **Never overstate the record.** A hit rate over a small sample is the easiest
  way to mislead a customer without lying. The page shows the count and the
  threshold, not just the percentage.

## Visual direction and shell

Light ground, white cards, indigo accent (`#4f46e5`), generous spacing.
Continuous with `brand/letterhead`. Note that `landing.html` is dark navy with
an amber accent — a prospect goes landing → signup → app in one sitting, so
either the landing page is relit later or the seam is accepted knowingly. This
spec does not change `landing.html`.

**One breakpoint at 900px.** No tablet-specific third layout — the middle
layout is the one that gets tested least and breaks quietest.

Three reflow points, and they are the entire cost of supporting both:

| Reflow | Above 900px | Below | Cost |
|:--|:--|:--|:--|
| KPI row | Two cards side by side | Stacked | CSS grid change; no second component |
| Calls list | Five-column table with header | Stacked card, reason on line two | **The one component written twice** |
| Navigation | Persistent sidebar | Bottom tab bar | Two small templates over one shared route list |

Every other screen is single-column at both sizes and needs no fork.

The route list has a single definition, following the pattern proven in the
terminal's `TPRouter.SECTIONS`: a link the router does not know about cannot
exist.

## Data model

**Target: SQLite.** The application's only database is
`prototype/tradepilot_analytics.db`, accessed through the standard library's
`sqlite3` in `prototype/analytics.py`. There is no ORM and no Postgres — the
`psycopg2` in `scripts/push-to-devpilot.py` talks to the separate DevPilot
database and is unrelated. Using stdlib `sqlite3` keeps the standing
no-new-dependencies constraint intact.

Types are therefore SQLite's: timestamps are `TEXT` in ISO-8601 (matching how
the rest of this codebase already stores times in JSON), money and quantities
are `REAL`. `calls` is declared first because `positions` references it, and
`PRAGMA foreign_keys = ON` must be set per connection — SQLite does not enforce
foreign keys by default.

```sql
PRAGMA foreign_keys = ON;

-- What was published, when, at what price. Written ONLY by the publish job.
CREATE TABLE IF NOT EXISTS calls (
  id             TEXT PRIMARY KEY,
  symbol         TEXT NOT NULL,
  side           TEXT NOT NULL,                -- 'BUY' | 'SELL'
  published_at   TEXT NOT NULL,                -- ISO-8601
  price_at_call  REAL NOT NULL,
  score          REAL,
  signal         TEXT,                         -- plain-English reason
  horizon        TEXT,                         -- 'intraday' | 'swing' | 'investment'
  target         REAL,
  stop           REAL,
  outcome_price  REAL,                         -- filled by the resolver
  outcome_at     TEXT,
  outcome        TEXT NOT NULL DEFAULT 'open'  -- 'hit' | 'miss' | 'open'
);
CREATE UNIQUE INDEX IF NOT EXISTS ux_calls_symbol_day
  ON calls (symbol, date(published_at));       -- enforces publish-job idempotency

-- One row per holding. Built for manual entry now, with `source` and
-- `broker_ref` so a Kite sync becomes a second writer rather than a rewrite.
CREATE TABLE IF NOT EXISTS positions (
  id          TEXT PRIMARY KEY,
  user_id     TEXT NOT NULL,
  symbol      TEXT NOT NULL,
  qty         REAL NOT NULL,
  avg_price   REAL NOT NULL,
  opened_at   TEXT NOT NULL,                   -- ISO-8601
  closed_at   TEXT,
  exit_price  REAL,
  source      TEXT NOT NULL DEFAULT 'manual',  -- 'manual' | 'kite'
  broker_ref  TEXT,                            -- Kite position id; NULL for manual
  call_id     TEXT REFERENCES calls(id)        -- nullable: clients log their own ideas
);
CREATE INDEX IF NOT EXISTS ix_positions_user ON positions (user_id, closed_at);
```

`call_id` is nullable by design. Clients will log trades that were never called,
and being honest about that split is worth more than pretending otherwise.

`positions.user_id` is the only thing this design assumes about project B.

## Phase 0 — capture and resolve

Two jobs. The publish job is the **only** writer of `calls`; if calls could be
written from anywhere, "we called this" becomes unfalsifiable.

```
09:20 IST    publish job    /api/picks  ->  INSERT INTO calls (..., published_at)
EOD + N      resolver       fill outcome_price, outcome_at, outcome
```

Requirements:

- The publish job is idempotent per `(symbol, date(published_at))`, enforced by
  the unique index `ux_calls_symbol_day` rather than by convention. Re-running it
  must not duplicate a day's calls, and the schema makes that impossible rather
  than merely intended.
- The resolver only fills rows whose horizon has elapsed. A call still within
  its horizon has `outcome = 'open'` and must never be counted in a hit rate.
- Neither job depends on `/app` existing. Both must run standalone.
- Failure of either job is logged and retried, never silently swallowed — a
  missing day in the record is worse than a visible gap.

## The five screens

| Screen | Populated | Empty / first-run |
|:--|:--|:--|
| Home | Value + today's P&L, today's calls, positions preview, hit-rate tile | **Three distinct states, not two.** *Logged out*: calls and hit-rate render; the book half is replaced by a sign-in prompt — never an empty value card implying zero. *Logged in, no positions*: value card becomes "Log your first trade". *Logged in with positions*: full render. **Never a blank page in any state** |
| Calls | Today's published calls, newest first, score, signal, price at call | Market closed or none fired — the common case outside market hours. Shows the last session's calls with an explicit "from Thursday's close" stamp |
| Call detail | Score breakdown, the signal that fired, entry/target/stop, price since | Live calls must not imply an outcome that has not occurred |
| Book | Positions marked to market, split by provenance | The log-a-trade form **is** the screen, not a modal behind a button |
| Track record | Hit rate, sample size, since-date, distribution, resolved calls | States the count and the threshold plainly: *"18 calls resolved since 28 Aug. We show hit rate from 100."* |

Empty states are not edge cases here — they are the entire first-run
experience.

## API surface

Every client endpoint lives under `/api/app/*`. This is the load-bearing
decision: the app has roughly seventy unprotected routes, and a shared prefix
means project B protects **one prefix with one `before_request` hook** rather
than auditing route by route, where a single missed decorator is a data leak.

```
PUBLIC
  GET    /api/app/calls              today's published calls
  GET    /api/app/calls/<id>         one call, why it fired, price since
  GET    /api/app/record             hit rate, n, since-date, distribution

GATED (requires current_user())
  GET    /api/app/positions          the book, marked to market
  POST   /api/app/positions          log a trade
  PATCH  /api/app/positions/<id>     edit or close
  DELETE /api/app/positions/<id>     remove a mistaken entry
  GET    /api/app/me                 account and plan          <- project B owns
```

Reused unchanged: `/api/indices` (market header),
`/api/stock/<sym>/chart` and `/spark` (call detail),
`/api/stock/<sym>/info` (metadata), `/api/scores` (mark-to-market prices).

Two deliberate exclusions:

- **`/api/paper/*` is not reused.** It is a global in-process dict, it is
  operator-facing, and `positions` replaces it for clients. Keeping both alive
  would create two competing books.
- **`/api/picks` is never exposed to clients.** It computes live, so serving it
  directly would show a "call" that was never published and never recorded.
  `/api/app/calls` reads the `calls` table only. That distinction is the whole
  difference between a defensible track record and an undefensible one.

## The seam with project B

C assumes exactly three things:

1. `current_user()` returns a user id or `None`
2. `/api/app/positions` and `/api/app/me` are protected; `/api/app/calls` and
   `/api/app/record` are not
3. `positions.user_id` is a stable identifier

Until B exists, `current_user()` is a stub returning a fixed demo id. Swapping
it is a one-function change. Everything else about B — signup, sessions,
password handling, plans, billing — C neither knows nor cares about.

## Error handling

Follows the discipline already proven in this codebase: `/api/floor/live` is
written never to 500 into a polling console's face, and the terminal's router
wraps every view hook so one failure degrades one card.

- A stale price feed degrades the mark-to-market card to a "prices as of…" chip.
  It must never blank the positions list — a client's own book is the last thing
  that should disappear because an upstream quote went stale.
- A failing section renders an inline message inside its own card and never
  prevents a sibling from rendering.
- Client-facing errors are sanitised. No SQL, no table names, no internal paths.

## Testing

| Layer | How |
|:--|:--|
| Eight endpoints | Flask `test_client` — response shapes, empty states, error paths |
| **Auth boundary** | **Enumeration test**: every route under `/api/app/` must appear in exactly one of the public or gated lists. A new endpoint in neither fails the suite |
| `calls` schema | Migration idempotency — runs twice without error |
| Publish job | Idempotent per `(symbol, date)`; re-run adds no duplicates |
| Resolver | Unit tests with fixtures; a call inside its horizon stays `open` and is excluded from hit-rate maths |
| Screens | Manual checklist in a durable tracked doc (`docs/APP_MANUAL_CHECKS.md`), following the precedent of `docs/TERMINAL_MANUAL_CHECKS.md`. No jsdom, per the standing no-new-dependencies constraint. The checklist must cover all three Home states above |

The enumeration test is what makes the prefix decision pay off: "did we forget
to protect something?" becomes a question the suite answers, not a review.

## Launch gate

**Before `/app` is made publicly reachable from the internet**, the SEBI
Research Analyst / Investment Adviser position must be checked. Publishing
buy/sell recommendations publicly in India sits closer to that regime than
showing them to authenticated subscribers does, and the public-calls decision
increases that exposure. This is recorded as a deploy gate, not a design change.
Nothing in this spec is blocked by it while the app remains local.

## Risks

| Risk | Mitigation |
|:--|:--|
| Track record empty at launch | C0 ships first and accrues from day one |
| Publish job silently stops; record gains a hole | Failures logged and retried; a visible gap beats a silent one |
| A client mistakes a live call for a resolved one | Call detail renders live and resolved states distinctly; resolver never marks a call inside its horizon |
| Small-sample hit rate reads as a claim | Threshold stated on the page; count always shown beside the percentage |
| Auth boundary rots as endpoints are added | Enumeration test fails on any unclassified `/api/app/` route |
| `/classic` and `/app` diverge into two maintained products | `/classic` redirects to `/app` once the five screens are complete |

## Deferred

- **Kite broker sync.** Designed for — `positions.source` and `broker_ref`
  exist — but not built. Requires per-user encrypted token storage, a publicly
  reachable callback, and confirmation of Zerodha's multi-user terms. The
  current integration writes a single token to `.env` and is single-user by
  construction.
- **Relighting `landing.html`** to match `/app`, or accepting the seam.
- **Delayed public calls** for non-members. The boundary is designed; the delay
  window is not built.
- **Notifications and alerts.** Out of scope for v1.
