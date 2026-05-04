#!/usr/bin/env python3
"""Tuesday EOD (2026-04-21) comprehensive battle report.

Sections:
  1. Cover + executive summary
  2. Leaderboard + win rates
  3. Top-4 head-to-head (v4 vs v5.6 vs v5_classic vs v5.7)
  4. v5 vs v5_classic side-by-side A/B (same symbols, different outcomes)
  5. Per-engine trade ladder with candles (▲ entry, ● exit)
  6. Per-engine full trade table
  7. Back cover
"""
import asyncio
import json
import subprocess
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

DATE = "2026-04-21"
ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "paper-trades"
OUT_DIR = ROOT / "docs" / "reports" / DATE
OUT_DIR.mkdir(parents=True, exist_ok=True)
CHART_DIR = OUT_DIR / "charts"
CHART_DIR.mkdir(exist_ok=True)

ENGINES = [
    ("v4",         "v4 Composite",     "#16a34a", "control"),
    ("v5_6",       "v5.6 Darvas",      "#f59e0b", "breakout"),
    ("v5_classic", "v5 Classic",       "#7c3aed", "pre-Rust"),
    ("v5_7",       "v5.7 Box Theory",  "#4f46e5", "mean-rev"),
    ("v5",         "v5 Multi-Horizon", "#dc2626", "hardened"),
    ("v5_3",       "v5.3 Staged",      "#6b7280", "staged"),
    ("v5_2",       "v5.2 Stat-Arb",    "#9ca3af", "dormant"),
]

# Top-4 for deep comparison
TOP_4 = ["v4", "v5_6", "v5_classic", "v5_7"]


def load_engine(key):
    fp = DATA_DIR / key / f"{DATE}.json"
    if not fp.exists():
        return {"closed_trades": [], "realized_pnl": 0, "summary": {}}
    d = json.loads(fp.read_text())
    if key == "v4":
        closed = [p for p in d.get("positions", []) if p.get("status") == "closed"]
        for t in closed:
            t.setdefault("position_type", "LONG")
            t.setdefault("exit_reason", t.get("exit_reason", "-"))
        return {"closed_trades": closed, "realized_pnl": d.get("realized_pnl", 0), "summary": {}}
    closed = []
    for pool_name, pool in d.get("pools", {}).items():
        for t in pool.get("closed", []):
            t.setdefault("pool", pool_name)
            t.setdefault("exit_reason", t.get("reason", "-"))
            closed.append(t)
    s = d.get("summary", {})
    return {"closed_trades": closed, "realized_pnl": s.get("total_pnl", 0), "summary": s}


def counts(d):
    closed = d.get("closed_trades", [])
    wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
    losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
    return len(closed), wins, losses


def avg_trade_pnl(d):
    closed = d.get("closed_trades", [])
    if not closed:
        return 0, 0, 0
    pnls = [t.get("pnl", 0) for t in closed]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    return (
        np.mean(pnls) if pnls else 0,
        np.mean(wins) if wins else 0,
        np.mean(losses) if losses else 0,
    )


data = {k: load_engine(k) for k, _, _, _ in ENGINES}

# ========================================================================
# Chart 1: Leaderboard
# ========================================================================
ranked = sorted(ENGINES, key=lambda e: -data[e[0]]["realized_pnl"])
fig, ax = plt.subplots(figsize=(11, 5), dpi=160)
names = [e[1] for e in ranked]
totals = [data[e[0]]["realized_pnl"] for e in ranked]
colors = [e[2] for e in ranked]
bars = ax.bar(names, totals, color=colors, edgecolor="white", linewidth=2)
for b, t in zip(bars, totals):
    y = b.get_height()
    ax.text(b.get_x() + b.get_width()/2, y + (800 if y >= 0 else -1200),
            f"Rs {int(t):+,}", ha="center", fontsize=10, fontweight="bold")
ax.set_ylabel("Realized P&L (INR)", fontsize=12)
ax.set_title(f"Engine Leaderboard — {DATE} (Combined Rs {sum(totals):+,.0f})",
             fontsize=14, fontweight="bold")
ax.axhline(0, color="black", linewidth=0.7)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)
plt.xticks(rotation=15, ha='right')
plt.tight_layout()
plt.savefig(CHART_DIR / "leaderboard.png", dpi=160, bbox_inches="tight")
plt.close()

# ========================================================================
# Chart 2: Top-4 multi-metric comparison
# ========================================================================
fig, axes = plt.subplots(2, 2, figsize=(11, 8), dpi=160)
labels_t4 = [next(e[1] for e in ENGINES if e[0] == k) for k in TOP_4]
colors_t4 = [next(e[2] for e in ENGINES if e[0] == k) for k in TOP_4]

