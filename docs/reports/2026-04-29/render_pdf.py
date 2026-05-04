"""Render PRODUCTION_ROADMAP_v6.1.pdf via Pyppeteer (NEVER WeasyPrint).

Pipeline mirrors docs/reports/2026-04-27/render_pdf.py:
  1. Read MD
  2. Convert to HTML (markdown.extra+tables+toc+sane_lists)
  3. Wrap in book-grade HTML template (gradient cover, fonts, page CSS)
  4. Render via Pyppeteer + Chrome headless (7in x 10in book format)
  5. Visual QA: page count, blank-page detection, qlmanage thumbnails
"""
import asyncio
from pathlib import Path

import markdown as md
from pyppeteer import launch

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/reports/2026-04-29")
MD_FILE = ROOT / "PRODUCTION_ROADMAP_v6.1.md"
HTML_FILE = ROOT / "PRODUCTION_ROADMAP_v6.1.html"
PDF_FILE = ROOT / "PRODUCTION_ROADMAP_v6.1.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

# ---- Step 1: read markdown ----
md_text = MD_FILE.read_text()

# ---- Step 2: convert to HTML ----
body_html = md.markdown(md_text, extensions=["extra", "tables", "toc", "sane_lists"])

# ---- Step 3: build cover ----
COVER_HTML = """
<section class="cover">
  <div class="cover-badge">PRODUCTION ROADMAP</div>
  <h1 class="cover-title">TradePilot v6.1</h1>
  <h2 class="cover-subtitle">From a 6-engine paper trading laptop to a SEBI-compliant, multi-broker, optionally autonomous production system</h2>

  <div class="cover-stats">
    <div class="stat">
      <div class="stat-value">36-40</div>
      <div class="stat-label">Weeks to public launch</div>
    </div>
    <div class="stat">
      <div class="stat-value">5</div>
      <div class="stat-label">Statistical decision gates</div>
    </div>
    <div class="stat">
      <div class="stat-value">80%</div>
      <div class="stat-label">Phase 1 complete today</div>
    </div>
  </div>

  <div class="cover-date">Wednesday, 29 April 2026</div>

  <div class="cover-author">
    <div>Author: Soumya Swain</div>
    <div>Co-founder, TradePilot / Sidewall</div>
    <div>Reconciles April 12 v6 master plan with shipped Track A + Fix #1</div>
  </div>
</section>
"""

# ---- Step 4: build full HTML document ----
HTML_TEMPLATE = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TradePilot v6.1 Production Roadmap - 2026-04-29</title>
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
    background: linear-gradient(160deg, #ffffff 0%, #ecfdf5 25%, #d1fae5 55%, #6ee7b7 85%, #10b981 100%);
    width: 7in;
    height: 10in;
    padding: 1.1in 0.8in 0.9in 0.8in;
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
    margin-bottom: 0.3in;
  }}
  .cover-title {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 44pt;
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
    margin: 0 0 0.4in 0;
    color: #065f46;
    line-height: 1.45;
    max-width: 5.2in;
    align-self: center;
  }}
  .cover-stats {{
    display: flex;
    justify-content: space-around;
    margin: 0.4in 0 0.5in 0;
  }}
  .cover-stats .stat {{
    background: rgba(255,255,255,0.92);
    border-radius: 10px;
    padding: 18px 14px;
    width: 30%;
    box-shadow: 0 4px 14px rgba(6,78,59,0.18);
    border: 1px solid rgba(16,185,129,0.25);
  }}
  .cover-stats .stat-value {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-weight: 700;
    font-size: 26pt;
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
    margin: 0 0 0.18in 0;
  }}
  .cover-author {{
    font-family: 'Avenir Next', Helvetica, sans-serif;
    font-size: 10.5pt;
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

  /* Page break utility */
  .page-break {{
    page-break-after: always;
    height: 0;
  }}

  /* Code blocks */
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
  li {{
    margin-bottom: 0.15rem;
  }}

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


# ---- Step 6: visual QA ----
from pypdf import PdfReader, PdfWriter
import subprocess

reader = PdfReader(str(PDF_FILE))
n_pages = len(reader.pages)
print(f"PDF page count: {n_pages}")

cover_text = reader.pages[0].extract_text().strip()
print(f"Page 1 (cover) text length: {len(cover_text)} chars")
if len(cover_text) < 30:
    print("WARN: cover page may be near-blank")

# Scan for blank body pages
warnings = 0
for i in range(1, n_pages - 1):
    text = reader.pages[i].extract_text().strip()
    clean = text.replace(str(i + 1), "").strip()
    if len(clean) < 80:
        print(f"  WARN: page {i+1} nearly blank ({len(clean)} chars)")
        warnings += 1

# Render thumbnails for visual confirmation
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
print("OK" if warnings == 0 else "REVIEW THUMBNAILS")
