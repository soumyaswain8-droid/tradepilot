#!/usr/bin/env python3
"""
fleet-telegram — render the fleet view as an image and send it to Telegram.

WHY AN IMAGE RATHER THAN A LINK
Getting the dashboard onto a phone by URL needs either a firewall exception (the
2026-07-24 hardening blocks all inbound) or a public tunnel (an ngrok URL is public
to anyone holding it). An image needs neither: it goes out over the Telegram bot
that already works, renders on the phone, and forwards to anyone with one tap.

It also degrades honestly — if Chrome or the render fails, it sends the TEXT summary
instead of silently sending nothing. A status report that can fail invisibly is
worse than none, which this stack has already proved twice (the Markdown page that
died at byte 236, the preflight that could not write its log).

Run:
    python3 scripts/fleet-telegram.py              # image + caption
    python3 scripts/fleet-telegram.py --text-only  # skip the render
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
FLEET_URL = "http://127.0.0.1:5051/?static=1"
FALLBACK_URL = "http://127.0.0.1:5050/fleet?static=1"
CPT = 14.30


def creds() -> tuple:
    env = ROOT / ".env"
    tok = chat = None
    if env.exists():
        for ln in env.read_text().splitlines():
            if ln.startswith("TELEGRAM_BOT_TOKEN="):
                tok = ln.split("=", 1)[1].strip().strip('"')
            elif ln.startswith("TELEGRAM_CHAT_ID="):
                chat = ln.split("=", 1)[1].strip().strip('"')
    return tok, chat


def collect() -> tuple:
    today = datetime.now().strftime("%Y-%m-%d")
    engines = []
    for f in sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / "*" / f"{today}.json"))):
        name = os.path.basename(os.path.dirname(f))
        try:
            d = json.load(open(f))
        except Exception:
            continue
        sm = d.get("summary") or {}
        pools = d.get("pools") or {}
        npos = sum(len(p.get("positions") or []) for p in pools.values())
        gross = sm.get("total_pnl") or 0
        net = sm.get("total_pnl_net")
        cost = sm.get("total_cost") or 0
        trades = sm.get("trades") or 0
        books = cost > 0
        true = net if (books and net is not None) else (gross - trades * CPT if not books else gross)
        cap = d.get("total_capital") or 0
        if cap <= 0:
            continue
        engines.append({"name": name, "cap": cap, "pos": npos,
                        "trades": trades, "net": round(true)})
    engines.sort(key=lambda e: -e["net"])
    fleet = {"n": len(engines), "pos": sum(e["pos"] for e in engines),
             "trades": sum(e["trades"] for e in engines),
             "net": round(sum(e["net"] for e in engines)),
             "green": sum(1 for e in engines if e["net"] > 0)}
    return engines, fleet


def caption(engines, fleet) -> str:
    """PLAIN TEXT. A Markdown caption died with 'can't parse entities' on
    2026-07-28 and never reached anyone."""
    ts = datetime.now().strftime("%d %b, %H:%M IST")
    lines = [f"TradePilot fleet - {ts}",
             f"Net Rs {fleet['net']:+,} | {fleet['pos']} open | {fleet['trades']} trades",
             f"{fleet['green']}/{fleet['n']} engines in profit", ""]
    for e in engines[:6]:
        tag = "1L" if 90000 <= e["cap"] <= 110000 else "10L"
        lines.append(f"  {e['name']:<12} {tag:<4} Rs {e['net']:+,}")
    if len(engines) > 6:
        lines.append(f"  ... and {len(engines)-6} more")
    lines.append("")
    lines.append("PAPER - simulated fills, no real money, no broker orders.")
    return "\n".join(lines)


def render(out: Path) -> bool:
    """Headless Chrome screenshot. Returns False on any failure so the caller can
    fall back to text rather than sending nothing."""
    if not os.path.exists(CHROME):
        print("  chrome not found — text only", file=sys.stderr)
        return False
    url = FLEET_URL
    try:
        import urllib.request
        urllib.request.urlopen(url, timeout=5)
    except Exception:
        url = FALLBACK_URL
    try:
        subprocess.run([CHROME, "--headless", "--disable-gpu", "--no-sandbox",
                        "--hide-scrollbars", "--force-device-scale-factor=2",
                        "--window-size=560,1400", f"--screenshot={out}", url],
                       capture_output=True, timeout=90)
        return out.exists() and out.stat().st_size > 5000
    except Exception as e:
        print(f"  render failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def send_photo(tok, chat, img: Path, cap: str) -> bool:
    try:
        import urllib.request, uuid
        b = uuid.uuid4().hex
        body = bytearray()
        for k, v in (("chat_id", chat), ("caption", cap)):
            body += f"--{b}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n{v}\r\n".encode()
        body += (f"--{b}\r\nContent-Disposition: form-data; name=\"photo\"; "
                 f"filename=\"fleet.png\"\r\nContent-Type: image/png\r\n\r\n").encode()
        body += img.read_bytes() + f"\r\n--{b}--\r\n".encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{tok}/sendPhoto", data=bytes(body),
            headers={"Content-Type": f"multipart/form-data; boundary={b}"})
        with urllib.request.urlopen(req, timeout=45) as r:
            return r.status == 200
    except Exception as e:
        print(f"  sendPhoto failed: {type(e).__name__}: {e}", file=sys.stderr)
        return False


def send_text(tok, chat, msg: str) -> bool:
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        with urllib.request.urlopen(
                f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=20) as r:
            return r.status == 200
    except Exception as e:
        print(f"  sendMessage failed: {e}", file=sys.stderr)
        return False


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--text-only", action="store_true")
    a = ap.parse_args()

    tok, chat = creds()
    if not (tok and chat):
        print("  no telegram credentials in .env", file=sys.stderr)
        return 1

    engines, fleet = collect()
    if not engines:
        print("  no engine data for today — nothing to send")
        return 0
    cap = caption(engines, fleet)

    if a.text_only:
        ok = send_text(tok, chat, cap)
        print(f"  text {'sent' if ok else 'FAILED'}")
        return 0 if ok else 1

    img = Path(tempfile.gettempdir()) / "tradepilot_fleet.png"
    if render(img):
        if send_photo(tok, chat, img, cap):
            print(f"  image sent ({img.stat().st_size//1024} KB) - {fleet['n']} engines")
            return 0
        print("  photo send failed — falling back to text", file=sys.stderr)
    else:
        print("  render failed — falling back to text", file=sys.stderr)

    ok = send_text(tok, chat, cap)
    print(f"  text fallback {'sent' if ok else 'FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
