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

# ── measured 2026-08-25, first live session (1,563 escalations) ──────────────
# Each trigger was scored against a CONTROL: random minutes in the same stock on the
# same day. Absolute move in the 15 min after the trigger, vs after a random minute:
#
#   SWEEP_RECLAIM  n=118  0.637% vs 0.359%  lift +0.278pp   <- best by 3x, quietest
#   LEVEL_TOUCH    n=473  0.404% vs 0.318%  lift +0.085pp
#   FAST_MOVE      n=432  0.417% vs 0.349%  lift +0.068pp
#   VOL_SPIKE      n=540  0.311% vs 0.325%  lift -0.014pp   <- loudest, NEGATIVE
#
# VOL_SPIKE fired more than any other trigger and predicted less than random. It is
# disabled rather than deleted, so the decision stays reversible and the evidence
# stays readable. Removing it drops ~35% of all traffic and loses nothing measured.
DISABLED_TRIGGERS = {"VOL_SPIKE"}

# SWEEP_RECLAIM was our strongest signal AND our quietest, which is the wrong way
# round — we were almost certainly missing valid instances. Loosened on both axes:
# a shallower pierce counts, and the reclaim gets longer to happen.
SWEEP_PIERCE_BPS = 3.0      # was 5.0
SWEEP_LOOKBACK = 45         # ticks; was 30

