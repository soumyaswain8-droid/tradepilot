#!/usr/bin/env python3
"""
build-winners-report — the candlestick evidence pack as a PDF.

Takes the twelve rendered charts and the mechanical candle analysis and produces a
document someone can check independently: chart, the breakout bar identified by rule
rather than by eye, the measured geometry beside its pattern name, the catalyst with
a source, and the count of times the SAME pattern appeared and failed.

WHY THE LAST NUMBER IS THE POINT. These twelve names were chosen by searching five
years for the biggest gains, so every pattern in them is conditioned on success. A
pack like this normally reads as "here is what works". It cannot say that. The only
unbiased figure in it is the false-breakout count, and the report leads with it.

Design system, fonts, logo and the render/QA pipeline are reused from build-explainer;
the CSS here is self-contained so that editing this file can never break that one.

    python3 brand/build-winners-report.py
    python3 brand/build-winners-report.py --measure     # page-height audit only
"""
from __future__ import annotations

import asyncio
import base64
import html
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "brand"))

import importlib.util as _ilu

_spec = _ilu.spec_from_file_location("bex", ROOT / "brand" / "build-explainer.py")
BEX = _ilu.module_from_spec(_spec)
_spec.loader.exec_module(BEX)

SRC = ROOT / "docs" / "research" / "overnight"
CHARTS = SRC / "charts"
ANALYSIS = SRC / "CANDLE-ANALYSIS.md"
OUT_HTML = ROOT / "brand" / "winners-report.html"
OUT_PDF = ROOT / "1cr-roadmap" / "TradePilot-Candlestick-Evidence.pdf"

INK = "#312e81"
INDIGO = "#4f46e5"
INDIGO_D = "#3730a3"
LILAC = "#a5b4fc"
MUTED = "#6b7280"
RULE = "rgba(49,46,129,.16)"
OK = "#16a34a"
BAD = "#dc2626"
WARN = "#d97706"


# ── minimal markdown -> html ────────────────────────────────────────────────────
# Deliberately small. The analysis file is machine-written to a known shape (H2 per
# symbol, one stats table, then prose), so a full parser would be more surface area
# than the job needs. Anything unrecognised passes through as a paragraph rather
# than being silently dropped.
def md_inline(s: str) -> str:
    s = html.escape(s)
    s = re.sub(r"`([^`]+)`", r'<code class="mono">\1</code>', s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<!\*)\*([^*]+)\*(?!\*)", r"<em>\1</em>", s)
    return s


def md_block(lines: list[str]) -> str:
    """Convert a run of markdown lines into HTML."""
    out, i = [], 0
    while i < len(lines):
        ln = lines[i].rstrip()
        if not ln.strip():
            i += 1
            continue
        # a markdown horizontal rule carries no meaning once each section owns its
        # own sheet, and printed literally it reads as a typo
        if re.fullmatch(r"\s*(-{3,}|\*{3,}|_{3,})\s*", ln):
            i += 1
            continue
        # table
        if ln.lstrip().startswith("|") and i + 1 < len(lines) and \
                set(lines[i + 1].replace("|", "").replace(" ", "")) <= set("-:"):
            head = [c.strip() for c in ln.strip().strip("|").split("|")]
            i += 2
            rows = []
            while i < len(lines) and lines[i].lstrip().startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            # A key-value table is written with empty headers in markdown. Rendering
            # the row anyway prints a bare purple bar above the table, which reads as
            # a rendering fault rather than a design choice.
            t = ['<table class="tbl">']
            if any(h.strip() for h in head):
                t.append("<thead><tr>")
                t += [f"<th>{md_inline(h)}</th>" for h in head]
                t.append("</tr></thead>")
            t.append("<tbody>")
            for r in rows:
                t.append("<tr>" + "".join(f"<td>{md_inline(c)}</td>" for c in r) + "</tr>")
            t.append("</tbody></table>")
            out.append("".join(t))
            continue
        # heading
        m = re.match(r"^(#{3,4})\s+(.*)$", ln)
        if m:
            lvl = len(m.group(1))
            out.append(f"<h{lvl}>{md_inline(m.group(2))}</h{lvl}>")
            i += 1
            continue
        # blockquote -> callout
        if ln.lstrip().startswith(">"):
            buf = []
            while i < len(lines) and lines[i].lstrip().startswith(">"):
                buf.append(lines[i].lstrip().lstrip(">").strip())
                i += 1
            out.append(f'<div class="box warn"><p>{md_inline(" ".join(buf))}</p></div>')
            continue
        # bullets
        if re.match(r"^\s*[-*]\s+", ln):
            buf = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i]):
                buf.append(re.sub(r"^\s*[-*]\s+", "", lines[i]).rstrip())
                i += 1
            out.append("<ul>" + "".join(f"<li>{md_inline(b)}</li>" for b in buf) + "</ul>")
            continue
        # paragraph
        buf = []
        while i < len(lines) and lines[i].strip() and \
                not lines[i].lstrip().startswith(("|", ">", "#")) and \
                not re.match(r"^\s*[-*]\s+", lines[i]):
            buf.append(lines[i].rstrip())
            i += 1
        out.append(f"<p>{md_inline(' '.join(buf))}</p>")
    return "".join(out)


