#!/usr/bin/env python3
"""
Build the TradePilot explainer PDF — the version you hand to someone who has never
bought a share in their life.

Two rules govern this document:
  1. NO ASSUMED KNOWLEDGE. Every market term is defined the first time it appears.
  2. NO UNBACKED NUMBER. Every figure is one we measured, and the page says so.

Renders via headless Chrome (pyppeteer). NEVER WeasyPrint — its font subsetting is
broken on macOS and silently renders text as dots.

    python3 brand/build-explainer.py
"""
from __future__ import annotations
import asyncio, base64, io, math, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT_HTML = ROOT / "brand" / "tradepilot-explainer.html"
OUT_PDF = ROOT / "1cr-roadmap" / "TradePilot-How-It-Works.pdf"

# ── brand ───────────────────────────────────────────────────────────────────
INDIGO, INDIGO_D, LILAC = "#4f46e5", "#4338ca", "#818cf8"
INK, BODY, MUTED = "#0a0520", "#2b2640", "#6b6580"
CREAM, RULE = "#f1f2fb", "#dddef5"
OK, WARN, BAD = "#1a7f4b", "#b45309", "#be123c"


def b64(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def logo_uri() -> str:
    """The bull mark, transparent.

    NOT prototype/static/logo-tradepilot.png — that file is a CONTACT SHEET: the same
    mark repeated at four sizes with "30px topbar / 60px / 120px / Detail view"
    captions baked onto an opaque background. Dropped into a 5mm-tall header it
    rendered as a strip of four dark boxes. brand/build-explainer.py extracts the
    largest tile, trims it, and knocks the background out to alpha.
    """
    from PIL import Image
    p = ROOT / "brand" / "letterhead" / "tradepilot-bull.png"
    im = Image.open(p).convert("RGBA")
    im.thumbnail((420, 420))
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()


def font_face(name: str, file: str, weight: int) -> str:
    p = ROOT / "brand" / "letterhead" / "fonts" / file
    if not p.exists():
        return ""
    return (f"@font-face{{font-family:'{name}';src:url('{b64(p,'font/ttf')}') "
            f"format('truetype');font-weight:{weight};font-style:normal;}}")


# ══════════════════════════════════════════════════════════════════════════════
# ISOMETRIC HELPERS — real 3D projection, computed not eyeballed
# ══════════════════════════════════════════════════════════════════════════════
def iso(x, y, z, ox=0, oy=0, sx=1.0, sy=0.5):
    """Project a 3D point to 2D on a standard 2:1 isometric grid."""
    return (ox + (x - y) * sx, oy + (x + y) * sy - z)


def slab(cx, cy, w, d, h, top, left, right, label="", sub="", lab_col="#fff"):
    """One 3D slab: top face plus two visible side faces. Returns SVG."""
    hw, hd = w / 2, d / 2
    # top face corners
    t = [iso(-hw, -hd, h, cx, cy), iso(hw, -hd, h, cx, cy),
         iso(hw, hd, h, cx, cy), iso(-hw, hd, h, cx, cy)]
    b = [iso(-hw, -hd, 0, cx, cy), iso(hw, -hd, 0, cx, cy),
         iso(hw, hd, 0, cx, cy), iso(-hw, hd, 0, cx, cy)]
    pts = lambda P: " ".join(f"{x:.1f},{y:.1f}" for x, y in P)
    s = []
    # left face (between t[0],t[3] and b[3],b[0]) and right face
    s.append(f'<polygon points="{pts([t[3],t[2],b[2],b[3]])}" fill="{left}"/>')
    s.append(f'<polygon points="{pts([t[2],t[1],b[1],b[2]])}" fill="{right}"/>')
    s.append(f'<polygon points="{pts(t)}" fill="{top}"/>')
    if label:
        lx, ly = iso(0, 0, h, cx, cy)
        s.append(f'<text x="{lx:.1f}" y="{ly+4:.1f}" text-anchor="middle" '
                 f'font-family="JetBrains Mono,monospace" font-size="17" '
                 f'font-weight="700" fill="{lab_col}">{label}</text>')
    if sub:
        rx, ry = iso(hw, hd, h / 2, cx, cy)
        s.append(f'<text x="{rx+16:.1f}" y="{ry+4:.1f}" font-family="Helvetica,sans-serif" '
                 f'font-size="12.5" fill="{BODY}">{sub}</text>')
    return "".join(s)


def funnel_svg() -> str:
    """The pipeline as a stack of 3D slabs narrowing downward.

    GEOMETRY NOTE. On an isometric grid a w x d top face has a VERTICAL extent of
    (w + d) * sy — for the widest slab that is ~178px. An earlier version spaced the
    slabs 52px apart, so each one painted over the label of the one above and the
    count on the top slab was sliced in half. Two fixes: flatten sy so the faces are
    shallower, and put every label OUTSIDE the stack at a fixed x, clear of the
    widest slab. Slabs may then overlap freely — that is what a stack looks like.
    """
    rows = [
        (938, "Every company we could trade", 1.00),
        (889, "Real companies only — funds removed", 0.95),
        (437, "Big enough, cheap enough, not frozen", 0.72),
        (320, "Studied in depth overnight", 0.56),
        (60,  "At least one scout interested", 0.36),
        (20,  "Given a full-time watcher", 0.22),
        (2,   "Actually bought", 0.09),
    ]
    W, H = 700, 352
    CX, SY = 258, 0.28
    NUM_X, LBL_X = 112, 430
    gap = 41
    parts = [f'<svg viewBox="0 0 {W} {H}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    for i, (n, lbl, frac) in enumerate(rows):
        w = 196 * frac + 30
        d = w * 0.34
        cy = 46 + i * gap
        t = i / (len(rows) - 1)
        top = f"rgb({int(79+(140-79)*t)},{int(70+(152-70)*t)},{int(229+(250-229)*t)})"
        lf = f"rgb({int(48+(92-48)*t)},{int(42+(100-42)*t)},{int(150+(190-150)*t)})"
        rt = f"rgb({int(61+(112-61)*t)},{int(52+(122-52)*t)},{int(190+(218-190)*t)})"
        hw, hd = w / 2, d / 2
        pt = lambda x, y, z: (CX + (x - y), cy + (x + y) * SY - z)
        T = [pt(-hw, -hd, 18), pt(hw, -hd, 18), pt(hw, hd, 18), pt(-hw, hd, 18)]
        B = [pt(-hw, -hd, 0), pt(hw, -hd, 0), pt(hw, hd, 0), pt(-hw, hd, 0)]
        P = lambda pts: " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)
        # GLASS SLAB. Three cues, all required: the side faces are darker and
        # semi-opaque (the body of the glass), the top face carries a gradient
        # (light passing through), and a bright 1px line runs along the leading
        # edge (the specular catch). Drop the highlight and it reads as plastic.
        gid = f"g{i}"
        parts.append(
            f'<defs><linearGradient id="{gid}" x1="0" y1="0" x2="0.6" y2="1">'
            f'<stop offset="0%" stop-color="{top}" stop-opacity="0.95"/>'
            f'<stop offset="55%" stop-color="{top}" stop-opacity="0.72"/>'
            f'<stop offset="100%" stop-color="{rt}" stop-opacity="0.88"/>'
            f'</linearGradient>'
            f'<linearGradient id="{gid}s" x1="0" y1="0" x2="1" y2="0.3">'
            f'<stop offset="0%" stop-color="{lf}" stop-opacity="0.95"/>'
            f'<stop offset="100%" stop-color="{lf}" stop-opacity="0.72"/>'
            f'</linearGradient></defs>')
        parts.append(f'<polygon points="{P([T[3],T[2],B[2],B[3]])}" fill="url(#{gid}s)"/>')
        parts.append(f'<polygon points="{P([T[2],T[1],B[1],B[2]])}" fill="{rt}" '
                     f'fill-opacity="0.86"/>')
        parts.append(f'<polygon points="{P(T)}" fill="url(#{gid})"/>')
        # specular highlight along the top-left edge
        parts.append(f'<polyline points="{P([T[0],T[1]])}" fill="none" '
                     f'stroke="#ffffff" stroke-opacity="0.75" stroke-width="1.4"/>')
        parts.append(f'<polyline points="{P([T[0],T[3]])}" fill="none" '
                     f'stroke="#ffffff" stroke-opacity="0.45" stroke-width="1.1"/>')
        # labels live outside the stack, so nothing can occlude them
        my = cy + 6
        parts.append(f'<text x="{NUM_X}" y="{my:.1f}" text-anchor="end" '
                     f'font-family="JetBrains Mono,monospace" font-size="17" '
                     f'font-weight="700" fill="{INDIGO_D}">{n:,}</text>')
        parts.append(f'<text x="{LBL_X}" y="{my:.1f}" font-family="Helvetica,sans-serif" '
                     f'font-size="11.5" fill="{BODY}">{lbl}</text>')
        # a hairline connecting the number to its slab, so the pairing is unambiguous
        parts.append(f'<line x1="{NUM_X+8}" y1="{my-4:.1f}" x2="{CX-hw-hd-4:.1f}" '
                     f'y2="{my-4:.1f}" stroke="{RULE}" stroke-width=".8"/>')
        parts.append(f'<line x1="{CX+hw+hd+4:.1f}" y1="{my-4:.1f}" x2="{LBL_X-8}" '
                     f'y2="{my-4:.1f}" stroke="{RULE}" stroke-width=".8"/>')
    parts.append("</svg>")
    return "".join(parts)


def bars3d_svg(data, w=660, h=260, ymin=None, ymax=None, unit="%") -> str:
    """3D bar chart — each bar an extruded box, so gains and losses read as solid
    objects rather than flat rectangles."""
    vals = [v for _, v in data]
    ymin = min(vals + [0]) if ymin is None else ymin
    ymax = max(vals + [0]) if ymax is None else ymax
    pad, base_y = 46, h - 58
    span = ymax - ymin or 1
    plot_h = base_y - 34
    zero_y = base_y - (0 - ymin) / span * plot_h
    bw = (w - pad * 2) / len(data) * 0.58
    step = (w - pad * 2) / len(data)
    dx, dy = 11, -8            # extrusion vector
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    # zero rule
    s.append(f'<line x1="{pad-8}" y1="{zero_y:.1f}" x2="{w-pad+18}" y2="{zero_y:.1f}" '
             f'stroke="{RULE}" stroke-width="1.5"/>')
    for i, (lbl, v) in enumerate(data):
        x = pad + i * step + (step - bw) / 2
        y = base_y - (v - ymin) / span * plot_h
        top_y, bot_y = min(y, zero_y), max(y, zero_y)
        hgt = max(bot_y - top_y, 1.2)
        pos = v >= 0
        face = INDIGO if pos else "#e11d48"
        side = INDIGO_D if pos else "#9f1239"
        cap = LILAC if pos else "#fb7185"
        # side face
        s.append(f'<polygon points="{x+bw},{top_y:.1f} {x+bw+dx},{top_y+dy:.1f} '
                 f'{x+bw+dx},{bot_y+dy:.1f} {x+bw},{bot_y:.1f}" fill="{side}"/>')
        # top cap
        s.append(f'<polygon points="{x},{top_y:.1f} {x+dx},{top_y+dy:.1f} '
                 f'{x+bw+dx},{top_y+dy:.1f} {x+bw},{top_y:.1f}" fill="{cap}"/>')
        # front face
        s.append(f'<rect x="{x:.1f}" y="{top_y:.1f}" width="{bw:.1f}" '
                 f'height="{hgt:.1f}" fill="{face}"/>')
        vy = top_y - 8 if pos else bot_y + dy + 16
        s.append(f'<text x="{x+bw/2+dx/2:.1f}" y="{vy:.1f}" text-anchor="middle" '
                 f'font-family="JetBrains Mono,monospace" font-size="10.5" '
                 f'fill="{BODY}">{v:+.3f}</text>')
        s.append(f'<text x="{x+bw/2:.1f}" y="{base_y+20:.1f}" text-anchor="middle" '
                 f'font-family="Helvetica,sans-serif" font-size="10" fill="{MUTED}">{lbl}</text>')
    s.append("</svg>")
    return "".join(s)


def confluence_svg() -> str:
    """The measured confluence gradient as a 3D ribbon climbing out of loss."""
    pts = [(1, -0.16), (2, -0.11), (3, -0.06), (4, -0.01),
           (5, 0.03), (6, 0.06), (7, 0.084)]
    w, h, pad = 660, 250, 52
    xs = lambda i: pad + (i - 1) / 6 * (w - pad * 2)
    lo, hi = -0.20, 0.11
    ys = lambda v: h - 52 - (v - lo) / (hi - lo) * (h - 96)
    dx, dy = 14, -10
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<defs><linearGradient id="rib" x1="0" y1="0" x2="1" y2="0">'
             f'<stop offset="0%" stop-color="#e11d48"/>'
             f'<stop offset="55%" stop-color="{LILAC}"/>'
             f'<stop offset="100%" stop-color="{INDIGO}"/></linearGradient></defs>')
    # right-anchored inside the viewBox: left-anchored at the line's end it ran past
    # the edge and published as "break"
    s.append(f'<line x1="{pad-10}" y1="{ys(0):.1f}" x2="{w-14}" y2="{ys(0):.1f}" '
             f'stroke="{RULE}" stroke-width="1.5" stroke-dasharray="4 4"/>')
    s.append(f'<text x="{w-14}" y="{ys(0)-6:.1f}" text-anchor="end" '
             f'font-family="Helvetica" font-size="10" fill="{MUTED}">break even</text>')
    # the extruded ribbon body
    top = " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in pts)
    back = " ".join(f"{xs(i)+dx:.1f},{ys(v)+dy:.1f}" for i, v in reversed(pts))
    s.append(f'<polygon points="{top} {back}" fill="url(#rib)" opacity="0.42"/>')
    s.append(f'<polyline points="{back}" fill="none" stroke="#ffffff" '
             f'stroke-opacity="0.6" stroke-width="1.2"/>')
    s.append(f'<polyline points="{top}" fill="none" stroke="url(#rib)" stroke-width="3.5" '
             f'stroke-linejoin="round"/>')
    for i, v in pts:
        s.append(f'<circle cx="{xs(i):.1f}" cy="{ys(v):.1f}" r="4.5" fill="#fff" '
                 f'stroke="{INDIGO_D}" stroke-width="2.2"/>')
        # values are already percentages — never scale them (see cost_svg)
        s.append(f'<text x="{xs(i):.1f}" y="{ys(v)-14:.1f}" text-anchor="middle" '
                 f'font-family="JetBrains Mono,monospace" font-size="10" '
                 f'fill="{OK if v>0 else BAD}">{v:+.3f}%</text>')
        s.append(f'<text x="{xs(i):.1f}" y="{h-26}" text-anchor="middle" '
                 f'font-family="Helvetica" font-size="11" fill="{MUTED}">{i}</text>')
    s.append(f'<text x="{w/2:.0f}" y="{h-8}" text-anchor="middle" font-family="Helvetica" '
             f'font-size="11" fill="{BODY}">how many independent scouts agree</text>')
    s.append("</svg>")
    return "".join(s)


def tick_walk_svg() -> str:
    """A worked example: one agent, one morning, price walking into its level."""
    w, h = 660, 300
    px = [412.0, 412.4, 411.8, 412.9, 413.6, 414.2, 413.9, 414.8, 415.6, 416.1,
          415.4, 414.2, 413.1, 412.4, 411.6, 410.9, 411.8, 413.2, 414.4, 415.9,
          417.2, 418.4, 419.1, 418.6, 419.8]
    lo, hi = 408, 422
    padl, padr, top, bot = 44, 152, 30, 62     # right gutter reserved for level labels
    xs = lambda i: padl + i / (len(px) - 1) * (w - padl - padr)
    ys = lambda v: h - bot - (v - lo) / (hi - lo) * (h - bot - top)
    LVL_PDL, LVL_VWAP = 411.0, 414.5
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<defs><linearGradient id="fill" x1="0" y1="0" x2="0" y2="1">'
             f'<stop offset="0%" stop-color="{INDIGO}" stop-opacity="0.20"/>'
             f'<stop offset="100%" stop-color="{INDIGO}" stop-opacity="0.01"/>'
             f'</linearGradient></defs>')
    # Level labels live in the right gutter, NOT over the plot. Placed inside, the
    # dashed rule struck straight through its own caption.
    for lv, name, col in ((LVL_PDL, "yesterday's low", "#e11d48"),
                          (LVL_VWAP, "today's average", INDIGO_D)):
        s.append(f'<line x1="{padl-6}" y1="{ys(lv):.1f}" x2="{w-padr+10}" '
                 f'y2="{ys(lv):.1f}" stroke="{col}" stroke-width="1.3" '
                 f'stroke-dasharray="5 4" opacity="0.8"/>')
        s.append(f'<text x="{w-padr+16}" y="{ys(lv)-1:.1f}" font-family="Helvetica" '
                 f'font-size="10" font-weight="600" fill="{col}">{name}</text>')
        s.append(f'<text x="{w-padr+16}" y="{ys(lv)+11:.1f}" '
                 f'font-family="JetBrains Mono,monospace" font-size="9.5" '
                 f'fill="{MUTED}">₹{lv:.2f}</text>')
    line = " ".join(f"{xs(i):.1f},{ys(v):.1f}" for i, v in enumerate(px))
    s.append(f'<polygon points="{line} {xs(len(px)-1):.1f},{h-bot} {padl:.1f},{h-bot}" '
             f'fill="url(#fill)"/>')
    s.append(f'<polyline points="{line}" fill="none" stroke="{INDIGO}" stroke-width="2.4" '
             f'stroke-linejoin="round" stroke-linecap="round"/>')
    # below=True keeps a caption off the dashed rule it would otherwise sit on
    marks = [(15, "sweep", "#e11d48", True), (17, "reclaim", WARN, True),
             (19, "BUY", OK, False)]
    for i, tag, col, below in marks:
        cy = ys(px[i])
        s.append(f'<circle cx="{xs(i):.1f}" cy="{cy:.1f}" r="6" fill="#fff" '
                 f'stroke="{col}" stroke-width="2.6"/>')
        ty = cy + 21 if below else cy - 15
        s.append(f'<text x="{xs(i):.1f}" y="{ty:.1f}" text-anchor="middle" '
                 f'font-family="Helvetica" font-size="10.5" font-weight="700" '
                 f'fill="{col}">{tag}</text>')
    s.append(f'<line x1="{padl-6}" y1="{h-bot}" x2="{w-padr+10}" y2="{h-bot}" '
             f'stroke="{RULE}" stroke-width="1"/>')
    s.append(f'<text x="{padl}" y="{h-bot+26}" font-family="Helvetica" font-size="10" '
             f'fill="{MUTED}">9:16am</text>')
    s.append(f'<text x="{w-padr+10}" y="{h-bot+26}" text-anchor="end" '
             f'font-family="Helvetica" font-size="10" fill="{MUTED}">11:05am</text>')
    s.append(f'<text x="{(padl+w-padr)/2:.0f}" y="{h-bot+26}" text-anchor="middle" '
             f'font-family="Helvetica" font-size="10" fill="{MUTED}">'
             f'one morning of live prices</text>')
    s.append("</svg>")
    return "".join(s)


