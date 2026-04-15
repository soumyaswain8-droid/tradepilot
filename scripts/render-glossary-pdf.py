#!/usr/bin/env python3
"""Render TRADEPILOT_GLOSSARY.md to PDF via Pyppeteer + Chrome."""
import asyncio
import subprocess
from pathlib import Path

PROJECT = Path(__file__).parent.parent
MD_FILE = PROJECT / "docs" / "TRADEPILOT_GLOSSARY.md"
HTML_FILE = PROJECT / "docs" / "TRADEPILOT_GLOSSARY.html"
PDF_FILE = PROJECT / "docs" / "TRADEPILOT_GLOSSARY.pdf"

# Step 1: Convert MD to styled HTML
def md_to_html():
    import markdown
    md_text = MD_FILE.read_text()
    html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code", "toc"])

    html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
@page {{
    size: A4;
    margin: 0.75in 0.6in 0.75in 0.7in;
}}
body {{
    font-family: 'Avenir Next', 'Avenir', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.55;
    color: #1a1a2e;
    max-width: 100%;
}}
h1 {{
    font-size: 22pt;
    color: #1e1b4b;
    border-bottom: 3px solid #4f46e5;
    padding-bottom: 8px;
    margin-top: 0;
}}
h2 {{
    font-size: 14pt;
    color: #312e81;
    border-bottom: 1.5px solid #c7d2fe;
    padding-bottom: 4px;
    margin-top: 28px;
    page-break-after: avoid;
}}
h3 {{
    font-size: 12pt;
    color: #4338ca;
    margin-top: 18px;
}}
table {{
    width: 100%;
    border-collapse: collapse;
    margin: 10px 0 16px 0;
    font-size: 9.5pt;
    page-break-inside: auto;
}}
thead {{
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
}}
th {{
    padding: 8px 10px;
    text-align: left;
    font-weight: 600;
    font-size: 9pt;
}}
td {{
    padding: 7px 10px;
    border-bottom: 1px solid #e5e7eb;
    vertical-align: top;
}}
tr:nth-child(even) {{
    background-color: #f8f9ff;
}}
tr:hover {{
    background-color: #eef2ff;
}}
strong {{
    color: #1e1b4b;
}}
code {{
    background: #f0f0f5;
    padding: 1px 5px;
    border-radius: 3px;
    font-size: 9pt;
    font-family: 'Courier New', monospace;
}}
pre {{
    background: #1e1b4b;
    color: #e0e7ff;
    padding: 12px 16px;
    border-radius: 6px;
    font-size: 9pt;
    overflow-x: auto;
    page-break-inside: avoid;
}}
hr {{
    border: none;
    border-top: 1.5px solid #c7d2fe;
    margin: 20px 0;
}}
em {{
    color: #6b7280;
}}
/* Cover styling for first section */
body > h1:first-of-type {{
    text-align: center;
    font-size: 26pt;
    margin-top: 40px;
    margin-bottom: 5px;
}}
body > h1:first-of-type + p {{
    text-align: center;
    font-style: italic;
    color: #6b7280;
}}
/* Badge for section headers */
h2::before {{
    content: '';
    display: inline-block;
    width: 4px;
    height: 18px;
    background: #4f46e5;
    margin-right: 8px;
    vertical-align: middle;
    border-radius: 2px;
}}
</style>
</head>
<body>
{html_body}
</body>
</html>"""
    HTML_FILE.write_text(html)
    print(f"HTML: {HTML_FILE} ({len(html):,} chars)")


# Step 2: Render HTML to PDF via Pyppeteer
async def html_to_pdf():
    from pyppeteer import launch

    browser = await launch(
        executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        args=["--no-sandbox", "--disable-gpu"],
    )
    page = await browser.newPage()
    abs_path = HTML_FILE.resolve()
    await page.goto(f"file://{abs_path}", waitUntil="networkidle0", timeout=30000)
    await asyncio.sleep(2)
    await page.pdf({
        "path": str(PDF_FILE),
        "printBackground": True,
        "preferCSSPageSize": True,
        "displayHeaderFooter": False,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    })
    await browser.close()
    size_kb = PDF_FILE.stat().st_size / 1024
    print(f"PDF: {PDF_FILE} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    print("Converting Markdown -> HTML...")
    md_to_html()
    print("Rendering HTML -> PDF...")
    asyncio.get_event_loop().run_until_complete(html_to_pdf())
    print("Done!")
