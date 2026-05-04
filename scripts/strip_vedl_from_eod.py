#!/usr/bin/env python3
"""Generate VEDL-stripped sibling versions of 2026-04-30 EOD reports.

Originals are NOT modified — they remain the audit record. For each variant,
this writes:
  docs/paper-trades/<variant>/2026-04-30_adjusted.json
  docs/paper-trades/<variant>/2026-04-30_adjusted.md

Both contain the same fields with VEDL trades removed and totals recomputed.
"""
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATE = "2026-04-30"
SYMBOL = "VEDL"

results = []

for vdir in sorted((ROOT / "docs" / "paper-trades").glob("v*")):
    src = vdir / f"{DATE}.json"
    if not src.exists():
        continue
    data = json.loads(src.read_text())

    # Strip VEDL from each pool's closed list and recompute pool pnl
    vedl_trades = []
    pools = data.get("pools", {})
    for pname, p in pools.items():
        kept = []
        removed_pnl = 0.0
        for c in p.get("closed", []):
            if c.get("symbol") == SYMBOL:
                vedl_trades.append({**c, "pool": pname})
                removed_pnl += float(c.get("pnl_net", c.get("pnl", 0)) or 0)
            else:
                kept.append(c)
        p["closed"] = kept
        # Recompute pool-level pnl from kept trades
        kept_pnl = sum(float(c.get("pnl_net", c.get("pnl", 0)) or 0) for c in kept)
        p["pnl"] = round(kept_pnl, 2)
        if removed_pnl != 0:
            p["_vedl_stripped_pnl"] = round(removed_pnl, 2)

    # Headline stats
    all_kept = [c for p in pools.values() for c in p.get("closed", [])]
    total_pnl = sum(float(c.get("pnl_net", c.get("pnl", 0)) or 0) for c in all_kept)
    wins = sum(1 for c in all_kept if float(c.get("pnl_net", c.get("pnl", 0)) or 0) > 0)
    win_rate = (wins / len(all_kept) * 100) if all_kept else 0
    longs = sum(1 for c in all_kept if c.get("position_type") != "SHORT")
    shorts = len(all_kept) - longs

    data["_adjustment"] = {
        "type": "VEDL_STRIPPED",
        "reason": "Vedanta 1:1 demerger ex-date 2026-04-30 — Rs 773 -> Rs 277 is value redistributed across 5 ISINs, not a market loss.",
        "stripped_trades": vedl_trades,
        "stripped_count": len(vedl_trades),
        "stripped_pnl_total": round(sum(float(t.get("pnl_net", t.get("pnl", 0)) or 0) for t in vedl_trades), 2),
        "adjusted_total_pnl": round(total_pnl, 2),
        "adjusted_trade_count": len(all_kept),
        "adjusted_win_rate_pct": round(win_rate, 1),
        "adjusted_long_short": f"{longs}/{shorts}",
        "generated_at": datetime.now().isoformat(),
    }

    out_json = vdir / f"{DATE}_adjusted.json"
    out_json.write_text(json.dumps(data, indent=2))

    # Markdown sibling
    capital = data.get("total_capital", 1_000_000)
    pct = (total_pnl / capital * 100) if capital else 0
    md = []
    md.append(f"# v5 Paper Trading Report (VEDL-Adjusted) — {DATE}")
    md.append("")
    md.append("> **Adjustment**: VEDL trades stripped. Rs 773 → Rs 277 was the 1:1 demerger ex-date redistribution, not a market loss. Originals preserved in `2026-04-30.json` / `2026-04-30_report.md`.")
    md.append("")
    md.append("## Adjusted Summary")
    md.append("")
    md.append("| Metric | Value |")
    md.append("|--------|-------|")
    md.append(f"| Engine | {data.get('engine','?')} multi-pool |")
    md.append(f"| Capital | Rs {capital/1e5:.2f}L |")
    md.append(f"| Regime | {data.get('regime','?')} |")
    md.append(f"| **Adjusted Net P&L** | **Rs {total_pnl:+,.0f} ({pct:+.2f}%)** |")
    md.append(f"| Adjusted Trades | {len(all_kept)} (L:{longs} S:{shorts}) |")
    md.append(f"| Adjusted Win Rate | {win_rate:.0f}% |")
    md.append(f"| VEDL trades stripped | {len(vedl_trades)} |")
    md.append(f"| VEDL fictitious P&L removed | Rs {data['_adjustment']['stripped_pnl_total']:+,.0f} |")
    md.append("")
    md.append("## VEDL Trades That Were Stripped")
    md.append("")
    if vedl_trades:
        md.append("| Pool | Type | Entry | Exit | Qty | P&L (gross) | P&L (net) | Reason |")
        md.append("|------|------|-------|------|-----|-------------|-----------|--------|")
        for t in vedl_trades:
            md.append(f"| {t.get('pool','?')} | {t.get('position_type','?')} | "
                      f"{t.get('entry_price','?')} | {t.get('exit_price','?')} | "
                      f"{t.get('qty','?')} | Rs {float(t.get('pnl',0)):+,.0f} | "
                      f"Rs {float(t.get('pnl_net', t.get('pnl', 0))):+,.0f} | {t.get('reason','?')} |")
    else:
        md.append("_(no VEDL trades found)_")
    md.append("")
    md.append("## Remaining Trades (post-adjustment)")
    md.append("")
    if all_kept:
        md.append("| # | Pool | Type | Stock | Entry | Exit | P&L (net) | Reason |")
        md.append("|---|------|------|-------|-------|------|-----------|--------|")
        for i, c in enumerate(all_kept, 1):
            md.append(f"| {i} | {c.get('pool','?')} | {c.get('position_type','?')} | "
                      f"{c.get('symbol','?')} | {c.get('entry_price','?')} | {c.get('exit_price','?')} | "
                      f"Rs {float(c.get('pnl_net', c.get('pnl', 0))):+,.0f} | {c.get('reason','?')} |")
    md.append("")

    out_md = vdir / f"{DATE}_adjusted.md"
    out_md.write_text("\n".join(md))

    results.append({
        "variant": vdir.name,
        "stripped_count": len(vedl_trades),
        "stripped_pnl": data["_adjustment"]["stripped_pnl_total"],
        "adjusted_pnl": total_pnl,
        "json": str(out_json.relative_to(ROOT)),
        "md": str(out_md.relative_to(ROOT)),
    })

print(f"\n{'Variant':<14} {'VEDL trades':>11}  {'Stripped P&L':>14}  {'Adjusted P&L':>14}")
print("-" * 60)
for r in results:
    print(f"{r['variant']:<14} {r['stripped_count']:>11}  Rs {r['stripped_pnl']:>+11,.0f}  Rs {r['adjusted_pnl']:>+11,.0f}")
print(f"\nGenerated {len(results)} adjusted report pairs.")