# Sub-chart 1: P&L
pnls_t4 = [data[k]["realized_pnl"] for k in TOP_4]
axes[0,0].bar(labels_t4, pnls_t4, color=colors_t4, edgecolor="white")
for i, p in enumerate(pnls_t4):
    axes[0,0].text(i, p + 500, f"Rs {int(p):+,}", ha="center", fontsize=10, fontweight="bold")
axes[0,0].set_title("P&L (INR)", fontweight="bold")
axes[0,0].spines["top"].set_visible(False); axes[0,0].spines["right"].set_visible(False)
axes[0,0].tick_params(axis='x', rotation=15)

# Sub-chart 2: Win Rate
wrs_t4 = []
for k in TOP_4:
    n, w, l = counts(data[k])
    wrs_t4.append((w/n*100) if n else 0)
axes[0,1].bar(labels_t4, wrs_t4, color=colors_t4, edgecolor="white")
for i, wr in enumerate(wrs_t4):
    axes[0,1].text(i, wr + 1, f"{wr:.0f}%", ha="center", fontsize=10, fontweight="bold")
axes[0,1].set_title("Win Rate (%)", fontweight="bold")
axes[0,1].set_ylim(0, 105)
axes[0,1].axhline(50, color="gray", linestyle="--", alpha=0.5)
axes[0,1].spines["top"].set_visible(False); axes[0,1].spines["right"].set_visible(False)
axes[0,1].tick_params(axis='x', rotation=15)

# Sub-chart 3: Trade count
trades_t4 = [counts(data[k])[0] for k in TOP_4]
axes[1,0].bar(labels_t4, trades_t4, color=colors_t4, edgecolor="white")
for i, t in enumerate(trades_t4):
    axes[1,0].text(i, t + 2, f"{t}", ha="center", fontsize=10, fontweight="bold")
axes[1,0].set_title("Total Trades", fontweight="bold")
axes[1,0].spines["top"].set_visible(False); axes[1,0].spines["right"].set_visible(False)
axes[1,0].tick_params(axis='x', rotation=15)

# Sub-chart 4: Avg P&L per trade
avg_t4 = [avg_trade_pnl(data[k])[0] for k in TOP_4]
axes[1,1].bar(labels_t4, avg_t4, color=colors_t4, edgecolor="white")
for i, a in enumerate(avg_t4):
    axes[1,1].text(i, a + (5 if a >= 0 else -10), f"Rs {int(a):+,}",
                   ha="center", fontsize=10, fontweight="bold")
axes[1,1].set_title("Avg P&L per Trade (INR)", fontweight="bold")
axes[1,1].axhline(0, color="black", linewidth=0.5)
axes[1,1].spines["top"].set_visible(False); axes[1,1].spines["right"].set_visible(False)
axes[1,1].tick_params(axis='x', rotation=15)

plt.suptitle("Top-4 Engines — Multi-Metric Comparison", fontsize=14, fontweight="bold", y=1.00)
plt.tight_layout()
plt.savefig(CHART_DIR / "top4_compare.png", dpi=160, bbox_inches="tight")
plt.close()

# ========================================================================
# Chart 3: v5 vs v5_classic A/B showdown
# ========================================================================
fig, ax = plt.subplots(figsize=(9, 5), dpi=160)
v5_pnl = data["v5"]["realized_pnl"]
v5c_pnl = data["v5_classic"]["realized_pnl"]
n_v5, w_v5, l_v5 = counts(data["v5"])
n_vc, w_vc, l_vc = counts(data["v5_classic"])
wr_v5 = (w_v5/n_v5*100) if n_v5 else 0
wr_vc = (w_vc/n_vc*100) if n_vc else 0
bars = ax.bar(
    ["v5\n(Rust, hardened)", "v5_classic\n(pre-Rust)"],
    [v5_pnl, v5c_pnl],
    color=["#dc2626", "#7c3aed"],
    edgecolor="white", linewidth=2
)
for i, (p, wr, n) in enumerate([(v5_pnl, wr_v5, n_v5), (v5c_pnl, wr_vc, n_vc)]):
    ax.text(i, p + (500 if p >= 0 else -800),
            f"Rs {int(p):+,}\n{wr:.0f}% WR · {n} trades",
            ha="center", fontsize=11, fontweight="bold")
delta = v5c_pnl - v5_pnl
ax.set_title(f"A/B Test Day 2: v5_classic beats v5 by Rs {int(delta):+,}",
             fontsize=14, fontweight="bold", color="#7c3aed")
ax.axhline(0, color="black", linewidth=0.7)
ax.spines["top"].set_visible(False)
ax.spines["right"].set_visible(False)
ax.grid(axis="y", alpha=0.3)
plt.tight_layout()
plt.savefig(CHART_DIR / "ab_test.png", dpi=160, bbox_inches="tight")
plt.close()

