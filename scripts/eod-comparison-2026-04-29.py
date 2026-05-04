#!/usr/bin/env python3
"""
EOD comparison job for Wed 2026-04-29 — v5-vs-v6 experiment.

Fires from LaunchAgent at 16:11 IST. Reads all 6 engine reports, applies the
decision matrix from docs/learning/2026-04-29-v5-vs-v6-experiment.md, writes
EOD summary to docs/learning/2026-04-29-eod-summary.md, appends one line to
docs/observation_journal.md, and pings Telegram.

Self-deletes (via the LaunchAgent OnDemand pattern) after one run.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path

DATE = "2026-04-29"
ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")
os.chdir(ROOT)

ENGINES = ["v4", "v5", "v5_classic", "v5_6", "v5_7", "v6", "v5_8"]


def load_report(engine: str) -> dict | None:
    fp = ROOT / "docs" / "paper-trades" / engine / f"{DATE}.json"
    if not fp.exists():
        return None
    try:
        return json.loads(fp.read_text())
    except Exception:
        return None


def closed_trades(engine: str, d: dict) -> list[dict]:
    if engine == "v4":
        cl = d.get("closed_trades")
        if cl:
            return cl
        return [p for p in d.get("positions", []) if p.get("status") == "closed"]
    pools = d.get("pools", {})
    out = []
    for pool in ("INTRADAY", "SWING"):
        out.extend(pools.get(pool, {}).get("closed", []))
    return out


def trade_pnl(t: dict) -> float:
    # v5 family writes net_pnl; v4 writes pnl
    return float(t.get("net_pnl", t.get("pnl", 0)) or 0)


def trade_side(t: dict) -> str:
    s = t.get("side") or t.get("position") or t.get("direction") or ""
    s = str(s).upper()
    if "SHORT" in s or s == "SELL":
        return "SHORT"
    return "LONG"


def engine_stats(engine: str) -> dict:
    d = load_report(engine)
    if not d:
        return {"present": False}
    cl = closed_trades(engine, d)
    if not cl:
        return {"present": True, "trades": 0, "pnl": 0.0, "wins": 0, "wr": 0.0,
                "long": 0, "short": 0, "exits": {}}
    pnls = [trade_pnl(t) for t in cl]
    wins = sum(1 for p in pnls if p > 0)
    sides = [trade_side(t) for t in cl]
    exits: dict[str, int] = {}
    for t in cl:
        r = (t.get("exit_reason") or t.get("reason") or "?").upper()
        exits[r] = exits.get(r, 0) + 1
    return {
        "present": True,
        "trades": len(cl),
        "pnl": sum(pnls),
        "wins": wins,
        "wr": (100.0 * wins / len(cl)) if cl else 0.0,
        "long": sides.count("LONG"),
        "short": sides.count("SHORT"),
        "exits": exits,
    }


def fix1_firings() -> tuple[int, list[str]]:
    log = ROOT / "logs" / "v5-paper-trade.log"
    if not log.exists():
        # also try the dated variant
        log = ROOT / "logs" / f"v5-{DATE}.log"
    if not log.exists():
        return 0, []
    try:
        text = log.read_text(errors="ignore")
    except Exception:
        return 0, []
    matches = re.findall(r".*Fix#1 filtered.*", text)
    return len(matches), matches[-5:]


def v6_signal_counts() -> list[str]:
    log = ROOT / "logs" / "v6-paper-trade.log"
    if not log.exists():
        log = ROOT / "logs" / f"v6-{DATE}.log"
    if not log.exists():
        return []
    try:
        text = log.read_text(errors="ignore")
    except Exception:
        return []
    return re.findall(r".*\[v6\].*signals.*", text)[-10:]


def watchdog_insights() -> str | None:
    fp = ROOT / "docs" / "learning" / f"v5-{DATE}-insights.md"
    if not fp.exists():
        return None
    try:
        return fp.read_text()
    except Exception:
        return None


def fmt_rs(x: float) -> str:
    return f"Rs {x:>+8,.0f}"


def build_summary(stats: dict[str, dict]) -> tuple[str, str]:
    """Return (markdown_summary, one_line_verdict)."""
    f1_count, f1_samples = fix1_firings()
    v6_lines = v6_signal_counts()
    wd = watchdog_insights()

    # Decision matrix
    v4 = stats["v4"]
    v5 = stats["v5"]
    v6 = stats["v6"]
    v6v4 = (v6.get("pnl", 0) - v4.get("pnl", 0)) if v6.get("present") and v4.get("present") else None
    v5v6 = (v5.get("pnl", 0) - v6.get("pnl", 0)) if v5.get("present") and v6.get("present") else None

    def row_label(diff: float | None, threshold: float) -> str:
        if diff is None:
            return "n/a"
        if diff >= threshold:
            return f">= +Rs {threshold:,.0f}"
        if diff <= -threshold:
            return f"<= -Rs {threshold:,.0f}"
        return f"within +/- Rs {threshold:,.0f}"

    v6_vs_v4 = row_label(v6v4, 3000)
    v5_vs_v6 = row_label(v5v6, 3000)

    if v6v4 is None or v5v6 is None:
        verdict = "Inconclusive — missing engine data."
    elif v6v4 >= 3000 and abs(v5v6) < 3000:
        verdict = "Best case: Track A is value-add, Fix #1 closed v5's gap. Both viable."
    elif v6v4 >= 3000 and v5v6 < -3000:
        verdict = "Track A is value-add. Fix #1 incomplete — v5 still has bugs (likely H2)."
    elif abs(v6v4) < 2000 and abs(v5v6) < 3000:
        verdict = "Track A neutral on v4 signals. Yesterday's gain was Track A compensating for v5 bugs."
    elif abs(v6v4) < 2000 and v5v6 < -3000:
        verdict = "v5 wrapper still actively harmful. Investigate H2 (re-emission debounce)."
    elif v6v4 < -3000:
        verdict = "Track A is hurting v4. SHORT_BLOCK or RE-ARM mis-firing on v4 signal mix."
    else:
        verdict = f"Mixed signal: v6-v4={fmt_rs(v6v4)} v5-v6={fmt_rs(v5v6)}. Need more samples."

    # Build markdown
    md = []
    md.append(f"# TradePilot EOD Summary — Wednesday {DATE}\n")
    md.append("> Day 2 of the v5 Track A observation window. First day with Fix #1 in")
    md.append("> v5's signal_engine wrapper AND the new v6 engine ('v4 raw + Track A bolt-on').")
    md.append("> This summary auto-generated by `scripts/eod-comparison-2026-04-29.py`")
    md.append("> at 16:11 IST.\n")
    md.append("---\n")

    # TL;DR
    md.append("## TL;DR\n")
    combined_pnl = sum(s.get("pnl", 0) for s in stats.values() if s.get("present"))
    combined_trades = sum(s.get("trades", 0) for s in stats.values() if s.get("present"))
    md.append(f"- **Combined P&L: {fmt_rs(combined_pnl)} across {combined_trades} trades**")
    if v4.get("present"):
        md.append(f"- v4 (control): {fmt_rs(v4['pnl'])} ({v4['wr']:.0f}% WR, {v4['trades']} trades)")
    if v5.get("present"):
        md.append(f"- v5 with Fix #1: {fmt_rs(v5['pnl'])} ({v5['wr']:.0f}% WR, {v5['trades']} trades) — Fix #1 fired {f1_count}x")
    if v6.get("present"):
        md.append(f"- v6 (v4 raw + Track A): {fmt_rs(v6['pnl'])} ({v6['wr']:.0f}% WR, {v6['trades']} trades)")
    if v6v4 is not None:
        md.append(f"- **v6 vs v4 gap: {fmt_rs(v6v4)}**")
    if v5v6 is not None:
        md.append(f"- **v5 vs v6 gap: {fmt_rs(v5v6)}**")
    md.append(f"- **Verdict**: {verdict}\n")
    md.append("---\n")

    # Scoreboard
    md.append("## Final scoreboard\n")
    md.append("| # | Engine | P&L | WR | Trades | LONG | SHORT | Top exit |")
    md.append("|:---:|---|---:|---:|---:|---:|---:|---|")
    ranked = sorted(
        [(e, s) for e, s in stats.items() if s.get("present")],
        key=lambda x: -x[1].get("pnl", 0),
    )
    for i, (e, s) in enumerate(ranked, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, str(i))
        top_exit = "—"
        if s.get("exits"):
            top_exit = max(s["exits"].items(), key=lambda kv: kv[1])[0]
        md.append(f"| {medal} | **{e}** | {fmt_rs(s['pnl'])} | {s['wr']:.0f}% | {s['trades']} | {s['long']} | {s['short']} | {top_exit} |")
    missing = [e for e, s in stats.items() if not s.get("present")]
    if missing:
        md.append("")
        md.append(f"**Missing reports**: {', '.join(missing)} (engine crashed or no trades)\n")
    md.append("\n---\n")

    # Did Fix #1 fire?
    md.append("## Did Fix #1 work?\n")
    md.append(f"- Filter firings today: **{f1_count}**")
    if f1_samples:
        md.append("- Last 5 firings:")
        md.append("```")
        for ln in f1_samples:
            md.append(ln.strip()[:200])
        md.append("```")
    else:
        md.append("- No firings detected — either tape gave no bottom-rank-but-not-weak candidates, or log file missing.\n")
    md.append("")

    # v6 signals
    md.append("## v6 signal generation\n")
    if v6_lines:
        md.append("Last 10 v6 signal-count log lines:")
        md.append("```")
        for ln in v6_lines:
            md.append(ln.strip()[:200])
        md.append("```")
    else:
        md.append("No v6 signal-count log lines found.")
    md.append("")

    # Watchdog
    md.append("## Watchdog findings (v5 learning watchdog)\n")
    if wd:
        # truncate to first 60 lines
        md.append(wd[:4000])
        if len(wd) > 4000:
            md.append("\n... [truncated, see full file]")
    else:
        md.append("No watchdog insights file found at `docs/learning/v5-2026-04-29-insights.md`.")
    md.append("")

    # Decision matrix application
    md.append("---\n")
    md.append("## Decision matrix application\n")
    md.append(f"- v6 vs v4: **{v6_vs_v4}** ({fmt_rs(v6v4) if v6v4 is not None else 'n/a'})")
    md.append(f"- v5(Fix#1) vs v6: **{v5_vs_v6}** ({fmt_rs(v5v6) if v5v6 is not None else 'n/a'})")
    md.append("")
    md.append(f"**Verdict**: {verdict}\n")
    md.append("**Reminder**: One day is one sample. Do not retire any engine on this single result. Feed all into the 4-week observation window ending 2026-05-25.\n")
    md.append("---\n")
    md.append(f"_Auto-generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S %Z')}_")

    return "\n".join(md), verdict


def append_journal(stats: dict[str, dict], verdict: str) -> None:
    journal = ROOT / "docs" / "observation_journal.md"
    v4p = stats.get("v4", {}).get("pnl", 0) if stats.get("v4", {}).get("present") else None
    v5p = stats.get("v5", {}).get("pnl", 0) if stats.get("v5", {}).get("present") else None
    v6p = stats.get("v6", {}).get("pnl", 0) if stats.get("v6", {}).get("present") else None
    line = (f"\n- {DATE}: "
            f"v4 {fmt_rs(v4p) if v4p is not None else 'n/a'}, "
            f"v5(Fix#1) {fmt_rs(v5p) if v5p is not None else 'n/a'}, "
            f"v6 {fmt_rs(v6p) if v6p is not None else 'n/a'}. "
            f"Verdict: {verdict}")
    try:
        if journal.exists():
            existing = journal.read_text()
            journal.write_text(existing.rstrip() + line + "\n")
        else:
            journal.write_text(f"# Observation Journal\n## Week 1\n{line}\n")
    except Exception as e:
        print(f"[warn] journal append failed: {e}", file=sys.stderr)


def telegram(msg: str) -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    token = chat = None
    for line in env.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("TELEGRAM_CHAT_ID="):
            chat = line.split("=", 1)[1].strip().strip('"')
    if not token or not chat:
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, timeout=5,
        )
    except Exception as e:
        print(f"[warn] telegram failed: {e}", file=sys.stderr)


def main() -> int:
    print(f"[eod-comparison] start {datetime.now().isoformat()}")
    stats = {e: engine_stats(e) for e in ENGINES}
    for e, s in stats.items():
        if s.get("present"):
            print(f"  {e:12s} P&L {fmt_rs(s['pnl'])} trades {s['trades']:3d} WR {s['wr']:4.1f}%")
        else:
            print(f"  {e:12s} NO REPORT")

    summary, verdict = build_summary(stats)
    out = ROOT / "docs" / "learning" / f"{DATE}-eod-summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(summary)
    print(f"[eod-comparison] wrote {out}")

    append_journal(stats, verdict)

    short_verdict = verdict[:100] + ("..." if len(verdict) > 100 else "")
    telegram(f"📊 EOD report {DATE} ready: docs/learning/{DATE}-eod-summary.md\n\n{short_verdict}")
    print(f"[eod-comparison] verdict: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
