#!/usr/bin/env python3
"""
A/B Live Dashboard — side-by-side comparison of live engines vs A/B variants.
  v4: LIVE (1,735-tree) vs A/B OLD (5-tree pre-May-4)
  v5: LIVE (with shorts) vs A/B LONG-ONLY
Pure stdlib. Run:  python3 ab_dashboard.py   ->  http://localhost:8899
"""
import json, datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

PORT = 8899
HOME = Path.home() / "Documents/tinker/projects"
SOURCES = [
    ("v4", "LIVE v4 (1,735-tree)", HOME/"tradepilot/docs/paper-trades/v4", "live"),
    ("v4", "A/B OLD v4 (5-tree)",  HOME/"tradepilot-oldengine-ab/docs/paper-trades/v4", "ab"),
    ("v5", "LIVE v5 (with shorts)",HOME/"tradepilot/docs/paper-trades/v5", "live"),
    ("v5", "A/B v5 LONG-ONLY",     HOME/"tradepilot-v5-longonly-ab/docs/paper-trades/v5", "ab"),
]

def today():
    return datetime.date.today().isoformat()

def read_engine(engine, label, base, kind):
    rec = {"engine": engine, "label": label, "kind": kind, "exists": False,
           "pnl": 0, "trades": 0, "wins": 0, "win_rate": None, "closed_n": 0, "open_n": 0,
           "longs": 0, "shorts": 0, "started": "-", "deployed": 0, "regime": "-"}
    f = base / f"{today()}.json"
    if not f.exists():
        return rec
    try:
        d = json.loads(f.read_text())
    except Exception:
        return rec  # mid-write; keep zeros, exists stays False
    rec["exists"] = True
    rec["started"] = d.get("started_at", "-")
    if engine == "v4":
        pos = d.get("positions", [])
        closed = [p for p in pos if p.get("status") != "open"]
        rec["pnl"] = d.get("realized_pnl", 0) or 0
        rec["closed_n"] = len(closed)
        rec["open_n"] = len(pos) - len(closed)
        rec["trades"] = len(pos)
        rec["wins"] = sum(1 for p in closed if (p.get("pnl") or 0) > 0)
        rec["longs"] = sum(1 for p in pos if p.get("v4_direction") == "BUY")
        rec["shorts"] = sum(1 for p in pos if p.get("v4_direction") == "SELL")
        rec["deployed"] = d.get("total_deployed", 0) or 0
        rec["regime"] = ("BEAR" if d.get("bear_mode") else "") + (" VIX-HI" if d.get("vix_high_mode") else "") or "-"
    else:  # v5
        s = d.get("summary", {})
        rec["pnl"] = s.get("total_pnl", 0) or 0
        rec["closed_n"] = s.get("trades", 0)
        rec["open_n"] = sum(len(p.get("positions", [])) for p in d.get("pools", {}).values())
        rec["trades"] = s.get("trades", 0)
        rec["wins"] = s.get("wins", 0)
        rec["longs"] = s.get("longs", 0)
        rec["shorts"] = s.get("shorts", 0)
        rec["regime"] = d.get("regime", "-")
    if rec["closed_n"]:
        rec["win_rate"] = round(100 * rec["wins"] / rec["closed_n"])
    return rec

def build_data():
    recs = [read_engine(*s) for s in SOURCES]
    return {"updated": datetime.datetime.now().strftime("%H:%M:%S"), "date": today(), "engines": recs}

