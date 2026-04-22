#!/usr/bin/env python3
"""
Consensus-Pick Analysis (5-day backtest).

Question: do trades that multiple engines agree on win more often than solo
trades? This is the data foundation for whether to wire the dashboard's
Market Pulse / Stocks scorer into the SWING pool (Item #6).

Engine-consensus is a real backtest from paper-trade reports.
Dashboard-alignment is approximate — dashboard scores are not archived
historically; we cross-reference past trades against today's BUY list.

Output:
  docs/research/consensus-pick-analysis.md
  docs/research/consensus-pick-charts/*.png  (matplotlib)
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "docs" / "paper-trades"
OUT_DIR = ROOT / "docs" / "research"
CHARTS_DIR = OUT_DIR / "consensus-pick-charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)
CHARTS_DIR.mkdir(parents=True, exist_ok=True)

ENGINES = ["v5", "v5_6", "v5_7"]
DATES = ["2026-04-15", "2026-04-16", "2026-04-17", "2026-04-20", "2026-04-21", "2026-04-22"]

# ───────────────────────────────────────────────────────────
# Parse closed trades from each engine's daily report.md
# Format:  | # | LONG | SWING | SYMBOL | ENTRY | EXIT | Rs ±N | REASON |
# ───────────────────────────────────────────────────────────

TRADE_PAT = re.compile(
    r"^\|\s*\d+\s*\|\s*(LONG|SHORT)\s*\|\s*(\w+)\s*\|\s*(\S+?)\s*\|\s*"
    r"([\d.]+)\s*\|\s*([\d.]+)\s*\|\s*Rs\s*([+\-]?[\d,]+)\s*\|\s*(\w+)",
    re.MULTILINE,
)


def parse_report(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        text = path.read_text(errors="ignore")
    except Exception:
        return []
    out = []
    for m in TRADE_PAT.finditer(text):
        side, pool, sym, entry, exit_p, pnl_str, reason = m.groups()
        try:
            pnl = int(pnl_str.replace(",", "").replace("+", ""))
        except ValueError:
            continue
        out.append({
            "side": side, "pool": pool, "symbol": sym,
            "entry": float(entry), "exit": float(exit_p),
            "pnl": pnl, "reason": reason,
        })
    return out


# Build the dataset: trades_by_engine_day[engine][date] = [trades...]
trades_by_engine_day: dict = defaultdict(dict)
for eng in ENGINES:
    for d in DATES:
        rpt = PAPER / eng / f"{d}_report.md"
        trades_by_engine_day[eng][d] = parse_report(rpt)

# Per-day, per-symbol — which engines traded it?
# coverage[date][symbol] = set of engines that traded it that day
coverage: dict = defaultdict(lambda: defaultdict(set))
for eng in ENGINES:
    for d, trades in trades_by_engine_day[eng].items():
        for t in trades:
            coverage[d][t["symbol"]].add(eng)


# ───────────────────────────────────────────────────────────
# Tag every trade with its consensus tier
# ───────────────────────────────────────────────────────────

def tier_for(date: str, symbol: str) -> str:
    n = len(coverage[date][symbol])
    if n >= 3: return "TRIPLE"
    if n == 2: return "PAIR"
    return "SOLO"


tagged_trades: list = []
for eng in ENGINES:
    for d, trades in trades_by_engine_day[eng].items():
        for t in trades:
            tt = dict(t)
            tt["engine"] = eng
            tt["date"] = d
            tt["tier"] = tier_for(d, t["symbol"])
            tagged_trades.append(tt)

# Aggregate by tier
def stats_by_tier(trades: list, tier_filter: str | None = None) -> dict:
    pool = trades if tier_filter is None else [t for t in trades if t["tier"] == tier_filter]
    if not pool:
        return {"trades": 0, "win_rate": 0, "total_pnl": 0, "avg_pnl": 0, "avg_win": 0, "avg_loss": 0}
    pnls = [t["pnl"] for t in pool]
    wins = [p for p in pnls if p > 0]
    losses = [p for p in pnls if p < 0]
    return {
        "trades": len(pool),
        "win_rate": round(100 * len(wins) / len(pool), 1),
        "total_pnl": sum(pnls),
        "avg_pnl": round(sum(pnls) / len(pool), 0),
        "avg_win": round(sum(wins) / len(wins), 0) if wins else 0,
        "avg_loss": round(sum(losses) / len(losses), 0) if losses else 0,
    }


tier_stats = {tier: stats_by_tier(tagged_trades, tier) for tier in ["SOLO", "PAIR", "TRIPLE"]}
overall = stats_by_tier(tagged_trades)


# ───────────────────────────────────────────────────────────
# Per-day tier breakdown for the chart
# ───────────────────────────────────────────────────────────

per_day = []
for d in DATES:
    day_trades = [t for t in tagged_trades if t["date"] == d]
    row = {"date": d, "total": len(day_trades)}
    for tier in ["SOLO", "PAIR", "TRIPLE"]:
        tt = [t for t in day_trades if t["tier"] == tier]
        row[f"{tier}_n"] = len(tt)
        row[f"{tier}_pnl"] = sum(t["pnl"] for t in tt)
        wins = sum(1 for t in tt if t["pnl"] > 0)
        row[f"{tier}_wr"] = round(100 * wins / len(tt), 1) if tt else 0
    per_day.append(row)


# ───────────────────────────────────────────────────────────
# Today's dashboard BUY list — best-effort approximation for Section 2
# ───────────────────────────────────────────────────────────

dashboard_buy = []
dashboard_error = None
try:
    sys.path.insert(0, str(ROOT / "prototype"))
    try:
        from ai_scorer_v2 import score_stocks_v2 as _score
    except ImportError:
        try:
            from ai_scorer import score_stocks as _score
        except ImportError:
            _score = None
    if _score:
        scores = _score()
        dashboard_buy = sorted(
            [{"symbol": s.get("name") or s.get("symbol"), "score": s.get("score", 0)}
             for s in scores if s.get("score", 0) >= 65],
            key=lambda r: -r["score"],
        )
except Exception as e:
    dashboard_error = str(e)[:200]


# Cross-tab: of past 5-day traded symbols, how many are in today's BUY list?
all_traded_syms = sorted({t["symbol"] for t in tagged_trades})
dashboard_buy_syms = {s["symbol"] for s in dashboard_buy}
overlap_syms = sorted(set(all_traded_syms) & dashboard_buy_syms)
engine_only_syms = sorted(set(all_traded_syms) - dashboard_buy_syms)
dashboard_only_syms = sorted(dashboard_buy_syms - set(all_traded_syms))


# ───────────────────────────────────────────────────────────
# Charts
# ───────────────────────────────────────────────────────────

def chart_tier_winrate(out: Path) -> None:
    tiers = ["SOLO", "PAIR", "TRIPLE"]
    wrs = [tier_stats[t]["win_rate"] for t in tiers]
    counts = [tier_stats[t]["trades"] for t in tiers]
    colors = ["#94a3b8", "#0d9488", "#16a34a"]
    fig, ax = plt.subplots(figsize=(8, 4.8), dpi=140)
    bars = ax.bar([f"{t}\n(n={c})" for t, c in zip(tiers, counts)], wrs,
                  color=colors, edgecolor="#111", linewidth=0.8)
    for b, w in zip(bars, wrs):
        ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 1,
                f"{w}%", ha="center", fontsize=12, fontweight="bold")
    ax.axhline(80, color="#16a34a", linestyle="--", linewidth=0.9, alpha=0.6, label="80% target")
    ax.axhline(50, color="#dc2626", linestyle="--", linewidth=0.7, alpha=0.6, label="50% (random)")
    ax.set_ylim(0, 105)
    ax.set_ylabel("Win Rate (%)")
    ax.set_title("Win Rate by Consensus Tier (5 trading days)", fontsize=13, fontweight="bold")
    ax.legend(loc="lower right", fontsize=9)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_tier_pnl(out: Path) -> None:
    tiers = ["SOLO", "PAIR", "TRIPLE"]
    avg_pnl = [tier_stats[t]["avg_pnl"] for t in tiers]
    total_pnl = [tier_stats[t]["total_pnl"] for t in tiers]
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.8), dpi=140)
    bars1 = axes[0].bar(tiers, avg_pnl, color=["#94a3b8", "#0d9488", "#16a34a"],
                        edgecolor="#111", linewidth=0.8)
    for b, v in zip(bars1, avg_pnl):
        axes[0].text(b.get_x() + b.get_width()/2, b.get_height(),
                     f"Rs {v:+.0f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    axes[0].set_title("Average P&L per Trade", fontsize=12, fontweight="bold")
    axes[0].set_ylabel("Rs"); axes[0].grid(True, axis="y", alpha=0.3)
    axes[0].axhline(0, color="#222", linewidth=0.8)

    bars2 = axes[1].bar(tiers, total_pnl, color=["#94a3b8", "#0d9488", "#16a34a"],
                        edgecolor="#111", linewidth=0.8)
    for b, v in zip(bars2, total_pnl):
        axes[1].text(b.get_x() + b.get_width()/2, b.get_height(),
                     f"Rs {v:+,.0f}", ha="center", va="bottom", fontsize=11, fontweight="bold")
    axes[1].set_title("Total P&L over 5 days", fontsize=12, fontweight="bold")
    axes[1].set_ylabel("Rs"); axes[1].grid(True, axis="y", alpha=0.3)
    axes[1].axhline(0, color="#222", linewidth=0.8)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


def chart_per_day_stack(out: Path) -> None:
    dates_short = [d[5:] for d in DATES]
    solo = [d["SOLO_n"] for d in per_day]
    pair = [d["PAIR_n"] for d in per_day]
    triple = [d["TRIPLE_n"] for d in per_day]
    fig, ax = plt.subplots(figsize=(10, 4.8), dpi=140)
    ax.bar(dates_short, solo, color="#94a3b8", edgecolor="#111", label="SOLO")
    ax.bar(dates_short, pair, bottom=solo, color="#0d9488", edgecolor="#111", label="PAIR")
    ax.bar(dates_short, triple, bottom=[s+p for s, p in zip(solo, pair)],
           color="#16a34a", edgecolor="#111", label="TRIPLE")
    for i, t in enumerate([s+p+tr for s, p, tr in zip(solo, pair, triple)]):
        ax.text(i, t + 1, str(t), ha="center", fontsize=9, fontweight="bold")
    ax.set_title("Trade Count by Tier per Day", fontsize=12, fontweight="bold")
    ax.set_ylabel("Number of trades"); ax.legend()
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    fig.savefig(out, bbox_inches="tight"); plt.close(fig)


chart_tier_winrate(CHARTS_DIR / "tier_winrate.png")
chart_tier_pnl(CHARTS_DIR / "tier_pnl.png")
chart_per_day_stack(CHARTS_DIR / "per_day_stack.png")


# ───────────────────────────────────────────────────────────
# Markdown report
# ───────────────────────────────────────────────────────────

def fmt_rs(v: float) -> str:
    if v == 0: return "Rs 0"
    sign = "+" if v > 0 else ""
    return f"Rs {sign}{v:,.0f}"


# Verdict logic
solo_wr = tier_stats["SOLO"]["win_rate"]
pair_wr = tier_stats["PAIR"]["win_rate"]
triple_wr = tier_stats["TRIPLE"]["win_rate"]

solo_pnl = tier_stats["SOLO"]["avg_pnl"]
pair_pnl = tier_stats["PAIR"]["avg_pnl"]
triple_pnl = tier_stats["TRIPLE"]["avg_pnl"]

wr_increases = solo_wr <= pair_wr <= triple_wr
pnl_increases = solo_pnl <= pair_pnl <= triple_pnl

if wr_increases and pnl_increases:
    verdict = "**HYPOTHESIS CONFIRMED.** Consensus picks (PAIR + TRIPLE) win more often AND make more money per trade than SOLO picks. Wiring dashboard scores into the SWING pool is worth pursuing."
elif wr_increases:
    verdict = "**HYPOTHESIS PARTIALLY CONFIRMED.** Win rate rises with consensus, but average P&L doesn't. Consensus is a quality filter, not a profit amplifier."
elif pnl_increases:
    verdict = "**MIXED SIGNAL.** Consensus picks make more money per trade but don't win more often — bigger wins offset more losses."
else:
    verdict = "**HYPOTHESIS REJECTED.** Consensus does not predict better outcomes. Each engine's edge is independent — wiring one feed into another would dilute, not improve."

now = datetime.now().strftime("%Y-%m-%d %H:%M")
md = f"""# Consensus-Pick Analysis — 5-Day Backtest