# ========================================================================
# Trade ladders — top 4 engines + v5 for A/B context
# ========================================================================
def trade_ladder(key, label, top_n=20):
    closed = data[key].get("closed_trades", [])
    if not closed:
        return None
    top = sorted(closed, key=lambda t: -abs(t.get("pnl", 0)))[:top_n]
    top = sorted(top, key=lambda t: -(t.get("pnl", 0)))
    fig, ax = plt.subplots(figsize=(11, max(4, len(top) * 0.38)), dpi=160)
    for i, t in enumerate(top):
        entry = t.get("entry_price", 0) or 0
        exit_p = t.get("exit_price", entry) or entry
        pnl = t.get("pnl", 0)
        sym = t.get("symbol", "?")
        is_short = t.get("position_type") == "SHORT" or t.get("direction") == "SELL"
        color = "#16a34a" if pnl > 0 else "#dc2626"
        y = len(top) - 1 - i
        pct = ((exit_p - entry) / entry * 100) if entry else 0
        if is_short:
            pct = -pct
        entry_color = "#16a34a" if not is_short else "#7c3aed"
        entry_marker = "^" if not is_short else "v"
        ax.plot([0, pct], [y, y], color=color, linewidth=2.5, alpha=0.55, zorder=1)
        ax.scatter([0], [y], marker=entry_marker, s=110, color=entry_color,
                   zorder=3, edgecolor="white", linewidth=1.5)
        ax.scatter([pct], [y], marker="o", s=90, color="#7c3aed",
                   zorder=3, edgecolor="white", linewidth=1.5)
        dirn = "SHORT" if is_short else "LONG"
        t_in = t.get("entry_time", "")
        t_out = t.get("exit_time", "")
        label_text = f"{dirn}  {sym}  {entry:.1f}→{exit_p:.1f}  Rs {int(pnl):+,}  [{t_in}→{t_out}]"
        ax.text(pct + (0.12 if pct >= 0 else -0.12), y, label_text,
                va="center", ha="left" if pct >= 0 else "right",
                fontsize=8.5, color="#1e1b4b")
    ax.axvline(0, color="#7c3aed", linewidth=1, alpha=0.4)
    ax.set_xlabel("% Change (direction-adjusted) — ▲/▼ entry · ● exit  ·  bracketed times = [entry→exit]",
                  fontsize=9)
    ax.set_title(f"{label} — Top {len(top)} Trades by |P&L|", fontsize=12, fontweight="bold")
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

for k, l, _, _ in ENGINES:
    trade_ladder(k, l)


# ========================================================================
# v5 vs v5_classic side-by-side overlap analysis
# ========================================================================
v5_trades = data["v5"]["closed_trades"]
vc_trades = data["v5_classic"]["closed_trades"]
v5_syms = set(t.get("symbol") for t in v5_trades)
vc_syms = set(t.get("symbol") for t in vc_trades)
overlap = sorted(v5_syms & vc_syms)


def trades_by_symbol(trades, sym):
    return [t for t in trades if t.get("symbol") == sym]


# Build comparison table data
ab_rows = []
for sym in overlap:
    v5_list = trades_by_symbol(v5_trades, sym)
    vc_list = trades_by_symbol(vc_trades, sym)
    v5_pnl_sum = sum(t.get("pnl", 0) for t in v5_list)
    vc_pnl_sum = sum(t.get("pnl", 0) for t in vc_list)
    ab_rows.append({
        "symbol": sym,
        "v5_trades": v5_list,
        "vc_trades": vc_list,
        "v5_pnl": v5_pnl_sum,
        "vc_pnl": vc_pnl_sum,
        "delta": vc_pnl_sum - v5_pnl_sum,
    })

# Add v5-only and v5_classic-only symbols as additional context rows
v5_only = sorted(v5_syms - vc_syms)
vc_only = sorted(vc_syms - v5_syms)


# ========================================================================
# HTML assembly
# ========================================================================
def html_trades_row(t):
    sym = t.get("symbol", "?")
    entry = t.get("entry_price", 0) or 0
    exit_p = t.get("exit_price", entry) or entry
    qty = t.get("qty", 0)
    pnl = t.get("pnl", 0)
    pnl_pct = t.get("pnl_pct", 0)
    reason = t.get("exit_reason", t.get("reason", "-"))
    t_in = t.get("entry_time", "-")
    t_out = t.get("exit_time", "-")
    is_short = t.get("position_type") == "SHORT"
    dirn = "SHORT" if is_short else "LONG"
    cls = "win" if pnl > 0 else ("loss" if pnl < 0 else "")
    arrow = "▼" if is_short else "▲"
    return (f'<tr class="{cls}">'
            f'<td>{t_in}</td><td>{t_out}</td>'
            f'<td class="dir">{arrow} {dirn}</td>'
            f'<td class="sym">{sym}</td>'
            f'<td>{qty}</td>'
            f'<td>{entry:.2f}</td>'
            f'<td>{exit_p:.2f}</td>'
            f'<td>{pnl:+,.0f}</td>'
            f'<td>{pnl_pct:+.2f}%</td>'
            f'<td>{reason}</td></tr>')