HTML = """<!doctype html><html><head><meta charset="utf-8"><title>TradePilot A/B Live</title>
<style>
 body{background:#0d1117;color:#e6edf3;font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;margin:0;padding:24px}
 h1{font-size:18px;font-weight:600;margin:0 0 4px}
 .sub{color:#7d8590;font-size:12px;margin-bottom:20px}
 .pair{display:grid;grid-template-columns:1fr 1fr 110px;gap:14px;margin-bottom:18px;align-items:stretch}
 .ttl{grid-column:1/-1;font-size:13px;font-weight:600;color:#58a6ff;letter-spacing:.04em;text-transform:uppercase;margin:6px 0 2px}
 .card{background:#161b22;border:1px solid #30363d;border-radius:10px;padding:16px}
 .card .name{font-size:12px;color:#7d8590;margin-bottom:10px}
 .pnl{font-size:30px;font-weight:700;letter-spacing:-.02em}
 .pos{color:#3fb950}.neg{color:#f85149}.zero{color:#7d8590}
 .row{display:flex;gap:16px;margin-top:10px;flex-wrap:wrap}
 .stat{font-size:12px;color:#aeb6bf}.stat b{color:#e6edf3;font-weight:600}
 .delta{display:flex;flex-direction:column;justify-content:center;align-items:center;background:#161b22;border:1px solid #30363d;border-radius:10px;padding:8px}
 .delta .d{font-size:18px;font-weight:700}.delta .l{font-size:10px;color:#7d8590;text-transform:uppercase}
 .wait{color:#7d8590;font-style:italic;font-size:13px;padding:8px 0}
 .badge{display:inline-block;font-size:10px;padding:1px 6px;border-radius:4px;background:#21262d;color:#7d8590;margin-left:6px}
 .gateok{background:#0f2f1a;color:#3fb950}.gatebad{background:#3d1418;color:#f85149}
 .dot{height:8px;width:8px;border-radius:50%;background:#3fb950;display:inline-block;margin-right:6px;animation:p 2s infinite}
 @keyframes p{50%{opacity:.3}}
</style></head><body>
<h1>TradePilot — A/B Live <span class="badge" id="date"></span></h1>
<div class="sub"><span class="dot"></span>auto-refresh 10s · last update <b id="upd">—</b></div>
<div id="root"></div>
<script>
function inr(n){const s=n<0?'-':(n>0?'+':'');return s+'₹'+Math.abs(Math.round(n)).toLocaleString('en-IN')}
function cls(n){return n>0?'pos':(n<0?'neg':'zero')}
function card(e){
  if(!e.exists) return `<div class="card"><div class="name">${e.label}</div><div class="wait">waiting for engine…</div></div>`;
  let gate='';
  if(e.label.includes('LONG-ONLY')) gate = e.shorts===0?'<span class="badge gateok">gate OK · 0 shorts</span>':'<span class="badge gatebad">GATE FAIL · '+e.shorts+' shorts</span>';
  return `<div class="card"><div class="name">${e.label}${gate}</div>
    <div class="pnl ${cls(e.pnl)}">${inr(e.pnl)} <span style="font-size:11px;color:#7d8590;font-weight:400">realized</span></div>
    <div class="row">
      <span class="stat">Closed <b>${e.closed_n}</b> · Open <b>${e.open_n}</b></span>
      <span class="stat">Win <b>${e.win_rate==null?'-':e.win_rate+'%'}</b></span>
      <span class="stat">L/S <b>${e.longs}/${e.shorts}</b></span>
      <span class="stat">Regime <b>${e.regime}</b></span>
      <span class="stat">Start <b>${e.started}</b></span>
    </div></div>`;
}
function pair(title, live, ab){
  let d='', dl='';
  if(live.exists && ab.exists){ const diff=ab.pnl-live.pnl; d=`<div class="d ${cls(diff)}">${inr(diff)}</div><div class="l">A/B − live</div>`; }
  else { d='<div class="l">—</div>'; }
  return `<div class="ttl">${title}</div><div class="pair">${card(live)}${card(ab)}<div class="delta">${d}</div></div>`;
}
async function tick(){
  try{
    const r=await fetch('/api/data'); const j=await r.json();
    document.getElementById('upd').textContent=j.updated;
    document.getElementById('date').textContent=j.date;
    const e=j.engines;
    document.getElementById('root').innerHTML =
      pair('v4 — live 1,735-tree vs A/B old 5-tree', e[0], e[1]) +
      pair('v5 — live (shorts) vs A/B long-only', e[2], e[3]);
  }catch(err){ document.getElementById('upd').textContent='error'; }
}
tick(); setInterval(tick, 10000);
</script></body></html>"""

class H(BaseHTTPRequestHandler):
    def log_message(self, *a): pass
    def do_GET(self):
        if self.path.startswith("/api/data"):
            body = json.dumps(build_data()).encode()
            self.send_response(200); self.send_header("Content-Type","application/json")
            self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)
        else:
            body = HTML.encode()
            self.send_response(200); self.send_header("Content-Type","text/html")
            self.send_header("Content-Length",str(len(body))); self.end_headers(); self.wfile.write(body)

if __name__ == "__main__":
    print(f"A/B dashboard -> http://localhost:{PORT}  (Ctrl-C to stop)")
    HTTPServer(("127.0.0.1", PORT), H).serve_forever()
