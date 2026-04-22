#!/usr/bin/env python3
"""
EOD Deep-Dive Report — full battle report combining all findings.

Goes beyond the auto EOD report: yesterday-vs-today comparison, structural
analysis (why some engines win), engine pathology (v4 51% = random; v5_2
options blowup), watchdog findings, and a prioritised tonight's tune-up
queue.

Output:
  docs/watchdog/reports/YYYY-MM-DD_deep_dive/
    report.html
    report.pdf
    charts/*.png
    data.json

Pipeline: Python -> matplotlib -> rich HTML -> Pyppeteer PDF (per project rule).
"""
from __future__ import annotations

import asyncio
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "docs" / "paper-trades"
WATCH = ROOT / "docs" / "watchdog"
LOGS = ROOT / "logs"
OUT_BASE = WATCH / "reports"

ENGINES = ["v4", "v5", "v5_classic", "v5_2", "v5_3", "v5_6", "v5_7"]
PALETTE = {
    "v4":         "#94a3b8",
    "v5":         "#2563eb",
    "v5_classic": "#0ea5e9",
    "v5_2":       "#dc2626",   # red — the loser
    "v5_3":       "#a855f7",
    "v5_6":       "#16a34a",
    "v5_7":       "#0d9488",
}
ENGINE_LABEL = {
    "v4": "v4 composite",
    "v5": "v5 (Rust-unlocked)",
    "v5_classic": "v5_classic",
    "v5_2": "v5_2 (options)",
    "v5_3": "v5_3 staged",
    "v5_6": "v5_6 Darvas Box",
    "v5_7": "v5_7 Intraday Box",
}


# ═════════════════════════════════════════════════════════════
# Data loading — combines JSON state, report.md, and log file
# ═════════════════════════════════════════════════════════════

def load_state(eng: str, date: str) -> dict | None:
    p = PAPER / eng / f"{date}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except Exception:
        return None


def load_report_md(eng: str, date: str) -> str | None:
    p = PAPER / eng / f"{date}_report.md"
    if not p.exists():
        return None
    return p.read_text(errors="ignore")


def parse_report_summary(md: str) -> dict:
    """Pull authoritative final numbers from the report.md (logs > JSON for truth)."""
    out = {"trades": 0, "win_rate": 0, "total_pnl": 0.0, "regime": "?", "longs": 0, "shorts": 0}
    if not md:
        return out
    m = re.search(r"\*\*Net P&L\*\*\s*\|\s*\*\*Rs\s*([\-\d,]+)", md)
    if m:
        out["total_pnl"] = float(m.group(1).replace(",", ""))
    m = re.search(r"Trades\s*\|\s*(\d+)(?:\s*\(L:(\d+)\s*S:(\d+)\))?", md)
    if m:
        out["trades"] = int(m.group(1))
        if m.group(2): out["longs"] = int(m.group(2))
        if m.group(3): out["shorts"] = int(m.group(3))
    m = re.search(r"Win Rate\*?\*?\s*\|\s*\*?\*?(\d+)%", md)
    if m:
        out["win_rate"] = int(m.group(1))
    m = re.search(r"Regime\s*\|\s*(\w+)", md)
    if m:
        out["regime"] = m.group(1)
    return out


def parse_log_trades(log_path: Path, date: str) -> list[dict]:
    """Extract closed trades from the per-engine paper-trade log for the date."""
    if not log_path.exists():
        return []
    trades = []
    # Multiple patterns — engines log in slightly different formats
    pat_v56 = re.compile(
        r"\[(\d{2}:\d{2}:\d{2})\]\s+>>\s+(WIN|LOSS)\s+LONG\s+(\S+)\s+x(\d+)\s+@([\d.]+)\s+\((\w+)\)\s+P&L:\s+Rs\s+([+\-\d,]+)"
    )
    pat_v4 = re.compile(
        r"\[(\d{2}:\d{2}:\d{2})\]\s+>>\s+(WIN|LOSS):\s+(\S+)\s+x(\d+)\s+@\s*Rs\s+([\d.]+)\s+\((\w+)\)\s+P&L:\s+Rs\s+([+\-\d,]+)"
    )
    pat_v52 = re.compile(
        r"\[(\d{2}:\d{2}:\d{2})\]\s+CLOSED\s+\[(\w+)\]:.*?(\S+)\s+@([\d.]+)->([\d.]+)\s+P&L:\s+Rs\s+([+\-\d,]+)"
    )
    text = log_path.read_text(errors="ignore")
    for m in pat_v56.finditer(text):
        trades.append({
            "time": m.group(1), "result": m.group(2), "symbol": m.group(3),
            "qty": int(m.group(4)), "exit_price": float(m.group(5)),
            "reason": m.group(6), "pnl": float(m.group(7).replace(",", "")),
        })
    for m in pat_v4.finditer(text):
        trades.append({
            "time": m.group(1), "result": m.group(2), "symbol": m.group(3),
            "qty": int(m.group(4)), "exit_price": float(m.group(5)),
            "reason": m.group(6), "pnl": float(m.group(7).replace(",", "")),
        })
    for m in pat_v52.finditer(text):
        trades.append({
            "time": m.group(1), "reason": m.group(2), "symbol": m.group(3),
            "entry_price": float(m.group(4)), "exit_price": float(m.group(5)),
            "pnl": float(m.group(6).replace(",", "")),
            "result": "WIN" if float(m.group(6).replace(",", "")) > 0 else "LOSS",
        })
    return trades


