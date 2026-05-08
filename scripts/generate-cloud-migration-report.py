#!/usr/bin/env python3
"""
Generate TradePilot Cloud Migration master report — Pyppeteer book-format PDF.

Follows the canonical PDF Book Publisher recipe:
- 7in x 10in page, margins 1in 0.75in 1in 0.875in (gutter on left)
- Body 11.5pt Charter / line-height 1.65
- Headings Avenir Next
- No forced page-break before every section — content flows naturally
- page-break-inside: avoid on all boxes
- Includes Cover, About the Author, Copyright, TOC, Body, Back cover
"""
import asyncio, base64, io, os, sys, qrcode
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import Rectangle
import numpy as np

DOCS = Path(__file__).parent.parent / "docs" / "research"
OUT_HTML = DOCS / "2026-05-08_cloud_migration_master.html"
OUT_PDF = DOCS / "2026-05-08_cloud_migration_master.pdf"

# Colour palette
INDIGO = "#635BFF"
INDIGO_DARK = "#4F46E5"
INK = "#0A2540"
INK_2 = "#3C4858"
INK_3 = "#525F7F"
GREEN = "#10B981"
RED = "#EF4444"
AMBER = "#F59E0B"
BG = "#FFFFFF"
BG_SOFT = "#F6F9FC"
HAIRLINE = "#E3E8EE"

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Avenir Next", "Avenir", "Helvetica", "Arial"],
    "axes.edgecolor": INK_3,
    "axes.labelcolor": INK,
    "xtick.color": INK_3,
    "ytick.color": INK_3,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.titleweight": "bold",
    "axes.titlecolor": INK,
})

