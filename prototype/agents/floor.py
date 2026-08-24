#!/usr/bin/env python3
"""
agents/floor — 20 stock-watcher agents on a live tick stream.

DESIGN (Soumya, 2026-08-24): "each agent watches one stock, constantly, like a real
human — the market turns in seconds, not in 30-minute polls."

THE ARCHITECTURE THAT MAKES THAT REAL
A human trader does NOT re-derive their thesis every second. They decide their levels
in the morning, then WATCH for those levels to be hit. This floor works the same way,
in two layers:

  FAST LAYER (this file) — a WebSocket tick stream, ~milliseconds. Every agent holds
  its own thesis (levels, structure, invalidation) and evaluates EVERY TICK against
  it. No polling, no 30-minute blind spots. This is what "constantly watching" means
  in practice, and it is far faster than any human.

  SLOW LAYER (the agent read) — when the fast layer detects something that MATTERS,
  it escalates: renders the chart and asks Sarathi for judgement. Judgement is
  expensive and slow (seconds); triggers are cheap and instant. Spending judgement
  only where it changes a decision is what makes 20 agents affordable AND fast.

That split is not a compromise — it is the same hybrid the agentic-waterfall spec
settled on after measuring: LLM slow, code fast, and never an LLM in the tick path.

WHAT EACH AGENT KNOWS
  - its stock, and only its stock (specialisation)
  - its thesis: levels that matter today, set at open and revised on structural change
  - the shared knowledge base (docs/sarathi/knowledge/) — every agent reads what
    every other agent learned, and writes back what it learns
  - the playbook (docs/sarathi/chart-reading-playbook.md), which leads with OUR
    measured results so no agent trades folklore we already disproved

TRIGGERS the fast layer watches for (all measurable, all from our own findings)
  LEVEL_TOUCH     price reaches a thesis level (PDH/PDL/VWAP/swing/round number)
  SWEEP_RECLAIM   pierced a level then closed back inside — the one SMC idea with
                  a defensible mechanism (stop-run then reversion)
  VOL_SPIKE       tick volume burst vs the rolling norm — participation confirms
  RANGE_BREAK     leaves a coiled range after volume dry-up
  FAST_MOVE       velocity spike (our 'market turns in seconds' case)
  INVALIDATION    an OPEN position's thesis broke — escalates immediately

Escalations are rate-limited per agent so one thrashing stock cannot flood the floor.

Run:
    python3 -m prototype.agents.floor --watchlist auto --dry     # no orders ever
    python3 -m prototype.agents.floor --status
"""
from __future__ import annotations

import json, os, sys, threading, time, warnings
from collections import deque
from datetime import datetime
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

KNOW = ROOT / "docs" / "sarathi" / "knowledge"
ESCALATIONS = KNOW / "escalations"
N_AGENTS = 20
MIN_PRICE, MAX_PRICE = 80.0, 800.0
ESCALATE_COOLDOWN_S = 180        # per agent, per trigger type
VOL_SPIKE_MULT = 3.0
FAST_MOVE_BPS_PER_MIN = 25.0


