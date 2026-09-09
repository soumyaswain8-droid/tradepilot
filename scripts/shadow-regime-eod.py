#!/usr/bin/env python3
"""
shadow-regime-eod — regime shadow (pre-registered 2026-09-08, docs/research/shadows/).
For each signal snapshot the sidecar captured, deploy v5's signals under the LIVE regime and
under the ALTERNATE regime using v5's own rules (score-ranked candidates, REGIME_SLOT_SPLIT
per direction, REGIME_ALLOC pool eligibility, positions sized at the engine's actual median notional), then price every counterfactual
position from Kite 5-min candles with v5's live exit rules (hard stop, target, trail 1.0/0.5,
15:15 close). Trades in both books cancel; the symmetric difference is the regime's cost.

  python3 scripts/shadow-regime-eod.py <date> [engine=v5] [candles.json]
Output: docs/research/shadows/regime/<date>.json + .md and a running ledger regime-ledger.csv
"""
import json, sys, time, math, csv
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent; sys.path.insert(0, str(ROOT))
DATE = sys.argv[1]; ENGINE = sys.argv[2] if len(sys.argv) > 2 else "v5"
CAND = json.load(open(sys.argv[3]))["candles"] if len(sys.argv) > 3 else {}
from prototype.v5.risk_manager import REGIME_SLOT_SPLIT          # noqa: E402
from prototype.v5.pool_manager import REGIME_ALLOC                # noqa: E402
ALT = {"BEAR": "SIDEWAYS", "SIDEWAYS": "BEAR", "BULL": "SIDEWAYS"}
ARM, STEP = 1.0, 0.5
# SIZING (fixed 2026-09-08 after the first run over-sized 20x): v5's real book runs through
# RiskManager scaling and safe_qty and lands at ~Rs 11k median notional. Rebuilding that chain
# here would be a second engine. The regime question is WHICH trades get slots, not how big,
# so every counterfactual position takes the engine's actual median notional for the day.
_led = json.load(open(ROOT / "docs/paper-trades" / ENGINE / f"{DATE}.json"))
_nots = sorted(t["entry_price"] * t["qty"] for p in _led["pools"].values() for t in p.get("closed", []))
NOTIONAL = _nots[len(_nots) // 2] if _nots else 11000.0; CLOSE_AT = "15:15"; FLEET_BPS = 12.0
OUT = ROOT / "docs/research/shadows/regime"; OUT.mkdir(parents=True, exist_ok=True)
SNAPS = sorted((ROOT / "docs/research/shadows" / ENGINE / DATE).glob("*.json"))
if not SNAPS: print("no snapshots"); sys.exit(1)

def candles(sym):
    if sym in CAND:
        if CAND[sym] and isinstance(CAND[sym][0].get("o"), str):
            CAND[sym] = [dict(t=b["t"], o=float(b["o"]), h=float(b["h"]), l=float(b["l"]), c=float(b["c"])) for b in CAND[sym]]
        return CAND[sym]
    from prototype.v4 import kite_data as kd
    try: df = kd.get_candles(sym, interval="5minute", days=1)
    except Exception: CAND[sym] = []; return []
    time.sleep(0.34)
    CAND[sym] = [] if df is None else [dict(t=str(i)[11:19], o=float(r.Open), h=float(r.High), l=float(r.Low), c=float(r.Close)) for i, r in df.iterrows() if str(i)[:10] == DATE]
    return CAND[sym]

def cost(qty, e, x): return round(qty * (e + x) / 2 * FLEET_BPS / 1e4, 2)

def replay(sym, short, entry, sl, tg, since):
    bars = [b for b in candles(sym) if b["t"] > since]
    if not bars: return None
    sl0 = sl or entry * (1.02 if short else 0.98); armed = False; best = entry
    for b in bars:
        hi, lo, c = b["h"], b["l"], b["c"]
        if short:
            if hi >= sl0: return (sl0, "STOPLOSS" if not armed else "TRAIL", b["t"])
            if tg and lo <= tg: return (tg, "TARGET", b["t"])
            best = min(best, lo)
            if (entry - c) / entry * 100 >= ARM:
                if not armed: armed, sl0 = True, entry
                else: sl0 = min(sl0, round(best * (1 + STEP / 100), 2))
        else:
            if lo <= sl0: return (sl0, "STOPLOSS" if not armed else "TRAIL", b["t"])
            if tg and hi >= tg: return (tg, "TARGET", b["t"])
            best = max(best, hi)
            if (c - entry) / entry * 100 >= ARM:
                if not armed: armed, sl0 = True, entry
                else: sl0 = max(sl0, round(best * (1 - STEP / 100), 2))
        if b["t"] >= CLOSE_AT: return (c, "TIME_EXIT", b["t"])
    return (bars[-1]["c"], "TIME_EXIT", bars[-1]["t"])

def simulate(regime):
    """Book under one regime across all snapshots. Returns list of counterfactual trades."""
    split = REGIME_SLOT_SPLIT[regime]; alloc = REGIME_ALLOC[regime]
    open_pos, closed, held = [], [], set()
    for f in SNAPS:
        s = json.loads(f.read_text()); at = s["at"]
        # close anything whose replayed exit is before this snapshot (keeps slot accounting honest)
        still = []
        for p in open_pos:
            if p["exit_at"] and p["exit_at"] <= at: closed.append(p); held.discard(p["symbol"])
            else: still.append(p)
        open_pos = still
        n_long = sum(1 for p in open_pos if p["dir"] == "LONG"); n_short = len(open_pos) - n_long
        cands = sorted(s.get("last_signals", []), key=lambda x: -float(x.get("score", 0)))
        for sig in cands:
            sym = sig["symbol"]; pool = sig.get("pool", "INTRADAY"); d = sig.get("position_type", "LONG" if sig["direction"] == "BUY" else "SHORT")
            if sym in held: continue
            if d == "LONG" and n_long >= split["long"]: continue
            if d == "SHORT" and n_short >= split["short"]: continue
            if alloc.get(pool, 0.0) <= 0: continue
            try: price = float(sig.get("entry_price") or 0)
            except (TypeError, ValueError): continue
            if not price or price != price or price <= 0: continue
            def _f(v):
                try: v = float(v); return v if v == v and v > 0 else None
                except (TypeError, ValueError): return None
            qty = int(math.floor(NOTIONAL / price))
            if qty <= 0: continue
            o = replay(sym, d == "SHORT", price, _f(sig.get("sl_price")), _f(sig.get("target_price")), at)
            if o is None: continue
            px, reason, when = o; sign = -1 if d == "SHORT" else 1
            g = round(sign * (px - price) * qty, 1)
            p = {"symbol": sym, "dir": d, "pool": pool, "score": sig.get("score"), "entry": price, "qty": qty, "entry_at": at,
                 "exit": round(px, 2), "reason": reason, "exit_at": when, "gross": g, "net": round(g - cost(qty, price, px), 1)}
            open_pos.append(p); held.add(sym)
            if d == "LONG": n_long += 1
            else: n_short += 1
    return closed + open_pos

live_regime = json.loads(SNAPS[-1].read_text()).get("regime") or "SIDEWAYS"; alt = ALT.get(live_regime, "SIDEWAYS")
books = {live_regime: simulate(live_regime), alt: simulate(alt)}
key = lambda p: (p["symbol"], p["dir"], p["entry_at"])
common = {key(p) for p in books[live_regime]} & {key(p) for p in books[alt]}
def tot(b): return round(sum(p["net"] for p in b), 1)
def uniq(b): return [p for p in b if key(p) not in common]
res = {"date": DATE, "engine": ENGINE, "live_regime": live_regime, "alt_regime": alt, "snapshots": len(SNAPS), "notional_per_position": round(NOTIONAL),
       "live_book_net": tot(books[live_regime]), "alt_book_net": tot(books[alt]), "common_trades": len(common),
       "live_only": uniq(books[live_regime]), "alt_only": uniq(books[alt])}
res["alt_minus_live"] = round(res["alt_book_net"] - res["live_book_net"], 1)
(OUT / f"{DATE}.json").write_text(json.dumps(res, indent=1, default=str))
led = OUT / "regime-ledger.csv"; new = not led.exists()
with open(led, "a", newline="") as fh:
    w = csv.writer(fh)
    if new: w.writerow(["date", "engine", "live_regime", "alt_regime", "snapshots", "live_book_net", "alt_book_net", "alt_minus_live", "live_only_n", "alt_only_n"])
    w.writerow([DATE, ENGINE, live_regime, alt, len(SNAPS), res["live_book_net"], res["alt_book_net"], res["alt_minus_live"], len(res["live_only"]), len(res["alt_only"])])
md = [f"# Regime shadow — {DATE} ({ENGINE})", "", f"Live regime **{live_regime}** vs alternate **{alt}** · {len(SNAPS)} snapshots · {len(common)} trades common to both books",
      "", "| Book | Net (replayed) | Trades |", "|---|---:|---:|",
      f"| live {live_regime} | {res['live_book_net']:+,.0f} | {len(books[live_regime])} |", f"| alt {alt} | {res['alt_book_net']:+,.0f} | {len(books[alt])} |",
      f"| **alt − live** | **{res['alt_minus_live']:+,.0f}** | |", ""]
for name, rows in (("Only under live", res["live_only"]), ("Only under alternate", res["alt_only"])):
    md += [f"## {name} ({len(rows)})", "", "| Stock | Dir | Pool | Score | Entry | Exit | Reason | Net |", "|---|---|---|---:|---:|---:|---|---:|"]
    md += [f"| {p['symbol']} | {p['dir']} | {p['pool']} | {p['score']} | {p['entry']} | {p['exit']} | {p['reason']} | {p['net']:+,.0f} |" for p in sorted(rows, key=lambda p: p['net'])[:25]]
    md.append("")
md.append("Replay: v5 rules (score-ranked, REGIME_SLOT_SPLIT, REGIME_ALLOC pool eligibility, positions sized at the engine's actual median notional, trail 1.0/0.5, 15:15 close), 5-min bars, 12 bps cost. Signals were generated under the live regime; the alternate book re-gates them, it does not re-score them.")
(OUT / f"{DATE}.md").write_text("\n".join(md))
print(f"{DATE} {ENGINE}: live {live_regime} {res['live_book_net']:+,.0f} | alt {alt} {res['alt_book_net']:+,.0f} | alt−live {res['alt_minus_live']:+,.0f} | common {len(common)} | -> {OUT / (DATE + '.md')}")
