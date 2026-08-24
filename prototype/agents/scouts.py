#!/usr/bin/env python3
"""
agents/scouts — a small team of market-wide scouts that decide WHAT the floor watches.

DESIGN (Soumya, 2026-08-24): "do not look at these 20 stocks only — we need uptrend
stocks / whichever stocks can make us profitable. A team of 2-4 agents keeps scanning
the ENTIRE market so we cannot miss any stock that is good to trade."

WHY SCOUTS AND WATCHERS ARE DIFFERENT JOBS
A watcher is DEEP and NARROW: one stock, every tick, levels held in memory. It cannot
see the other 900 names — that is the price of specialisation.
A scout is BROAD and SHALLOW: all 938 liquid names, once a minute, four numbers each.
Neither can do the other's job. Together they cover the market without missing it.

    938 liquid names --> 4 scouts (60s sweep) --> ranked candidates --> 20 watchers

WHY FOUR LENSES AND NOT ONE RANKING
Four scouts running the SAME logic would be one scout with extra cost. Each lens is
chosen because the other three are structurally blind to it:

  TREND     stocks in a real multi-day uptrend, pulled back rather than extended.
            (The user's "uptrend stocks" — but see the honesty note below.)
  FLOW      unusual volume vs its own 20-day norm. Direction-agnostic: this is the
            "someone knows something" lens, and it fires before price does.
  LEVEL     price sitting AT a decision point (PDH/PDL/52w/round/VWAP/range edge).
            Our own falsification run says the edge lives at levels, not mid-range.
  REVERSAL  5-day losers snapping back — our 2nd-best measured predicate (+0.057%),
            and the one thing a trend scout can never surface.

HONESTY NOTE, CARRIED FROM OUR OWN MEASUREMENTS
Our falsification run (145,500 trades) found that INTRADAY this market mean-reverts:
trading WITH the daily bias lost (-0.039%), against it gained (+0.003%). So the TREND
scout does not chase strength — it ranks strong DAILY structure that is NOT extended
today, i.e. the pullback. Chasing a stock already up 4% is the exact trade our data
says loses money.

THE MERGE IS THE POINT
The one finding that survived falsification was CONFLUENCE: gross edge rose
monotonically with the number of agreeing predicates (-0.16% at 1 agreeing, +0.084%
at 7). So the merge is not "best score wins" — a name two scouts found independently
outranks any single scout's favourite. Agreement between independent reads IS the
signal; any one lens is not.

Run:
    python3 -m prototype.agents.scouts --once        # one sweep, print the board
    python3 -m prototype.agents.scouts --watch       # sweep every 60s
"""
from __future__ import annotations

import json, math, re, sys, time, warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

CTX_CACHE = ROOT / "prototype" / "data" / "scout_ctx"
UNIVERSE_F = ROOT / "quant" / "universe_screened.txt"

SWEEP_BATCH = 500            # Kite quote() accepts 500 instruments per call
CTX_TOP_N = 320              # daily history is pulled for the top-N by turnover
MIN_PRICE, MAX_PRICE = 80.0, 800.0     # the Rs1k tradeable band (quantisation)
MIN_TURNOVER = 2e7           # Rs2 crore traded today — below this, spread eats us
MIN_DAY_RANGE_PCT = 0.30     # below this the instrument does not move at all
CIRCUIT_HEADROOM_PCT = 0.50  # this close to a circuit limit there is no counterparty

# ETFs are not stocks, and the gold ones are all THE SAME TRADE. The first sweep put
# five gold ETFs in the top fourteen and scored it as confluence — it was one macro
# bet counted five times, which is exactly the error the confluence merge exists to
# avoid rewarding.
#
# Match the WRAPPER, never the holdings. An earlier version also filtered names
# containing GOLD/SILVER and ate five real companies — Deccan Gold Mines, Goldiam,
# Sky Gold, Shanti Gold, Silver Touch. A gold miner and a gold ETF share every word
# about what they hold; they differ only in what they ARE. So: the literal token ETF
# or BEES, the phrase "exchange traded fund", or AMC- branding (AXISAMC-GOLDAXIS).
# Verified on the full 938: catches 49, keeps all nine real look-alikes including
# HDFCAMC and UTIAMC, whose "AMC" has no trailing dash.
ETF_PAT = re.compile(
    r"\b(ETF|BEES)\b|MUTUAL FUND|INDEX FUND|EXCHANGE TRADED|\bFOF\b|AMC-", re.I)


