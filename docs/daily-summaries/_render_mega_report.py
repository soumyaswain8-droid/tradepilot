#!/usr/bin/env python3
"""Render mega report HTML to PDF using Pyppeteer + Chrome."""
import asyncio
import os

async def main():
    from pyppeteer import launch

    src = os.path.abspath(os.path.join(os.path.dirname(__file__), "2026-04-13_mega_report.md"))
    out = os.path.abspath(os.path.join(os.path.dirname(__file__), "2026-04-13_mega_report.pdf"))

    print(f"Source: {src}")
    print(f"Output: {out}")

    browser = await launch(
        executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        args=['--no-sandbox', '--disable-gpu', '--disable-setuid-sandbox']
    )
    page = await browser.newPage()
    await page.goto(f"file://{src}", waitUntil='networkidle0', timeout=30000)
    await asyncio.sleep(2)
    await page.pdf({
        'path': out,
        'printBackground': True,
        'preferCSSPageSize': True,
        'displayHeaderFooter': False,
        'format': 'A4',
        'margin': {'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
    })
    await browser.close()

    size_kb = os.path.getsize(out) / 1024
    print(f"PDF generated: {out} ({size_kb:.0f} KB)")

asyncio.get_event_loop().run_until_complete(main())
