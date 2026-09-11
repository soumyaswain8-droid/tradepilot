#!/usr/bin/env python3
"""Backtest every rule extracted from the five candlestick lessons on TradePilot's
own universe: 399 F&O/NIFTY-500 names, 5-minute bars 2026-07-13..2026-09-11 (45
sessions) plus one year of daily bars. One uniform exit model so patterns are
comparable; the opening-range strategies use the exits their lessons prescribe.

    python3 run.py            # writes results/*.json and results/summary.md

Exit model for candle patterns (lessons 1 and 2 both say 2:1):
  entry  = next bar's open after the signal bar (no look-ahead)
  stop   = the lesson's stop for that pattern
  target = entry + 2 * risk in the trade direction
  time   = flat at the last bar of the session (5m) or after 10 bars (daily)
  both hit in one bar -> counted as a stop (conservative)
  costs  = 12 bps round trip (the fleet cost model used by the shadow experiments)
  sizing = fixed 500 rupees of risk per trade, so rupee totals compare across patterns
"""
from __future__ import annotations
import json, sys, os, math, collections
import numpy as np
import pandas as pd

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", "..", ".."))
DATA = os.path.join(HERE, "..", "data")
OUT = os.path.join(HERE, "results")
os.makedirs(OUT, exist_ok=True)
sys.path.insert(0, HERE)
import candles as C  # noqa: E402

COST = 0.0012          # round trip
RISK_RS = 500.0        # rupees risked per trade
RR = 2.0               # reward-to-risk target
IST = "Asia/Kolkata"


# ------------------------------------------------------------------ data
def load_5m():
    # Pickles are written by our own downloader in ../data (same session, local, trusted) — not user-supplied input.
    b = pd.read_pickle(os.path.join(DATA, "bars_5m.pkl"))
    b = b.rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    ts = b.index.get_level_values("ts").tz_convert(IST)
    b.index = pd.MultiIndex.from_arrays([b.index.get_level_values("symbol"), ts], names=["symbol", "ts"])
    b = b[(ts.time >= pd.Timestamp("09:15").time()) & (ts.time <= pd.Timestamp("15:25").time())]
    b = b[(b["high"] > 0) & (b["low"] > 0)]
    return b


def load_1d():
    d = pd.read_pickle(os.path.join(DATA, "bars_1d.pkl")).rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
    d = d[(d["high"] > 0)]
    return d


def daily_context(d1):
    """Per symbol: prior-day high/low/close and 14-day ATR keyed by session date."""
    ctx = {}
    for sym, g in d1.groupby(level="symbol"):
        g = g.droplevel("symbol").sort_index()
        tr = np.maximum(g["high"] - g["low"], np.maximum((g["high"] - g["close"].shift()).abs(), (g["low"] - g["close"].shift()).abs()))
        atr = tr.rolling(14).mean()
        prev = g.shift()
        df = pd.DataFrame({"pdh": prev["high"], "pdl": prev["low"], "pdc": prev["close"], "atr": atr.shift()})
        df.index = pd.to_datetime(df.index).date
        ctx[sym] = df
    return ctx


# ------------------------------------------------------------------ exits
def walk(o, h, l, c, i0, direction, entry, stop, target, last):
    """Walk bars i0..last. Returns (exit_price, exit_index, reason)."""
    for i in range(i0, last + 1):
        if direction > 0:
            if l[i] <= stop:
                return (min(o[i], stop) if i == i0 else stop), i, "stop"
            if h[i] >= target:
                return target, i, "target"
        else:
            if h[i] >= stop:
                return (max(o[i], stop) if i == i0 else stop), i, "stop"
            if l[i] <= target:
                return target, i, "target"
    return c[last], last, "time"


def trade_result(direction, entry, exit_px, stop):
    risk = abs(entry - stop)
    if risk <= 0:
        return None
    gross_pct = direction * (exit_px - entry) / entry
    net_pct = gross_pct - COST
    qty = RISK_RS / risk
    rs = qty * (direction * (exit_px - entry)) - qty * entry * COST
    r_mult = (direction * (exit_px - entry)) / risk
    return {"net_pct": net_pct, "rs": rs, "r": r_mult}