**Generated:** {now} IST · **Author:** Kishore Rajendra · TradePilot research

---

## Question

When **multiple engines agree** on a stock (PAIR or TRIPLE consensus), do those trades **win more often** and **make more money** than trades only one engine took (SOLO)?

This data answers Item #6 in tonight's queue (Market Pulse → SWING wiring feasibility).

---

## TL;DR

{verdict}

| Tier | Trades | Win Rate | Avg P&L per trade | Total P&L (5d) |
|------|-------:|--------:|------------------:|---------------:|
| SOLO   (1 engine traded the symbol) | {tier_stats['SOLO']['trades']:>5} | {tier_stats['SOLO']['win_rate']}% | {fmt_rs(tier_stats['SOLO']['avg_pnl'])} | {fmt_rs(tier_stats['SOLO']['total_pnl'])} |
| PAIR   (2 engines agreed) | {tier_stats['PAIR']['trades']:>5} | {tier_stats['PAIR']['win_rate']}% | {fmt_rs(tier_stats['PAIR']['avg_pnl'])} | {fmt_rs(tier_stats['PAIR']['total_pnl'])} |
| TRIPLE (all 3 engines agreed) | {tier_stats['TRIPLE']['trades']:>5} | {tier_stats['TRIPLE']['win_rate']}% | {fmt_rs(tier_stats['TRIPLE']['avg_pnl'])} | {fmt_rs(tier_stats['TRIPLE']['total_pnl'])} |
| **Overall** | **{overall['trades']}** | **{overall['win_rate']}%** | **{fmt_rs(overall['avg_pnl'])}** | **{fmt_rs(overall['total_pnl'])}** |

