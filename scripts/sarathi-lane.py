#!/usr/bin/env python3
"""
sarathi-lane — the agent-read lane. Rs1,000 paper, charts read by Sarathi.

BORN 2026-08-24 (Soumya): the engines score with six backward-looking features; this
lane asks whether an agent READING THE CHART — structure, levels, wicks, volume,
context — calls better trades than mechanised predicates did.

WHY THIS IS NOT A REPEAT OF THE SMC RUN
We already measured those concepts mechanically (145,500 trades): liquidity sweeps,
FVG, order blocks, AMD, SMT, MTF — none cleared the toll, and MTF (my "strong prior")
came 9th of 10. What was NOT tested is holistic reading: a judgement that weighs where
price sits, what the structure is, and whether independent reads AGREE — the one
finding that was monotonically positive (gross rose from -0.16% at 1 agreeing
predicate to +0.084% at 7). This lane tests that, under the same gate.

HOW IT WORKS
  --watch    builds the candidate list (Rs1k-tradeable band + engine interest) and
             RENDERS each as a candlestick PNG with volume, VWAP, PDH/PDL and swing
             levels marked — so the agent can actually LOOK at the chart, not just
             read numbers. Also dumps the computed technicals as JSON.
  --enter    records the agent's call: symbol, entry, stop (the invalidation PRICE,
             not a percentage), target in R, and the written reasoning + confidence.
  --check    re-renders open positions for a management decision.
  --exit     closes with the agent's reason.

THE R-MULTIPLE CONVENTION (what "1.5x / 2x" means here)
Targets are multiples of RISK, not of capital: risk = entry - invalidation. A 1.5R
target on a Rs2 risk is Rs3 of reward. Equity intraday does not deliver 2x capital in
a day; 1.5-2R on a well-placed stop is the real version of that ambition.

THE GATE (pre-registered): >=20 agent-called trades, net > 0 after 0.106% fees, and
beating a random entry on the same names/days. Fails -> the lane closes.
"""
from __future__ import annotations

import argparse, json, sys, warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from prototype.v4 import kite_data as kd

ENGINE = "sarathi"
DIR = ROOT / "docs" / "paper-trades" / ENGINE
CHARTS = ROOT / "docs" / "sarathi" / "charts"
CAPITAL, LEVERAGE = 1000.0, 4.0
MIN_PRICE, MAX_PRICE, MIN_QTY = 80.0, 800.0, 5
MAX_SPREAD_BPS = 15.0
TIME_STOP = "14:45"
FEE_PCT = 0.106


def load():
    f = DIR / "lane_state.json"
    return json.loads(f.read_text()) if f.exists() else {"open": [], "history": []}


def save(s):
    DIR.mkdir(parents=True, exist_ok=True)
    (DIR / "lane_state.json").write_text(json.dumps(s, indent=2))


def bars(sym, interval="5minute", days=3):
    tok = kd.token_for(sym)
    if not tok:
        return []
    return kd.client().historical_data(
        tok, datetime.now() - timedelta(days=days), datetime.now(), interval)