# ------------------------------------------------------------------ pattern loop
def run_patterns(b5, ctx, tf="5m", first90=False, key_level=False, run_filter=0):
    """Returns list of trade dicts across all symbols/days."""
    trades = []
    for sym, g in b5.groupby(level="symbol"):
        g = g.droplevel("symbol")
        if tf == "15m":
            g = g.resample("15min", label="left", closed="left").agg({"open": "first", "high": "max", "low": "min", "close": "last", "volume": "sum"}).dropna()
        for day, gd in g.groupby(g.index.date):
            o, h, l, c = (gd[k].to_numpy(float) for k in ("open", "high", "low", "close"))
            n = len(o)
            if n < 10:
                continue
            times = gd.index
            cx = ctx.get(sym)
            lv = None
            if cx is not None and day in cx.index:
                row = cx.loc[day]
                lv = {"pdh": row["pdh"], "pdl": row["pdl"], "pdc": row["pdc"], "atr": row["atr"]}
            day_hi = np.maximum.accumulate(h)
            day_lo = np.minimum.accumulate(l)
            for name, (fn, lesson, kind) in C.PATTERNS.items():
                try:
                    sig, stop, direction = fn(o, h, l, c, run=run_filter) if "run" in fn.__code__.co_varnames else fn(o, h, l, c)
                except TypeError:
                    sig, stop, direction = fn(o, h, l, c)
                idx = np.flatnonzero(sig)
                for i in idx:
                    if i + 1 >= n:
                        continue
                    t = times[i]
                    if first90 and (t.hour * 60 + t.minute) > 10 * 60 + 45:
                        continue
                    if (t.hour * 60 + t.minute) >= 15 * 60 + 10:
                        continue
                    if key_level:
                        if lv is None or not np.isfinite(lv.get("atr", np.nan)):
                            continue
                        ext = l[i] if direction > 0 else h[i]
                        levels = [lv["pdh"], lv["pdl"], lv["pdc"], day_hi[i - 1] if i else np.nan, day_lo[i - 1] if i else np.nan]
                        band = 0.15 * lv["atr"]
                        if not any(np.isfinite(L) and abs(ext - L) <= band for L in levels):
                            continue
                    entry = o[i + 1]
                    st = stop[i]
                    if not np.isfinite(st) or (direction > 0 and st >= entry) or (direction < 0 and st <= entry):
                        continue
                    risk = abs(entry - st)
                    if risk / entry < 0.0005 or risk / entry > 0.03:   # sanity: 5 bps .. 3%
                        continue
                    target = entry + direction * RR * risk
                    exit_px, j, reason = walk(o, h, l, c, i + 1, direction, entry, st, target, n - 1)
                    res = trade_result(direction, entry, exit_px, st)
                    if res is None:
                        continue
                    trades.append({"pattern": name, "lesson": lesson, "kind": kind, "sym": sym, "day": str(day),
                                   "t": t.strftime("%H:%M"), "dir": direction, "entry": entry, "stop": st,
                                   "exit": exit_px, "reason": reason, "bars": int(j - i), **res})
    return trades


def run_patterns_daily(d1):
    trades = []
    for sym, g in d1.groupby(level="symbol"):
        g = g.droplevel("symbol").sort_index()
        o, h, l, c = (g[k].to_numpy(float) for k in ("open", "high", "low", "close"))
        n = len(o)
        dates = g.index
        for name, (fn, lesson, kind) in C.PATTERNS.items():
            try:
                sig, stop, direction = fn(o, h, l, c, run=3) if "run" in fn.__code__.co_varnames else fn(o, h, l, c)
            except TypeError:
                sig, stop, direction = fn(o, h, l, c)
            for i in np.flatnonzero(sig):
                if i + 1 >= n:
                    continue
                entry = o[i + 1]
                st = stop[i]
                if not np.isfinite(st) or (direction > 0 and st >= entry) or (direction < 0 and st <= entry):
                    continue
                risk = abs(entry - st)
                if risk / entry < 0.002 or risk / entry > 0.15:
                    continue
                target = entry + direction * RR * risk
                exit_px, j, reason = walk(o, h, l, c, i + 1, direction, entry, st, target, min(n - 1, i + 10))
                res = trade_result(direction, entry, exit_px, st)
                if res is None:
                    continue
                trades.append({"pattern": name, "lesson": lesson, "kind": kind, "sym": sym, "day": str(dates[i].date()),
                               "t": "1d", "dir": direction, "entry": entry, "stop": st, "exit": exit_px,
                               "reason": reason, "bars": int(j - i), **res})
    return trades