def agent_anatomy_svg() -> str:
    """What one agent holds in its head, and the five things that wake it up."""
    w, h = 660, 330
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    s.append(f'<defs><linearGradient id="ag" x1="0" y1="0" x2="1" y2="1">'
             f'<stop offset="0%" stop-color="{INDIGO}"/>'
             f'<stop offset="100%" stop-color="{INDIGO_D}"/></linearGradient></defs>')
    # the agent core, drawn as a 3D box
    cx, cy = 165, 150
    bw, bh, d = 148, 96, 20
    s.append(f'<polygon points="{cx-bw/2},{cy-bh/2} {cx-bw/2+d},{cy-bh/2-d*0.7} '
             f'{cx+bw/2+d},{cy-bh/2-d*0.7} {cx+bw/2},{cy-bh/2}" fill="{LILAC}"/>')
    s.append(f'<polygon points="{cx+bw/2},{cy-bh/2} {cx+bw/2+d},{cy-bh/2-d*0.7} '
             f'{cx+bw/2+d},{cy+bh/2-d*0.7} {cx+bw/2},{cy+bh/2}" fill="{INDIGO_D}"/>')
    s.append(f'<rect x="{cx-bw/2}" y="{cy-bh/2}" width="{bw}" height="{bh}" fill="url(#ag)" rx="3"/>')
    s.append(f'<text x="{cx}" y="{cy-16}" text-anchor="middle" font-family="Helvetica" '
             f'font-size="13" font-weight="700" fill="#fff">ONE AGENT</text>')
    s.append(f'<text x="{cx}" y="{cy+4}" text-anchor="middle" font-family="JetBrains Mono,monospace" '
             f'font-size="10.5" fill="#dcd9fb">watches 1 stock</text>')
    s.append(f'<text x="{cx}" y="{cy+22}" text-anchor="middle" font-family="JetBrains Mono,monospace" '
             f'font-size="10.5" fill="#dcd9fb">every single tick</text>')
    # memory box — height must cover the header plus every bullet, or the last line
    # is silently clipped by the rect (it was, at height 74)
    mem = ["yesterday's high and low", "today's average price",
           "the day's high and low so far", "the nearest round number"]
    box_y, line0, lh = 226, 246, 13.5
    box_h = (line0 + lh * len(mem)) - box_y + 4
    s.append(f'<rect x="24" y="{box_y}" width="282" height="{box_h:.0f}" rx="4" '
             f'fill="{CREAM}" stroke="{RULE}"/>')
    s.append(f'<text x="36" y="{box_y+16}" font-family="Helvetica" font-size="10.5" '
             f'font-weight="700" fill="{INK}">WHAT IT REMEMBERS (set at 9:16am)</text>')
    for j, t in enumerate(mem):
        s.append(f'<text x="36" y="{line0+j*lh:.0f}" font-family="JetBrains Mono,monospace" '
                 f'font-size="9.2" fill="{BODY}">• {t}</text>')
    # triggers — thresholds in plain percentages, since "bps" is never defined for a
    # reader who has not traded before
    trig = [("price touches a level", "within 0.08%"),
            ("dips below then jumps back", "the trap springs"),
            ("moves unusually fast", "0.25% in a minute"),
            ("sudden burst of buying", "3x the normal rate"),
            ("our trade goes wrong", "act immediately")]
    for j, (t, sub) in enumerate(trig):
        y = 34 + j * 56
        s.append(f'<rect x="360" y="{y}" width="278" height="44" rx="4" fill="#fff" '
                 f'stroke="{RULE}"/>')
        s.append(f'<rect x="360" y="{y}" width="3.5" height="44" fill="{INDIGO if j<4 else "#e11d48"}"/>')
        s.append(f'<text x="374" y="{y+19}" font-family="Helvetica" font-size="11" '
                 f'font-weight="600" fill="{INK}">{t}</text>')
        s.append(f'<text x="374" y="{y+34}" font-family="JetBrains Mono,monospace" '
                 f'font-size="9" fill="{MUTED}">{sub}</text>')
        s.append(f'<path d="M {cx+bw/2+d+6} {cy} C 320 {cy}, 330 {y+22}, 356 {y+22}" '
                 f'fill="none" stroke="{RULE}" stroke-width="1.4"/>')
    s.append(f'<text x="499" y="18" text-anchor="middle" font-family="Helvetica" font-size="10.5" '
             f'font-weight="700" fill="{MUTED}">FIVE THINGS MAKE IT RAISE ITS HAND</text>')
    s.append("</svg>")
    return "".join(s)