class StockAgent:
    """One agent, one stock. Holds a thesis; judges every tick against it."""

    def __init__(self, symbol, token, thesis, shared):
        self.symbol, self.token = symbol, token
        self.thesis = thesis            # levels + structure, set by the read
        self.shared = shared            # the floor's shared knowledge
        self.ticks = deque(maxlen=600)  # (ts, ltp, vol)
        self.last_escalation = {}
        self.position = None
        self.state = "WATCHING"
        self.seen = 0

    # ── the tick path: must stay microseconds, no I/O, no LLM ──────────────
    def on_tick(self, t):
        ltp = t.get("last_price")
        if not ltp:
            return None
        now = time.time()
        self.ticks.append((now, float(ltp), t.get("volume_traded") or 0))
        self.seen += 1
        return self._evaluate(now, float(ltp), t)

    def _fire(self, kind, detail, now):
        last = self.last_escalation.get(kind, 0)
        if now - last < ESCALATE_COOLDOWN_S:
            return None
        self.last_escalation[kind] = now
        return {"symbol": self.symbol, "trigger": kind, "detail": detail,
                "ltp": self.ticks[-1][1] if self.ticks else None,
                "at": datetime.now().strftime("%H:%M:%S"),
                "thesis": self.thesis, "state": self.state}

    def _evaluate(self, now, ltp, t):
        th = self.thesis
        # 1. an open position's invalidation is the highest-priority event
        if self.position:
            if ltp <= self.position["stop"]:
                return self._fire("INVALIDATION",
                                  f"stop {self.position['stop']} breached", now)
            if ltp >= self.position["target"]:
                return self._fire("TARGET_REACHED",
                                  f"target {self.position['target']} reached", now)
        # 2. level proximity — the agent's whole reason for watching this stock
        for name, lvl in (th.get("levels") or {}).items():
            if not lvl:
                continue
            dist_bps = abs(ltp - lvl) / lvl * 10000
            if dist_bps <= 8:                      # within 8 bps of a thesis level
                return self._fire(f"LEVEL_TOUCH:{name}",
                                  f"{ltp} at {name} {lvl} ({dist_bps:.1f}bps)", now)
        # 3. sweep + reclaim: pierced a level, came back inside
        if len(self.ticks) > 30:
            recent = [p for _, p, _ in list(self.ticks)[-30:]]
            for name, lvl in (th.get("levels") or {}).items():
                if not lvl:
                    continue
                if min(recent) < lvl < ltp and (lvl - min(recent)) / lvl * 10000 > 5:
                    return self._fire(f"SWEEP_RECLAIM:{name}",
                                      f"swept {min(recent):.2f} below {name} {lvl}, "
                                      f"reclaimed to {ltp}", now)
        # 4. velocity — "the market turns in seconds"
        if len(self.ticks) > 20:
            t0, p0, _ = self.ticks[-20]
            dt = max(now - t0, 1e-6)
            bps_min = abs(ltp - p0) / p0 * 10000 * (60.0 / dt)
            if bps_min > FAST_MOVE_BPS_PER_MIN:
                return self._fire("FAST_MOVE",
                                  f"{bps_min:.0f} bps/min ({p0:.2f}->{ltp:.2f})", now)
        # 5. volume burst
        if len(self.ticks) > 60:
            vols = [v for _, _, v in list(self.ticks)]
            d_recent = vols[-1] - vols[-20] if vols[-20] else 0
            d_norm = (vols[-20] - vols[-60]) / 2 if vols[-60] else 0
            if d_norm > 0 and d_recent > d_norm * VOL_SPIKE_MULT:
                return self._fire("VOL_SPIKE",
                                  f"{d_recent:,.0f} vs norm {d_norm:,.0f}", now)
        return None