def split_at_table(lines: list[str]) -> tuple[list[str], list[str]]:
    """Return (through the first table, everything after).

    A chart plus a fourteen-row stats table plus 250 words does not fit an A4 page —
    measured at 310-322mm against a 274mm budget. Rather than shrink the chart, which
    is the evidence, each symbol runs across two sheets: chart and numbers, then the
    reading. The split point is the end of the first table.
    """
    end = None
    for i, ln in enumerate(lines):
        if ln.lstrip().startswith("|"):
            j = i
            while j < len(lines) and lines[j].lstrip().startswith("|"):
                j += 1
            end = j
            break
    if end is None:
        return lines, []
    return lines[:end], lines[end:]


def weight(lines: list[str]) -> int:
    """Approximate rendered height in arbitrary units.

    A raw line count treats a table row and a prose line as equal, and they are not —
    a row costs roughly 5mm against 2mm, so a section that is mostly table measures
    short and then overflows. Weighting table rows fixed the 8mm spill on the
    synthesis continuation.
    """
    w = 0
    for ln in lines:
        s = ln.strip()
        if not s:
            continue
        w += 5 if s.startswith("|") else (4 if s.startswith("#") else 2)
    return w


def chunk_at_h3(lines: list[str], budget: int = 132) -> list[list[str]]:
    """Break a long narrative section into page-sized groups at H3 boundaries.

    Measured rather than guessed: the synthesis ran 441mm against a 274mm budget, so
    it needs two sheets. Splitting anywhere other than a heading would strand a table
    from its caption, so the H3s are the only legal cut points and a group that is
    itself too long simply stays long — better one over-full page than a table
    severed from the sentence explaining it.
    """
    blocks, cur = [], []
    for ln in lines:
        if ln.startswith("### ") and cur:
            blocks.append(cur)
            cur = [ln]
        else:
            cur.append(ln)
    if cur:
        blocks.append(cur)

    # A single H3 section can exceed a whole sheet on its own, and then no amount of
    # rebalancing helps — it has to be cut internally. Cut on blank lines only, and
    # never while inside a table, so a header never parts from its rows.
    split = []
    for b in blocks:
        if weight(b) <= budget:
            split.append(b)
            continue
        run, intable = [], False
        for ln in b:
            s = ln.strip()
            intable = s.startswith("|")
            if not s and not intable and weight(run) >= budget:
                split.append(run)
                run = []
                continue
            run.append(ln)
        if run:
            split.append(run)
    blocks = split
    # Balance rather than greedily fill. A greedy pass packs the first sheet to the
    # brim and leaves the last holding one short block on an otherwise empty page,
    # which reads as a mistake. Decide the sheet count first, then aim for even
    # sheets — the cut still only ever lands on a heading.
    total = sum(weight(b) for b in blocks)
    n = max(1, -(-total // budget))
    target = -(-total // n)
    pages, run = [], []
    for b in blocks:
        if run and weight(run) + weight(b) > target and len(pages) < n - 1:
            pages.append(run)
            run = list(b)
        else:
            run += b
    if run:
        pages.append(run)
    return pages


def parse_analysis() -> tuple[list[dict], list[dict]]:
    """Split CANDLE-ANALYSIS.md into per-symbol sections and the narrative sections."""
    if not ANALYSIS.exists():
        return [], []
    txt = ANALYSIS.read_text()
    parts = re.split(r"^##\s+", txt, flags=re.M)[1:]
    syms, other = [], []
    for p in parts:
        head, _, body = p.partition("\n")
        title = head.strip()
        key = re.match(r"^([A-Z0-9&\-]+)", title)
        png = None
        if key:
            hits = sorted(CHARTS.glob(f"{key.group(1)}_*.png"))
            png = hits[0] if hits else None
        if png:
            top, rest = split_at_table(body.splitlines())
            syms.append({"title": title, "sym": key.group(1), "png": png,
                         "top": md_block(top), "rest": md_block(rest)})
        else:
            other.append({"title": title,
                          "chunks": [md_block(c) for c in chunk_at_h3(body.splitlines())]})
    return syms, other


def img_uri(p: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(p.read_bytes()).decode()


# ── document ───────────────────────────────────────────────────────────────────
def css() -> str:
    faces = BEX.font_face("Syne", "Syne-ExtraBold.ttf", 800) + \
        BEX.font_face("JetBrains Mono", "JetBrainsMono-Medium.ttf", 500)
    return f"""
{faces}
@page {{ size: A4; margin: 0; }}
*{{box-sizing:border-box;}}
body{{margin:0;font-family:'Helvetica Neue',Helvetica,Arial,sans-serif;
  font-size:9.3pt;line-height:1.48;color:#1f2937;-webkit-print-color-adjust:exact;}}
.page{{width:210mm;min-height:296mm;padding:20mm 18mm 16mm;position:relative;
  page-break-after:always;
  background:linear-gradient(165deg,#ffffff 0%,#f7f8fe 55%,#eef0fe 100%);}}
.page:last-child{{page-break-after:auto;}}

/* The running header and footer are absolutely positioned against .page. A blanket
   `.page > * {{position:relative}}` would override that and print them on top of the
   H1 — that exact collision cost a rebuild once. Scope it to exclude them. */
.page > *:not(.mesh):not(.rh):not(.rf){{position:relative;z-index:1;}}
.page > .rh{{z-index:2;}} .page > .rf{{z-index:2;}}

h1,h2,h3,h4{{font-family:'Syne','Helvetica Neue',sans-serif;color:{INK};
  letter-spacing:-.015em;margin:0;}}
h2{{font-size:20pt;line-height:1.12;margin:0 0 3mm;}}
h3{{font-size:12.5pt;margin:6mm 0 2mm;}}
h4{{font-size:10.5pt;margin:4mm 0 1.5mm;}}
p{{margin:0 0 2.6mm;}}
ul{{margin:0 0 3mm;padding-left:5mm;}} li{{margin:0 0 1.2mm;}}
.mono{{font-family:'JetBrains Mono',ui-monospace,Menlo,monospace;}}
code.mono{{font-size:8.6pt;background:rgba(79,70,229,.07);padding:.3mm 1mm;
  border-radius:2pt;color:{INDIGO_D};}}
.dim{{color:{MUTED};}} strong{{color:{INK};}}
.lead{{font-size:11.4pt;line-height:1.55;color:{INK};margin:0 0 4mm;}}

.rh{{position:absolute;top:9mm;left:18mm;right:18mm;display:flex;
  justify-content:space-between;align-items:center;
  border-bottom:.6pt solid {RULE};padding-bottom:2.5mm;}}
.rh .brand{{display:flex;align-items:center;gap:2.2mm;}}
.rh img{{height:6.2mm;width:auto;}}
.rh .wm{{font-family:'Syne',sans-serif;font-size:10.5pt;color:{INK};}}
.rh span.sec{{font-family:'JetBrains Mono',monospace;font-size:6.6pt;color:{MUTED};
  letter-spacing:.14em;text-transform:uppercase;}}
.rf{{position:absolute;bottom:9mm;left:18mm;right:18mm;display:flex;
  justify-content:space-between;font-family:'JetBrains Mono',monospace;
  font-size:6.6pt;color:{MUTED};border-top:.6pt solid {RULE};padding-top:2mm;}}

/* Pinned to the sheet, not min-height: the cover is full-bleed and has no padding,
   so it does not obey the content budget the other pages are measured against. Left
   free it reports 297mm and spills a 1mm sliver onto a blank second sheet. */
.cover{{background:linear-gradient(160deg,{INK} 0%,#1a0a3e 55%,{INDIGO_D} 100%);
  color:#fff;padding:0;display:flex;flex-direction:column;
  height:296mm;min-height:296mm;overflow:hidden;}}
.cover .inner{{padding:32mm 18mm 18mm;flex:1;display:flex;flex-direction:column;}}
.cover h1{{font-size:37pt;line-height:1.03;color:#fff;margin:0 0 6mm;}}
.cover .sub{{font-size:12.5pt;color:#c9c4f5;max-width:132mm;line-height:1.5;}}
.cover .mk{{margin-bottom:11mm;}} .cover .mk svg{{width:22mm;height:22mm;}}
.cover .meta{{margin-top:auto;border-top:.8pt solid rgba(255,255,255,.22);
  padding-top:5mm;display:flex;gap:12mm;font-family:'JetBrains Mono',monospace;
  font-size:7.6pt;color:#b9b3ef;}}
.cover .meta b{{display:block;color:#fff;font-size:8.6pt;margin-top:1mm;
  font-family:'Helvetica Neue',sans-serif;}}
.cover .strip{{height:9mm;background:linear-gradient(90deg,{INDIGO},{LILAC},#fff);}}

/* The chart is 1.92:1, so full column width costs ~90mm of a 274mm page and pushed
   every symbol sheet 7-20mm over. At 86% it is 150mm wide — still the dominant
   element and legible at A4 — and the whole section lands on one sheet, which is
   worth more than the extra centimetre. */
.fig{{margin:3.5mm 0;page-break-inside:avoid;}}
.fig img{{width:84%;height:auto;display:block;margin:0 auto;border-radius:4pt;
  border:.6pt solid rgba(49,46,129,.18);}}
.figcap{{font-size:7.5pt;color:{MUTED};margin-top:1.2mm;font-style:italic;
  text-align:center;}}

.box{{background:rgba(255,255,255,.80);border:0.6pt solid rgba(255,255,255,.9);
  border-left:2.6pt solid {INDIGO};padding:3.6mm 4.6mm;margin:3.5mm 0;
  page-break-inside:avoid;border-radius:0 5pt 5pt 0;
  box-shadow:0 0.8pt 0 rgba(49,46,129,.10), inset 0 0.6pt 0 rgba(255,255,255,.95);}}
.box.warn{{border-left-color:{WARN};background:rgba(253,246,236,.82);}}
.box.bad{{border-left-color:{BAD};background:rgba(253,240,243,.82);}}
.box.ok{{border-left-color:{OK};background:rgba(238,248,242,.82);}}
.box h4{{margin:0 0 1.5mm;font-size:10.2pt;}}
.box p{{margin:0 0 2mm;}} .box p:last-child{{margin:0;}}

/* Compact on purpose. A long stats table is atomic — it cannot be split across
   sheets without parting the header from its rows — so the only way to keep one
   inside a page is to make the rows shorter. Measured: this took the widest
   synthesis table from 282mm to inside the budget. */
table.tbl{{width:100%;border-collapse:collapse;margin:2.5mm 0;font-size:7.9pt;
  page-break-inside:avoid;line-height:1.34;}}
table.tbl th{{background:linear-gradient(135deg,{INDIGO},#7c3aed);color:#fff;
  text-align:left;padding:1.4mm 2mm;font-weight:600;font-size:7.6pt;}}
table.tbl td{{padding:1.15mm 2mm;border-bottom:.5pt solid rgba(49,46,129,.10);
  vertical-align:top;}}
table.tbl tr:nth-child(even) td{{background:rgba(79,70,229,.035);}}
table.tbl td:first-child{{font-family:'JetBrains Mono',monospace;font-size:8pt;
  color:{INK};white-space:nowrap;}}

.kpi{{display:flex;gap:3mm;margin:4mm 0;}}
.kpi div{{flex:1;background:rgba(255,255,255,.82);border:.6pt solid rgba(255,255,255,.9);
  border-radius:5pt;padding:3mm;text-align:center;
  box-shadow:0 .8pt 0 rgba(49,46,129,.10), inset 0 .6pt 0 rgba(255,255,255,.95);}}
.kpi .n{{font-family:'Syne',sans-serif;font-size:17pt;color:{INK};display:block;}}
.kpi .l{{font-size:7.4pt;color:{MUTED};text-transform:uppercase;letter-spacing:.08em;}}
.kpi .n.bad{{color:{BAD};}} .kpi .n.ok{{color:{OK};}}
"""


def page(body: str, sec: str, pno: int, logo: str) -> str:
    return f"""<div class="page">
  <div class="rh"><div class="brand"><img src="{logo}"/><span class="wm">TradePilot</span></div>
    <span class="sec">{html.escape(sec)}</span></div>
  {body}
  <div class="rf"><span>Candlestick Evidence Pack</span><span>{pno}</span></div>
</div>"""


def build_html() -> str:
    logo = BEX.logo_uri()
    mark = (ROOT / "brand" / "letterhead" / "tradepilot-mark.svg").read_text()
    syms, other = parse_analysis()
    today = datetime.now().strftime("%d %B %Y")

    pages = []

    # cover
    pages.append(f"""<div class="page cover">
  <div class="inner">
    <div class="mk">{mark}</div>
    <h1>Which candle<br/>broke out —<br/>and did it matter?</h1>
    <p class="sub">Twelve of the largest multi-week gains on the NSE, drawn from real
    Kite bars. For each one: the breakout bar identified by rule rather than by eye,
    its measured geometry, the catalyst behind the move — and the number of times the
    same pattern appeared in that stock and failed.</p>
    <div class="meta">
      <div>PREPARED<b>{today}</b></div>
      <div>AUTHOR<b>Soumya Swain</b></div>
      <div>SOURCE<b>Kite Connect daily bars</b></div>
      <div>UNIVERSE<b>1,232 sessions &times; 3,046 symbols</b></div>
    </div>
  </div>
  <div class="strip"></div>
</div>""")

    # how to read
    pages.append(page(f"""
<h2>How to read one of these charts</h2>
<p class="lead">Nothing here needs prior knowledge of markets. A candle is one day of
trading drawn as a single shape, and once you can read the shape, every chart in this
pack is legible.</p>

<h3>The four numbers inside one candle</h3>
<p>Each trading day has four prices that matter: where it <strong>opened</strong>,
the <strong>highest</strong> it traded, the <strong>lowest</strong> it traded, and
where it <strong>closed</strong>. A candle draws all four at once.</p>
<ul>
<li>The thick middle — the <em>body</em> — spans the open and the close.</li>
<li><strong>Green</strong> means it closed higher than it opened; <strong>red</strong>
means it closed lower.</li>
<li>The thin lines above and below — the <em>wicks</em> — reach to the day's high and
low. A long wick means the price went there and came back.</li>
</ul>

<div class="box">
<h4>Why the shape carries information</h4>
<p>A tall green body with almost no wicks says buyers held control from open to close.
A small body with a long lower wick says sellers pushed it down hard and buyers took
it all back before the bell. The <em>proportions</em> are the signal, which is why
every pattern in this pack is stated as a measured ratio, not as a name someone
assigned by looking at it.</p>
</div>

<h3>The two lines drawn across every chart</h3>
<p>The <strong>20-day</strong> and <strong>50-day moving averages</strong> are simply
the average closing price of the last 20 and 50 days, redrawn each day. They are the
crudest possible summary of "where has this been trading lately", and they matter here
for one reason: a price crossing back above them is the most widely watched
confirmation signal there is, and it is something you can act on in real time.</p>

<h3>What the shaded band and arrows mark</h3>
<p>The shaded region is the run being studied. The green arrow marks the lowest point
before the rise, the red arrow the peak. <strong>Both were identified after the
fact.</strong> They are the ceiling — what a perfect trade would have captured — and
they are printed to be compared against what was actually reachable, never as a
suggestion that they were knowable at the time.</p>
""", "Reading the charts", 2, logo))

    # what this proves
    pages.append(page(f"""
<h2>What this pack can and cannot tell you</h2>
<p class="lead">This is the most important page in the document, and it argues against
the pack's own apparent message.</p>

<div class="box bad">
<h4>These twelve were chosen because they won</h4>
<p>The selection rule was: search five years of survivorship-free data for the largest
multi-week gains. Every chart therefore ends well, and every pattern visible in them
is a pattern <em>conditioned on success</em>.</p>
<p>That makes the usual reading — "these candles signal a breakout" — unavailable. To
know whether a pattern works you need to know how often it appears and <em>fails</em>,
and a sample of winners cannot answer that by construction.</p>
</div>

<h3>So the pack answers a narrower question honestly</h3>
<p>Not "what should we buy", but: <strong>when a stock did run, what did the entry
point actually look like at the moment it happened?</strong> That question is
answerable from winners, and its answer turned out to be uncomfortable.</p>

<div class="box warn">
<h4>The finding that changed our conclusion</h4>
<p>All twelve optimal entries sat <strong>below both moving averages, in a 22–60%
drawdown</strong>. That is nearly a tautology — the low of a run is by definition its
point of maximum weakness — but stating it plainly kills the idea that our entry rules
need tuning. At that bar, every trend signal says sell. No trend-following system can
aim there.</p>
</div>

<h3>The reachable number, beside the ceiling</h3>
<p>Waiting for the first close back above the 50-day moving average — a signal visible
in real time, with no hindsight — meant entering on average <strong>35.9% above the
low and 8.3 sessions late</strong>. It still left <strong>+106.5%</strong> on the
table against a perfect <strong>+169.7%</strong>: about 63% of the move, using
information that actually existed at the time.</p>

<div class="box">
<h4>One unbiased fact does live inside this sample</h4>
<p>Holding 60 sessions past the peak gave back <strong>21% on average, and 11 of the
12 ended lower</strong>. That measurement does not depend on how the names were
picked, so unlike everything else here, it generalises.</p>
</div>
""", "What it proves", 3, logo))

    # narrative sections first — method, then synthesis, so the reader meets the rule
    # before the results it produced
    pno = 4
    for o in other:
        if o["title"].lower().startswith("appendix"):
            continue
        sec = o["title"].split("—")[0].strip()
        for n, ch in enumerate(o["chunks"]):
            head = f"<h2>{md_inline(o['title'])}</h2>" if n == 0 else \
                f'<h2>{md_inline(sec)} <span class="dim">continued</span></h2>'
            pages.append(page(head + ch, sec, pno, logo))
            pno += 1

    # per-symbol: chart and numbers, then the reading
    for s in syms:
        pages.append(page(f"""
<h2>{html.escape(s['title'])}</h2>
<div class="fig"><img src="{img_uri(s['png'])}"/>
<div class="figcap">Daily candles from Kite Connect. Green arrow = run low, red arrow
= run peak; both identified after the fact. Blue line = 20-day average, orange =
50-day. Volume below.</div></div>
{s['top']}
{s['rest']}
""", s["sym"], pno, logo))
        pno += 1

    # appendix last
    for o in other:
        if not o["title"].lower().startswith("appendix"):
            continue
        for n, ch in enumerate(o["chunks"]):
            head = f"<h2>{md_inline(o['title'])}</h2>" if n == 0 else \
                '<h2>Appendix <span class="dim">continued</span></h2>'
            pages.append(page(head + ch, "Appendix", pno, logo))
            pno += 1

    return f"""<!doctype html><html><head><meta charset="utf-8"/>
<title>TradePilot — Candlestick Evidence</title><style>{css()}</style></head>
<body>{''.join(pages)}</body></html>"""


def main() -> int:
    if not ANALYSIS.exists():
        print(f"  missing {ANALYSIS} — run the candle analysis first")
        return 1
    OUT_HTML.write_text(build_html())
    print(f"  html: {OUT_HTML}")
    if "--measure" in sys.argv:
        asyncio.get_event_loop().run_until_complete(BEX.measure(OUT_HTML))
        return 0
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    asyncio.get_event_loop().run_until_complete(BEX.render(OUT_HTML, OUT_PDF))
    BEX.qa(OUT_PDF)
    BEX.shrink(OUT_PDF)
    print(f"  pdf : {OUT_PDF}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
