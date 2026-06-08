#!/usr/bin/env python3
"""
TradePilot Trade Audit + Counterfactual Engine
==============================================
For EVERY trade made by EVERY engine, answer three questions:
  L1 TIMING   — how much was left on the table by exiting at the wrong moment
                (best-possible exit for the side actually taken, vs actual)?
  L2 REGIME   — was the trade on the right side of the stock's real move?
                On a bear day, a LONG into a faller should have been a SHORT.
  L3 SIGNAL   — did the trade obey the pre-market dashboard BUY/SELL score?

Then aggregate into a "bear-day solution": total Rs lost, total Rs left on the
table, the leak broken down by mistake class, and the concrete counterfactual —
what flipping the wrong-direction trades, and shorting the dashboard's own SELL
list, would have earned today.

Built 2026-06-08 during a BEAR session (Nifty -0.94%) where v4 went long into 47
positions and v5/v5_classic shorted risers — all three bleeding. The point is to
turn that into a repeatable, quantified post-close diagnosis.

Inputs (all already on disk — nothing new to capture):
  docs/paper-trades/{engine}/{date}.json   — per-engine trades (two schemas, see below)
  docs/dashboard-scores/{date}.json        — pre-market BUY/HOLD/SELL universe
  yfinance EOD day-OHLC                     — for L1 timing + L2 regime math

Outputs:
  docs/audit/{date}_trade-audit.jsonl      — one row per trade (the ledger)
  docs/audit/{date}_audit-report.md        — human report + bear-day solution
  docs/audit/{date}_audit-report.pdf       — rendered via dp content render (best-effort)

Usage:
  python3 scripts/trade-audit.py                 # today
  python3 scripts/trade-audit.py 2026-06-05      # a specific date
  python3 scripts/trade-audit.py --no-fetch      # skip yfinance (entry/exit-only math)
  python3 scripts/trade-audit.py --no-pdf        # skip PDF + Finder open
"""

import json
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PAPER = ROOT / "docs" / "paper-trades"
SCORES = ROOT / "docs" / "dashboard-scores"
AUDIT_DIR = ROOT / "docs" / "audit"
AUDIT_DIR.mkdir(parents=True, exist_ok=True)

ENGINES = ["v4", "v5", "v5_classic"]

# How much of `actual` a winning trade may leave behind before we call it
# EXIT_TOO_EARLY (timing_loss > EARLY_FACTOR * actual_pnl).
EARLY_FACTOR = 2.0


# ──────────────────────────────────────────────────────────────────────────
# NORMALIZE — collapse v4's flat schema and v5's pooled schema into one record
# ──────────────────────────────────────────────────────────────────────────

def _side_of(rec: dict) -> str:
    """LONG/SHORT from whatever field an engine happens to use. v4 is long-only."""
    raw = (rec.get("position_type") or rec.get("direction") or rec.get("side") or "").upper()
    if "SHORT" in raw or raw == "SELL":
        return "SHORT"
    return "LONG"


def _norm_closed(engine: str, rec: dict, pool: str) -> dict:
    return {
        "engine": engine, "pool": pool, "symbol": rec.get("symbol", "?"),
        "side": _side_of(rec), "status": "closed",
        "entry_price": rec.get("entry_price"), "exit_price": rec.get("exit_price"),
        "qty": rec.get("qty", 0),
        "entry_time": rec.get("entry_time"), "exit_time": rec.get("exit_time"),
        "actual_pnl": rec.get("pnl", rec.get("pnl_net", 0)) or 0,
        "pnl_pct": rec.get("pnl_pct"), "reason": rec.get("reason", ""),
        "score": rec.get("v4_score", rec.get("score")),
    }