def in_session(now=None):
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return (9 * 60 + 15) <= m < (15 * 60 + 30)


# ══════════════════════════════════════════════════════════════════════════════
# Daily context — the multi-day memory a quote() snapshot cannot provide
# ══════════════════════════════════════════════════════════════════════════════
class DailyContext:
    """Daily bars for the names worth ranking. Pulled once, cached per-day.

    A quote() sweep gives today: open/high/low/LTP/volume/VWAP and PREV CLOSE. That
    is enough for the LEVEL lens but not for 'is this a real uptrend', 'is today's
    volume unusual', or 'has this fallen 5 days running'. Those need history — so we
    pull it once for the top names by turnover and cache it to disk, which makes a
    restart mid-session instant instead of a 2-minute stall.
    """

    def __init__(self):
        CTX_CACHE.mkdir(parents=True, exist_ok=True)
        self.f = CTX_CACHE / f"{datetime.now():%Y-%m-%d}.json"
        self.ctx = json.loads(self.f.read_text()) if self.f.exists() else {}

    def have(self, sym):
        return sym in self.ctx

    def build(self, symbols, verbose=True):
        from prototype.v4 import kite_data as kd
        k = kd.client()
        todo = [s for s in symbols if s not in self.ctx]
        if not todo:
            return self.ctx
        if verbose:
            print(f"  building daily context for {len(todo)} names "
                  f"({len(self.ctx)} cached)...", flush=True)
        end = datetime.now()
        start = end - timedelta(days=400)
        done = 0
        for s in todo:
            try:
                tok = kd.token_for(s)
                if not tok:
                    self.ctx[s] = None
                    continue
                b = k.historical_data(tok, start, end, "day")
                if len(b) < 30:
                    self.ctx[s] = None
                    continue
                # exclude today's partial bar from every historical statistic
                today = datetime.now().strftime("%Y-%m-%d")
                b = [x for x in b if str(x["date"])[:10] < today] or b[:-1]
                c = [float(x["close"]) for x in b]
                v = [float(x.get("volume") or 0) for x in b]
                h = [float(x["high"]) for x in b]
                lo = [float(x["low"]) for x in b]
                n = len(c)
                sma = lambda w: sum(c[-w:]) / w if n >= w else None
                trs = [max(h[i] - lo[i], abs(h[i] - c[i - 1]), abs(lo[i] - c[i - 1]))
                       for i in range(max(1, n - 14), n)]
                self.ctx[s] = {
                    "close": c[-1],
                    "sma20": sma(20), "sma50": sma(50), "sma200": sma(200),
                    "avg_vol20": sum(v[-20:]) / min(20, n),
                    "atr14": (sum(trs) / len(trs)) if trs else None,
                    "hi52": max(h[-250:]) if n >= 60 else max(h),
                    "lo52": min(lo[-250:]) if n >= 60 else min(lo),
                    "ret5": (c[-1] / c[-6] - 1) if n >= 6 else None,
                    "ret20": (c[-1] / c[-21] - 1) if n >= 21 else None,
                    # swing structure: higher highs AND higher lows over 3 x 5d blocks
                    "hh": (n >= 15 and max(h[-5:]) > max(h[-10:-5]) > max(h[-15:-10])),
                    "hl": (n >= 15 and min(lo[-5:]) > min(lo[-10:-5]) > min(lo[-15:-10])),
                    "lh": (n >= 15 and max(h[-5:]) < max(h[-10:-5]) < max(h[-15:-10])),
                }
            except Exception:
                self.ctx[s] = None
            done += 1
            if verbose and done % 60 == 0:
                print(f"    ...{done}/{len(todo)}", flush=True)
            time.sleep(0.34)          # Kite historical rate limit is 3 req/s
        self.f.write_text(json.dumps(self.ctx))
        return self.ctx

    def get(self, sym):
        return self.ctx.get(sym)

    def prewarm(self):
        """Build today's context BEFORE the open, off yesterday's name list.

        Without this the first sweep of the day pays ~110s of Kite historical calls
        at 09:16 — silence through the most volatile minutes of the session. The
        names worth ranking barely change overnight, so yesterday's cache keys are
        an excellent guess, and anything genuinely new is filled in by the first
        live sweep at a cost of a second or two.
        """
        prior = sorted(CTX_CACHE.glob("*.json"))
        prior = [p for p in prior if p.name != self.f.name]
        if prior:
            try:
                # cap it: each day's cache seeds the next, so an uncapped prewarm
                # ratchets upward every session until it no longer fits before the
                # open. The sweep only ranks CTX_TOP_N anyway.
                names = list(json.loads(prior[-1].read_text()).keys())[:CTX_TOP_N]
                print(f"  prewarming from {prior[-1].name}: {len(names)} names")
                return self.build(names)
            except Exception as e:
                print(f"  prewarm read failed: {str(e)[:60]}")
        u = [l.strip().replace(".NS", "")
             for l in UNIVERSE_F.read_text().splitlines() if l.strip()]
        print(f"  no prior cache — prewarming first {CTX_TOP_N} of the universe")
        return self.build(u[:CTX_TOP_N])


