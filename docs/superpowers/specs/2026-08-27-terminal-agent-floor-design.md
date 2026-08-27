# Terminal — Agent Floor and Detail Restoration

**Design spec · 2026-08-27 · Project A of three**

## Why this exists

The terminal shell at `/` was built on 2026-08-11 to replace the 7,173-line
single-template dashboard at `/classic`. The comment in `app.py:86` states the
intent plainly: *"the old 7,173-line single-template dashboard stays reachable at
/classic until the terminal has absorbed every view."*

Absorption stopped after two tabs. The terminal has **Desk** and **Market**;
everything else is either an `↗` link out or stranded on one of six orphaned
page templates. Meanwhile the Agent Floor — the two screens that show what the
agents are actually doing — has no place in the navigation at all. `/floor` is
not even listed in `pageswitch.js`.

This spec covers finishing the absorption and giving the Agent Floor a home.

## Scope boundary

This is one of three sub-projects. It is deliberately the only one that touches
no data model and no authentication.

| | Sub-project | Status | Depends on |
|:--|:--|:--|:--|
| **A** | **Terminal — Agent Floor and detail restoration** | **this spec** | nothing |
| B | Accounts — identity and per-user state | not started | nothing |
| C | Client dashboard — `/classic` as a Groww-clean SaaS surface | not started | B |

Out of scope here: authentication, user accounts, per-user portfolios, and the
client-facing redesign of `/classic`. Project A only *removes* operator views
from `index.html`; it does not restyle what remains.

## Decisions taken

| Decision | Choice | Rationale |
|:--|:--|:--|
| Audience split | Two separate surfaces | The terminal is an operator cockpit; `/classic` becomes a client product. They may diverge freely in design language and data exposure. |
| Agent Floor shape | Section with two sub-tabs | Quant Desk and Live Floor keep their current layouts, re-homed under one roof. |
| Isolation for those two | Iframe panes, lazy-mounted | Both pages assume they own the document. The browser gives perfect style isolation for free. |
| Isolation for everything else | Real extraction into the terminal | Extraction doubles as the prep work project C needs. |
| Nav shape | 5 sections, max 3 sub-tabs each | Ten flat destinations is too many for one row. |
| `pageswitch.js` | Retired from both surfaces | Superseded by the terminal's own nav, and it currently leaks operator links onto the client dashboard. |

## The style-isolation problem

`floor.html` and `team.html` are self-contained documents that assume they own
the browser. `floor.html` sets `body{overflow:hidden}`, paints CRT scanlines via
`body::after`, and sizes a `<canvas>` radar to the viewport. `team.html` styles
bare `header`, `main`, `section` and `h2` selectors. Dropped into the terminal's
DOM, those rules escape into every other view.

The three files also define near-miss palettes under identical variable names:

| Token | `desk.css` | `team.html` | `floor.html` |
|:--|:--|:--|:--|
| `--bg` | `#0a0d13` | `#0b0d12` | `--void #04080f` |
| `--panel` | `#10141c` | `#11141b` | `#0d1826` |
| `--green` | `#16c784` | `#10b981` | `--lime #5ddc7a` |
| `--amber` | `#f0a93b` | `--yellow #f59e0b` | `#ffb020` |

`--bg`, `--panel` and `--green` collide by name with different values.
Concatenating these stylesheets means last-one-wins silently restyles whichever
view loaded first.

Iframes remove this class of bug entirely for the two heaviest live screens. The
remaining ported views are re-scoped explicitly under their own `#view-X` root.

## Information architecture

```
┌─ TRADEPILOT TERMINAL ──────── NIFTY ····  SENSEX ····  ● OPEN  18:41:50 ─┐
│                                                                          │
│   Desk      Market      Agent Floor      Research      Portfolio         │
│  ─────────────────────────────────────────────────────────────────────   │
│                                                                          │
│  Desk         →  Overview · Fleet health                                 │
│  Market       →  India · F&O · US                                        │
│  Agent Floor  →  Quant Desk · Live Floor          ◄── iframes            │
│  Research     →  Trade Lab · A/B Lab · Decisions                         │
│  Portfolio    →  (flat, no sub-tabs)                                     │
│                                                                          │
│                                        Ask ⌘K  ◄── drawer, not a tab     │
└──────────────────────────────────────────────────────────────────────────┘
```

| Section | Sub-tabs | Source | Mechanism |
|:--|:--|:--|:--|
| Desk | Overview · Fleet health | existing; `/fleet`, `/api/system-health`, `/api/rust-status`, `/api/engine-status` | port |
| Market | India · F&O · US | existing; `loadFnoStocks()`, `loadUSMarket()`, `loadUSEngine()` | extract from `index.html` |
| Agent Floor | Quant Desk · Live Floor | `/team`, `/floor` | iframe, lazy-mount |
| Research | Trade Lab · A/B Lab · Decisions | `loadTradeLab()`, `/api/engine-arena`, `/lab`, `/decisions` | extract + port |
| Portfolio | — | `/portfolio`, `/api/catalogue/*`, `/api/portfolio/trades` | port |
| Ask | — | `/api/ask`, `/api/bots/geopolitical`, `/api/bots/market-pulse` | drawer overlay |