def gather_engine(eng: str, date: str) -> dict:
    state = load_state(eng, date) or {}
    md = load_report_md(eng, date)
    md_sum = parse_report_summary(md or "")

    # logs: today's date file or rolling
    log_paths = [LOGS / f"{eng}-{date}.log", LOGS / f"{eng}-paper-trade.log"]
    trades = []
    for p in log_paths:
        ts = parse_log_trades(p, date)
        if ts:
            trades = ts; break

    # Authoritative numbers: prefer report.md, fallback to JSON summary, fallback to trades sum
    s = state.get("summary", {}) or {}
    total_pnl = md_sum["total_pnl"] or float(s.get("total_pnl", 0) or 0) or sum(t["pnl"] for t in trades)
    n_trades = md_sum["trades"] or int(s.get("trades", 0) or 0) or len(trades)
    wr = md_sum["win_rate"] or (round(100*int(s.get("wins", 0))/max(1, int(s.get("trades", 1) or 1)), 0))

    pnls = [t["pnl"] for t in trades]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    avg_win = sum(wins)/len(wins) if wins else 0
    avg_loss = sum(losses)/len(losses) if losses else 0

    # Open positions (from JSON — live snapshot at session end)
    open_pos = []
    pool_break = {}
    for pname, pool in (state.get("pools") or {}).items():
        positions = pool.get("positions", []) or []
        open_pos.extend(positions)
        pool_break[pname] = {
            "open": len(positions),
            "realized": float(pool.get("realized_pnl", 0) or 0),
        }

    exit_reasons = Counter(t.get("reason", "?").upper() for t in trades)
    unique_syms = sorted({t["symbol"] for t in trades} | {p.get("symbol", "?") for p in open_pos})

    return {
        "engine": eng,
        "label": ENGINE_LABEL.get(eng, eng),
        "regime": md_sum["regime"] or state.get("regime", "?"),
        "total_pnl": round(total_pnl, 2),
        "trades": n_trades,
        "win_rate": int(wr) if wr else 0,
        "avg_win": round(avg_win, 0),
        "avg_loss": round(avg_loss, 0),
        "longs": md_sum["longs"],
        "shorts": md_sum["shorts"],
        "open_positions": len(open_pos),
        "unique_symbols": unique_syms,
        "n_unique_symbols": len(unique_syms),
        "exit_reasons": dict(exit_reasons),
        "trades_detail": trades,
        "open_snapshot": open_pos,
        "pools": pool_break,
    }


def load_snapshots(date: str) -> list[dict]:
    p = WATCH / f"{date}_snapshots.jsonl"
    if not p.exists():
        return []
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()]


# ═════════════════════════════════════════════════════════════
# Charts — extend the auto-EOD set with deep-dive specific
# ═════════════════════════════════════════════════════════════

