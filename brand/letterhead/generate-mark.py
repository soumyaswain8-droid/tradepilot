#!/usr/bin/env python3
"""
generate-mark — procedurally generate TradePilot logo candidates as SVG.

WHY GENERATED RATHER THAN DRAWN
The mark renders at 32x32 in the letterhead masthead. At that size the only thing
that survives is silhouette: stroke weights below ~2px at the mark's own scale
disappear, and anything with more than about four distinct shapes reads as a smudge.
Generating the geometry from parameters lets the same design be re-emitted at a
different weight or grid without redrawing it, and lets every candidate be tested at
the size it will actually be used.

WHY NOT AN IMAGE MODEL
A diffusion-generated logo is a raster. Downsampled to 32px inside a PDF it loses its
edges, and the brand indigo drifts because the model never emits an exact hex. SVG
keeps both exact.

Run:
    python3 brand/letterhead/generate-mark.py            # write all candidates
    python3 brand/letterhead/generate-mark.py --pick b   # write the chosen one as
                                                         # tradepilot-mark.svg
"""
from __future__ import annotations

import argparse
from pathlib import Path

HERE = Path(__file__).resolve().parent

INDIGO_D = "#4338CA"      # gradient dark stop
INDIGO_L = "#7C7FF3"      # gradient light stop

HEAD = (
    '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 72 72" width="72" '
    'height="72" role="img" aria-label="TradePilot">\n'
    '  <defs>\n'
    f'    <linearGradient id="tpg" x1="0" y1="72" x2="72" y2="0" '
    'gradientUnits="userSpaceOnUse">\n'
    f'      <stop offset="0%" stop-color="{INDIGO_D}"/>\n'
    f'      <stop offset="100%" stop-color="{INDIGO_L}"/>\n'
    '    </linearGradient>\n'
    '  </defs>\n'
)
TAIL = "</svg>\n"


def candle(x, body_top, body_h, wick_top, wick_bot, w=8.0, fill="url(#tpg)"):
    """One candlestick: a wick line behind a filled body. Body width is generous —
    a 3px body vanishes at 32px, an 8px body does not."""
    half = w / 2
    return (
        f'    <line x1="{x}" y1="{wick_top}" x2="{x}" y2="{wick_bot}" '
        f'stroke="{fill}" stroke-width="2.6" stroke-linecap="round"/>\n'
        f'    <rect x="{x-half}" y="{body_top}" width="{w}" height="{body_h}" '
        f'rx="1.8" fill="{fill}"/>\n'
    )


def variant_a() -> str:
    """Enclosed: three rising candles inside a rounded square. Reads as an app icon."""
    s = HEAD
    s += ('  <rect x="2" y="2" width="68" height="68" rx="17" fill="none" '
          'stroke="url(#tpg)" stroke-width="4"/>\n  <g>\n')
    for x, bt, bh, wt, wb in ((22, 42, 11, 38, 57), (36, 31, 15, 26, 50), (50, 20, 17, 16, 42)):
        s += candle(x, bt, bh, wt, wb)
    return s + "  </g>\n" + TAIL


def variant_b() -> str:
    """Open: candles rising over an implied baseline. No container, so the silhouette
    itself carries the mark — the strongest option at very small sizes."""
    s = HEAD + "  <g>\n"
    for x, bt, bh, wt, wb in ((14, 44, 13, 39, 60), (30, 32, 17, 27, 54), (46, 19, 20, 14, 46)):
        s += candle(x, bt, bh, wt, wb, w=9.5)
    s += ('    <path d="M8 63 L64 63" stroke="url(#tpg)" stroke-width="3.4" '
          'stroke-linecap="round" opacity="0.35"/>\n')
    return s + "  </g>\n" + TAIL


def variant_c() -> str:
    """Directional: candles with an ascending path arrow through them — the 'pilot'
    half of the name made explicit."""
    # Weights are deliberately heavy. The mark sits beside an 800-weight wordmark at
    # 32px; drawn at "correct" icon weights it renders as a thin scribble and reads
    # as an artifact rather than a logo. Verified by rendering at 32px, not by eye
    # at full size.
    s = HEAD + "  <g>\n"
    for x, bt, bh, wt, wb in ((15, 45, 15, 40, 62), (34, 34, 17, 29, 56), (53, 23, 17, 18, 45)):
        s += candle(x, bt, bh, wt, wb, w=11.5)
    s += ('    <path d="M9 54 L27 41 L45 30 L60 15" fill="none" stroke="url(#tpg)" '
          'stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>\n'
          '    <path d="M47 13 L62 13 L62 28" fill="none" stroke="url(#tpg)" '
          'stroke-width="6.5" stroke-linecap="round" stroke-linejoin="round"/>\n')
    return s + "  </g>\n" + TAIL


def variant_d() -> str:
    """Monogram: a 'T' cut from candlestick forms. Most abstract, least literal."""
    s = HEAD + "  <g>\n"
    s += ('    <rect x="10" y="14" width="52" height="11" rx="3" fill="url(#tpg)"/>\n'
          '    <rect x="30.5" y="14" width="11" height="46" rx="3" fill="url(#tpg)"/>\n')
    for x, bt, bh in ((17, 40, 16), (55, 32, 24)):
        s += (f'    <rect x="{x-4}" y="{bt}" width="8" height="{bh}" rx="1.8" '
              'fill="url(#tpg)" opacity="0.55"/>\n')
    return s + "  </g>\n" + TAIL


VARIANTS = {"a": variant_a, "b": variant_b, "c": variant_c, "d": variant_d}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--pick", choices=sorted(VARIANTS),
                    help="write this candidate as tradepilot-mark.svg")
    a = ap.parse_args()

    for k, fn in VARIANTS.items():
        p = HERE / f"mark-candidate-{k}.svg"
        p.write_text(fn())
        print(f"  wrote {p.name}")

    if a.pick:
        dst = HERE / "tradepilot-mark.svg"
        dst.write_text(VARIANTS[a.pick]())
        print(f"  PICKED {a.pick} -> {dst.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
