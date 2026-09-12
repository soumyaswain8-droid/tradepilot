#!/usr/bin/env python3
"""Render ../report/candlestick-lessons-backtest.html to PDF with headless Chrome via
pyppeteer (never WeasyPrint), then run the screening pass: page count, near-blank
pages, and thumbnails of key pages for a visual look."""
import asyncio, os, subprocess, sys
from pyppeteer import launch
from pypdf import PdfReader, PdfWriter

HERE = os.path.dirname(os.path.abspath(__file__))
REP = os.path.abspath(os.path.join(HERE, "..", "report"))
WHICH = sys.argv[sys.argv.index("--which") + 1] if "--which" in sys.argv else "lessons"
NAME = {"lessons": "candlestick-lessons-backtest", "oracle": "where-the-money-was"}[WHICH]
HTML = os.path.join(REP, NAME + ".html")
PDF = os.path.join(REP, NAME + ".pdf")
QA = os.path.join(REP, "qa", WHICH)
os.makedirs(QA, exist_ok=True)


async def render():
    browser = await launch(executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
                           headless=True, args=["--no-sandbox", "--disable-gpu"])
    page = await browser.newPage()
    await page.goto(f"file://{HTML}", waitUntil="networkidle0", timeout=180000)
    await asyncio.sleep(2)
    await page.pdf({"path": PDF, "printBackground": True, "preferCSSPageSize": True,
                    "displayHeaderFooter": False, "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}})
    await browser.close()


def screen():
    r = PdfReader(PDF)
    n = len(r.pages)
    print(f"pages: {n}, size: {os.path.getsize(PDF)//1024} KB")
    for i in range(n):
        txt = r.pages[i].extract_text().strip()
        imgs = len(r.pages[i].images)
        if len(txt) < 80 and imgs == 0 and 0 < i < n - 1:
            print(f"WARNING: page {i+1} nearly blank ({len(txt)} chars, no images)")
    for p in sorted(set([1, 2, 3, n // 2, n])):
        w = PdfWriter(); w.add_page(r.pages[p - 1])
        f = os.path.join(QA, f"p{p}.pdf")
        with open(f, "wb") as fh:
            w.write(fh)
        subprocess.run(["qlmanage", "-t", "-s", "900", "-o", QA, f], capture_output=True, timeout=30)
    print("thumbnails in", QA)


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(render())
    screen()
