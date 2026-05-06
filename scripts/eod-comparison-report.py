#!/usr/bin/env python3
"""
EOD Side-by-Side Engine Comparison Report.

Reads today's engine JSON files + snapshot timeline (from profit-watchdog)
and produces:
  docs/watchdog/reports/YYYY-MM-DD_eod/
    report.html       (rich HTML — colors, tables, charts)
    report.pdf        (Pyppeteer render)
    charts/*.png      (matplotlib charts)
    data.json         (all raw analysis — for future diffing)

Sections in the report:
  1. Scoreboard — all engines ranked by P&L
  2. P&L timeline chart — how each engine did through the day
  3. Trade overlap matrix — which engines took the same trade
  4. Exit reason mix per engine — TARGET vs STOPLOSS vs SIGNAL_FLIP
  5. Winners & losers per engine — top 5 each
  6. Hour-of-day performance — when does each engine make/lose money
  7. "Tonight's tune-ups" — auto-surfaced patterns

Run:
  python3 scripts/eod-comparison-report.py            # today
  python3 scripts/eod-comparison-report.py 2026-04-22 # specific date
"""
from __future__ import annotations

import asyncio
import json
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "docs" / "paper-trades"
WATCH = ROOT / "docs" / "watchdog"
REPORTS = WATCH / "reports"

ENGINES = ["v4", "v5", "v5_classic", "v5_2", "v5_3", "v5_6", "v5_7", "v5_8", "v6"]

PALETTE = {
    "v4":         "#64748b",
    "v5":         "#2563eb",
    "v5_classic": "#0ea5e9",
    "v5_2":       "#7c3aed",
    "v5_3":       "#a855f7",
    "v5_4":       "#ec4899",
    "v5_5":       "#f59e0b",
    "v5_6":       "#16a34a",
    "v5_7":       "#dc2626",
}


# ═════════════════════════════════════════════════════════════
# Data loading
# ═════════════════════════════════════════════════════════════

def load_engine(engine: str, date_str: str) -> dict | None:
    p = PAPER / engine / f"{date_str}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def all_closed_trades(d: dict) -> list[dict]:
    """Flatten all closed trades across pools, with pool name attached.

    Two shapes supported:
      v5 family : d['pools'][pool]['closed_trades' or 'closed']
      v4 flat   : d['closed_trades']  (single implicit pool 'MAIN')
    """
    out = []
    pools = d.get("pools") or {}
    if pools:
        for pname, pool in pools.items():
            # v5 stores under 'closed_trades' historically; v5_classic uses 'closed'
            trades = pool.get("closed_trades") or pool.get("closed") or []
            for t in trades:
                tt = dict(t)
                tt["_pool"] = pname
                out.append(tt)
    else:
        # v4 flat shape — top-level closed_trades, no pool concept
        for t in d.get("closed_trades") or []:
            tt = dict(t)
            tt["_pool"] = "MAIN"
            out.append(tt)
    return out


def all_positions(d: dict) -> list[dict]:
    """Flatten all positions across pools, with pool name attached.
    Same dual-shape support as all_closed_trades — see that docstring."""
    out = []
    pools = d.get("pools") or {}
    if pools:
        for pname, pool in pools.items():
            for p in pool.get("positions") or []:
                pp = dict(p)
                pp["_pool"] = pname
                out.append(pp)
    else:
        # v4 flat shape — open positions are entries with status == 'open'
        for p in d.get("positions") or []:
            if p.get("status") == "open":
                pp = dict(p)
                pp["_pool"] = "MAIN"
                out.append(pp)
    return out