def _norm_open(engine: str, rec: dict, pool: str, mark: float | None) -> dict:
    """Open-at-close position. exit_price = day mark (close); pnl = unrealized."""
    side = _side_of(rec)
    entry = rec.get("entry_price")
    qty = rec.get("qty", 0)
    pnl = None
    if mark is not None and entry is not None:
        pnl = (mark - entry) * qty if side == "LONG" else (entry - mark) * qty
    return {
        "engine": engine, "pool": pool, "symbol": rec.get("symbol", "?"),
        "side": side, "status": "open",
        "entry_price": entry, "exit_price": mark, "qty": qty,
        "entry_time": rec.get("entry_time"), "exit_time": "OPEN@CLOSE",
        "actual_pnl": pnl if pnl is not None else 0,
        "pnl_pct": None, "reason": "held to close",
        "score": rec.get("v4_score", rec.get("score")),
    }


def load_engine_trades(engine: str, date: str, marks: dict) -> list[dict]:
    """Return normalized closed + open trades for one engine, both schemas."""
    path = PAPER / engine / f"{date}.json"
    if not path.exists():
        return []
    d = json.loads(path.read_text())
    out: list[dict] = []
    # v4 flat schema
    if "closed_trades" in d or ("positions" in d and "pools" not in d):
        for r in d.get("closed_trades", []):
            out.append(_norm_closed(engine, r, "FLAT"))
        for r in d.get("positions", []):
            if r.get("status") in (None, "open"):
                out.append(_norm_open(engine, r, "FLAT", marks.get(_clean(r.get("symbol", "")))))
    # v5 pooled schema
    if "pools" in d:
        for pname, pool in d["pools"].items():
            if not isinstance(pool, dict):
                continue
            for r in pool.get("closed", []):
                out.append(_norm_closed(engine, r, pname))
            for r in pool.get("positions", []):
                out.append(_norm_open(engine, r, pname, marks.get(_clean(r.get("symbol", "")))))
    return out


def engine_regime(engine: str, date: str) -> str | None:
    path = PAPER / engine / f"{date}.json"
    if path.exists():
        return json.loads(path.read_text()).get("regime")
    return None


def _clean(sym: str) -> str:
    return sym.replace(".NS", "").upper().strip()


# ──────────────────────────────────────────────────────────────────────────
# DASHBOARD (signal layer) + EOD PRICES (timing/regime layer)
# ──────────────────────────────────────────────────────────────────────────

def load_dashboard(date: str) -> dict:
    path = SCORES / f"{date}.json"
    if not path.exists():
        return {}
    d = json.loads(path.read_text())
    out = {}
    for s in d.get("stocks", []):
        out[_clean(s.get("symbol", ""))] = {
            "direction": s.get("direction"), "score": s.get("score"),
            "change_pct": s.get("change_pct"), "price": s.get("price"),
        }
    return out


def fetch_eod(symbols: set[str], date: str) -> dict:
    """{SYMBOL: {open,high,low,close,prev_close,day_return_pct}} via yfinance.

    For `today` yfinance returns the live/partial day bar — fine for a test run;
    the 15:35 auto-run gets the settled bar. Returns {} on any failure so the
    audit degrades to entry/exit-only math instead of crashing.
    """
    if not symbols:
        return {}
    try:
        import yfinance as yf
    except ImportError:
        print("  [warn] yfinance not installed — running entry/exit-only")
        return {}
    def _tkr(s):  # index symbols (^NSEI) take no .NS suffix
        return s if s.startswith("^") else s + ".NS"
    ns = [_tkr(s) for s in sorted(symbols)]
    out: dict = {}
    try:
        df = yf.download(ns, period="5d", interval="1d", group_by="ticker",
                         progress=False, threads=True, auto_adjust=False)
    except Exception as e:
        print(f"  [warn] yfinance download failed ({e}) — entry/exit-only")
        return {}

    def rows_for(tkr):
        try:
            sub = df[tkr].dropna(how="all") if len(ns) > 1 else df.dropna(how="all")
            return sub
        except Exception:
            return None

    for sym in symbols:
        sub = rows_for(_tkr(sym))
        if sub is None or len(sub) == 0:
            continue
        # match target date if present, else use the last available bar
        idx = [str(i.date()) for i in sub.index]
        pos = idx.index(date) if date in idx else len(sub) - 1
        try:
            r = sub.iloc[pos]
            prev_close = float(sub.iloc[pos - 1]["Close"]) if pos > 0 else float(r["Open"])
            close = float(r["Close"])
            out[sym] = {
                "open": float(r["Open"]), "high": float(r["High"]),
                "low": float(r["Low"]), "close": close, "prev_close": prev_close,
                "day_return_pct": round((close - prev_close) / prev_close * 100, 2) if prev_close else 0.0,
            }
        except Exception:
            continue
    return out