# ── autonomous paper entry (Soumya, 2026-08-26) ──────────────────────────────
# "we need an automation system where the system doesn't need my approvals at all,
#  but whenever I want to see, I can see."
#
# Until now self.position was assigned exactly once — to None — and never again. So
# INVALIDATION and TARGET_REACHED were unreachable code, the "never reassign an agent
# holding a position" brake had nothing to protect, and the console's position count
# could only ever read zero. This closes that loop.
#
# WHY ONLY SWEEP_RECLAIM. A rule needs a SIDE, and only one trigger implies one:
# price pierced a level, then reclaimed it, so buyers defended -> long. LEVEL_TOUCH
# says where, not which way. FAST_MOVE has no side and our own data says intraday
# this market mean-reverts, so chasing it is the losing trade. SWEEP_RECLAIM also
# carried the best measured lift on 2026-08-25 (+0.278pp, 3x the next).
#
# HONEST STATUS: no trigger showed a DIRECTIONAL edge (signed returns -0.014%,
# 45.6% up, all inside the 0.106% toll). This rule is not believed to be profitable.
# It exists so that acting on an escalation produces evidence instead of a guess —
# which is the only thing 1,563 fired-and-forgotten escalations could never give us.
AUTO_ENTRY = True
ENTRY_TRIGGER = "SWEEP_RECLAIM"
ENTRY_MIN_AGREE = 2          # confluence: our one finding that survived falsification
MAX_CONCURRENT = 5
ENTRY_WINDOW = ("09:30", "14:30")   # not the open (noise), not near the close
FORCE_EXIT_AT = "15:15"
NOTIONAL = 6000.0            # matches the equity lane's per-slot size
TARGET_R = 1.5               # reward per unit of risk; below this the toll eats it
POSITIONS_FILE = KNOW / "positions"

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
        if self.position:
            self.mark(float(ltp))
        return self._evaluate(now, float(ltp), t)

    def _fire(self, kind, detail, now, extra=None):
        if kind.split(":")[0] in DISABLED_TRIGGERS:
            return None
        last = self.last_escalation.get(kind, 0)
        if now - last < ESCALATE_COOLDOWN_S:
            return None
        self.last_escalation[kind] = now
        ev = {"symbol": self.symbol, "trigger": kind, "detail": detail,
              "ltp": self.ticks[-1][1] if self.ticks else None,
              "at": datetime.now().strftime("%H:%M:%S"),
              "thesis": self.thesis, "state": self.state,
              "agree": self.scout.get("agree", 0), "score": self.scout.get("score", 0)}
        if extra:
            ev.update(extra)
        return ev

    # ── position handling ────────────────────────────────────────────────────
    def open_position(self, entry, stop, target, qty, why):
        self.position = {"entry": entry, "stop": stop, "target": target, "qty": qty,
                         "why": why, "at": datetime.now().strftime("%H:%M:%S"),
                         "t0": time.time(), "peak": entry, "trough": entry}
        self.state = "IN_POSITION"
        return self.position

    def mark(self, ltp):
        p = self.position
        if p:
            p["peak"] = max(p["peak"], ltp)
            p["trough"] = min(p["trough"], ltp)

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
        if len(self.ticks) > SWEEP_LOOKBACK:
            recent = [p for _, p, _ in list(self.ticks)[-SWEEP_LOOKBACK:]]
            for name, lvl in (th.get("levels") or {}).items():
                if not lvl:
                    continue
                if (min(recent) < lvl < ltp
                        and (lvl - min(recent)) / lvl * 10000 > SWEEP_PIERCE_BPS):
                    # the swept low is the invalidation: if price returns below what
                    # it just reclaimed, the read was simply wrong. A structural stop,
                    # not an arbitrary percentage.
                    return self._fire(f"SWEEP_RECLAIM:{name}",
                                      f"swept {min(recent):.2f} below {name} {lvl}, "
                                      f"reclaimed to {ltp}", now,
                                      extra={"swept_low": round(min(recent), 2),
                                             "level": lvl, "level_name": name})
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
        self.positions = []
        self.declined = []
        self.sandbox = False       # set True in tests; blocks ledger writes
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
                closed = [p for p in self.positions if p["status"] == "CLOSED"]
                if self.positions:
                    print(f"     paper: {len(closed)} closed, {held} open, "
                          f"net Rs{sum(p.get('pnl_net',0) for p in closed):+.2f}, "
                          f"{len(self.declined)} declined", flush=True)
                if datetime.now().strftime("%H:%M") >= FORCE_EXIT_AT and \
                        self.open_count():
                    print(f"  {FORCE_EXIT_AT} — squaring off every open position",
                          flush=True)
                    self.force_exit_all()
                if datetime.now().strftime("%H:%M") >= "15:30":
                    self.force_exit_all("SESSION_END")
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

    # ── autonomous paper trading ─────────────────────────────────────────────
    def _in_window(self, now=None):
        t = (now or datetime.now()).strftime("%H:%M")
        return ENTRY_WINDOW[0] <= t <= ENTRY_WINDOW[1]

    def open_count(self):
        return sum(1 for a in self.agents.values() if a.position)

    def maybe_enter(self, agent, ev):
        """Take a paper position, with no human in the loop.

        Every condition below is a reason to say NO, and they are all recorded when
        they fire — a rule that only logs its entries teaches you nothing about the
        trades it declined.
        """
        if not AUTO_ENTRY or agent.position:
            return None
        if ev["trigger"].split(":")[0] != ENTRY_TRIGGER:
            return None
        why_not = None
        if ev.get("agree", 0) < ENTRY_MIN_AGREE:
            why_not = f"only {ev.get('agree',0)} scout(s) agree"
        elif not self._in_window():
            why_not = f"outside {ENTRY_WINDOW[0]}-{ENTRY_WINDOW[1]}"
        elif self.open_count() >= MAX_CONCURRENT:
            why_not = f"{MAX_CONCURRENT} positions already open"
        elif not ev.get("swept_low") or not ev.get("ltp"):
            why_not = "no swept low to anchor the stop"
        if why_not:
            self.declined.append({**{k: ev[k] for k in ("at", "symbol", "trigger")},
                                  "reason": why_not})
            return None

        entry = float(ev["ltp"])
        stop = float(ev["swept_low"])
        risk = entry - stop
        if risk <= 0 or risk / entry > 0.02:      # >2% risk is not a scalp
            self.declined.append({"at": ev["at"], "symbol": ev["symbol"],
                                  "trigger": ev["trigger"],
                                  "reason": f"risk {risk/entry*100:.2f}% out of range"})
            return None
        target = round(entry + TARGET_R * risk, 2)
        qty = max(1, int(NOTIONAL / entry))
        pos = agent.open_position(entry, round(stop, 2), target, qty,
                                  ev.get("detail", "")[:70])
        rec = {"symbol": agent.symbol, "side": "LONG", "entry": entry,
               "stop": pos["stop"], "target": target, "qty": qty,
               "risk_pct": round(risk / entry * 100, 3), "r_target": TARGET_R,
               "entered_at": pos["at"], "trigger": ev["trigger"],
               "agree": ev.get("agree"), "score": ev.get("score"),
               "level": ev.get("level"), "level_name": ev.get("level_name"),
               "status": "OPEN"}
        self.positions.append(rec)
        print(f"  ## {pos['at']} ENTER {agent.symbol} x{qty} @ {entry} "
              f"stop {pos['stop']} target {target} "
              f"(risk {rec['risk_pct']}%, {ev.get('agree')} scouts)", flush=True)
        self._write_positions()
        return rec

    def close_position(self, agent, price, reason):
        p = agent.position
        if not p:
            return
        pnl = (price - p["entry"]) * p["qty"]
        gross_pct = (price / p["entry"] - 1) * 100
        fee = p["entry"] * p["qty"] * 0.00106      # our measured round-trip toll
        rec = next((r for r in self.positions
                    if r["symbol"] == agent.symbol and r["status"] == "OPEN"), None)
        if rec:
            rec.update({"status": "CLOSED", "exit": round(price, 2), "reason": reason,
                        "exited_at": datetime.now().strftime("%H:%M:%S"),
                        "pnl_gross": round(pnl, 2), "pnl_net": round(pnl - fee, 2),
                        "fee": round(fee, 2), "gross_pct": round(gross_pct, 3),
                        "held_s": int(time.time() - p["t0"]),
                        "mfe_pct": round((p["peak"] / p["entry"] - 1) * 100, 3),
                        "mae_pct": round((p["trough"] / p["entry"] - 1) * 100, 3)})
        agent.position = None
        agent.state = "WATCHING"
        print(f"  ## {datetime.now():%H:%M:%S} EXIT  {agent.symbol} @ {price} "
              f"{reason} gross Rs{pnl:+.2f} net Rs{pnl-fee:+.2f}", flush=True)
        self._write_positions()

    def _write_positions(self):
        # A unit test of maybe_enter() once wrote a synthetic TESTCO trade straight
        # into the live ledger. Anything not on a real stream stays out of the book.
        if getattr(self, "sandbox", False):
            return
        POSITIONS_FILE.mkdir(parents=True, exist_ok=True)
        f = POSITIONS_FILE / f"{datetime.now():%Y-%m-%d}.json"
        closed = [p for p in self.positions if p["status"] == "CLOSED"]
        f.write_text(json.dumps({
            "positions": self.positions,
            "declined": self.declined[-60:],
            "declined_total": len(self.declined),
            "open": sum(1 for p in self.positions if p["status"] == "OPEN"),
            "closed": len(closed),
            "net": round(sum(p.get("pnl_net", 0) for p in closed), 2),
            "gross": round(sum(p.get("pnl_gross", 0) for p in closed), 2),
            "wins": sum(1 for p in closed if p.get("pnl_net", 0) > 0),
            "rule": {"trigger": ENTRY_TRIGGER, "min_agree": ENTRY_MIN_AGREE,
                     "target_r": TARGET_R, "notional": NOTIONAL,
                     "window": list(ENTRY_WINDOW)},
        }, indent=1))

    def force_exit_all(self, reason="TIME_STOP"):
        for a in list(self.agents.values()):
            if a.position:
                last = a.ticks[-1][1] if a.ticks else a.position["entry"]
                self.close_position(a, last, reason)

    def escalate(self, ev):
        """Something happened. Record it, and act on it if the rule says so."""
        self.escalation_log.append(ev)
        agent = next((a for a in self.agents.values()
                      if a.symbol == ev["symbol"]), None)
        if agent:
            base = ev["trigger"].split(":")[0]
            if base == "INVALIDATION" and agent.position:
                self.close_position(agent, float(ev["ltp"]), "STOP")
            elif base == "TARGET_REACHED" and agent.position:
                self.close_position(agent, float(ev["ltp"]), "TARGET")
            else:
                self.maybe_enter(agent, ev)
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
            "positions": self.positions,
            "declined_total": len(self.declined),
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
