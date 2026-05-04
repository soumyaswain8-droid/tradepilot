"""Render DEEP_DIVE_ROOT_CAUSE.pdf via Pyppeteer (NEVER WeasyPrint).

Pipeline:
  1. Read DEEP_DIVE_ROOT_CAUSE.md
  2. Convert markdown -> HTML using markdown library
  3. Wrap in book-grade HTML template (cover, fonts, page CSS)
  4. Render via Pyppeteer + Chrome headless (7in x 10in book)
  5. Visual QA: render page 1 as PNG thumbnail and confirm not blank
"""
import asyncio
import base64
import re
from pathlib import Path

import markdown as md
from pyppeteer import launch

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/reports/2026-04-27")
MD_FILE  = ROOT / "DEEP_DIVE_ROOT_CAUSE.md"
HTML_FILE = ROOT / "DEEP_DIVE_ROOT_CAUSE.html"
PDF_FILE  = ROOT / "DEEP_DIVE_ROOT_CAUSE.pdf"
CHROME    = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ---- Step 1: read markdown ----
md_text = MD_FILE.read_text()

# ---- Step 2: replace local image paths with base64 data URIs (Chrome file:// safer this way) ----
def embed_image(match):
    alt = match.group(1)
    rel_path = match.group(2)
    img_path = (ROOT / rel_path).resolve()
    if not img_path.exists():
        return match.group(0)
    data = base64.b64encode(img_path.read_bytes()).decode("ascii")
    return f'<img alt="{alt}" src="data:image/png;base64,{data}" class="chart-img" />'

md_text = re.sub(r"!\[([^\]]*)\]\(([^)]+)\)", embed_image, md_text)

# ---- Step 3: page-break div passthrough ----
# markdown-py with `extra` extension preserves raw HTML
body_html = md.markdown(md_text, extensions=["extra", "tables", "toc", "sane_lists"])

# ---- Step 4: build full book HTML ----
COVER_HTML = """
<section class="cover">
  <div class="cover-badge">DEEP DIVE</div>
  <h1 class="cover-title">Root Cause Analysis</h1>
  <h2 class="cover-subtitle">TradePilot v5 / v5_6 / v5_7 - Worst Day of v5 Observation Window</h2>
  <div class="cover-date">Monday, 27 April 2026</div>

  <div class="cover-stats">
    <div class="stat">
      <div class="stat-value">98.3%</div>
      <div class="stat-label">P&amp;L drop vs 04-22 elite day</div>
    </div>
    <div class="stat">
      <div class="stat-value">Rs -2,596</div>
      <div class="stat-label">Combined SHORT-side bleed</div>
    </div>
    <div class="stat">
      <div class="stat-value">1h 41m</div>
      <div class="stat-label">Engine downtime at market open</div>
    </div>
  </div>

  <div class="cover-author">
    <div>Author: Soumya Swain</div>
    <div>Co-founder, TradePilot / Sidewall</div>
    <div>Generated: 2026-04-27 post-market</div>
  </div>
</section>
"""

