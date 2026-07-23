# TradePilot Landing Page — Sci-Fi Mission Control Redesign

**Date:** 2026-07-23 · **Approved:** verbally in session · **Approach:** A (Mission Control HUD)

## Goal
Replace the Stripe/Plaid-style light landing page with a dark, futuristic sci-fi page — illustrative SVG designs and animated graphs — using assets from the aide design library.

## Design tokens (from aide library)
- **Palette:** "Combo 01: Tiffany + Dark Gray" (plate 45) — `#21F1A8` neon mint on `#171717` near-black. Elevated panels ~`#1D1F1E`. Dim red `#FF5C5C` reserved for down/risk semantics only.
- **Fonts (aide fontlab, available=true):** Space Grotesk (display + body), JetBrains Mono (numbers, HUD labels). Google Fonts, same loading pattern as current page.

## Structure (fresh copy, same facts)
1. **Nav** — glass bar + mono ticker strip.
2. **Hero** — "Seven engines. One flight computer." Animated HUD: orbital ring with 7 pulsing engine nodes, self-drawing equity curve, mono telemetry readouts.
3. **№01 Fleet** — 7 engines as an SVG constellation/system diagram; engine cards with sparklines. Engines: v4 Composite, v5 Multi-pool, v5 Classic, v5_6 Darvas Box, v5_7 Mean-Revert, v5_8 Regime-Aware, v6 Bolt-On.
4. **№02 Risk Shield** — concentric HUD shield rings for the layered defence; kill-switch tiers T0–T3 (−₹2.5K warn / −₹5K soft hold / −₹10K hard kill).
5. **№03 Flight Log** — trading day as mission timeline (08:45 scoring → 09:15 deploy → 10m scans → 30m rescore → 15:15 force exit).
6. **№04 Telemetry** — real Mode A numbers: best day +₹1,96,789 (v4 · 243 trades · 92% wins), fleet day +₹3,77,836 (877 trades), 38:1 P/L, 6× turnover. Leaderboard bar graph.
7. **CTA + footer** — dashboard link, support@devpilot.co.in, privacy/terms, full Mode A paper-trading disclaimer (kept verbatim).

## Constraints
- Single self-contained template at `prototype/templates/landing.html`; old version archived as `landing-stripe-2026-07-23.html` (existing convention).
- No JS libraries, no build step — inline SVG + CSS animations only.
- `/landing` route in `prototype/app.py` unchanged.
- All numbers/claims carried over verbatim from the current page (no invented stats).
- Contact/footer links per landing-page-contact-standard (no auto-generated contacts).
- `prefers-reduced-motion` respected for animations.