# ══════════════════════════════════════════════════════════════════════════════
# The four lenses. Each returns {symbol: (score 0-1, reason)} — nothing else.
# ══════════════════════════════════════════════════════════════════════════════
def _pct(a, b):
    return (a / b - 1.0) * 100.0 if b else 0.0


def scout_trend(rows, ctx):
    """Real multi-day uptrend, NOT extended today.

    Our data says chasing intraday strength loses. So extension is PENALISED: a
    stock already up 4% today scores lower than the same stock up 0.5% and sitting
    on its 20-day average. This scout looks for a strong horse taking a breath.
    """
    out = {}
    for r in rows:
        c = ctx.get(r["sym"])
        if not c or not c.get("sma20") or not c.get("sma50"):
            continue
        px, prev = r["ltp"], r["prev"]
        if not (c["close"] > c["sma20"] > c["sma50"]):
            continue                                  # not an uptrend, next
        chg = _pct(px, prev)
        # HARD BOUNDS, not a soft penalty. The first sweep ranked BLS as an uptrend
        # while it was DOWN 11% today, and BALUFORGE while it was UP 13.8%. Both got
        # through because the daily context deliberately excludes today's bar — so
        # yesterday's uptrend outlived a crash that had already happened. A graded
        # penalty could always be outrun by a high base score; a gate cannot be.
        if chg > 4.0 or chg < -2.0:
            continue
        s = 0.30
        if c.get("hh") and c.get("hl"):
            s += 0.25                                 # textbook HH+HL structure
        elif c.get("hh"):
            s += 0.12
        if c.get("sma200") and c["close"] > c["sma200"]:
            s += 0.10
        if c.get("ret20") and c["ret20"] > 0.05:
            s += 0.10
        # extension penalty inside the gate — the honest part
        if chg > 3.0:
            s -= 0.30
        elif chg > 1.5:
            s -= 0.12
        # reward the pullback: near the 20SMA or below today's VWAP in an uptrend
        if c["sma20"] and abs(px - c["sma20"]) / c["sma20"] < 0.02:
            s += 0.20
        if r["vwap"] and px < r["vwap"] and chg > -1.0:
            s += 0.10
        if s > 0.35:
            out[r["sym"]] = (min(s, 1.0),
                             f"uptrend {c['ret20']*100:+.1f}%/20d, today {chg:+.1f}%"
                             + (", at 20SMA" if c["sma20"] and
                                abs(px - c["sma20"]) / c["sma20"] < 0.02 else ""))
    return out


