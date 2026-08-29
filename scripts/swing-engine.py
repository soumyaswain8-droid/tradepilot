#!/usr/bin/env python3
"""
swing-engine (v5_swing) — the 2-3 day dip-buy experiment. Paper only.

BORN 2026-08-19 (Soumya): red morning across every broad index; buy quality dips
with breakout potential, hold 2-3 days, full Rs10L on one engine, positions sized
ABOVE the Rs66,667 fee cliff. Runs alongside the intraday fleet as a separate lane.

WHAT THE PRIOR EVIDENCE DOES AND DOES NOT SAY
test-timeframe (08-05) showed v5's INTRADAY entries held for days have zero
market-adjusted alpha — that killed "hold the same trades longer", not this. A
selection built FOR the 2-3 day horizon is untested. This engine is that test, and
it carries its own pre-registered gate: after ~60 closed swings, net after 0.079%
fees must beat a random-dip control or the lane closes.

THE SELECTION (one month of daily structure, all criteria measurable)
  1. TREND    close > 20DMA and 20DMA rising over the month  — dip in an uptrend,
              not a falling knife
  2. COILED   last-5-day range < 60% of the month's average 5-day range — tight
              consolidation near the level
  3. NEAR THE LEVEL  close within 4% of the 1-month high — "breakout candidate"
              means the level is actually nearby
  4. DIPPED   today red or flat — we are buying the dip the market is offering
  Score = proximity to the level + trend slope + compression; top N get slots.

EXITS (swing, not intraday — no 15:15 force-flat)
  target  breakout level + 2%      (the move we claim will happen)
  stop    -2.5% from entry         (thesis wrong)
  time    close of the 3rd session (thesis expired — the 2-3 day claim is falsified
                                    by time, not by price)

SESSION-GUARD: entries only 09:15-15:30 (v10 bought 19 stale-priced positions
pre-open on 08-10; every engine born after carries the clock gate from birth).

State files use the fleet schema (pools/closed/positions_active) so /api/desk and
the terminal record it with zero dashboard changes.

Run:
    python3 scripts/swing-engine.py --backtest      # validate selection on simcache
    python3 scripts/swing-engine.py --scan          # scan + deploy today's entries
    python3 scripts/swing-engine.py --manage        # stops/targets/time exits
"""
from __future__ import annotations

import argparse, json, math, statistics as st, sys, warnings
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v4 import kite_data as kd
from prototype.v4.config import ACTIVE_SYMBOLS_YF

ENGINE = "v5_swing"
DIR = ROOT / "docs" / "paper-trades" / ENGINE
CAPITAL = 1_000_000
N_SLOTS = 8                       # ~Rs115k/slot — every position above the cliff
TARGET_OVER_LEVEL = 2.0           # % beyond the 1-month high
STOP_PCT = 2.5
MAX_HOLD_SESSIONS = 3
NEAR_LEVEL_PCT = 4.0
COIL_RATIO = 0.60
FEE_PCT = 0.24                    # CNC DELIVERY round trip — multi-day holds cannot
                                  # use MIS. STT 0.1% EACH side + stamp + DP charge.
                                  # Was wrongly 0.0787 (intraday) until 2026-08-23.

CACHE = ROOT / "prototype" / "data" / "simcache"


def in_session(now=None) -> bool:
    now = now or datetime.now()
    if now.weekday() >= 5:
        return False
    m = now.hour * 60 + now.minute
    return 9 * 60 + 15 <= m < 15 * 60 + 30


def daily_from_cache(sym):
    f = CACHE / f"{sym}_5m.parquet"
    if not f.exists():
        return None
    b = pd.read_parquet(f)
    d = b.resample("1D").agg({"Open": "first", "High": "max", "Low": "min",
                              "Close": "last", "Volume": "sum"}).dropna()
    d.index = d.index.tz_localize(None).normalize()
    return d


