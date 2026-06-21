#!/usr/bin/env python3
"""
v4 sizer diagnostic — one-shot WHY explainer.

Reads v4 state + today's dashboard scores, traces the filter funnel:
  scorer BUYs --> held/corp_ban/loss_cap/watchlist filter --> sizer floor --> deployed

Outputs a single Markdown report at:
  docs/v4-leakage/diagnostic-YYYY-MM-DD-HHMMSS.md
"""
import json, datetime, sys
from pathlib import Path

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")
sys.path.insert(0, str(ROOT / "prototype"))
TODAY = datetime.date.today().isoformat()
NOW = datetime.datetime.now().strftime("%H%M%S")
STATE = ROOT / f"docs/paper-trades/v4/{TODAY}.json"
DASH = ROOT / f"docs/dashboard-scores/{TODAY}.json"
OUT_DIR = ROOT / "docs/v4-leakage"
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT = OUT_DIR / f"diagnostic-{TODAY}-{NOW}.md"

# ─── Load inputs ─────────────────────────────────────────────────────────────
state = json.loads(STATE.read_text()) if STATE.exists() else {}
dash = json.loads(DASH.read_text()) if DASH.exists() else {}

held = {p.get("symbol", p.get("ticker", "")) for p in state.get("positions", [])}
watchlist = state.get("watchlist", {}) or {}
loss_counts = state.get("stock_loss_count", {}) or {}
corp_actions_path = ROOT / "prototype/data/corp_actions.json"
corp_bans = {}
if corp_actions_path.exists():
    try:
        ca = json.loads(corp_actions_path.read_text())
        corp_bans = ca.get("bans", ca) if isinstance(ca, dict) else {}
    except Exception:
        corp_bans = {}

cash = float(state.get("cash", 0) or 0)
deployed_capital = float(state.get("total_deployed", 0) or 0)
realized = float(state.get("realized_pnl", 0) or 0)

# Pull the BUY list from dashboard scores
all_stocks = dash.get("stocks", [])
buys = [s for s in all_stocks if s.get("direction") == "BUY"]
buys_sorted = sorted(buys, key=lambda x: x.get("score", 0), reverse=True)

# ─── Trace each BUY through the filter chain ─────────────────────────────────
MAX_LOSSES_PER_STOCK_PER_DAY = 2  # from v4-paper-trade.py defaults

rows = []
for b in buys_sorted:
    sym_full = b.get("symbol", "")
    sym = sym_full.replace(".NS", "")
    score = b.get("score", 0)
    price = b.get("price", 0)
    status = "PASS"
    reason = ""
    if sym_full in held or sym in held:
        status, reason = "DROP-held", "already in portfolio"
    elif sym_full in corp_bans or sym in corp_bans:
        status, reason = "DROP-corp", str(corp_bans.get(sym, corp_bans.get(sym_full, "")))[:60]
    elif loss_counts.get(sym, 0) >= MAX_LOSSES_PER_STOCK_PER_DAY:
        status, reason = "DROP-losses", f"{loss_counts.get(sym)} losses today"
    elif sym in watchlist or sym_full in watchlist:
        status, reason = "DROP-watchlist", "needs revival signal (Bullish Engulfing + 1.5x vol)"
    rows.append({"sym": sym, "score": score, "price": price, "status": status, "reason": reason})

passes = [r for r in rows if r["status"] == "PASS"]

# ─── Reconstruct sizer math ──────────────────────────────────────────────────
MIN_FLOOR = 20_000.0
MAX_PCT = 0.20
sizer_pass = []
sizer_drop = []
if passes:
    total_score = sum(r["score"] for r in passes)
    max_alloc = MAX_PCT * cash
    for r in passes:
        base = (r["score"] / total_score) * cash if total_score > 0 else 0
        capped = min(base, max_alloc)
        if capped < MIN_FLOOR:
            sizer_drop.append({**r, "alloc": capped, "would_qty": int(capped / r["price"]) if r["price"] > 0 else 0})
        else:
            qty = int(capped / r["price"]) if r["price"] > 0 else 0
            sizer_pass.append({**r, "alloc": capped, "qty": qty})

# ─── Render Markdown report ──────────────────────────────────────────────────
md = []
md.append(f"# v4 sizer diagnostic — {TODAY} {datetime.datetime.now().strftime('%H:%M:%S')}\n")
md.append(f"**Source**: state @ `{STATE.name}` · scores @ `{DASH.name}`\n")
md.append("\n## TL;DR — the funnel\n")
funnel = [
    ("Stocks scored", dash.get("total_scored", len(all_stocks))),
    ("Scorer BUYs", len(buys)),
    ("After held filter", len(buys) - sum(1 for r in rows if r["status"] == "DROP-held")),
    ("After corp-action filter", len(buys) - sum(1 for r in rows if r["status"].startswith("DROP-") and r["status"] != "DROP-held")),
    ("After loss-count filter", len(buys) - sum(1 for r in rows if r["status"] in ("DROP-held", "DROP-corp", "DROP-losses"))),
    ("After watchlist filter (passes pre-sizer)", len(passes)),
    ("After sizer floor (deployable)", len(sizer_pass)),
]
md.append("| Stage | Count |")
md.append("|---|---:|")
for label, n in funnel:
    md.append(f"| {label} | **{n}** |")