def scout_flow(rows, ctx):
    """Unusual participation vs the stock's own norm — direction-agnostic.

    Compares today's volume RUN-RATE (extrapolated to a full session) against the
    20-day average. Run-rate matters: 2x average volume at 09:30 is extraordinary,
    the same figure at 15:20 is ordinary. This fires before price commits, which is
    exactly why the other three lenses cannot see what it sees.
    """
    now = datetime.now()
    mins = max((now.hour * 60 + now.minute) - (9 * 60 + 15), 5)
    frac = min(mins / 375.0, 1.0)              # fraction of the session elapsed
    out = {}
    for r in rows:
        c = ctx.get(r["sym"])
        if not c or not c.get("avg_vol20") or c["avg_vol20"] <= 0:
            continue
        projected = r["vol"] / frac
        ratio = projected / c["avg_vol20"]
        if ratio < 1.8:
            continue
        s = min(0.25 + 0.22 * math.log(ratio, 2), 1.0)
        # range expansion confirms the volume is doing something, not just churning
        if c.get("atr14") and c["atr14"] > 0:
            rng = (r["high"] - r["low"]) / c["atr14"]
            if rng > 1.2:
                s += 0.15
        out[r["sym"]] = (min(s, 1.0),
                         f"{ratio:.1f}x normal volume ({r['vol']/1e5:.1f}L by "
                         f"{now:%H:%M})")
    return out


def scout_level(rows, ctx):
    """Price AT a decision point. Our falsification run's clearest survivor.

    Mid-range is explicitly a no-trade in the playbook, so this lens scores only
    proximity: 52-week extremes, prior-day close, round numbers, VWAP, and the
    day's own extremes. It says WHERE, never which way — the watcher decides that.
    """
    out = {}
    for r in rows:
        px = r["ltp"]
        c = ctx.get(r["sym"]) or {}
        best, why = 0.0, None
        def near(level, name, weight):
            nonlocal best, why
            if not level:
                return
            bps = abs(px - level) / level * 10000
            if bps < 60:
                sc = weight * (1 - bps / 60)
                if sc > best:
                    best, why = sc, f"{bps:.0f}bps from {name} {level:.1f}"
        near(c.get("hi52"), "52w HIGH", 1.00)
        near(c.get("lo52"), "52w LOW", 0.85)
        near(r["prev"], "prev close", 0.55)
        near(round(px / 50) * 50 if px > 200 else round(px / 10) * 10, "round", 0.45)
        # Intraday levels are only levels WHILE the session runs. After the close LTP
        # is the close, so nearly everything sits "at VWAP" and inside its own day
        # range — the first sweep flagged VWAP proximity on 4 of its top 5 at 22:28.
        # Structural levels (52w, round, prev close) stay valid around the clock.
        if in_session():
            near(r["vwap"], "VWAP", 0.60)
            near(r["high"], "day HIGH", 0.65)
            near(r["low"], "day LOW", 0.65)
        # a tight coil at a level is worth more than a level alone
        if c.get("atr14") and c["atr14"] > 0 and best > 0:
            if (r["high"] - r["low"]) / c["atr14"] < 0.5:
                best, why = min(best + 0.20, 1.0), (why or "") + ", coiled"
        if best > 0.35:
            out[r["sym"]] = (best, why)
    return out


def scout_reversal(rows, ctx):
    """5-day losers snapping back — our 2nd-best measured predicate (+0.057%).

    Structurally invisible to the trend scout, which by construction rejects every
    name this one wants. That is the whole reason it is a separate lens.
    """
    out = {}
    for r in rows:
        c = ctx.get(r["sym"])
        if not c or c.get("ret5") is None:
            continue
        if c["ret5"] > -0.03:
            continue                                    # not beaten up enough
        s = min(0.30 + abs(c["ret5"]) * 4.0, 0.75)
        chg = _pct(r["ltp"], r["prev"])
        if chg > 0.3:
            s += 0.20                                   # the snapback has started
        if r["vwap"] and r["ltp"] > r["vwap"]:
            s += 0.10                                   # reclaimed the day's VWAP
        if c.get("sma200") and c["close"] > c["sma200"]:
            s += 0.10                                   # falling knife filter
        if c.get("lh"):
            s -= 0.25                                   # structurally still broken
        if s > 0.40:
            out[r["sym"]] = (min(s, 1.0),
                             f"{c['ret5']*100:+.1f}%/5d, today {chg:+.1f}%")
    return out


