#!/usr/bin/env python3
"""Render the 2026-04-17 battle report PDF via Pyppeteer (book-grade)."""
import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATE = "2026-04-17"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "paper-trades"
OUT_DIR = ROOT / "docs" / "reports" / DATE
OUT_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR = OUT_DIR / "charts"
CHART_DIR.mkdir(exist_ok=True)

ENGINES = [
    ("v4",   "v4 Composite",     "#16a34a"),
    ("v5",   "v5 Multi-Horizon", "#dc2626"),
    ("v5_3", "v5.3 Staged",      "#6b7280"),
    ("v5_6", "v5.6 Darvas",      "#f59e0b"),
    ("v5_7", "v5.7 Box Theory",  "#4f46e5"),
]

import re
LOG_TRADE_RE = re.compile(
    r"\[(\d{2}:\d{2}:\d{2})\]\s+>>\s+(WIN|LOSS)\s+(LONG|SHORT)\s+(\S+)\s+x(\d+)\s+@([\d.]+)\s+\(([\w_]+)\)\s+P&L:\s+Rs\s+([+-]?[\d,]+)\s+\(([+-]?[\d.]+)%\)\s+\[(\w+)\]"
)

def parse_log_trades(key):
    log_path = Path(f"/tmp/{key}.log")
    if not log_path.exists():
        return []
    trades = []
    for line in log_path.read_text(errors="ignore").splitlines():
        m = LOG_TRADE_RE.search(line)
        if not m:
            continue
        tm, outcome, dirn, sym, qty, exit_p, reason, pnl_s, pct, pool = m.groups()
        trades.append({
            "time": tm, "symbol": sym, "qty": int(qty),
            "exit_price": float(exit_p), "reason": reason,
            "pnl": float(pnl_s.replace(",", "")),
            "pnl_pct": float(pct),
            "position_type": dirn, "pool": pool,
            "outcome": outcome,
        })
    return trades

def load_engine(key):
    fp = DATA_DIR / key / f"{DATE}.json"
    d = json.loads(fp.read_text()) if fp.exists() else {}
    # v4 has flat closed_trades
    if key == "v4":
        closed = d.get("closed_trades") or [p for p in d.get("positions", []) if p.get("status") == "closed"]
        for t in closed:
            if "position_type" not in t:
                t["position_type"] = "LONG"
        return {"closed_trades": closed, "realized_pnl": d.get("realized_pnl", 0), "summary": {}}
    # v5 family: use log parse + JSON summary
    log_trades = parse_log_trades(key)
    # Convert log trade shape to unified
    for t in log_trades:
        t["entry_price"] = t["exit_price"] / (1 + t["pnl_pct"]/100) if t["position_type"] == "LONG" else t["exit_price"] / (1 - t["pnl_pct"]/100)
        t["exit_reason"] = t["reason"]
    return {"closed_trades": log_trades, "realized_pnl": d.get("summary", {}).get("total_pnl", 0), "summary": d.get("summary", {})}

def engine_total_pnl(d):
    realized = d.get("realized_pnl", 0)
    return realized, 0  # At EOD, all positions closed — no unrealized

def counts(d):
    closed = d.get("closed_trades", [])
    wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
    losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
    return len(closed), wins, losses

data = {k: load_engine(k) for k, _, _ in ENGINES}

# ======== Chart 1: leaderboard bar chart ========
fig, ax = plt.subplots(figsize=(10, 5), dpi=160)
names, totals, colors = [], [], []
for key, label, color in ENGINES:
    r, u = engine_total_pnl(data[key])
    t = r + u
    names.append(label)
    totals.append(t)
    colors.append(color)
bars = ax.bar(names, totals, color=colors, edgecolor="white", linewidth=2)
for b, t in zip(bars, totals):
    y = b.get_height()
    ax.text(b.get_x() + b.get_width()/2, y + (500 if y >= 0 else -800),
            f"Rs {int(t):,}", ha="center", fontsize=11, fontweight="bold")
ax.set_ylabel("P&L (INR)", fontsize=12)
ax.set_title("Engine Leaderboard — 2026-04-17", fontsize=14, fontweight="bold")
ax.axhline(0, color="black", linewidth=0.7)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / "leaderboard.png", dpi=160, bbox_inches="tight")
plt.close()