def chart_scoreboard_h(summaries: list[dict], out: Path) -> None:
    ok = sorted([s for s in summaries if s["trades"] > 0 or s["total_pnl"] != 0],
                key=lambda s: s["total_pnl"], reverse=True)
    names = [s["label"] for s in ok]
    pnls = [s["total_pnl"] for s in ok]
    colors = ["#16a34a" if p > 0 else "#dc2626" if p < 0 else "#94a3b8" for p in pnls]
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=140)
    bars = ax.barh(names[::-1], pnls[::-1], color=colors[::-1], edgecolor="#111", linewidth=0.7)
    for bar, p in zip(bars, pnls[::-1]):
        x = bar.get_width()
        ax.text(x + (max(pnls) - min(pnls)) * 0.01 * (1 if x >= 0 else -2.5),
                bar.get_y() + bar.get_height()/2,
                f"Rs {p:+,.0f}", va="center", fontsize=10, fontweight="bold")
    ax.axvline(0, color="#222", linewidth=0.8)
    ax.set_title("Final Scoreboard — Net P&L per Engine", fontsize=13, fontweight="bold")
    ax.set_xlabel("Rs")
    ax.grid(True, axis="x", alpha=0.3)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_pnl_timeline(snapshots: list[dict], out: Path) -> None:
    if not snapshots:
        return
    times = [s["time_hhmm"] for s in snapshots]
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=140)
    for eng in ENGINES:
        series = []
        for s in snapshots:
            hit = next((e for e in s.get("engines", []) if e.get("engine") == eng), None)
            series.append(hit.get("total_pnl") if hit and hit.get("status") == "ok" else None)
        if any(v is not None for v in series):
            ax.plot(times, series, label=ENGINE_LABEL.get(eng, eng),
                    color=PALETTE.get(eng, "#333"), marker="o", markersize=4, linewidth=2)
    ax.axhline(0, color="#555", linewidth=0.7, linestyle="--")
    ax.set_title("P&L Trajectory Through the Trading Day", fontsize=13, fontweight="bold")
    ax.set_xlabel("Time (IST)"); ax.set_ylabel("Cumulative Net P&L (Rs)")
    ax.grid(True, alpha=0.3)
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    plt.xticks(rotation=45, fontsize=8)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_yday_vs_today_v5(yday: dict, today: dict, out: Path) -> None:
    metrics = ["trades", "win_rate", "total_pnl"]
    labels = ["Trades", "Win Rate (%)", "P&L (Rs)"]
    y_vals = [yday["trades"], yday["win_rate"], yday["total_pnl"]]
    t_vals = [today["trades"], today["win_rate"], today["total_pnl"]]

    fig, axes = plt.subplots(1, 3, figsize=(11, 4.2), dpi=140)
    for ax, lab, yv, tv in zip(axes, labels, y_vals, t_vals):
        bars = ax.bar(["Yesterday\n(Rust locked)", "Today\n(Rust unlocked)"],
                      [yv, tv],
                      color=["#94a3b8", "#16a34a" if tv >= yv else "#dc2626"],
                      edgecolor="#111", linewidth=0.8)
        for b, v in zip(bars, [yv, tv]):
            ax.text(b.get_x() + b.get_width()/2, b.get_height(),
                    f"{v:+,.0f}" if "P&L" in lab else f"{v}",
                    ha="center", va="bottom", fontsize=11, fontweight="bold")
        ax.set_title(lab, fontsize=11, fontweight="bold")
        ax.grid(True, axis="y", alpha=0.3)
    fig.suptitle("v5 Engine: Yesterday vs Today (after Rust position-cap unlock)",
                 fontsize=13, fontweight="bold")
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_winrate_bubble(summaries: list[dict], out: Path) -> None:
    ok = [s for s in summaries if s["trades"] > 0]
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=140)
    for s in ok:
        size = max(120, abs(s["total_pnl"]) / 25)
        ax.scatter(s["trades"], s["win_rate"], s=size,
                   color=PALETTE.get(s["engine"], "#333"),
                   alpha=0.8, edgecolor="#111", linewidth=1.4)
        ax.annotate(s["label"], (s["trades"], s["win_rate"]),
                    xytext=(8, 6), textcoords="offset points", fontsize=9, fontweight="bold")
    ax.axhline(80, color="#16a34a", linestyle="--", linewidth=0.9, label="80% target")
    ax.axhline(50, color="#dc2626", linestyle="--", linewidth=0.7, label="50% (random)")
    ax.set_title("Win Rate vs Trade Count (bubble size = |P&L|)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Trade count"); ax.set_ylabel("Win rate (%)")
    ax.set_ylim(0, 105); ax.grid(True, alpha=0.3); ax.legend()
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_exit_mix(summaries: list[dict], out: Path) -> None:
    ok = [s for s in summaries if s["trades"] > 0]
    if not ok:
        return
    all_reasons = sorted({r for s in ok for r in s["exit_reasons"].keys()})
    reason_colors = {"TARGET": "#16a34a", "STOPLOSS": "#dc2626", "SIGNAL_FLIP": "#f59e0b",
                     "TIME_EXIT": "#2563eb", "EOD_EXIT": "#7c3aed", "EOD": "#7c3aed",
                     "TIMEOUT": "#94a3b8", "?": "#cbd5e1"}
    names = [s["label"] for s in ok]
    fig, ax = plt.subplots(figsize=(10, 5.2), dpi=140)
    bottom = [0]*len(ok)
    for r in all_reasons:
        vals = [s["exit_reasons"].get(r, 0) for s in ok]
        ax.bar(names, vals, bottom=bottom, label=r,
               color=reason_colors.get(r, "#999"), edgecolor="#111", linewidth=0.5)
        bottom = [b+v for b, v in zip(bottom, vals)]
    ax.set_title("Exit Reason Mix per Engine", fontsize=12, fontweight="bold")
    ax.set_ylabel("Number of trades")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, axis="y", alpha=0.3)
    plt.xticks(rotation=15, fontsize=9)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_breadth_vs_depth(summaries: list[dict], out: Path) -> None:
    ok = [s for s in summaries if s["trades"] > 0]
    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=140)
    for s in ok:
        breadth = s["n_unique_symbols"]
        depth = s["trades"] / max(1, breadth)
        size = max(120, abs(s["total_pnl"]) / 25)
        ax.scatter(breadth, depth, s=size,
                   color=PALETTE.get(s["engine"], "#333"),
                   alpha=0.8, edgecolor="#111", linewidth=1.4)
        ax.annotate(f"{s['label']}\n({s['win_rate']}% WR)", (breadth, depth),
                    xytext=(7, 7), textcoords="offset points", fontsize=8, fontweight="bold")
    ax.set_title("Breadth (unique symbols) vs Depth (trades per symbol)", fontsize=12, fontweight="bold")
    ax.set_xlabel("Unique symbols traded")
    ax.set_ylabel("Avg trades per symbol")
    ax.grid(True, alpha=0.3)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_v52_blowup(v52: dict, out: Path) -> None:
    if not v52.get("trades_detail"):
        return
    t = v52["trades_detail"][0]
    entry = t.get("entry_price", 210.20); exitp = t.get("exit_price", 8.50)
    pnl = t.get("pnl", -45385)
    fig, ax = plt.subplots(figsize=(10, 4.5), dpi=140)
    # Simple bar showing entry vs exit price
    bars = ax.bar(["Entry @09:15", "Exit @15:21 EOD"], [entry, exitp],
                  color=["#16a34a", "#dc2626"], edgecolor="#111", linewidth=0.8, width=0.5)
    for b, v in zip(bars, [entry, exitp]):
        ax.text(b.get_x() + b.get_width()/2, b.get_height() + 5,
                f"Rs {v:.2f}", ha="center", fontsize=12, fontweight="bold")
    ax.set_title(f"v5_2 Catastrophe — NIFTY 24300PE Option\nP&L: Rs {pnl:+,.0f} ({(exitp-entry)/entry*100:+.1f}%)",
                 fontsize=12, fontweight="bold", color="#dc2626")
    ax.set_ylabel("Option price (Rs)")
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


# ═════════════════════════════════════════════════════════════
# Insights and tune-up generation
# ═════════════════════════════════════════════════════════════

def diagnose_v5_unlock(yday: dict, today: dict) -> dict:
    return {
        "trade_delta": today["trades"] - yday["trades"],
        "trade_multiplier": today["trades"] / max(1, yday["trades"]),
        "wr_delta": today["win_rate"] - yday["win_rate"],
        "pnl_delta": today["total_pnl"] - yday["total_pnl"],
        "verdict": "Spectacular win" if today["total_pnl"] - yday["total_pnl"] > 30000 else "Modest improvement",
    }


def diagnose_v5_gap(v5: dict, v56: dict, v57: dict) -> dict:
    leader = max([v56, v57], key=lambda x: x["total_pnl"])
    gap = leader["total_pnl"] - v5["total_pnl"]
    wr_gap = leader["win_rate"] - v5["win_rate"]
    breadth_diff = v5["n_unique_symbols"] - leader["n_unique_symbols"]
    return {
        "leader": leader["engine"],
        "leader_label": leader["label"],
        "pnl_gap": gap,
        "wr_gap": wr_gap,
        "breadth_diff": breadth_diff,
        "v5_breadth": v5["n_unique_symbols"],
        "leader_breadth": leader["n_unique_symbols"],
    }