# ------------------------------------------------------------------ opening-range strategies
def opening_range(b5, ctx):
    """Lessons 3, 4, 5 and the ORB control, on 5-minute bars."""
    out = collections.defaultdict(list)
    for sym, g in b5.groupby(level="symbol"):
        g = g.droplevel("symbol")
        cx = ctx.get(sym)
        for day, gd in g.groupby(g.index.date):
            o, h, l, c = (gd[k].to_numpy(float) for k in ("open", "high", "low", "close"))
            n = len(o)
            if n < 20 or gd.index[0].strftime("%H:%M") != "09:15":
                continue
            lv = cx.loc[day] if (cx is not None and day in cx.index) else None
            atr = float(lv["atr"]) if lv is not None and np.isfinite(lv["atr"]) else np.nan
            pdh = float(lv["pdh"]) if lv is not None else np.nan
            pdl = float(lv["pdl"]) if lv is not None else np.nan
            pdc = float(lv["pdc"]) if lv is not None else np.nan
            body, rng, up, lo, green, red = C._parts(o, h, l, c)

            # ---------- Lesson 5: R1/R2 open = high / open = low on the first 5-min bar, exit 09:30
            tol = 0.001 * o[0]
            gap = (o[0] - pdc) / pdc if np.isfinite(pdc) and pdc > 0 else np.nan
            for rule, cond, direction in (("R1_open_eq_high_short", abs(o[0] - h[0]) <= tol and c[0] < o[0], -1),
                                          ("R2_open_eq_low_long", abs(o[0] - l[0]) <= tol and c[0] > o[0], 1)):
                if cond and n > 3:
                    entry = o[1]
                    for label, j in (("0930", 2), ("1015", 11), ("close", n - 1)):
                        ex = c[min(j, n - 1)]
                        gross = direction * (ex - entry) / entry
                        out[f"{rule}_exit{label}"].append({"sym": sym, "day": str(day), "dir": direction, "net_pct": gross - COST, "gap": gap,
                                                            "rs": RISK_RS * (gross - COST) / 0.005})  # 0.5% risk unit for comparability
            # R4 base rate: does the first bar's colour hold to 09:30?
            if n > 3 and c[0] != o[0]:
                first = np.sign(c[0] - o[0])
                hold = np.sign(c[2] - c[0])
                out["R4_first_bar_colour_holds_to_0930"].append({"sym": sym, "day": str(day), "hit": int(first == hold), "gap": gap})

            # ---------- Lesson 3: Q liquidity candle + reversal outside the box, target far edge
            if n > 21 and np.isfinite(atr) and atr > 0:
                box_hi, box_lo = h[:3].max(), l[:3].min()
                orange = box_hi - box_lo
                liq = orange >= 0.25 * atr
                move = np.sign(c[2] - o[0])
                out["Q1_liquidity_candle_rate"].append({"sym": sym, "day": str(day), "hit": int(liq), "ratio": orange / atr})
                if liq and move != 0:
                    done = False
                    for i in range(3, min(n - 1, 21)):            # up to 10:45
                        if move > 0 and c[i] > box_hi:
                            inv_h = (up[i] >= 2 * body[i]) & (lo[i] <= 0.35 * rng[i])
                            eng = red[i] and green[i - 1] and o[i] >= c[i - 1] and c[i] <= o[i - 1]
                            if inv_h or eng:
                                entry, st, direction = o[i + 1], h[i], -1
                                tgt_box = box_lo
                                if st > entry:
                                    for label, tgt in (("box", tgt_box), ("2R", entry - RR * (st - entry))):
                                        ex, j, why = walk(o, h, l, c, i + 1, direction, entry, st, tgt, n - 1)
                                        r = trade_result(direction, entry, ex, st)
                                        if r:
                                            out[f"Q2_reversal_short_target_{label}"].append({"sym": sym, "day": str(day), "t": gd.index[i].strftime("%H:%M"), "dir": -1, "reason": why, **r})
                                done = True
                                break
                        if move < 0 and c[i] < box_lo:
                            ham = (lo[i] >= 2 * body[i]) & (up[i] <= 0.35 * rng[i])
                            eng = green[i] and red[i - 1] and o[i] <= c[i - 1] and c[i] >= o[i - 1]
                            if ham or eng:
                                entry, st, direction = o[i + 1], l[i], 1
                                if st < entry:
                                    for label, tgt in (("box", box_hi), ("2R", entry + RR * (entry - st))):
                                        ex, j, why = walk(o, h, l, c, i + 1, direction, entry, st, tgt, n - 1)
                                        r = trade_result(direction, entry, ex, st)
                                        if r:
                                            out[f"Q3_reversal_long_target_{label}"].append({"sym": sym, "day": str(day), "t": gd.index[i].strftime("%H:%M"), "dir": 1, "reason": why, **r})
                                done = True
                                break
                    # Q5 control: ORB continuation, first close beyond the box after 09:30 in the opening direction
                    for i in range(3, min(n - 1, 21)):
                        if move > 0 and c[i] > box_hi:
                            entry, st, direction = o[i + 1], box_lo + orange / 2, 1
                        elif move < 0 and c[i] < box_lo:
                            entry, st, direction = o[i + 1], box_hi - orange / 2, -1
                        else:
                            continue
                        if (direction > 0 and st < entry) or (direction < 0 and st > entry):
                            tgt = entry + direction * RR * abs(entry - st)
                            ex, j, why = walk(o, h, l, c, i + 1, direction, entry, st, tgt, n - 1)
                            r = trade_result(direction, entry, ex, st)
                            if r:
                                out["Q5_control_ORB_continuation_2R"].append({"sym": sym, "day": str(day), "dir": direction, "reason": why, **r})
                        break

            # ---------- Lesson 4: S sneaky pivot at prior-day high/low on 15-minute bars
            if n > 12 and np.isfinite(pdh) and np.isfinite(pdl) and np.isfinite(atr) and atr > 0:
                # 15-minute bars from 5-minute
                m = n // 3
                O = o[:m * 3].reshape(m, 3)[:, 0]; H = h[:m * 3].reshape(m, 3).max(1); L = l[:m * 3].reshape(m, 3).min(1); Cc = c[:m * 3].reshape(m, 3)[:, 2]
                band = 0.25 * atr
                if L[0] <= pdl + band:                       # opening bar reached the range low
                    for k in (1, 2):                          # sneaky candle within 2 bars
                        if k < m and Cc[k] > O[k]:
                            for e in range(k + 1, min(m, k + 4)):   # entry within next 45 min
                                if H[e] > H[k]:
                                    entry, st, direction = max(H[k], O[e]), L[:e].min(), 1
                                    if st < entry:
                                        # walk on 5-min bars from the start of 15-min bar e
                                        i0 = e * 3
                                        for label, tgt in (("PDH", pdh), ("2R", entry + RR * (entry - st))):
                                            ex, j, why = walk(o, h, l, c, i0, direction, entry, st, tgt, n - 1)
                                            r = trade_result(direction, entry, ex, st)
                                            if r:
                                                out[f"S1_sneaky_long_at_PDL_target_{label}"].append({"sym": sym, "day": str(day), "dir": 1, "reason": why, **r})
                                    break
                            break
                if H[0] >= pdh - band:
                    for k in (1, 2):
                        if k < m and Cc[k] < O[k]:
                            for e in range(k + 1, min(m, k + 4)):
                                if L[e] < L[k]:
                                    entry, st, direction = min(L[k], O[e]), H[:e].max(), -1
                                    if st > entry:
                                        i0 = e * 3
                                        for label, tgt in (("PDL", pdl), ("2R", entry - RR * (st - entry))):
                                            ex, j, why = walk(o, h, l, c, i0, direction, entry, st, tgt, n - 1)
                                            r = trade_result(direction, entry, ex, st)
                                            if r:
                                                out[f"S2_sneaky_short_at_PDH_target_{label}"].append({"sym": sym, "day": str(day), "dir": -1, "reason": why, **r})
                                    break
                            break
    return out


