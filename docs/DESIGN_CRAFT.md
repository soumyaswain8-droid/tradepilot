# Dashboard Design-Craft Notes (Emil Kowalski · Taste · Impeccable)

Source: deep-research 2026-06-06 — 25/25 claims verified (3-vote adversarial), tracing to Emil
Kowalski's primary sources (emilkowal.ski, animations.dev, his SKILL.md repo), corroborated by
web.dev / NN/g / Material Design.

## Principles (verified)
- **Animate ONLY `transform` + `opacity`** — GPU-composited, stay smooth under a busy main thread
  (critical for a live-updating dashboard). Never `transition: all`; never animate width/height/
  margin/padding or blur >20px.
- **Fast + tiered durations**: button/press 100–160ms · tooltips 125–200ms · dropdowns/panels
  150–250ms · modals/drawers 200–500ms. Exits ~20% faster than entrances. 180ms > 400ms for "feel".
- **Easing is the highest-leverage choice.** Use Emil's exact curves:
  - `--ease-out: cubic-bezier(.23,1,.32,1)` — entering/exiting elements (default for UI).
  - `--ease-drawer: cubic-bezier(.32,.72,0,1)` — drawer/panel slide.
  - `--ease-in-out: cubic-bezier(.77,0,.175,1)` — on-screen elements that move/morph (radar repositioning).
  - **Never `ease-in` for UI** (feels sluggish). Plain `ease` ok for hover/color.
- **Micro-interactions**: entry scale from **0.93** (NOT scale 0); `:active { transform: scale(.97) }`
  for tactile press.
- **CSS transitions for interruptible state** (hover/select/toggle — redirect mid-flight); keyframes
  only for one-shot loops (radar sweep, alert pulse).
- **`font-variant-numeric: tabular-nums`** on ALL live numbers (P&L, prices, timers, coords) — stops
  horizontal jitter as digits change. THE highest-impact "impeccable" fix for a trading UI.
- **Restraint = taste**: ask "should this animate at all?" High-frequency refreshes (the 5s ticker,
  rapidly-updating numbers) must NOT animate. Reserve motion for state transitions (open/close/select/alert).
- Palette: dark base + single primary + one accent + monospace; glow sparingly. (Refs: Arwes —
  inspiration only, alpha; scificn-ui green #00ed3f / amber #ff8800.) Our cyan/green is legitimate.

## Applied (2026-06-06) — live.html + lab.html + pageswitch.js
- [x] tabular-nums on body + all numeric displays
- [x] Emil's exact `--ease-out`, `--ease-drawer`, `--ease-io` vars
- [x] staggered one-shot entrance (top → sessions → panes), ease-out, prefers-reduced-motion fallback
- [x] detail panel reveal via drawer ease, entry scale .97 (not 0)
- [x] `:active` press (scale .97) on chips + switcher; row press scale .995
- [x] removed `transition: all` from switcher
- [x] did NOT animate the 5s poll / live numbers (restraint)

## Remaining (next craft pass)
- [ ] Radar sweep: retime with --ease-io; draw rings on first load (one-shot keyframe).
- [ ] Sign-change flash: brief color pulse ONLY when a P&L crosses zero (not every tick).
- [ ] Spacing scale audit: settle on a 4px base scale; optical alignment of numbers/labels.
- [ ] Empty/loading states for panels (considered, not just "waiting…").
- [ ] Accessibility: green/amber gain-loss + red-green colorblindness — add shape/sign cues, check contrast.
- [ ] Confirm Chakra Petch honors tnum; if not, render big numbers in the mono stack.
