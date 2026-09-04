# Dashboard Redesign — one system, two skins

Date: 2026-09-05. Status: approved by Soumya (canvas reviewed). Canvas: https://claude.ai/code/artifact/e5770914-09a3-495f-8034-d4bebb6f0ca7 · working files `docs/design/2026-09-05-redesign/*.dc.html`.

## Why
Launch needs one product feel. Today three visual systems coexist (light indigo client, dark Terminal, Stripe-style legacy Desk, sci-fi /live, navy landing). A prospect goes landing → sign-in → /app in one sitting and sees three products.

## Decisions
- **Audience tiers.** Client tier = strangers and friends: landing, login, signup, set-password, /app. Operator tier = Soumya: Terminal (`/`), /live, /lab, /team, /decisions, /portfolio, /dashboard. `/classic` (index.html, 7k lines) is frozen and untouched.
- **Client skin (light, Groww-inspired, original palette).** Ground `#FFFFFF`; cards white, hairline `#EAECF0`, radius 16px; tint `#F6F8FA`. Action + gain green `#0FA36B` (hover `#0B8F5F`), loss `#E04A3C`, open-call indigo `#4A55C7`, ink `#1B1F2A`, muted `#6C7280`, faint `#9AA0AE`. Text: Plus Jakarta Sans (Google Fonts) with system fallback; every number in JetBrains Mono with `font-variant-numeric: tabular-nums`. Controls 44px tall; chips 24px pills. Desktop: 68px top bar with logo, four tabs (Home, Calls, Book, Record), search box, market-state dot, avatar. Phone (<900px): bottom tab bar with stroke icons, 52px targets. One breakpoint at 900px, unchanged from the client spec.
- **Operator skin (dark, existing Terminal tokens, unchanged).** `desk.css` tokens are the source of truth: bg `#0a0d13`, panel `#10141c`, line `#1c2330`, ink `#e6ebf2`, green `#16c784`, red `#ea3943`, amber `#f0a93b`, accent `#6366f1`, mono tabular numbers, radius 6px. Green/red mean P&L only.
- **Operator navigation.** The Terminal nav gains external links Live, Lab, Agents, Decisions, Portfolio, Classic ↗ and a right-aligned "Client app ↗". Every operator page renders the same header + nav via a Jinja include `templates/_operator_nav.html` (server-rendered, marks the current page). `static/pageswitch.js` injection is removed from every template; the file stays on disk.
- **/live** keeps radar, engine pods and detail panel; loses film grain, scanline, vignette, corner brackets and Orbitron; adopts desk tokens and the operator nav.
- **/dashboard** is reskinned, not rewritten: its inline `:root` palette is replaced by desk tokens, its own header/sidebar are kept but recoloured, and the operator nav is added above. Panels and JS untouched.
- **Landing** is relit to the client skin (white, green, Plus Jakarta Sans). Copy unchanged except colour-bound assets. Done last.
- **Content rules from the client spec stay absolute**: no engine names on client pages, no hit rate without sample size, `hit_rate === null` renders "Not yet", missing price renders "price unavailable" never ₹0, `since` means recording since.

## Components (client)
`app.css` primitives: `.topbar .tabs .tab .search .avatar`, `.card .card.tint`, `.label`, `.big` (mono, 38px/800), `.chip.{buy,sell,open,hit,miss,ung}`, `.tbl` (desktop table) and `.row` (phone stacked row — the one component written twice), `.btn .btn.ghost`, `.fchip` filter pills, `.field .input`, `.idx` index tile, `.tabbar .tabm`, `.progress`. Empty states use `.empty` with a one-line explanation, never a zero.

## Data flow
Unchanged. Screens keep consuming `/api/app/*`; `screens.js` renders the new markup from the same payloads; `main.js` renders the nav from the same route list via `TPRoute`. No new endpoints. Operator pages keep their existing fetches.

## Error handling
Unchanged semantics: a failed fetch shows the card's own failure line; a 401 shows the signed-out state. Nav include must not depend on any API.

## Testing
- `python3 -m pytest tests/ -q` stays green (23 app-screen tests + rest).
- Playwright pass at 1366×900 and 390×844 on `/app#home`, `#calls`, `#book`, `#record`, `/login`, `/signup`, `/`, `/live`, `/lab`, `/team`, `/decisions`, `/portfolio`, `/dashboard`, `/landing`: no horizontal scroll, nav present and current tab marked, no console errors, numbers tabular, no engine names in client DOM (`grep -i v5|v4|regime` on rendered text).
- Flask must be restarted after template edits (Jinja cache).

## Out of scope
`/classic`, `/fleet` and the :5051 mobile server (screenshot-safe `?static=1` mode must keep working, so they are not touched), Kite sync, notifications, SEBI gate (deploy gate, unchanged).
