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

# ── dynamic reassignment (Soumya, 2026-08-24) ────────────────────────────────
# "Do not look at these 20 stocks only — the moto is to make profit, so we cannot
#  miss any stock that is good to trade."
# A fixed watchlist can only be as good as 09:16's information. The scout team
# (agents/scouts.py) sweeps all ~889 liquid names every minute and the floor moves
# its watchers to whatever is actually worth watching.
REBALANCE_EVERY_S = 120
SWAP_MARGIN = 0.15          # a challenger must beat the incumbent by this much
MIN_TENURE_S = 600          # an agent must hold a stock this long before a swap
MAX_SWAPS_PER_CYCLE = 4     # never churn the whole floor at once


def in_session_now(now=None):
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return (9 * 60 + 15) <= m < (15 * 60 + 30)


def displaces(cand, incumbent_score, incumbent_agree):
    """Does this challenger earn an incumbent's seat?

    Two ways in, and the first one exists because the score arithmetic alone got it
    wrong. Measured on the real board 2026-08-24: the weakest incumbent scored 0.635
    on 2 scouts, so the margin bar was 0.785 — while a MARGINAL three-scout name
    scores 0.776. A fresh three-way confluence, the strongest signal we measure,
    would have been rejected by nine thousandths.

    So state the rule instead of approximating it: MORE INDEPENDENT LENSES AGREEING
    WINS. That is the one finding that survived falsification (edge rose monotonically
    with agreeing predicates), and it should not be re-derived from a weighted sum
    that can round it away.
    """
    if cand["agree"] > incumbent_agree:
        return True, "more scouts agree (%d vs %d)" % (cand["agree"], incumbent_agree)
    if cand["score"] >= incumbent_score + SWAP_MARGIN:
        return True, "score %+.3f over incumbent" % (cand["score"] - incumbent_score)
    return False, ""


