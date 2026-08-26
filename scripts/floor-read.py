#!/usr/bin/env python3
"""
floor-read — render the charts behind the floor's escalations so an agent can
actually LOOK at them, then answer the six questions.

This is option (c). Options (a) and (b) are mechanical: a rule fires, a position
opens. This one asks whether holistic chart reading beats the mechanised predicates,
which every one of our falsification runs found wanting.

WHAT IT CAN AND CANNOT DO, stated plainly. An LLM cannot sit in the tick loop — a
call takes seconds and the move takes seconds. So this does not run continuously. It
renders the charts behind recent escalations on demand; the read happens when asked,
and the answer is recorded with the timestamp it was made at, so hindsight cannot
creep in later.

    python3 scripts/floor-read.py                 # latest escalations, all triggers
    python3 scripts/floor-read.py --trigger SWEEP_RECLAIM --limit 4
    python3 scripts/floor-read.py --record TIMEX --verdict no-trade --why "mid-range"
"""
from __future__ import annotations

import argparse, json, sys, warnings
from datetime import datetime, timedelta
from pathlib import Path

warnings.filterwarnings("ignore")
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

KNOW = ROOT / "docs" / "sarathi" / "knowledge"
ESC = KNOW / "escalations"
OUT = KNOW / "reads"
READS = KNOW / "chart-reads.jsonl"


def bars(symbol, minutes=180):
    from prototype.v4 import kite_data as kd
    tok = kd.token_for(symbol)
    if not tok:
        return []
    now = datetime.now()
    try:
        return kd.client().historical_data(
            tok, now - timedelta(minutes=minutes + 60), now, "5minute")
    except Exception as e:
        print(f"    bars failed for {symbol}: {str(e)[:60]}")
        return []


def render(sym, b, levels, ev, out):
    """Candlestick + volume with the agent's own levels drawn on.

    The escalation is marked so the read is anchored to the exact bar the agent
    reacted to — reading the chart as a whole, after the fact, is a different and
    much easier question than the one the agent faced.
    """
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    b = b[-70:]
    if len(b) < 8:
        return None
    fig, (ax, av) = plt.subplots(2, 1, figsize=(11, 6.2), sharex=True,
                                 gridspec_kw={"height_ratios": [3.2, 1]},
                                 facecolor="#0b1017")
    for a in (ax, av):
        a.set_facecolor("#0b1017")
        a.tick_params(colors="#6a8199", labelsize=8)
        for sp in a.spines.values():
            sp.set_color("#17293d")
        a.grid(color="#12202f", lw=.6)

    for i, x in enumerate(b):
        o, h, l, c = (float(x["open"]), float(x["high"]),
                      float(x["low"]), float(x["close"]))
        col = "#3fd67f" if c >= o else "#ff4d6d"
        ax.plot([i, i], [l, h], color=col, lw=.9, zorder=2)
        ax.add_patch(Rectangle((i - .32, min(o, c)), .64, max(abs(c - o), 1e-6),
                               color=col, zorder=3))
        av.bar(i, float(x.get("volume") or 0), color=col, alpha=.55, width=.7)

    pal = {"VWAP": "#6c63ff", "PDH": "#ffb020", "PDL": "#ffb020",
           "DAY_HIGH": "#3ff0d8", "DAY_LOW": "#3ff0d8", "ROUND": "#7a8fa3"}
    for name, lvl in (levels or {}).items():
        if not lvl:
            continue
        ax.axhline(lvl, color=pal.get(name, "#7a8fa3"), lw=1, ls="--", alpha=.85)
        ax.text(len(b) - .5, lvl, f" {name} {lvl}", color=pal.get(name, "#7a8fa3"),
                fontsize=7.5, va="center")

    # anchor the read to the bar the agent actually reacted to
    hhmm = (ev.get("at") or "")[:5]
    idx = None
    for i, x in enumerate(b):
        if str(x["date"])[11:16] >= hhmm:
            idx = i
            break
    if idx is not None:
        ax.axvline(idx, color="#ff4d6d", lw=1.1, alpha=.75)
        ax.text(idx, ax.get_ylim()[1], f" {ev.get('trigger','')} {hhmm}",
                color="#ff4d6d", fontsize=8, va="top")

    ax.set_title(f"{sym}   {ev.get('trigger','')}   ltp {ev.get('ltp')}   "
                 f"{ev.get('agree','?')} scouts",
                 color="#c3d4e4", fontsize=10.5, loc="left")
    av.set_xlabel("5-minute bars", color="#6a8199", fontsize=8)
    plt.tight_layout()
    out.parent.mkdir(parents=True, exist_ok=True)
    plt.savefig(out, dpi=110, facecolor="#0b1017")
    plt.close(fig)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--day", default=datetime.now().strftime("%Y-%m-%d"))
    ap.add_argument("--trigger", default=None)
    ap.add_argument("--limit", type=int, default=4)
    ap.add_argument("--record", help="symbol to record a verdict for")
    ap.add_argument("--verdict", choices=["long", "short", "no-trade"])
    ap.add_argument("--why", default="")
    ap.add_argument("--confidence", type=float, default=0.0)
    a = ap.parse_args()

    if a.record:
        rec = {"at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
               "symbol": a.record, "verdict": a.verdict, "why": a.why,
               "confidence": a.confidence}
        READS.parent.mkdir(parents=True, exist_ok=True)
        with open(READS, "a") as f:
            f.write(json.dumps(rec) + "\n")
        print(f"  recorded: {a.record} {a.verdict} ({a.confidence}) — {a.why}")
        return

    f = ESC / f"{a.day}.jsonl"
    if not f.exists():
        print(f"  no escalations for {a.day}")
        return
    ev = [json.loads(l) for l in f.read_text().splitlines() if l.strip()]
    if a.trigger:
        ev = [e for e in ev if e["trigger"].split(":")[0] == a.trigger]
    # one per symbol, most recent — reading the same stock four times is not four reads
    seen, picks = set(), []
    for e in reversed(ev):
        if e["symbol"] in seen:
            continue
        seen.add(e["symbol"])
        picks.append(e)
        if len(picks) >= a.limit:
            break
    if not picks:
        print(f"  nothing matching {a.trigger or 'any trigger'} on {a.day}")
        return

    print(f"  rendering {len(picks)} charts -> {OUT}")
    for e in picks:
        sym = e["symbol"]
        b = bars(sym)
        lv = (e.get("thesis") or {}).get("levels") or {}
        out = OUT / f"{a.day}_{sym}_{e['at'].replace(':','')}.png"
        r = render(sym, b, lv, e, out)
        print(f"    {sym:<12} {e['at']}  {e['trigger']:<22} -> "
              f"{r.name if r else 'FAILED (thin bars)'}")
    print("\n  THE SIX QUESTIONS (answer in order; fail 1 or 2 = no trade)")
    for i, q in enumerate([
            "WHERE IS PRICE? nearest level above and below, with distance",
            "WHAT IS THE STRUCTURE? trend/range on the 15m, name the protected level",
            "WHAT IS THE TRIGGER? a specific event, not 'it looks bullish'",
            "WHAT SAYS I AM WRONG? the invalidation price, named BEFORE entry",
            "HOW MANY INDEPENDENT READS AGREE? fewer than 4 is not worth the toll",
            "WHAT IS THE REWARD? distance to next opposing level / risk. <1.5R = skip"], 1):
        print(f"    {i}. {q}")
    print("\n  record with: floor-read.py --record SYM --verdict long|short|no-trade "
          "--confidence 0.7 --why '...'")


if __name__ == "__main__":
    main()