**Ask is a drawer, not a tab.** It is a query interface over everything else —
it should be available *while* looking at the Trade Lab, not a place you navigate
away to. `desk.html` already has a working drawer plus overlay pattern for the
stock detail panel; Ask reuses that mechanism.

Ask opens on `Cmd/Ctrl+K` and closes on `Escape`. `Escape` is already bound to
`closeDrawer()` in `desk.js`; that handler must close whichever drawer is open
rather than assuming the stock drawer.

## Routing

`switchTab(name)` becomes two-level. The hash format is `#section/sub`.

Existing bookmarks must not break. Today's deep links are `#market`,
`#market/RELIANCE` and `#market/TITAN/5y`. Making Market a section with sub-tabs
would make segment 2 ambiguous, so the parser falls back: **if segment 2 is not a
known sub-tab id for that section, treat it as a symbol against the section's
default sub-tab.**

Every section declares a **default sub-tab**. A bare `#section` resolves to it,
and an unrecognised sub falls through to it rather than rendering nothing.
Sections with no sub-tabs (Portfolio) take no second segment.

| Section | Default sub-tab |
|:--|:--|
| Desk | Overview |
| Market | India |
| Agent Floor | Quant Desk |
| Research | Trade Lab |
| Portfolio | *(flat — no sub-tabs)* |

```
#desk                      → Desk › Overview            (default)
#agents                    → Agent Floor › Quant Desk   (default)
#agents/floor              → Agent Floor › Live Floor
#market/fno                → Market › F&O
#portfolio                 → Portfolio                  (flat)
#market/india/TITAN/5y     → Market › India, drawer open, 5y range
#market/TITAN/5y           → legacy form, still resolves (TITAN ∉ subs → symbol)
#market/nonsense           → Market › India             (unknown sub → default)
```

Folded page routes become redirects rather than deletions, so existing bookmarks
and any scripts pointing at them keep working:

| Old route | Redirects to |
|:--|:--|
| `/lab` | `/#research/ab` |
| `/decisions` | `/#research/decisions` |
| `/portfolio` | `/#portfolio` |
| `/fleet` | `/#desk/fleet` |

`/floor` and `/team` remain directly reachable as full pages. They are the
iframe targets, and keeping them standalone means a broken terminal never costs
visibility into the live floor.

## Lifecycle registry

`desk.js` already contains every idiom this refactor needs. The design
generalises them rather than inventing new ones:

- lazy-load-on-first-show — `if (name === "market" && !mktRows.length) loadMarket();`
- poll-only-when-visible — `if ($("view-market").classList.contains("on")) loadMarket();`
- background throttle — `if (document.hidden) return;`
- hash deep links — `#market/TITAN/5y`

Each view registers a contract; the router owns when each hook fires:

```js
{ id: "tradelab", mount(), refresh(), unmount(), pollMs: 60000 }
```

| Hook | When |
|:--|:--|
| `mount()` | first time the view becomes visible |
| `refresh()` | on tick, only while visible and `!document.hidden` |
| `unmount()` | on hide — iframe panes only |

## Iframe panes

```js
mount()   → frame.src = "/floor?embed=1"
unmount() → frame.src = "about:blank"
```

Setting `about:blank` on hide stops the one-second poll dead rather than leaving
it running behind a hidden tab. Two live pollers left running would otherwise
issue ~3,600 requests an hour against `/api/floor/live` and `/api/team/status`
for a screen nobody is looking at.

This requires **two small additive edits**, one per file. `floor.html` and
`team.html` read `?embed=1` and, when present:

1. hide their own brand header bar (the terminal supplies the chrome)
2. skip loading `pageswitch.js`

No restructuring, no CSS changes, no change to their polling or rendering logic.

## Extraction recipe

Applied identically to Trade Lab, US Market, F&O and Ask. Step 4 is what makes
project C tractable.

| Step | Action | Serves |
|:--|:--|:--|
| 1 | Move `<section class="view" id="view-X">` markup out of `index.html` into a terminal partial | A |
| 2 | Move its named functions out of the 3,341-line inline block into `static/desk/view-X.js` | A |
| 3 | Move its CSS rules into `desk.css`, scoped under `#view-X` | A |
| 4 | **Delete the view from `index.html`** | **C** |
| 5 | Add the route and DOM smoke test before moving to the next view | both |

