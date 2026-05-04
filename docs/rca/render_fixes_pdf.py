"""Render tonight's fixes summary to PDF + run visual QA."""
import asyncio
import subprocess
from pathlib import Path
from pyppeteer import launch
from pypdf import PdfReader, PdfWriter

HERE = Path(__file__).parent
HTML = HERE / "2026-05-01_fixes_applied.html"
PDF = HERE / "2026-05-01_fixes_applied.pdf"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"


async def render():
    import tempfile
    user_dir = tempfile.mkdtemp(prefix="tp-pdf-")
    browser = await launch(
        executablePath=CHROME, headless=True,
        args=["--no-sandbox", "--disable-gpu", f"--user-data-dir={user_dir}"],
    )
    page = await browser.newPage()
    await page.goto(f"file://{HTML.resolve()}", waitUntil="networkidle0", timeout=60000)
    await asyncio.sleep(2)
    await page.pdf({
        "path": str(PDF),
        "printBackground": True,
        "preferCSSPageSize": True,
        "displayHeaderFooter": False,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    })
    await browser.close()


def qa():
    reader = PdfReader(PDF)
    total = len(reader.pages)
    print(f"PDF: {PDF.name}  pages={total}  size={PDF.stat().st_size/1024:.1f} KB")

    warnings = []
    for i in range(total):
        text = reader.pages[i].extract_text().strip()
        clean = text.replace(str(i + 1), "").strip()
        if len(clean) < 80 and i > 0 and i < total - 1:
            warnings.append(f"  WARN p{i+1}: only {len(clean)} chars")

    print("\n".join(warnings) if warnings else "No near-blank pages.")

    qa_pages = sorted({1, 2, max(1, total // 2), max(1, total - 1), total})
    for p in qa_pages:
        if 1 <= p <= total:
            w = PdfWriter()
            w.add_page(reader.pages[p - 1])
            single = HERE / f"qa_fx_p{p}.pdf"
            with open(single, "wb") as f:
                w.write(f)
            subprocess.run(["qlmanage", "-t", "-s", "900", "-o", str(HERE), str(single)],
                           capture_output=True, timeout=15)
            print(f"  qa_fx_p{p}.pdf.png")


if __name__ == "__main__":
    asyncio.get_event_loop().run_until_complete(render())
    qa()
