#!/usr/bin/env python3
"""
red-day-watchdog.py (TP-RCA, 2026-06-30) — real-time loss attribution + red-day edge.

WHY: On 2026-06-30 the market opened red (NIFTY -0.72%) and engines bled. Live attribution
showed the LONGS were the entire loss while the SHORTS were green — i.e. we lose on red days
because we stay LONG-HEAVY instead of flipping SHORT-HEAVY. This watchdog proves/monitors that
in real time and quantifies the "if we were positioned for the tape" counterfactual — the path
to making profit on ANY day.

Each cycle (every 5 min, market hours), for every active engine it logs:
  - NIFTY intraday direction (is it a red day?)
  - net P&L split into LONG vs SHORT contribution
  - the REGIME-MISMATCH verdict: on a red tape, are shorts green AND are we under-short?
  - the counterfactual: avg short-trade P&L x a BEAR slot split (long 8 / short 12) vs actual
Telegrams an alert when a clear regime mismatch is bleeding money (red tape + green shorts +
long-heavy book). Read-only: it never touches the engines. Exits at 15:35 EOD.

Run: nohup python3 scripts/red-day-watchdog.py > logs/red-day-watchdog-$(date +%F).log 2>&1 &
"""
import json, os, time, sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENGINES = ["v5", "v5_classic", "v5_long", "v5_cut"]
CYCLE_SEC = 300          # 5 min
EOD_HHMM = (15, 35)
BEAR_SLOTS = (8, 12)     # (long, short) — the BEAR regime slot split the engines already support


def _yf():
    import yfinance as yf
    try:  # per-process cache isolation (TP-RCA 2026-06-26 data-stall fix)
        tzc = Path.home() / "Library" / "Caches" / "py-yfinance" / f"reddaywd{os.getpid()}"
        tzc.mkdir(parents=True, exist_ok=True)
        yf.set_tz_cache_location(str(tzc))
    except Exception:
        pass
    return yf


def nifty_intraday():
    try:
        yf = _yf()
        n = yf.download("^NSEI", period="1d", interval="5m", progress=False)
        if len(n):
            o = float(n["Open"].iloc[0]); c = float(n["Close"].iloc[-1])
            return o, c, 100 * (c - o) / o
    except Exception:
        pass
    return None, None, None


def attribute(engine, day):
    f = ROOT / "docs" / "paper-trades" / engine / f"{day}.json"
    if not f.exists():
        return None
    try:
        d = json.load(open(f))
    except Exception:
        return None
    s = d.get("summary", {})
    longp = shortp = ln = sn = 0
    short_pnls = []

    def walk(positions):
        nonlocal longp, shortp, ln, sn
        for p in positions:
            pnl = p.get("pnl", 0) or 0
            pt = p.get("position_type") or p.get("v4_direction", "")
            if pt in ("LONG", "BUY"):
                longp += pnl; ln += 1
            elif pt in ("SHORT", "SELL"):
                shortp += pnl; sn += 1; short_pnls.append(pnl)

    pools = d.get("pools", {})
    if pools:
        for pl in pools.values():
            walk(pl.get("positions", [])); walk(pl.get("closed", []))
    else:
        walk(d.get("positions", []))
    net = s.get("total_pnl_net", s.get("total_pnl", d.get("realized_pnl", 0)))
    avg_short = (shortp / sn) if sn else 0.0
    return {"net": net, "longp": longp, "shortp": shortp, "ln": ln, "sn": sn,
            "avg_short": avg_short, "regime": s.get("regime", "?")}


def send_telegram(msg):
    env = ROOT / ".env"
    if not env.exists():
        return
    tok = chat = None
    for ln in env.read_text().splitlines():
        if ln.startswith("TELEGRAM_BOT_TOKEN="):
            tok = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("TELEGRAM_CHAT_ID="):
            chat = ln.split("=", 1)[1].strip().strip('"')
    if tok and chat:
        try:
            import urllib.request, urllib.parse
            data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
            urllib.request.urlopen(f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10)
        except Exception:
            pass


def log(m):
    print(f"[{datetime.now():%H:%M:%S}] {m}", flush=True)


def main():
    log("=== Red-Day Watchdog START — loss attribution + red-day edge ===")
    alerted = False
    while True:
        now = datetime.now()
        if (now.hour, now.minute) >= EOD_HHMM:
            log("reached EOD, exiting"); break
        day = now.strftime("%Y-%m-%d")
        o, c, pct = nifty_intraday()
        red = pct is not None and pct < -0.15
        tape = f"NIFTY {pct:+.2f}%" if pct is not None else "NIFTY ?"
        log(f"--- cycle --- {tape}  {'[RED TAPE]' if red else ''}")

        mismatch_engines = []
        for e in ENGINES:
            a = attribute(e, day)
            if not a:
                continue
            # counterfactual: same avg-short-trade P&L applied to a BEAR-style book
            # (12 shorts) minus a small long book (8 longs at the actual avg long pnl)
            avg_long = (a["longp"] / a["ln"]) if a["ln"] else 0.0
            cf = BEAR_SLOTS[1] * a["avg_short"] + BEAR_SLOTS[0] * avg_long
            verdict = ""
            if red and a["shortp"] > 0 and a["longp"] < 0 and a["ln"] > a["sn"]:
                verdict = "  <-- REGIME MISMATCH: red tape, shorts GREEN, but LONG-HEAVY"
                mismatch_engines.append(e)
            log(f"  {e:<11} net {a['net']:>8.0f} | LONG {a['longp']:>8.0f}({a['ln']}t) "
                f"SHORT {a['shortp']:>8.0f}({a['sn']}t) | reg {a['regime']:<8} "
                f"| red-day CF~{cf:>+8.0f}{verdict}")

        if red and mismatch_engines and not alerted:
            send_telegram(
                f"RED-DAY WATCHDOG: {tape}. Losing because LONG-HEAVY on a down tape — "
                f"shorts are GREEN but longs bleed. Engines mispositioned: {', '.join(mismatch_engines)}. "
                f"Red-day edge = flip short-heavy (BEAR slot split). The engines that profit on red "
                f"days are the ones that go short.")
            alerted = True
            log("  >>> Telegram alert sent (one-shot) <<<")
        time.sleep(CYCLE_SEC)


if __name__ == "__main__":
    main()