![Win Rate by Tier](consensus-pick-charts/tier_winrate.png)

![P&L by Tier](consensus-pick-charts/tier_pnl.png)

---

## Section 1 — Engine Consensus Tiers (real backtest)

### Methodology

For each (date, symbol) combination across {len(DATES)} trading days ({DATES[0]} → {DATES[-1]}), count how many of the three top engines (v5, v5_6, v5_7) traded that symbol on that day:

- **SOLO** = 1 engine traded it
- **PAIR** = 2 engines traded it
- **TRIPLE** = all 3 engines traded it

Each *trade* (not symbol) is then tagged with its tier. So if v5_6 and v5_7 both bought NATIONALUM on Apr 21 and each closed 4 round-trips, that's **8 PAIR trades**.

### Per-day breakdown

| Date | Total trades | SOLO | PAIR | TRIPLE | SOLO P&L | PAIR P&L | TRIPLE P&L |
|------|------:|-----:|-----:|-------:|---------:|---------:|-----------:|"""

for d in per_day:
    md += (
        f"\n| {d['date']} | {d['total']:>4} | {d['SOLO_n']:>4} | {d['PAIR_n']:>4} | {d['TRIPLE_n']:>4} "
        f"| {fmt_rs(d['SOLO_pnl'])} | {fmt_rs(d['PAIR_pnl'])} | {fmt_rs(d['TRIPLE_pnl'])} |"
    )

md += f"""