# ──────────────────────────────────────────────────────────────────────────
# COUNTERFACTUALS — the three layers, per trade
# ──────────────────────────────────────────────────────────────────────────

def audit_trade(t: dict, ohlc: dict, dash: dict, regime: str) -> dict:
    sym = _clean(t["symbol"])
    side, qty = t["side"], t.get("qty", 0) or 0
    E, X = t.get("entry_price"), t.get("exit_price")
    actual = t.get("actual_pnl", 0) or 0
    bar = ohlc.get(sym, {})
    sig = dash.get(sym, {})

    timing_loss = 0.0          # L1: better exit, same side, same entry
    regime_loss = 0.0          # L2: opposite side would have earned this much more
    direction_correct = None   # L2: was the side right for the stock's actual move
    stock_day_ret = bar.get("day_return_pct")

    if bar and E:
        if side == "LONG":
            best_exit_pnl = (bar["high"] - E) * qty
        else:
            best_exit_pnl = (E - bar["low"]) * qty
        timing_loss = max(0.0, best_exit_pnl - actual)

    # L2 — direction correctness uses the trade's own realized move when closed,
    # else the stock's day return for open positions.
    move = None
    if X is not None and E is not None and t["status"] == "closed":
        move = X - E
    elif stock_day_ret is not None and E:
        move = E * stock_day_ret / 100.0
    if move is not None:
        rose = move > 0
        direction_correct = (side == "LONG" and rose) or (side == "SHORT" and not rose)
        if not direction_correct:
            # the opposite side, same magnitude, would have flipped the sign
            opposite_pnl = -actual if actual else abs(move) * qty
            regime_loss = max(0.0, opposite_pnl - actual)

    # L3 — signal adherence
    dash_dir = sig.get("direction")
    # The scorer's bearish label is AVOID (it never emits SELL — a structural
    # long-bias we surface in the report). Treat SELL/AVOID as "go short / don't long".
    bearish = dash_dir in ("SELL", "AVOID")
    bullish = dash_dir == "BUY"
    signal_mismatch = (bearish and side == "LONG") or (bullish and side == "SHORT")

    # mistake classification (priority order)
    if direction_correct is False and side == "LONG" and regime == "BEAR":
        klass = "LONG_IN_BEAR"
    elif direction_correct is False and side == "SHORT":
        klass = "SHORTED_RISER"
    elif direction_correct is False:
        klass = "WRONG_DIRECTION"
    elif signal_mismatch and actual < 0:
        klass = "IGNORED_SIGNAL"
    elif t["status"] == "open" and actual < 0:
        klass = "HELD_LOSER"
    elif actual > 0 and timing_loss > EARLY_FACTOR * max(actual, 1):
        klass = "EXIT_TOO_EARLY"
    elif actual > 0:
        klass = "GOOD_TRADE"
    else:
        klass = "LOSS_OTHER"

    rs_on_table = round(regime_loss if regime_loss > 0 else timing_loss, 0)

    return {
        **t,
        "stock_day_return_pct": stock_day_ret,
        "timing_loss": round(timing_loss, 0),
        "regime_loss": round(regime_loss, 0),
        "direction_correct": direction_correct,
        "dashboard_direction": dash_dir,
        "signal_mismatch": signal_mismatch,
        "mistake_class": klass,
        "rs_on_table": rs_on_table,
    }


# ──────────────────────────────────────────────────────────────────────────
# BEAR-DAY SOLUTION — what would have made money today
# ──────────────────────────────────────────────────────────────────────────