# ------------------------------------------------------------------ engine overlay
def engine_overlay(b5):
    """Tag every v5 / v5_wide closed trade of the last 30 sessions with the candle
    patterns that completed on its entry bar or the bar before, and sum P&L by tag."""
    import glob
    rows = []
    for f in sorted(glob.glob(os.path.join(ROOT, "docs", "paper-trades", "v5*", "2026-0[89]-*.json"))):
        eng = os.path.basename(os.path.dirname(f))
        if eng not in ("v5", "v5_wide"):
            continue
        day = os.path.basename(f)[:10]
        if day < "2026-08-11":
            continue
        try:
            d = json.load(open(f))
        except Exception:
            continue
        for pool, p in (d.get("pools") or {}).items():
            for t in p.get("closed") or []:
                rows.append({"engine": eng, "day": day, "pool": pool, **t})
    if not rows:
        return {}
    cache = {}
    tagged = []
    for t in rows:
        sym = f"{t['symbol']}.NS"
        if sym not in b5.index.get_level_values("symbol"):
            continue
        key = (sym, t["day"])
        if key not in cache:
            g = b5.loc[sym]
            gd = g[g.index.date == pd.Timestamp(t["day"]).date()]
            if len(gd) < 10:
                cache[key] = None
            else:
                o, h, l, c = (gd[k].to_numpy(float) for k in ("open", "high", "low", "close"))
                sigs = {}
                for name, (fn, lesson, kind) in C.PATTERNS.items():
                    try:
                        s, st, dr = fn(o, h, l, c, run=0) if "run" in fn.__code__.co_varnames else fn(o, h, l, c)
                    except TypeError:
                        s, st, dr = fn(o, h, l, c)
                    sigs[name] = (s, dr)
                cache[key] = (gd.index, sigs)
        if cache[key] is None:
            continue
        times, sigs = cache[key]
        et = t.get("entry_time") or ""
        try:
            hh, mm = int(et[:2]), int(et[3:5])
        except Exception:
            continue
        emin = hh * 60 + mm
        idx = [i for i, ts in enumerate(times) if ts.hour * 60 + ts.minute <= emin]
        if not idx:
            continue
        i = idx[-1]
        tdir = -1 if (t.get("position_type") or "").upper() == "SHORT" else 1
        agree, oppose = [], []
        for name, (s, dr) in sigs.items():
            if s[i] or (i > 0 and s[i - 1]):
                (agree if dr == tdir else oppose).append(name)
        pnl = float(t.get("pnl_net", t.get("pnl", 0)) or 0)
        tag = "opposing" if oppose else ("agreeing" if agree else "none")
        tagged.append({"engine": t["engine"], "day": t["day"], "sym": t["symbol"], "dir": tdir, "pnl": pnl, "tag": tag, "agree": agree, "oppose": oppose})
    summary = {}
    for eng in ("v5", "v5_wide", "both"):
        sub = [x for x in tagged if eng == "both" or x["engine"] == eng]
        for tag in ("agreeing", "opposing", "none"):
            xs = [x for x in sub if x["tag"] == tag]
            if xs:
                summary[f"{eng}:{tag}"] = {"n": len(xs), "pnl": round(sum(x["pnl"] for x in xs), 0), "win": round(100 * sum(1 for x in xs if x["pnl"] > 0) / len(xs))}
    # per opposing pattern
    per = collections.defaultdict(lambda: [0, 0.0])
    for x in tagged:
        for nm in x["oppose"]:
            per[nm][0] += 1; per[nm][1] += x["pnl"]
    summary["opposing_by_pattern"] = {k: {"n": v[0], "pnl": round(v[1])} for k, v in sorted(per.items(), key=lambda kv: kv[1][1])}
    json.dump(tagged, open(os.path.join(OUT, "engine_overlay_trades.json"), "w"))
    return summary


