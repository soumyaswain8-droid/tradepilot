#!/usr/bin/env python3
"""Satish's Telegram digest — trade-data only, no system alerts.

Two modes:
  --mode premarket     Top picks + regime context (09:00 IST)
  --mode hourly        New trades + open positions + closed summary (every 60 min)

Recipient control:
  --test               Send to TELEGRAM_CHAT_ID (Soumya — for approval)
  --production         Send to SATISH_TELEGRAM_CHAT_ID (after approval)
                        If SATISH_TELEGRAM_CHAT_ID not set, falls back to test mode.

Usage:
    python3 scripts/satish-digest.py --mode premarket --test
    python3 scripts/satish-digest.py --mode hourly --test
    python3 scripts/satish-digest.py --mode hourly --production
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "paper-trades"

# Engines whose trades we report (skip v5_classic — that's A/B internal)
REPORT_ENGINES = ["v4", "v5_6", "v5_7", "v5"]

# Human-readable strategy labels per engine
STRATEGY = {
    "v4":         "v4 Composite (LONG, ML + ORB + VWAP)",
    "v5":         "v5 Multi-Horizon (LONG + SHORT)",
    "v5_6":       "v5.6 Darvas Box (breakout)",
    "v5_7":       "v5.7 Box Theory (mean-reversion)",
    "v5_classic": "v5 Classic (pre-Rust, A/B)",
    "v5_2":       "v5.2 F&O Options",
    "v5_3":       "v5.3 Staged Entry",
}


def load_env():
    env_file = ROOT / ".env"
    out = {}
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                out[k.strip()] = v.strip().strip('"')
    return out


def send_telegram(msg, chat_id, token):
    try:
        r = subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"https://api.telegram.org/bot{token}/sendMessage",
             "--data-urlencode", f"chat_id={chat_id}",
             "--data-urlencode", f"text={msg}"],
            timeout=10, capture_output=True, text=True,
        )
        return r.returncode == 0
    except Exception:
        return False


def load_engine_trades(engine, date_str):
    """Return list of closed trades + list of open positions for an engine."""
    fp = DATA_DIR / engine / f"{date_str}.json"
    if not fp.exists():
        return [], []
    try:
        d = json.loads(fp.read_text())
    except Exception:
        return [], []

    closed = []
    open_pos = []
    if engine == "v4":
        for p in d.get("positions", []):
            base = {
                "symbol": p.get("symbol"),
                "entry_time": p.get("entry_time", "-"),
                "entry_price": p.get("entry_price", 0),
                "qty": p.get("qty", 0),
                "direction": "LONG",
                "pool": "INTRADAY",
                "sl": p.get("sl_price", 0),
                "tgt": p.get("target_price", 0),
            }
            if p.get("status") == "closed":
                base.update({
                    "exit_time": p.get("exit_time", "-"),
                    "exit_price": p.get("exit_price", 0),
                    "pnl": p.get("pnl", 0),
                    "reason": p.get("exit_reason", "-"),
                })
                closed.append(base)
            else:
                open_pos.append(base)
    else:
        # v5 family — pools
        for pool_name, pool in d.get("pools", {}).items():
            for p in pool.get("positions", []):
                open_pos.append({
                    "symbol": p.get("symbol"),
                    "entry_time": p.get("entry_time", "-"),
                    "entry_price": p.get("entry_price", 0),
                    "qty": p.get("qty", 0),
                    "direction": p.get("position_type", "LONG"),
                    "pool": pool_name,
                    "sl": p.get("sl_price", 0),
                    "tgt": p.get("target_price", 0),
                })
            for t in pool.get("closed", []):
                closed.append({
                    "symbol": t.get("symbol"),
                    "entry_time": t.get("entry_time", "-"),
                    "entry_price": t.get("entry_price", 0),
                    "exit_time": t.get("exit_time", "-"),
                    "exit_price": t.get("exit_price", 0),
                    "qty": t.get("qty", 0),
                    "direction": t.get("position_type", "LONG"),
                    "pool": pool_name,
                    "pnl": t.get("pnl", 0),
                    "reason": t.get("reason", "-"),
                })
    return closed, open_pos


def build_premarket(date_str):
    """Pre-market top picks message.

    Uses v4's signals from its first pre-market scan (usually at 08:45–09:00 IST).
    If no data yet, falls back to yesterday's closing picks as candidates.
    """
    # For today, ideally we'd read pre-market signals directly. For now,
    # peek into v4's current scan state or log for most recent signals.
    log_file = ROOT / "logs" / f"v4-{date_str}.log"
    picks_lines = []
    regime = "UNKNOWN"
    vix = "?"
    nifty_gap = "?"

    if log_file.exists():
        try:
            content = log_file.read_text(errors="ignore")
            # Find regime
            for line in content.splitlines():
                if "Regime:" in line:
                    # Example: "Regime: NEUTRAL | FII: -1060Cr DII: +2967Cr"
                    try:
                        regime = line.split("Regime:")[1].split("|")[0].strip()
                    except Exception:
                        pass
                if "VIX=" in line or "VIX " in line:
                    try:
                        v = line.split("VIX")[1].split()[0].replace("=", "").strip().rstrip(">").rstrip(")")
                        if v.replace(".", "").isdigit():
                            vix = v
                    except Exception:
                        pass
                if "Nifty" in line and "(" in line and "%" in line:
                    # Example: "Nifty: 24365 (+0.05%)"
                    try:
                        nifty_gap = line.split("(")[1].split(")")[0]
                    except Exception:
                        pass
        except Exception:
            pass

    # Read top picks directly from v4's state file (today's positions at pre-market)
    picks_from_state = []
    state_file = DATA_DIR / "v4" / f"{date_str}.json"
    if state_file.exists():
        try:
            d = json.loads(state_file.read_text())
            # v4 opens positions in pre-market — take the first 10 by entry_time
            for p in d.get("positions", [])[:10]:
                sym = p.get("symbol", "?")
                entry = p.get("entry_price", 0)
                qty = p.get("qty", 0)
                sl = p.get("sl_price", 0)
                tgt = p.get("target_price", 0)
                score = p.get("v4_score", 0)
                reasons = p.get("reasons", [])
                reason_short = reasons[0] if reasons else ""
                picks_from_state.append(
                    f"{sym:12s} @Rs {entry:.1f}  qty {qty:3d}  SL {sl:.1f}  TGT {tgt:.1f}  "
                    f"score {score:.0f}  [{reason_short[:40]}]"
                )
        except Exception:
            pass
    picks_lines = picks_from_state

    # Compact picks from state
    compact_picks = []
    state_file = DATA_DIR / "v4" / f"{date_str}.json"
    if state_file.exists():
        try:
            d = json.loads(state_file.read_text())
            for p in d.get("positions", [])[:7]:
                sym = p.get("symbol", "?")
                entry = p.get("entry_price", 0)
                tgt = p.get("target_price", 0)
                sl = p.get("sl_price", 0)
                score = p.get("v4_score", 0)
                upside = ((tgt - entry) / entry * 100) if entry else 0
                compact_picks.append(f"  🟢 {sym:11s} {entry:7.1f} → {tgt:7.1f} ({upside:+.1f}%) score {score:.0f}")
        except Exception:
            pass

    lines = []
    lines.append(f"🌅 Pre-Market · {date_str}")
    ctx = []
    if regime != "UNKNOWN":
        ctx.append(regime)
    if nifty_gap != "?":
        ctx.append(f"Nifty {nifty_gap}")
    if ctx:
        lines.append(" · ".join(ctx))
    lines.append("")
    if compact_picks:
        lines.append("Top picks (entry → target):")
        lines.extend(compact_picks)
    else:
        lines.append("(Pre-market scan in progress)")
    lines.append("")
    lines.append("Engines: v4 · v5 · v5.6 · v5.7")
    return "\n".join(lines)


def build_hourly(date_str, lookback_minutes=60):
    """Hourly message: new trades + open positions + cumulative summary."""
    now = datetime.now()
    cutoff = now - timedelta(minutes=lookback_minutes)
    cutoff_hhmm = cutoff.strftime("%H:%M")

    all_closed = []
    all_open = []
    per_engine_tally = {}

    for eng in REPORT_ENGINES:
        closed, open_pos = load_engine_trades(eng, date_str)
        for t in closed:
            t["engine"] = eng
            all_closed.append(t)
        for p in open_pos:
            p["engine"] = eng
            all_open.append(p)
        wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
        losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
        pnl_sum = sum(t.get("pnl", 0) for t in closed)
        per_engine_tally[eng] = {
            "trades": len(closed), "wins": wins, "losses": losses,
            "pnl": pnl_sum, "open": len(open_pos),
        }

    # New trades this hour (closed OR opened)
    def _recent_close(t):
        et = t.get("exit_time", "")
        try:
            return len(et) >= 5 and et[:5] > cutoff_hhmm
        except Exception:
            return False

    def _recent_open(p):
        et = p.get("entry_time", "")
        try:
            return len(et) >= 5 and et[:5] > cutoff_hhmm
        except Exception:
            return False

    recent_closed = [t for t in all_closed if _recent_close(t)]
    recent_opened = [p for p in all_open if _recent_open(p)]

    def _fmt_closed(t):
        arrow = "▲" if t["direction"] == "LONG" else "▼"
        pnl = t.get("pnl", 0)
        outcome = "✓" if pnl > 0 else "✗"
        return (f"  {arrow}{outcome} {t['symbol']:10s} "
                f"{t['entry_time'][:5]}→{t['exit_time'][:5]} "
                f"Rs {pnl:+,.0f}")

    def _fmt_open(p):
        arrow = "▲" if p["direction"] == "LONG" else "▼"
        return f"  {arrow} {p['symbol']:10s} {p['entry_time'][:5]} @{p['entry_price']:.1f}"

    lines = []
    lines.append(f"📊 {now.strftime('%H:%M')} · Last {lookback_minutes}min")

    total_trades = sum(t["trades"] for t in per_engine_tally.values())
    total_wins = sum(t["wins"] for t in per_engine_tally.values())
    total_losses = sum(t["losses"] for t in per_engine_tally.values())
    total_pnl = sum(t["pnl"] for t in per_engine_tally.values())
    total_open = sum(t["open"] for t in per_engine_tally.values())
    wr = (total_wins/total_trades*100) if total_trades else 0

    lines.append(f"Day: Rs {total_pnl:+,.0f} · {total_trades}t · {wr:.0f}% WR · {total_open} open")
    lines.append("")

    # Per-engine one-liner
    for eng in REPORT_ENGINES:
        t = per_engine_tally[eng]
        name = eng.replace("_", ".")
        lines.append(f"  {name:10s} Rs {t['pnl']:+6,.0f}  {t['trades']:3d}t ({t['wins']}W/{t['losses']}L)")
    lines.append("")

    # New closed — top 5 by |pnl|
    if recent_closed:
        top5 = sorted(recent_closed, key=lambda x: -abs(x.get("pnl", 0)))[:5]
        lines.append(f"Closed this hour ({len(recent_closed)} total, top 5):")
        for t in top5:
            lines.append(_fmt_closed(t))
    else:
        lines.append("No trades closed this hour.")
    lines.append("")

    # New opened — just count + top 5 symbols
    if recent_opened:
        syms = ", ".join(sorted(set(p["symbol"] for p in recent_opened))[:8])
        lines.append(f"Opened ({len(recent_opened)}): {syms}")
    lines.append("")

    # Currently holding — just count + top 5 by size
    if all_open:
        top_holds = sorted(all_open, key=lambda x: -(x.get("qty",0)*x.get("entry_price",0)))[:5]
        syms = ", ".join(p["symbol"] for p in top_holds)
        lines.append(f"Holding ({len(all_open)}): {syms}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["premarket", "hourly"], required=True)
    parser.add_argument("--test", action="store_true",
                        help="Send to Soumya (for approval)")
    parser.add_argument("--production", action="store_true",
                        help="Send to Satish (after approval)")
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--lookback", type=int, default=60, help="Hourly lookback minutes")
    parser.add_argument("--no-send", action="store_true", help="Print, don't send")
    args = parser.parse_args()

    date_str = args.date or datetime.now().strftime("%Y-%m-%d")

    if args.mode == "premarket":
        msg = build_premarket(date_str)
    else:
        msg = build_hourly(date_str, lookback_minutes=args.lookback)

    print(msg)
    print()

    if args.no_send:
        return 0

    env = load_env()
    token = env.get("TELEGRAM_BOT_TOKEN", "")
    if not token:
        print("ERROR: TELEGRAM_BOT_TOKEN not in .env")
        return 1

    # Routing: default to TEST unless --production AND SATISH_TELEGRAM_CHAT_ID is set
    if args.production:
        satish_chat = env.get("SATISH_TELEGRAM_CHAT_ID", "")
        if not satish_chat:
            print("⚠ SATISH_TELEGRAM_CHAT_ID not in .env — falling back to TEST (Soumya)")
            chat = env.get("TELEGRAM_CHAT_ID", "")
            recipient = "Soumya (fallback)"
        else:
            chat = satish_chat
            recipient = "Satish"
    else:
        chat = env.get("TELEGRAM_CHAT_ID", "")
        recipient = "Soumya (test)"

    if not chat:
        print("ERROR: no chat_id resolved")
        return 1

    ok = send_telegram(msg, chat, token)
    print(f"→ sent to {recipient}: {'✓' if ok else '✗'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
