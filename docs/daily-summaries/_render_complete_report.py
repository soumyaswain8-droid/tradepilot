#!/usr/bin/env python3
"""Render complete trade report MD -> HTML -> PDF via Pyppeteer + Chrome."""

import asyncio
import os
import markdown

BASE = "/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/daily-summaries"
MD_PATH = os.path.join(BASE, "2026-04-10_complete_trade_report.md")
HTML_PATH = os.path.join(BASE, "2026-04-10_complete_trade_report.html")
PDF_PATH = os.path.join(BASE, "2026-04-10_complete_trade_report.pdf")
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

CSS = """
@page {
    size: A4;
    margin: 0.7in 0.6in 0.7in 0.6in;
}

* { box-sizing: border-box; }

body {
    font-family: 'Avenir Next', 'Avenir', 'Helvetica Neue', Helvetica, Arial, sans-serif;
    font-size: 10pt;
    line-height: 1.6;
    color: #1a1a2e;
    background: #ffffff;
    max-width: 100%;
    padding: 0;
    margin: 0;
}

/* Title block */
body > h1:first-child {
    font-size: 24pt;
    text-align: center;
    border-bottom: none;
    color: #1e1b4b;
    margin-top: 1.2rem;
    margin-bottom: 0.2rem;
    padding-bottom: 0;
    letter-spacing: -0.5px;
}

body > h1:first-child + p {
    text-align: center;
    font-style: italic;
    color: #6366f1;
    font-size: 11pt;
    margin-bottom: 0.3rem;
}

body > h1:first-child + p + p {
    text-align: center;
    color: #64748b;
    font-size: 9.5pt;
    margin-bottom: 0.1rem;
}

body > h1:first-child + p + p + p {
    text-align: center;
    color: #64748b;
    font-size: 9.5pt;
    margin-bottom: 1rem;
}

h1 {
    font-size: 20pt;
    font-weight: 700;
    color: #312e81;
    border-bottom: 3px solid #6366f1;
    padding-bottom: 0.35rem;
    margin-top: 1.6rem;
    margin-bottom: 0.7rem;
    letter-spacing: -0.3px;
}

h2 {
    font-size: 14pt;
    font-weight: 600;
    color: #3730a3;
    border-left: 4px solid #818cf8;
    padding-left: 0.6rem;
    margin-top: 1.4rem;
    margin-bottom: 0.5rem;
    page-break-after: avoid;
}

h3 {
    font-size: 11.5pt;
    font-weight: 600;
    color: #4338ca;
    margin-top: 1rem;
    margin-bottom: 0.35rem;
    page-break-after: avoid;
}

p {
    margin-bottom: 0.5rem;
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
    margin: 1rem 0;
}

/* Tables */
table {
    border-collapse: collapse;
    width: 96%;
    margin: 0.6rem auto;
    font-size: 8.5pt;
    page-break-inside: avoid;
    border-radius: 6px;
    overflow: hidden;
}

thead th {
    background: linear-gradient(135deg, #4f46e5, #7c3aed);
    color: white;
    font-weight: 600;
    padding: 0.45rem 0.5rem;
    text-align: left;
    font-size: 8pt;
    letter-spacing: 0.3px;
    border: none;
    white-space: nowrap;
}

thead th:first-child {
    border-radius: 6px 0 0 0;
}
thead th:last-child {
    border-radius: 0 6px 0 0;
}

tbody td {
    padding: 0.3rem 0.5rem;
    border-bottom: 1px solid #e2e8f0;
    vertical-align: top;
}

tbody tr:nth-child(odd) {
    background: #f8fafc;
}
tbody tr:nth-child(even) {
    background: #ffffff;
}

tbody tr:last-child td:first-child {
    border-radius: 0 0 0 6px;
}
tbody tr:last-child td:last-child {
    border-radius: 0 0 6px 0;
}

/* Profit cells green, loss cells red */
td {
    font-variant-numeric: tabular-nums;
}

/* Code blocks */
pre {
    background: #f5f5fa;
    border: 1px solid #e0e0eb;
    border-radius: 6px;
    padding: 0.6rem 0.8rem;
    font-family: 'Courier New', Courier, monospace;
    font-size: 8.5pt;
    line-height: 1.45;
    overflow-x: auto;
    color: #1e1b4b;
    page-break-inside: avoid;
}

code {
    font-family: 'Courier New', Courier, monospace;
    font-size: 8.5pt;
    background: #eef0f8;
    padding: 0.1rem 0.25rem;
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
    margin: 0.3rem 0 0.5rem 1.3rem;
    padding: 0;
}

li {
    margin-bottom: 0.2rem;
}

/* Bold rows in tables for totals */
tbody tr td strong {
    color: #312e81;
    font-weight: 700;
}

/* Page breaks */
h2 {
    page-break-after: avoid;
}

/* Footer */
body > p:last-child {
    text-align: center;
    color: #94a3b8;
    font-style: italic;
    font-size: 8.5pt;
    margin-top: 1.5rem;
    border-top: 1px solid #e2e8f0;
    padding-top: 0.5rem;
}
"""


def md_to_html(md_path):
    with open(md_path, "r") as f:
        md_text = f.read()

    extensions = ["tables", "fenced_code", "smarty"]
    html_body = markdown.markdown(md_text, extensions=extensions)

    # Color profit/loss values in tables
    import re
    # Green for positive P&L
    html_body = re.sub(
        r'<td>(\+[\d,]+)</td>',
        r'<td style="color:#16a34a;font-weight:600">\1</td>',
        html_body
    )
    html_body = re.sub(
        r'<td>(\+Rs[\s\d,]+)</td>',
        r'<td style="color:#16a34a;font-weight:600">\1</td>',
        html_body
    )
    html_body = re.sub(
        r'<td>(\+\d+[\.,]\d+%)</td>',
        r'<td style="color:#16a34a;font-weight:600">\1</td>',
        html_body
    )
    # Red for negative P&L
    html_body = re.sub(
        r'<td>(-[\d,]+)</td>',
        r'<td style="color:#dc2626;font-weight:600">\1</td>',
        html_body
    )
    html_body = re.sub(
        r'<td>(-\d+[\.,]\d+%)</td>',
        r'<td style="color:#dc2626;font-weight:600">\1</td>',
        html_body
    )

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
