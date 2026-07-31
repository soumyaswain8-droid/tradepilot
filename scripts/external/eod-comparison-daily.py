# MIRROR — DEPLOYED COPY LIVES OUTSIDE THE REPO.
#
#   deployed: ~/Library/Application Support/tradepilot/eod-comparison-daily.py
#   run by  : com.tradepilot.eod-comparison-daily (launchd, 16:11 weekdays)
#
# It lives outside the repo to dodge the TCC per-file taint that killed the
# other cadence jobs (see docs/learning/2026-07-28-incident-silent-failures.md).
# That also means it is NOT version-controlled where it runs — one machine
# rebuild from being lost. This mirror is tracked; edits must be applied to
# BOTH. Verify they match:  diff scripts/external/eod-comparison-daily.py \
#   "$HOME/Library/Application Support/tradepilot/eod-comparison-daily.py"
# Mirrored 2026-07-30.
#!/usr/bin/env python3
"""
Date-agnostic EOD comparison runner.

Fires daily at 16:11 IST via LaunchAgent. Reads today's reports across all
7 active engines, computes per-engine P&L (gross + adjusted for known
corporate actions), writes summary to docs/learning/{date}-eod-summary.md,
sends Telegram.

Replaces the one-shot eod-comparison-2026-04-29.py pattern.

Path note: lives in ~/Library/Application Support/tradepilot/ to avoid TCC
sandbox blocking launchd from reading scripts in ~/Documents.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime
from pathlib import Path

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")
os.chdir(ROOT)

# Engine roster is DERIVED from scripts/launch-market.sh — the single source of
# truth for what is actually trading — rather than hardcoded. The hardcoded list
# had gone stale: it still named v4/v5_6/v5_7/v6/v5_8 (all retired months ago) and
# was missing v5_long, v5_cut, v5_flip, v5_chop, v5_rrg, v5_gate and v10, so the
# EOD summary silently reported only 2 of 9 live engines. Same derivation that
# scripts/post-open-check.sh uses. Falls back to the live roster if parsing fails.
def _live_engines() -> list:
    fallback = ["v5", "v5_classic", "v5_long", "v5_cut", "v5_flip",
                "v5_chop", "v5_rrg", "v5_gate", "v10"]
    try:
        txt = (ROOT / "scripts" / "launch-market.sh").read_text()
        m = re.search(r"^ENGINES=\((.*?)^\)", txt, re.S | re.M)
        if not m:
            return fallback
        names = []
        for line in m.group(1).splitlines():
            line = line.strip()
            if not line or line.startswith("#"):      # skip retired/commented entries
                continue
            hit = re.match(r'"([a-z0-9_]+)\|', line)
            if hit:
                names.append(hit.group(1))
        return names or fallback
    except Exception:
        return fallback


ENGINES = _live_engines()

# Known corporate-action ex-dates that should be excluded from "real" P&L.
# This is a STOPGAP until the corporate-action filter ships in v5/v6 themselves
# (top priority — see FUTURE_PLANS.md). Each entry: (symbol, ex_date_str)
KNOWN_CORP_ACTIONS = [
    ("VEDL", "2026-04-30"),  # 4-way demerger, 1:1 into 5 entities
]


def load_report(engine: str, d: str) -> dict | None:
    fp = ROOT / "docs" / "paper-trades" / engine / f"{d}.json"
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
    return float(t.get("net_pnl", t.get("pnl", 0)) or 0)


def trade_side(t: dict) -> str:
    # `position_type` added 2026-07-30. The April-vintage engine (v10) writes ONLY
    # position_type, while later engines write both it and `direction`. Without it
    # every lookup missed, and the `else "LONG"` default silently reported v10 as
    # 76 LONG / 0 SHORT when it actually traded 52/24. Verified that position_type
    # and direction agree on 109/109 v5 + v5_classic trades, so ordering is safe.
    s = (t.get("side") or t.get("position") or t.get("position_type")
         or t.get("direction") or "")
    su = str(s).upper()
    if not su:
        # Unknown schema — do NOT silently default to LONG, which is what hid the
        # v10 bug. Surface it so a new engine's mis-parse is visible immediately.
        print(f"[warn] trade_side: no side field on trade {t.get('symbol','?')}", file=sys.stderr)
    return "SHORT" if "SHORT" in su or su == "SELL" else "LONG"


def is_corp_action_today(symbol: str, today: str) -> bool:
    return any(sym == symbol and ex == today for sym, ex in KNOWN_CORP_ACTIONS)


def engine_stats(engine: str, today: str) -> dict:
    d = load_report(engine, today)
    if not d:
        return {"present": False}
    cl = closed_trades(engine, d)
    if not cl:
        return {"present": True, "trades": 0, "pnl": 0.0, "adj_pnl": 0.0,
                "wins": 0, "wr": 0.0, "long": 0, "short": 0, "ca_pnl": 0.0,
                "ca_count": 0, "exits": {}}
    pnls = [trade_pnl(t) for t in cl]
    sides = [trade_side(t) for t in cl]
    wins = sum(1 for p in pnls if p > 0)

    # Corporate-action stripping
    ca_trades = [t for t in cl if is_corp_action_today(t.get("symbol", ""), today)]
    ca_pnl = sum(trade_pnl(t) for t in ca_trades)

    exits: dict[str, int] = {}
    for t in cl:
        r = (t.get("exit_reason") or t.get("reason") or "?").upper()
        exits[r] = exits.get(r, 0) + 1

    return {
        "present": True,
        "trades": len(cl),
        "pnl": sum(pnls),
        "adj_pnl": sum(pnls) - ca_pnl,
        "wins": wins,
        "wr": (100.0 * wins / len(cl)) if cl else 0.0,
        "long": sides.count("LONG"),
        "short": sides.count("SHORT"),
        "ca_pnl": ca_pnl,
        "ca_count": len(ca_trades),
        "exits": exits,
    }


def regime_today(today: str) -> str:
    log = ROOT / "logs" / f"v5-{today}.log"
    if not log.exists():
        return "unknown"
    try:
        text = log.read_text(errors="ignore")
    except Exception:
        return "unknown"
    matches = re.findall(r"regime=([A-Z]+)", text)
    if not matches:
        return "unknown"
    from collections import Counter
    counts = Counter(matches)
    return ", ".join(f"{k}({v})" for k, v in counts.most_common())


def fix1_count(today: str) -> int:
    log = ROOT / "logs" / f"v5-{today}.log"
    if not log.exists():
        return 0
    try:
        return len(re.findall(r"Fix#1 filtered", log.read_text(errors="ignore")))
    except Exception:
        return 0


def slot_blocks(engine: str, today: str) -> int:
    log = ROOT / "logs" / f"{engine}-{today}.log"
    if not log.exists():
        return 0
    try:
        return len(re.findall(r"LONG slot cap reached|SHORT slot cap reached",
                              log.read_text(errors="ignore")))
    except Exception:
        return 0


def fmt_rs(x: float) -> str:
    return f"Rs {x:>+8,.0f}"


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
    if not (token and chat):
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, timeout=8,
        )
    except Exception as e:
        print(f"warn: telegram failed: {e}", file=sys.stderr)


def build_summary(today: str, stats: dict[str, dict]) -> tuple[str, str]:
    f1c = fix1_count(today)
    regime = regime_today(today)

    md = []
    md.append(f"# TradePilot EOD Summary — {datetime.strptime(today, '%Y-%m-%d').strftime('%A')} {today}\n")
    md.append("> Auto-generated by `eod-comparison-daily.py`. Includes corporate-action adjustments.\n")
    md.append("---\n")

    # Combined
    combined_raw = sum(s.get("pnl", 0) for s in stats.values() if s.get("present"))
    combined_adj = sum(s.get("adj_pnl", 0) for s in stats.values() if s.get("present"))
    combined_trades = sum(s.get("trades", 0) for s in stats.values() if s.get("present"))
    ca_total = combined_raw - combined_adj
    ca_count = sum(s.get("ca_count", 0) for s in stats.values() if s.get("present"))

    md.append("## TL;DR\n")
    md.append(f"- **Reported combined P&L: {fmt_rs(combined_raw)}** across {combined_trades} trades")
    if abs(ca_total) > 100:
        md.append(f"- **Corporate-action adjustment: {fmt_rs(-ca_total)}** ({ca_count} trades on ex-dates — see ADJUSTMENT section)")
        md.append(f"- **REAL combined P&L (excl. corp actions): {fmt_rs(combined_adj)}**")
    md.append(f"- Regime distribution: {regime}")
    md.append(f"- v5 Fix #1 firings: {f1c}")
    md.append("")
    md.append("---\n")

    # Scoreboard (REAL P&L)
    md.append("## Scoreboard (real P&L, corp-action adjusted)\n")
    md.append("| # | Engine | Real P&L | Reported P&L | Δ (corp action) | WR | Trades | LONG | SHORT |")
    md.append("|:---:|---|---:|---:|---:|---:|---:|---:|---:|")
    ranked = sorted([(e, s) for e, s in stats.items() if s.get("present")],
                    key=lambda x: -x[1].get("adj_pnl", 0))
    for i, (e, s) in enumerate(ranked, 1):
        medal = {1: "🥇", 2: "🥈", 3: "🥉"}.get(i, str(i))
        ca_str = fmt_rs(-s.get("ca_pnl", 0)) if abs(s.get("ca_pnl", 0)) > 100 else "—"
        md.append(f"| {medal} | **{e}** | {fmt_rs(s['adj_pnl'])} | {fmt_rs(s['pnl'])} | {ca_str} | {s['wr']:.0f}% | {s['trades']} | {s['long']} | {s['short']} |")
    md.append("")

    # Corp-action adjustment detail
    if ca_count > 0:
        md.append("---\n")
        md.append("## Corporate-action adjustment\n")
        md.append("These trades were on ex-dates and the price drop was a value distribution, not a market loss. Stripped from real P&L:\n")
        md.append("| Symbol | Ex-date | Action | Total impact across engines |")
        md.append("|---|---|---|---:|")
        for sym, ex in KNOWN_CORP_ACTIONS:
            if ex != today:
                continue
            total = sum(
                trade_pnl(t)
                for e in ENGINES
                for t in (closed_trades(e, load_report(e, today) or {}) if load_report(e, today) else [])
                if t.get("symbol") == sym
            )
            action = "Demerger 1:1 into 5 entities" if sym == "VEDL" else "Corporate action"
            md.append(f"| **{sym}** | {ex} | {action} | {fmt_rs(total)} |")
        md.append("")
        md.append("**This is a known data hygiene gap**. Corporate-action filter is the top-priority Phase 1 fix scheduled for weekend May 3-4. See `docs/FUTURE_PLANS.md` TOP PRIORITY section.\n")

    md.append("---\n")
    md.append(f"_Auto-generated at {datetime.now().strftime('%Y-%m-%d %H:%M:%S IST')}_")

    # Verdict
    if abs(ca_total) > 50000 and combined_adj > -10000:
        verdict = f"Reported {fmt_rs(combined_raw)} is misleading. REAL day = {fmt_rs(combined_adj)} after stripping {ca_count} corp-action trades."
    elif combined_adj > 0:
        winner = ranked[0][0] if ranked else "?"
        verdict = f"Real combined +{fmt_rs(combined_adj)}. Best engine: {winner}."
    else:
        loser = ranked[-1][0] if ranked else "?"
        verdict = f"Real combined {fmt_rs(combined_adj)}. Worst engine: {loser}. Investigate."

    return "\n".join(md), verdict


def main() -> int:
    today = date.today().isoformat()
    print(f"[eod-comparison] {today} start {datetime.now().isoformat()}")
    stats = {e: engine_stats(e, today) for e in ENGINES}
    for e, s in stats.items():
        if s.get("present"):
            extra = ""
            if abs(s.get("ca_pnl", 0)) > 100:
                extra = f" (corp-action adj: {fmt_rs(-s['ca_pnl'])} → real: {fmt_rs(s['adj_pnl'])})"
            print(f"  {e:12s} reported {fmt_rs(s['pnl'])} {extra}")
        else:
            print(f"  {e:12s} NO REPORT")

    summary, verdict = build_summary(today, stats)
    out = ROOT / "docs" / "learning" / f"{today}-eod-summary.md"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(summary)
    print(f"[eod-comparison] wrote {out}")

    short_verdict = verdict[:200]
    telegram(f"📊 EOD report {today} ready: docs/learning/{today}-eod-summary.md\n\n{short_verdict}")
    print(f"[eod-comparison] verdict: {verdict}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