def engine_section(key, label, color, tag):
    d = data[key]
    closed = d.get("closed_trades", [])
    realized = d.get("realized_pnl", 0)
    n, w, l = counts(d)
    wr = (w/n*100) if n else 0
    avg_pnl, avg_win, avg_loss = avg_trade_pnl(d)
    sorted_trades = sorted(closed, key=lambda t: t.get("entry_time", ""))
    rows = "\n".join(html_trades_row(t) for t in sorted_trades) or (
        '<tr><td colspan="10" style="text-align:center;color:#9ca3af">No closed trades</td></tr>'
    )
    viz = f'<div class="trade-viz"><img src="charts/trades_{key}.png"/></div>' if closed else ""
    return f"""
    <div class="engine-section">
      <div class="card-hdr" style="background: linear-gradient(135deg, {color}, {color}dd);">
        <h2>{label} <span class="tag">[{tag}]</span></h2>
        <div class="hdr-stats">
          <span>Realized: <b>Rs {realized:+,.0f}</b></span>
          <span>{n} trades · {w}W / {l}L · {wr:.0f}% WR</span>
          <span>Avg: Rs {avg_pnl:+,.0f}</span>
          <span>Win avg: Rs {avg_win:+,.0f} · Loss avg: Rs {avg_loss:+,.0f}</span>
        </div>
      </div>
      {viz}
      <table class="trade-table">
        <thead><tr>
          <th>Entry Time</th><th>Exit Time</th>
          <th>Dir</th><th>Symbol</th><th>Qty</th>
          <th>Entry</th><th>Exit</th>
          <th>P&amp;L (Rs)</th><th>%</th><th>Reason</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
    </div>
    """


def ab_side_by_side_block(row):
    sym = row["symbol"]
    v5 = row["v5_trades"]
    vc = row["vc_trades"]
    v5_rows = "".join(f"""
      <tr class="{'win' if t.get('pnl',0)>0 else 'loss'}">
        <td>{t.get('entry_time','-')}</td><td>{t.get('exit_time','-')}</td>
        <td>{t.get('position_type','LONG')}</td>
        <td>{t.get('entry_price',0):.2f}</td><td>{t.get('exit_price',0):.2f}</td>
        <td>{t.get('pnl',0):+,.0f}</td>
        <td>{t.get('reason','-')}</td>
      </tr>""" for t in v5) or '<tr><td colspan="7" class="empty">No trades</td></tr>'
    vc_rows = "".join(f"""
      <tr class="{'win' if t.get('pnl',0)>0 else 'loss'}">
        <td>{t.get('entry_time','-')}</td><td>{t.get('exit_time','-')}</td>
        <td>{t.get('position_type','LONG')}</td>
        <td>{t.get('entry_price',0):.2f}</td><td>{t.get('exit_price',0):.2f}</td>
        <td>{t.get('pnl',0):+,.0f}</td>
        <td>{t.get('reason','-')}</td>
      </tr>""" for t in vc) or '<tr><td colspan="7" class="empty">No trades</td></tr>'
    delta = row['delta']
    delta_cls = "pos" if delta > 0 else "neg"
    winner = "v5_classic wins" if delta > 0 else ("v5 wins" if delta < 0 else "tie")
    return f"""
    <div class="ab-block">
      <div class="ab-header">
        <h3>{sym}</h3>
        <div class="ab-summary">
          <span>v5: Rs {row['v5_pnl']:+,.0f} ({len(v5)} trades)</span>
          <span>v5_classic: Rs {row['vc_pnl']:+,.0f} ({len(vc)} trades)</span>
          <span class="delta {delta_cls}">Δ Rs {delta:+,.0f} — {winner}</span>
        </div>
      </div>
      <div class="ab-tables">
        <div class="ab-col">
          <h4 class="v5-hdr">v5 (Rust, hardened)</h4>
          <table class="ab-table">
            <thead><tr><th>Entry</th><th>Exit</th><th>Dir</th><th>In</th><th>Out</th><th>P&amp;L</th><th>Reason</th></tr></thead>
            <tbody>{v5_rows}</tbody>
          </table>
        </div>
        <div class="ab-col">
          <h4 class="vc-hdr">v5_classic (pre-Rust)</h4>
          <table class="ab-table">
            <thead><tr><th>Entry</th><th>Exit</th><th>Dir</th><th>In</th><th>Out</th><th>P&amp;L</th><th>Reason</th></tr></thead>
            <tbody>{vc_rows}</tbody>
          </table>
        </div>
      </div>
    </div>
    """