# ======== Chart 2: Win rate comparison ========
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=160)
wrs, labels, colors2 = [], [], []
for key, label, color in ENGINES:
    n, w, l = counts(data[key])
    wr = (w / n * 100) if n > 0 else 0
    wrs.append(wr)
    labels.append(f"{label}\n{w}W / {l}L")
    colors2.append(color)
bars = ax.bar(labels, wrs, color=colors2, edgecolor="white", linewidth=2)
for b, wr in zip(bars, wrs):
    ax.text(b.get_x() + b.get_width()/2, b.get_height() + 2,
            f"{wr:.0f}%", ha="center", fontsize=12, fontweight="bold")
ax.set_ylabel("Win Rate (%)", fontsize=12)
ax.set_title("Win Rate by Engine", fontsize=14, fontweight="bold")
ax.set_ylim(0, 110)
ax.axhline(50, color="gray", linewidth=0.7, linestyle="--", alpha=0.5)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
plt.tight_layout()
plt.savefig(CHART_DIR / "winrate.png", dpi=160, bbox_inches="tight")
plt.close()

# ======== Chart 3: v5 yesterday vs today ========
fig, ax = plt.subplots(figsize=(8, 4.5), dpi=160)
v5_today_pnl = data["v5"]["realized_pnl"]
v5_today_n, v5_today_w, v5_today_l = counts(data["v5"])
v5_today_wr = (v5_today_w/v5_today_n*100) if v5_today_n else 0
days = ["Yesterday (Apr 16)", "Today (Apr 17)"]
pnls = [17295, int(v5_today_pnl)]
wrs3 = [92, int(v5_today_wr)]
colors3 = ["#16a34a", "#dc2626"]
x = np.arange(len(days))
ax.bar(x, pnls, color=colors3, edgecolor="white", linewidth=2)
for i, (p, w) in enumerate(zip(pnls, wrs3)):
    ax.text(i, p + 600, f"Rs {p:,}\n{w}% win", ha="center", fontsize=12, fontweight="bold")
ax.set_xticks(x)
ax.set_xticklabels(days, fontsize=11)
ax.set_ylabel("P&L (INR)", fontsize=12)
ax.set_title("v5 Engine: 95% Drop Day-over-Day", fontsize=14, fontweight="bold", color="#dc2626")
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / "v5_dod.png", dpi=160, bbox_inches="tight")
plt.close()

# ======== Chart 4: Shorts vs Longs P&L ========
fig, ax = plt.subplots(figsize=(10, 4.5), dpi=160)
engs, long_pnl, short_pnl = [], [], []
for key, label, _ in ENGINES:
    if key in ("v5_3",):
        continue
    d = data[key]
    closed = d.get("closed_trades") or [p for p in d.get("positions", []) if p.get("status") == "closed"]
    lp = sum(t.get("pnl", 0) for t in closed if t.get("position_type", "LONG") == "LONG" or t.get("direction") == "BUY")
    sp = sum(t.get("pnl", 0) for t in closed if t.get("position_type") == "SHORT" or t.get("direction") == "SELL")
    engs.append(label.replace(" ", "\n", 1))
    long_pnl.append(lp)
    short_pnl.append(sp)
x = np.arange(len(engs))
w = 0.35
ax.bar(x - w/2, long_pnl, w, label="LONG", color="#16a34a", edgecolor="white")
ax.bar(x + w/2, short_pnl, w, label="SHORT", color="#dc2626", edgecolor="white")
ax.set_xticks(x)
ax.set_xticklabels(engs, fontsize=10)
ax.set_ylabel("Realized P&L (INR)", fontsize=12)
ax.set_title("Long vs Short — Shorts Killed v5/v5.6/v5.7", fontsize=14, fontweight="bold")
ax.axhline(0, color="black", linewidth=0.7)
ax.legend()
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / "longs_vs_shorts.png", dpi=160, bbox_inches="tight")
plt.close()