def img_to_b64(fig, dpi=150):
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=dpi, bbox_inches="tight",
                facecolor="white", edgecolor="none")
    plt.close(fig)
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ────────── Charts ──────────
def chart_providers():
    fig, ax = plt.subplots(figsize=(8.5, 4))
    providers = ["Render\nFree", "Render\nHobby", "Railway\n2GB", "DO Bangalore\n2GB",
                 "AWS Lightsail\nMumbai 3GB", "AWS ECS\nFargate"]
    monthly_inr = [0, 580, 2900, 1660, 1650, 2500]
    static_ip_india = [False, False, False, True, True, True]
    india_only = [False, False, False, True, True, True]
    colors = []
    for ip, india in zip(static_ip_india, india_only):
        if ip and india: colors.append(INDIGO)
        elif india: colors.append(AMBER)
        else: colors.append("#CBD5E0")
    bars = ax.bar(providers, monthly_inr, color=colors, edgecolor="white", linewidth=1.5)
    ax.set_ylabel("Rs / month", fontsize=10, fontweight="bold")
    ax.set_title("Monthly cost by provider", pad=12, fontsize=12)
    ax.set_ylim(0, max(monthly_inr) * 1.2)
    for bar, v in zip(bars, monthly_inr):
        ax.text(bar.get_x() + bar.get_width()/2, v + 50,
                f"Rs {v:,}" if v else "Rs 0",
                ha="center", fontsize=9, fontweight="bold", color=INK)
    ax.grid(axis="y", linestyle="--", linewidth=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    legend = [
        mpatches.Patch(color=INDIGO, label="SEBI-ready (static IP + India)"),
        mpatches.Patch(color=AMBER, label="India region only"),
        mpatches.Patch(color="#CBD5E0", label="Paper-trade only"),
    ]
    ax.legend(handles=legend, loc="upper left", frameon=False, fontsize=8.5)
    plt.tight_layout()
    return img_to_b64(fig)

def chart_timeline():
    fig, ax = plt.subplots(figsize=(8.5, 4))
    phases = [
        ("Pre-flight",                   "2026-05-08", 2,  "#94A3B8"),
        ("Phase 1: Render dashboard",    "2026-05-10", 2,  INDIGO),
        ("Parallel run",                 "2026-05-12", 5,  "#A5B4FC"),
        ("Phase 2: Lightsail Mumbai",    "2026-05-17", 4,  INDIGO_DARK),
        ("Engine cutover",               "2026-05-21", 4,  INDIGO_DARK),
        ("Phase 3: Kite + security",     "2026-05-25", 8,  GREEN),
        ("Real money go-live",           "2026-06-02", 1,  "#22D3EE"),
    ]
    from datetime import datetime
    for i, (label, start, days, color) in enumerate(phases):
        offset = (datetime.fromisoformat(start) - datetime.fromisoformat("2026-05-08")).days
        ax.barh(i, days, left=offset, color=color, edgecolor="white",
                linewidth=2, height=0.6)
        ax.text(offset + days/2, i, f"{days}d", ha="center", va="center",
                color="white", fontweight="bold", fontsize=9)
    ax.set_yticks(range(len(phases)))
    ax.set_yticklabels([p[0] for p in phases], fontsize=9)
    ax.invert_yaxis()
    ax.set_xlabel("Days from 2026-05-08", fontsize=10, fontweight="bold")
    ax.set_title("Migration timeline", pad=12, fontsize=12)
    ax.grid(axis="x", linestyle="--", linewidth=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    ax.set_xlim(0, 30)
    plt.tight_layout()
    return img_to_b64(fig)

def chart_risks():
    fig, ax = plt.subplots(figsize=(8.5, 5))
    risks = [
        ("Cache poisoning recurs",            1, 4, INDIGO),
        ("DNS / SSL setup fails",             2, 3, AMBER),
        ("Python version mismatch",           2, 3, AMBER),
        ("Kite IP whitelist drift",           1, 5, RED),
        ("Cloud disk fills (logs)",           2, 2, INDIGO),
        ("Timezone mismatch",                 3, 2, INDIGO),
        ("Cost overrun first month",          2, 2, INDIGO),
        ("State file corruption",             1, 4, RED),
        ("yfinance throttling new IP",        2, 3, AMBER),
        ("Real-money pre-flight rushed",      2, 5, RED),
        ("Engine crash undetected",           1, 4, AMBER),
    ]
    for label, lik, imp, color in risks:
        ax.scatter(lik, imp, s=300, color=color, edgecolor="white",
                   linewidth=2, zorder=3)
        ax.annotate(label, (lik, imp), xytext=(7, 0), textcoords="offset points",
                    fontsize=8.5, color=INK, va="center")
    ax.add_patch(Rectangle((0.5, 3.5), 2, 2, facecolor="#FEE2E2", alpha=0.5, zorder=1))
    ax.add_patch(Rectangle((2.5, 3.5), 2, 2, facecolor="#FEE2E2", alpha=0.7, zorder=1))
    ax.add_patch(Rectangle((2.5, 1.5), 2, 2, facecolor="#FEF3C7", alpha=0.5, zorder=1))
    ax.add_patch(Rectangle((0.5, 1.5), 2, 2, facecolor="#FEF3C7", alpha=0.4, zorder=1))
    ax.add_patch(Rectangle((0.5, 0.5), 4, 1, facecolor="#D1FAE5", alpha=0.4, zorder=1))
    ax.text(1.0, 5.3, "MEDIUM-HIGH", fontsize=8, color="#991B1B", fontweight="bold")
    ax.text(3.2, 5.3, "CRITICAL",     fontsize=8, color="#991B1B", fontweight="bold")
    ax.text(1.0, 1.0, "LOW",          fontsize=8, color="#065F46", fontweight="bold")
    ax.set_xticks([1, 2, 3, 4])
    ax.set_xticklabels(["Rare", "Unlikely", "Possible", "Likely"])
    ax.set_yticks([1, 2, 3, 4, 5])
    ax.set_yticklabels(["Trivial", "Minor", "Moderate", "Major", "Critical"])
    ax.set_xlabel("Likelihood", fontsize=10, fontweight="bold")
    ax.set_ylabel("Impact", fontsize=10, fontweight="bold")
    ax.set_xlim(0.5, 6)
    ax.set_ylim(0.5, 5.5)
    ax.set_title("Risk register", pad=12, fontsize=12)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.4)
    ax.set_axisbelow(True)
    plt.tight_layout()
    return img_to_b64(fig)

def chart_cost():
    fig, ax = plt.subplots(figsize=(8.5, 4))
    months = ["May", "Jun", "Jul", "Aug", "Sep", "Oct",
              "Nov", "Dec", "Jan", "Feb", "Mar", "Apr"]
    render_only   = [0, 0, 580, 580, 580, 580, 580, 580, 580, 580, 580, 580]
    aws_lightsail = [825, 1650, 1650, 1650, 1650, 1650, 1650, 1650, 1650, 1650, 1650, 1650]
    full_stack    = [0, 1650, 2200, 2350, 2500, 2700, 2800, 2900, 3000, 3100, 3200, 3300]
    ax.plot(months, render_only,   marker="o", linewidth=2,   color="#A5B4FC",
            label="Render only (paper)", markersize=6)
    ax.plot(months, aws_lightsail, marker="s", linewidth=2,   color=INDIGO,
            label="AWS Lightsail Mumbai", markersize=6)
    ax.plot(months, full_stack,    marker="^", linewidth=2.5, color=INDIGO_DARK,
            label="Full stack (with Kite + Cloudflare)", markersize=6)
    ax.fill_between(range(len(months)), full_stack, alpha=0.1, color=INDIGO_DARK)
    ax.set_ylabel("Rs / month", fontsize=10, fontweight="bold")
    ax.set_title("12-month cost projection", pad=12, fontsize=12)
    ax.legend(loc="upper left", frameon=False, fontsize=9)
    ax.grid(True, linestyle="--", linewidth=0.4, alpha=0.6)
    ax.set_axisbelow(True)
    plt.tight_layout()
    return img_to_b64(fig)

def make_qr(url, color=INDIGO):
    qr = qrcode.QRCode(version=1, error_correction=qrcode.constants.ERROR_CORRECT_M,
                       box_size=10, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=color, back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode()

# ────────── HTML build ──────────
def build_html():
    chart1 = chart_providers()
    chart2 = chart_timeline()
    chart3 = chart_risks()
    chart4 = chart_cost()
    qr_linkedin = make_qr("https://www.linkedin.com/in/soumya-swain-iim/")
    qr_email    = make_qr("mailto:soumya@sidewall.in")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>TradePilot Cloud Migration — Master Plan</title>
<style>
  /* ─── Page setup ─── */
  /* Chromium doesn't reliably support @page :first margin: 0 so we use
     zero page margins and put the content margins on body padding. Cover and
     back-cover use negative margins to break out and bleed to page edges. */
  @page {{
    size: 7in 10in;
    margin: 0;
  }}

  * {{ box-sizing: border-box; }}
  html {{ margin: 0; padding: 0; }}

  body {{
    font-family: Charter, Georgia, "Times New Roman", serif;
    font-size: 11.5pt;
    line-height: 1.65;
    color: {INK};
    background: white;
    margin: 0;
    /* This padding becomes the visible page margin on body pages.
       Cover/back-cover negate this with negative margins. */
    padding: 1in 0.75in 1in 0.875in;
  }}

  h1, h2, h3, h4 {{
    font-family: "Avenir Next", "Avenir", Helvetica, sans-serif;
    color: {INK};
    line-height: 1.25;
    margin-top: 1.3em;
    margin-bottom: 0.5em;
    page-break-after: avoid;
  }}
  h1 {{ font-size: 22pt; font-weight: 700; letter-spacing: -0.01em; }}
  h2 {{ font-size: 16pt; font-weight: 700; border-bottom: 2px solid {INDIGO}; padding-bottom: 4px; margin-top: 1.5em; }}
  h3 {{ font-size: 12.5pt; font-weight: 700; color: {INDIGO_DARK}; }}
  h4 {{ font-size: 11.5pt; font-weight: 700; color: {INK}; }}

  p {{ margin: 0 0 0.6rem 0; orphans: 3; widows: 3; }}
  strong {{ font-weight: 700; color: {INK}; }}
  em {{ font-style: italic; color: {INK_3}; }}
  code {{
    font-family: "Courier New", Courier, monospace;
    font-size: 10pt;
    background: {BG_SOFT};
    padding: 1px 5px;
    border-radius: 3px;
    color: {INDIGO_DARK};
  }}

  table {{
    width: 100%;
    border-collapse: collapse;
    margin: 0.8rem 0;
    font-size: 10pt;
    page-break-inside: avoid;
  }}
  th {{
    background: linear-gradient(135deg, {INDIGO} 0%, {INDIGO_DARK} 100%);
    color: white;
    padding: 8px 10px;
    text-align: left;
    font-family: "Avenir Next", sans-serif;
    font-weight: 600;
    font-size: 9.5pt;
    letter-spacing: 0.02em;
  }}
  td {{
    padding: 7px 10px;
    border-bottom: 1px solid {HAIRLINE};
    color: {INK};
    vertical-align: top;
  }}
  tr:nth-child(even) td {{ background: {BG_SOFT}; }}

  ul, ol {{ margin: 0.4em 0 0.8em 1.4em; padding: 0; }}
  ul li, ol li {{ margin-bottom: 0.3em; }}

  /* ─── Cover (full bleed) ─── */
  /* Negative margins counter the body padding so the gradient extends edge-to-edge.
     With body padding 1in/0.75in/1in/0.875in and page size 7in × 10in, the cover
     box becomes 7in × 10in centered on the page. */
  .cover {{
    page-break-after: always;
    margin: -1in -0.75in 0 -0.875in;
    width: 7in;
    height: 10in;
    background: linear-gradient(180deg,
      #ffffff 0%, #F0F4FF 30%, #DBEAFE 60%, #C7D2FE 100%);
    padding: 1.5in 0.75in 0.5in 0.875in;
    position: relative;
  }}
  .cover .badge {{
    display: inline-block;
    background: {INDIGO};
    color: white;
    padding: 4px 14px;
    border-radius: 100px;
    font-family: "Avenir Next", sans-serif;
    font-size: 9.5pt;
    font-weight: 700;
    letter-spacing: 0.08em;
    margin-bottom: 0.4in;
  }}
  .cover h1 {{
    font-size: 38pt;
    color: #1E1B4B;
    margin: 0 0 0.2in 0;
    letter-spacing: -0.02em;
    line-height: 1.05;
    border: none;
    padding: 0;
  }}
  .cover .subtitle {{
    font-family: Charter, Georgia, serif;
    font-size: 14pt;
    font-style: italic;
    color: {INK_3};
    margin-bottom: 1.2in;
    max-width: 5in;
    line-height: 1.45;
  }}
  .cover .meta-strip {{
    position: absolute;
    bottom: 1in;
    left: 0.875in;
    right: 0.75in;
    border-top: 2px solid {INDIGO};
    padding-top: 0.25in;
  }}
  .cover .meta-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1fr;
    gap: 0.2in;
  }}
  .cover .meta-cell .label {{
    color: {INK_3};
    font-family: "Avenir Next", sans-serif;
    font-size: 8pt;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    margin-bottom: 4px;
  }}
  .cover .meta-cell .value {{
    color: {INK};
    font-family: "Avenir Next", sans-serif;
    font-weight: 700;
    font-size: 11pt;
  }}

  /* ─── Front matter (about author, copyright, TOC) ─── */
  .front-matter {{ page-break-after: always; }}
  .front-matter h1 {{ margin-top: 0; }}

  /* ─── Standard layout blocks ─── */
  .meta-block {{
    background: {BG_SOFT};
    border-left: 3px solid {INDIGO};
    padding: 14px 18px;
    margin: 1rem 0 1.4rem 0;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
  }}
  .meta-block table {{ margin: 0; }}
  .meta-block td {{ background: transparent !important; border: none; padding: 4px 0; }}
  .meta-block td:first-child {{
    width: 32%;
    color: {INK_3};
    font-weight: 600;
    font-size: 9.5pt;
    font-family: "Avenir Next", sans-serif;
  }}

  .callout {{
    background: #EFF6FF;
    border-left: 4px solid {INDIGO};
    padding: 14px 18px;
    margin: 0.9rem 0;
    border-radius: 0 6px 6px 0;
    page-break-inside: avoid;
  }}
  .callout.warn {{ background: #FFFBEB; border-color: {AMBER}; }}
  .callout.danger {{ background: #FEF2F2; border-color: {RED}; }}
  .callout.success {{ background: #F0FDF4; border-color: {GREEN}; }}
  .callout > strong:first-child {{
    display: block;
    margin-bottom: 6px;
    font-size: 9.5pt;
    font-family: "Avenir Next", sans-serif;
    text-transform: uppercase;
    letter-spacing: 0.08em;
  }}

  .chart {{
    width: 100%;
    margin: 1rem 0;
    page-break-inside: avoid;
  }}
  .chart img {{ width: 100%; height: auto; display: block; }}

  .badge-pill {{
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-family: "Avenir Next", sans-serif;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 0.05em;
    text-transform: uppercase;
  }}
  .badge-ok     {{ background: #D1FAE5; color: #065F46; }}
  .badge-warn   {{ background: #FEF3C7; color: #92400E; }}
  .badge-danger {{ background: #FEE2E2; color: #991B1B; }}

  /* ─── Author block ─── */
  .author-card {{
    border: 1px solid {HAIRLINE};
    border-radius: 8px;
    padding: 24px;
    margin: 1rem 0;
    display: grid;
    grid-template-columns: 1fr 1.4in;
    gap: 24px;
    page-break-inside: avoid;
  }}
  .author-card .who {{ font-family: "Avenir Next", sans-serif; }}
  .author-card .name {{
    font-size: 16pt;
    font-weight: 700;
    color: {INK};
    margin: 0 0 4px 0;
  }}
  .author-card .role {{
    font-size: 10pt;
    color: {INK_3};
    margin: 0 0 12px 0;
    font-family: Charter, serif;
    font-style: italic;
  }}
  .author-card .contact {{ font-size: 9.5pt; color: {INK_2}; line-height: 1.7; }}
  .author-card .contact a {{ color: {INDIGO}; text-decoration: none; }}
  .author-card .qr {{
    text-align: center;
    background: white;
    padding: 8px;
    border: 1px solid {HAIRLINE};
    border-radius: 6px;
  }}
  .author-card .qr img {{ width: 1.1in; height: 1.1in; display: block; margin: 0 auto; }}
  .author-card .qr-label {{
    font-family: "Avenir Next", sans-serif;
    font-size: 8pt;
    color: {INK_3};
    margin-top: 6px;
  }}

  /* ─── Table of Contents ─── */
  .toc {{ font-family: "Avenir Next", sans-serif; }}
  .toc-entry {{
    display: flex;
    justify-content: space-between;
    border-bottom: 1px dotted {HAIRLINE};
    padding: 8px 0;
    font-size: 11pt;
  }}
  .toc-entry .num {{
    color: {INDIGO};
    font-weight: 700;
    margin-right: 12px;
    min-width: 24px;
  }}
  .toc-entry .title {{ flex: 1; color: {INK}; }}
  .toc-entry .page {{ color: {INK_3}; font-weight: 600; }}

  /* ─── Back cover (full bleed) ─── */
  .back-cover {{
    page-break-before: always;
    margin: 0 -0.75in -1in -0.875in;
    width: 7in;
    height: 10in;
    background: linear-gradient(135deg, #1E1B4B 0%, #312E81 60%, #4338CA 100%);
    color: white;
    padding: 1.2in 0.875in 0.5in 0.875in;
    position: relative;
  }}
  .back-cover h2 {{
    color: white;
    border: none;
    font-size: 26pt;
    margin: 0 0 0.4in 0;
    padding: 0;
  }}
  .back-cover p {{ color: #C7D2FE; font-size: 13pt; line-height: 1.6; }}
  .back-cover .accent {{
    margin-top: 0.6in;
    font-family: "Avenir Next", sans-serif;
    font-size: 14pt;
    color: white;
    font-weight: 600;
  }}
  .back-cover .qr-block {{
    position: absolute;
    bottom: 0.9in;
    right: 0.875in;
    background: white;
    padding: 12px;
    border-radius: 8px;
    text-align: center;
  }}
  .back-cover .qr-block img {{ width: 1.2in; height: 1.2in; display: block; }}
  .back-cover .qr-block .qr-label {{
    color: {INK};
    font-family: "Avenir Next", sans-serif;
    font-size: 8.5pt;
    margin-top: 6px;
  }}
</style>
</head>
<body>

<!-- ============== COVER ============== -->
<div class="cover">
  <span class="badge">CLOUD MIGRATION · MASTER PLAN</span>
  <h1>TradePilot to Cloud</h1>
  <div class="subtitle">A 4-week migration from a traveling laptop to a SEBI-ready, real-money-capable cloud system. Researched 2026-05-08 in response to live trading concerns.</div>

  <div class="meta-strip">
    <div class="meta-grid">
      <div class="meta-cell">
        <div class="label">Author</div>
        <div class="value">Soumya Swain</div>
      </div>
      <div class="meta-cell">
        <div class="label">Project</div>
        <div class="value">TradePilot · Mode A</div>
      </div>
      <div class="meta-cell">
        <div class="label">Date</div>
        <div class="value">2026-05-08 · v1.0</div>
      </div>
    </div>
  </div>
</div>

<!-- ============== ABOUT THE AUTHOR ============== -->
<div class="front-matter">
  <h1>About the Author</h1>

  <div class="author-card">
    <div class="who">
      <p class="name">Soumya Swain</p>
      <p class="role">Co-founder, Sidewall · IIM MBA · fintech operator</p>
      <div class="contact">
        Email: <a href="mailto:soumya@sidewall.in">soumya@sidewall.in</a><br>
        LinkedIn: <a href="https://www.linkedin.com/in/soumya-swain-iim/">linkedin.com/in/soumya-swain-iim</a><br>
        TradePilot is built and operated by Soumya as a personal R&amp;D project,
        with paper-trading validation against Indian NSE markets.
      </div>
    </div>
    <div class="qr">
      <img src="{qr_linkedin}" alt="LinkedIn QR">
      <div class="qr-label">LinkedIn</div>
    </div>
  </div>

  <h3>About this report</h3>
  <p>This document is the synthesis of four parallel research workstreams conducted on 2026-05-08 in response to a sequence of laptop-environment bugs that surfaced through the week of 2026-05-04. The full underlying research (provider comparison, cloud architecture, security and compliance threat model, and migration plan) lives alongside this PDF in the same folder. Cross-references are linked at the back of this document.</p>
</div>

<!-- ============== COPYRIGHT & DISCLAIMER ============== -->
<div class="front-matter">
  <h1>Copyright &amp; Disclaimer</h1>

  <div class="meta-block">
    <table>
      <tr><td>Project</td><td>TradePilot</td></tr>
      <tr><td>Version</td><td><code>v1.0</code></td></tr>
      <tr><td>Status</td><td>Active · awaiting Friday pre-flight</td></tr>
      <tr><td>Created</td><td>2026-05-08</td></tr>
      <tr><td>Updated</td><td>2026-05-08</td></tr>
      <tr><td>Author</td><td>Soumya Swain</td></tr>
    </table>
  </div>

  <h3>Disclaimer</h3>
  <p>TradePilot is currently in <strong>Mode A — paper trading only</strong>. All trades referenced in this document are simulated against real-time market data. No real capital is deployed. Cost projections, regulatory commentary, and provider recommendations are based on publicly available information as of 2026-05-08 and are not investment, legal, or tax advice. SEBI compliance requirements may change; always verify current rules with a qualified compliance advisor before deploying real money.</p>

  <p>Research conducted by automated agents based on publicly available pricing pages, official documentation, and regulatory references. Pricing in INR uses an indicative USD-INR rate of 83 and may differ from actual provider invoicing. Treat all numbers as planning estimates, not contractual quotes.</p>

  <p>This document is a private working artifact. Do not redistribute outside the TradePilot project without consent.</p>
</div>

<!-- ============== TABLE OF CONTENTS ============== -->
<div class="front-matter">
  <h1>Contents</h1>
  <div class="toc">
    <div class="toc-entry"><span class="num">·</span><span class="title">Executive Summary</span><span class="page">7</span></div>
    <div class="toc-entry"><span class="num">1</span><span class="title">Provider Comparison</span><span class="page">9</span></div>
    <div class="toc-entry"><span class="num">2</span><span class="title">Architecture</span><span class="page">11</span></div>
    <div class="toc-entry"><span class="num">3</span><span class="title">Migration Timeline</span><span class="page">13</span></div>
    <div class="toc-entry"><span class="num">4</span><span class="title">Security &amp; Compliance</span><span class="page">15</span></div>
    <div class="toc-entry"><span class="num">5</span><span class="title">Cost Projection</span><span class="page">17</span></div>
    <div class="toc-entry"><span class="num">6</span><span class="title">Pre-Flight Checklist</span><span class="page">18</span></div>
    <div class="toc-entry"><span class="num">7</span><span class="title">The Decision</span><span class="page">19</span></div>
  </div>

  <p style="margin-top: 1.5rem; color: {INK_3}; font-size: 10pt; font-style: italic;">
    Page numbers are approximate; the document flows naturally and chapter headings appear at consistent positions.
  </p>
</div>

<!-- ============== EXECUTIVE SUMMARY ============== -->
<h1>Executive Summary</h1>

<div class="meta-block">
<table>
<tr><td>Trigger</td><td>Owner travels frequently · laptop in backpack with lid closed during market hours · 5 distinct laptop-environment bugs in past 2 weeks</td></tr>
<tr><td>Decision needed</td><td>Move TradePilot from laptop to cloud — by 2026-05-11 (this weekend) or 2026-05-18 (next weekend) at the latest</td></tr>
<tr><td>Recommendation</td><td>Phased migration: Render free tier → AWS Lightsail Mumbai → SEBI-compliant real money</td></tr>
<tr><td>Total cost (12 mo)</td><td>Rs 19,800 — Rs 35,000 depending on path</td></tr>
<tr><td>SEBI deadline</td><td>Static IP whitelisting with Zerodha required <strong>before</strong> any real-money trading</td></tr>
</table>
</div>

<h3>The 30-second version</h3>
<p>The laptop was never going to be a sustainable platform for an algorithmic trading system run by someone who travels. Cloud isn't an upgrade — it's the only path that addresses the actual constraints: stay-awake-in-backpack, battery, thermal, network, and the SEBI static-IP requirement that's mandatory for real-money Kite Connect trading. The plan below moves to cloud in 3 phases, each one reversible, with the first phase done this weekend.</p>

<h3>Three phases at a glance</h3>
<table>
<tr><th>Phase</th><th>Window</th><th>Goal</th><th>Cost</th><th>Risk</th></tr>
<tr><td><strong>1 · Dashboard cloud</strong></td><td>2026-05-10 / 11</td><td>Move Flask + paper-trading dashboard to Render free tier · laptop still runs engines · validates cloud setup</td><td>Rs 0/mo</td><td><span class="badge-pill badge-ok">Low</span></td></tr>
<tr><td><strong>2 · Engine cloud</strong></td><td>2026-05-17 / 24</td><td>Move 7 engines + Rust to AWS Lightsail Mumbai (3GB) · static IP · laptop becomes backup</td><td>Rs 1,650/mo</td><td><span class="badge-pill badge-warn">Medium</span></td></tr>
<tr><td><strong>3 · Real money + security</strong></td><td>2026-05-25 / 06-08</td><td>Kite Connect + JWT auth + audit logs + SEBI registration · paper-to-real-money cutover</td><td>+Rs 500-1,000/mo</td><td><span class="badge-pill badge-danger">High</span> (gated)</td></tr>
</table>

<div class="callout">
<strong>Why phased</strong>
Each phase is reversible inside 10 minutes. Phase 1 doesn't risk real money (paper only). Phase 2 builds confidence with no money at stake. Phase 3 is the only phase with regulatory and financial risk — and it's gated by phases 1 and 2 succeeding.
</div>

<!-- ============== PROVIDER COMPARISON ============== -->
<h2>1 · Provider Comparison</h2>

<p>Four agents researched 10+ providers across pricing, India region availability, static-IP support, and workload fit. The cost picture below shows what matters: <strong>SEBI-ready (real-money) deployment requires a static IP in India</strong>. PaaS-style services like Render and Railway have rotating IPs and are paper-trade-only.</p>

<div class="chart"><img src="{chart1}" alt="Provider cost comparison"></div>

<h3>The shortlist</h3>
<table>
<tr><th>Provider</th><th>Plan</th><th>RAM</th><th>India</th><th>Static IP</th><th>Rs/mo</th><th>Best for</th></tr>
<tr><td>Render</td><td>Free</td><td>512MB</td><td>No</td><td>No</td><td>0</td><td>Phase 1 — dashboard only</td></tr>
<tr><td>Render</td><td>Hobby</td><td>2GB</td><td>No</td><td>No</td><td>580</td><td>Paper-trade scaling</td></tr>
<tr><td>Railway</td><td>Hobby</td><td>2GB</td><td>SG (~150ms)</td><td>No</td><td>2,900</td><td>Skip — high latency</td></tr>
<tr><td>DigitalOcean</td><td>Bangalore 2GB</td><td>2GB</td><td>Yes</td><td>Yes (paid)</td><td>1,660</td><td>Phase 2 alternative</td></tr>
<tr><td><strong>AWS Lightsail</strong></td><td><strong>Mumbai 3GB</strong></td><td><strong>3GB</strong></td><td><strong>Yes</strong></td><td><strong>Yes</strong></td><td><strong>1,650</strong></td><td><strong>Phase 2 winner</strong></td></tr>
<tr><td>AWS ECS Fargate</td><td>Auto-scaled</td><td>Variable</td><td>Yes</td><td>Yes (NAT)</td><td>2,500+</td><td>Future scale (Phase 4+)</td></tr>
</table>

<div class="callout success">
<strong>Phase 2 winner: AWS Lightsail Mumbai 3GB at Rs 1,650/month</strong>
Sub-10ms latency to NSE servers · static IP that satisfies Kite Connect's whitelisting requirement · simpler than ECS Fargate for a one-person team · auto-renewing SSL · Ubuntu 22.04 with full SSH access · India region keeps you compliant with data residency.
</div>

<!-- ============== ARCHITECTURE ============== -->
<h2>2 · Architecture</h2>

<p>Current architecture: <code>launchd</code> + <code>nohup</code> + <code>pgrep</code> on macOS. Cloud target: <strong>Docker Compose on AWS Lightsail</strong> (Phase 2) with optional ECS Fargate path for Phase 4+ if scale demands it. Kubernetes is overkill for 7 background workers and 1 web app.</p>

<h3>Service breakdown</h3>
<table>
<tr><th>Service</th><th>Type</th><th>RAM</th><th>Restart policy</th></tr>
<tr><td>Flask dashboard</td><td>Web (Gunicorn 2 workers)</td><td>~250 MB</td><td>always</td></tr>
<tr><td>Rust engine</td><td>HTTP service (port 8081)</td><td>~100 MB</td><td>always</td></tr>
<tr><td>v4 paper-trade engine</td><td>Long-running script</td><td>~200 MB</td><td>on-failure</td></tr>
<tr><td>v5 / v5_classic / v5_6 / v5_7 / v5_8 / v6</td><td>6 long-running scripts</td><td>~150 MB each</td><td>on-failure</td></tr>
<tr><td>EOD report cron</td><td>Scheduled (16:11 IST)</td><td>~100 MB</td><td>cron</td></tr>
<tr><td>Telegram digest cron</td><td>Scheduled (every 30 min)</td><td>~50 MB</td><td>cron</td></tr>
</table>

<h3>State persistence — keep it simple</h3>
<p>Current: ~50 MB of JSON files in <code>prototype/data/</code> and <code>prototype/v*/</code>. Cloud option A (recommended): <strong>persistent volume</strong> on Lightsail, JSON files keep working. No DB migration. Cloud option B (later, when Phase 4): PostgreSQL for trade history, S3 for ML weights. <strong>Don't migrate to DB yet</strong> — adds 2 weeks of work for marginal gain at this stage.</p>

<h3>Process orchestration</h3>
<p>Replace <code>launchd</code> with <strong>Docker Compose with restart policies</strong>. One <code>docker-compose.yml</code> with the 9 services above. <code>docker compose up -d</code> on Lightsail = full system running. Cron-style scheduled jobs (auto-stop-eod, EOD report, Telegram digest) handled by <strong>system cron inside the container</strong> — simpler than EventBridge for a one-person team.</p>

<h3>CI/CD — start manual, automate later</h3>
<table>
<tr><th>Phase</th><th>Deploy method</th><th>Rollback</th></tr>
<tr><td>1 (Render)</td><td>git push, auto-deploy via Render webhook</td><td>Render dashboard "rollback to previous" button</td></tr>
<tr><td>2 (Lightsail)</td><td>git pull + docker compose restart on the VM (manual SSH)</td><td>git checkout previous SHA + restart</td></tr>
<tr><td>3+ (production)</td><td>GitHub Actions, SSH deploy with health-check gate + market-hours block</td><td>Automated rollback on health-check failure</td></tr>
</table>

<!-- ============== MIGRATION TIMELINE ============== -->
<h2>3 · Migration Timeline</h2>

<div class="chart"><img src="{chart2}" alt="Migration timeline"></div>

<h3>This weekend (Phase 1)</h3>
<table>
<tr><th>When</th><th>Task</th><th>Effort</th><th>Verifies</th></tr>
<tr><td>Fri 2026-05-09 evening</td><td>Render account · GitHub repo connected · review existing <code>render.yaml</code></td><td>30 min</td><td>Cloud account works</td></tr>
<tr><td>Sat 2026-05-10 09:00</td><td>Pre-flight checks · Docker builds locally · <code>.env.cloud</code> drafted</td><td>1 hr</td><td>Code is cloud-portable</td></tr>
<tr><td>Sat 10:00 – 12:00</td><td>First deploy to Render free tier · dashboard reachable at .onrender.com URL</td><td>2 hrs</td><td>HTTP 200, HTTPS valid</td></tr>
<tr><td>Sat 12:00 – 15:35</td><td>Parallel run · cloud dashboard alongside laptop · compare /api/engine-status data</td><td>Watch only</td><td>Data parity</td></tr>
<tr><td>Sat 16:00</td><td>EOD review — cloud rendered correctly?</td><td>15 min</td><td>End-to-end works</td></tr>
<tr><td>Sun 2026-05-11</td><td>Run cloud dashboard read-only all day · take screenshots from phone</td><td>Watch only</td><td>Mobile-accessible</td></tr>
<tr><td>Sun 14:00</td><td>Go/no-go for Phase 2 next weekend</td><td>15 min</td><td>Confidence gate</td></tr>
</table>

<h3>Cutover gates — Phase 1 must pass all 6 before Phase 2 begins</h3>
<ol>
<li>Cloud dashboard returns HTTP 200 from any device on any network</li>
<li>HTTPS certificate is valid (browser shows lock icon)</li>
<li><code>/api/engine-status</code> data matches laptop's data within 60 seconds</li>
<li>Logs visible in Render dashboard (or AWS CloudWatch)</li>
<li>No 500 errors in first 24 hours of running</li>
<li>Owner can interpret cloud logs without help</li>
</ol>

<h3>Phase 2 (next weekend)</h3>
<p><strong>2026-05-17 (Sat):</strong> Provision AWS Lightsail Mumbai 3GB. SSH access verified. Dockerfile multi-stage builds correctly. Static IP attached. <strong>2026-05-18 (Sun):</strong> Deploy 7 engines + Rust + cron via docker-compose. Run alongside laptop with state files synced via S3. Compare BUY/HOLD counts and trade decisions side-by-side for 24 hours. Cutover Monday morning if parity holds.</p>

<h3>Phase 3 (week of 2026-05-25)</h3>
<p>Add JWT auth (Flask-JWT-Extended), Flask-Limiter (10 req/min), Doppler for secrets, Cloudflare in front of Lightsail. Apply for Kite Connect production app (Rs 2,000/month). Submit static IP to Zerodha for whitelisting. Begin 5-day shadow trading: signals computed on cloud, orders go to Kite paper account first, then real account with 1% capital, scaling up over a week.</p>

<!-- ============== SECURITY & COMPLIANCE ============== -->
<h2>4 · Security &amp; Compliance</h2>

<div class="callout danger">
<strong>SEBI compliance · the non-negotiable</strong>
Individual algo traders are exempt from formal algo registration if trading <strong>under 10 orders per second</strong>. TradePilot targets 2-4 OPS, so we're inside the exemption. <strong>But</strong> Zerodha requires static IP whitelisting for any production-grade Kite Connect access — this means real money cannot trade from a laptop with a rotating IP, and not from Render or Railway either. <strong>This single requirement determines the cloud provider choice.</strong>
</div>

<h3>Threat model — the top 6</h3>
<table>
<tr><th>Threat</th><th>Likelihood</th><th>Impact</th><th>Mitigation</th></tr>
<tr><td>Kite API key leaked via git commit</td><td>Possible</td><td>Critical</td><td>Doppler secrets · pre-commit hook · GitHub secret scanning</td></tr>
<tr><td>Flask /api/paper/buy abused without auth</td><td>Likely</td><td>Major</td><td>JWT on all write endpoints · Flask-Limiter 10 req/min/IP</td></tr>
<tr><td>State file corrupted mid-write during outage</td><td>Possible</td><td>Major</td><td>Atomic writes (write-tmp-then-rename) · S3 hourly backups</td></tr>
<tr><td>Cache-poisoning style bug recurs</td><td>Likely</td><td>Moderate</td><td>Pre-market cache write block · 5-min TTL · all-NaN write rejection</td></tr>
<tr><td>Cloud provider outage during market</td><td>Unlikely</td><td>Major</td><td>Failover to laptop (paper only — real money pauses) · status-page subscription</td></tr>
<tr><td>Bad commit deploys during market hours</td><td>Possible</td><td>Critical</td><td>GitHub Actions: block production deploys 09:15-15:30 IST · canary deploy gate</td></tr>
</table>

<div class="chart"><img src="{chart3}" alt="Risk heatmap"></div>

<h3>Critical pre-launch tasks (real-money gate)</h3>
<ol>
<li><strong>Static IP registered with Zerodha</strong> — submit Lightsail IP via Kite Connect dashboard, wait 1-2 business days for whitelist confirmation</li>
<li><strong>JWT auth on all write endpoints</strong> — Flask-JWT-Extended, 15-min access tokens, 7-day refresh tokens</li>
<li><strong>Doppler secrets management</strong> — Kite api_key + api_secret + access_token (rotates daily) · Telegram bot token · Render/AWS credentials</li>
<li><strong>HTTPS-only enforcement</strong> — Render auto-provisions, Lightsail needs Let's Encrypt via certbot</li>
<li><strong>Audit log to S3 Glacier</strong> — every order decision logged immutably, 5-year retention per SEBI</li>
<li><strong>Rate limiting</strong> — Flask-Limiter on all endpoints to prevent abuse and cost spikes</li>
<li><strong>Market-hours deploy block</strong> — GitHub Actions check refuses production deploy between 09:15-15:30 IST</li>
<li><strong>Cloudflare in front</strong> — DDoS protection · WAF · Rs 1,650/month Pro tier (only needed for Phase 3)</li>
</ol>

<!-- ============== COST PROJECTION ============== -->
<h2>5 · Cost Projection</h2>

<div class="chart"><img src="{chart4}" alt="12-month cost projection"></div>

<h3>Where the money goes</h3>
<table>
<tr><th>Item</th><th>One-time</th><th>Monthly</th><th>Annual</th></tr>
<tr><td>Domain (tradepilot.in or similar)</td><td>Rs 950</td><td>—</td><td>Rs 950</td></tr>
<tr><td>Render (Phase 1, dashboard)</td><td>—</td><td>Rs 0 free / Rs 580 hobby</td><td>Rs 0 — Rs 6,960</td></tr>
<tr><td>AWS Lightsail Mumbai 3GB (Phase 2)</td><td>—</td><td>Rs 1,650</td><td>Rs 19,800</td></tr>
<tr><td>Kite Connect (Phase 3)</td><td>—</td><td>Rs 2,000</td><td>Rs 24,000</td></tr>
<tr><td>Cloudflare Pro (Phase 3, optional)</td><td>—</td><td>Rs 1,650</td><td>Rs 19,800</td></tr>
<tr><td>Doppler (free tier sufficient)</td><td>—</td><td>Rs 0</td><td>Rs 0</td></tr>
<tr><td>S3 backups + CloudWatch logs</td><td>—</td><td>Rs 250</td><td>Rs 3,000</td></tr>
<tr><td><strong>Year 1 total · paper-trading only</strong></td><td><strong>Rs 950</strong></td><td><strong>Rs 1,900 avg</strong></td><td><strong>Rs 23,750</strong></td></tr>
<tr><td><strong>Year 1 total · with real money</strong></td><td><strong>Rs 950</strong></td><td><strong>Rs 5,550 avg</strong></td><td><strong>Rs 67,550</strong></td></tr>
</table>

<div class="callout">
<strong>The Kite Connect cost is the new line item</strong>
Rs 2,000/month is real money's price of admission. It buys you a stable WebSocket tick stream (eliminates the entire yfinance NaN/cache/poll category of bugs) and the legal right to place real orders programmatically. Worth it the day you flip to real money — not before.
</div>

<!-- ============== PRE-FLIGHT CHECKLIST ============== -->
<h2>6 · Pre-Flight Checklist</h2>

<h3>Skills to learn before Saturday morning (~2 hours)</h3>
<ol>
<li><strong>Docker basics</strong> — <code>docker build</code>, <code>docker run</code>, <code>docker ps</code>, <code>docker logs</code>. Practice on local machine first.</li>
<li><strong>Reading cloud logs</strong> — Render dashboard → Logs tab. AWS Lightsail → SSH + <code>docker logs &lt;service&gt; -f</code></li>
<li><strong>HTTPS &amp; DNS basics</strong> — what an A record does, what a CNAME does, why HTTPS matters</li>
<li><strong>SSH into a VM</strong> — <code>ssh -i key.pem ubuntu@&lt;ip&gt;</code> · navigate, view logs, restart services</li>
<li><strong>Reading deployment errors</strong> — common ones: missing env var, wrong Python version, port already in use</li>
</ol>

<h3>Pre-flight checklist (do by Friday EOD)</h3>
<ul>
<li>Render account created · payment method added (even for free tier — required)</li>
<li>GitHub repo public OR Render given access to private repo</li>
<li>Local <code>docker build .</code> succeeds against current <code>Dockerfile</code></li>
<li>Local <code>docker compose up</code> brings up Flask + Rust + 7 engines</li>
<li>Backup taken of <code>~/Desktop/TradePilot/</code> from yesterday — git push to origin too</li>
<li><code>.env.cloud</code> created (a copy of <code>.env</code> with Render-specific paths)</li>
<li>Domain purchased (optional but recommended — <code>tradepilot.in</code> or similar at Rs 950)</li>
<li>Reviewed this PDF end-to-end · understands the 3 phases · agrees to phase order</li>
</ul>

<h3>Saturday morning — go/no-go gate</h3>
<p>If <strong>any</strong> of these are FALSE on Saturday 09:00, postpone Phase 1 to next weekend:</p>
<ol>
<li>Local docker compose runs all 9 services without crashes</li>
<li>You slept &gt;6 hours · not jet-lagged · not in transit</li>
<li>Stable internet · not on hotel Wi-Fi or mobile tether</li>
<li>You can dedicate the full Saturday — no client calls, no other commitments</li>
<li>Markets are closed (Saturday is fine for India)</li>
</ol>

<h3>Rollback runbook — if Phase 1 breaks Monday morning</h3>
<table>
<tr><th>Step</th><th>Action</th><th>Time</th></tr>
<tr><td>1</td><td>Render dashboard → Service settings → Suspend</td><td>30s</td></tr>
<tr><td>2</td><td>Confirm laptop engines still running: <code>./scripts/launch-market.sh --status</code></td><td>30s</td></tr>
<tr><td>3</td><td>If laptop is also down: launch it: <code>./scripts/launch-market.sh</code></td><td>1 min</td></tr>
<tr><td>4</td><td>If you bought a custom domain: revert DNS A record to laptop tunnel (or skip)</td><td>5 min</td></tr>
<tr><td>5</td><td>Telegram self-message: "Cloud rolled back, laptop is primary"</td><td>30s</td></tr>
<tr><td><strong>Total rollback</strong></td><td></td><td><strong>&lt;10 minutes</strong></td></tr>
</table>

<!-- ============== THE DECISION ============== -->
<h2>7 · The Decision</h2>

<h3>Option A · Cloud this weekend (recommended)</h3>
<p><strong>What:</strong> Render free tier · dashboard only · laptop continues running engines.<br>
<strong>Risk:</strong> <span class="badge-pill badge-ok">Low</span> — pure addition, nothing existing breaks.<br>
<strong>Effort:</strong> 4-6 hours Saturday.<br>
<strong>Outcome:</strong> Cloud dashboard reachable from anywhere, validates the migration concept, sets up Phase 2.</p>

<h3>Option B · Cloud next weekend</h3>
<p><strong>What:</strong> Same as A but week of prep first.<br>
<strong>Risk:</strong> <span class="badge-pill badge-ok">Lower</span> — more time to learn, build confidence.<br>
<strong>Effort:</strong> 1-2 hours/day this week + 4-6 hours next Saturday.<br>
<strong>Outcome:</strong> Same as A, just a week later.</p>

<h3>Option C · Skip Phase 1, jump to AWS Lightsail next weekend</h3>
<p><strong>What:</strong> Skip Render · go directly to Lightsail Mumbai.<br>
<strong>Risk:</strong> <span class="badge-pill badge-warn">Medium</span> — first cloud deploy is also your production deploy. No safety net.<br>
<strong>Effort:</strong> 8-12 hours over the weekend.<br>
<strong>Outcome:</strong> Static IP from day 1 · no Render-to-Lightsail re-migration later · costs start at Rs 1,650/mo immediately.</p>

<div class="callout success">
<strong>Recommendation: Option A</strong>
Phase 1 this weekend on Render free. It's the cheapest way to learn that cloud deployment works for your code without risk. Phase 2 next weekend on AWS Lightsail. By 2026-05-19 you have a SEBI-ready cloud system. By 2026-06-08 you can flip to real money. <strong>Total elapsed: 31 days.</strong> Total cost in those 31 days: Rs 950 (domain) + Rs 0 (Render free) + Rs 825 (half-month Lightsail). <strong>About the price of one decent dinner.</strong>
</div>

<h3>References</h3>
<ul>
<li><code>docs/research/2026-05-08_cloud_providers.md</code> — provider comparison detail</li>
<li><code>docs/research/2026-05-08_cloud_architecture.md</code> — service breakdown, deployment files</li>
<li><code>docs/research/2026-05-08_cloud_security.md</code> — SEBI, OWASP, secrets, threat model</li>
<li><code>docs/research/2026-05-08_cloud_migration_plan.md</code> — day-by-day timeline</li>
<li><code>docs/planning/WEEKEND_PLAN_2026-05-10.md</code> — execution playbook</li>
</ul>

<!-- ============== BACK COVER ============== -->
<div class="back-cover">
  <div style="height: 1.2in"></div>
  <h2>Decision time.</h2>
  <p>The laptop got us here.<br>It won't get us where you're going.</p>
  <div class="accent">2026-05-10 · 09:00 IST<br>The first deploy.</div>

  <div class="qr-block">
    <img src="{qr_email}" alt="Email QR">
    <div class="qr-label">soumya@sidewall.in</div>
  </div>
</div>

</body>
</html>"""
    OUT_HTML.write_text(html)
    print(f"HTML: {OUT_HTML}")
    return OUT_HTML

# ────────── Render PDF ──────────
async def render_pdf(html_path):
    from pyppeteer import launch
    browser = await launch(
        executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        args=["--no-sandbox", "--disable-gpu", "--disable-dev-shm-usage"],
        handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False,
    )
    page = await browser.newPage()
    await page.goto(f"file://{html_path}", waitUntil="networkidle0", timeout=60000)
    await asyncio.sleep(2)
    await page.pdf({
        "path": str(OUT_PDF),
        "printBackground": True,
        "preferCSSPageSize": True,
        "displayHeaderFooter": False,
        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
    })
    await browser.close()
    print(f"PDF: {OUT_PDF}")

if __name__ == "__main__":
    html_path = build_html()
    asyncio.get_event_loop().run_until_complete(render_pdf(str(html_path)))
    size_kb = OUT_PDF.stat().st_size // 1024
    print(f"Size: {size_kb} KB")