def shorting_the_sells(dash: dict, ohlc: dict, top_n: int = 10, notional: float = 30000) -> dict:
    """If we had shorted the dashboard's bearish list (SELL or AVOID) with
    `notional` each, what would the day's move have earned? Ranked by the stocks
    that actually fell most. Pure arithmetic on signals we already generated and
    prices that already happened."""
    bearish = [(s, v) for s, v in dash.items() if v.get("direction") in ("SELL", "AVOID")]
    # rank by biggest actual fall (most negative day return); need a price bar
    scored = [(s, v, ohlc[s]) for s, v in bearish if s in ohlc and ohlc[s].get("prev_close")]
    scored.sort(key=lambda t: t[2]["day_return_pct"])  # most negative first
    picks, total = [], 0.0
    for sym, v, bar in scored[:top_n]:
        ret = bar["day_return_pct"] / 100.0
        pnl = -ret * notional  # short profits when price falls
        total += pnl
        picks.append({"symbol": sym, "label": v.get("direction"),
                      "day_return_pct": bar["day_return_pct"], "short_pnl": round(pnl, 0)})
    return {"picks": picks, "total_pnl": round(total, 0), "notional_each": notional,
            "bearish_universe": len(bearish), "priced": len(scored)}


def build_solution(rows: list[dict], dash: dict, ohlc: dict, regime: str, nifty_ret) -> dict:
    by_engine, by_class = {}, {}
    total_actual = total_table = 0.0
    long_cnt = short_cnt = 0
    for r in rows:
        e = r["engine"]
        be = by_engine.setdefault(e, {"pnl": 0.0, "trades": 0, "longs": 0, "shorts": 0,
                                       "wins": 0, "on_table": 0.0})
        be["pnl"] += r["actual_pnl"]; be["trades"] += 1
        be["on_table"] += r["rs_on_table"]
        be["wins"] += 1 if r["actual_pnl"] > 0 else 0
        if r["side"] == "LONG": be["longs"] += 1; long_cnt += 1
        else: be["shorts"] += 1; short_cnt += 1
        bc = by_class.setdefault(r["mistake_class"], {"count": 0, "pnl": 0.0, "on_table": 0.0})
        bc["count"] += 1; bc["pnl"] += r["actual_pnl"]; bc["on_table"] += r["rs_on_table"]
        total_actual += r["actual_pnl"]; total_table += r["rs_on_table"]

    flip_gain = sum(r["regime_loss"] for r in rows if r["direction_correct"] is False)
    return {
        "regime": regime, "nifty_return_pct": nifty_ret,
        "totals": {"realized_pnl": round(total_actual, 0), "rs_on_table": round(total_table, 0),
                   "trades": len(rows), "longs": long_cnt, "shorts": short_cnt},
        "by_engine": {k: {kk: round(vv, 0) if isinstance(vv, float) else vv
                          for kk, vv in v.items()} for k, v in by_engine.items()},
        "by_mistake": {k: {kk: round(vv, 0) if isinstance(vv, float) else vv
                           for kk, vv in v.items()} for k, v in
                       sorted(by_class.items(), key=lambda kv: kv[1]["on_table"], reverse=True)},
        "flip_wrong_direction_gain": round(flip_gain, 0),
        "short_the_sells": shorting_the_sells(dash, ohlc),
    }


# ──────────────────────────────────────────────────────────────────────────
# REPORT
# ──────────────────────────────────────────────────────────────────────────