HTML_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>Deep-Dive Root Cause Analysis - 2026-04-27</title>
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

  /* Cover page */
  .cover {{
    background: linear-gradient(180deg, #ffffff 0%, #f0f4ff 30%, #dbeafe 65%, #93c5fd 100%);
    width: 7in;
    height: 10in;
    padding: 1.2in 0.8in;
    page-break-after: always;
    text-align: center;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
    color: #1e1b4b;
  }}
  .cover-badge {{
    display: inline-block;
    background: #4f46e5;
    color: white;
    padding: 6px 18px;
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 11pt;
    letter-spacing: 2px;
    border-radius: 3px;
    align-self: center;
    margin-bottom: 0.4in;
  }}
  .cover-title {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 38pt;
    margin: 0 0 0.2in 0;
    color: #1e1b4b;
    line-height: 1.1;
  }}
  .cover-subtitle {{
    font-family: 'Charter', Georgia, serif;
    font-weight: 400;
    font-style: italic;
    font-size: 14pt;
    margin: 0 0 0.6in 0;
    color: #312e81;
    line-height: 1.4;
  }}
  .cover-date {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 13pt;
    color: #4338ca;
    font-weight: 600;
    letter-spacing: 1px;
  }}
  .cover-stats {{
    display: flex;
    justify-content: space-around;
    margin: 0.8in 0;
  }}
  .cover-stats .stat {{
    background: rgba(255,255,255,0.85);
    border-radius: 8px;
    padding: 18px 16px;
    width: 30%;
    box-shadow: 0 4px 12px rgba(30,27,75,0.12);
  }}
  .cover-stats .stat-value {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 22pt;
    color: #dc2626;
    margin-bottom: 4px;
  }}
  .cover-stats .stat-label {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 9pt;
    color: #1e1b4b;
    line-height: 1.3;
  }}
  .cover-author {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 11pt;
    color: #1e1b4b;
    line-height: 1.6;
  }}

  /* Body content */
  h1 {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 22pt;
    color: #1e1b4b;
    border-bottom: 3px solid #4f46e5;
    padding-bottom: 6px;
    margin-top: 0.4in;
    margin-bottom: 0.18in;
    page-break-after: avoid;
  }}
  h2 {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 16pt;
    color: #312e81;
    margin-top: 0.28in;
    margin-bottom: 0.12in;
    page-break-after: avoid;
  }}
  h3 {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 600;
    font-size: 13pt;
    color: #4338ca;
    margin-top: 0.2in;
    margin-bottom: 0.08in;
    page-break-after: avoid;
  }}
  p {{
    margin: 0 0 0.6rem 0;
    text-align: justify;
    page-break-inside: avoid;
  }}
  strong {{ color: #1e1b4b; }}
  em {{ color: #4338ca; }}

  /* Tables */
  table {{
    width: 100%;
    max-width: 95%;
    border-collapse: collapse;
    margin: 0.18in 0;
    font-size: 9.5pt;
    page-break-inside: avoid;
  }}
  th {{
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
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
    background: #fafafa;
  }}

  /* Charts */
  .chart-img {{
    max-width: 100%;
    margin: 0.2in auto;
    display: block;
    border: 1px solid #e5e7eb;
    border-radius: 4px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    page-break-inside: avoid;
  }}

  /* Page break utility */
  .page-break {{
    page-break-after: always;
    height: 0;
  }}

  /* Code blocks */
  code {{
    font-family: 'Courier New', Courier, monospace;
    font-size: 9pt;
    background: #f3f4f6;
    padding: 1px 4px;
    border-radius: 3px;
    color: #7c2d12;
  }}
  pre {{
    background: #1f2937;
    color: #f9fafb;
    padding: 12px 14px;
    border-radius: 6px;
    overflow-x: auto;
    font-size: 8.5pt;
    line-height: 1.45;
    page-break-inside: avoid;
  }}
  pre code {{
    background: none;
    color: inherit;
    padding: 0;
  }}

  /* Lists */
  ul, ol {{
    padding-left: 1.4em;
    margin: 0.4rem 0 0.6rem 0;
  }}
  li {{
    margin-bottom: 0.15rem;
  }}

  /* HR */
  hr {{
    border: none;
    border-top: 1px solid #c7d2fe;
    margin: 0.3in 0;
  }}

  /* Blockquote */
  blockquote {{
    border-left: 4px solid #4f46e5;
    background: #eef2ff;
    margin: 0.2in 0;
    padding: 12px 18px;
    color: #312e81;
    font-style: italic;
    page-break-inside: avoid;
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
print(f"Wrote HTML: {HTML_FILE} ({HTML_FILE.stat().st_size} bytes)")


# ---- Step 5: Pyppeteer render ----
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


# ---- Step 6: visual QA - count pages and verify cover not blank ----
from pypdf import PdfReader, PdfWriter
import subprocess
reader = PdfReader(str(PDF_FILE))
n_pages = len(reader.pages)
print(f"PDF page count: {n_pages}")

# Check page 1 (cover) and a body page have text/content
cover_text = reader.pages[0].extract_text().strip()
print(f"Page 1 (cover) text length: {len(cover_text)} chars")
if len(cover_text) < 30:
    print("WARN: cover page may be near-blank")

body_text = reader.pages[2].extract_text().strip() if n_pages >= 3 else ""
print(f"Page 3 (body) text length: {len(body_text)} chars")

# Render page 1 as PNG thumbnail for visual confirmation
qa_dir = ROOT / "qa"
qa_dir.mkdir(exist_ok=True)
for p in [1, 2, max(1, n_pages // 2), n_pages]:
    if p > n_pages: continue
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
