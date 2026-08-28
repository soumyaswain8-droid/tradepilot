# Terminal Manual Verification Checklist

`prototype/static/desk/router.js` and `prototype/static/desk/panes.js` touch
the DOM directly (view mounting, iframe lifecycle, hash-based navigation) and
have no automated coverage: exercising them properly needs a DOM environment
such as jsdom, and the terminal build carries a no-new-dependencies
constraint. `route.js` is pure and node-tested; `router.js` and `panes.js`
are not. This checklist is the only backstop for that gap and must be run by
hand in a real browser.

Run this checklist after any change under `prototype/static/desk/`.

::: {.checklist}

| | Verification |
|:---:|:-------------|
| ☐ | `/` opens on Desk with no sub-tab bar visible |
| ☐ | Agent Floor shows two sub-tabs and both panes load, with no duplicate header or nav pill inside the frame |
| ☐ | Leaving Agent Floor stops all `api/floor/live` and `api/team/status` traffic (watch DevTools Network); returning resumes it |
| ☐ | `#market/TITAN/5y` still opens the TITAN drawer at 5y range |
| ☐ | `#agents/floor` deep-links straight to Live Floor |
| ☐ | Pressing Back once from a freshly loaded `/` leaves the terminal (does not trap on `#desk`) |
| ☐ | `/team` and `/floor` still work standalone with their own chrome; no console errors on any tab across two poll cycles |

:::