# ------------------------------------------------------------------ summarise
def summarise(trades, keys=("pattern",)):
    df = pd.DataFrame(trades)
    if df.empty:
        return pd.DataFrame()
    g = df.groupby(list(keys))
    s = pd.DataFrame({
        "n": g.size(),
        "win%": (g["net_pct"].apply(lambda x: 100 * (x > 0).mean())).round(0),
        "avg_R": g["r"].mean().round(2) if "r" in df else np.nan,
        "exp_bps": (g["net_pct"].mean() * 1e4).round(1),
        "total_rs@500risk": g["rs"].sum().round(0) if "rs" in df else np.nan,
        "stop%": g["reason"].apply(lambda x: 100 * (x == "stop").mean()).round(0) if "reason" in df else np.nan,
        "target%": g["reason"].apply(lambda x: 100 * (x == "target").mean()).round(0) if "reason" in df else np.nan,
    })
    return s.sort_values("total_rs@500risk", ascending=False) if "total_rs@500risk" in s else s


def main():
    print("loading", flush=True)
    b5 = load_5m()
    d1 = load_1d()
    ctx = daily_context(d1)
    print("5m bars", len(b5), "symbols", b5.index.get_level_values("symbol").nunique(), flush=True)

    results = {}
    variants = [
        ("5m_all_day", dict(tf="5m")),
        ("5m_first90", dict(tf="5m", first90=True)),
        ("5m_trend_run3", dict(tf="5m", run_filter=3)),
        ("5m_key_level", dict(tf="5m", key_level=True)),
        ("5m_key_level_first90", dict(tf="5m", key_level=True, first90=True)),
        ("15m_all_day", dict(tf="15m")),
    ]
    for name, kw in variants:
        print("patterns", name, flush=True)
        tr = run_patterns(b5, ctx, **kw)
        json.dump(tr, open(os.path.join(OUT, f"trades_{name}.json"), "w"))
        results[name] = summarise(tr)
        print(results[name].to_string(), flush=True)

    print("patterns daily", flush=True)
    trd = run_patterns_daily(d1)
    json.dump(trd, open(os.path.join(OUT, "trades_1d.json"), "w"))
    results["1d"] = summarise(trd)
    print(results["1d"].to_string(), flush=True)

    print("opening range", flush=True)
    orr = opening_range(b5, ctx)
    or_summary = {}
    for k, v in orr.items():
        df = pd.DataFrame(v)
        if "hit" in df:
            or_summary[k] = {"n": len(df), "rate%": round(100 * df["hit"].mean(), 1)}
            if "ratio" in df:
                or_summary[k]["median_ratio"] = round(float(df["ratio"].median()), 2)
        else:
            row = {"n": len(df), "win%": round(100 * (df["net_pct"] > 0).mean()), "exp_bps": round(float(df["net_pct"].mean() * 1e4), 1)}
            if "rs" in df:
                row["total_rs@500risk"] = round(float(df["rs"].sum()))
            if "r" in df:
                row["avg_R"] = round(float(df["r"].mean()), 2)
            if "reason" in df:
                row["stop%"] = round(100 * (df["reason"] == "stop").mean()); row["target%"] = round(100 * (df["reason"] == "target").mean())
            if "gap" in df:
                top = df[df["gap"].abs() >= df["gap"].abs().quantile(0.9)]
                if len(top):
                    row["top10%gappers"] = {"n": len(top), "win%": round(100 * (top["net_pct"] > 0).mean()), "exp_bps": round(float(top["net_pct"].mean() * 1e4), 1)}
            or_summary[k] = row
    json.dump(or_summary, open(os.path.join(OUT, "opening_range.json"), "w"), indent=1)
    print(json.dumps(or_summary, indent=1), flush=True)

    print("engine overlay", flush=True)
    ov = engine_overlay(b5)
    json.dump(ov, open(os.path.join(OUT, "engine_overlay.json"), "w"), indent=1)
    print(json.dumps(ov, indent=1), flush=True)

    with open(os.path.join(OUT, "summary.md"), "w") as f:
        f.write("# Candle backtest summary\n\n")
        for name, s in results.items():
            f.write(f"## {name}\n\n{s.to_markdown()}\n\n")
        f.write("## Opening-range strategies\n\n```json\n" + json.dumps(or_summary, indent=1) + "\n```\n\n")
        f.write("## Engine overlay\n\n```json\n" + json.dumps(ov, indent=1) + "\n```\n")
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