class StockAgent:
    """One agent, one stock. Holds a thesis; judges every tick against it."""

    def __init__(self, symbol, token, thesis, shared, scout=None):
        self.symbol, self.token = symbol, token
        self.thesis = thesis            # levels + structure, set by the read
        self.shared = shared            # the floor's shared knowledge
        self.ticks = deque(maxlen=600)  # (ts, ltp, vol)
        self.last_escalation = {}
        self.position = None
        self.state = "WATCHING"
        self.seen = 0
        self.scout = scout or {}        # why the scouts sent this stock here
        self.assigned_at = time.time()

    @property
    def tenure_s(self):
        return time.time() - self.assigned_at

    def can_be_reassigned(self):
        """An agent is only movable when it has nothing at stake and has had a fair
        look. Both halves matter:
          - holding a position is absolute — walking away from an open trade to watch
            something shinier is how a floor loses money it already committed;
          - the tenure floor exists because the deepest triggers need history.
            SWEEP_RECLAIM reads 30 ticks and VOL_SPIKE reads 60, so an agent churned
            every minute could NEVER fire its two most valuable signals — it would be
            permanently re-seeded into blindness.
        """
        return self.position is None and self.tenure_s >= MIN_TENURE_S

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

    def __init__(self, dry=True, verbose=False):
        self.agents = {}
        self.dry = dry
        self.verbose = verbose
        self.escalation_log = []
        self.scouts = None
        self.kws = None
        self.swap_log = []
        self.near_miss_log = []
        self.gaps = []
        self.gap_open = None
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

    def scout_board(self, n=N_AGENTS, depth=3):
        """Ask the scout team what is worth watching right now.

        Asks for more than n: the extras are the bench. When the top pick is already
        being watched — the common case on a rebalance — the floor needs the next
        names down to have anything to move an idle agent to.
        """
        from prototype.agents.scouts import ScoutTeam
        if self.scouts is None:
            self.scouts = ScoutTeam(verbose=self.verbose)
            print(f"  scouts: 4 lenses over {len(self.scouts.universe)} liquid names "
                  f"({self.scouts.dropped_etf} ETFs/funds excluded)")
        return self.scouts.scan(top=n * depth)

    def build_watchlist(self, n=N_AGENTS):
        """The opening assignment: the scouts' top n that we can actually get a
        tradeable token for."""
        from prototype.v4 import kite_data as kd
        out = []
        for b in self.scout_board(n):
            tok = kd.token_for(b["symbol"])
            if tok:
                out.append((b["symbol"], tok, b))
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

    def seed_only(self):
        """Everything the live floor does except the stream — so the scout board,
        thesis seeding and the swap brakes can all be exercised outside market
        hours, when a real run is impossible."""
        wl = self.build_watchlist()
        if not wl:
            print("  no watchlist — scouts returned nothing"); return
        print(f"\n  ASSIGNED {len(wl)} AGENTS")
        for sym, tok, meta in wl:
            self.agents[tok] = StockAgent(sym, tok, self.seed_thesis(sym, meta),
                                          self.shared, scout=meta)
            lv = self.agents[tok].thesis.get("levels", {})
            print(f"    {sym:<13}[{meta.get('agree',0)} scouts {meta.get('score',0):.2f}] "
                  + " ".join(f"{k}={v}" for k, v in list(lv.items())[:4]))
        print("\n  REBALANCE DRY-RUN")
        movable = [a for a in self.agents.values() if a.can_be_reassigned()]
        print(f"    movable now: {len(movable)}/{len(self.agents)} "
              f"(tenure floor is {MIN_TENURE_S}s — everything was just assigned, "
              f"so a swap correctly cannot happen yet)")
        n = self.rebalance()
        print(f"    swaps executed: {n}")

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
            print("  no watchlist — scouts returned nothing"); return
        print(f"  seeding theses for {len(wl)} agents...")
        for sym, tok, meta in wl:
            self.agents[tok] = StockAgent(sym, tok, self.seed_thesis(sym, meta),
                                          self.shared, scout=meta)
            lv = self.agents[tok].thesis.get("levels", {})
            print(f"    {sym:<12} [{meta.get('agree', 0)} scouts, "
                  f"{meta.get('score', 0):.2f}] " +
                  " ".join(f"{k}={v}" for k, v in list(lv.items())[:3]))
        kws = KiteTicker(api_key, token)
        self.kws = kws

        def on_ticks(ws, ticks):
            for t in ticks:
                a = self.agents.get(t.get("instrument_token"))
                if not a:
                    continue
                ev = a.on_tick(t)
                if ev:
                    self.escalate(ev)

        def on_connect(ws, resp):
            # read the roster live, not from a captured list — after a reassignment
            # a reconnect would otherwise resubscribe stocks nobody is watching and
            # leave the newly assigned ones silent.
            toks = list(self.agents)
            ws.subscribe(toks)
            ws.set_mode(ws.MODE_FULL, toks)
            print(f"  STREAM LIVE — {len(toks)} agents watching every tick "
                  f"({datetime.now():%H:%M:%S})")

        def on_error(ws, code, reason):
            print(f"  [{datetime.now():%H:%M:%S}] stream error {code}: {reason}",
                  flush=True)

        def on_close(ws, code, reason):
            self.note_gap("CLOSE", f"{code}: {reason}")

        def on_reconnect(ws, attempt):
            print(f"  [{datetime.now():%H:%M:%S}] reconnecting (attempt {attempt})",
                  flush=True)

        def on_noreconnect(ws):
            self.note_gap("GAVE_UP", "reconnect attempts exhausted")

        kws.on_ticks = on_ticks
        kws.on_connect = on_connect
        kws.on_error = on_error
        kws.on_close = on_close
        kws.on_reconnect = on_reconnect
        kws.on_noreconnect = on_noreconnect
        # The link is unreliable today (Soumya, 2026-08-25). Be explicit rather than
        # relying on library defaults: keep retrying all session, with backoff.
        kws.connect(threaded=True, disable_ssl_verification=False)
        last_rebalance = time.time()
        last_seen_total = 0
        try:
            while True:
                time.sleep(30)
                live = sum(a.seen for a in self.agents.values())
                held = sum(1 for a in self.agents.values() if a.position)
                # DATA GAP DETECTION. A dead link and a silent market look identical
                # from in here: ticks simply stop arriving. Unrecorded, that turns
                # today's escalation count — the one number this run exists to
                # produce — into a figure nobody can interpret. So the absence of
                # ticks is logged as a positive fact, not left as an absence.
                if live == last_seen_total and in_session_now():
                    self.note_gap("NO_TICKS", f"no ticks in 30s (total {live:,})")
                elif self.gap_open:
                    self.close_gap(live)
                last_seen_total = live
                print(f"  [{datetime.now():%H:%M:%S}] {live:,} ticks | "
                      f"{len(self.escalation_log)} escalations | "
                      f"{len(self.swap_log)} reassignments | {held} in position | "
                      f"{len(self.gaps)} data gaps", flush=True)
                if datetime.now().strftime("%H:%M") >= "15:30":
                    print("  session over — stopping"); break
                # the scouts keep sweeping; the floor follows them
                if time.time() - last_rebalance >= REBALANCE_EVERY_S:
                    last_rebalance = time.time()
                    self.rebalance()
        except KeyboardInterrupt:
            print("  interrupted")
        finally:
            self.save_shared()
            self.dump_escalations()

    # ── data-gap ledger ──────────────────────────────────────────────────────
    def note_gap(self, kind, detail):
        """Record that we were BLIND, and for how long.

        Carries forward the DATA-GUARD lesson from the July outage: when the feed
        dies, every downstream artefact still renders — it just renders emptiness.
        An escalation count of 3 means one thing if the stream ran all day and
        something entirely different if we were disconnected for two hours, and
        nothing in the output distinguishes them unless the blindness is written
        down at the time.
        """
        now = datetime.now()
        if self.gap_open:
            return                      # already inside a gap; wait for it to close
        self.gap_open = {"kind": kind, "detail": detail,
                         "from": now.strftime("%H:%M:%S"), "t0": time.time()}
        print(f"  !! {now:%H:%M:%S} DATA GAP OPENED ({kind}): {detail}", flush=True)

    def close_gap(self, tick_total):
        g = self.gap_open
        if not g:
            return
        dur = round(time.time() - g["t0"], 1)
        g.update({"to": datetime.now().strftime("%H:%M:%S"), "seconds": dur,
                  "ticks_at_recovery": tick_total})
        g.pop("t0", None)
        self.gaps.append(g)
        self.gap_open = None
        print(f"  ++ {datetime.now():%H:%M:%S} DATA GAP CLOSED after {dur}s "
              f"— ticks flowing again", flush=True)

    # ── dynamic reassignment ─────────────────────────────────────────────────
    def rebalance(self):
        """Move idle agents onto whatever the scouts now rank highest.

        Three brakes, and each one prevents a specific failure:
          SWAP_MARGIN         a challenger must clearly beat the incumbent, or the
                              floor thrashes between names of equal merit;
          MAX_SWAPS_PER_CYCLE at most a few move per cycle, so a single odd sweep
                              cannot empty the floor of every settled agent;
          can_be_reassigned() never abandons an open position, never churns an agent
                              before it has the tick history its triggers need.
        """
        from prototype.v4 import kite_data as kd
        try:
            board = self.scout_board()
        except Exception as e:
            print(f"  rebalance skipped — scout sweep failed: {str(e)[:80]}")
            return 0
        if not board:
            return 0
        watching = {a.symbol for a in self.agents.values()}
        challengers = [b for b in board if b["symbol"] not in watching]
        if not challengers:
            return 0
        movable = sorted((a for a in self.agents.values() if a.can_be_reassigned()),
                         key=lambda a: (a.scout.get("agree", 0),
                                        a.scout.get("score", 0)))
        swaps, near_misses = 0, []
        for cand in challengers:
            if swaps >= MAX_SWAPS_PER_CYCLE or not movable:
                break
            weakest = movable[0]
            ok, why_swap = displaces(cand, weakest.scout.get("score", 0),
                                     weakest.scout.get("agree", 0))
            if not ok:
                # Record what ALMOST cleared. Whether these brakes are set right is
                # an empirical question we cannot answer by reasoning about it — the
                # near-miss trail is how tomorrow's log tells us, instead of us
                # guessing again.
                near_misses.append({
                    "cand": cand["symbol"], "cand_score": cand["score"],
                    "cand_agree": cand["agree"], "vs": weakest.symbol,
                    "inc_score": round(weakest.scout.get("score", 0), 3),
                    "inc_agree": weakest.scout.get("agree", 0),
                    "short_by": round(weakest.scout.get("score", 0) + SWAP_MARGIN
                                      - cand["score"], 3)})
                continue
            tok = kd.token_for(cand["symbol"])
            if not tok or tok in self.agents:
                continue
            old_tok, old_sym = weakest.token, weakest.symbol
            try:
                new_agent = StockAgent(cand["symbol"], tok,
                                       self.seed_thesis(cand["symbol"], cand),
                                       self.shared, scout=cand)
            except Exception as e:
                print(f"  could not seed {cand['symbol']}: {str(e)[:60]}")
                continue
            del self.agents[old_tok]
            self.agents[tok] = new_agent
            if self.kws:
                try:
                    self.kws.unsubscribe([old_tok])
                    self.kws.subscribe([tok])
                    self.kws.set_mode(self.kws.MODE_FULL, [tok])
                except Exception as e:
                    print(f"  stream reassign warning: {str(e)[:60]}")
            movable.pop(0)
            swaps += 1
            rec = {"at": datetime.now().strftime("%H:%M:%S"),
                   "out": old_sym, "out_score": round(weakest.scout.get("score", 0), 3),
                   "out_agree": weakest.scout.get("agree", 0),
                   "in": cand["symbol"], "in_score": cand["score"],
                   "agree": cand["agree"], "rule": why_swap, "why": cand["why"],
                   # the price at swap time, both sides — this is what makes the
                   # end-of-day question answerable: did the stock we moved TO
                   # actually move more than the one we left?
                   "in_px": cand.get("ltp"),
                   "out_px": weakest.ticks[-1][1] if weakest.ticks else None}
            self.swap_log.append(rec)
            print(f"  ~~ {rec['at']} REASSIGN {old_sym} ({rec['out_score']}, "
                  f"{rec['out_agree']} scouts) -> {cand['symbol']} ({cand['score']}, "
                  f"{cand['agree']} scouts) — {why_swap}", flush=True)
            print(f"       {cand['why']}", flush=True)
        if near_misses:
            self.near_miss_log.extend(near_misses)
            best = min(near_misses, key=lambda x: x["short_by"])
            print(f"     ({len(near_misses)} near-misses, closest: {best['cand']} "
                  f"short by {best['short_by']})", flush=True)
        return swaps

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
        if not self.escalation_log and not self.swap_log:
            return
        f = ESCALATIONS / f"{datetime.now():%Y-%m-%d}_summary.json"
        by = {}
        for e in self.escalation_log:
            by.setdefault(e["symbol"], []).append(e["trigger"])
        f.write_text(json.dumps({
            "total": len(self.escalation_log),
            "by_symbol": {k: len(v) for k, v in by.items()},
            "triggers": by,
            # the reassignment trail is its own evidence: at EOD we can ask whether
            # the stocks the scouts swapped IN actually moved more than the ones they
            # swapped OUT. That is the only honest test of whether scouting pays.
            "reassignments": self.swap_log,
            # if this list is long and the reassignment list is empty, the brakes are
            # too tight; if reassignments churn and escalations stay flat, too loose.
            # blindness is reported as loudly as activity — see note_gap()
            "data_gaps": self.gaps + ([self.gap_open] if self.gap_open else []),
            "blind_seconds": round(sum(g.get("seconds", 0) for g in self.gaps), 1),
            "near_misses": self.near_miss_log[-200:],
            "near_miss_total": len(self.near_miss_log),
            "watched_at_close": sorted(a.symbol for a in self.agents.values()),
        }, indent=2))
        print(f"  wrote {f}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--watchlist", default="auto")
    ap.add_argument("--dry", action="store_true", default=True)
    ap.add_argument("--status", action="store_true")
    ap.add_argument("--seed-only", action="store_true",
                    help="scout, seed 20 theses, run one rebalance — no stream")
    a = ap.parse_args()
    if a.status:
        f = ESCALATIONS / f"{datetime.now():%Y-%m-%d}_summary.json"
        print(f.read_text() if f.exists() else "  no escalations recorded today")
        return
    if a.seed_only:
        Floor(dry=True, verbose=True).seed_only()
        return
    Floor(dry=a.dry).start()


if __name__ == "__main__":
    main()
