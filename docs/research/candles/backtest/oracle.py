#!/usr/bin/env python3
"""Hindsight study: where SHOULD we have entered and exited, and what candle was there?

For every stock and every session:
  1. find the decent intraday swings with a zigzag (reversal threshold THR of price),
     so each swing is an ideal trade: enter at the turning-point bar, exit at the next
     turning point, long or short;
  2. name the candle BEFORE, AT and AFTER the entry turning point (and the exit), using
     the single-candle vocabulary of the lessons, and list every multi-bar pattern from
     candles.py that completed within one bar of the turning point;
  3. compare how often each candle name appears at ideal turning points against how
     often it appears anywhere (base rate) -> lift. Lift 1.0 = no information.
  4. measure the practical version: enter at the open of the bar after the confirmation
     bar (the lessons' candle-over-candle rule) and see how much of the swing is left.

    python3 oracle.py [--thr 0.008] [--data ../data/bars_5m.pkl]

Writes results/oracle_trades.json, results/oracle_summary.json, ../oracle/daily/<date>.md
and ../oracle/charts/<date>_<symbol>.png (top opportunities per day, marked).
"""
from __future__ import annotations
import os, sys, json, argparse, collections
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import candles as C  # noqa: E402
from run import load_5m, load_1d, daily_context, COST, IST  # noqa: E402

RES = os.path.join(HERE, "results")
ORA = os.path.abspath(os.path.join(HERE, "..", "oracle"))
os.makedirs(os.path.join(ORA, "daily"), exist_ok=True)
os.makedirs(os.path.join(ORA, "charts"), exist_ok=True)


# ------------------------------------------------------------------ candle names
def classify(o, h, l, c, med_rng):
    """Single-candle name for every bar, from the lessons' vocabulary."""
    body = np.abs(c - o); rng = np.maximum(h - l, 1e-9)
    up = h - np.maximum(o, c); lo = np.minimum(o, c) - l
    br, ur, lr = body / rng, up / rng, lo / rng
    big = rng >= med_rng
    names = []
    for i in range(len(o)):
        g = c[i] >= o[i]
        col = "green" if g else "red"
        if br[i] <= 0.1:
            if lr[i] >= 0.6: n = "dragonfly doji"
            elif ur[i] >= 0.6: n = "gravestone doji"
            elif lr[i] >= 0.3 and ur[i] >= 0.3: n = "long-legged doji"
            else: n = "doji"
        elif lr[i] >= 0.6 and ur[i] <= 0.15 and br[i] <= 0.4:
            n = f"hammer shape ({col})"
        elif ur[i] >= 0.6 and lr[i] <= 0.15 and br[i] <= 0.4:
            n = f"inverted hammer shape ({col})"
        elif br[i] >= 0.85:
            n = f"marubozu {col}"
        elif br[i] >= 0.6 and big[i]:
            n = f"long body {col}"
        elif br[i] <= 0.3 and lr[i] >= 0.25 and ur[i] >= 0.25:
            n = "spinning top"
        elif br[i] <= 0.3:
            n = f"small body {col}"
        else:
            n = f"normal {col}"
        names.append(n)
    return names


# ------------------------------------------------------------------ zigzag
def zigzag(h, l, thr):
    """Alternating pivots [(idx, price, 'H'|'L'), ...] using highs for peaks and lows
    for troughs. A peak is confirmed when a later low is thr below it, and so on."""
    n = len(h)
    if n < 5:
        return []
    piv = []
    trend = 0            # +1 rising (tracking a high), -1 falling (tracking a low)
    hi_i, hi = 0, h[0]
    lo_i, lo = 0, l[0]
    for i in range(1, n):
        if trend >= 0:
            if h[i] > hi:
                hi_i, hi = i, h[i]
            if l[i] <= hi * (1 - thr):
                if trend == 0 and lo <= hi:   # starting: decide which came first
                    pass
                piv.append((hi_i, hi, "H"))
                trend = -1
                lo_i, lo = i, l[i]
                continue
        if trend <= 0:
            if l[i] < lo:
                lo_i, lo = i, l[i]
            if h[i] >= lo * (1 + thr):
                piv.append((lo_i, lo, "L"))
                trend = 1
                hi_i, hi = i, h[i]
    # close the last leg at its extreme
    if trend == 1:
        piv.append((hi_i, hi, "H"))
    elif trend == -1:
        piv.append((lo_i, lo, "L"))
    # drop a duplicated first pivot type
    out = []
    for p in piv:
        if out and out[-1][2] == p[2]:
            if (p[2] == "H" and p[1] > out[-1][1]) or (p[2] == "L" and p[1] < out[-1][1]):
                out[-1] = p
            continue
        out.append(p)
    return out


