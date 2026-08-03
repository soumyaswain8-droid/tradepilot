#!/usr/bin/env python3
"""
fleet-mobile-server — read-only fleet view for your phone, on the LAN.

WHY A SEPARATE PROCESS INSTEAD OF BINDING THE MAIN APP TO 0.0.0.0
The main Flask app on :5050 serves 60 routes. Exposing it to the network would
also expose /admin, /api/paper/buy, /api/trade/calculate and — worst — /kite/login
and /kite/callback. That callback WRITES CREDENTIALS TO .env, so anyone on the same
WiFi could drive your Zerodha auth flow. The 2026-07-24 hardening bound :5050 to
loopback for exactly this reason and that stays untouched.

This server exposes exactly ONE route, GET /, rendering the same fleet view. It has:
  - no write endpoints of any kind
  - no access to Kite, orders, or credentials
  - no API surface — it reads the engines' own JSON state files off disk
Worst case if someone on your network finds it: they see paper-trading P&L.

Run:
    python3 scripts/fleet-mobile-server.py            # LAN, port 5051
    python3 scripts/fleet-mobile-server.py --port 8080
    python3 scripts/fleet-mobile-server.py --loopback # localhost only

Then on your phone (same WiFi): http://<your-mac-lan-ip>:5051
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import socket
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "prototype"))

CPT = 14.30   # v5's measured cost/trade — corrects engines that book no costs


def lan_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"


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
        wins = sm.get("wins") or 0
        books = cost > 0
        true = net if (books and net is not None) else (gross - trades * CPT if not books else gross)
        cap = d.get("total_capital") or 0
        if cap <= 0:
            continue
        engines.append({"name": name, "cap": cap,
                        "tier": "1L" if 90000 <= cap <= 110000 else "10L",
                        "pos": npos, "trades": trades,
                        "wr": round(wins / trades * 100) if trades else 0,
                        "net": round(true)})
    engines.sort(key=lambda e: -e["net"])
    fleet = {"n": len(engines),
             "pos": sum(e["pos"] for e in engines),
             "trades": sum(e["trades"] for e in engines),
             "net": round(sum(e["net"] for e in engines)),
             "green": sum(1 for e in engines if e["net"] > 0)}
    return engines, fleet


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=5051)
    ap.add_argument("--loopback", action="store_true",
                    help="bind 127.0.0.1 only (no phone access)")
    a = ap.parse_args()

    from flask import Flask, render_template
    app = Flask(__name__, template_folder=str(ROOT / "prototype" / "templates"))

    @app.route("/")
    def index():
        engines, fleet = collect()
        mx = max([abs(e["net"]) for e in engines] or [1])
        return render_template("fleet.html", engines=engines, fleet=fleet, mx=mx,
                               stamp=datetime.now().strftime("%d %b %Y, %H:%M IST"))

    host = "127.0.0.1" if a.loopback else "0.0.0.0"
    ip = lan_ip()
    print("=" * 58)
    print("  TradePilot fleet — READ ONLY, no write endpoints")
    if a.loopback:
        print(f"  http://127.0.0.1:{a.port}   (loopback only)")
    else:
        print(f"  On this Mac : http://127.0.0.1:{a.port}")
        print(f"  On your phone: http://{ip}:{a.port}   (same WiFi)")
        print(f"  Reachable to anyone on your network — it shows paper P&L only.")
    print("=" * 58)
    app.run(host=host, port=a.port, debug=False, threaded=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
