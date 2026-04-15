#!/usr/bin/env python3
"""Render TradePilot v6 Master Plan HTML to PDF using Pyppeteer + Chrome."""
import asyncio
import os

async def render():
    from pyppeteer import launch

    base = "/Users/soumyaswain/Documents/tinker/projects/tradepilot/docs/research"
    html_path = os.path.join(base, "2026-04-12_v6_master_plan.html")
    pdf_path = os.path.join(base, "2026-04-12_v6_master_plan.pdf")

    browser = await launch(
        executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        args=['--no-sandbox', '--disable-gpu']
    )
    page = await browser.newPage()
    await page.goto(f"file://{html_path}", waitUntil='networkidle0', timeout=30000)
    await asyncio.sleep(2)
    await page.pdf({
        'path': pdf_path,
        'printBackground': True,
        'preferCSSPageSize': True,
        'displayHeaderFooter': False,
        'format': 'A4',
        'margin': {'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
    })
    await browser.close()
    print(f"PDF generated: {pdf_path}")
    sz = os.path.getsize(pdf_path)
    print(f"Size: {sz:,} bytes ({sz/1024:.0f} KB)")

asyncio.get_event_loop().run_until_complete(render())