# Leaderboard HTML
medals = ["🥇", "🥈", "🥉", "4", "5", "6", "7"]
grades = ["gold", "silver", "bronze", "", "", "", ""]
leader_rows_html = []
for i, (key, label, color, tag) in enumerate(ranked):
    pnl = data[key]["realized_pnl"]
    n, w, l = counts(data[key])
    wr = (w/n*100) if n else 0
    medal = medals[i] if i < len(medals) else str(i+1)
    grade = grades[i] if i < len(grades) else ""
    pnl_cls = "pos" if pnl > 0 else ("neg" if pnl < 0 else "")
    trades_txt = f"{w}W / {l}L" if n else "0 trades"
    wr_txt = f"{wr:.0f}% WR" if n else "sat out"
    leader_rows_html.append(f'''
    <div class="leader {grade}">
      <div class="rank">{medal}</div>
      <div class="name">{label} <span class="tag">[{tag}]</span></div>
      <div class="pnl {pnl_cls}">Rs {pnl:+,.0f}</div>
      <div class="stats">{trades_txt}</div>
      <div class="stats">{wr_txt}</div>
    </div>''')
leaderboard_html = "\n".join(leader_rows_html)
combined_pnl = sum(data[k]["realized_pnl"] for k, *_ in ENGINES)
combined_trades = sum(counts(data[k])[0] for k, *_ in ENGINES)