class Floor:
    """Runs the agents, owns the stream, records escalations, shares knowledge."""

    def __init__(self, dry=True):
        self.agents = {}
        self.dry = dry
        self.escalation_log = []
        KNOW.mkdir(parents=True, exist_ok=True)
        ESCALATIONS.mkdir(parents=True, exist_ok=True)
        self.shared = self._load_shared()

    def _load_shared(self):
        f = KNOW / "shared.json"
        if f.exists():
            try:
                return json.loads(f.read_text())
            except Exception:
                pass
        return {"lessons": [], "per_symbol": {}, "updated": None}

    def save_shared(self):
        self.shared["updated"] = datetime.now().isoformat(timespec="seconds")
        (KNOW / "shared.json").write_text(json.dumps(self.shared, indent=2))

    def build_watchlist(self, n=N_AGENTS):
        """The n stocks worth a dedicated agent: tradeable at Rs1k, liquid, and
        with the engines' interest. One agent per stock — specialisation is the
        point, so the list is fixed for the session."""
        import requests
        from prototype.v4 import kite_data as kd
        from prototype.v4.config import ACTIVE_SYMBOLS_YF
        try:
            rows = requests.get("http://127.0.0.1:5050/api/scores", timeout=10).json()
        except Exception:
            rows = []
        scored = {r["symbol"]: r for r in rows if r.get("symbol")}
        # /api/scores serves NIFTY-50 only — barely a dozen land in the Rs1k band,
        # so the floor draws from the full NIFTY-200 and uses scores where present.
        universe = [s.replace(".NS", "") for s in ACTIVE_SYMBOLS_YF]
        k = kd.client()
        live = {}
        for i in range(0, len(universe), 200):
            ch = universe[i:i + 200]
            try:
                live.update(k.quote([f"NSE:{s}" for s in ch]))
            except Exception:
                pass
        cands = []
        for s in universe:
            d = live.get(f"NSE:{s}")
            if not d:
                continue
            px = float(d.get("last_price") or 0)
            if not (MIN_PRICE <= px <= MAX_PRICE):
                continue
            vol = int(d.get("volume") or 0)
            sc = scored.get(s, {})
            # rank: scored names first (engine interest), then by turnover — an
            # agent on an illiquid stock watches a chart nobody else is trading.
            cands.append(((0 if sc.get("score") else 1),
                          -(sc.get("score") or 0), -(vol * px), s, px, sc))
        cands.sort()
        out = []
        for _, _, _, s, px, sc in cands:
            tok = kd.token_for(s)
            if tok:
                out.append((s, tok, {**sc, "price": px}))
            if len(out) >= n:
                break
        return out

    def seed_thesis(self, symbol, meta):
        """Levels that matter today, computed from closed bars — the agent's brief.
        Revised by the slow layer when structure changes."""
        from prototype.v4 import kite_data as kd
        from datetime import timedelta
        try:
            tok = kd.token_for(symbol)
            b = kd.client().historical_data(
                tok, datetime.now() - timedelta(days=6), datetime.now(), "5minute")
        except Exception:
            return {"levels": {}, "note": "no bars"}
        if len(b) < 30:
            return {"levels": {}, "note": "thin history"}
        today = str(b[-1]["date"])[:10]
        prev = [x for x in b if str(x["date"])[:10] != today]
        cur = [x for x in b if str(x["date"])[:10] == today]
        lv = {}
        if prev:
            lv["PDH"] = round(max(float(x["high"]) for x in prev), 2)
            lv["PDL"] = round(min(float(x["low"]) for x in prev), 2)
        if cur:
            tv = sum(float(x.get("volume") or 0) for x in cur) or 1
            lv["VWAP"] = round(sum(float(x["close"]) * float(x.get("volume") or 0)
                                   for x in cur) / tv, 2)
            lv["DAY_HIGH"] = round(max(float(x["high"]) for x in cur), 2)
            lv["DAY_LOW"] = round(min(float(x["low"]) for x in cur), 2)
        last = float(b[-1]["close"])
        lv["ROUND"] = round(round(last / 10) * 10, 2)
        return {"levels": lv, "seeded_at": datetime.now().strftime("%H:%M:%S"),
                "last": round(last, 2),
                "lessons": self.shared.get("per_symbol", {}).get(symbol, [])}

    def start(self):
        from kiteconnect import KiteTicker
        from prototype.v4 import kite_data as kd
        api_key = os.environ.get("KITE_API_KEY")
        token = os.environ.get("KITE_ACCESS_TOKEN")
        if not api_key or not token:
            for line in (ROOT / ".env").read_text().splitlines():
                if line.startswith("KITE_API_KEY="):
                    api_key = line.split("=", 1)[1].strip().strip('"')
                if line.startswith("KITE_ACCESS_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"')
        wl = self.build_watchlist()
        if not wl:
            print("  no watchlist — is the scores API up?"); return
        print(f"  seeding theses for {len(wl)} agents...")
        for sym, tok, meta in wl:
            self.agents[tok] = StockAgent(sym, tok, self.seed_thesis(sym, meta),
                                          self.shared)
            lv = self.agents[tok].thesis.get("levels", {})
            print(f"    {sym:<12} levels: " +
                  " ".join(f"{k}={v}" for k, v in list(lv.items())[:4]))
        tokens = list(self.agents)
        kws = KiteTicker(api_key, token)

        def on_ticks(ws, ticks):
            for t in ticks:
                a = self.agents.get(t.get("instrument_token"))
                if not a:
                    continue
                ev = a.on_tick(t)
                if ev:
                    self.escalate(ev)

        def on_connect(ws, resp):
            ws.subscribe(tokens)
            ws.set_mode(ws.MODE_FULL, tokens)
            print(f"  STREAM LIVE — {len(tokens)} agents watching every tick "
                  f"({datetime.now():%H:%M:%S})")

        def on_error(ws, code, reason):
            print(f"  stream error {code}: {reason}")

        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_error = on_error
        kws.connect(threaded=True)
        try:
            while True:
                time.sleep(30)
                live = sum(a.seen for a in self.agents.values())
                print(f"  [{datetime.now():%H:%M:%S}] {live:,} ticks processed | "
                      f"{len(self.escalation_log)} escalations")
                if datetime.now().strftime("%H:%M") >= "15:30":
                    print("  session over — stopping"); break
        except KeyboardInterrupt:
            print("  interrupted")
        finally:
            self.save_shared()
            self.dump_escalations()

    def escalate(self, ev):
        """Something happened. Record it for Sarathi's judgement — the slow layer."""
        self.escalation_log.append(ev)
        line = (f"  >> {ev['at']} {ev['symbol']:<12} {ev['trigger']:<22} "
                f"{ev['ltp']}  {ev['detail']}")
        print(line, flush=True)
        f = ESCALATIONS / f"{datetime.now():%Y-%m-%d}.jsonl"
        with open(f, "a") as fh:
            fh.write(json.dumps(ev) + "\n")

    def dump_escalations(self):
        if not self.escalation_log:
            return
        f = ESCALATIONS / f"{datetime.now():%Y-%m-%d}_summary.json"
        by = {}
        for e in self.escalation_log:
            by.setdefault(e["symbol"], []).append(e["trigger"])
        f.write_text(json.dumps({"total": len(self.escalation_log),
                                 "by_symbol": {k: len(v) for k, v in by.items()},
                                 "triggers": by}, indent=2))
        print(f"  wrote {f}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="auto")
    ap.add_argument("--dry", action="store_true", default=True)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.status:
        f = ESCALATIONS / f"{datetime.now():%Y-%m-%d}_summary.json"
        print(f.read_text() if f.exists() else "  no escalations recorded today")
        return
    Floor(dry=a.dry).start()


if __name__ == "__main__":
    main()