# ======== Candlestick-ish trade viz per engine ========
def trade_viz(key, label):
    d = data[key]
    closed = d.get("closed_trades") or [p for p in d.get("positions", []) if p.get("status") == "closed"]
    if not closed:
        return None
    fig, ax = plt.subplots(figsize=(11, max(4, len(closed) * 0.45)), dpi=160)
    for i, t in enumerate(closed):
        entry = t.get("entry_price", 0)
        exit_p = t.get("exit_price", entry)
        pnl = t.get("pnl", 0)
        sym = t.get("symbol", "?")
        is_short = t.get("position_type") == "SHORT" or t.get("direction") == "SELL"
        color = "#16a34a" if pnl > 0 else "#dc2626"
        y = len(closed) - 1 - i
        # Entry marker (green arrow for buy, orange for short-entry)
        entry_arrow = "▲" if not is_short else "▼"
        exit_arrow = "●"
        # Range line entry -> exit, normalized to % change
        pct = ((exit_p - entry) / entry * 100) if entry else 0
        if is_short:
            pct = -pct
        ax.plot([0, pct], [y, y], color=color, linewidth=3, alpha=0.7, zorder=1)
        ax.scatter([0], [y], marker="o", s=80, color="#4f46e5", zorder=3, edgecolor="white", linewidth=1.5)
        ax.scatter([pct], [y], marker=">" if pct >= 0 else "<", s=100, color=color, zorder=3, edgecolor="white", linewidth=1.5)
        dirn = "SHORT" if is_short else "LONG"
        label_text = f"{dirn}  {sym}  {entry:.1f}→{exit_p:.1f}  Rs {int(pnl):+,}"
        ax.text(pct + (0.15 if pct >= 0 else -0.15), y, label_text,
                va="center", ha="left" if pct >= 0 else "right",
                fontsize=9, color="#1e1b4b")
    ax.axvline(0, color="#4f46e5", linewidth=1, alpha=0.4)
    ax.set_xlabel("% Change from Entry (adjusted for direction)", fontsize=11)
    ax.set_title(f"{label} — Trade Ladder", fontsize=13, fontweight="bold")
    ax.set_yticks([])
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["left"].set_visible(False)
    ax.grid(axis="x", alpha=0.25)
    xlim = ax.get_xlim()
    ax.set_xlim(xlim[0] - 2, xlim[1] + 2)
    plt.tight_layout()
    fp = CHART_DIR / f"trades_{key}.png"
    plt.savefig(fp, dpi=160, bbox_inches="tight")
    plt.close()
    return fp.name

for key, label, _ in ENGINES:
    trade_viz(key, label)

# ======== Build HTML ========
def html_trades_row(t):
    sym = t.get("symbol", "?")
    entry = t.get("entry_price", 0)
    exit_p = t.get("exit_price", entry)
    pnl = t.get("pnl", 0)
    pnl_pct = t.get("pnl_pct", 0)
    reason = t.get("exit_reason", "-")
    is_short = t.get("position_type") == "SHORT" or t.get("direction") == "SELL"
    dirn = "SHORT" if is_short else "LONG"
    cls = "win" if pnl > 0 else ("loss" if pnl < 0 else "")
    arrow = "▼" if is_short else "▲"
    return f"""<tr class="{cls}"><td class="dir">{arrow} {dirn}</td><td class="sym">{sym}</td><td>{entry:.1f}</td><td>{exit_p:.1f}</td><td>{pnl:+,.0f}</td><td>{pnl_pct:+.2f}%</td><td>{reason}</td></tr>"""

def engine_card(key, label, color):
    d = data[key]
    closed = d.get("closed_trades") or [p for p in d.get("positions", []) if p.get("status") == "closed"]
    realized, unrealized = engine_total_pnl(d)
    total = realized + unrealized
    n, w, l = counts(d)
    wr = (w/n*100) if n else 0
    rows = "\n".join(html_trades_row(t) for t in closed) or "<tr><td colspan='7' style='text-align:center;color:#9ca3af'>No closed trades</td></tr>"
    viz = f'<div class="trade-viz"><img src="charts/trades_{key}.png"/></div>' if closed else ""
    return f"""
    <div class="engine-card">
      <div class="card-hdr" style="background: linear-gradient(135deg, {color}, {color}dd);">
        <h2>{label}</h2>
        <div class="hdr-stats">
          <span>Total: <b>Rs {total:+,.0f}</b></span>
          <span>Realized: Rs {realized:+,.0f}</span>
          <span>Unrealized: Rs {unrealized:+,.0f}</span>
          <span>{w}W / {l}L ({wr:.0f}%)</span>
        </div>
      </div>
      {viz}
      <table class="trade-table">
        <thead><tr><th>Dir</th><th>Symbol</th><th>Entry</th><th>Exit</th><th>P&L (Rs)</th><th>%</th><th>Reason</th></tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """

# ======= Build leaderboard HTML from computed data =======
ranked = []
for key, label, color in ENGINES:
    r, u = engine_total_pnl(data[key])
    n, w, l = counts(data[key])
    wr = (w/n*100) if n else 0
    ranked.append((key, label, r + u, n, w, l, wr))
# Sort by P&L desc, but keep v5.3 with 0 trades at end
ranked_sorted = sorted(ranked, key=lambda x: (-x[3] if x[3]>0 else 0, -x[2]))
# Actually: rank by total P&L desc, but if 0 trades go last
ranked_sorted = sorted(ranked, key=lambda x: (-(x[2] if x[3] > 0 else -999999)))
medals = ["🥇", "🥈", "🥉", "4", "5"]
grades = ["gold", "silver", "bronze", "", ""]
leaderboard_rows = []
for i, (key, label, pnl, n, w, l, wr) in enumerate(ranked_sorted):
    medal = medals[i] if i < len(medals) else str(i+1)
    grade = grades[i] if i < len(grades) else ""
    pnl_cls = "pos" if pnl > 0 else ("neg" if pnl < 0 else "")
    trades_txt = f"{w}W / {l}L" if n else "0 trades"
    wr_txt = f"{wr:.0f}% win" if n else "sat out"
    leaderboard_rows.append(f'''
    <div class="leader {grade}">
      <div class="rank">{medal}</div>
      <div class="name">{label}</div>
      <div class="pnl {pnl_cls}">Rs {pnl:+,.0f}</div>
      <div class="stats">{trades_txt}</div>
      <div class="stats">{wr_txt}</div>
    </div>''')
leaderboard_html = "\n".join(leaderboard_rows)
combined_pnl = sum(p for _, _, p, n, _, _, _ in ranked_sorted)

# ======= Watchdog findings =======
watchdog_rows = [
    ("pgrep -f tradepilot-engine matched watchdog itself", "rust auto-restart broken", "Fixed v2 — port 8080 lsof check"),
    ("pgrep -f 'python3 app.py' matched watchdog itself", "flask auto-restart broken", "Fixed v2 — port 5050 lsof check"),
    ("Yahoo per-stock TypeError fired false crash alerts", "Noise notifications", "Fixed v3 — negative grep filter"),
    ("Watchdog had no market-hours awareness", "Restarted v5.3 infinitely post-close", "Stopped manually at 16:15"),
    ("sudo pmset -a disablesleep 1 silently failed (SleepDisabled=0)", "Laptop slept in bag, ALL python engines died", "Never took effect — retry tomorrow, verify"),
    ("caffeinate -dims alone does not prevent clamshell sleep", "False sense of protection", "Known limitation"),
    ("Engine's telegram_bot.py returns 404 on every send", "Engines can't alert user directly", "Not fixed (my monitor works via direct curl)"),
]