def summarise(engine: str, d: dict | None) -> dict:
    if not d:
        return {"engine": engine, "status": "no_data"}
    s = d.get("summary", {}) or {}
    closed = all_closed_trades(d)
    open_p = all_positions(d)

    # 2026-05-07 fix: v4 has flat shape with no 'summary' block. Compute totals
    # directly from closed trades when summary is absent. Without this branch,
    # v4's row in the comparison report shows total_pnl=0, trades=0 every day,
    # even on days v4 leads (e.g., 2026-05-06: actual +Rs 196,789 / 243 trades
    # was reported as Rs 0 / 0 trades).
    if s:
        total_pnl = float(s.get("total_pnl", 0) or 0)
        trades = int(s.get("trades", 0) or 0)
        wins = int(s.get("wins", 0) or 0)
        losses = int(s.get("losses", 0) or 0)
        longs = int(s.get("longs", 0) or 0)
        shorts = int(s.get("shorts", 0) or 0)
    else:
        total_pnl = float(d.get("realized_pnl", 0) or 0)
        trades = len(closed)
        wins = sum(1 for t in closed if (t.get("pnl") or 0) > 0)
        losses = trades - wins
        # v4 is long-only; if a position_type field is absent, treat all as LONG
        longs = sum(1 for t in closed if t.get("position_type", "LONG") != "SHORT")
        shorts = trades - longs
    win_rate = round(100.0 * wins / trades, 1) if trades > 0 else 0.0

    # Per-closed-trade P&L (best-effort; engines use different keys)
    pnls = []
    for t in closed:
        pnl = t.get("pnl")
        if pnl is None:
            ep = t.get("entry_price")
            xp = t.get("exit_price")
            qty = t.get("qty", 0)
            if ep is not None and xp is not None:
                pnl = (float(xp) - float(ep)) * float(qty)
        if pnl is not None:
            pnls.append(float(pnl))

    best = max(pnls) if pnls else 0
    worst = min(pnls) if pnls else 0
    avg_win = (sum(p for p in pnls if p > 0) / max(1, sum(1 for p in pnls if p > 0))) if pnls else 0
    avg_loss = (sum(p for p in pnls if p < 0) / max(1, sum(1 for p in pnls if p < 0))) if pnls else 0

    exit_reasons = Counter(
        (t.get("exit_reason") or t.get("reason") or "UNKNOWN").upper()
        for t in closed
    )

    return {
        "engine": engine,
        "status": "ok",
        "regime": d.get("regime", "?"),
        "total_pnl": round(total_pnl, 2),
        "trades": trades,
        "wins": wins,
        "losses": losses,
        "longs": longs,
        "shorts": shorts,
        "win_rate": win_rate,
        "open_positions": len(open_p),
        "best_trade": round(best, 2),
        "worst_trade": round(worst, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "closed_trades": closed,
        "open_snapshot": open_p,
        "exit_reasons": dict(exit_reasons),
    }


def load_snapshots(date_str: str) -> list[dict]:
    p = WATCH / f"{date_str}_snapshots.jsonl"
    if not p.exists():
        return []
    out = []
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except Exception:
            pass
    return out


# ═════════════════════════════════════════════════════════════
# Charts
# ═════════════════════════════════════════════════════════════

def chart_pnl_timeline(snapshots: list[dict], out_path: Path) -> None:
    if not snapshots:
        return
    times = [s["time_hhmm"] for s in snapshots]
    fig, ax = plt.subplots(figsize=(10, 5), dpi=140)
    for eng in ENGINES:
        series = []
        for s in snapshots:
            hit = next((e for e in s["engines"] if e["engine"] == eng), None)
            if hit and hit.get("status") == "ok":
                series.append(hit.get("total_pnl", 0))
            else:
                series.append(None)
        if any(v is not None for v in series):
            ax.plot(times, series, label=eng, color=PALETTE.get(eng, "#333"),
                    marker="o", markersize=4, linewidth=1.8)
    ax.axhline(0, color="#555", linewidth=0.7, linestyle="--")
    ax.set_title("P&L Timeline — All Engines Through the Day", fontsize=13, fontweight="bold")
    ax.set_xlabel("Time")
    ax.set_ylabel("Net P&L (Rs)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8, ncol=3)
    plt.xticks(rotation=45, fontsize=8)
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def chart_scoreboard(summaries: list[dict], out_path: Path) -> None:
    ok = [s for s in summaries if s.get("status") == "ok"]
    ok = sorted(ok, key=lambda s: s["total_pnl"], reverse=True)
    names = [s["engine"] for s in ok]
    pnls = [s["total_pnl"] for s in ok]
    colors = ["#16a34a" if p >= 0 else "#dc2626" for p in pnls]

    fig, ax = plt.subplots(figsize=(10, 5), dpi=140)
    bars = ax.barh(names[::-1], pnls[::-1], color=colors[::-1], edgecolor="#111", linewidth=0.6)
    for bar, pnl in zip(bars, pnls[::-1]):
        ax.text(bar.get_width(), bar.get_y() + bar.get_height() / 2,
                f"  Rs {pnl:+,.0f}", va="center",
                fontsize=9, fontweight="bold",
                color="#111")
    ax.axvline(0, color="#222", linewidth=0.8)
    ax.set_title("EOD Scoreboard — Ranked by Net P&L", fontsize=13, fontweight="bold")
    ax.set_xlabel("Net P&L (Rs)")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def chart_exit_mix(summaries: list[dict], out_path: Path) -> None:
    ok = [s for s in summaries if s.get("status") == "ok" and s.get("trades", 0) > 0]
    if not ok:
        return
    all_reasons = sorted({r for s in ok for r in s["exit_reasons"].keys()})
    reason_colors = {
        "TARGET":      "#16a34a",
        "STOPLOSS":    "#dc2626",
        "SIGNAL_FLIP": "#f59e0b",
        "EOD":         "#2563eb",
        "TIMEOUT":     "#7c3aed",
        "UNKNOWN":     "#64748b",
    }

    names = [s["engine"] for s in ok]
    bottom = [0] * len(ok)
    fig, ax = plt.subplots(figsize=(10, 5), dpi=140)
    for r in all_reasons:
        vals = [s["exit_reasons"].get(r, 0) for s in ok]
        color = reason_colors.get(r, "#999")
        ax.bar(names, vals, bottom=bottom, label=r, color=color, edgecolor="#111", linewidth=0.5)
        bottom = [b + v for b, v in zip(bottom, vals)]
    ax.set_title("Exit Reason Mix per Engine", fontsize=13, fontweight="bold")
    ax.set_ylabel("Number of trades")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


def chart_winrate_vs_trades(summaries: list[dict], out_path: Path) -> None:
    ok = [s for s in summaries if s.get("status") == "ok" and s.get("trades", 0) > 0]
    if not ok:
        return
    fig, ax = plt.subplots(figsize=(9, 6), dpi=140)
    for s in ok:
        color = PALETTE.get(s["engine"], "#333")
        size = max(80, abs(s["total_pnl"]) / 30)
        ax.scatter(s["trades"], s["win_rate"], s=size, color=color,
                   alpha=0.75, edgecolor="#111", linewidth=1.2, label=s["engine"])
        ax.annotate(s["engine"], (s["trades"], s["win_rate"]),
                    xytext=(6, 6), textcoords="offset points", fontsize=9)
    ax.axhline(80, color="#16a34a", linestyle="--", linewidth=0.9, label="80% target")
    ax.set_title("Win Rate vs Trade Count (bubble size = |P&L|)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Trade count")
    ax.set_ylabel("Win rate (%)")
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 105)
    plt.tight_layout()
    fig.savefig(out_path, bbox_inches="tight")
    plt.close(fig)


# ═════════════════════════════════════════════════════════════
# Overlap matrix
# ═════════════════════════════════════════════════════════════

def build_overlap_matrix(summaries: list[dict]) -> dict:
    """
    For each pair of engines, count symbols that both held or closed today.
    Returns dict[(a, b)] -> set of symbols.
    """
    by_engine = {}
    for s in summaries:
        if s.get("status") != "ok":
            continue
        syms = {t.get("symbol") for t in s.get("closed_trades", []) if t.get("symbol")}
        syms |= {p.get("symbol") for p in s.get("open_snapshot", []) if p.get("symbol")}
        by_engine[s["engine"]] = syms
    out = {}
    names = list(by_engine.keys())
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            out[(a, b)] = by_engine[a] & by_engine[b]
    return out


# ═════════════════════════════════════════════════════════════
# Insights — the "what to tune tonight" engine
# ═════════════════════════════════════════════════════════════

def generate_insights(summaries: list[dict]) -> list[str]:
    ok = [s for s in summaries if s.get("status") == "ok"]
    if not ok:
        return ["No engine produced data today — nothing to analyse."]

    insights: list[str] = []
    by_pnl = sorted(ok, key=lambda s: s["total_pnl"], reverse=True)
    winner, loser = by_pnl[0], by_pnl[-1]

    insights.append(
        f"Winner: <b>{winner['engine']}</b> with Rs {winner['total_pnl']:+,.0f} "
        f"across {winner['trades']} trades ({winner['win_rate']}% win)."
    )
    if loser["engine"] != winner["engine"]:
        insights.append(
            f"Laggard: <b>{loser['engine']}</b> with Rs {loser['total_pnl']:+,.0f} "
            f"across {loser['trades']} trades ({loser['win_rate']}% win)."
        )

    # Volume vs profit — is more trading helping?
    high_vol = [s for s in ok if s["trades"] >= 50]
    low_vol = [s for s in ok if s["trades"] < 50 and s["trades"] > 0]
    if high_vol and low_vol:
        h_avg = sum(s["total_pnl"] for s in high_vol) / len(high_vol)
        l_avg = sum(s["total_pnl"] for s in low_vol) / len(low_vol)
        if h_avg > l_avg * 1.3:
            insights.append(
                f"High-volume engines (50+ trades) averaged Rs {h_avg:,.0f}; "
                f"low-volume averaged Rs {l_avg:,.0f}. <b>More trades = more profit today.</b>"
            )
        elif l_avg > h_avg * 1.3:
            insights.append(
                f"Low-volume engines outperformed — selectivity beat volume today "
                f"(low-vol avg Rs {l_avg:,.0f} vs high-vol Rs {h_avg:,.0f})."
            )

    # v5 vs v5.6 head-to-head (since v5 was the fix target)
    v5 = next((s for s in ok if s["engine"] == "v5"), None)
    v56 = next((s for s in ok if s["engine"] == "v5_6"), None)
    if v5 and v56:
        if v5["trades"] >= v56["trades"] * 0.8:
            insights.append(
                f"v5 trade-throttling fix <b>worked</b>: v5 did {v5['trades']} trades today vs "
                f"{v56['trades']} for v5.6 (yesterday v5 was stuck at 10)."
            )
        else:
            insights.append(
                f"v5 still under-trading: {v5['trades']} vs v5.6 {v56['trades']}. "
                f"Rust fix helped but another bottleneck remains."
            )
        pnl_gap = v56["total_pnl"] - v5["total_pnl"]
        if abs(pnl_gap) >= 1000:
            leader = "v5.6" if pnl_gap > 0 else "v5"
            insights.append(
                f"P&L gap: {leader} is ahead by Rs {abs(pnl_gap):,.0f}. "
                f"Investigate overlap matrix to see where they diverged."
            )

    # Exit-reason hints — engines that stop out too often need looser SL
    for s in ok:
        if s["trades"] < 10:
            continue
        sl = s["exit_reasons"].get("STOPLOSS", 0)
        tgt = s["exit_reasons"].get("TARGET", 0)
        if sl >= tgt and sl >= 5:
            insights.append(
                f"<b>{s['engine']}</b>: STOPLOSS ({sl}) >= TARGET ({tgt}). "
                f"Consider widening SL or tightening entry filters."
            )
        sig_flip = s["exit_reasons"].get("SIGNAL_FLIP", 0)
        if sig_flip >= (sl + tgt) and sig_flip >= 10:
            insights.append(
                f"<b>{s['engine']}</b>: dominated by SIGNAL_FLIP exits ({sig_flip}). "
                f"Entries are noisy — filter signals more aggressively."
            )

    # Win-rate vs target
    for s in ok:
        if s["trades"] < 10:
            continue
        if s["win_rate"] < 60:
            insights.append(
                f"<b>{s['engine']}</b>: {s['win_rate']}% win rate (target 80%). "
                f"Entry quality is the problem — tune ML score threshold up."
            )
        elif s["win_rate"] >= 85:
            insights.append(
                f"<b>{s['engine']}</b>: {s['win_rate']}% win rate — excellent. "
                f"Scale this engine up if P&L is positive."
            )

    return insights or ["No strong patterns yet."]


# ═════════════════════════════════════════════════════════════
# HTML render
# ═════════════════════════════════════════════════════════════

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8">
<title>TradePilot EOD Comparison — {date}</title>
<style>
@page {{ size: A4; margin: 18mm 14mm; }}
* {{ box-sizing: border-box; }}
body {{ font-family: Charter, Georgia, 'Times New Roman', serif; font-size: 11pt;
       color: #111; line-height: 1.55; margin: 0; padding: 0; background: #fff; }}
h1, h2, h3 {{ font-family: 'Avenir Next', Avenir, Helvetica, sans-serif;
              margin: 0.6em 0 0.3em; }}
h1 {{ font-size: 26pt; color: #1e1b4b; border-bottom: 3px solid #4f46e5; padding-bottom: 6px; }}
h2 {{ font-size: 16pt; color: #312e81; margin-top: 1.4em; }}
h3 {{ font-size: 13pt; color: #4338ca; }}
.cover {{ text-align: center; padding: 40px 0 20px; background: linear-gradient(180deg, #fff, #eef2ff); border-radius: 8px; margin-bottom: 22px; }}
.cover .badge {{ display: inline-block; background: #4f46e5; color: #fff; padding: 4px 14px; border-radius: 20px; font-size: 10pt; font-weight: 600; letter-spacing: 1px; }}
.cover h1 {{ border: none; margin-top: 14px; }}
.cover .subtitle {{ color: #475569; font-style: italic; margin-top: 4px; }}
table {{ width: 100%; border-collapse: collapse; margin: 0.8em 0; font-size: 10.5pt; }}
thead th {{ background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff;
           padding: 8px 10px; text-align: left; font-family: 'Avenir Next', sans-serif; }}
td {{ padding: 6px 10px; border-bottom: 1px solid #e5e7eb; }}
tr.row-win td {{ background: #f0fdf4; }}
tr.row-loss td {{ background: #fef2f2; }}
tr.row-lead td {{ background: #fff7ed; font-weight: 600; }}
.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
.green {{ color: #15803d; font-weight: 600; }}
.red {{ color: #b91c1c; font-weight: 600; }}
.muted {{ color: #64748b; }}
.insight {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 10px 14px;
            margin: 8px 0; border-radius: 4px; }}
.insight.warn {{ background: #fff7ed; border-left-color: #f59e0b; }}
.insight.good {{ background: #f0fdf4; border-left-color: #16a34a; }}
.chart {{ text-align: center; margin: 1em 0; }}
.chart img {{ max-width: 100%; border: 1px solid #e2e8f0; border-radius: 6px;
              box-shadow: 0 1px 4px rgba(0,0,0,0.06); }}
.small {{ font-size: 9pt; }}
.page-break {{ page-break-before: always; }}
.kpi-row {{ display: flex; gap: 10px; margin: 10px 0; }}
.kpi {{ flex: 1; padding: 14px; border-radius: 8px; text-align: center;
        background: #f8fafc; border: 1px solid #e2e8f0; }}
.kpi .label {{ font-size: 9pt; text-transform: uppercase; color: #64748b; letter-spacing: 1px; }}
.kpi .value {{ font-size: 20pt; font-weight: 700; margin-top: 4px; }}
.kpi.pos .value {{ color: #15803d; }}
.kpi.neg .value {{ color: #b91c1c; }}
.footer {{ text-align: center; color: #64748b; font-size: 9pt; margin-top: 2em;
           padding-top: 12px; border-top: 1px solid #e5e7eb; }}
</style></head>
<body>
<div class="cover">
  <span class="badge">TRADEPILOT · EOD REPORT</span>
  <h1>Engine Comparison — {date}</h1>
  <div class="subtitle">Side-by-side performance across {n_engines} engines · generated {gen_time}</div>
</div>

<div class="kpi-row">
  <div class="kpi {winner_cls}"><div class="label">Today's Winner</div>
    <div class="value">{winner_name}</div>
    <div class="small">Rs {winner_pnl:+,.0f} · {winner_trades} trades · {winner_wr}% wins</div>
  </div>
  <div class="kpi"><div class="label">Total Engines</div>
    <div class="value">{n_engines}</div>
    <div class="small">Profitable: {n_profit} · Negative: {n_neg}</div>
  </div>
  <div class="kpi"><div class="label">Best Single Trade</div>
    <div class="value">Rs {best_trade:+,.0f}</div>
    <div class="small">{best_engine} · {best_symbol}</div>
  </div>
</div>

<h2>1. Scoreboard</h2>
<table><thead><tr>
  <th>Rank</th><th>Engine</th><th class="num">Trades</th><th class="num">Win %</th>
  <th class="num">Avg Win</th><th class="num">Avg Loss</th><th class="num">Net P&L</th>
</tr></thead><tbody>
{scoreboard_rows}
</tbody></table>

<div class="chart"><img src="charts/scoreboard.png" alt="Scoreboard"></div>

<div class="page-break"></div>
<h2>2. P&L Timeline</h2>
<p class="muted">How each engine's profit evolved through the day (30-min snapshots).</p>
<div class="chart"><img src="charts/pnl_timeline.png" alt="PnL Timeline"></div>

<h2>3. Win Rate vs Trade Count</h2>
<p class="muted">Bubble size = absolute P&L. Top-right is the sweet spot.</p>
<div class="chart"><img src="charts/winrate_bubble.png" alt="Win Rate vs Trades"></div>

<div class="page-break"></div>
<h2>4. Exit Reason Mix</h2>
<p class="muted">What ended each trade — reveals whether stops, targets, or flips dominate.</p>
<div class="chart"><img src="charts/exit_mix.png" alt="Exit Mix"></div>

<h2>5. Trade Overlap Matrix</h2>
<p class="muted">Number of symbols both engines touched today. High overlap with very different P&L = you've found the part of the logic that matters.</p>
{overlap_table}

<div class="page-break"></div>
<h2>6. Tonight's Tune-ups (auto-surfaced)</h2>
<p class="muted">Patterns the watchdog surfaced from today's data. Treat as starting points, not conclusions.</p>
{insights_html}

<h2>7. Per-Engine Detail</h2>
{per_engine_html}

<div class="footer">TradePilot watchdog · report {date} · no commits made · uncommitted engine diffs preserved on main</div>
</body></html>
"""


def render_scoreboard_rows(summaries: list[dict]) -> str:
    ok = [s for s in summaries if s.get("status") == "ok"]
    ok = sorted(ok, key=lambda s: s["total_pnl"], reverse=True)
    rows = []
    for rank, s in enumerate(ok, 1):
        cls = "row-lead" if rank == 1 else ("row-win" if s["total_pnl"] > 0 else "row-loss")
        pnl_cls = "green" if s["total_pnl"] >= 0 else "red"
        rows.append(f"""<tr class="{cls}">
  <td>{rank}</td>
  <td><b>{s['engine']}</b></td>
  <td class="num">{s['trades']}</td>
  <td class="num">{s['win_rate']}%</td>
  <td class="num green">Rs {s['avg_win']:+,.0f}</td>
  <td class="num red">Rs {s['avg_loss']:+,.0f}</td>
  <td class="num {pnl_cls}">Rs {s['total_pnl']:+,.0f}</td>
</tr>""")
    # Missing engines
    missing = [s for s in summaries if s.get("status") != "ok"]
    for s in missing:
        rows.append(f'<tr><td>-</td><td>{s["engine"]}</td>'
                    f'<td colspan="5" class="muted">{s.get("status","?")}</td></tr>')
    return "\n".join(rows)


def render_overlap_table(overlap: dict, summaries: list[dict]) -> str:
    pnl = {s["engine"]: s.get("total_pnl", 0) for s in summaries if s.get("status") == "ok"}
    if not overlap:
        return "<p class='muted'>No overlap data.</p>"
    rows = []
    # Sort by descending overlap size
    for (a, b), syms in sorted(overlap.items(), key=lambda kv: -len(kv[1])):
        if not syms:
            continue
        gap = pnl.get(a, 0) - pnl.get(b, 0)
        sample = ", ".join(sorted(syms)[:6]) + ("..." if len(syms) > 6 else "")
        rows.append(f"<tr><td><b>{a}</b> vs <b>{b}</b></td>"
                    f"<td class='num'>{len(syms)}</td>"
                    f"<td class='num'>Rs {gap:+,.0f}</td>"
                    f"<td class='small muted'>{sample}</td></tr>")
    if not rows:
        return "<p class='muted'>No shared trades.</p>"
    return ("<table><thead><tr><th>Pair</th><th class='num'>Shared symbols</th>"
            "<th class='num'>P&L gap (a - b)</th><th>Sample</th></tr></thead><tbody>"
            + "\n".join(rows) + "</tbody></table>")


def render_insights_html(insights: list[str]) -> str:
    pieces = []
    for line in insights:
        cls = "insight"
        low = line.lower()
        if any(w in low for w in ["excellent", "worked", "winner", "scale"]):
            cls = "insight good"
        elif any(w in low for w in ["problem", "laggard", "under-trading", "noisy", "consider", "tune"]):
            cls = "insight warn"
        pieces.append(f'<div class="{cls}">{line}</div>')
    return "\n".join(pieces)


def render_per_engine_html(summaries: list[dict]) -> str:
    parts = []
    for s in summaries:
        if s.get("status") != "ok":
            continue
        pnls = []
        for t in s["closed_trades"]:
            pnl = t.get("pnl")
            if pnl is None:
                ep = t.get("entry_price"); xp = t.get("exit_price"); qty = t.get("qty", 0)
                if ep is not None and xp is not None:
                    pnl = (float(xp) - float(ep)) * float(qty)
            if pnl is not None:
                pnls.append((t.get("symbol", "?"), float(pnl),
                             t.get("exit_reason") or t.get("reason") or "?"))
        pnls.sort(key=lambda r: r[1], reverse=True)
        top_wins = pnls[:5]
        top_losses = sorted([p for p in pnls if p[1] < 0], key=lambda r: r[1])[:5]
        exit_mix = " · ".join(f"{k}:{v}" for k, v in sorted(s["exit_reasons"].items(),
                                                            key=lambda kv: -kv[1]))
        rows_w = "".join(
            f"<tr><td>{i+1}</td><td>{sym}</td><td class='num green'>Rs {p:+,.0f}</td>"
            f"<td class='small muted'>{r}</td></tr>"
            for i, (sym, p, r) in enumerate(top_wins)
        ) or "<tr><td colspan='4' class='muted'>no closed wins</td></tr>"
        rows_l = "".join(
            f"<tr><td>{i+1}</td><td>{sym}</td><td class='num red'>Rs {p:+,.0f}</td>"
            f"<td class='small muted'>{r}</td></tr>"
            for i, (sym, p, r) in enumerate(top_losses)
        ) or "<tr><td colspan='4' class='muted'>no closed losses</td></tr>"
        parts.append(f"""
<h3>{s['engine']} — Rs {s['total_pnl']:+,.0f} · {s['trades']} trades · {s['win_rate']}%</h3>
<p class="small muted">Regime: {s['regime']} · open positions at EOD: {s['open_positions']} · exits: {exit_mix}</p>
<table class="small"><thead><tr><th colspan="4">Top 5 winners</th></tr></thead>
<tbody>{rows_w}</tbody></table>
<table class="small"><thead><tr><th colspan="4">Top 5 losers</th></tr></thead>
<tbody>{rows_l}</tbody></table>
""")
    return "\n".join(parts) if parts else "<p class='muted'>No engine data.</p>"


# ═════════════════════════════════════════════════════════════
# Pyppeteer PDF
# ═════════════════════════════════════════════════════════════

async def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    from pyppeteer import launch
    chrome_path = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser = await launch(
        executablePath=chrome_path,
        headless=True,
        args=["--no-sandbox", "--disable-gpu"],
    )
    try:
        page = await browser.newPage()
        await page.goto(f"file://{html_path.resolve()}",
                        {"waitUntil": "networkidle0", "timeout": 60000})
        await asyncio.sleep(1.5)
        await page.pdf({
            "path": str(pdf_path),
            "printBackground": True,
            "preferCSSPageSize": True,
            "displayHeaderFooter": False,
            "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"},
        })
    finally:
        await browser.close()


# ═════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════

def main() -> int:
    date_str = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    out_dir = REPORTS / f"{date_str}_eod"
    charts_dir = out_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    print(f"[eod-report] date: {date_str}")
    print(f"[eod-report] output: {out_dir}")

    # Load everything
    summaries = [summarise(e, load_engine(e, date_str)) for e in ENGINES]
    snapshots = load_snapshots(date_str)

    # Charts
    chart_scoreboard(summaries, charts_dir / "scoreboard.png")
    chart_pnl_timeline(snapshots, charts_dir / "pnl_timeline.png")
    chart_exit_mix(summaries, charts_dir / "exit_mix.png")
    chart_winrate_vs_trades(summaries, charts_dir / "winrate_bubble.png")
    print(f"[eod-report] charts rendered: {len(list(charts_dir.glob('*.png')))}")

    # Overlap + insights
    overlap = build_overlap_matrix(summaries)
    insights = generate_insights(summaries)

    # Compute KPI headers
    ok = [s for s in summaries if s.get("status") == "ok"]
    ok_sorted = sorted(ok, key=lambda s: s["total_pnl"], reverse=True)
    winner = ok_sorted[0] if ok_sorted else {"engine": "n/a", "total_pnl": 0, "trades": 0, "win_rate": 0}
    n_profit = sum(1 for s in ok if s["total_pnl"] > 0)
    n_neg = sum(1 for s in ok if s["total_pnl"] <= 0)

    # Best single trade across all engines
    best_trade = 0; best_engine = "-"; best_symbol = "-"
    for s in ok:
        for t in s["closed_trades"]:
            pnl = t.get("pnl")
            if pnl is None:
                ep, xp, qty = t.get("entry_price"), t.get("exit_price"), t.get("qty", 0)
                if ep is not None and xp is not None:
                    pnl = (float(xp) - float(ep)) * float(qty)
            if pnl is not None and pnl > best_trade:
                best_trade = float(pnl)
                best_engine = s["engine"]
                best_symbol = t.get("symbol", "?")

    html = HTML_TEMPLATE.format(
        date=date_str,
        gen_time=datetime.now().strftime("%H:%M:%S"),
        n_engines=len(ok),
        n_profit=n_profit,
        n_neg=n_neg,
        winner_name=winner.get("engine", "n/a"),
        winner_pnl=winner.get("total_pnl", 0),
        winner_trades=winner.get("trades", 0),
        winner_wr=winner.get("win_rate", 0),
        winner_cls="pos" if winner.get("total_pnl", 0) >= 0 else "neg",
        best_trade=best_trade,
        best_engine=best_engine,
        best_symbol=best_symbol,
        scoreboard_rows=render_scoreboard_rows(summaries),
        overlap_table=render_overlap_table(overlap, summaries),
        insights_html=render_insights_html(insights),
        per_engine_html=render_per_engine_html(summaries),
    )

    html_path = out_dir / "report.html"
    html_path.write_text(html)
    print(f"[eod-report] HTML: {html_path}")

    # Save raw data for diffing across days
    data_path = out_dir / "data.json"
    # Strip big fields from JSON dump
    trimmed = []
    for s in summaries:
        if s.get("status") != "ok":
            trimmed.append(s); continue
        t = {k: v for k, v in s.items() if k not in ("closed_trades", "open_snapshot")}
        t["n_closed"] = len(s["closed_trades"])
        t["n_open"] = len(s["open_snapshot"])
        trimmed.append(t)
    data_path.write_text(json.dumps({
        "date": date_str,
        "generated_at": datetime.now().isoformat(),
        "summaries": trimmed,
        "overlap": {f"{a}|{b}": sorted(syms) for (a, b), syms in overlap.items() if syms},
        "insights": insights,
    }, indent=2))
    print(f"[eod-report] data.json: {data_path}")

    # PDF via Pyppeteer
    pdf_path = out_dir / "report.pdf"
    try:
        asyncio.run(html_to_pdf(html_path, pdf_path))
        print(f"[eod-report] PDF: {pdf_path}")
    except Exception as e:
        print(f"[eod-report] PDF render failed: {e}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