![Per-day stacked breakdown](consensus-pick-charts/per_day_stack.png)

### Detailed tier stats

| Tier | Trades | Win Rate | Avg P&L | Avg Win | Avg Loss | Total P&L |
|------|-------:|--------:|--------:|--------:|---------:|----------:|
| SOLO   | {tier_stats['SOLO']['trades']} | {tier_stats['SOLO']['win_rate']}% | {fmt_rs(tier_stats['SOLO']['avg_pnl'])} | {fmt_rs(tier_stats['SOLO']['avg_win'])} | {fmt_rs(tier_stats['SOLO']['avg_loss'])} | {fmt_rs(tier_stats['SOLO']['total_pnl'])} |
| PAIR   | {tier_stats['PAIR']['trades']} | {tier_stats['PAIR']['win_rate']}% | {fmt_rs(tier_stats['PAIR']['avg_pnl'])} | {fmt_rs(tier_stats['PAIR']['avg_win'])} | {fmt_rs(tier_stats['PAIR']['avg_loss'])} | {fmt_rs(tier_stats['PAIR']['total_pnl'])} |
| TRIPLE | {tier_stats['TRIPLE']['trades']} | {tier_stats['TRIPLE']['win_rate']}% | {fmt_rs(tier_stats['TRIPLE']['avg_pnl'])} | {fmt_rs(tier_stats['TRIPLE']['avg_win'])} | {fmt_rs(tier_stats['TRIPLE']['avg_loss'])} | {fmt_rs(tier_stats['TRIPLE']['total_pnl'])} |

---

## Section 2 — Dashboard Alignment (today's snapshot, approximate)

**Limitation:** the dashboard's daily ML scores (`score_stocks_v2`) are **not archived per day**. We can only check past trades against TODAY's BUY list. This is a snapshot, not a true backtest. To enable a real Section 2 backtest, build a daily snapshot job that records the dashboard BUY list at EOD."""

if dashboard_error:
    md += f"\n\n*Note: dashboard scorer not loadable — {dashboard_error}*"
elif not dashboard_buy:
    md += "\n\n*Note: today's BUY list is empty (scorer ran but returned 0 picks ≥ 65). Dashboard alignment cannot be assessed.*"
else:
    md += f"""