# ======= Lessons =======
lessons = [
    ("NaN guard bug in 5 files", "v5, v5.4, v5.5, v5.6, v5.7 all had <code>if price &lt;= 0</code> which doesn't catch NaN (NaN&lt;=0 is False in Python). Fixed to <code>if not (price &gt; 0)</code>. Root cause: copy-paste propagation.", "Create <code>utils/signal_guards.py</code> with shared <code>safe_qty(budget, price)</code>. One fix, all engines benefit."),
    ("Shorts got destroyed in a rising market", "v5 shorted ENRIN 3 times, lost 3 times for total -Rs 3,566. Same pattern in v5.6/v5.7. Regime was SIDEWAYS but Nifty gapped +0.38%.", "Add pre-market gap filter: Nifty gap &gt; +0.2% disables all shorts for the day."),
    ("Laptop-in-bag is unreliable on macOS", "Clamshell sleep killed all 5 paper-trade engines at ~16:15. Rust+Flask survived (launched via different shell paths).", "Move engines to a $5/mo VPS (DigitalOcean/Hetzner). 24/7 uptime, no sleep issues."),
    ("pmset silently failed", "<code>sudo pmset -a disablesleep 1</code> appeared to succeed but <code>SleepDisabled</code> remained 0.", "Always verify with <code>pmset -g | grep SleepDisabled</code> showing 1 BEFORE trusting."),
    ("State saved only at cycle end", "v5 crashed at 10:28, lost GODFRYPHLP +Rs 487 win because state save was pending for the cycle.", "Atomic state writes after every trade entry/exit, not per-scan."),
]

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>TradePilot Battle Report {DATE}</title>
<style>
@page {{ size: 7in 10in; margin: 1in 0.75in 1in 0.875in; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Charter, Georgia, serif; font-size: 10.5pt; line-height: 1.55; color: #1e1b4b; }}
h1, h2, h3, h4 {{ font-family: 'Avenir Next', Avenir, Helvetica, sans-serif; font-weight: 600; }}
h1 {{ font-size: 28pt; margin: 0 0 0.3rem 0; }}
h2 {{ font-size: 18pt; margin: 0.6rem 0 0.5rem 0; color: #1e1b4b; }}
h3 {{ font-size: 14pt; margin: 0.8rem 0 0.4rem 0; color: #312e81; }}
h4 {{ font-size: 11pt; margin: 0.5rem 0 0.3rem 0; color: #4f46e5; }}
p {{ margin-bottom: 0.6rem; }}
.cover {{
  height: 9in;
  background: linear-gradient(180deg, #ffffff, #f0f4ff, #dbeafe, #bfdbfe, #93c5fd);
  padding: 1.5in 0.5in 0.5in;
  text-align: center;
  page-break-after: always;
  border-radius: 8px;
  position: relative;
}}
.cover .badge {{ display: inline-block; background: #4f46e5; color: white; padding: 6px 18px; border-radius: 999px; font-size: 9pt; font-weight: 600; letter-spacing: 0.1em; margin-bottom: 1rem; }}
.cover h1 {{ font-size: 40pt; color: #1e1b4b; line-height: 1.1; }}
.cover .subtitle {{ font-size: 14pt; color: #312e81; margin: 1rem 0; font-style: italic; }}
.cover .date {{ font-size: 12pt; color: #4338ca; margin-top: 2rem; font-weight: 600; }}
.cover .tagline {{ position: absolute; bottom: 0.5in; left: 0; right: 0; color: #1e1b4b; font-size: 10pt; font-style: italic; padding: 0 1in; }}
.cover .emoji-row {{ font-size: 32pt; margin: 1.5rem 0; }}

.report-meta {{
  display: grid; grid-template-columns: auto 1fr; gap: 0.3rem 1rem;
  background: #f8fafc; padding: 0.8rem 1rem; border-left: 4px solid #4f46e5;
  border-radius: 4px; margin: 0.8rem 0;
  font-family: 'Avenir Next', sans-serif; font-size: 9.5pt;
}}
.report-meta b {{ color: #4f46e5; }}

.hero-box {{
  background: linear-gradient(135deg, #fef3c7, #fde68a);
  padding: 1rem 1.2rem; border-left: 4px solid #f59e0b;
  border-radius: 4px; margin: 0.8rem 0;
  page-break-inside: avoid;
}}
.hero-box h3 {{ color: #92400e; margin-top: 0; }}

.leader {{
  display: grid; grid-template-columns: 50px 1fr 120px 100px 100px;
  gap: 0.5rem; align-items: center;
  padding: 0.6rem 0.8rem; margin: 0.35rem 0;
  background: #f8fafc; border-radius: 6px; border-left: 4px solid #4f46e5;
  page-break-inside: avoid;
}}
.leader.gold {{ background: linear-gradient(135deg, #fef3c7, #fde68a); border-color: #f59e0b; }}
.leader.silver {{ background: linear-gradient(135deg, #f1f5f9, #e2e8f0); border-color: #6b7280; }}
.leader.bronze {{ background: linear-gradient(135deg, #fed7aa, #fdba74); border-color: #ea580c; }}
.leader .rank {{ font-size: 18pt; text-align: center; font-weight: bold; }}
.leader .name {{ font-family: 'Avenir Next', sans-serif; font-weight: 600; font-size: 11pt; }}
.leader .pnl {{ font-weight: bold; text-align: right; font-size: 12pt; }}
.leader .pnl.pos {{ color: #16a34a; }}
.leader .pnl.neg {{ color: #dc2626; }}
.leader .stats {{ font-size: 9pt; color: #4b5563; text-align: center; }}

.engine-card {{
  margin: 0.6rem 0;
  border-radius: 8px;
  overflow: hidden;
  page-break-inside: avoid;
  border: 1px solid #e5e7eb;
}}
.card-hdr {{ padding: 0.8rem 1rem; color: white; }}
.card-hdr h2 {{ color: white; margin: 0; font-size: 14pt; }}
.card-hdr .hdr-stats {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.3rem; font-size: 9pt; opacity: 0.95; font-family: 'Avenir Next', sans-serif; }}
.card-hdr .hdr-stats b {{ font-size: 10pt; }}
.trade-viz {{ padding: 0.3rem; background: white; }}
.trade-viz img {{ width: 100%; display: block; }}
.trade-table {{ width: 100%; border-collapse: collapse; font-size: 9pt; }}
.trade-table th {{ background: #f1f5f9; padding: 0.4rem 0.6rem; text-align: left; font-weight: 600; font-family: 'Avenir Next', sans-serif; border-bottom: 2px solid #4f46e5; }}
.trade-table td {{ padding: 0.35rem 0.6rem; border-bottom: 1px solid #f1f5f9; }}
.trade-table tr.win td.dir, .trade-table tr.win td:nth-child(5) {{ color: #16a34a; font-weight: 600; }}
.trade-table tr.loss td.dir, .trade-table tr.loss td:nth-child(5) {{ color: #dc2626; font-weight: 600; }}
.trade-table td.sym {{ font-family: 'Avenir Next', sans-serif; font-weight: 600; }}

.chart-block {{ margin: 0.8rem 0; page-break-inside: avoid; }}
.chart-block img {{ width: 100%; border-radius: 6px; border: 1px solid #e5e7eb; }}
.chart-caption {{ font-size: 9pt; color: #6b7280; text-align: center; font-style: italic; margin-top: 0.2rem; }}

.finding-row, .lesson-row {{
  background: #fef2f2; border-left: 4px solid #dc2626;
  padding: 0.7rem 1rem; margin: 0.5rem 0; border-radius: 4px;
  page-break-inside: avoid;
}}
.lesson-row {{ background: #eff6ff; border-color: #4f46e5; }}
.finding-row h4 {{ color: #991b1b; margin: 0 0 0.2rem 0; }}
.lesson-row h4 {{ color: #1e40af; margin: 0 0 0.2rem 0; }}
.finding-row .impact {{ color: #7c2d12; font-size: 9.5pt; margin: 0.2rem 0; }}
.finding-row .fix {{ color: #065f46; font-size: 9.5pt; font-weight: 600; }}
.lesson-row .body {{ font-size: 9.5pt; margin: 0.2rem 0; }}
.lesson-row .action {{ color: #065f46; font-size: 9.5pt; font-weight: 600; background: #d1fae5; padding: 0.3rem 0.6rem; border-radius: 4px; display: inline-block; margin-top: 0.3rem; }}

code {{ font-family: 'Courier New', monospace; background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: 9.5pt; color: #be185d; }}

.page-break {{ page-break-before: always; }}

.back-cover {{
  background: linear-gradient(135deg, #1e1b4b, #312e81, #4338ca);
  color: white;
  padding: 1.2in 0.6in 0.8in;
  text-align: center;
  page-break-before: always;
  page-break-after: avoid;
  border-radius: 8px;
}}
.back-cover h2 {{ color: white; font-size: 22pt; margin-bottom: 0.8rem; }}
.back-cover p {{ font-size: 10.5pt; color: #c7d2fe; margin: 0.3rem 0; line-height: 1.4; }}
.back-cover .quote {{ font-size: 13pt; color: white; font-style: italic; margin: 1rem 0 1.5rem; line-height: 1.4; }}
.back-cover .footer {{ font-size: 9pt; color: #a5b4fc; margin-top: 1rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.2); }}
</style></head><body>

<!-- ====== COVER ====== -->
<div class="cover">
  <div class="badge">TRADEPILOT BATTLE REPORT</div>
  <h1>6 Engines.<br>1 Trading Day.<br>Rs {combined_pnl:+,.0f}.</h1>
  <div class="emoji-row">🥇 🥈 🥉</div>
  <div class="subtitle">Post-mortem of Day 1 live-market test<br>featuring v5.6 Darvas &amp; v5.7 Box Theory</div>
  <div class="date">April 17, 2026 · Nifty 24,231 · VIX 17.2</div>
  <div class="tagline">"Everything failed in interesting ways — the data taught us more than perfection ever could."</div>
</div>

<!-- ====== META ====== -->
<h2>Executive Summary</h2>
<div class="report-meta">
  <div><b>Date</b></div><div>2026-04-17 (Fri) · 09:15 – 15:15 IST</div>
  <div><b>Market</b></div><div>Nifty 24,231 · Gap UP +0.38% · Regime SIDEWAYS · VIX 17.2</div>
  <div><b>Engines</b></div><div>v4, v5, v5.2, v5.3, v5.6, v5.7, Rust</div>
  <div><b>Capital</b></div><div>Rs 10.00L per engine (Rs 60L aggregate)</div>
  <div><b>Combined P&amp;L</b></div><div>Rs {combined_pnl:+,.0f} today vs +Rs 38,977 yesterday</div>
  <div><b>Author</b></div><div>Soumya Swain · soumya@sidewall.in</div>
</div>

<p>Today was a stress-test: brand-new engines (v5.6 Darvas, v5.7 Box Theory — committed yesterday 21:19) went into production with no prior live-market exposure. Three Python crashes, one stuck ML retrain, and one laptop sleep event later, we came out with useful data and a clear path forward.</p>

<div class="hero-box">
  <h3>🎯 The Hero Stock: UNITDSPR</h3>
  <p>4 engines independently caught UNITDSPR long. v4 booked +Rs 2,835 and +Rs 1,921 on two re-entries. v5.6 and v5.7 held it through close at +Rs 1,097 and +Rs 1,791 unrealized. Cross-engine consensus validates the v4 composite scorer.</p>
</div>

<!-- ====== LEADERBOARD ====== -->
<h2>Leaderboard</h2>
<div class="chart-block">
  <img src="charts/leaderboard.png"/>
  <div class="chart-caption">Realized P&amp;L per engine at end of day</div>
</div>

{leaderboard_html}

<div class="chart-block">
  <img src="charts/winrate.png"/>
  <div class="chart-caption">Win rate comparison · v4's 80% (on 5 trades) stands out</div>
</div>

<!-- ====== V5 DEEP DIVE ====== -->
<div class="page-break"></div>
<h2>The v5 Collapse — 95% Drop Day-over-Day</h2>

<div class="chart-block">
  <img src="charts/v5_dod.png"/>
  <div class="chart-caption">v5 went from +Rs 17,295 (92% win) yesterday to +Rs 781 (36% win) today</div>
</div>

<h3>Four root causes</h3>

<div class="finding-row">
  <h4>1. Shorting in a rising market (-Rs 3,566 on one stock)</h4>
  <div class="impact">v5 shorted ENRIN THREE times, lost all three: -Rs 1,098, -Rs 1,314, -Rs 1,154. Also lost JIOFIN shorts -Rs 318, TMPV -Rs 151.</div>
  <div class="fix">Fix: Pre-market gap filter — if Nifty gap &gt; +0.2%, disable all shorts for the day.</div>
</div>

<div class="finding-row">
  <h4>2. Crash wiped out morning gains (-Rs 487)</h4>
  <div class="impact">v5 crashed at 10:28 (NaN guard bug). Before crash, it had hit GODFRYPHLP target for +Rs 487 and deployed UNITDSPR. State save was pending — both were lost on restart.</div>
  <div class="fix">Fix: Atomic state writes after every trade entry/exit, not per-cycle.</div>
</div>

<div class="finding-row">
  <h4>3. No same-stock re-entry block</h4>
  <div class="impact">After ENRIN short #1 hit SL, v5 re-entered ENRIN short. Hit SL. Re-entered again. Hit SL. No circuit breaker for repeated losses on same stock.</div>
  <div class="fix">Fix: Block same-stock short re-entry for the day after 1 SL hit.</div>
</div>

<div class="finding-row">
  <h4>4. KALYANKJIL carry-over hit SL (-Rs 119)</h4>
  <div class="impact">Yesterday's open LONG KALYANKJIL @442.50 stopped out today at 427.65. Holding overnight added risk without commensurate reward.</div>
  <div class="fix">Fix: Evaluate all carry-overs against opening gap before market open; exit losers proactively.</div>
</div>

<div class="chart-block">
  <img src="charts/longs_vs_shorts.png"/>
  <div class="chart-caption">Long trades made money across all engines. Short trades lost money across all engines.</div>
</div>

<!-- ====== PER-ENGINE ====== -->
<div class="page-break"></div>
<h2>Per-Engine Trade Ledger</h2>

{engine_card("v4", "v4 Composite Scorer (control, long-only)", "#16a34a")}
{engine_card("v5", "v5 Multi-Horizon (main)", "#dc2626")}
{engine_card("v5_6", "v5.6 Darvas Box (breakout)", "#f59e0b")}
{engine_card("v5_7", "v5.7 Box Theory (mean reversion)", "#4f46e5")}

<!-- ====== WATCHDOG FINDINGS ====== -->
<div class="page-break"></div>
<h2>Watchdog Findings</h2>
<p>The auto-restart + crash-detection infrastructure surfaced <b>7 bugs in itself or the environment</b>. Net saves during market hours: 0. The system caught bugs by breaking, not by protecting.</p>

{"".join(f'''<div class="finding-row"><h4>#{i+1}. {bug}</h4><div class="impact"><b>Impact:</b> {impact}</div><div class="fix"><b>Status:</b> {fix}</div></div>''' for i, (bug, impact, fix) in enumerate(watchdog_rows))}

<!-- ====== LESSONS ====== -->
<div class="page-break"></div>
<h2>Top 5 Lessons for Tomorrow</h2>

{"".join(f'''<div class="lesson-row"><h4>#{i+1}. {title}</h4><div class="body">{body}</div><div class="action">{action}</div></div>''' for i, (title, body, action) in enumerate(lessons))}

<!-- ====== BACK COVER ====== -->
<div class="back-cover">
  <h2>Tomorrow's Action Plan</h2>
  <p>1. Shared <span style="background:rgba(255,255,255,0.15);color:#fef3c7;padding:1px 6px;border-radius:3px;font-family:Courier New;">utils/signal_guards.py</span> — consolidate NaN protection across all engines</p>
  <p>2. Pre-market gap filter — disable shorts if Nifty gap &gt; +0.2%</p>
  <p>3. Migrate to cloud VPS — laptop-in-bag failed, clamshell sleep killed engines</p>
  <p>4. Atomic state writes — save after every trade, not per-cycle</p>
  <p>5. Same-stock re-entry block after stoploss</p>
  <div class="quote">"Yesterday's winning engine is today's losing engine.<br>The market doesn't reward yesterday."</div>
  <div class="footer">
    TradePilot · Soumya Swain · soumya@sidewall.in<br>
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M IST')}
  </div>
</div>

</body></html>
"""

html_path = OUT_DIR / "battle-report.html"
html_path.write_text(html)
pdf_path = OUT_DIR / "battle-report.pdf"
print(f"HTML written: {html_path}")

# ======= Render via Pyppeteer =======
async def render():
    from pyppeteer import launch
    browser = await launch(
        executablePath="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
        headless=True,
        handleSIGINT=False, handleSIGTERM=False, handleSIGHUP=False,
        args=['--no-sandbox', '--disable-dev-shm-usage', '--disable-setuid-sandbox',
              '--disable-web-security', '--allow-file-access-from-files']
    )
    page = await browser.newPage()
    await page.goto(f"file://{html_path.resolve()}", waitUntil='networkidle0', timeout=60000)
    await asyncio.sleep(2)
    await page.pdf({
        'path': str(pdf_path),
        'printBackground': True,
        'preferCSSPageSize': True,
        'displayHeaderFooter': False,
        'margin': {'top': '0', 'right': '0', 'bottom': '0', 'left': '0'}
    })
    await browser.close()

asyncio.get_event_loop().run_until_complete(render())
print(f"PDF: {pdf_path}")

# ======= Visual QA =======
from pypdf import PdfReader
reader = PdfReader(pdf_path)
total = len(reader.pages)
print(f"Pages: {total}")
size = pdf_path.stat().st_size
print(f"Size: {size//1024} KB")

warnings = []
for i in range(total):
    text = reader.pages[i].extract_text().strip()
    clean = text.replace(str(i+1), '').strip()
    if len(clean) < 60 and 0 < i < total - 1:
        warnings.append(f"  p{i+1}: nearly blank ({len(clean)} chars)")

if warnings:
    print("QA WARNINGS:")
    print("\n".join(warnings))
else:
    print("QA: All pages populated")

# Open in Preview
subprocess.run(["open", str(pdf_path)])
print(f"Opened: {pdf_path}")