SCOUTS = [("TREND", scout_trend), ("FLOW", scout_flow),
          ("LEVEL", scout_level), ("REVERSAL", scout_reversal)]


# ══════════════════════════════════════════════════════════════════════════════
class ScoutTeam:
    def __init__(self, verbose=True):
        self.verbose = verbose
        self.ctx = DailyContext()
        self._k = None
        raw = [l.strip().replace(".NS", "")
               for l in UNIVERSE_F.read_text().splitlines() if l.strip()]
        names = self._instrument_names()
        self.universe = [s for s in raw
                         if not ETF_PAT.search(names.get(s, "") or "")]
        self.dropped_etf = len(raw) - len(self.universe)

    def _instrument_names(self):
        try:
            return {i["tradingsymbol"]: i.get("name") or ""
                    for i in self.kite().instruments("NSE")}
        except Exception:
            return {}

    def kite(self):
        if self._k is None:
            from prototype.v4 import kite_data as kd
            self._k = kd.client()
        return self._k

    def sweep(self):
        """One quote pass over the whole liquid universe. Two API calls, ~0.3s."""
        k, live = self.kite(), {}
        for i in range(0, len(self.universe), SWEEP_BATCH):
            ch = self.universe[i:i + SWEEP_BATCH]
            try:
                live.update(k.quote([f"NSE:{s}" for s in ch]))
            except Exception as e:
                if self.verbose:
                    print(f"  sweep batch error: {str(e)[:70]}")
        rows = []
        for s in self.universe:
            d = live.get(f"NSE:{s}")
            if not d:
                continue
            o = d.get("ohlc") or {}
            px = float(d.get("last_price") or 0)
            prev = float(o.get("close") or 0)
            vol = float(d.get("volume") or 0)
            if not px or not prev:
                continue
            if not (MIN_PRICE <= px <= MAX_PRICE):
                continue                       # outside the Rs1k quantisation band
            if px * vol < MIN_TURNOVER:
                continue                       # too thin — spread would eat the edge
            hi, lo = float(o.get("high") or px), float(o.get("low") or px)
            if (hi - lo) / px * 100 < MIN_DAY_RANGE_PCT:
                continue     # dead instrument: nothing to trade even if we wanted to
            # A stock at its circuit limit has NO COUNTERPARTY — you cannot buy a
            # locked-upper name at any price, and you cannot exit a locked-lower one.
            # The scouts' best-looking names are exactly the ones at risk of this,
            # because a lock is what a huge move ends in. 0 of 20 tonight, but a
            # +20% name would be untradeable and still top the board.
            uc = float(d.get("upper_circuit_limit") or 0)
            lc = float(d.get("lower_circuit_limit") or 0)
            if uc and lc:
                if (uc - px) / px * 100 < CIRCUIT_HEADROOM_PCT:
                    continue
                if (px - lc) / px * 100 < CIRCUIT_HEADROOM_PCT:
                    continue
            rows.append({"sym": s, "ltp": px, "prev": prev, "vol": vol,
                         "high": float(o.get("high") or px),
                         "low": float(o.get("low") or px),
                         "open": float(o.get("open") or px),
                         "vwap": float(d.get("average_price") or 0) or None,
                         "turnover": px * vol})
        return rows

    def scan(self, top=20):
        """Sweep, run all four lenses, merge on CONFLUENCE, return a ranked board."""
        rows = self.sweep()
        if not rows:
            return []
        # daily context only for names worth ranking — by today's turnover
        rows.sort(key=lambda r: -r["turnover"])
        need = [r["sym"] for r in rows[:CTX_TOP_N]]
        self.ctx.build(need, verbose=self.verbose)
        ranked_rows = rows[:CTX_TOP_N]

        found = {}
        for name, fn in SCOUTS:
            try:
                for sym, (sc, why) in fn(ranked_rows, self.ctx).items():
                    found.setdefault(sym, {})[name] = (sc, why)
            except Exception as e:
                if self.verbose:
                    print(f"  scout {name} failed: {str(e)[:80]}")

        by_sym = {r["sym"]: r for r in ranked_rows}
        board = []
        for sym, hits in found.items():
            n = len(hits)
            best = max(s for s, _ in hits.values())
            avg = sum(s for s, _ in hits.values()) / n
            # CONFLUENCE DOMINATES. Our measured gradient says agreement between
            # independent reads is the signal; a single lens's conviction is not.
            final = best * 0.45 + avg * 0.15 + (n - 1) * 0.28
            board.append({
                "symbol": sym, "score": round(min(final, 1.0), 3), "agree": n,
                "lenses": {k: round(v[0], 2) for k, v in hits.items()},
                "why": " | ".join(f"{k}: {v[1]}" for k, v in
                                  sorted(hits.items(), key=lambda x: -x[1][0])),
                "ltp": by_sym[sym]["ltp"],
                "chg": round(_pct(by_sym[sym]["ltp"], by_sym[sym]["prev"]), 2),
                "turnover_cr": round(by_sym[sym]["turnover"] / 1e7, 1),
            })
        # Rank by score ALONE. An earlier version sorted by (-agree, -score), which
        # double-counted confluence — the score already carries it at 0.28 per extra
        # scout — and made the list non-monotonic in score: a 3-scout name whose
        # lenses all barely tripped scores 0.776 and sorted ABOVE a 2-scout name at
        # full conviction scoring 0.880. The floor's swap loop breaks on the first
        # challenger that misses its margin, so that inversion silently cost real
        # reassignments. Sorting by score restores monotonicity and makes the break
        # correct as well as cheap.
        board.sort(key=lambda x: -x["score"])
        return board[:top]