def technicals(b5, bday):
    """The numbers behind the picture — computed only from CLOSED bars."""
    import statistics as st
    if len(b5) < 30:
        return {}
    c = [float(x["close"]) for x in b5]
    h = [float(x["high"]) for x in b5]
    l = [float(x["low"]) for x in b5]
    v = [float(x.get("volume") or 0) for x in b5]
    today = [x for x in b5 if str(x["date"])[:10] == str(b5[-1]["date"])[:10]]
    tv = sum(float(x.get("volume") or 0) for x in today) or 1
    vwap = sum(float(x["close"]) * float(x.get("volume") or 0) for x in today) / tv
    prev_day = [x for x in b5 if str(x["date"])[:10] != str(b5[-1]["date"])[:10]]
    pdh = max((float(x["high"]) for x in prev_day), default=None)
    pdl = min((float(x["low"]) for x in prev_day), default=None)
    # swings (fractal k=2) on the 5m
    sw_h, sw_l = [], []
    for i in range(2, len(b5) - 2):
        if h[i] == max(h[i-2:i+3]):
            sw_h.append((str(b5[i]["date"])[11:16], h[i]))
        if l[i] == min(l[i-2:i+3]):
            sw_l.append((str(b5[i]["date"])[11:16], l[i]))
    last = c[-1]
    dvol = [float(x.get("volume") or 0) for x in bday] if bday else []
    return {
        "last": round(last, 2),
        "vwap": round(vwap, 2),
        "vs_vwap_pct": round((last / vwap - 1) * 100, 2) if vwap else None,
        "day_open": round(float(today[0]["open"]), 2) if today else None,
        "day_high": round(max(float(x["high"]) for x in today), 2) if today else None,
        "day_low": round(min(float(x["low"]) for x in today), 2) if today else None,
        "pdh": round(pdh, 2) if pdh else None,
        "pdl": round(pdl, 2) if pdl else None,
        "recent_swing_highs": [(t, round(p, 2)) for t, p in sw_h[-4:]],
        "recent_swing_lows": [(t, round(p, 2)) for t, p in sw_l[-4:]],
        "last5_bars": [{"t": str(x["date"])[11:16], "o": float(x["open"]),
                        "h": float(x["high"]), "l": float(x["low"]),
                        "c": float(x["close"]), "v": int(x.get("volume") or 0)}
                       for x in b5[-5:]],
        "vol_last_vs_avg": round(v[-1] / (st.mean(v[-20:]) or 1), 2),
        "day_range_pct": round((max(float(x["high"]) for x in today) /
                                min(float(x["low"]) for x in today) - 1) * 100, 2)
                          if today else None,
        "atr14_pct": round(st.mean([h[i] - l[i] for i in range(-14, 0)]) / last * 100, 2),
    }


