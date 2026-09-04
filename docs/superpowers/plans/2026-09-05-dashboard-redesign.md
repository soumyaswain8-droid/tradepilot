# Dashboard Redesign — implementation plan

Spec: `docs/superpowers/specs/2026-09-05-dashboard-redesign-design.md`. Reference markup: `docs/design/2026-09-05-redesign/*.dc.html` (copy exact values from these files).

Global constraints: no new runtime dependencies, no build step, ES5 in `static/app/*`, Google Fonts only via `<link>`. Never edit `/classic` (index.html), `fleet.html`, `scripts/fleet-mobile-server.py`. Never restart Flask from an agent — the orchestrator restarts once at the end. Do not commit.

## Work packages (independent, run in parallel)

- [ ] **WP-A Client app** — `prototype/static/app.css` (rewrite to the client skin), `prototype/templates/app.html` (top bar with tabs/search/avatar, keep the five mount points and script tags, add the Google Fonts link), `prototype/static/app/main.js` (`renderNav` builds top tabs and bottom tabs from the same list), `prototype/static/app/screens.js` (home, calls, call, book, record render the new markup: index strip is NOT added — no endpoint; KPI cards, tables on desktop, `.row` stack on phone via CSS, chips, progress bar in record, add-a-trade form as the Book screen). Keep every content rule. Run `python3 -m pytest tests/test_app_screens.py -q`.
- [ ] **WP-B Auth pages** — `prototype/templates/login.html`, `signup.html`, `set-password.html`: split layout from `SignIn.dc.html` (left tinted panel with the promise + two count tiles, right form). Keep every form field name, action, CSRF/hidden input, error and `done` branch exactly. Bracketed `[SEBI STATUS LINE]` stays as literal text.
- [ ] **WP-C Operator nav + Live/Lab/Team/Decisions/Portfolio** — create `prototype/templates/_operator_nav.html` (header + nav markup identical to `desk.html`'s topbar/nav, links: Desk `/`, Market `/#market`, Movers `/#movers`, News `/#news`, Agents `/#agents`, Live `/live`, Lab `/lab`, Decisions `/decisions`, Portfolio `/portfolio`, Classic ↗ `/classic`, right-aligned Client app ↗ `/app`; `{% set current = 'live' %}` before include marks the tab). Add `EXTERNAL` entries Live/Lab/Portfolio to `static/desk/router.js` and a right-aligned Client app link. Include the nav in `live.html`, `lab.html`, `team.html`, `decisions.html`, `portfolio.html`; remove the `pageswitch.js` script line from each. Restyle each to desk tokens (link `/static/desk.css` first, then page-specific overrides). `/live`: delete grain/scanline/vignette/bracket overlays and Orbitron/Chakra fonts; keep radar SVG, engine pods, positions list, detail panel, session strip; keep `?date=` validation.
- [ ] **WP-D Legacy Desk reskin** — `prototype/templates/dashboard.html`: replace `:root` palette values with desk tokens (bg/panel/line/ink/muted/green/red/accent), swap Inter Tight/Inter for the system stack and keep JetBrains Mono, include `_operator_nav.html` at the top of `<body>`, remove `pageswitch.js`. Do not touch panel markup or JS. Fix any hard-coded light colours that now clash (search `#F6F9FC`, `#fff`, `#0A2540`).
- [ ] **WP-E Landing** — `prototype/templates/landing.html`: relight to the client skin (white ground, green accent, Plus Jakarta Sans, 16px cards, 44px buttons). Copy unchanged. CTA links unchanged. Check at 390px.

## Verification (after all packages)
- [ ] Restart Flask on :5050; `python3 -m pytest tests/ -q`.
- [ ] Playwright pass per spec §Testing at 1366×900 and 390×844; screenshots to `docs/design/2026-09-05-redesign/verify/`.
- [ ] Client DOM text contains no `v4`, `v5`, `regime`, `composite`, `alpha-hunter`.