# ------------------------------------------------------------------ charts
def draw(sym, day, gd, trades, names, path):
    o, h, l, c = (gd[k].to_numpy(float) for k in ("open", "high", "low", "close"))
    x = np.arange(len(o))
    fig, ax = plt.subplots(figsize=(13, 6))
    for i in range(len(o)):
        col = "#16a34a" if c[i] >= o[i] else "#dc2626"
        ax.vlines(x[i], l[i], h[i], color=col, lw=1)
        ax.add_patch(plt.Rectangle((x[i] - 0.35, min(o[i], c[i])), 0.7, max(abs(c[i] - o[i]), 1e-9), facecolor=col if c[i] < o[i] else "white", edgecolor=col, lw=1.2))
    for t in trades:
        ei, xi = t["entry_i"], t["exit_i"]
        ey, xy = t["entry"], t["exit"]
        if t["dir"] > 0:
            ax.annotate("", xy=(ei, ey), xytext=(ei, ey - (h.max() - l.min()) * 0.06), arrowprops=dict(arrowstyle="-|>", color="#16a34a", lw=2.5))
            ax.text(ei, ey - (h.max() - l.min()) * 0.075, f"BUY {gd.index[ei].strftime('%H:%M')}\n{names[ei]}", ha="center", va="top", fontsize=7.5, color="#16a34a")
        else:
            ax.annotate("", xy=(ei, ey), xytext=(ei, ey + (h.max() - l.min()) * 0.06), arrowprops=dict(arrowstyle="-|>", color="#16a34a", lw=2.5))
            ax.text(ei, ey + (h.max() - l.min()) * 0.075, f"SELL {gd.index[ei].strftime('%H:%M')}\n{names[ei]}", ha="center", va="bottom", fontsize=7.5, color="#16a34a")
        off = (h.max() - l.min()) * 0.06 * (1 if t["dir"] > 0 else -1)
        ax.annotate("", xy=(xi, xy), xytext=(xi, xy + off), arrowprops=dict(arrowstyle="-|>", color="#7c3aed", lw=2.5))
        ax.text(xi, xy + off * 1.25, f"EXIT {gd.index[xi].strftime('%H:%M')} {t['move_pct']:+.2f}%\n{names[xi]}", ha="center", va="bottom" if t["dir"] > 0 else "top", fontsize=7.5, color="#7c3aed")
    ticks = list(range(0, len(o), 6))
    ax.set_xticks(ticks); ax.set_xticklabels([gd.index[i].strftime("%H:%M") for i in ticks], rotation=0, fontsize=8)
    ax.set_title(f"{sym.replace('.NS','')} · {day} · ideal entries (green) and exits (purple), 5-minute bars", color="#1e1b4b")
    ax.grid(alpha=0.2)
    fig.tight_layout(); fig.savefig(path, dpi=130); plt.close(fig)


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--thr", type=float, default=0.008, help="minimum swing as a fraction of price (0.008 = 0.8%)")
    ap.add_argument("--data", default=None, help="alternative bars pickle (e.g. Kite 3-month file)")
    ap.add_argument("--charts-per-day", type=int, default=2)
    args = ap.parse_args()

    if args.data:
        import run as R
        R.DATA = os.path.dirname(os.path.abspath(args.data))
        # local pickle written by our own downloader/fetcher in this repo — trusted, not user input
        b5 = pd.read_pickle(args.data).rename(columns=str.lower)[["open", "high", "low", "close", "volume"]]
        ts = b5.index.get_level_values("ts")
        if ts.tz is None:
            ts = ts.tz_localize(IST)
        else:
            ts = ts.tz_convert(IST)
        b5.index = pd.MultiIndex.from_arrays([b5.index.get_level_values("symbol"), ts], names=["symbol", "ts"])
        b5 = b5[(ts.time >= pd.Timestamp("09:15").time()) & (ts.time <= pd.Timestamp("15:25").time())]
    else:
        b5 = load_5m()
    print("bars", len(b5), "symbols", b5.index.get_level_values("symbol").nunique(), flush=True)

    trades = []
    base = collections.Counter(); base_n = 0
    at_entry = collections.Counter(); before_entry = collections.Counter(); after_entry = collections.Counter()
    at_exit = collections.Counter(); before_exit = collections.Counter()
    pat_entry = collections.Counter(); pat_entry_dir = collections.Counter()
    pat_base = collections.Counter()
    per_day = collections.defaultdict(list)
    day_frames = {}

    for sym, g in b5.groupby(level="symbol"):
        g = g.droplevel("symbol")
        for day, gd in g.groupby(g.index.date):
            o, h, l, c = (gd[k].to_numpy(float) for k in ("open", "high", "low", "close"))
            n = len(o)
            if n < 30:
                continue
            rng = np.maximum(h - l, 1e-9)
            names = classify(o, h, l, c, np.median(rng))
            base.update(names); base_n += n
            # multi-bar patterns completing at each bar
            comp = collections.defaultdict(list)
            for pname, (fn, lesson, kind) in C.PATTERNS.items():
                try:
                    s, st, d = fn(o, h, l, c, run=0) if "run" in fn.__code__.co_varnames else fn(o, h, l, c)
                except TypeError:
                    s, st, d = fn(o, h, l, c)
                for i in np.flatnonzero(s):
                    comp[i].append((pname, d))
                    pat_base[pname] += 1
            piv = zigzag(h, l, args.thr)
            day_trades = []
            for a, b in zip(piv, piv[1:]):
                ei, ep, et = a; xi, xp, xt = b
                if xi - ei < 2 or ei < 1 or xi >= n - 1:
                    continue
                d = 1 if et == "L" else -1
                move = d * (xp - ep) / ep
                if move < args.thr:
                    continue
                # practical entry: open of the bar after the confirmation bar (candle over/under candle)
                conf = None
                for j in range(ei + 1, min(xi, ei + 4)):
                    if (d > 0 and h[j] > h[ei]) or (d < 0 and l[j] < l[ei]):
                        conf = j; break
                prac_entry = o[conf + 1] if conf is not None and conf + 1 < n else np.nan
                prac_move = d * (xp - prac_entry) / prac_entry - COST if np.isfinite(prac_entry) else np.nan
                pats = [(p, dd) for k in (ei - 1, ei, ei + 1) for (p, dd) in comp.get(k, [])]
                t = {"sym": sym, "day": str(day), "dir": d, "entry_i": int(ei), "exit_i": int(xi),
                     "entry_t": gd.index[ei].strftime("%H:%M"), "exit_t": gd.index[xi].strftime("%H:%M"),
                     "entry": float(ep), "exit": float(xp), "move_pct": round(100 * move, 2), "bars": int(xi - ei),
                     "before_entry": names[ei - 1], "at_entry": names[ei], "after_entry": names[ei + 1],
                     "before_exit": names[xi - 1], "at_exit": names[xi],
                     "patterns_at_entry": [p for p, dd in pats], "patterns_agree": [p for p, dd in pats if dd == d],
                     "confirm_bar": int(conf) if conf is not None else None,
                     "practical_move_pct": round(100 * prac_move, 2) if np.isfinite(prac_move) else None}
                trades.append(t); day_trades.append(t)
                at_entry[(d, names[ei])] += 1; before_entry[(d, names[ei - 1])] += 1; after_entry[(d, names[ei + 1])] += 1
                at_exit[(d, names[xi])] += 1; before_exit[(d, names[xi - 1])] += 1
                for p, dd in pats:
                    pat_entry[p] += 1
                    if dd == d:
                        pat_entry_dir[p] += 1
            if day_trades:
                per_day[str(day)].extend(day_trades)
                day_frames[(sym, str(day))] = (gd, names)
        print(sym, "done", len(trades), flush=True) if sym.endswith("0ONE.NS") or len(trades) % 5000 < 3 else None

    print("ideal trades", len(trades), flush=True)
    json.dump(trades, open(os.path.join(RES, "oracle_trades.json"), "w"))

    # ---------------- lifts
    def lift_table(counter, direction):
        tot = sum(v for (d, nm), v in counter.items() if d == direction)
        rows = []
        for (d, nm), v in counter.items():
            if d != direction:
                continue
            share = v / tot if tot else 0
            b = base[nm] / base_n if base_n else 0
            rows.append({"candle": nm, "n": v, "share%": round(100 * share, 1), "base%": round(100 * b, 1), "lift": round(share / b, 2) if b else None})
        return sorted(rows, key=lambda r: -r["n"])
    n_pat_entry_total = len(trades)
    pat_rows = []
    for p in C.PATTERNS:
        obs = pat_entry.get(p, 0); agree = pat_entry_dir.get(p, 0)
        # base: probability a random bar has this pattern completing within a 3-bar window
        pb = 3 * pat_base.get(p, 0) / base_n if base_n else 0
        po = obs / n_pat_entry_total if n_pat_entry_total else 0
        pat_rows.append({"pattern": p, "at_ideal_entries": obs, "agreeing_direction": agree, "share%": round(100 * po, 2), "base%": round(100 * pb, 2), "lift": round(po / pb, 2) if pb else None})
    pat_rows.sort(key=lambda r: -(r["lift"] or 0))

    df = pd.DataFrame(trades)
    summary = {
        "thr_pct": 100 * args.thr, "sessions": int(df["day"].nunique()) if len(df) else 0, "symbols": int(df["sym"].nunique()) if len(df) else 0,
        "ideal_trades": len(trades), "longs": int((df["dir"] > 0).sum()) if len(df) else 0, "shorts": int((df["dir"] < 0).sum()) if len(df) else 0,
        "median_move_pct": float(df["move_pct"].median()) if len(df) else None, "mean_move_pct": float(df["move_pct"].mean()) if len(df) else None,
        "per_symbol_day": round(len(trades) / max(1, len(day_frames)), 2),
        "practical": {"n": int(df["practical_move_pct"].notna().sum()) if len(df) else 0,
                      "median_pct": float(df["practical_move_pct"].median()) if len(df) else None,
                      "win%": round(100 * float((df["practical_move_pct"] > 0).mean()), 1) if len(df) else None,
                      "captured_share%": round(100 * float((df["practical_move_pct"].dropna() / df.loc[df["practical_move_pct"].notna(), "move_pct"]).median()), 1) if len(df) else None},
        "entry_candle_long": lift_table(at_entry, 1), "entry_candle_short": lift_table(at_entry, -1),
        "before_entry_long": lift_table(before_entry, 1), "before_entry_short": lift_table(before_entry, -1),
        "after_entry_long": lift_table(after_entry, 1), "after_entry_short": lift_table(after_entry, -1),
        "exit_candle_long": lift_table(at_exit, 1), "exit_candle_short": lift_table(at_exit, -1),
        "before_exit_long": lift_table(before_exit, 1), "before_exit_short": lift_table(before_exit, -1),
        "patterns_at_entry": pat_rows,
        "base_candles": {k: round(100 * v / base_n, 2) for k, v in base.most_common()},
        "base_bars": int(base_n), "base_counts": dict(base), "pattern_base_counts": dict(pat_base),
        "hour_of_entry": {str(k): int(v) for k, v in df["entry_t"].str[:2].value_counts().sort_index().items()} if len(df) else {},
    }
    json.dump(summary, open(os.path.join(RES, "oracle_summary.json"), "w"), indent=1)

    # ---------------- per-day markdown + charts
    for day in sorted(per_day):
        rows = sorted(per_day[day], key=lambda t: -t["move_pct"])
        with open(os.path.join(ORA, "daily", f"{day}.md"), "w") as f:
            f.write(f"# {day}: where the money was\n\n{len(rows)} ideal swings ≥ {100*args.thr:.1f}% across {len({t['sym'] for t in rows})} stocks. Top 25 by size.\n\n")
            f.write("| stock | side | entry | exit | move | bars | candle before entry | candle at entry | confirmation | patterns at entry | candle at exit | practical |\n|---|---|---|---|---:|---:|---|---|---|---|---|---:|\n")
            for t in rows[:25]:
                f.write(f"| {t['sym'].replace('.NS','')} | {'LONG' if t['dir']>0 else 'SHORT'} | {t['entry_t']} @ {t['entry']:.2f} | {t['exit_t']} @ {t['exit']:.2f} | {t['move_pct']:+.2f}% | {t['bars']} | {t['before_entry']} | {t['at_entry']} | {t['after_entry']} | {', '.join(t['patterns_agree']) or '-'} | {t['at_exit']} | {t['practical_move_pct'] if t['practical_move_pct'] is not None else '-'} |\n")
        # charts: top N stocks of the day, all their swings on one chart each
        seen = []
        for t in rows:
            if t["sym"] in seen:
                continue
            seen.append(t["sym"])
            if len(seen) > args.charts_per_day:
                break
            gd, names = day_frames[(t["sym"], day)]
            draw(t["sym"], day, gd, [x for x in rows if x["sym"] == t["sym"]], names, os.path.join(ORA, "charts", f"{day}_{t['sym'].replace('.NS','')}.png"))
    print("DONE", flush=True)


if __name__ == "__main__":
    main()