def print_board(board, scanned=None):
    print(f"\n  {'#':<3}{'SYMBOL':<14}{'SCORE':>6}{'AGREE':>7}{'LTP':>9}"
          f"{'CHG%':>7}{'TURN(cr)':>10}  LENSES")
    print("  " + "-" * 108)
    for i, b in enumerate(board, 1):
        lens = ",".join(f"{k}:{v}" for k, v in b["lenses"].items())
        print(f"  {i:<3}{b['symbol']:<14}{b['score']:>6.3f}{b['agree']:>7}"
              f"{b['ltp']:>9.2f}{b['chg']:>7.2f}{b['turnover_cr']:>10.1f}  {lens}")
    if board:
        print("\n  WHY (top 5):")
        for b in board[:5]:
            print(f"    {b['symbol']:<12} {b['why']}")


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--prewarm", action="store_true",
                    help="build today's daily context before the open")
    ap.add_argument("--top", type=int, default=20)
    a = ap.parse_args()
    team = ScoutTeam()
    print(f"  scout team: {len(SCOUTS)} lenses over {len(team.universe)} liquid names "
          f"({team.dropped_etf} ETFs/funds excluded)")
    if a.prewarm:
        t0 = time.time()
        team.ctx.prewarm()
        print(f"  context ready for {len(team.ctx.ctx)} names in {time.time()-t0:.0f}s "
              f"— the 09:16 floor will start streaming immediately")
        return
    if a.watch:
        while True:
            print(f"\n  ═══ SWEEP {datetime.now():%H:%M:%S} ═══")
            print_board(team.scan(a.top))
            if datetime.now().strftime("%H:%M") >= "15:30":
                break
            time.sleep(60)
    else:
        print_board(team.scan(a.top))


if __name__ == "__main__":
    main()