def render(sym, b5, tech, out):
    """Candlestick + volume PNG with VWAP / PDH / PDL / swings drawn, so the agent
    reads the same picture a human would — the point of this lane."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    b = b5[-90:]
    if len(b) < 10:
        return None
    fig, (ax, av) = plt.subplots(2, 1, figsize=(13, 7), sharex=True,
                                 gridspec_kw={"height_ratios": [3, 1]},
                                 facecolor="#0e1116")
    for a in (ax, av):
        a.set_facecolor("#0e1116")
        a.tick_params(colors="#8a94a6", labelsize=8)
        for sp in a.spines.values():
            sp.set_color("#1c2330")
        a.grid(color="#1c2330", linewidth=.5)
    for i, x in enumerate(b):
        o, hi, lo, c = (float(x["open"]), float(x["high"]),
                        float(x["low"]), float(x["close"]))
        col = "#16c784" if c >= o else "#ea3943"
        ax.plot([i, i], [lo, hi], color=col, linewidth=.8)
        ax.add_patch(plt.Rectangle((i - .3, min(o, c)), .6,
                                   max(abs(c - o), 1e-6), color=col))
        av.bar(i, float(x.get("volume") or 0), color=col, width=.7, alpha=.6)
    # Levels are the core of the read — if PDH/PDL sit outside today's range the
    # auto-scaled axis hides them and the agent reads a chart with no context.
    lo_b = min(float(x["low"]) for x in b); hi_b = max(float(x["high"]) for x in b)
    lvls = [v for v in (tech.get("vwap"), tech.get("pdh"), tech.get("pdl")) if v]
    if lvls:
        pad = (hi_b - lo_b) * 0.04 or 1
        ax.set_ylim(min(lo_b, min(lvls)) - pad, max(hi_b, max(lvls)) + pad)
    for lvl, lab, col in ((tech.get("vwap"), "VWAP", "#f0a93b"),
                          (tech.get("pdh"), "PDH", "#6366f1"),
                          (tech.get("pdl"), "PDL", "#6366f1")):
        if lvl:
            ax.axhline(lvl, color=col, linestyle="--", linewidth=.9, alpha=.8)
            ax.text(len(b) + .5, lvl, f" {lab} {lvl:,.2f}", color=col,
                    fontsize=7, va="center")
    ax.axhline(tech["last"], color="#e6ebf2", linewidth=.7, alpha=.5)
    ax.text(len(b) + .5, tech["last"], f" {tech['last']:,.2f}", color="#e6ebf2",
            fontsize=8, va="center", weight="bold")
    ax.set_title(f"{sym} · 5m · {datetime.now():%Y-%m-%d %H:%M} · "
                 f"vs VWAP {tech.get('vs_vwap_pct')}% · ATR {tech.get('atr14_pct')}%",
                 color="#e6ebf2", fontsize=10, loc="left")
    step = max(1, len(b) // 8)
    av.set_xticks(range(0, len(b), step))
    av.set_xticklabels([str(b[i]["date"])[11:16] for i in range(0, len(b), step)])
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=110, facecolor="#0e1116")
    plt.close()
    return out


def cmd_watch(limit):
    import requests
    try:
        rows = requests.get("http://127.0.0.1:5050/api/scores", timeout=10).json()
    except Exception:
        rows = []
    pool = [r for r in rows if r.get("price")
            and MIN_PRICE <= float(r["price"]) <= MAX_PRICE]
    pool.sort(key=lambda r: -(r.get("score") or 0))
    names = [r["symbol"] for r in pool[:limit]]
    if not names:
        print("  no in-band candidates"); return
    k = kd.client()
    q = k.quote([f"NSE:{s}" for s in names])
    CHARTS.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%H%M")
    out = []
    for s in names:
        d = q.get(f"NSE:{s}")
        if not d:
            continue
        px = float(d.get("last_price") or 0)
        dep = d.get("depth") or {}
        bid = (dep.get("buy") or [{}])[0]; ask = (dep.get("sell") or [{}])[0]
        # Depth is EMPTY outside market hours (bid=0) — a spread screen that silently
        # drops everything after the close is a screen that only works when you do
        # not need it. Out of session we render anyway and mark the spread unknown;
        # in session the screen is real and binding.
        if bid.get("price") and ask.get("price"):
            spread = (ask["price"] - bid["price"]) / px * 10000
        else:
            spread = None
        qty = int(CAPITAL * LEVERAGE / px)
        if qty < MIN_QTY or (spread is not None and spread > MAX_SPREAD_BPS):
            continue
        b5 = bars(s, "5minute", 3)
        bday = bars(s, "day", 40)
        if len(b5) < 30:
            continue
        tech = technicals(b5, bday)
        png = CHARTS / f"{datetime.now():%Y-%m-%d}_{stamp}_{s}.png"
        render(s, b5, tech, png)
        tech.update(symbol=s, qty=qty,
                    spread_bps=(round(spread, 2) if spread is not None else "closed"),
                    exposure=round(qty * px, 2), chart=str(png),
                    engine_score=next((r.get("score") for r in pool if r["symbol"] == s), None),
                    engine_signal=next((r.get("signal") for r in pool if r["symbol"] == s), None))
        out.append(tech)
        sp = f"{spread:>4.1f}b" if spread is not None else " n/a"
        print(f"  {s:<12} {px:>8,.2f} x{qty:<4} spread {sp}  chart -> {png.name}")
    j = CHARTS / f"{datetime.now():%Y-%m-%d}_{stamp}_watch.json"
    j.write_text(json.dumps(out, indent=2, default=str))
    print(f"\n  {len(out)} candidates rendered. Technicals: {j}")
    print("  Sarathi now READS the charts and calls --enter on any that qualify.")


def cmd_enter(sym, entry, stop, r_target, reason, conf):
    s = load()
    if any(p["symbol"] == sym for p in s["open"]):
        print(f"  {sym} already open"); return
    risk = round(entry - stop, 2)
    if risk <= 0:
        print("  stop must be BELOW entry for a long — risk must be positive"); return
    qty = int(CAPITAL * LEVERAGE / entry)
    tgt = round(entry + risk * r_target, 2)
    p = {"symbol": sym, "entry_price": entry, "qty": qty, "sl_price": stop,
         "target_price": tgt, "risk_per_share": risk, "r_target": r_target,
         "risk_rupees": round(risk * qty, 2),
         "entry_time": datetime.now().strftime("%H:%M:%S"),
         "entry_date": datetime.now().strftime("%Y-%m-%d"),
         "reason": reason, "confidence": conf, "pool": "SARATHI",
         "position_type": "LONG"}
    s["open"].append(p); save(s)
    print(f"  ENTERED {sym} x{qty} @ {entry} | stop {stop} (risk Rs{risk*qty:.0f}) "
          f"| target {tgt} ({r_target}R) | conf {conf}")
    print(f"  reason: {reason}")


def cmd_exit(sym, price, reason):
    s = load()
    p = next((x for x in s["open"] if x["symbol"] == sym), None)
    if not p:
        print(f"  {sym} not open"); return
    gross = (price - p["entry_price"]) * p["qty"]
    exposure = p["entry_price"] * p["qty"]
    fee = exposure * FEE_PCT / 100
    net = gross - fee
    r = (price - p["entry_price"]) / p["risk_per_share"]
    f = DIR / f"{datetime.now():%Y-%m-%d}.json"
    j = json.loads(f.read_text()) if f.exists() else {
        "date": f.stem, "engine": ENGINE, "total_capital": CAPITAL,
        "pools": {"SARATHI": {"positions": [], "closed": [], "pnl": 0.0}},
        "summary": {"total_pnl": 0.0, "trades": 0, "wins": 0, "losses": 0}}
    j["pools"]["SARATHI"]["closed"].append({
        **p, "exit_price": price, "exit_time": datetime.now().strftime("%H:%M:%S"),
        "pnl": round(net, 2), "pnl_gross": round(gross, 2), "fees": round(fee, 2),
        "pnl_pct": round((price / p["entry_price"] - 1) * 100, 2),
        "r_multiple": round(r, 2), "reason": reason, "cost": round(exposure, 2)})
    j["pools"]["SARATHI"]["pnl"] += net
    j["summary"]["total_pnl"] += net
    j["summary"]["trades"] += 1
    j["summary"]["wins" if net > 0 else "losses"] += 1
    DIR.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(j, indent=2))
    s["open"] = [x for x in s["open"] if x["symbol"] != sym]
    s["history"].append({**p, "exit_price": price, "pnl": round(net, 2),
                         "r_multiple": round(r, 2), "exit_reason": reason})
    save(s)
    print(f"  EXITED {sym} @ {price} ({reason}): {r:+.2f}R, gross Rs{gross:+.2f}, "
          f"fees Rs{fee:.2f}, NET Rs{net:+.2f}")


def cmd_status():
    s = load()
    for p in s["open"]:
        print(f"  OPEN {p['symbol']} x{p['qty']} @ {p['entry_price']} "
              f"stop {p['sl_price']} tgt {p['target_price']} ({p['r_target']}R)")
        print(f"       {p['reason'][:100]}")
    h = [x for x in s["history"] if "pnl" in x]
    if h:
        tot = sum(x["pnl"] for x in h)
        rs = [x["r_multiple"] for x in h]
        print(f"  closed: {len(h)}/20 toward the gate | net Rs{tot:+,.2f} | "
              f"avg {sum(rs)/len(rs):+.2f}R")
    else:
        print("  no closed trades yet (gate needs 20)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--watch", action="store_true")
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--enter", type=str)
    ap.add_argument("--price", type=float)
    ap.add_argument("--stop", type=float)
    ap.add_argument("--rtarget", type=float, default=1.5)
    ap.add_argument("--reason", type=str, default="")
    ap.add_argument("--conf", type=float, default=0.6)
    ap.add_argument("--exit", type=str)
    ap.add_argument("--status", action="store_true")
    a = ap.parse_args()
    if a.watch:
        cmd_watch(a.limit)
    elif a.enter:
        cmd_enter(a.enter, a.price, a.stop, a.rtarget, a.reason, a.conf)
    elif a.exit:
        cmd_exit(a.exit, a.price, a.reason or "agent call")
    else:
        cmd_status()


if __name__ == "__main__":
    main()