def score_setup(d: pd.DataFrame):
    """Apply the 4 criteria to the last 22 sessions of a daily frame.
    Returns (score, info) or None. Uses ONLY closed daily bars."""
    if d is None or len(d) < 22:
        return None
    w = d.tail(22)
    close = float(w["Close"].iloc[-1])
    ma20 = float(w["Close"].tail(20).mean())
    ma20_prev = float(w["Close"].iloc[-21:-1].tail(20).mean()) if len(d) >= 23 else ma20
    hi_1m = float(w["High"].max())
    today_chg = (close / float(w["Close"].iloc[-2]) - 1) * 100
    # 5-day ranges across the month
    r5 = [float(w["High"].iloc[i:i+5].max() - w["Low"].iloc[i:i+5].min())
          for i in range(0, 17)]
    coil = (r5[-1] / st.mean(r5)) if st.mean(r5) > 0 else 9
    dist = (hi_1m - close) / close * 100
    if close <= ma20:            return None       # 1. trend
    if ma20 <= ma20_prev:        return None
    if coil > COIL_RATIO:        return None       # 2. coiled
    if dist > NEAR_LEVEL_PCT:    return None       # 3. near the level
    if today_chg > 0.10:         return None       # 4. dipped (red/flat day)
    slope = (ma20 / ma20_prev - 1) * 100
    score = (NEAR_LEVEL_PCT - dist) * 10 + slope * 20 + (COIL_RATIO - coil) * 30
    return score, dict(close=close, level=round(hi_1m, 2), dist_pct=round(dist, 2),
                       coil=round(coil, 2), ma20_slope=round(slope, 3),
                       today=round(today_chg, 2))


# ── backtest: same rule, walked over the cache ──────────────────────────────
def backtest():
    files = sorted(CACHE.glob("*_5m.parquet"))
    syms = [f.name[:-11] for f in files if not f.name.startswith("NIFTY")]
    frames = {s: daily_from_cache(s) for s in syms}
    frames = {s: d for s, d in frames.items() if d is not None and len(d) > 30}
    days = sorted(set().union(*[set(d.index.strftime("%Y-%m-%d")) for d in frames.values()]))
    rets, hits = [], 0
    per_day = []
    for di in range(22, len(days) - MAX_HOLD_SESSIONS):
        day = days[di]
        cands = []
        for s, d in frames.items():
            hist = d[d.index.strftime("%Y-%m-%d") <= day]
            r = score_setup(hist)
            if r:
                cands.append((r[0], s, r[1]))
        cands.sort(reverse=True)
        picked = cands[:N_SLOTS]
        if not picked:
            continue
        day_n = 0
        for sc, s, info in picked:
            d = frames[s]
            fut = d[d.index.strftime("%Y-%m-%d") > day]
            if len(fut) < MAX_HOLD_SESSIONS:
                continue
            entry = info["close"]
            tgt = info["level"] * (1 + TARGET_OVER_LEVEL / 100)
            stp = entry * (1 - STOP_PCT / 100)
            ret = None
            for k in range(MAX_HOLD_SESSIONS):
                hi, lo, cl = (float(fut["High"].iloc[k]), float(fut["Low"].iloc[k]),
                              float(fut["Close"].iloc[k]))
                if lo <= stp:                       # stop first — pessimistic
                    ret = -STOP_PCT; break
                if hi >= tgt:
                    ret = (tgt - entry) / entry * 100
                    hits += 1
                    break
            if ret is None:
                ret = (float(fut["Close"].iloc[MAX_HOLD_SESSIONS - 1]) - entry) / entry * 100
            rets.append(ret - FEE_PCT)
            day_n += 1
        per_day.append(day_n)
    n = len(rets)
    if n < 20:
        print(f"  only {n} historical setups — not enough"); return
    m = st.mean(rets); sd = st.pstdev(rets)
    t = m / (sd / math.sqrt(n)) if sd else 0
    win = sum(1 for r in rets if r > 0) / n * 100
    print(f"  BACKTEST (same rule walked over the cache, entries at scan-day close):")
    print(f"    setups: {n} across {len(per_day)} scan days (avg {st.mean(per_day):.1f}/day)")
    print(f"    breakout hit rate (target touched in 3d): {hits}/{n} = {hits/n*100:.0f}%")
    print(f"    win rate: {win:.0f}%  |  net/trade after {FEE_PCT}%: {m:+.4f}%  |  t={t:+.2f}")
    # This t is NOT trustworthy as printed, and the audit of 2026-08-29 (see
    # docs/research/overnight/hac-audit.md) says so explicitly. Two independent
    # violations of the independence the formula assumes:
    #   1. it pools ~8 setups per day as if they were iid, when same-day setups share
    #      the market factor — the same error that inflated a per-trade t 6.3x elsewhere
    #   2. the 3-day hold overlaps across consecutive scan days
    # The two errors were measured pointing in OPPOSITE directions here, so the printed
    # number cannot even be assumed too high. It is simply uninterpretable.
    #
    # Harmless today only because the result is negative (net -0.35%/trade on 74
    # sessions / 93 setups, which is near-powerless either way). If this ever prints
    # t > 2, DO NOT promote on it — recompute with date-clustered errors and a HAC lag
    # of the holding period first.
    if m > 0 and t > 2:
        print("    t>2 BUT UNVERIFIED — pooled same-day setups + overlapping 3d holds.")
        print("    Do NOT promote on this number; recompute clustered + HAC. (hac-audit.md)")
    else:
        print("    NO significant edge in-sample — deploy as EXPERIMENT ONLY")


