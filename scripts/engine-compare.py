#!/usr/bin/env python3
"""
engine-compare.py (TP-RCA, 2026-06-26) — daily four-way engine comparison + Telegram.

Reports today's (or the latest available session's) Net P&L / win-rate / trades for the
ACTIVE lean roster, plus a trailing cumulative, and sends it to Telegram. Scheduled via
com.tradepilot.engine-compare.plist (weekdays 15:40 IST, after auto-stop-eod at 15:35).
Built to track the RC-1 experiment: v5_long (long-only) vs live v5 vs v5_classic vs v5_cut.

Usage: python3 scripts/engine-compare.py            # latest session
       python3 scripts/engine-compare.py 2026-06-29 # specific date
"""
import json, os, sys, glob
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ["v5", "v5_long", "v5_classic", "v5_cut", "v5_flip"]   # active lean roster
LABELS = {"v5": "v5 (live)", "v5_long": "v5_long (RC-1 long-only)",
          "v5_classic": "v5_classic (frozen)", "v5_cut": "v5_cut",
          "v5_flip": "v5_flip (fast regime-flip)"}


def _pnl(engine: str, d: str):
    """Return (net_pnl, trades, win_rate, longs, shorts) for engine on date d, or None."""
    f = ROOT / "docs" / "paper-trades" / engine / f"{d}.json"
    if not f.exists():
        return None
    try:
        s = json.load(open(f)).get("summary", {})
        net = s.get("total_pnl_net", s.get("total_pnl", 0.0))
        wins, losses = s.get("wins", 0), s.get("losses", 0)
        wr = (100.0 * wins / (wins + losses)) if (wins + losses) else 0.0
        return (net, s.get("trades", 0), wr, s.get("longs", 0), s.get("shorts", 0))
    except Exception:
        return None


def _latest_date():
    """Most recent date for which live v5 has a data file."""
    files = sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / "v5" / "20*.json")))
    files = [f for f in files if "_" not in Path(f).stem]   # skip *_report etc.
    return Path(files[-1]).stem if files else None


def _recent_dates(n=8):
    files = sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / "v5" / "20*.json")))
    return [Path(f).stem for f in files if "_" not in Path(f).stem][-n:]


def build_message(target: str) -> str:
    lines = [f"TradePilot engine compare — {target}", ""]
    day = {e: _pnl(e, target) for e in ENGINES}
    ranked = sorted([e for e in ENGINES if day[e]], key=lambda e: day[e][0], reverse=True)
    if not ranked:
        lines.append("(no trade data for this date)")
    for e in ranked:
        net, tr, wr, lo, sh = day[e]
        flag = "🟢" if net > 0 else ("🔴" if net < 0 else "⚪")
        lines.append(f"{flag} {LABELS[e]}: Rs {net:+,.0f}  ({tr}t, {wr:.0f}% WR, L{lo}/S{sh})")
    # trailing cumulative
    dates = _recent_dates(8)
    lines += ["", f"Cumulative (last {len(dates)} sessions):"]
    cum = []
    for e in ENGINES:
        tot = sum(_pnl(e, d)[0] for d in dates if _pnl(e, d))
        cum.append((e, tot))
    for e, tot in sorted(cum, key=lambda x: x[1], reverse=True):
        lines.append(f"  {LABELS[e]}: Rs {tot:+,.0f}")
    return "\n".join(lines)


def send_telegram(msg: str):
    env = ROOT / ".env"
    if not env.exists():
        return
    tok = chat = None
    for ln in env.read_text().splitlines():
        if ln.startswith("TELEGRAM_BOT_TOKEN="):
            tok = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("TELEGRAM_CHAT_ID="):
            chat = ln.split("=", 1)[1].strip().strip('"')
    if not (tok and chat):
        return
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10)
    except Exception as e:
        print(f"telegram send failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else (_latest_date() or str(date.today()))
    message = build_message(target)
    print(message)
    send_telegram(message)
