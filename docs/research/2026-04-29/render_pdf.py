"""Render regime-switching-master.pdf via Pyppeteer (NEVER WeasyPrint).

Pipeline:
  1. Read regime-switching-master.md
  2. Replace mermaid blocks with styled HTML cards (mmdc not installed)
  3. Convert markdown to HTML
  4. Wrap in book-grade HTML template
  5. Render via Pyppeteer (7in x 10in)
  6. Visual QA: page count, blank-page detection, qlmanage thumbnails
"""
import asyncio
import re
from pathlib import Path

import markdown as md
from pyppeteer import launch

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/research/2026-04-29")
MD_FILE = ROOT / "regime-switching-master.md"
HTML_FILE = ROOT / "regime-switching-master.html"
PDF_FILE = ROOT / "regime-switching-master.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ---- Step 1: read markdown ----
md_text = MD_FILE.read_text()


# ---- Step 2: replace mermaid blocks with styled HTML ----
def replace_mermaid_block(match):
    """Convert mermaid block content into a labelled diagram card."""
    body = match.group(1).strip()
    # Detect direction
    is_lr = body.startswith("graph LR") or body.startswith("flowchart LR")
    is_td = body.startswith("graph TD") or body.startswith("flowchart TD")

    # Extract node definitions like  P1[Phase 1: ...]
    node_pattern = re.compile(r"(\w+)\[([^\]]+)\]")
    nodes = {nid: label.replace("<br/>", " — ") for nid, label in node_pattern.findall(body)}

    # Extract edges:  P1 --> P2  or  D -->|label| M
    edge_pattern = re.compile(r"(\w+)\s*-+>(?:\|([^|]+)\|)?\s*(\w+)")
    edges = [(a, lbl or "", b) for a, lbl, b in edge_pattern.findall(body)]

    if is_lr:
        # Render as horizontal pipeline
        cells = []
        seen = []
        for a, _, b in edges:
            if a not in seen and a in nodes:
                seen.append(a)
            if b not in seen and b in nodes:
                seen.append(b)
        for nid in seen:
            label = nodes.get(nid, nid)
            cells.append(f'<div class="phase-card">{label}</div>')
        return (
            '<div class="diagram-lr">'
            + '<div class="diagram-arrow">▶</div>'.join(cells)
            + '</div>'
        )
    else:
        # Render as vertical structured diagram
        # Build adjacency
        from collections import defaultdict
        children = defaultdict(list)
        node_set = set()
        for a, lbl, b in edges:
            if a in nodes and b in nodes:
                children[a].append((b, lbl))
                node_set.add(a)
                node_set.add(b)

        # Find roots (nodes with no incoming edges)
        targets = {b for a, _, b in edges}
        roots = [n for n in nodes if n in node_set and n not in targets]

        # Render as nested cards
        rendered = ['<div class="diagram-td">']
        for root in roots:
            rendered.append(f'<div class="td-node td-root">{nodes[root]}</div>')
            for child, lbl in children.get(root, []):
                arrow_lbl = f' <span class="td-arrow-lbl">({lbl})</span>' if lbl else ""
                rendered.append(f'<div class="td-arrow">↓{arrow_lbl}</div>')
                rendered.append(f'<div class="td-node">{nodes[child]}</div>')
                # Render grandchildren (one level deep)
                for gc, gclbl in children.get(child, []):
                    gc_lbl = f' <span class="td-arrow-lbl">({gclbl})</span>' if gclbl else ""
                    rendered.append(f'<div class="td-arrow">↓{gc_lbl}</div>')
                    rendered.append(f'<div class="td-node">{nodes[gc]}</div>')
        rendered.append('</div>')
        return "".join(rendered)


md_text = re.sub(r"```mermaid\n(.*?)\n```", replace_mermaid_block, md_text, flags=re.DOTALL)

# ---- Step 3: convert markdown to HTML ----
body_html = md.markdown(md_text, extensions=["extra", "tables", "toc", "sane_lists"])

# ---- Step 4: build cover ----
COVER_HTML = """
<section class="cover">
  <div class="cover-badge">DEEP RESEARCH</div>
  <h1 class="cover-title">Regime-Switching<br/>Engines</h1>
  <h2 class="cover-subtitle">Should TradePilot build 3-4 specialist engines and route between them by market regime? A 5-agent parallel research dive.</h2>

  <div class="cover-stats">
    <div class="stat">
      <div class="stat-value">5</div>
      <div class="stat-label">Parallel research agents</div>
    </div>
    <div class="stat">
      <div class="stat-value">175</div>
      <div class="stat-label">LONG signals v5 blocked on 04-29</div>
    </div>
    <div class="stat">
      <div class="stat-value">3 wk</div>
      <div class="stat-label">Recommended fix vs 9-15 wk hard switch</div>
    </div>
  </div>

  <div class="cover-date">Wednesday, 29 April 2026</div>

  <div class="cover-author">
    <div>Author: Soumya Swain · Synthesis from 5 sub-agents</div>
    <div>Co-founder, TradePilot / Sidewall</div>
    <div>Companion to PRODUCTION_ROADMAP_v6.1</div>
  </div>
</section>
"""