# ── live: scan + deploy ─────────────────────────────────────────────────────
def load_state():
    f = DIR / "positions_active.json"
    if f.exists():
        try:
            return json.loads(f.read_text())
        except Exception:
            pass
    return {"positions": {"SWING": []}}


def save_state(state):
    DIR.mkdir(parents=True, exist_ok=True)
    state["saved_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (DIR / "positions_active.json").write_text(json.dumps(state, indent=2))


def day_file():
    f = DIR / f"{datetime.now():%Y-%m-%d}.json"
    if f.exists():
        try:
            return json.loads(f.read_text()), f
        except Exception:
            pass
    return {"date": f.stem, "engine": ENGINE, "total_capital": CAPITAL,
            "pools": {"SWING": {"positions": [], "closed": [], "pnl": 0.0}},
            "summary": {"total_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}}, f


def quotes(symlist):
    out = {}
    for i in range(0, len(symlist), 200):
        chunk = symlist[i:i + 200]
        try:
            res = kd.client().quote([f"NSE:{s}" for s in chunk])
        except Exception as e:
            print(f"  quote batch failed: {e}"); continue
        for s in chunk:
            q = res.get(f"NSE:{s}")
            if q and q.get("last_price"):
                out[s] = float(q["last_price"])
    return out


def scan_and_deploy():
    if not in_session():
        print(f"  [SESSION-GUARD] {datetime.now():%H:%M} outside 09:15-15:30 — no entries")
        return
    state = load_state()
    held = {p["symbol"] for p in state["positions"]["SWING"]}
    free_slots = N_SLOTS - len(held)
    if free_slots <= 0:
        print(f"  all {N_SLOTS} slots full"); return
    syms = [s.replace(".NS", "") for s in ACTIVE_SYMBOLS_YF]
    # month of dailies from Kite (fresh, includes today so far — we drop today and
    # score on CLOSED sessions only, entering at the live price)
    cands = []
    for s in syms:
        if s in held:
            continue
        try:
            tok = kd.token_for(s)
            if not tok:
                continue
            bars = kd.client().historical_data(
                tok, datetime.now() - timedelta(days=45), datetime.now(), "day")
        except Exception:
            continue
        if len(bars) < 23:
            continue
        d = pd.DataFrame([{"dt": b["date"], "Open": b["open"], "High": b["high"],
                           "Low": b["low"], "Close": b["close"], "Volume": b["volume"]}
                          for b in bars]).set_index("dt")
        if str(d.index[-1])[:10] == f"{datetime.now():%Y-%m-%d}":
            d = d.iloc[:-1]                     # score closed sessions only
        r = score_setup(d)
        if r:
            cands.append((r[0], s, r[1]))
    cands.sort(reverse=True)
    # PRE-OPEN GAP VETO (2026-08-20): if a VALIDATED snapshot of today's auction
    # exists, skip candidates that gapped UP > 1% — the one-session study (19 Aug)
    # showed >+1% auction gaps faded -1.17% open->close (20% win), consistent with
    # the measured intraday mean-reversion. A VETO on chasing, not a signal; logged
    # so the ablation can judge it later. No snapshot -> no change in behaviour.
    gp = ROOT / "prototype" / "data" / "preopen" / f"{datetime.now():%Y-%m-%d}.json"
    if gp.exists():
        gaps = json.loads(gp.read_text())
        before = len(cands)
        vetoed = [(s, gaps.get(s)) for _, s, _ in cands
                  if gaps.get(s) is not None and gaps[s] > 1.0]
        cands = [c for c in cands if not (gaps.get(c[1]) is not None and gaps[c[1]] > 1.0)]
        for s, g in vetoed:
            print(f"  GAP-VETO {s}: auction gap {g:+.2f}% > +1% — not chasing")
        print(f"  pre-open overlay: {before} -> {len(cands)} candidates")
    picked = cands[:free_slots]
    print(f"  scan: {len(cands)} candidates pass all 4 criteria; taking {len(picked)}")
    if not picked:
        return
    px = quotes([s for _, s, _ in picked])
    slot = CAPITAL / N_SLOTS
    j, f = day_file()
    for sc, s, info in picked:
        p = px.get(s)
        if not p or p <= 0:
            continue
        qty = int(slot / p)
        if qty < 1 or qty * p < 66_667:
            print(f"  {s}: slot would be Rs{qty*p:,.0f} — below the fee cliff, skipped")
            continue
        pos = {"symbol": s, "entry_price": p, "qty": qty, "cost": round(qty * p, 2),
               "entry_time": datetime.now().strftime("%H:%M:%S"),
               "entry_date": datetime.now().strftime("%Y-%m-%d"),
               "sl_price": round(p * (1 - STOP_PCT / 100), 2),
               "target_price": round(info["level"] * (1 + TARGET_OVER_LEVEL / 100), 2),
               "position_type": "LONG", "pool": "SWING",
               "breakout_level": info["level"], "score": round(sc, 1),
               "hold_until": None,  # filled by manage() session counting
               "sessions_held": 0,
               "reasons": [
                   {"text": f"1mo high {info['level']:,} is {info['dist_pct']}% away", "type": "positive"},
                   {"text": f"20DMA rising {info['ma20_slope']}%/day, price above", "type": "positive"},
                   {"text": f"5d range coiled to {info['coil']}x monthly avg", "type": "positive"},
                   {"text": f"dip day {info['today']}% — buying weakness in trend", "type": "positive"}]}
        state["positions"]["SWING"].append(pos)
        j["pools"]["SWING"]["positions"].append(pos)
        print(f"  BUY {s:<12} x{qty:<5} @ {p:>10,.2f} = Rs{qty*p:>9,.0f}  "
              f"tgt {pos['target_price']:,} (level+2%)  sl {pos['sl_price']:,}  3-session clock")
    save_state(state)
    f.write_text(json.dumps(j, indent=2))
    print(f"  deployed. state + day file written -> dashboard picks it up on next /api/desk refresh")


def manage():
    state = load_state()
    poss = state["positions"]["SWING"]
    if not poss:
        print("  no open swings"); return
    px = quotes([p["symbol"] for p in poss])
    j, f = day_file()
    keep = []
    eod_pass = datetime.now().hour >= 15   # session counting at the 15:05 run
    for p in poss:
        cur = px.get(p["symbol"])
        if not cur:
            keep.append(p); continue
        sgn_pnl = (cur - p["entry_price"]) * p["qty"]
        reason = None
        if cur <= p["sl_price"]:
            reason = "STOPLOSS"
        elif cur >= p["target_price"]:
            reason = "TARGET"
        elif eod_pass and p.get("sessions_held", 0) + 1 >= MAX_HOLD_SESSIONS:
            reason = "TIME_3D"
        if reason:
            pct = (cur - p["entry_price"]) / p["entry_price"] * 100
            j["pools"]["SWING"]["closed"].append({**p, "exit_price": cur,
                "exit_time": datetime.now().strftime("%H:%M:%S"),
                "pnl": round(sgn_pnl, 2), "pnl_pct": round(pct, 2), "reason": reason})
            j["pools"]["SWING"]["pnl"] += sgn_pnl
            j["summary"]["total_pnl"] += sgn_pnl
            j["summary"]["trades"] += 1
            j["summary"]["wins" if sgn_pnl > 0 else "losses"] += 1
            print(f"  EXIT {p['symbol']:<12} @ {cur:,.2f} ({reason}) Rs{sgn_pnl:+,.0f} ({pct:+.2f}%)")
        else:
            if eod_pass:
                p["sessions_held"] = p.get("sessions_held", 0) + 1
            keep.append(p)
            print(f"  HOLD {p['symbol']:<12} @ {cur:,.2f} Rs{sgn_pnl:+,.0f} "
                  f"(session {p.get('sessions_held',0)}/{MAX_HOLD_SESSIONS})")
    state["positions"]["SWING"] = keep
    save_state(state)
    f.write_text(json.dumps(j, indent=2))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--backtest", action="store_true")
    ap.add_argument("--scan", action="store_true")
    ap.add_argument("--manage", action="store_true")
    a = ap.parse_args()
    if a.backtest:
        backtest(); return 0
    ok, detail = kd.token_alive()
    if not ok:
        print(f"  Kite token dead: {detail}"); return 2
    if a.scan:
        scan_and_deploy()
    if a.manage:
        manage()
    if not (a.scan or a.manage):
        print("  use --backtest, --scan or --manage")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