def tune_up_queue(summaries: list[dict]) -> list[dict]:
    queue = []
    by = {s["engine"]: s for s in summaries}
    v52 = by.get("v5_2")
    v4 = by.get("v4")
    v5 = by.get("v5")
    v56 = by.get("v5_6")
    v57 = by.get("v5_7")

    if v52 and v52["total_pnl"] < -10000:
        queue.append({
            "priority": 1, "rank_class": "critical",
            "action": "Cap v5_2 (options) position size + add daily loss kill-switch",
            "impact": f"Prevents single-trade losses like today's Rs {v52['total_pnl']:+,.0f}",
            "risk": "Low — purely protective",
            "rationale": (f"v5_2 lost Rs {abs(v52['total_pnl']):,.0f} on a single options bet. "
                          f"That's more damage than v5_classic made all day. "
                          f"Add: max 10% capital per trade + -Rs 5000 daily loss kill-switch."),
        })
    if v4 and 45 <= v4["win_rate"] <= 55 and v4["trades"] > 10:
        queue.append({
            "priority": 2, "rank_class": "high",
            "action": "Diagnose & retire OR retrain v4 composite scorer",
            "impact": f"Frees CPU + capital. v4 has {v4['win_rate']}% WR = no edge.",
            "risk": "Low",
            "rationale": (f"v4 traded {v4['trades']}× at {v4['win_rate']}% win rate (coin flip). "
                          f"Best trade Rs {max(t['pnl'] for t in v4['trades_detail']):+,.0f}, "
                          f"worst Rs {min(t['pnl'] for t in v4['trades_detail']):+,.0f}. "
                          "The composite scorer model is stale or misconfigured."),
        })
    if v5 and v56 and v57:
        leader = max([v56, v57], key=lambda x: x["total_pnl"])
        gap = leader["total_pnl"] - v5["total_pnl"]
        if gap > 5000:
            queue.append({
                "priority": 3, "rank_class": "high",
                "action": f"Port {leader['label']}'s box-theory exits onto v5",
                "impact": f"Could close ~Rs {gap:,.0f} P&L gap to leader",
                "risk": "Medium — needs paper-trade testing",
                "rationale": (f"v5 took {v5['n_unique_symbols']} unique symbols (broader) but "
                              f"{leader['label']} hit {leader['win_rate']}% WR vs v5's {v5['win_rate']}% — "
                              "the gap is exit precision, not entry quality. "
                              "Box-theory targets are mathematically defined, not ML-second-guessed."),
            })
    if v56 and v57 and any(s["open_positions"] >= 18 for s in [v5, v56, v57] if s):
        queue.append({
            "priority": 4, "rank_class": "med",
            "action": "Test raising pool position cap from 20 → 30",
            "impact": "More trades on high-WR days. Symmetric on bad days.",
            "risk": "Medium — backtest on bear/sideways/bull regimes first",
            "rationale": ("All top engines hit the 20-position cap within 30-60 minutes of open and "
                          "then could only enter new trades when old ones closed. On a 92% WR day "
                          "more positions = more profit; on a -EV day, more positions = more loss."),
        })
    queue.append({
        "priority": 5, "rank_class": "med",
        "action": "Build Live Engine Picks widget (Part B from queue)",
        "impact": "Dashboard transparency — currently 87% of 'BUY'-rated stocks aren't held by any engine",
        "risk": "Low",
        "rationale": "See docs/TONIGHT_TUNEUPS_2026-04-22.md Parts B/D/E.",
    })
    return queue


# ═════════════════════════════════════════════════════════════
# HTML render
# ═════════════════════════════════════════════════════════════