# ---- Step 5: full HTML ----
HTML_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Regime-Switching Engines — Deep Research</title>
<style>
  @page {{
    size: 7in 10in;
    margin: 0.85in 0.7in 0.85in 0.85in;
  }}
  @page :first {{
    margin: 0;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    font-family: 'Charter', Georgia, 'Times New Roman', serif;
    font-size: 11pt;
    line-height: 1.55;
    color: #1f2937;
    margin: 0;
    padding: 0;
    -webkit-print-color-adjust: exact;
    print-color-adjust: exact;
  }}

  /* Cover page — green to match v6.1 roadmap */
  .cover {{
    background: linear-gradient(160deg, #ffffff 0%, #ecfdf5 25%, #d1fae5 55%, #6ee7b7 85%, #10b981 100%);
    width: 7in;
    height: 10in;
    padding: 1.0in 0.8in 0.85in 0.8in;
    page-break-after: always;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    color: #064e3b;
  }}
  .cover-badge {{
    display: inline-block;
    background: #047857;
    color: white;
    padding: 6px 18px;
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 11pt;
    letter-spacing: 2px;
    border-radius: 3px;
    align-self: center;
    margin-bottom: 0.25in;
  }}
  .cover-title {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 40pt;
    margin: 0 0 0.18in 0;
    color: #064e3b;
    line-height: 1.05;
    letter-spacing: -0.5px;
  }}
  .cover-subtitle {{
    font-family: 'Charter', Georgia, serif;
    font-weight: 400;
    font-style: italic;
    font-size: 13pt;
    margin: 0 0 0.35in 0;
    color: #065f46;
    line-height: 1.45;
    max-width: 5.2in;
    align-self: center;
  }}
  .cover-stats {{
    display: flex;
    justify-content: space-around;
    margin: 0.3in 0 0.4in 0;
  }}
  .cover-stats .stat {{
    background: rgba(255,255,255,0.92);
    border-radius: 10px;
    padding: 16px 12px;
    width: 30%;
    box-shadow: 0 4px 14px rgba(6,78,59,0.18);
    border: 1px solid rgba(16,185,129,0.25);
  }}
  .cover-stats .stat-value {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 24pt;
    color: #047857;
    margin-bottom: 4px;
    line-height: 1;
  }}
  .cover-stats .stat-label {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 8.5pt;
    color: #064e3b;
    line-height: 1.3;
  }}
  .cover-date {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 13pt;
    color: #047857;
    font-weight: 600;
    letter-spacing: 1px;
    margin: 0 0 0.16in 0;
  }}
  .cover-author {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 10pt;
    color: #064e3b;
    line-height: 1.65;
  }}

  /* Body content */
  h1 {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 22pt;
    color: #064e3b;
    border-bottom: 3px solid #10b981;
    padding-bottom: 6px;
    margin-top: 0.4in;
    margin-bottom: 0.18in;
    page-break-after: avoid;
    page-break-before: always;
  }}
  h1:first-of-type {{
    page-break-before: auto;
  }}
  h2 {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 15pt;
    color: #065f46;
    margin-top: 0.28in;
    margin-bottom: 0.12in;
    page-break-after: avoid;
  }}
  h3 {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 600;
    font-size: 12.5pt;
    color: #047857;
    margin-top: 0.2in;
    margin-bottom: 0.08in;
    page-break-after: avoid;
  }}
  p {{
    margin: 0 0 0.55rem 0;
    text-align: justify;
    page-break-inside: avoid;
  }}
  strong {{ color: #064e3b; }}
  em {{ color: #047857; }}

  /* Tables */
  table {{
    width: 100%;
    max-width: 95%;
    border-collapse: collapse;
    margin: 0.16in 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
  }}
  th {{
    background: linear-gradient(135deg, #047857, #10b981);
    color: white;
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 600;
    padding: 8px 10px;
    text-align: left;
    font-size: 9pt;
  }}
  td {{
    padding: 6px 10px;
    border-bottom: 1px solid #e5e7eb;
    vertical-align: top;
  }}
  tr:nth-child(even) td {{
    background: #f0fdf4;
  }}

  /* Diagrams */
  .diagram-lr {{
    display: flex;
    flex-direction: row;
    align-items: center;
    justify-content: space-around;
    flex-wrap: wrap;
    margin: 0.25in 0;
    page-break-inside: avoid;
    gap: 4px;
  }}
  .phase-card {{
    background: linear-gradient(135deg, #047857, #10b981);
    color: white;
    padding: 12px 14px;
    border-radius: 8px;
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 600;
    font-size: 9pt;
    text-align: center;
    box-shadow: 0 3px 8px rgba(6,78,59,0.2);
    flex: 1;
    min-width: 1.3in;
    line-height: 1.3;
  }}
  .diagram-arrow {{
    color: #047857;
    font-size: 14pt;
    font-weight: 700;
    padding: 0 4px;
  }}
  .diagram-td {{
    margin: 0.25in auto;
    text-align: center;
    page-break-inside: avoid;
    max-width: 5in;
  }}
  .td-node {{
    display: inline-block;
    background: #ecfdf5;
    border: 2px solid #10b981;
    color: #064e3b;
    padding: 8px 14px;
    border-radius: 6px;
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 600;
    font-size: 9.5pt;
    margin: 4px 0;
    min-width: 2in;
  }}
  .td-root {{
    background: linear-gradient(135deg, #047857, #10b981);
    color: white;
    border-color: #064e3b;
  }}
  .td-arrow {{
    color: #047857;
    font-size: 12pt;
    font-weight: 700;
    line-height: 1;
    margin: 2px 0;
  }}
  .td-arrow-lbl {{
    font-size: 8.5pt;
    font-style: italic;
    color: #065f46;
    font-weight: 400;
  }}

  /* Page break utility */
  .page-break {{ page-break-after: always; height: 0; }}

  /* Code */
  code {{
    font-family: 'Courier New', Courier, monospace;
    font-size: 9pt;
    background: #f0fdf4;
    padding: 1px 5px;
    border-radius: 3px;
    color: #065f46;
    border: 1px solid #d1fae5;
  }}
  pre {{
    background: #064e3b;
    color: #ecfdf5;
    padding: 12px 14px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 8.5pt;
    line-height: 1.45;
    page-break-inside: avoid;
    margin: 0.18in 0;
  }}
  pre code {{
    background: none;
    color: inherit;
    padding: 0;
    border: none;
  }}

  /* Lists */
  ul, ol {{
    padding-left: 1.4em;
    margin: 0.35rem 0 0.55rem 0;
  }}
  li {{ margin-bottom: 0.15rem; }}

  /* HR */
  hr {{
    border: none;
    border-top: 1px solid #6ee7b7;
    margin: 0.3in 0;
  }}

  /* Blockquote */
  blockquote {{
    border-left: 4px solid #10b981;
    background: #ecfdf5;
    margin: 0.2in 0;
    padding: 12px 18px;
    color: #065f46;
    font-style: italic;
    page-break-inside: avoid;
    border-radius: 0 6px 6px 0;
  }}
</style>
</head>
<body>
{COVER_HTML}
<main>
{body_html}
</main>
</body>
</html>
"""

HTML_FILE.write_text(HTML_TEMPLATE)
print(f"Wrote HTML: {HTML_FILE} ({HTML_FILE.stat().st_size:,} bytes)")


# ---- Step 6: Pyppeteer render ----
async def render():
    browser = await launch(
        executablePath=CHROME,
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False,
    )
    page = await browser.newPage()
    await page.setViewport({"width": 700, "height": 1000, "deviceScaleFactor": 2})
    await page.goto(f"file://{HTML_FILE}", waitUntil="networkidle0", timeout=60000)
    await asyncio.sleep(2)
    await page.pdf({
        "path": str(PDF_FILE),
        "printBackground": True,
        "preferCSSPageSize": True,
        "displayHeaderFooter": False,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    })
    await browser.close()
    print(f"Wrote PDF: {PDF_FILE} ({PDF_FILE.stat().st_size:,} bytes)")


asyncio.get_event_loop().run_until_complete(render())


# ---- Step 7: visual QA ----
from pypdf import PdfReader, PdfWriter
import subprocess

reader = PdfReader(str(PDF_FILE))
n_pages = len(reader.pages)
print(f"PDF page count: {n_pages}")

cover_text = reader.pages[0].extract_text().strip()
print(f"Page 1 (cover) text length: {len(cover_text)} chars")
if len(cover_text) < 30:
    print("WARN: cover may be near-blank")

warnings = 0
for i in range(1, n_pages - 1):
    text = reader.pages[i].extract_text().strip()
    clean = text.replace(str(i + 1), "").strip()
    if len(clean) < 80:
        print(f"  WARN: page {i+1} nearly blank ({len(clean)} chars)")
        warnings += 1

# Render thumbnails
qa_dir = ROOT / "qa"
qa_dir.mkdir(exist_ok=True)
for p in [1, 2, max(2, n_pages // 2), n_pages]:
    if p > n_pages:
        continue
    w = PdfWriter()
    w.add_page(reader.pages[p - 1])
    tmp = qa_dir / f"qa_p{p}.pdf"
    with open(tmp, "wb") as f:
        w.write(f)
    subprocess.run(
        ["qlmanage", "-t", "-s", "800", "-o", str(qa_dir), str(tmp)],
        capture_output=True, timeout=15,
    )
print(f"QA thumbnails: {qa_dir}")
print(f"Blank-page warnings: {warnings}")
print("OK" if warnings <= 2 else "REVIEW THUMBNAILS")