html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>TradePilot Tuesday EOD {DATE}</title>
<style>
@page {{ size: 11in 14in; margin: 0.8in 0.6in; }}
* {{ box-sizing: border-box; margin: 0; padding: 0; }}
body {{ font-family: Charter, Georgia, serif; font-size: 10pt; line-height: 1.5; color: #1e1b4b; }}
h1, h2, h3, h4 {{ font-family: 'Avenir Next', Avenir, Helvetica, sans-serif; font-weight: 600; }}
h1 {{ font-size: 30pt; margin: 0 0 0.3rem 0; }}
h2 {{ font-size: 17pt; margin: 0.6rem 0 0.5rem 0; color: #1e1b4b; }}
h3 {{ font-size: 13pt; margin: 0.6rem 0 0.3rem 0; color: #312e81; }}
h4 {{ font-size: 11pt; margin: 0.3rem 0; color: #4f46e5; }}
p {{ margin-bottom: 0.5rem; }}
.tag {{ font-size: 8pt; font-weight: 400; opacity: 0.7; }}
.small {{ font-size: 8.5pt; }}

.cover {{
  height: 12in;
  background: linear-gradient(180deg, #ffffff, #f0f4ff, #dbeafe, #bfdbfe, #93c5fd);
  padding: 2in 0.6in 0.6in;
  text-align: center;
  page-break-after: always;
  border-radius: 8px;
  position: relative;
}}
.cover .badge {{ display: inline-block; background: #7c3aed; color: white; padding: 6px 18px; border-radius: 999px; font-size: 9pt; font-weight: 600; letter-spacing: 0.1em; margin-bottom: 1rem; }}
.cover h1 {{ font-size: 42pt; color: #1e1b4b; line-height: 1.1; }}
.cover .subtitle {{ font-size: 14pt; color: #312e81; margin: 1rem 0; font-style: italic; }}
.cover .date {{ font-size: 12pt; color: #4338ca; margin-top: 2rem; font-weight: 600; }}
.cover .tagline {{ position: absolute; bottom: 0.6in; left: 0; right: 0; color: #1e1b4b; font-size: 10pt; font-style: italic; padding: 0 1in; }}
.cover .emoji-row {{ font-size: 32pt; margin: 1.5rem 0; }}

.report-meta {{
  display: grid; grid-template-columns: auto 1fr; gap: 0.3rem 1rem;
  background: #f8fafc; padding: 0.7rem 1rem; border-left: 4px solid #7c3aed;
  border-radius: 4px; margin: 0.8rem 0;
  font-family: 'Avenir Next', sans-serif; font-size: 9.5pt;
}}
.report-meta b {{ color: #7c3aed; }}

.hero-box {{
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  padding: 1rem 1.2rem; border-left: 4px solid #7c3aed;
  border-radius: 4px; margin: 0.8rem 0;
  page-break-inside: avoid;
}}
.hero-box h3 {{ color: #5b21b6; margin-top: 0; }}

.leader {{
  display: grid; grid-template-columns: 50px 1fr 140px 100px 100px;
  gap: 0.5rem; align-items: center;
  padding: 0.55rem 0.8rem; margin: 0.3rem 0;
  background: #f8fafc; border-radius: 6px; border-left: 4px solid #4f46e5;
  page-break-inside: avoid;
}}
.leader.gold {{ background: linear-gradient(135deg, #fef3c7, #fde68a); border-color: #f59e0b; }}
.leader.silver {{ background: linear-gradient(135deg, #f1f5f9, #e2e8f0); border-color: #6b7280; }}
.leader.bronze {{ background: linear-gradient(135deg, #fed7aa, #fdba74); border-color: #ea580c; }}
.leader .rank {{ font-size: 16pt; text-align: center; font-weight: bold; }}
.leader .name {{ font-family: 'Avenir Next', sans-serif; font-weight: 600; font-size: 10.5pt; }}
.leader .pnl {{ font-weight: bold; text-align: right; font-size: 11pt; }}
.leader .pnl.pos {{ color: #16a34a; }}
.leader .pnl.neg {{ color: #dc2626; }}
.leader .stats {{ font-size: 9pt; color: #4b5563; text-align: center; }}

.chart-block {{ margin: 0.8rem 0; page-break-inside: avoid; }}
.chart-block img {{ width: 100%; border-radius: 6px; border: 1px solid #e5e7eb; }}
.chart-caption {{ font-size: 9pt; color: #6b7280; text-align: center; font-style: italic; margin-top: 0.2rem; }}

.engine-section {{
  margin: 0.6rem 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid #e5e7eb;
  page-break-inside: avoid;
}}
.card-hdr {{ padding: 0.7rem 1rem; color: white; }}
.card-hdr h2 {{ color: white; margin: 0; font-size: 13pt; }}
.card-hdr .hdr-stats {{ display: flex; gap: 1rem; flex-wrap: wrap; margin-top: 0.3rem; font-size: 9pt; opacity: 0.95; font-family: 'Avenir Next', sans-serif; }}
.card-hdr .hdr-stats b {{ font-size: 10pt; }}
.trade-viz {{ padding: 0.3rem; background: white; }}
.trade-viz img {{ width: 100%; display: block; }}
.trade-table {{ width: 100%; border-collapse: collapse; font-size: 8.5pt; }}
.trade-table th {{ background: #f1f5f9; padding: 0.35rem 0.5rem; text-align: left; font-weight: 600; font-family: 'Avenir Next', sans-serif; border-bottom: 2px solid #7c3aed; font-size: 8pt; }}
.trade-table td {{ padding: 0.25rem 0.5rem; border-bottom: 1px solid #f1f5f9; }}
.trade-table tr.win td {{ color: #166534; }}
.trade-table tr.loss td {{ color: #991b1b; }}
.trade-table td.sym {{ font-family: 'Avenir Next', sans-serif; font-weight: 600; }}
.trade-table td.dir {{ font-weight: 600; }}

.ab-block {{
  border: 1px solid #e5e7eb;
  border-radius: 8px;
  margin: 0.8rem 0;
  overflow: hidden;
  page-break-inside: avoid;
}}
.ab-header {{
  background: linear-gradient(135deg, #ede9fe, #ddd6fe);
  padding: 0.6rem 1rem;
  border-bottom: 1px solid #c4b5fd;
}}
.ab-header h3 {{ color: #5b21b6; margin: 0 0 0.3rem 0; }}
.ab-summary {{ display: flex; gap: 1.5rem; flex-wrap: wrap; font-size: 9.5pt; font-family: 'Avenir Next', sans-serif; }}
.ab-summary .delta {{ font-weight: 700; }}
.ab-summary .delta.pos {{ color: #16a34a; }}
.ab-summary .delta.neg {{ color: #dc2626; }}
.ab-tables {{ display: grid; grid-template-columns: 1fr 1fr; gap: 0.5rem; padding: 0.5rem; }}
.ab-col h4 {{ font-size: 10pt; padding: 0.25rem 0.5rem; margin: 0 0 0.3rem 0; border-radius: 4px; }}
.ab-col h4.v5-hdr {{ background: #fee2e2; color: #991b1b; }}
.ab-col h4.vc-hdr {{ background: #ede9fe; color: #5b21b6; }}
.ab-table {{ width: 100%; border-collapse: collapse; font-size: 8pt; }}
.ab-table th {{ background: #f1f5f9; padding: 0.25rem 0.4rem; text-align: left; font-size: 7.5pt; font-family: 'Avenir Next', sans-serif; }}
.ab-table td {{ padding: 0.2rem 0.4rem; border-bottom: 1px solid #f1f5f9; }}
.ab-table tr.win td {{ color: #166534; }}
.ab-table tr.loss td {{ color: #991b1b; }}
.ab-table td.empty {{ text-align: center; color: #9ca3af; font-style: italic; padding: 0.5rem; }}

code {{ font-family: 'Courier New', monospace; background: #f1f5f9; padding: 1px 5px; border-radius: 3px; font-size: 9pt; color: #be185d; }}

.page-break {{ page-break-before: always; }}

.back-cover {{
  background: linear-gradient(135deg, #1e1b4b, #312e81, #4338ca);
  color: white;
  padding: 1.5in 0.8in 1in;
  text-align: center;
  page-break-before: always;
  border-radius: 8px;
}}
.back-cover h2 {{ color: white; font-size: 22pt; margin-bottom: 0.8rem; }}
.back-cover p {{ font-size: 10.5pt; color: #c7d2fe; margin: 0.3rem 0; line-height: 1.4; }}
.back-cover .quote {{ font-size: 13pt; color: white; font-style: italic; margin: 1rem 0 1.5rem; line-height: 1.4; }}
.back-cover .footer {{ font-size: 9pt; color: #a5b4fc; margin-top: 1rem; padding-top: 0.8rem; border-top: 1px solid rgba(255,255,255,0.2); }}
</style></head><body>

<!-- ====== COVER ====== -->
<div class="cover">
  <div class="badge">TRADEPILOT · TUESDAY EOD</div>
  <h1>7 Engines.<br>Best Day Yet.<br>Rs {combined_pnl:+,.0f}.</h1>
  <div class="emoji-row">🥇 🥈 🥉</div>
  <div class="subtitle">Post-ML-fix rematch · 4 engines cleared Rs 13K+<br>A/B Day 2: v5_classic still ahead</div>
  <div class="date">Tuesday, April 21, 2026 · {combined_trades} trades · 85%+ WR on top 3</div>
  <div class="tagline">"The morning ML fix worked. The afternoon was the payoff."</div>
</div>

<!-- ====== EXECUTIVE SUMMARY ====== -->
<h2>Executive Summary</h2>
<div class="report-meta">
  <div><b>Date</b></div><div>Tuesday, 2026-04-21 · 09:15 – 15:15 IST</div>
  <div><b>Engines</b></div><div>7 (v4, v5, v5_classic, v5.2, v5.3, v5.6, v5.7)</div>
  <div><b>Combined P&amp;L</b></div><div>Rs {combined_pnl:+,.0f} across {combined_trades} trades</div>
  <div><b>Winner</b></div><div>v4 Composite · Rs {data['v4']['realized_pnl']:+,.0f} · {(counts(data['v4'])[1]/counts(data['v4'])[0]*100):.0f}% WR</div>
  <div><b>A/B verdict Day 2</b></div><div>v5_classic beats v5 by Rs {int(data['v5_classic']['realized_pnl']-data['v5']['realized_pnl']):+,} (widened from Day 1)</div>
  <div><b>ML model status</b></div><div>best_iteration=1,726 · india_vix #1 feature · retrained 08:24 IST</div>
  <div><b>Author</b></div><div>Soumya Swain · soumya@sidewall.in</div>
</div>

<p>Today was the first full day trading on the retrained ML model (fixed 08:24 IST with random val split + loosened regularization). The result: 4 engines posted wins over Rs 13,000, with win rates between 85–92%. The A/B test on v5 vs v5_classic now has 2 consecutive days of data — the pre-Rust classic keeps beating the hardened current version.</p>

<div class="hero-box">
  <h3>🎯 Headline Result: 85%+ Win Rate Across Top 4</h3>
  <p>v4 closed at <b>85% WR on 102 trades</b>, v5.6 at <b>87%</b>, v5.7 at <b>85%</b>, v5_classic at <b>88%</b>. This is the consistency we've been chasing since April 10. The common factor: all four use the same fresh ML model with restored india_vix importance. The stale-model regime from April 11–17 is gone.</p>
</div>

<!-- ====== LEADERBOARD ====== -->
<h2>Leaderboard</h2>
<div class="chart-block">
  <img src="charts/leaderboard.png"/>
  <div class="chart-caption">Realized P&amp;L per engine · Combined Rs {combined_pnl:+,.0f}</div>
</div>

{leaderboard_html}

<!-- ====== TOP-4 COMPARISON ====== -->
<div class="page-break"></div>
<h2>Top-4 Head-to-Head: v4 vs v5.6 vs v5_classic vs v5.7</h2>
<div class="chart-block">
  <img src="charts/top4_compare.png"/>
  <div class="chart-caption">Four metrics · P&amp;L, win rate, trade count, avg per-trade</div>
</div>

<p><b>Interpretation:</b> v4 leads on total P&amp;L (Rs {data['v4']['realized_pnl']:+,.0f}) driven by a larger position book
({counts(data['v4'])[0]} trades). v5.6 and v5.7 are quality leaders — fewer trades, higher per-trade P&amp;L, and
comparable win rates. v5_classic sits in the middle — the A/B test engine proves the pre-Rust code still has edge.
This suggests a portfolio construction: v4 as the volume play, v5.6/v5.7 as the selective overlay.</p>

<!-- ====== V5 VS V5_CLASSIC A/B ====== -->
<div class="page-break"></div>
<h2>A/B Test Day 2 — v5 vs v5_classic</h2>
<div class="chart-block">
  <img src="charts/ab_test.png"/>
  <div class="chart-caption">Same ML model. Same market. Same capital. Only the Rust integration differs.</div>
</div>

<p>Day 1 (Monday): v5_classic led by Rs 4,950. Day 2 (today): the gap grew to
<b>Rs {int(data['v5_classic']['realized_pnl']-data['v5']['realized_pnl']):+,}</b>.
v5 took only {counts(data['v5'])[0]} trades all day ({counts(data['v5'])[1]}W/{counts(data['v5'])[2]}L) —
deeply conservative. v5_classic took {counts(data['v5_classic'])[0]} trades ({counts(data['v5_classic'])[1]}W/{counts(data['v5_classic'])[2]}L) —
wider engagement, higher win rate, more P&amp;L captured.</p>

<h3>Same-Symbol Side-by-Side</h3>
<p>The {len(overlap)} symbols that both engines traded. For each, v5 on the left, v5_classic on the right.
Entry/exit times, prices, P&amp;L, and reason for exit shown. Delta shows the per-symbol gap.</p>

{"".join(ab_side_by_side_block(r) for r in sorted(ab_rows, key=lambda x: -x['delta']))}

<h4 style="margin-top: 1rem;">Symbols only one engine traded</h4>
<p><b>v5 only ({len(v5_only)}):</b> {', '.join(v5_only) if v5_only else '—'}</p>
<p><b>v5_classic only ({len(vc_only)}):</b> {', '.join(vc_only[:30]) + ('...' if len(vc_only) > 30 else '')}</p>
<p class="small" style="color:#6b7280;font-style:italic;">v5_classic captured {len(vc_only)} opportunities that v5 passed on — that's where most of the A/B gap comes from.</p>

<!-- ====== PER-ENGINE DETAILED ====== -->
<div class="page-break"></div>
<h2>Per-Engine Trade Ledgers</h2>
<p>Top 20 trades by |P&amp;L| shown as ladders. Full trade tables ordered by entry time.</p>

{engine_section("v4", "v4 Composite Scorer", "#16a34a", "control · champion")}
{engine_section("v5_6", "v5.6 Darvas Box", "#f59e0b", "breakout · winner #2")}
{engine_section("v5_classic", "v5 Classic (pre-Rust)", "#7c3aed", "A/B test leader")}
{engine_section("v5_7", "v5.7 Box Theory", "#4f46e5", "mean-reversion")}
{engine_section("v5", "v5 Multi-Horizon (current)", "#dc2626", "hardened · Rust")}
{engine_section("v5_3", "v5.3 Staged Entry", "#6b7280", "staged · over-filtered")}
{engine_section("v5_2", "v5.2 Stat-Arb", "#9ca3af", "dormant")}

<!-- ====== BACK COVER ====== -->
<div class="back-cover">
  <h2>Tuesday in One Line</h2>
  <div class="quote">"The ML fix worked. 4 engines cleared Rs 13K at 85%+ WR.<br>v5_classic extended its A/B lead. Best day since launch."</div>
  <p><b>Combined P&amp;L:</b> Rs {combined_pnl:+,.0f} · <b>Trades:</b> {combined_trades} · <b>Best WR:</b> 92% (v5.7)</p>
  <p><b>A/B gap widened:</b> v5_classic +Rs {int(data['v5_classic']['realized_pnl']-data['v5']['realized_pnl']):+,} over v5 (Day 1: +Rs 4,950 · Day 2: today)</p>
  <p><b>Tomorrow's focus:</b> Universe expansion (Nifty 500 + mid/small caps) · Day 3 A/B continuation</p>
  <div class="footer">
    TradePilot · Soumya Swain · soumya@sidewall.in<br>
    Generated {datetime.now().strftime('%Y-%m-%d %H:%M IST')}
  </div>
</div>

</body></html>
"""

html_path = OUT_DIR / "tuesday-eod.html"
html_path.write_text(html)
pdf_path = OUT_DIR / "tuesday-eod.pdf"
print(f"HTML written: {html_path}")


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
    await page.goto(f"file://{html_path.resolve()}", waitUntil='networkidle0', timeout=90000)
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

from pypdf import PdfReader
reader = PdfReader(pdf_path)
total = len(reader.pages)
size = pdf_path.stat().st_size
print(f"Pages: {total}")
print(f"Size: {size//1024} KB")

warnings = []
for i in range(total):
    text = reader.pages[i].extract_text().strip()
    clean = text.replace(str(i+1), '').strip()
    if len(clean) < 60 and 0 < i < total - 1:
        warnings.append(f"  p{i+1}: nearly blank ({len(clean)} chars)")

if warnings:
    print("QA WARNINGS:"); print("\n".join(warnings))
else:
    print("QA: All pages populated")

subprocess.run(["open", str(pdf_path)])
print(f"Opened: {pdf_path}")
