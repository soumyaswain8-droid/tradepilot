#!/usr/bin/env python3
"""Render v5 performance paper MD -> HTML -> PDF via Pyppeteer + Chrome."""

import asyncio
import os
import markdown

MD_PATH = "/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/daily-summaries/2026-04-10_v5_performance_paper.md"
PDF_PATH = "/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/daily-summaries/2026-04-10_v5_performance_paper.pdf"
HTML_PATH = "/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/daily-summaries/2026-04-10_v5_performance_paper.html"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page {
    size: A4;
    margin: 0.8in 0.7in 0.8in 0.7in;
}

* { box-sizing: border-box; }

body {
    font-family: 'Avenir Next', 'Avenir', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.65;
    color: #1a1a2e;
    background: #fafafe;
    max-width: 100%;
    padding: 0;
    margin: 0;
}

h1 {
    font-size: 22pt;
    font-weight: 700;
    color: #312e81;
    border-bottom: 3px solid #6366f1;
    padding-bottom: 0.4rem;
    margin-top: 1.8rem;
    margin-bottom: 0.8rem;
    letter-spacing: -0.3px;
}

h2 {
    font-size: 15pt;
    font-weight: 600;
    color: #3730a3;
    border-left: 4px solid #818cf8;
    padding-left: 0.7rem;
    margin-top: 1.6rem;
    margin-bottom: 0.6rem;
}

h3 {
    font-size: 12pt;
    font-weight: 600;
    color: #4338ca;
    margin-top: 1.2rem;
    margin-bottom: 0.4rem;
}

p {
    margin-bottom: 0.6rem;
}

strong {
    color: #1e1b4b;
}

em {
    color: #475569;
}

hr {
    border: none;
    border-top: 1.5px solid #c7d2fe;
    margin: 1.2rem 0;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 95%;
    margin: 0.8rem auto;
    font-size: 9.5pt;
    page-break-inside: avoid;
}

thead th {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
    font-weight: 600;
    padding: 0.5rem 0.65rem;
    text-align: left;
    font-size: 9pt;
    letter-spacing: 0.3px;
    border: none;
}

thead th:first-child {
    border-radius: 6px 0 0 0;
}
thead th:last-child {
    border-radius: 0 6px 0 0;
}

tbody td {
    padding: 0.4rem 0.65rem;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
}

tbody tr:nth-child(odd) {
    background: #f8fafc;
}
tbody tr:nth-child(even) {
    background: #ffffff;
}
tbody tr:hover {
    background: #eef2ff;
}

tbody tr:last-child td:first-child {
    border-radius: 0 0 0 6px;
}
tbody tr:last-child td:last-child {
    border-radius: 0 0 6px 0;
}

/* Right-align numeric columns */
td:last-child, th:last-child {
    text-align: right;
}

/* Code blocks */
pre {
    background: #f5f5fa;
    border: 1px solid #e0e0eb;
    border-radius: 6px;
    padding: 0.7rem 0.9rem;
    font-family: 'Courier New', Courier, monospace;
    font-size: 9pt;
    line-height: 1.5;
    overflow-x: auto;
    color: #1e1b4b;
    page-break-inside: avoid;
    margin: 0.6rem 0;
}

code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 9pt;
    background: #eef0f8;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    color: #4338ca;
}

pre code {
    background: none;
    padding: 0;
    color: inherit;
}

/* Lists */
ul, ol {
    margin: 0.4rem 0 0.6rem 1.4rem;
    padding: 0;
}

li {
    margin-bottom: 0.25rem;
}

/* Special styling for the title block */
body > h1:first-child {
    font-size: 26pt;
    text-align: center;
    border-bottom: none;
    color: #1e1b4b;
    margin-bottom: 0.3rem;
    padding-bottom: 0;
}

body > h1:first-child + p {
    text-align: center;
    font-style: italic;
    color: #6366f1;
    font-size: 11pt;
    margin-bottom: 1rem;
}

/* Bold rows in tables for totals/summaries */
tbody tr td strong {
    color: #312e81;
}

/* Insight headers */
h3 > strong {
    color: #6d28d9;
}

/* Page break control */
h2 {
    page-break-after: avoid;
}

table {
    page-break-inside: avoid;
}
"""

def md_to_html(md_path):
    with open(md_path, "r") as f:
        md_text = f.read()

    extensions = ["tables", "fenced_code", "codehilite", "smarty"]
    html_body = markdown.markdown(md_text, extensions=extensions)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8"/>
<style>{CSS}</style>
</head>
<body>
{html_body}
</body>
</html>"""


async def render_pdf():
    from pyppeteer import launch

    # Write HTML
    html_content = md_to_html(MD_PATH)
    with open(HTML_PATH, "w") as f:
        f.write(html_content)

    abs_html = os.path.abspath(HTML_PATH)
    print(f"HTML written to {abs_html}")

    browser = await launch(
        executablePath=CHROME,
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
    )
    page = await browser.newPage()
    await page.goto(f"file://{abs_html}", waitUntil="networkidle0", timeout=30000)
    await asyncio.sleep(2)

    await page.pdf({
        "path": PDF_PATH,
        "printBackground": True,
        "preferCSSPageSize": False,
        "format": "A4",
        "displayHeaderFooter": False,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    })
    await browser.close()

    size_kb = os.path.getsize(PDF_PATH) / 1024
    print(f"PDF rendered: {PDF_PATH} ({size_kb:.0f} KB)")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(render_pdf())