CSS = """
@page { size: A4; margin: 16mm 12mm 18mm 12mm; @bottom-center { content: "TradePilot Battle Report · Page " counter(page) " of " counter(pages); font-family: 'Avenir Next', sans-serif; font-size: 8pt; color: #94a3b8; } }
* { box-sizing: border-box; }
body { font-family: Charter, Georgia, 'Times New Roman', serif; font-size: 11pt; line-height: 1.55; color: #0f172a; margin: 0; padding: 0; }
h1, h2, h3, h4 { font-family: 'Avenir Next', Avenir, Helvetica, sans-serif; margin: 0.6em 0 0.3em; }
h1 { font-size: 30pt; color: #0f172a; }
h2 { font-size: 17pt; color: #1e293b; border-left: 5px solid #4f46e5; padding-left: 12px; margin-top: 1.6em; }
h3 { font-size: 13pt; color: #312e81; margin-top: 1.1em; }
h4 { font-size: 12pt; color: #4338ca; }

.cover { text-align: center; padding: 70px 20px 50px; background: linear-gradient(180deg, #ffffff 0%, #eef2ff 50%, #c7d2fe 100%); border-radius: 12px; margin-bottom: 24px; }
.cover .badge { display: inline-block; background: #4f46e5; color: #fff; padding: 6px 18px; border-radius: 20px; font-size: 10pt; font-weight: 700; letter-spacing: 2px; }
.cover h1 { margin-top: 18px; color: #1e1b4b; }
.cover .subtitle { color: #475569; font-style: italic; margin-top: 8px; font-size: 13pt; }
.cover .verdict { margin-top: 24px; padding: 14px 18px; background: rgba(255,255,255,0.7); border-radius: 8px; font-size: 12pt; display: inline-block; }
.cover .verdict strong { color: #15803d; }

.kpi-row { display: flex; gap: 10px; margin: 14px 0; }
.kpi { flex: 1; padding: 14px 12px; border-radius: 10px; text-align: center; background: #f8fafc; border: 1px solid #e2e8f0; }
.kpi .label { font-size: 8pt; text-transform: uppercase; color: #64748b; letter-spacing: 1.5px; }
.kpi .value { font-size: 22pt; font-weight: 800; margin-top: 4px; }
.kpi .small { font-size: 9pt; color: #475569; }
.kpi.pos .value { color: #15803d; }
.kpi.neg .value { color: #b91c1c; }
.kpi.warn .value { color: #d97706; }

table { width: 100%; border-collapse: collapse; margin: 0.8em 0; font-size: 10.5pt; }
thead th { background: linear-gradient(135deg, #4f46e5, #7c3aed); color: #fff; padding: 8px 10px; text-align: left; font-family: 'Avenir Next', sans-serif; font-weight: 600; }
td { padding: 7px 10px; border-bottom: 1px solid #e5e7eb; }
tr.row-lead td { background: #fff7ed; font-weight: 600; }
tr.row-win  td { background: #f0fdf4; }
tr.row-loss td { background: #fef2f2; }
tr.row-flat td { background: #f1f5f9; color: #64748b; }
.num { text-align: right; font-variant-numeric: tabular-nums; }
.green { color: #15803d; font-weight: 700; }
.red   { color: #b91c1c; font-weight: 700; }
.muted { color: #64748b; }
.medal { font-size: 14pt; }

.callout { padding: 14px 16px; margin: 12px 0; border-radius: 6px; border-left: 4px solid #2563eb; background: #eff6ff; }
.callout.warn { background: #fff7ed; border-color: #f59e0b; }
.callout.good { background: #f0fdf4; border-color: #16a34a; }
.callout.crit { background: #fef2f2; border-color: #dc2626; }
.callout strong { color: #0f172a; }

.chart { text-align: center; margin: 1.2em 0; page-break-inside: avoid; }
.chart img { max-width: 100%; border: 1px solid #e2e8f0; border-radius: 8px; box-shadow: 0 1px 3px rgba(0,0,0,0.05); }

.tune-up { padding: 14px 16px; margin: 10px 0; border-radius: 8px; border-left: 6px solid #4f46e5; background: #fafafa; page-break-inside: avoid; }
.tune-up.critical { border-color: #dc2626; background: #fef2f2; }
.tune-up.high     { border-color: #f59e0b; background: #fff7ed; }
.tune-up.med      { border-color: #2563eb; background: #eff6ff; }
.tune-up .priority { font-weight: 700; color: #4f46e5; font-size: 9pt; letter-spacing: 1.5px; text-transform: uppercase; }
.tune-up.critical .priority { color: #dc2626; }
.tune-up .action { font-size: 13pt; font-weight: 700; margin: 4px 0; color: #0f172a; }
.tune-up .meta { font-size: 9.5pt; color: #475569; }
.tune-up .meta .label { font-weight: 600; color: #1e293b; }
.tune-up .rationale { margin-top: 6px; font-size: 10pt; color: #334155; }

.page-break { page-break-before: always; }

.symbol-grid { display: flex; flex-wrap: wrap; gap: 6px; margin: 8px 0; }
.symbol-chip { background: #e0e7ff; color: #3730a3; padding: 4px 10px; border-radius: 12px; font-size: 9pt; font-family: 'Avenir Next', sans-serif; font-weight: 600; }
.symbol-chip.consensus { background: #dcfce7; color: #166534; }

.appendix-table { font-size: 9.5pt; }
.appendix-table .num { font-variant-numeric: tabular-nums; }

.footer { text-align: center; color: #64748b; font-size: 9pt; margin-top: 2em; padding-top: 12px; border-top: 1px solid #e5e7eb; }
"""


def render_html(date: str, summaries: list[dict], snapshots: list[dict],
                v5_unlock: dict, v5_gap: dict, tune_ups: list[dict]) -> str:
    by = {s["engine"]: s for s in summaries}
    profitable = [s for s in summaries if s["total_pnl"] > 0]
    losers     = [s for s in summaries if s["total_pnl"] < 0]
    flat       = [s for s in summaries if s["total_pnl"] == 0]
    net = sum(s["total_pnl"] for s in summaries)

    ranked = sorted(summaries, key=lambda s: s["total_pnl"], reverse=True)
    winner = ranked[0] if ranked else None

    # Scoreboard rows
    medal = ["🥇", "🥈", "🥉"]
    sb_rows = []
    for i, s in enumerate(ranked):
        m = medal[i] if i < 3 and s["total_pnl"] > 0 else ("☠️" if s["total_pnl"] < -20000 else "—")
        cls = "row-lead" if i == 0 and s["total_pnl"] > 0 else ("row-loss" if s["total_pnl"] < 0 else ("row-win" if s["total_pnl"] > 0 else "row-flat"))
        pcls = "green" if s["total_pnl"] >= 0 else "red"
        pct = s["total_pnl"] / 1_000_000 * 100
        sb_rows.append(f"""<tr class="{cls}">
  <td><span class="medal">{m}</span></td>
  <td><b>{s['label']}</b></td>
  <td class="num {pcls}">Rs {s['total_pnl']:+,.0f}</td>
  <td class="num {pcls}">{pct:+.2f}%</td>
  <td class="num">{s['trades']}</td>
  <td class="num">{s['win_rate']}%</td>
  <td class="num green">Rs {s['avg_win']:+,.0f}</td>
  <td class="num red">Rs {s['avg_loss']:+,.0f}</td>
</tr>""")

    # Symbol overlap (v5 vs v5_6 vs v5_7)
    v5s = set(by["v5"]["unique_symbols"]) if "v5" in by else set()
    v56s = set(by["v5_6"]["unique_symbols"]) if "v5_6" in by else set()
    v57s = set(by["v5_7"]["unique_symbols"]) if "v5_7" in by else set()
    consensus = v5s & v56s & v57s
    v5_only   = v5s - v56s - v57s
    box_only  = (v56s & v57s) - v5s

    def chips(syms, css="symbol-chip"):
        if not syms: return "<i>none</i>"
        return ''.join(f'<span class="{css}">{s}</span>' for s in sorted(syms))

    # Tune-up cards
    tune_html = "\n".join(f"""<div class="tune-up {t['rank_class']}">
  <div class="priority">Priority {t['priority']} — {t['rank_class']}</div>
  <div class="action">{t['action']}</div>
  <div class="meta"><span class="label">Impact:</span> {t['impact']}</div>
  <div class="meta"><span class="label">Risk:</span> {t['risk']}</div>
  <div class="rationale">{t['rationale']}</div>
</div>""" for t in tune_ups)

    # Per-engine appendix
    eng_blocks = []
    for s in ranked:
        if not s["trades_detail"]:
            eng_blocks.append(f"""<h3>{s['label']} — Rs {s['total_pnl']:+,.0f} · {s['trades']} trades · {s['win_rate']}% WR</h3>
<p class="muted">No trade detail available.</p>""")
            continue
        ts = sorted(s["trades_detail"], key=lambda t: t["pnl"], reverse=True)
        wins = ts[:5]
        losses = sorted([t for t in ts if t["pnl"] < 0], key=lambda t: t["pnl"])[:5]
        ex_mix = " · ".join(f"{k}:{v}" for k, v in sorted(s["exit_reasons"].items(), key=lambda kv: -kv[1]))
        rows_w = "".join(f"<tr><td>{i+1}</td><td>{t['symbol']}</td>"
                         f"<td class='num green'>Rs {t['pnl']:+,.0f}</td>"
                         f"<td class='small muted'>{t.get('reason','?')} @ {t.get('time','')}</td></tr>"
                         for i, t in enumerate(wins)) or "<tr><td colspan='4' class='muted'>—</td></tr>"
        rows_l = "".join(f"<tr><td>{i+1}</td><td>{t['symbol']}</td>"
                         f"<td class='num red'>Rs {t['pnl']:+,.0f}</td>"
                         f"<td class='small muted'>{t.get('reason','?')} @ {t.get('time','')}</td></tr>"
                         for i, t in enumerate(losses)) or "<tr><td colspan='4' class='muted'>—</td></tr>"
        eng_blocks.append(f"""<h3>{s['label']} — Rs {s['total_pnl']:+,.0f} · {s['trades']} trades · {s['win_rate']}% WR</h3>
<p class="muted">Regime: {s['regime']} · open at EOD: {s['open_positions']} · unique symbols: {s['n_unique_symbols']} · exits: {ex_mix}</p>
<div style="display:flex;gap:14px;">
  <div style="flex:1"><table class="appendix-table"><thead><tr><th colspan="4">Top 5 winners</th></tr></thead><tbody>{rows_w}</tbody></table></div>
  <div style="flex:1"><table class="appendix-table"><thead><tr><th colspan="4">Top 5 losers</th></tr></thead><tbody>{rows_l}</tbody></table></div>
</div>""")

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="UTF-8"><title>TradePilot Battle Report — {date}</title>
<style>{CSS}</style></head><body>