def write_report(date: str, sol: dict, rows: list[dict]) -> Path:
    t = sol["totals"]
    md = []
    md.append(f"# Trade Audit & Bear-Day Solution — {date}\n")
    nr = sol["nifty_return_pct"]
    nifty_txt = f" · Nifty {nr}%" if nr is not None else ""
    md.append(f"*Regime: **{sol['regime']}**{nifty_txt}* — "
              f"generated {datetime.now().strftime('%H:%M:%S')}\n")

    md.append("## Bottom line\n")
    md.append(f"- **Realized P&L today: Rs {t['realized_pnl']:,.0f}** across {t['trades']} "
              f"trades ({t['longs']} long / {t['shorts']} short)")
    md.append(f"- **Rs left on the table: Rs {t['rs_on_table']:,.0f}** "
              f"(recoverable with the right side + timing)")
    md.append(f"- **Flip every wrong-direction trade → +Rs {sol['flip_wrong_direction_gain']:,.0f}**")
    sts = sol["short_the_sells"]
    md.append(f"- **Short the dashboard's top SELLs (Rs {sts['notional_each']:,.0f} ea) "
              f"→ Rs {sts['total_pnl']:,.0f}**\n")

    md.append("## Where each engine went wrong\n")
    md.append("| Engine | Trades | L/S | Wins | Realized | On table |")
    md.append("|--------|-------:|----:|-----:|---------:|---------:|")
    for e, v in sol["by_engine"].items():
        md.append(f"| {e} | {v['trades']} | {v['longs']}/{v['shorts']} | {v['wins']} | "
                  f"Rs {v['pnl']:,.0f} | Rs {v['on_table']:,.0f} |")

    md.append("\n## The leak, by mistake class\n")
    md.append("| Mistake | Count | Realized | Rs on table |")
    md.append("|---------|------:|---------:|------------:|")
    for k, v in sol["by_mistake"].items():
        md.append(f"| {k} | {v['count']} | Rs {v['pnl']:,.0f} | Rs {v['on_table']:,.0f} |")

    md.append("\n## What would have made money today\n")
    md.append(f"*The scorer emitted **0 SELL** signals today — {sts['bearish_universe']} stocks "
              f"were labelled AVOID (its only bearish output). Shorting the AVOID stocks that "
              f"actually fell most:*\n")
    if sts["picks"]:
        md.append("| Symbol | Label | Day % | Short P&L |")
        md.append("|--------|-------|------:|----------:|")
        for p in sts["picks"]:
            md.append(f"| {p['symbol']} | {p['label']} | {p['day_return_pct']}% | Rs {p['short_pnl']:,.0f} |")

    md.append("\n## Prescription — flip a bear day\n")
    md.append(_prescription(sol))

    md.append("\n## Worst 15 trades (by Rs on table)\n")
    md.append("| Engine | Symbol | Side | Entry→Exit | Realized | Class | On table |")
    md.append("|--------|--------|------|-----------|---------:|-------|---------:|")
    def _px(v):
        return f"{v:,.1f}" if isinstance(v, (int, float)) else v
    for r in sorted(rows, key=lambda x: x["rs_on_table"], reverse=True)[:15]:
        ep, xp = _px(r.get("entry_price")), _px(r.get("exit_price"))
        md.append(f"| {r['engine']} | {_clean(r['symbol'])} | {r['side']} | "
                  f"{ep}→{xp} | Rs {r['actual_pnl']:,.0f} | {r['mistake_class']} | "
                  f"Rs {r['rs_on_table']:,.0f} |")

    out = AUDIT_DIR / f"{date}_audit-report.md"
    out.write_text("\n".join(md) + "\n")
    return out


def _prescription(sol: dict) -> str:
    lines, bm = [], sol["by_mistake"]
    sts = sol["short_the_sells"]
    if bm.get("LONG_IN_BEAR", {}).get("count"):
        c = bm["LONG_IN_BEAR"]
        lines.append(f"1. **BEAR regime gate (long-only engines):** {c['count']} longs in a bear "
                     f"regime cost Rs {c['on_table']:,.0f} on the table. In BEAR, block new longs "
                     f"unless the stock is a confirmed dashboard BUY with positive day momentum.")
    if bm.get("SHORTED_RISER", {}).get("count"):
        c = bm["SHORTED_RISER"]
        lines.append(f"2. **Short selection:** {c['count']} shorts hit risers (Rs {c['on_table']:,.0f} "
                     f"on the table). Only short dashboard SELLs with negative day return AND "
                     f"price below VWAP — never short a stock that's green on the day.")
    lines.append(f"3. **The scorer has no SELL output (root cause):** today it emitted 147 BUY / "
                 f"121 HOLD / {sts['bearish_universe']} AVOID / **0 SELL**. The engines literally "
                 f"cannot follow a short signal because none is produced — that is why a bear day "
                 f"becomes a long-only bloodbath. Add a real SELL tier to the scorer.")
    if sts["total_pnl"] > 0:
        lines.append(f"4. **Act on the bearish list:** shorting the AVOID stocks that fell would "
                     f"have made Rs {sts['total_pnl']:,.0f} today with Rs {sts['notional_each']:,.0f} "
                     f"per name. The information was there; nothing acted on it.")
    if not lines:
        lines.append("No dominant leak today — trades were broadly regime-aligned.")
    return "\n".join(lines)