md.append("")

# Why each drop bucket exists
md.append("## Drop reasons\n")
buckets = {"DROP-held": [], "DROP-corp": [], "DROP-losses": [], "DROP-watchlist": []}
for r in rows:
    if r["status"] in buckets:
        buckets[r["status"]].append(r)
for tag, label in [
    ("DROP-held", "Already held"),
    ("DROP-corp", "Corporate action ban"),
    ("DROP-losses", "Hit per-day loss cap (2 losses → blacklist)"),
    ("DROP-watchlist", "On watchlist (recently exited at loss; needs revival signal)"),
]:
    items = buckets.get(tag, [])
    md.append(f"### {label} — {len(items)} drops")
    if items:
        md.append("| Symbol | Score | Reason |")
        md.append("|---|---:|---|")
        for r in items[:20]:
            md.append(f"| {r['sym']} | {r['score']:.1f} | {r['reason'] or '—'} |")
    md.append("")

# Sizer floor drops
md.append(f"## Sizer floor drops — {len(sizer_drop)} candidates\n")
md.append(f"Cash available: **Rs {cash:,.0f}**, floor Rs {MIN_FLOOR:,.0f}/stock, max {MAX_PCT*100:.0f}%/stock\n")
if sizer_drop:
    md.append("| Symbol | Score | Allocation | Floor | Why dropped |")
    md.append("|---|---:|---:|---:|---|")
    for r in sizer_drop[:20]:
        md.append(f"| {r['sym']} | {r['score']:.1f} | Rs {r['alloc']:,.0f} | Rs {MIN_FLOOR:,.0f} | below floor |")
else:
    md.append("_No sizer-floor drops in this scan._\n")
md.append("")

# What deployed
md.append(f"## Would deploy — {len(sizer_pass)} positions\n")
if sizer_pass:
    total_alloc = sum(r["alloc"] for r in sizer_pass)
    md.append(f"Total deployed: **Rs {total_alloc:,.0f}** ({total_alloc/cash*100:.1f}% of cash)\n")
    md.append("| Symbol | Score | Price | Allocation | Qty |")
    md.append("|---|---:|---:|---:|---:|")
    for r in sizer_pass[:20]:
        md.append(f"| {r['sym']} | {r['score']:.1f} | Rs {r['price']:.2f} | Rs {r['alloc']:,.0f} | {r['qty']} |")
md.append("")

# Leakage estimate
md.append("## Leakage estimate\n")
total_buys = len(buys)
deployed_n = len(sizer_pass)
gap = total_buys - deployed_n
ideal_alloc_per = cash / max(deployed_n, 1) if deployed_n else 0
intraday_proxy = (realized / deployed_capital * 100) if deployed_capital else 0
idle_capital = cash - sum(r["alloc"] for r in sizer_pass)
leakage = idle_capital * intraday_proxy / 100
md.append(f"- Scorer BUYs: **{total_buys}** | Actually deployable: **{deployed_n}** | Gap: **{gap}**")
md.append(f"- Idle cash: **Rs {idle_capital:,.0f}**")
md.append(f"- Realized P&L proxy alpha: **{intraday_proxy:.2f}%**")
md.append(f"- Estimated leakage Rs (idle × alpha): **Rs {leakage:,.0f}**")
md.append("")
md.append("> Note: leakage is a lower bound. It assumes idle capital would have earned the same alpha as deployed. On a trending day with higher alpha, leakage scales linearly.")
md.append("")

# Diagnosis & recommendations
md.append("## Diagnosis\n")
if buckets["DROP-held"] and len(buckets["DROP-held"]) > 5:
    md.append(f"- **`held` filter is the dominant bucket ({len(buckets['DROP-held'])} drops)** — v4 already owns these names. This is correct behavior.")
if buckets["DROP-watchlist"]:
    md.append(f"- **`watchlist` is blocking {len(buckets['DROP-watchlist'])} re-entries** — they exited at loss earlier and need a revival candle pattern. Loosening the revival check (or shrinking the watchlist window) would re-open these.")
if buckets["DROP-losses"]:
    md.append(f"- **`loss_cap` blocked {len(buckets['DROP-losses'])} re-entries** — these stocks hit 2 losses today and are blacklisted. Increasing MAX_LOSSES_PER_STOCK_PER_DAY would re-open them but raises overtrading risk.")
if sizer_drop:
    md.append(f"- **{len(sizer_drop)} below-floor drops** — score-weighted allocation under-allocates them. Either lower `min_per_stock_rs` or shrink the universe (drop lowest scores explicitly so survivors clear floor).")
md.append("")

OUT.write_text("\n".join(md))
print(f"Wrote {OUT}")
print(f"\nFunnel:")
for label, n in funnel:
    print(f"  {label}: {n}")