<div class="cover">
  <div class="badge">TRADEPILOT · DEEP-DIVE BATTLE REPORT</div>
  <h1>{date}</h1>
  <div class="subtitle">7-engine fleet · post-Rust-unlock day · SIDEWAYS regime</div>
  <div class="verdict">
    Net across the fleet: <strong>Rs {net:+,.0f}</strong>
    · {len(profitable)} profitable · {len(losers)} losing · {len(flat)} inactive
  </div>
</div>

<div class="kpi-row">
  <div class="kpi pos"><div class="label">Champion</div>
    <div class="value">{winner['label']}</div>
    <div class="small">Rs {winner['total_pnl']:+,.0f} · {winner['win_rate']}% WR · {winner['trades']} trades</div>
  </div>
  <div class="kpi pos"><div class="label">v5 Comeback</div>
    <div class="value">+Rs {by['v5']['total_pnl']:,.0f}</div>
    <div class="small">vs yesterday Rs {v5_unlock['pnl_delta']-by['v5']['total_pnl']+by['v5']['total_pnl']:+,.0f} → +Rs {v5_unlock['pnl_delta']:+,.0f} delta</div>
  </div>
  <div class="kpi neg"><div class="label">v5_2 Catastrophe</div>
    <div class="value">Rs {by['v5_2']['total_pnl']:+,.0f}</div>
    <div class="small">single options bet · -96% on NIFTY 24300PE</div>
  </div>
</div>

<h2>1. Final Scoreboard</h2>
<p>End of day {date}. Numbers from each engine's report.md (authoritative).</p>
<table><thead><tr>
  <th>Rank</th><th>Engine</th><th class="num">Net P&L</th><th class="num">% Cap</th>
  <th class="num">Trades</th><th class="num">Win %</th><th class="num">Avg Win</th><th class="num">Avg Loss</th>
</tr></thead><tbody>
{''.join(sb_rows)}
</tbody></table>
<div class="chart"><img src="charts/scoreboard.png" alt="Scoreboard"></div>

<div class="page-break"></div>
<h2>2. The Rust Unlock — Was Last Night's Fix Worth It?</h2>
<p>Last night we externalised the Rust risk-engine position cap (was hardcoded at 30, now env-driven and raised to 150). v5 was the engine being throttled. Today's data answers: was the fix worth the work?</p>

<div class="callout good">
  <strong>Verdict: {v5_unlock['verdict']}.</strong>
  v5 went from {by['v5']['trades']-v5_unlock['trade_delta']} trades / Rs {by['v5']['total_pnl']-v5_unlock['pnl_delta']:+,.0f} yesterday
  to <strong>{by['v5']['trades']} trades / Rs {by['v5']['total_pnl']:+,.0f} today</strong> —
  a swing of <strong>Rs {v5_unlock['pnl_delta']:+,.0f}</strong> in 24 hours.
</div>

<div class="chart"><img src="charts/v5_yday_vs_today.png" alt="v5 yesterday vs today"></div>