def cost_svg() -> str:
    """Every strategy we tested, against the toll drawn as the bar they must REACH.

    NOTE ON UNITS: these values are already percentages (0.106 means 0.106%). An
    earlier version printed them as `v*100` and published "+10.6000%" — a hundredfold
    overstatement of the single most important number in the document. Format them
    as-is; never scale.

    The toll is a THRESHOLD, not a competitor, so it is a vertical line the bars have
    to cross rather than another bar beside them. Drawn that way the point needs no
    caption: nothing reaches it.
    """
    w, h = 660, 232
    items = [("Best confluence setup", 0.0910, INDIGO),
             ("Our main scorer", 0.0690, LILAC),
             ("Best single chart pattern", 0.0510, LILAC),
             ("Trend following", -0.0390, "#e11d48")]
    TOLL = 0.1060
    pad_l, pad_r, bh, gap, top = 178, 96, 24, 16, 40
    mx = 0.125
    zero = pad_l
    span = w - pad_l - pad_r
    xof = lambda v: zero + v / mx * span
    s = [f'<svg viewBox="0 0 {w} {h}" width="100%" xmlns="http://www.w3.org/2000/svg">']
    # the toll: a wall every bar has to reach
    tx = xof(TOLL)
    s.append(f'<rect x="{zero}" y="{top-10}" width="{tx-zero:.1f}" '
             f'height="{len(items)*(bh+gap)+6}" fill="#fdf0f3"/>')
    s.append(f'<line x1="{tx:.1f}" y1="{top-16}" x2="{tx:.1f}" '
             f'y2="{top+len(items)*(bh+gap)}" stroke="#e11d48" stroke-width="2.2"/>')
    s.append(f'<text x="{tx+7:.1f}" y="{top-22}" font-family="Helvetica" font-size="10.5" '
             f'font-weight="700" fill="#e11d48">THE TOLL — 0.106%</text>')
    s.append(f'<text x="{tx+7:.1f}" y="{top-9}" font-family="Helvetica" font-size="9" '
             f'fill="{MUTED}">every bar must reach this line</text>')
    for i, (lbl, v, col) in enumerate(items):
        y = top + i * (bh + gap)
        bw = abs(v) / mx * span
        x = zero if v >= 0 else zero - bw
        s.append(f'<polygon points="{x+bw},{y} {x+bw+7},{y-5} {x+bw+7},{y+bh-5} '
                 f'{x+bw},{y+bh}" fill="{col}" opacity="0.5"/>')
        s.append(f'<polygon points="{x},{y} {x+7},{y-5} {x+bw+7},{y-5} {x+bw},{y}" '
                 f'fill="{col}" opacity="0.72"/>')
        bid = f"b{i}"
        s.append(f'<defs><linearGradient id="{bid}" x1="0" y1="0" x2="0" y2="1">'
                 f'<stop offset="0%" stop-color="#ffffff" stop-opacity="0.42"/>'
                 f'<stop offset="35%" stop-color="{col}" stop-opacity="0.98"/>'
                 f'<stop offset="100%" stop-color="{col}" stop-opacity="0.82"/>'
                 f'</linearGradient></defs>')
        s.append(f'<rect x="{x:.1f}" y="{y}" width="{bw:.1f}" height="{bh}" '
                 f'fill="url(#{bid})" rx="1.5"/>')
        s.append(f'<line x1="{x:.1f}" y1="{y+0.8}" x2="{x+bw:.1f}" y2="{y+0.8}" '
                 f'stroke="#ffffff" stroke-opacity="0.7" stroke-width="1.2"/>')
        s.append(f'<text x="{pad_l-14}" y="{y+16}" text-anchor="end" font-family="Helvetica" '
                 f'font-size="11" fill="{INK}">{lbl}</text>')
        # Labels sit INSIDE the bar when its end is close to the toll line, otherwise
        # they overlap it — the longest bar is exactly the one whose label collides.
        inside = (tx - (x + bw)) < 92 and bw > 120
        lx = (x + bw - 10) if inside else (x + bw + 14)
        anchor = "end" if inside else "start"
        col_v = "#ffffff" if inside else BODY
        col_g = "#f3c9d3" if inside else "#e11d48"
        s.append(f'<text x="{lx:.1f}" y="{y+11}" text-anchor="{anchor}" '
                 f'font-family="JetBrains Mono,monospace" font-size="10" '
                 f'fill="{col_v}">{v:+.4f}%</text>')
        s.append(f'<text x="{lx:.1f}" y="{y+22}" text-anchor="{anchor}" '
                 f'font-family="Helvetica" font-size="8.5" '
                 f'fill="{col_g}">short by {TOLL-v:.3f}%</text>')
    s.append(f'<line x1="{zero}" y1="{top-16}" x2="{zero}" y2="{top+len(items)*(bh+gap)}" '
             f'stroke="{INK}" stroke-width="1.4"/>')
    s.append(f'<text x="{zero-14}" y="{top+len(items)*(bh+gap)+14}" text-anchor="end" '
             f'font-family="Helvetica" font-size="9" fill="{MUTED}">break even</text>')
    s.append("</svg>")
    return "".join(s)