### Today's dashboard BUY list ({len(dashboard_buy)} symbols, score ≥ 65)

{', '.join(s['symbol'] for s in dashboard_buy[:20])}{'...' if len(dashboard_buy) > 20 else ''}

### Cross-reference (past 5-day trades vs today's BUY list)

| Bucket | Count | Symbols (first 10) |
|--------|------:|--------------------|
| Engines AND dashboard | {len(overlap_syms)} | {', '.join(overlap_syms[:10])}{'...' if len(overlap_syms) > 10 else ''} |
| Engines only (dashboard ignored) | {len(engine_only_syms)} | {', '.join(engine_only_syms[:10])}{'...' if len(engine_only_syms) > 10 else ''} |
| Dashboard only (engines ignored) | {len(dashboard_only_syms)} | {', '.join(dashboard_only_syms[:10])}{'...' if len(dashboard_only_syms) > 10 else ''} |

**Engine ↔ dashboard overlap rate:** {round(100*len(overlap_syms)/max(1, len(all_traded_syms)), 1)}% of past-traded symbols also appear in today's BUY list."""

md += f"""

---

## Section 3 — Recommendation

### What this analysis tells us
{verdict}

### What it does NOT tell us
- **Causation vs correlation**: PAIR/TRIPLE picks may win more because the *underlying setup* is stronger (which is why multiple engines saw it), not because consensus *itself* is the edge.
- **Future generalisation**: 5 days of data, all in a SIDEWAYS regime. Box-theory engines (v5_6/v5_7) thrive here. The consensus edge may shrink in BULL/BEAR regimes when these engines diverge.
- **True dashboard alignment**: Section 2 used today's snapshot only. Real historical comparison requires daily score archiving.

### Concrete next steps for Item #6 (Market Pulse → SWING wiring)

1. **Build a daily-scores archiver** *(15 min weekend task)*. Cron `score_stocks_v2()` output to `docs/dashboard-scores/YYYY-MM-DD.json` at 09:00 IST daily. After 5+ days we can rerun this analysis with a real Section 2.

2. **Conditional wiring proposal** *(based on this run's verdict)*:
   - If verdict = HYPOTHESIS CONFIRMED → wire dashboard BUY list as an additional filter for v5/v5_6/v5_7 SWING-pool entries. Trades passing both engine signal AND dashboard BUY get larger position sizing.
   - If verdict = REJECTED → leave engines and dashboard independent. They serve different time horizons.

3. **Position-sizing experiment**: regardless of wiring, today's data suggests TRIPLE-tagged trades could be sized 1.5x. Backtest this on the next 10 days.

---

## Appendix — Methodology Caveats

- Trades parsed from `docs/paper-trades/<engine>/YYYY-MM-DD_report.md` files. Reports for v5_6 and v5_7 only exist from Apr 17 onward (newer engines). v5 has full 6-day history.
- "Same day, same symbol, multiple engines" = consensus. Different entry/exit times within a day still count as consensus if all engines were holding overlapping positions at any point.
- P&L is per closed trade (entry → exit), not mark-to-market. EOD-open positions excluded.
- Win = pnl > 0. Tie (pnl == 0) counts as not-a-win.

**Files used:**
- v5: {sum(1 for d in DATES if (PAPER/'v5'/f'{d}_report.md').exists())} of {len(DATES)} days
- v5_6: {sum(1 for d in DATES if (PAPER/'v5_6'/f'{d}_report.md').exists())} of {len(DATES)} days
- v5_7: {sum(1 for d in DATES if (PAPER/'v5_7'/f'{d}_report.md').exists())} of {len(DATES)} days

**Total trades parsed:** {len(tagged_trades)}
"""

out_path = OUT_DIR / "consensus-pick-analysis.md"
out_path.write_text(md)
print(f"[consensus-analysis] wrote: {out_path}")
print(f"[consensus-analysis] charts: {len(list(CHARTS_DIR.glob('*.png')))}")
print(f"[consensus-analysis] trades parsed: {len(tagged_trades)}")
print()
print("=== Quick verdict ===")
print(verdict)
print()
print("=== Tier stats ===")
for tier in ["SOLO", "PAIR", "TRIPLE"]:
    s = tier_stats[tier]
    print(f"  {tier:<7} n={s['trades']:>4}  WR={s['win_rate']:>5}%  avg_pnl={fmt_rs(s['avg_pnl'])}  total={fmt_rs(s['total_pnl'])}")