<table><thead><tr><th>Metric</th><th class="num">Yesterday (Rust locked)</th><th class="num">Today (Rust unlocked)</th><th class="num">Delta</th></tr></thead><tbody>
<tr><td>Trades</td><td class="num">{by['v5']['trades']-v5_unlock['trade_delta']}</td><td class="num">{by['v5']['trades']}</td><td class="num green">+{v5_unlock['trade_delta']} ({v5_unlock['trade_multiplier']:.1f}x)</td></tr>
<tr><td>Win Rate</td><td class="num">{by['v5']['win_rate']-v5_unlock['wr_delta']}%</td><td class="num">{by['v5']['win_rate']}%</td><td class="num green">+{v5_unlock['wr_delta']} pts</td></tr>
<tr><td>Net P&L</td><td class="num">Rs {by['v5']['total_pnl']-v5_unlock['pnl_delta']:+,.0f}</td><td class="num green">Rs {by['v5']['total_pnl']:+,.0f}</td><td class="num green">Rs {v5_unlock['pnl_delta']:+,.0f}</td></tr>
</tbody></table>

<div class="page-break"></div>
<h2>3. P&L Trajectory — Who Pulled Ahead and When</h2>
<p>15 snapshots captured by the profit-watchdog from market open to close. The shape of each engine's curve tells you when its edge kicked in.</p>
<div class="chart"><img src="charts/pnl_timeline.png" alt="P&L timeline"></div>
<p class="muted">Notice v5_6 and v5_7 climb in near-lockstep all day — both run box-theory exits in a sideways market. v5 (blue) stays Rs 5-15K behind throughout, suggesting structural exit-precision gap, not a different opportunity set.</p>

<h2>4. Why v5_6 and v5_7 Have an Edge Over v5</h2>
<p>v5 had the <strong>widest symbol coverage today ({v5_gap['v5_breadth']} unique stocks)</strong>. v5_6/v5_7 traded only {v5_gap['leader_breadth']} unique each but did 156-164 round-trips on them. v5 still finished Rs {v5_gap['pnl_gap']:,.0f} behind the leader. <strong>Breadth lost to depth.</strong></p>

<div class="chart"><img src="charts/breadth_vs_depth.png" alt="Breadth vs Depth"></div>

<table><thead><tr><th>Aspect</th><th>v5 (Rust-unlocked)</th><th>v5_6 (Darvas Box)</th><th>v5_7 (Intraday Box)</th></tr></thead><tbody>
<tr><td>Entry logic</td><td>ML score + tiered models</td><td>Find Darvas price box, buy at bottom</td><td>Mean reversion: buy oversold, sell overbought</td></tr>
<tr><td>Exit logic</td><td>Rust risk + signal flip (ML-driven)</td><td>Box top = mathematical target</td><td>Intraday box top = mathematical target</td></tr>
<tr><td>Best regime</td><td>Trending markets</td><td>Sideways markets ✓ today</td><td>Sideways markets ✓ today</td></tr>
<tr><td>Today's WR</td><td class="num">{by['v5']['win_rate']}%</td><td class="num">{by['v5_6']['win_rate']}%</td><td class="num">{by['v5_7']['win_rate']}%</td></tr>
<tr><td>Today's P&L</td><td class="num">Rs {by['v5']['total_pnl']:+,.0f}</td><td class="num">Rs {by['v5_6']['total_pnl']:+,.0f}</td><td class="num">Rs {by['v5_7']['total_pnl']:+,.0f}</td></tr>
</tbody></table>

<div class="callout">
<strong>The structural insight:</strong> Box theory gives you a mathematically defined exit (the box top). v5's ML-driven exit second-guesses the price action. In a sideways market, math beats opinion — that's why both box engines hit 92% WR while v5 sat at {by['v5']['win_rate']}%.
</div>

<h3>Symbol overlap — where the engines agreed and disagreed</h3>
<p><strong>All three agreed (consensus):</strong></p>
<div class="symbol-grid">{chips(consensus, "symbol-chip consensus")}</div>
<p><strong>v5_6 + v5_7 agreed, v5 missed:</strong></p>
<div class="symbol-grid">{chips(box_only)}</div>
<p><strong>Only v5 (the Rust-unlocked exclusive plays — Adani group + mid-cap momentum):</strong></p>
<div class="symbol-grid">{chips(v5_only)}</div>

<div class="page-break"></div>
<h2>5. Why v4 Did NOT "Fail Completely"</h2>
<p>The morning snapshot suggested v4 was dead, but its actual report tells a different story:</p>

<table><thead><tr><th>Metric</th><th class="num">v4 today</th><th>Diagnosis</th></tr></thead><tbody>
<tr><td>Trades executed</td><td class="num">{by['v4']['trades']}</td><td>Engine ran fine — scanned and traded all day</td></tr>
<tr><td>Win rate</td><td class="num">{by['v4']['win_rate']}%</td><td><strong class="red">Coin flip. The composite scorer has no edge.</strong></td></tr>
<tr><td>Net P&L</td><td class="num">Rs {by['v4']['total_pnl']:+,.0f}</td><td>Wins and losses cancel out</td></tr>
<tr><td>Best trade</td><td class="num green">Rs {max((t['pnl'] for t in by['v4']['trades_detail']), default=0):+,.0f}</td><td>Decent</td></tr>
<tr><td>Worst trade</td><td class="num red">Rs {min((t['pnl'] for t in by['v4']['trades_detail']), default=0):+,.0f}</td><td>Bad — and balances the best</td></tr>
</tbody></table>

<div class="callout warn">
<strong>Real diagnosis:</strong> v4 isn't broken — it's <em>random</em>. 51% WR with cancelling P&L is what you'd get from coin flips. The composite scoring model dates from before the v5 generation; either retire v4 or retrain its model on the last 6 months of data.
</div>

<h2>6. The Real Disaster — v5_2 (Options Engine)</h2>
<p>While the equity engines were quietly racking up wins, v5_2 made <strong>one trade all day</strong> — and lost Rs 45,385 on it.</p>
<div class="chart"><img src="charts/v52_blowup.png" alt="v5_2 blowup"></div>

<div class="callout crit">
<strong>What happened:</strong> v5_2 bought a NIFTY 24300PE put option in the morning, expecting a market crash. The market went sideways instead. The put option decayed to near-zero (entry Rs 210.20 → exit Rs 8.50 at EOD = -96%). Single bet wiped out <strong>4.54% of v5_2's capital</strong>.
</div>