# ══════════════════════════════════════════════════════════════════════════════
def build_html() -> str:
    faces = font_face("Syne", "Syne-ExtraBold.ttf", 800) + \
            font_face("JetBrains Mono", "JetBrainsMono-Medium.ttf", 500)
    logo = logo_uri()
    mark = (ROOT / "brand" / "letterhead" / "tradepilot-mark.svg").read_text()

    css = f"""
{faces}
@page {{ size: A4; margin: 0; }}

/* ── GLASS SYSTEM ────────────────────────────────────────────────────────────
   Real glass has three cues and needs all three or it reads as a grey box:
     1. it TINTS what is behind it   -> translucent gradient fill
     2. it catches light on its edge -> 1px inset highlight along the top
     3. it floats                    -> a soft, wide, low-opacity shadow
   backdrop-filter is unreliable in print, so the ground carries its own colour
   and the panels tint it with rgba instead of blurring it. */
.glass{{
  background:linear-gradient(150deg,rgba(255,255,255,.86),rgba(255,255,255,.52));
  border:0.6pt solid rgba(255,255,255,.9);
  border-radius:5pt;
  box-shadow:0 0.8pt 0 rgba(49,46,129,.10), 0 2pt 0 rgba(49,46,129,.05),inset 0 0.6pt 0 rgba(255,255,255,.95);
}}
.glass-d{{
  background:linear-gradient(150deg,rgba(79,70,229,.13),rgba(129,140,248,.05));
  border:0.6pt solid rgba(255,255,255,.75);
  border-radius:5pt;
  box-shadow:0 0.8pt 0 rgba(49,46,129,.14), 0 2pt 0 rgba(49,46,129,.06),inset 0 0.6pt 0 rgba(255,255,255,.85);
}}
/* The ground the glass sits on. Drawn as inline SVG, NOT css radial-gradient:
   Chrome rasterises css radial gradients into image XObjects when printing —
   6-11 per page, and the file went from 551KB to 7.4MB. SVG gradients stay
   vector into the PDF at no size cost. */
.mesh{{position:absolute;inset:0;z-index:0;overflow:hidden;}}
.mesh svg{{width:100%;height:100%;display:block;}}
.page > *:not(.mesh){{position:relative;z-index:1;}}
/* ...but NOT the page furniture. The rule above exists so glass panels sit above
   the tinted ground; applied blindly it also overrode position:absolute on the
   running header and footer, which dropped into normal flow and printed on top of
   the H1 and the last table row. Re-assert them AFTER, so specificity resolves in
   their favour. */
.page > .rh{{position:absolute;top:9mm;left:18mm;right:18mm;z-index:2;}}
.page > .rf{{position:absolute;bottom:9mm;left:18mm;right:18mm;z-index:2;}}
*{{box-sizing:border-box;}}
html,body{{margin:0;padding:0;}}
body{{
  font:400 10.6pt/1.62 "Helvetica Neue",Helvetica,Arial,sans-serif;
  color:{BODY}; -webkit-print-color-adjust:exact; print-color-adjust:exact;
}}
.page{{
  width:210mm; min-height:296mm; padding:20mm 18mm 16mm; position:relative;
  page-break-after:always;
  background:linear-gradient(165deg,#ffffff 0%,#f7f8fe 55%,#eef0fe 100%);
}}
.page:last-child{{page-break-after:auto;}}
h1,h2,h3,h4{{font-family:'Syne',"Helvetica Neue",sans-serif;color:{INK};
  letter-spacing:-.015em;margin:0;}}
h2{{font-size:21pt;line-height:1.12;margin:0 0 4mm;}}
h3{{font-size:13pt;margin:7mm 0 2.5mm;}}
h4{{font-size:11pt;margin:5mm 0 1.5mm;}}
p{{margin:0 0 3mm;}}
.mono{{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;}}
.dim{{color:{MUTED};}}
strong{{color:{INK};}}

/* running header + footer */
.rh{{position:absolute;top:9mm;left:18mm;right:18mm;display:flex;
  justify-content:space-between;align-items:center;
  border-bottom:.6pt solid {RULE};padding-bottom:2.5mm;}}
.rh .brand{{display:flex;align-items:center;gap:2.2mm;}}
.rh img{{height:6.2mm;width:auto;}}
.rh .wm{{font-family:'Syne',sans-serif;font-size:10.5pt;color:{INK};
  letter-spacing:-.01em;}}
.rh span.sec{{font-family:'JetBrains Mono',monospace;font-size:6.6pt;color:{MUTED};
  letter-spacing:.14em;text-transform:uppercase;}}
.rf{{position:absolute;bottom:9mm;left:18mm;right:18mm;display:flex;
  justify-content:space-between;font-family:'JetBrains Mono',monospace;
  font-size:6.6pt;color:{MUTED};border-top:.6pt solid {RULE};padding-top:2mm;}}

/* cover */
.cover{{background:linear-gradient(160deg,{INK} 0%,#1a0a3e 55%,{INDIGO_D} 100%);
  color:#fff;padding:0;display:flex;flex-direction:column;}}
.cover .inner{{padding:30mm 18mm 18mm;flex:1;display:flex;flex-direction:column;}}
.cover h1{{font-size:40pt;line-height:1.02;color:#fff;margin:0 0 6mm;}}
.cover .sub{{font-size:13pt;color:#c9c4f5;max-width:130mm;line-height:1.5;}}
.cover .mk{{margin-bottom:12mm;}}
.cover .mk svg{{width:22mm;height:22mm;}}
.cover .meta{{margin-top:auto;border-top:.8pt solid rgba(255,255,255,.22);
  padding-top:5mm;display:flex;gap:14mm;font-family:'JetBrains Mono',monospace;
  font-size:8pt;color:#b9b3ef;}}
.cover .meta b{{display:block;color:#fff;font-size:9pt;margin-top:1mm;
  font-family:'Helvetica Neue',sans-serif;}}
.cover .strip{{height:9mm;background:linear-gradient(90deg,{INDIGO},{LILAC},#fff);}}

/* components */
.lead{{font-size:12pt;line-height:1.55;color:{INK};margin:0 0 5mm;}}
.fig{{margin:5mm 0;page-break-inside:avoid;}}
.figcap{{font-size:8.2pt;color:{MUTED};margin-top:1.5mm;font-style:italic;}}
.box{{background:rgba(255,255,255,.80);
  border:0.6pt solid rgba(255,255,255,.9);border-left:2.6pt solid {INDIGO};
  padding:4mm 5mm;margin:4mm 0;page-break-inside:avoid;border-radius:0 5pt 5pt 0;
  box-shadow:0 0.8pt 0 rgba(49,46,129,.10), inset 0 0.6pt 0 rgba(255,255,255,.95);}}
.box.warn{{border-left-color:{WARN};
  background:rgba(253,246,236,.82);}}
.box.bad{{border-left-color:{BAD};
  background:rgba(253,240,243,.82);}}
.box.ok{{border-left-color:{OK};
  background:rgba(238,248,242,.82);}}
.box h4{{margin:0 0 1.5mm;font-size:10.5pt;}}
.box p{{margin:0 0 2mm;}} .box p:last-child{{margin:0;}}
.jargon{{border:0.6pt solid rgba(255,255,255,.9);border-radius:5pt;padding:3.2mm 4mm;
  margin:3mm 0;page-break-inside:avoid;
  background:rgba(255,255,255,.78);
  box-shadow:0 0.8pt 0 rgba(49,46,129,.08), inset 0 0.6pt 0 rgba(255,255,255,.95);}}
.jargon b{{font-family:'JetBrains Mono',monospace;font-size:9pt;color:{INDIGO_D};}}
table{{width:100%;border-collapse:separate;border-spacing:0;font-size:9pt;
  margin:3.5mm 0;page-break-inside:avoid;border-radius:5pt;overflow:hidden;
  box-shadow:0 0.8pt 0 rgba(49,46,129,.12);}}
th{{text-align:left;color:#fff;padding:2.4mm 3mm;
  background:linear-gradient(135deg,{INK},{INDIGO_D});
  font-family:'JetBrains Mono',monospace;font-size:7.4pt;letter-spacing:.1em;
  text-transform:uppercase;font-weight:500;}}
td{{padding:2.3mm 3mm;border-bottom:.5pt solid rgba(221,222,245,.8);vertical-align:top;
  background:rgba(255,255,255,.62);}}
tr:last-child td{{border-bottom:none;}}
td.n{{font-family:'JetBrains Mono',monospace;white-space:nowrap;}}
/* SCOPED to table cells and spans on purpose. Bare .ok/.bad/.warn also matched
   .box.bad / .box.warn and recoloured every word inside those callouts — the whole
   "why the toll changes everything" panel rendered crimson. Specificity collisions
   like this are invisible until you look at the render. */
td.ok,span.ok{{color:{OK};}}
td.bad,span.bad{{color:{BAD};}}
td.warn,span.warn{{color:{WARN};}}
td.dim{{color:{MUTED};}}
.cards{{display:flex;gap:3mm;margin:4mm 0;page-break-inside:avoid;}}
.c{{flex:1;border:0.6pt solid rgba(255,255,255,.9);border-top:2.2pt solid {INDIGO};
  border-radius:5pt;padding:3.5mm;
  background:rgba(255,255,255,.82);
  box-shadow:0 0.8pt 0 rgba(49,46,129,.10), inset 0 0.6pt 0 rgba(255,255,255,.95);}}
.c h5{{margin:0 0 1mm;font-family:'Syne',sans-serif;font-size:9.6pt;color:{INK};}}
.c p{{margin:0;font-size:8.4pt;line-height:1.45;color:{BODY};}}
.c .pm{{font-family:'JetBrains Mono',monospace;font-size:7.4pt;color:{MUTED};
  margin-top:2mm;display:block;line-height:1.5;}}
ol.steps{{padding-left:0;list-style:none;counter-reset:st;margin:3mm 0;}}
ol.steps li{{counter-increment:st;padding:2.4mm 0 2.4mm 11mm;position:relative;
  border-bottom:.5pt solid {RULE};font-size:9.6pt;}}
ol.steps li:last-child{{border-bottom:none;}}
ol.steps li::before{{content:counter(st);position:absolute;left:0;top:2.4mm;
  width:7mm;height:7mm;border-radius:50%;background:{INDIGO};color:#fff;
  font-family:'JetBrains Mono',monospace;font-size:8pt;display:flex;
  align-items:center;justify-content:center;}}
ol.steps b{{color:{INK};}}
.kv{{display:flex;justify-content:space-between;border-bottom:.5pt dotted {RULE};
  padding:1.4mm 0;font-size:9pt;}}
.kv .v{{font-family:'JetBrains Mono',monospace;color:{INK};}}
"""

    MESH = ("<svg viewBox='0 0 210 297' preserveAspectRatio='none'>"
            "<defs>"
            "<radialGradient id='m1' cx='.5' cy='.5' r='.5'>"
            "<stop offset='0%' stop-color='#818cf8' stop-opacity='.20'/>"
            "<stop offset='100%' stop-color='#818cf8' stop-opacity='0'/></radialGradient>"
            "<radialGradient id='m2' cx='.5' cy='.5' r='.5'>"
            "<stop offset='0%' stop-color='#4f46e5' stop-opacity='.13'/>"
            "<stop offset='100%' stop-color='#4f46e5' stop-opacity='0'/></radialGradient>"
            "</defs>"
            "<ellipse cx='196' cy='26' rx='62' ry='62' fill='url(#m1)'/>"
            "<ellipse cx='12' cy='232' rx='54' ry='54' fill='url(#m2)'/>"
            "</svg>")

    def page(inner, num, title, cover=False):
        if cover:
            return f'<div class="page cover">{inner}</div>'
        return f"""<div class="page">
  <div class="mesh">{MESH}</div>
  <div class="rh">
    <div class="brand"><img src="{logo}"/><span class="wm">TradePilot</span></div>
    <span class="sec">{title}</span>
  </div>
  {inner}
  <div class="rf"><span>TradePilot — how the system works</span><span>{num}</span></div>
</div>"""

    P = []

    # ── COVER ───────────────────────────────────────────────────────────────
    P.append(page(f"""
  <div class="inner">
    <div class="mk">{mark}</div>
    <h1>How TradePilot<br/>Works</h1>
    <p class="sub">A robot team that watches 889 companies at once, decides which
    two are worth buying today, and never blinks. Written so that it makes sense
    even if you have never bought a share in your life.</p>
    <div class="meta">
      <div>PREPARED BY<b>Soumya Swain</b></div>
      <div>DATE<b>26 August 2026</b></div>
      <div>STATUS<b>Paper trading — the agents now trade on their own</b></div>
    </div>
  </div>
  <div class="strip"></div>""", 0, "", cover=True))

    # ── 1. THE BASICS ───────────────────────────────────────────────────────
    P.append(page(f"""
  <h2>First, the five words you need</h2>
  <p class="lead">Everything in this document is built out of five ideas. If you
  understand these, you will understand the whole system.</p>

  <div class="jargon"><b>SHARE</b> — A company splits itself into millions of tiny
  pieces. One piece is a share. If you own one share of a company worth ₹400 a share,
  you own ₹400 of that company. Buy it at ₹400, sell it at ₹406, and you made ₹6.</div>

  <div class="jargon"><b>THE MARKET</b> — A giant public auction where about 900 Indian
  companies have their shares bought and sold. It runs 9:15am to 3:30pm, Monday to
  Friday. Prices change several times <em>per second</em> because thousands of people
  are bidding at once.</div>

  <div class="jargon"><b>THE TOLL</b> — Every time you buy and then sell, you pay fees
  and government taxes. For us that is <span class="mono">0.106%</span> of the money
  involved. Trade ₹10,000 and it costs you about ₹10.60 — <em>whether you win or
  lose</em>. This one number is the villain of the entire story.</div>

  <div class="jargon"><b>A LEVEL</b> — A specific price that lots of people are
  watching, like yesterday's lowest price. Prices tend to do something interesting
  when they arrive at one — bounce off it, or break through it. Levels are where our
  system pays attention.</div>

  <div class="jargon"><b>PAPER TRADING</b> — Playing the whole game with fake money to
  see whether the plan works, before risking real money. Everything in this document
  is currently paper. Real money starts Wednesday, with ₹3,000.</div>""", 2, "The basics"))

    P.append(page(f"""
  <h2>Why the toll changes everything</h2>
  <p class="lead">Most explanations of trading talk about being right more often than
  you are wrong. That is not the hard part.</p>

  <p>The hard part is that <strong>you must be right by more than 0.106% every single
  time</strong> — otherwise you go slowly broke while technically "winning" more often
  than you lose. Being right is not enough. You have to be right by <em>enough</em>.</p>

  <div class="box bad">
    <h4>Ten famous ideas. All ten lost money.</h4>
    <p>We tested ten well-known trading ideas against real market history —
    <strong>145,500 simulated trades</strong> across 201 companies. Not opinions:
    measurements.</p>
    <p>The best idea earned <span class="mono">0.051%</span> per trade. The toll is
    <span class="mono">0.106%</span>. So the single best-performing famous strategy
    still lost about half the toll on every trade it took. That is the problem
    TradePilot exists to solve, and it is why the system spends most of its effort
    <em>refusing</em> trades.</p>
  </div>

  <div class="fig">{cost_svg()}
    <div class="figcap">What each strategy earned on an average trade. The red line is
    the toll — every bar has to reach it to break even, and not one of them does. The
    best famous idea falls short by 0.015% per trade; trend following falls short by
    0.145%. That picture is the entire difficulty of this business.</div>
  </div>

  <div class="box">
    <h4>So what is left?</h4>
    <p>If the famous ideas do not work, the answer is not a cleverer idea. It is to be
    far more selective about <em>when</em> to trade at all — and to find something that
    holds up when everything else is tested honestly. We found exactly one such thing,
    and it is on page 8.</p>
  </div>""", 3, "The basics"))

    # ── 2. WHAT THE SYSTEM DOES ─────────────────────────────────────────────
    P.append(page(f"""
  <h2>What the system actually does</h2>
  <p class="lead">Imagine a huge marketplace with 889 shops. Every shop's price
  changes every few seconds. You have enough money to buy from two shops today. Which
  two, and when exactly?</p>

  <p>No human can watch 889 price boards at once. So TradePilot uses two different
  kinds of worker, because the job is really two jobs:</p>

  <div class="cards">
    <div class="c"><h5>4 Scouts</h5>
      <p><strong>Broad and shallow.</strong> They walk the entire market once every
      minute and glance at all 889 shops. They cannot study any one shop closely —
      but nothing escapes them.</p>
      <span class="pm">every 60 seconds<br/>889 companies<br/>4 numbers each</span></div>
    <div class="c"><h5>20 Watchers</h5>
      <p><strong>Narrow and deep.</strong> Each one stands in front of exactly one
      shop and stares at its price board without blinking. It knows that shop
      perfectly — and is blind to the other 888.</p>
      <span class="pm">every price change<br/>1 company each<br/>thousands of looks/min</span></div>
    <div class="c"><h5>1 Judge</h5>
      <p><strong>Slow and careful.</strong> Only called when a watcher raises its
      hand. Looks at the actual chart, asks six questions, and either approves a
      trade or refuses it.</p>
      <span class="pm">only on request<br/>~seconds per decision<br/>can say no</span></div>
  </div>

  <p>The scouts decide <strong>what to look at</strong>. The watchers decide
  <strong>when something happened</strong>. The judge decides <strong>whether to
  actually buy</strong>. None of them can do the others' job, and that is the point —
  a scout that tried to watch closely would see almost nothing, and a watcher that
  tried to scan everything would notice nothing in time.</p>""", 4, "What it does"))

    P.append(page(f"""
  <h2>889 companies in, 2 trades out</h2>
  <p class="lead">Every layer below is a filter, and each one throws work away. These
  numbers come from a real scan on 24 August 2026 — they are not an illustration.</p>

  <div class="fig">{funnel_svg()}
    <div class="figcap">Read it top to bottom. The whole market enters at the top; two
    trades leave at the bottom. The system's main job is saying no.</div>
  </div>

  <table>
    <thead><tr><th>Stage</th><th>What gets removed</th><th>Why</th></tr></thead>
    <tbody>
      <tr><td class="n">938 → 889</td><td>Funds and baskets</td>
        <td>These are bundles of many companies, not companies. Five gold funds once filled our shortlist and looked like five separate opinions — they were one opinion counted five times.</td></tr>
      <tr><td class="n">889 → 437</td><td>Too expensive, too quiet, or frozen</td>
        <td>Shares costing more than ₹600 we cannot size properly. Companies barely traded today would move against us when we buy. And a share frozen at its daily limit has nobody to sell it to us.</td></tr>
      <tr><td class="n">437 → 60</td><td>Nothing interesting today</td>
        <td>At least one of the four scouts has to find a reason.</td></tr>
      <tr><td class="n">60 → 20</td><td>Not the strongest reasons</td>
        <td>We only have twenty watchers.</td></tr>
      <tr><td class="n">20 → 2</td><td>The moment never arrived</td>
        <td>Most watched companies never trigger anything worth acting on. That is normal and expected.</td></tr>
    </tbody>
  </table>""", 5, "The funnel"))

    # ── 3. THE SCOUTS ───────────────────────────────────────────────────────
    P.append(page(f"""
  <h2>The four scouts, and what each one hunts</h2>
  <p class="lead">Four scouts, not one — and deliberately four <em>different</em>
  ones. If all four looked for the same thing, we would have one scout at four times
  the cost. Each one is built to notice what the other three physically cannot see.</p>

  <div class="cards">
    <div class="c"><h5>1 · Trend</h5>
      <p>Looks for companies that have been climbing steadily for weeks — but have
      <em>paused</em> today. Like a strong runner catching their breath.</p>
      <span class="pm">rising 20 &amp; 50 day averages<br/>higher highs, higher lows<br/>NOT up more than 4% today</span></div>
    <div class="c"><h5>2 · Flow</h5>
      <p>Looks for unusually heavy buying and selling versus that company's own
      normal. Doesn't care which direction. This is the "something is happening
      here" scout.</p>
      <span class="pm">at least 1.8× normal volume<br/>measured as a rate, not a total<br/>fires before price moves</span></div>
    <div class="c"><h5>3 · Level</h5>
      <p>Looks for prices sitting right on top of an important number — a 52-week
      high, yesterday's close, a round number like ₹500.</p>
      <span class="pm">within 0.6% of a level<br/>52-week high scores highest<br/>middle of nowhere = ignored</span></div>
    <div class="c"><h5>4 · Reversal</h5>
      <p>Looks for good companies that have been beaten down for five days and are
      just starting to bounce. The Trend scout rejects every single one of these.</p>
      <span class="pm">down more than 3% over 5 days<br/>bounce already starting<br/>still above its 200-day average</span></div>
  </div>

  <p>The Reversal scout is the clearest illustration of why four are needed. It hunts
  companies that have been <em>falling</em>. The Trend scout rejects every one of those
  automatically. Neither is wrong — they are looking for different opportunities, and a
  single combined scout would simply miss one of them.</p>""", 6, "The scouts"))

    P.append(page(f"""
  <h2>How a scout turns a company into a score</h2>
  <p class="lead">Each scout gives every company a score between 0 and 1. It starts
  from a base number and then adds or subtracts points for specific, measurable facts —
  no opinions anywhere. Here is the Trend scout in full. The other three work the
  same way.</p>

  <table>
    <thead><tr><th>What it checks</th><th>Effect on score</th><th>Why</th></tr></thead>
    <tbody>
      <tr><td>Price above its 20-day and 50-day average</td><td class="n">required</td><td>If this fails, it isn't a trend at all</td></tr>
      <tr><td>Today's move outside −2% to +4%</td><td class="n bad">rejected outright</td><td>Crashing or already exploded — both are bad entries</td></tr>
      <tr><td>Starting score</td><td class="n">0.30</td><td>—</td></tr>
      <tr><td>Making higher highs AND higher lows</td><td class="n ok">+0.25</td><td>The textbook shape of a healthy climb</td></tr>
      <tr><td>Above its 200-day average</td><td class="n ok">+0.10</td><td>Healthy over the long run, not just recently</td></tr>
      <tr><td>Up more than 5% over 20 days</td><td class="n ok">+0.10</td><td>The climb is real, not noise</td></tr>
      <tr><td>Sitting right on its 20-day average</td><td class="n ok">+0.20</td><td>This is the pause we want to buy</td></tr>
      <tr><td>Already up more than 3% today</td><td class="n bad">−0.30</td><td>We are late. Chasing loses money.</td></tr>
    </tbody>
  </table>

  <div class="box warn">
    <h4>Why we punish a stock for going up</h4>
    <p>This surprises people. Surely a stock rising fast is a <em>good</em> sign?</p>
    <p>Not within a single day. We measured this over 145,500 trades: buying in the
    direction of the day's move <strong>lost</strong> 0.039%, while buying against it
    gained 0.003%. Within one day, Indian shares tend to snap back rather than run.
    So we look for strong companies that are <em>resting</em>, never ones already flying.</p>
    <p>This is a good example of how the system is built: a rule that sounds wrong,
    kept because the measurement says so.</p>
  </div>""", 7, "The scouts"))

    # ── 4. CONFLUENCE ───────────────────────────────────────────────────────
    P.append(page(f"""
  <h2>The one thing that actually worked</h2>
  <p class="lead">We tested ten well-known trading ideas. Nine of them were somewhere
  between useless and harmful. But one finding survived every test we threw at it, and
  it is the reason the whole system is built the way it is.</p>

  <h3>When separate scouts agree, the odds improve — every time</h3>

  <div class="fig">{confluence_svg()}
    <div class="figcap">Each point is thousands of real trades. On the left: only one
    scout was interested, and those trades lost badly. On the right: seven independent
    signals agreed, and those trades made money. The line climbs without a single dip —
    that consistency is what makes it trustworthy.</div>
  </div>

  <p>Think about why this makes sense. If one friend tells you a shop is worth visiting,
  they might be wrong, or biased, or just excited. If four friends who went there for
  <em>completely different reasons</em> all say it independently — a busy queue, a
  discount sign, a good smell, a familiar face — you should probably go.</p>

  <p>That is exactly what the scout board does. The four scouts never talk to each
  other. They look at different things entirely. When two or three of them
  independently land on the same company, that agreement is worth more than any single
  scout being extremely confident.</p>""", 8, "Agreement"))

    P.append(page(f"""
  <h2>Agreement, made into a rule</h2>
  <p class="lead">Because agreement is the only thing we proved, the system is built
  to reward it directly — and getting that right took a correction.</p>

  <div class="box ok">
    <h4>So agreement beats enthusiasm — and we had to say so explicitly</h4>
    <p>We originally combined the four scores into one number with a formula, hoping
    agreement would come out naturally. It nearly worked. Then we checked, and found a
    case where a company all <em>three</em> scouts liked was rejected in favour of one
    that two scouts liked — losing by <span class="mono">0.009</span> points.</p>
    <p>A formula was quietly throwing away the one thing we had actually proved. So we
    stopped being clever and wrote the rule down plainly: <strong>more scouts agreeing
    wins, full stop.</strong></p>
  </div>

  <table>
    <thead><tr><th>Scouts agreeing</th><th>Score range</th><th>Companies on 24 Aug</th><th>What it means</th></tr></thead>
    <tbody>
      <tr><td class="n">3</td><td class="n ok">0.931 – 0.964</td><td class="n">3</td><td>Rare and strong. Watch these.</td></tr>
      <tr><td class="n">2</td><td class="n warn">0.553 – 0.850</td><td class="n">26</td><td>Worth a watcher.</td></tr>
      <tr><td class="n">1</td><td class="n dim">0.492 – 0.600</td><td class="n">31</td><td>Interesting, not convincing.</td></tr>
    </tbody>
  </table>

  <p>Notice the gaps between those bands. A company cannot drift from "two scouts" to
  "three scouts" by a rounding error — a third scout has to genuinely find a reason.
  That gap is deliberate: it means the system only changes its mind when something
  real has changed, not when a number wobbles.</p>""", 9, "Agreement"))

    # ── 5. AGENT FLOOR ──────────────────────────────────────────────────────
    P.append(page(f"""
  <h2>The agent floor, in detail</h2>
  <p class="lead">This is the newest part of the system and the part people ask about
  most. Twenty independent agents, each assigned one company, each watching it
  continuously for the entire trading day.</p>

  <h3>Why not just have one clever AI watch everything?</h3>
  <p>Because of speed. An AI that "thinks" takes a few seconds to answer. A price move
  worth catching also takes a few seconds. By the time the AI finished thinking, the
  moment would be gone — every time.</p>

  <p>So we split the job the way a real trader actually works. A trader does not
  re-analyse everything every second. They <strong>decide their important prices in the
  morning</strong>, then simply <strong>watch for those prices to arrive</strong>. That
  is two very different activities, and only the second one needs to be fast.</p>

  <div class="fig">{agent_anatomy_svg()}
    <div class="figcap">One agent. On the left, the small set of facts it memorises at
    9:16am. On the right, the only five events that make it interrupt anyone. Everything
    else it sees, it silently ignores.</div>
  </div>""", 10, "The agent floor"))

    P.append(page(f"""
  <h2>Fast eyes, slow judgement</h2>
  <p class="lead">The whole design rests on separating two things people usually lump
  together: <em>noticing</em> that something happened, and <em>deciding</em> what to do
  about it.</p>

  <table>
    <thead><tr><th>Layer</th><th>Speed</th><th>What it does</th><th>Runs how often</th></tr></thead>
    <tbody>
      <tr><td><strong>Fast</strong> — plain code</td><td class="n">microseconds</td>
        <td>Compares the live price against the agent's memorised levels. No thinking, just arithmetic.</td>
        <td class="n">every price change</td></tr>
      <tr><td><strong>Slow</strong> — judgement</td><td class="n">seconds</td>
        <td>Reads the actual chart, asks six questions, approves or refuses the trade.</td>
        <td class="n">only when a hand goes up</td></tr>
    </tbody>
  </table>

  <div class="box">
    <h4>The point of the split</h4>
    <p>Thinking is expensive and slow. Arithmetic is free and instant. By letting cheap
    arithmetic decide <em>when</em> something matters, and spending expensive judgement
    only on those rare moments, we can afford twenty agents watching continuously —
    and still respond faster than a human could.</p>
  </div>

  <h3>The five things that make an agent speak</h3>
  <table>
    <thead><tr><th>Trigger</th><th>In plain words</th><th>Exact threshold</th></tr></thead>
    <tbody>
      <tr><td>Level touch</td><td>Price has arrived at one of the important prices it memorised</td><td class="n">within 0.08%</td></tr>
      <tr><td>Sweep and reclaim</td><td>Price dipped below an important price and jumped straight back above it</td><td class="n">dip &gt;0.05%, then recover</td></tr>
      <tr><td>Fast move</td><td>Price is moving unusually quickly right now</td><td class="n">0.25% in a minute</td></tr>
      <tr><td>Volume burst <em>(retired)</em></td><td>A sudden rush of buying and selling</td><td class="n">was 3× — see below</td></tr>
      <tr><td class="bad">Invalidation</td><td>A trade we already hold has gone wrong</td><td class="n">instant, highest priority</td></tr>
    </tbody>
  </table>

  <p class="dim">After any one of these fires, that agent stays quiet about the same
  kind of event for three minutes. Without that pause, a single jumpy company could
  raise its hand hundreds of times and drown out the other nineteen.</p>

  </div>""", 11, "The agent floor"))

    P.append(page(f"""
  <h2>One trigger was retired — on evidence</h2>
  <p class="lead">Every alert type was scored against a control: what the same stock
  did after a <em>random</em> minute of the same day. That control is what separates a
  real signal from a stock that was simply moving anyway.</p>

  <div class="tw"><table>
    <thead><tr><th>Alert</th><th>Fired</th><th>Move after vs random</th><th>Verdict</th></tr></thead>
    <tbody>
      <tr><td>Dipped below, jumped back</td><td class="n">118</td>
        <td class="n ok">+0.278pp</td><td class="ok">best by 3×</td></tr>
      <tr><td>At an important number</td><td class="n">473</td>
        <td class="n ok">+0.085pp</td><td>keeps its place</td></tr>
      <tr><td>Moving fast</td><td class="n">432</td>
        <td class="n ok">+0.068pp</td><td>keeps its place</td></tr>
      <tr><td>Volume burst</td><td class="n">540</td>
        <td class="n bad">−0.014pp</td><td class="bad">retired</td></tr>
    </tbody>
  </table></div>

  <div class="box bad">
    <h4>The loudest one was the worst one</h4>
    <p>Every trigger was scored against a control — what the same stock did after a
    <em>random</em> minute of the same day. Four beat the control. <strong>Volume burst
    did not:</strong> it fired more than any other (540 times in one session) and
    predicted <em>less</em> than random. It was switched off, removing about a third of
    all alerts and losing nothing that had ever been measured.</p>
    <p>It is disabled rather than deleted, so the decision can be reversed and the
    evidence stays readable.</p>
  </div>

  <div class="box">
    <h4>An open puzzle worth stating</h4>
    <p>The best-performing alert — <em>dipped below, jumped back</em> — scored well
    here but scored <strong>badly</strong> in our older historical testing. Both were
    measured properly. Either watching live prices tick by tick catches something the
    older method flattened out, or 118 examples is simply too few to trust yet. We do
    not know which, and it matters before anything else is built on top of it.</p>
  </div>""", 11, "The agent floor"))

    # ── 6. AGENT DAY / REASSIGNMENT ─────────────────────────────────────────
    P.append(page(f"""
  <h2>One agent's working day</h2>

  <ol class="steps">
    <li><b>9:00am — Homework.</b> Before the market opens, the system studies about 320
    companies: their averages, their typical daily swing, their 52-week high and low.</li>
    <li><b>9:16am — Assignment.</b> The scouts publish their ranked list. The top 20
    companies each get an agent. Each agent memorises four or five important prices for
    its company — yesterday's high and low, today's average, the nearest round number.</li>
    <li><b>All day — Watching.</b> The agent receives every single price change from
    the exchange and compares it to its memorised levels. Thousands of comparisons per
    minute. It does not get bored, distracted or tired.</li>
    <li><b>Whenever it matters — Raising a hand.</b> If one of the five trigger
    conditions is met, the agent escalates: it records what happened, at what price, and
    at what time, and asks for judgement.</li>
    <li><b>Every 2 minutes — Possible reassignment.</b> The scouts are still scanning.
    If a much better company appears, an <em>idle</em> agent is moved to it.</li>
    <li><b>3:30pm — Reporting.</b> Every escalation, every reassignment, and every
    near-miss is written to a file so we can check the next morning whether the agents
    were actually useful.</li>
  </ol>

  <h3>The three rules that stop agents wandering off</h3>
  <p>Moving agents around sounds obviously good, but done carelessly it destroys the
  system. Three rules prevent that:</p>

  <div class="cards">
    <div class="c"><h5>Never abandon a trade</h5>
      <p>An agent holding an open position cannot be moved, no matter how attractive
      another company looks. You do not walk away from money you have already committed.</p></div>
    <div class="c"><h5>Ten minutes minimum</h5>
      <p>An agent must watch a company for at least 10 minutes before it can be moved.
      Two of its five triggers need 30 and 60 price-changes of history — an agent moved
      constantly would be permanently blind.</p></div>
    <div class="c"><h5>Four moves maximum</h5>
      <p>At most four agents change company in any one cycle, and the newcomer must be
      clearly better, not marginally. Otherwise the floor would churn all day and settle
      on nothing.</p></div>
  </div>

  <div class="box warn">
    <h4>What we are honestly unsure about</h4>
    <p>Nobody has run this live yet. Today is the first real session. We do not know
    whether 20 agents will produce 15 useful alerts or 500 useless ones — so the system
    records every alert <em>and</em> every alert it nearly raised. If the settings are
    wrong, the log will say so, and we will change them rather than guess again.</p>
  </div>""", 12, "An agent's day"))

    # ── 7. WORKED EXAMPLE ───────────────────────────────────────────────────
    P.append(page(f"""
  <h2>The agents now trade on their own</h2>
  <p class="lead">Until 26 August the agents could only <em>shout</em>. One would spot
  something and write it down — 1,563 times in a single session — and then nothing
  happened. Nobody bought anything. A very attentive guard who was never allowed to
  open a door.</p>

  <p>They now act without asking anyone. Fake money, real prices, real timing — so at
  the end of the day we can ask <strong>"was that a good idea?"</strong> instead of
  "I wonder what would have happened."</p>

  <h3>Only one kind of alert is allowed to start a trade</h3>
  <p>Buying needs a <em>direction</em>, and only one of the four alerts implies one.</p>
  <div class="tw"><table>
    <thead><tr><th>Alert</th><th>Does it tell you which way?</th></tr></thead>
    <tbody>
      <tr><td><strong>Dipped below a line, jumped back</strong></td>
        <td class="ok">Yes — buyers defended that price. Buy.</td></tr>
      <tr><td>Price is at an important number</td>
        <td>No — it says <em>where</em>, not which way</td></tr>
      <tr><td>Moving fast</td>
        <td>No — and our own data says that within a day, shares that shoot up drift back</td></tr>
      <tr><td>Volume burst</td><td>No — and retired anyway</td></tr>
    </tbody>
  </table></div>

  <div class="box ok">
    <h4>Where the exit price comes from — it is not a guess</h4>
    <p>Most people pick a stop loss arbitrarily: "I'll sell if I lose 1%." Why 1%? No
    reason.</p>
    <p>Ours writes itself. The trade's whole logic was <em>"price dipped and buyers
    defended it."</em> So if price goes back below that dip, the story we believed is
    simply false. <strong>That exact price is the exit.</strong> And because it is a
    real price, the arithmetic becomes honest: risking ₹100, we aim to make ₹150 —
    with the full ₹0.106 per ₹100 of fees already charged against it.</p>
  </div>

  <div class="box warn">
    <h4>What this is, and what it is not</h4>
    <p>It is <strong>not</strong> a money-making machine, and I am not claiming it is
    profitable. Nothing we have measured reliably predicts direction.</p>
    <p>It is a <strong>measuring instrument</strong>. It turns "the agent noticed
    something" into "here is exactly what happened next, priced honestly" — the one
    thing 1,563 unanswered alerts could never give us. It also records every trade it
    <em>refused</em> and why, so "no trades today" can never hide a setting that is
    silently rejecting everything.</p>
  </div>""", 15, "The agents trade"))

    P.append(page(f"""
  <h2>Watch one trade happen, step by step</h2>
  <p class="lead">This is the clearest way to understand the whole system: follow a
  single company through one morning, from the agent's first glance to the order.</p>

  <div class="fig">{tick_walk_svg()}
    <div class="figcap">A company's price through one morning. The two dashed lines are
    levels the agent memorised at 9:16am. Everything the agent does is a reaction to
    those lines.</div>
  </div>

  <div class="box">
    <h4>Why "sweep and reclaim" is worth waking someone up for</h4>
    <p>Many people leave a standing instruction with their broker: "sell my shares
    automatically if the price drops below ₹411." When the price does dip under ₹411,
    all of those instructions fire at once and shove the price down briefly.</p>
    <p>If the price then climbs straight back above ₹411, it tells you something
    specific: those forced sellers are finished, and buyers were waiting underneath the
    whole time. The dip on its own means nothing. <strong>The recovery is the
    signal</strong> — which is exactly why the agent stays silent at 11:02 and only
    speaks at 11:04.</p>
  </div>""", 13, "A trade, step by step"))

    P.append(page(f"""
  <h2>The same trade, minute by minute</h2>
  <p class="lead">Here is the identical sequence written out, so you can see how little
  the agent actually does — and how much of the day it spends deliberately silent.</p>

  <table>
    <thead><tr><th>Time</th><th>What happens</th><th>What the agent does</th></tr></thead>
    <tbody>
      <tr><td class="n">9:16</td><td>Assigned to this company by the scouts — Trend and Level both flagged it</td>
        <td>Memorises: yesterday's low ₹411.00, today's average ₹414.50</td></tr>
      <tr><td class="n">9:30–10:40</td><td>Price drifts up and down between ₹411 and ₹416</td>
        <td class="dim">Nothing. Watches ~40,000 price changes, stays silent.</td></tr>
      <tr><td class="n">11:02</td><td>Price falls <em>below</em> ₹411 — under yesterday's low</td>
        <td>Notes it. Still silent — a break alone is not the signal.</td></tr>
      <tr><td class="n">11:04</td><td>Price jumps straight back <em>above</em> ₹411</td>
        <td class="ok"><strong>Raises its hand.</strong> This is the "sweep and reclaim" pattern.</td></tr>
      <tr><td class="n">11:04</td><td>Judgement is called</td>
        <td>Six questions asked. Where is price? At a level. What is the structure? Uptrend. What broke? Nothing. Where am I wrong? Below ₹410.90.</td></tr>
      <tr><td class="n">11:05</td><td>Approved — a trade card is sent to a phone</td>
        <td class="ok">Buy 14 shares at ₹414.40. Stop at ₹411.10. Target ₹420.60.</td></tr>
      <tr><td class="n">14:45</td><td>Either the target, the stop, or the clock ends it</td>
        <td>Position closed. Nothing is ever held overnight.</td></tr>
    </tbody>
  </table>

  <div class="box ok">
    <h4>Look at what the agent did NOT do</h4>
    <p>Between 9:30 and 10:40 it examined roughly forty thousand price changes and said
    nothing at all. It did not get bored, did not talk itself into a trade, and did not
    lower its standards because the morning was quiet.</p>
    <p>That patience is the actual product. Anyone can find reasons to buy. The
    difficult part — the part the toll punishes — is sitting still for four hours and
    acting only when a specific, pre-defined thing happens.</p>
  </div>""", 14, "A trade, minute by minute"))

    # ── 8. THE SIX QUESTIONS + MONEY ────────────────────────────────────────
    P.append(page(f"""
  <h2>The six questions before any money moves</h2>
  <p class="lead">An agent raising its hand is not permission to trade. Every candidate
  must survive six questions in order. Fail the first two and the answer is simply no.</p>

  <ol class="steps">
    <li><b>Where is the price right now?</b> Name the nearest important price above and
    below, with the distance to each. If we are in the middle of nowhere, there is no
    trade — the edge only exists at levels.</li>
    <li><b>What shape is the chart in?</b> Climbing, falling, or going sideways — and
    name the exact price that would prove it has changed. If you cannot name that price,
    there is no trade.</li>
    <li><b>What specific thing just happened?</b> "Dipped below yesterday's low and
    recovered." Not "it looks good." A feeling is not a trigger.</li>
    <li><b>What would prove me wrong?</b> An exact price, decided <em>before</em>
    buying. That price becomes the automatic exit, and the gap between it and the entry
    is exactly how much we can lose.</li>
    <li><b>How many separate reasons agree?</b> Count them. Fewer than four and the
    profit will not cover the toll.</li>
    <li><b>How much is there to win?</b> Distance to the next obstacle, divided by the
    amount at risk. Below 1.5 times, skip it.</li>
  </ol>

  <p class="dim">A confidence figure between 0 and 1 is stated, and anything under 0.6
  is skipped. <strong>A day with no trades at all is a perfectly good outcome</strong> —
  and often the correct one.</p>

  <div class="box">
    <h4>Question 4 is the one that protects the money</h4>
    <p>Deciding the exit price <em>before</em> buying sounds like a technicality. It is
    the single most important rule in the document. It converts "I hope this goes up"
    into "I lose exactly ₹X if I am wrong" — a known, bounded, survivable number.</p>
    <p>Everyone who blows up an account skipped question 4.</p>
  </div>""", 15, "The six questions"))

    P.append(page(f"""
  <h2>Where the money actually goes</h2>
  <p class="lead">We start with <strong>₹3,000</strong>. For trades opened and closed
  on the same day the broker lends four times that, so we control about ₹12,000 —
  split into two positions of ₹6,000 each.</p>

  <table>
    <thead><tr><th>Positions</th><th>Each</th><th>Most expensive share we can buy</th><th>Companies available</th><th>Cost per trade</th></tr></thead>
    <tbody>
      <tr><td class="n">1</td><td class="n">₹12,000</td><td class="n">₹1,200</td><td class="n">100%</td><td class="n">0.1060%</td></tr>
      <tr><td class="n ok">2 ← chosen</td><td class="n">₹6,000</td><td class="n">₹600</td><td class="n">82%</td><td class="n">0.1060%</td></tr>
      <tr><td class="n">3</td><td class="n">₹4,000</td><td class="n">₹400</td><td class="n bad">58%</td><td class="n">0.1060%</td></tr>
    </tbody>
  </table>

  <div class="box ok">
    <h4>Two positions cost exactly the same as one</h4>
    <p>Look at the last column: splitting the money changes nothing about the cost,
    because every fee is a straight percentage. So two positions are <strong>free
    diversification</strong> — and they double how much we learn per day, which matters
    when the plan is to judge this over ten sessions.</p>
    <p>Three would be free too, but the share price limit drops to ₹400 and we would
    lose 42% of the companies we can choose from. Two is the sweet spot.</p>
  </div>

  <div class="box warn">
    <h4>Why the price limit exists at all</h4>
    <p>With ₹6,000 you can buy 10 shares of a ₹600 company — or 2 shares of a ₹2,500
    company. With only 2 shares, you cannot size a position properly; you are stuck
    jumping in huge steps. We insist on at least 10 shares, and that single rule is what
    sets the ₹600 ceiling.</p>
  </div>""", 16, "Where the money goes"))

    # ── 9. OPTIONS + STATUS ─────────────────────────────────────────────────
    P.append(page(f"""
  <h2>The second experiment: options</h2>
  <p class="lead">Alongside buying shares, we are testing something different — and
  riskier — with a small, fixed amount.</p>

  <div class="jargon"><b>AN OPTION</b> — A ticket that says "I may buy the market at
  ₹24,250 before next Tuesday". If the market climbs well past that, the ticket becomes
  valuable. If it doesn't, the ticket expires and is worth exactly nothing. You can lose
  100% of what you paid — but you can never lose more than that.</div>

  <p>Options are attractive because a small amount of money can produce a large gain.
  They are dangerous because <strong>the most likely single outcome is losing
  everything you put in.</strong> That is why this lane is capped, is being tested on
  paper first, and must pass a gate before it ever sees real money.</p>

  <table>
    <thead><tr><th>Budget</th><th>Closest ticket we can afford</th><th>Cost</th><th>Fees as % of the trade</th></tr></thead>
    <tbody>
      <tr><td class="n">₹1,000</td><td class="n bad">far away — needs a huge move</td><td class="n">₹725</td><td class="n bad">6.5%</td></tr>
      <tr><td class="n ok">₹3,000</td><td class="n ok">very close to the current price</td><td class="n">₹2,532</td><td class="n ok">1.9%</td></tr>
    </tbody>
  </table>

  <p>This is the clearest argument for raising the amount from ₹1,000 to ₹3,000. At
  ₹1,000 we could only afford tickets so far from the current price that they were
  effectively lottery tickets. At ₹3,000 we can buy one that responds to ordinary market
  moves — and the fees drop from 6.5% to 1.9% of the trade.</p>

  <div class="box bad">
    <h4>Tomorrow is expiry day — so extra rules apply</h4>
    <p>Options have a deadline. Tomorrow is the deadline for this week's batch. On
    deadline day a ticket that is not clearly winning loses value very fast, and by
    3:30pm it is worthless with certainty.</p>
    <p>Our budget forces us onto this day — it is the only one where ₹3,000 buys a
    ticket close to the current price. So we guard it: <strong>no new tickets bought
    after 1:00pm</strong>, everything sold by <strong>3:00pm</strong>, and we only buy
    tickets that plenty of other people are trading, so there is always someone to sell
    back to.</p>
  </div>

  <div class="box">
    <h4>Why this lane is capped, and gated</h4>
    <p>It cannot spend real money until it has produced <strong>eight paper trades
    profitable after fees</strong>. So far: zero. That gate is not a formality — six
    earlier ideas here were killed by exactly this kind of pre-agreed test.</p>
  </div>""", 17, "Options"))

    P.append(page(f"""
  <h2>What we know, and what we don't</h2>
  <p class="lead">The most useful thing in this document is the honest list of what
  remains unproven. Every row below has a specific test attached, decided in advance,
  so that we cannot later argue ourselves into a favourable interpretation.</p>
  <table>
    <thead><tr><th>Question</th><th>How it gets answered</th><th>Where we are</th></tr></thead>
    <tbody>
      <tr><td>Do 20 agents produce useful alerts?</td><td>Alerts scored against a random-minute control</td><td class="ok">answered — 3 of 4 beat it, 1 retired</td></tr>
      <tr><td>Does acting on an alert make money?</td><td>Paper trades, priced with full fees</td><td class="bad">25 trades, −₹360, 32% win rate</td></tr>
      <tr><td>Should agents move companies mid-day?</td><td>Did companies moved <em>to</em> beat the ones left behind?</td><td class="warn">measured, not yet known</td></tr>
      <tr><td>Does reading charts beat pure arithmetic?</td><td>20 trades, profitable after costs, beating random picks</td><td class="bad">open</td></tr>
      <tr><td>Do options work at this size?</td><td>8 paper trades, profitable after ₹47 of fees</td><td class="bad">0 of 8</td></tr>
      <tr><td>Are the agents watching the right prices?</td><td>Compare each agent's memorised levels against the live ones</td><td class="bad">no — frozen at 9:16am, one drifted 10%</td></tr>
      <tr><td>Do real orders fill at the price we expect?</td><td>10 real sessions, fills within 0.15% of the plan</td><td class="bad">starts Wednesday</td></tr>
    </tbody>
  </table>

  <div class="box">
    <h4>The honest summary</h4>
    <p>We have built a system that watches the whole market properly, filters it down
    with rules we can defend, and refuses far more trades than it takes. We have proved
    that most popular trading ideas do not survive costs, and we have found one that
    does: independent agreement.</p>
    <p><strong>We have not yet proved that the finished system makes money.</strong>
    On its first day of trading on its own it lost ₹360 across 25 paper trades — and we
    then found that every agent had been watching prices frozen at 9:16am, one of them
    10% stale. So that loss is not yet a fair test of the idea; it was measured on a
    broken instrument, and that gets fixed before it is measured again.</p>
    <p>Every number here came from a measurement, and where we do not know something,
    this document says so.</p>
    <p>If someone shows you a trading system with no page like this one, that is the
    page they chose not to write.</p>
  </div>""", 18, "Status"))

    body = "".join(P)
    return f"<!doctype html><html><head><meta charset='utf-8'><title>TradePilot — How It Works</title><style>{css}</style></head><body>{body}</body></html>"