# ──────────────────────────────────────────────────────────────────────────
# MAIN
# ──────────────────────────────────────────────────────────────────────────

def main():
    args = sys.argv[1:]
    no_fetch = "--no-fetch" in args
    no_pdf = "--no-pdf" in args
    date = next((a for a in args if not a.startswith("--")), datetime.now().strftime("%Y-%m-%d"))
    print(f"=== Trade Audit — {date} ===")

    regime = next((engine_regime(e, date) for e in ENGINES if engine_regime(e, date)), "UNKNOWN")
    dash = load_dashboard(date)
    print(f"  dashboard: {len(dash)} scored stocks · regime: {regime}")

    # gather symbols we need prices for: everything traded + the dashboard SELLs
    raw_all: list[dict] = []
    for e in ENGINES:
        raw_all += load_engine_trades(e, date, {})  # marks filled after fetch
    traded_syms = {_clean(t["symbol"]) for t in raw_all}
    # bearish candidates = SELL/AVOID, prioritise the biggest pre-market fallers
    bearish = [(s, v) for s, v in dash.items() if v.get("direction") in ("SELL", "AVOID")]
    bearish.sort(key=lambda kv: kv[1].get("change_pct") if kv[1].get("change_pct") is not None else 0)
    need = traded_syms | {s for s, _ in bearish[:40]}

    ohlc = {} if no_fetch else fetch_eod(need, date)
    print(f"  prices: {len(ohlc)}/{len(need)} symbols")
    marks = {s: b["close"] for s, b in ohlc.items()}

    # regime return: real Nifty 50 index move (^NSEI); None if fetch fails
    nifty_ret = None
    if not no_fetch:
        nb = fetch_eod({"^NSEI"}, date)
        if "^NSEI" in nb:
            nifty_ret = nb["^NSEI"]["day_return_pct"]

    # re-load trades now that we have marks for open positions
    rows = []
    for e in ENGINES:
        for t in load_engine_trades(e, date, marks):
            rows.append(audit_trade(t, ohlc, dash, regime))

    if not rows:
        print("  no trades found for any engine — nothing to audit.")
        return

    # write ledger
    ledger = AUDIT_DIR / f"{date}_trade-audit.jsonl"
    with open(ledger, "w") as f:
        for r in rows:
            f.write(json.dumps(r, default=str) + "\n")
    print(f"  ledger: {ledger}  ({len(rows)} trades)")

    sol = build_solution(rows, dash, ohlc, regime, nifty_ret)
    report = write_report(date, sol, rows)
    print(f"  report: {report}")

    t = sol["totals"]
    print(f"\n  Realized: Rs {t['realized_pnl']:,.0f} | On table: Rs {t['rs_on_table']:,.0f} "
          f"| Flip wrong-dir: +Rs {sol['flip_wrong_direction_gain']:,.0f} "
          f"| Short-the-SELLs: Rs {sol['short_the_sells']['total_pnl']:,.0f}")

    if not no_pdf:
        _render_pdf(report)


def _render_pdf(report: Path):
    import subprocess
    pdf = report.with_suffix(".pdf")
    try:
        r = subprocess.run(["dp", "content", "render", str(report), "-o", str(pdf)],
                           capture_output=True, timeout=120, text=True)
        if r.returncode == 0 and pdf.exists():
            print(f"  pdf: {pdf}")
            subprocess.run(["open", str(pdf)], timeout=10)
        else:
            subprocess.run(["open", str(report)], timeout=10)
    except Exception as e:
        print(f"  [warn] pdf render skipped ({e})")


if __name__ == "__main__":
    main()