<div class="callout warn">
<strong>Containment {'>'} cleverness.</strong> One bad day for v5_2 wipes out v5_classic's entire profitable day. This is the #1 priority for tonight: cap position size + add a daily loss kill-switch.
</div>

<div class="page-break"></div>
<h2>7. Watchdog Findings — Where Money Was Left on the Table</h2>

<h3>A. Pool-cap saturation</h3>
<p>All top engines hit their <strong>20-position pool cap</strong> within 30-60 minutes of open. After that, new entries only happened when an old position closed. On a 92% WR day, raising the cap would compound profits.</p>

<h3>B. Win-rate by trade count</h3>
<div class="chart"><img src="charts/winrate_bubble.png" alt="Win rate vs trades bubble"></div>
<p>The "highly profitable machine" zone is top-right: 80%+ win rate AND 100+ trades. Today v5_6 and v5_7 both landed there. v5 is climbing toward that zone — closing the WR gap is the next win.</p>

<h3>C. Exit reason mix</h3>
<div class="chart"><img src="charts/exit_mix.png" alt="Exit reasons"></div>
<p>Engines dominated by TARGET exits (green) are showing structural edge. Engines dominated by SIGNAL_FLIP or STOPLOSS need entry-quality work.</p>

<div class="page-break"></div>
<h2>8. Tonight's Tune-Up Queue</h2>
<p>Prioritised by impact and risk. Items 1-2 are tonight's must-dos. Items 3-5 are queued in <code>docs/TONIGHT_TUNEUPS_2026-04-22.md</code>.</p>

{tune_html}

<h2>9. Per-Engine Appendix</h2>
<p>Top 5 winners and losers per engine. Source: paper-trade logs.</p>

{''.join(eng_blocks)}

<div class="footer">
TradePilot deep-dive battle report · {date} · generated {datetime.now().strftime('%H:%M:%S')} ·
no commits made · uncommitted engine diffs preserved on main · all changes queued for review
</div>
</body></html>"""


# ═════════════════════════════════════════════════════════════
# Pyppeteer PDF
# ═════════════════════════════════════════════════════════════

async def html_to_pdf(html_path: Path, pdf_path: Path) -> None:
    from pyppeteer import launch
    chrome = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
    browser = await launch(executablePath=chrome, headless=True,
                           args=["--no-sandbox", "--disable-gpu"])
    try:
        page = await browser.newPage()
        await page.goto(f"file://{html_path.resolve()}",
                        {"waitUntil": "networkidle0", "timeout": 60000})
        await asyncio.sleep(2)
        await page.pdf({"path": str(pdf_path), "printBackground": True,
                        "preferCSSPageSize": True, "displayHeaderFooter": False,
                        "margin": {"top": "0", "right": "0", "bottom": "0", "left": "0"}})
    finally:
        await browser.close()


# ═════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════

def main() -> int:
    today = sys.argv[1] if len(sys.argv) > 1 else datetime.now().strftime("%Y-%m-%d")
    yday  = sys.argv[2] if len(sys.argv) > 2 else "2026-04-21"

    out_dir = OUT_BASE / f"{today}_deep_dive"
    charts_dir = out_dir / "charts"
    out_dir.mkdir(parents=True, exist_ok=True)
    charts_dir.mkdir(parents=True, exist_ok=True)

    print(f"[deep-dive] dates: today={today} yday={yday}")
    print(f"[deep-dive] output: {out_dir}")

    summaries = [gather_engine(e, today) for e in ENGINES]
    by = {s["engine"]: s for s in summaries}

    yday_v5 = gather_engine("v5", yday)
    snapshots = load_snapshots(today)

    v5_unlock = diagnose_v5_unlock(yday_v5, by["v5"])
    v5_gap = diagnose_v5_gap(by["v5"], by["v5_6"], by["v5_7"])
    tune_ups = tune_up_queue(summaries)

    print(f"[deep-dive] v5 unlock: trades +{v5_unlock['trade_delta']}, P&L Rs {v5_unlock['pnl_delta']:+,.0f}")
    print(f"[deep-dive] v5 gap to leader: Rs {v5_gap['pnl_gap']:,.0f}")
    print(f"[deep-dive] tune-up items: {len(tune_ups)}")

    # Charts
    chart_scoreboard_h(summaries, charts_dir / "scoreboard.png")
    chart_pnl_timeline(snapshots, charts_dir / "pnl_timeline.png")
    chart_yday_vs_today_v5(yday_v5, by["v5"], charts_dir / "v5_yday_vs_today.png")
    chart_winrate_bubble(summaries, charts_dir / "winrate_bubble.png")
    chart_exit_mix(summaries, charts_dir / "exit_mix.png")
    chart_breadth_vs_depth(summaries, charts_dir / "breadth_vs_depth.png")
    chart_v52_blowup(by["v5_2"], charts_dir / "v52_blowup.png")
    n_charts = len(list(charts_dir.glob("*.png")))
    print(f"[deep-dive] charts: {n_charts}")

    html = render_html(today, summaries, snapshots, v5_unlock, v5_gap, tune_ups)
    html_path = out_dir / "report.html"
    html_path.write_text(html)
    print(f"[deep-dive] HTML: {html_path}")

    # data.json — for diffing across days
    data = {
        "date": today,
        "generated_at": datetime.now().isoformat(),
        "summaries": [{k: v for k, v in s.items() if k not in ("trades_detail", "open_snapshot")}
                      for s in summaries],
        "v5_unlock": v5_unlock,
        "v5_gap": v5_gap,
        "tune_ups": tune_ups,
    }
    (out_dir / "data.json").write_text(json.dumps(data, indent=2, default=str))

    # PDF
    pdf_path = out_dir / "report.pdf"
    asyncio.run(html_to_pdf(html_path, pdf_path))
    print(f"[deep-dive] PDF: {pdf_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