The inline JS is one 3,341-line `<script>` block spanning lines 3831–7022, but it
has discrete named entry points — `loadTradeLab()`, `loadUSMarket()`,
`loadUSEngine()`, `loadFnoStocks(type)` — so each view is separable.

`index.html` also loads Chart.js from a CDN at line 2572. Any extracted view that
depends on it must either be ported to the terminal's existing canvas drawing
helpers or have the dependency made explicit — it must not silently rely on a
global that only exists on `/classic`.

## Module structure

Ten views would push `desk.js` past 2,000 lines. Splitting per view keeps each
file small enough to hold in context, which materially improves edit reliability.

```
prototype/static/desk/
  router.js        nav, two-level hash routing, lifecycle registry
  panes.js         iframe mount/unmount for the Agent Floor
  view-desk.js
  view-fleet.js
  view-market.js
  view-fno.js
  view-us.js
  view-tradelab.js
  view-ab.js
  view-decisions.js
  view-portfolio.js
  view-ask.js
```

`desk.html` carries a standing rule worth preserving verbatim: *"JS is a separate
file BY RULE: on 2026-08-03 a tab shipped blank because its logic was appended
inside a `<script src>` tag, whose inline content the browser silently
discards."* Every module is loaded by its own tag with no inline content.

## Error handling

Every `mount()` and `refresh()` is wrapped. A failing view renders an inline
error card inside its own pane, showing the endpoint that failed. It never blanks
the tab, never throws past the router, and never prevents other views from
mounting.

This mirrors the discipline already applied to `/api/floor/live`, which is
explicitly written never to 500 into the console's face because it is polled once
a second. One dead endpoint must not take the cockpit down.

## Testing

`tests/` holds 14 files, all engine and strategy logic. There are **no route
tests and no `test_client` usage** — the web layer is entirely uncovered. Moving
ten views with no coverage invites a repeat of the 2026-08-03 blank-tab incident.

New file `tests/test_web_routes.py`, using the Flask test client:

| # | Assertion |
|:--|:--|
| 1 | Every page route returns 200 and contains a route-specific sentinel string |
| 2 | Every registered destination — ported view *and* iframe pane — has its section id present in the rendered terminal |
| 3 | Every **ported** view has a corresponding `static/desk/view-X.js` referenced by a `<script src>` — the direct regression test for the blank-tab bug. Iframe panes are exempt: they carry no view module and are served by `panes.js` |
| 4 | `?embed=1` on `/floor` and `/team` suppresses `pageswitch.js` and the brand header |
| 5 | `/classic` no longer references `pageswitch.js` or any extracted operator view id |
| 6 | Each folded route returns a redirect to its terminal hash |

Tests land per view as part of extraction step 5, not in a batch at the end.

## Files touched

| File | Change |
|:--|:--|
| `prototype/templates/desk.html` | 5 sections, sub-tab bars, ported view markup |
| `prototype/static/desk.js` | split into `prototype/static/desk/*.js` |
| `prototype/static/desk.css` | scoped rules for ported views |
| `prototype/templates/floor.html` | `?embed=1` handling (~3 lines) |
| `prototype/templates/team.html` | `?embed=1` handling (~3 lines) |
| `prototype/templates/index.html` | delete 4 operator views; drop `pageswitch.js` |
| `prototype/templates/lab.html` | absorbed; route becomes a redirect |
| `prototype/templates/decisions.html` | absorbed; route becomes a redirect |
| `prototype/templates/portfolio.html` | absorbed; route becomes a redirect |
| `prototype/templates/fleet.html` | absorbed; route becomes a redirect |
| `prototype/app.py` | `?embed` param, redirects for folded routes |
| `tests/test_web_routes.py` | new — first web-layer coverage |
| `prototype/static/pageswitch.js` | retired |

## Risks

| Risk | Mitigation |
|:--|:--|
| Large refactor of a cockpit in daily use | Route tests land per view during extraction, not at the end. Each view is verified as it moves. |
| A ported view silently depends on a `/classic` global (e.g. Chart.js) | Extraction step 3 makes every dependency explicit; test 3 asserts the module is actually loaded. |
| Two live pollers running behind hidden tabs | `unmount()` sets `about:blank`, killing the frame's timers outright. |
| Deleting views from `index.html` breaks `/classic` | `ind-shell.js` groups tabs by id; its `markets`/`lab` groups must be updated in the same commit. Test 5 covers the leftovers. |
| Breaking existing deep links | Hash parser falls back to symbol interpretation; folded routes redirect rather than 404. |

## Deferred

- Unifying the three palettes into one token set. Iframes make this unnecessary
  for now; it becomes worthwhile only if the Agent Floor is later ported in.
- Restyling `/classic`. That is project C and must not be started here.
- Any authentication or per-user state. That is project B.