# ══════════════════════════════════════════════════════════════════════════════
async def render(html_path: Path, pdf_path: Path):
    from pyppeteer import launch
    br = await launch(executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      headless=True, args=["--no-sandbox", "--disable-gpu",
                                           "--font-render-hinting=none"])
    pg = await br.newPage()
    await pg.goto(f"file://{html_path}", waitUntil="networkidle0", timeout=60000)
    await asyncio.sleep(2)
    await pg.pdf({"path": str(pdf_path), "printBackground": True,
                  "preferCSSPageSize": True, "displayHeaderFooter": False,
                  "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}})
    await br.close()


async def measure(html_path: Path):
    """Report each page div's real height against the printable budget.

    A .page taller than the budget silently spills onto a second sheet — and because
    the running header and footer are positioned against the DIV, not the sheet, they
    land in the middle of the document. 18 sheets from 10 divs is what that looks
    like. Measuring beats guessing where to split.
    """
    from pyppeteer import launch
    br = await launch(executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                      headless=True, args=["--no-sandbox", "--disable-gpu"])
    pg = await br.newPage()
    await pg.goto(f"file://{html_path}", waitUntil="networkidle0", timeout=60000)
    await asyncio.sleep(1.5)
    rows = await pg.evaluate("""() => {
        const mm = 297 / document.querySelector('.page').getBoundingClientRect().height;
        return [...document.querySelectorAll('.page')].map((p,i) => {
            // .mesh is position:absolute inset:0, so it is ALWAYS 297mm tall and
            // would report every page as full. Measure content only.
            const kids = [...p.children].filter(c => !c.classList.contains('rh')
                                                  && !c.classList.contains('rf')
                                                  && !c.classList.contains('mesh'));
            const bottom = kids.length ? Math.max(...kids.map(c =>
                c.getBoundingClientRect().bottom)) : 0;
            const top = p.getBoundingClientRect().top;
            return {i: i, used: (bottom - top) * mm,
                    h2: (p.querySelector('h2')||{}).textContent || '(cover)'};
        });
    }""")
    await br.close()
    # The true content area is page height minus BOTH paddings: 296 - 20 - 16 = 260mm,
    # measured from the top of the content box. An earlier budget of 297-16 measured
    # from the page top and so declared pages "fitting" that were spilling a few
    # millimetres onto a second sheet — which is what produced the blank pages.
    # getBoundingClientRect() EXCLUDES the trailing margin of the last child, so a
    # page ending in a .box (margin 4mm) is ~4mm taller than measured and spills a
    # sliver onto a blank sheet. Hold a 6mm safety band rather than chase exact
    # margin arithmetic per element.
    BUDGET = 296 - 16 - 6      # content bottom, measured from page top
    print(f"  page budget ~{BUDGET:.0f}mm of content height")
    for r in rows:
        over = r["used"] - BUDGET
        flag = f"OVER by {over:5.0f}mm  -> spills to {1+math.ceil(over/BUDGET)} sheets" \
            if over > 0 else "fits"
        print(f"    p{r['i']+1:<3}{r['used']:6.0f}mm  {flag:<38}{r['h2'][:42]}")
    return rows


def qa(pdf_path: Path):
    from pypdf import PdfReader
    r = PdfReader(str(pdf_path))
    n = len(r.pages)
    print(f"  pages: {n}")
    bad = []
    for i, p in enumerate(r.pages):
        t = (p.extract_text() or "").strip()
        clean = t.replace(str(i + 1), "").strip()
        if len(clean) < 60 and i != 0:
            bad.append((i + 1, len(clean)))
    if bad:
        print(f"  WARNING near-blank pages: {bad}")
    else:
        print("  no near-blank pages")
    print(f"  size: {pdf_path.stat().st_size/1024:.0f} KB")
    return n


def shrink(pdf: Path):
    """Merge duplicated resources. Chrome embeds a SEPARATE font subset on every
    page rather than sharing one — 32 subsets across 20 pages, and ~5MB of a 6.6MB
    file. Ghostscript rewrites them as a single shared set."""
    import shutil, subprocess
    gs = shutil.which("gs")
    if not gs:
        print("  (ghostscript not found — skipping font de-duplication)")
        return
    tmp = pdf.with_suffix(".opt.pdf")
    before = pdf.stat().st_size
    r = subprocess.run([gs, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.7",
                        "-dPDFSETTINGS=/prepress", "-dNOPAUSE", "-dQUIET", "-dBATCH",
                        "-dSubsetFonts=true", "-dCompressFonts=true",
                        f"-sOutputFile={tmp}", str(pdf)], capture_output=True)
    if r.returncode == 0 and tmp.exists() and tmp.stat().st_size > 40_000:
        tmp.replace(pdf)
        print(f"  optimised: {before/1024:.0f}KB -> {pdf.stat().st_size/1024:.0f}KB")
    else:
        tmp.unlink(missing_ok=True)
        print(f"  optimisation skipped (gs rc={r.returncode})")


def main():
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    OUT_HTML.write_text(build_html())
    print(f"  html: {OUT_HTML}")
    loop = asyncio.get_event_loop()
    if "--measure" in sys.argv:
        loop.run_until_complete(measure(OUT_HTML))
        return
    loop.run_until_complete(render(OUT_HTML, OUT_PDF))
    print(f"  pdf : {OUT_PDF}")
    shrink(OUT_PDF)
    qa(OUT_PDF)


if __name__ == "__main__":
    main()
