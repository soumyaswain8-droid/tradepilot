#!/usr/bin/env python3
"""v5_god — a ONE-DAY discretionary book run alongside the systematic fleet.

WHAT THIS IS
Every other engine in docs/paper-trades/ picks by rule. This one is picked by an
LLM (Sarathi) exercising discretion over the NIFTY-200, on 2026-08-18, with a
Rs2,00,000 notional book. The question it exists to answer:

    does discretionary selection beat the rules, on the same tape, same fees?

WHY THE ANSWER FROM A SINGLE DAY IS WORTH ALMOST NOTHING
Measured across 3,526 live paper trades, this stack's gross edge is ~+0.069% against
a 0.1060% round-trip toll, and commit 02565eb records that a full 36-combination
strategy search produced nothing that survived holdout at real fees. One session of
three positions is noise with a fee drag stapled to it. The output that actually has
value is the LOGGED REASONING — a thesis and an invalidation level written to disk
BEFORE each fill, which can be audited later across many days. A day's P&L cannot be
audited; a day's reasoning can.

THE ONE THING THIS BOOK EXPLOITS THAT THE FLEET CANNOT
Zerodha intraday brokerage is "0.03% or Rs20 per order, whichever is LOWER". Below
Rs66,667 per position the percentage binds; above it the flat Rs20 binds and the
round-trip cost FALLS as size rises. Measured 2026-08-10: median fleet position was
Rs7,252 and the largest in three months was Rs44,992 — the entire fleet has always
traded inside the most expensive bracket. At Rs67k+ per position this book pays
roughly 0.078% instead of 0.1060%. That ~3bp saving is larger than the net deficit
the fleet has been failing to close, and it is the only edge here that is PROVEN
rather than hoped for.

    MIN_POSITION_VALUE = 67_000     enforced at entry, not suggested

COSTS ARE REPORTED TWICE, DELIBERATELY
  real_cost    the actual Zerodha ledger — brokerage/STT/exchange/SEBI/stamp/GST,
               size-dependent, what the money would truly do
  fleet_cost   the fleet's flat 12bps model, so the P&L is comparable to v5 et al
If we only reported real_cost, this book would look better than the fleet purely
because it models fees more accurately. Both numbers, always.

PRE-REGISTRATION IS THE POINT
enter() writes thesis + stop to disk with a timestamp before the position exists.
The file is append-only in spirit: exits record what happened, they never revise why
we entered. Without this, an EOD writeup is a story told by the winner.

SHORTS
Allowed, but gated: price must be BELOW the day VWAP at entry. From the 2026-07-24
fix-day, a VWAP-only short rule was net-negative on its own and only paid as an
AND-gate with the directional signal. The gate is enforced in code, not remembered.

Usage:
    python3 scripts/v5_god-paper-trade.py scan            # live candidate table
    python3 scripts/v5_god-paper-trade.py enter SYM LONG --qty N --stop P --thesis "..."
    python3 scripts/v5_god-paper-trade.py mark            # mark to market, run exits
    python3 scripts/v5_god-paper-trade.py close SYM --reason "..."
    python3 scripts/v5_god-paper-trade.py eod             # daily artifact + scorecard
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
import time
from datetime import datetime, timedelta as _td
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

ENGINE = "v5_god"
OUTDIR = ROOT / "docs" / "paper-trades" / ENGINE
STATE = OUTDIR / "positions_active.json"

CAPITAL = 200_000.0
MAX_POSITIONS = 3
MIN_POSITION_VALUE = 67_000.0     # the brokerage cliff — below this we pay 0.1060%
SQUARE_OFF = "15:15"

# TARGET / TRAIL — operator directive 2026-08-18 09:35: "exit when we made more than 1.3".
# Read as a FLOOR, not a cap: bank at least 1.3%, then let the trail chase anything beyond.
# NOTE this deliberately overrides the arm0.3/step0.25 variant from 770e0be. That trail
# arms at +0.30% and gives back 0.25%, so it exits most winners near +0.05..1.0% and would
# make a 1.3% floor unreachable by construction. The two rules are mutually exclusive and
# the operator's directive wins — but it is a REAL trade-off, not a free upgrade: demanding
# 1.3% before arming means every trade that peaks at +1.2% and reverses now round-trips to
# the stop instead of banking a small win. Fewer, larger wins; more full losses.
# ── 2026-08-19 HYPOTHESIS ────────────────────────────────────────────────────
# Yesterday ranked 10/15 at -0.090%. Three failure modes were identified, and each
# gets exactly one rule here so the result stays attributable:
#
#  1 GESHIP  -984  entered at 1322.00 while its signal bar was 1316.00-1324.40 —
#                  INSIDE the bar. The breakout had not happened; I called it
#                  confirmed anyway. TIINDIA, entered 2 seconds later in the same
#                  sector, was at 2898.10 against a bar high of 2893.80 — genuinely
#                  beyond it — and paid +838.
#                  -> REQUIRE_BREAKOUT: price must be past the signal bar's extreme.
#  2 KFINTECH -499 held 224 minutes. It was RIGHT at 10:45 (+0.29%) and dead by
#                  13:10. A thesis that has not paid in 90 minutes is occupying a
#                  slot, not working.
#                  -> MAX_HOLD_MIN: force the exit, do not wait for the stop.
#  3 afternoon      every post-11:00 candidate failed the volume test (0.11x-1.05x).
#                  There was nothing to trade and entering would have been invention.
#                  -> NO_ENTRY_AFTER: stop looking rather than lower the bar.
#
# FALSIFICATION: if today loses money with all three rules active, the entry filter
# is not the binding constraint and the next suspect is selection itself.
REQUIRE_BREAKOUT = os.environ.get("REQUIRE_BREAKOUT", "1") == "1"
# 11:30 -> 13:45 on 2026-08-19 by operator decision. The 11:30 cutoff was built from a
# SINGLE dead afternoon (08-18) and today's MORNING was equally dead, which undercuts
# the premise that mornings are where the volume is. 13:45 is not arbitrary: square-off
# is 15:15 and MAX_HOLD_MIN is 90, so it is the last moment a position can live its full
# intended life instead of being cut short by the clock.
NO_ENTRY_AFTER = os.environ.get("NO_ENTRY_AFTER", "13:45")
MAX_HOLD_MIN = int(os.environ.get("MAX_HOLD_MIN", "90"))

TARGET_FLOOR_PCT = 1.30           # trail does not arm until the position has made this
TRAIL_STEP_PCT = 0.25             # give-back once armed
FLEET_COST_BPS = 12.0             # v5's flat round-trip model, for comparability


# ── costs ────────────────────────────────────────────────────────────────────
def real_cost(qty: int, entry: float, exit_: float, side: str) -> dict:
    """Actual Zerodha intraday equity ledger. Size-dependent by construction —
    that dependence is the whole reason this book runs big positions."""
    buy_val = qty * (entry if side == "LONG" else exit_)
    sell_val = qty * (exit_ if side == "LONG" else entry)
    turnover = buy_val + sell_val

    brokerage = min(0.0003 * buy_val, 20.0) + min(0.0003 * sell_val, 20.0)
    stt = 0.00025 * sell_val                 # intraday equity: sell side only
    exch = 0.0000297 * turnover              # NSE transaction charge
    sebi = 0.000001 * turnover               # Rs10 per crore
    stamp = 0.00003 * buy_val                # buy side only
    gst = 0.18 * (brokerage + exch + sebi)
    total = brokerage + stt + exch + sebi + stamp + gst
    return {
        "brokerage": round(brokerage, 2), "stt": round(stt, 2),
        "exchange": round(exch, 2), "sebi": round(sebi, 2),
        "stamp": round(stamp, 2), "gst": round(gst, 2),
        "total": round(total, 2),
        "pct_of_turnover": round(total / turnover * 100, 4) if turnover else 0.0,
    }


def fleet_cost(qty: int, entry: float, exit_: float) -> float:
    """v5's flat 12bps model on average notional. Kept so this book's P&L can be
    compared to engines that use it, without pretending it is the true cost."""
    return round(qty * (entry + exit_) / 2 * (FLEET_COST_BPS / 10000), 2)


# ── market data ──────────────────────────────────────────────────────────────
def kite():
    from prototype.v5 import kite_broker as kb
    c = kb.credentials()
    if not c["api_key"] or not c["access_token"]:
        raise SystemExit("kite credentials missing — run /kite/login")
    from kiteconnect import KiteConnect
    k = KiteConnect(api_key=c["api_key"])
    k.set_access_token(c["access_token"])
    return k


def full_quotes(symbols: list[str]) -> dict:
    """Full Kite quote: last, day VWAP (average_price), OHLC, volume, depth.
    kite_broker.quotes() returns only last/prev_close, which cannot gate a short."""
    k = kite()
    out = {}
    for i in range(0, len(symbols), 200):        # Kite caps instruments per call
        chunk = [f"NSE:{s}" for s in symbols[i:i + 200]]
        # RETRY WITH BACKOFF. Kite's quote endpoint allows roughly one request per
        # second; two concurrent watchers collide and one gets throttled. Observed
        # live 2026-08-18 09:54 — every position reported NO QUOTE for a full cycle,
        # which means stops could not fire. A transient throttle must never leave an
        # open book unmanaged, so we retry rather than skip. Failing loudly after the
        # retries is deliberate: silence is what made this dangerous the first time.
        raw = None
        for attempt in range(4):
            try:
                raw = k.quote(chunk)
                break
            except Exception as e:
                if attempt == 3:
                    print(f"  QUOTE FAILED after 4 attempts: {type(e).__name__}: {e}",
                          file=sys.stderr)
                else:
                    time.sleep(1.5 * (attempt + 1))
        if raw is None:
            continue
        for key, v in raw.items():
            sym = key.split(":", 1)[1]
            last = v.get("last_price") or 0
            o = v.get("ohlc") or {}
            prev = o.get("close") or 0
            if last <= 0 or prev <= 0:
                continue                          # omit, never fabricate
            vwap = v.get("average_price") or 0
            out[sym] = {
                "price": round(last, 2),
                "prev_close": round(prev, 2),
                "open": round(o.get("open") or 0, 2),
                "high": round(o.get("high") or 0, 2),
                "low": round(o.get("low") or 0, 2),
                "vwap": round(vwap, 2),
                "volume": v.get("volume") or 0,
                "chg_pct": round((last - prev) / prev * 100, 2),
                "vs_vwap_pct": round((last - vwap) / vwap * 100, 2) if vwap else None,
                "day_range_pos": (round((last - o.get("low", last)) /
                                        (o.get("high", last) - o.get("low", last)) * 100, 1)
                                  if (o.get("high") or 0) > (o.get("low") or 0) else None),
            }
    return out


def universe() -> list[str]:
    f = ROOT / "quant" / "universe_expanded.txt"
    return [l.strip() for l in f.read_text().splitlines()
            if l.strip() and not l.startswith("#")]


# ── market regime ────────────────────────────────────────────────────────────
# Added 2026-08-19 after the operator's Kite dashboard showed what the engine could
# not see: NIFTY -0.30%, NEXT 50 -0.62%, MIDCAP/SMLCAP -0.39%. Every index red and the
# broader the index the worse it was — and the engine was hunting LONG breakouts in it.
# MRPL confirmed, then lost VWAP and fell 1.25% within twenty minutes.
#
# A single stock's candle cannot tell you the tide is going out. Reading breakouts
# without the index is reading a sentence with the page torn off.
INDEX_KEYS = ["NSE:NIFTY 50", "NSE:NIFTY BANK", "NSE:NIFTY NEXT 50",
              "NSE:NIFTY MIDCAP 100", "NSE:NIFTY SMLCAP 100", "NSE:INDIA VIX"]
REGIME_BLOCK_PCT = float(os.environ.get("REGIME_BLOCK_PCT", "0.25"))


def market_regime() -> dict:
    """Broad-tape read. Returns direction, breadth and VIX so an entry can be refused
    for fighting the tide rather than for anything about the stock itself."""
    try:
        raw = kite().quote(INDEX_KEYS)
    except Exception as e:
        return {"ok": False, "why": f"{type(e).__name__}"}
    idx, vix = {}, None
    for k, v in raw.items():
        name = k.split(":", 1)[1]
        last = v.get("last_price")
        prev = (v.get("ohlc") or {}).get("close")
        if not last or not prev:
            continue
        chg = (last - prev) / prev * 100
        if name == "INDIA VIX":
            vix = last
        else:
            idx[name] = round(chg, 2)
    if not idx:
        return {"ok": False, "why": "no index data"}
    vals = list(idx.values())
    avg = sum(vals) / len(vals)
    up = sum(1 for x in vals if x > 0)
    direction = "UP" if avg > REGIME_BLOCK_PCT else ("DOWN" if avg < -REGIME_BLOCK_PCT else "FLAT")
    return {"ok": True, "indices": idx, "avg_pct": round(avg, 2), "vix": vix,
            "breadth": f"{up}/{len(vals)} indices green", "direction": direction}


def regime_blocks(side: str) -> tuple:
    """True when a trade fights the broad tape. Deliberately only blocks a CLEAR
    counter-tide trade — a FLAT market blocks nothing, because refusing to trade a
    directionless index would mean never trading at all."""
    r = market_regime()
    if not r.get("ok"):
        return False, f"regime unknown ({r.get('why')}) — not blocking"
    if side == "LONG" and r["direction"] == "DOWN":
        return True, (f"tape is DOWN (avg {r['avg_pct']}%, {r['breadth']}) — "
                      f"a long breakout here fights the tide")
    if side == "SHORT" and r["direction"] == "UP":
        return True, (f"tape is UP (avg {r['avg_pct']}%, {r['breadth']}) — "
                      f"a short here fights the tide")
    return False, f"tape {r['direction']} (avg {r['avg_pct']}%) — no conflict"


# ── kite candles (the data behind Kite's TradingView charts) ─────────────────
# Switched off yfinance 2026-08-19. yfinance was the weakest component in the stack:
# NSE data arrives delayed, it rate-limited mid-session yesterday (YFRateLimitError on
# TIINDIA), and it is a scrape of a consumer endpoint with no delivery guarantee. Kite's
# historical API returns the exact OHLCV the Kite chart draws, in real time — the 09:35
# candle was readable at 09:37. Requires the Historical Data add-on, verified live on
# this account 2026-08-19.
_TOKENS: dict = {}


def instrument_tokens() -> dict:
    """symbol -> instrument_token for NSE. Cached on disk: the dump is ~10k rows and
    changes once a day, so refetching it per signal would waste seconds we do not have
    intraday."""
    global _TOKENS
    if _TOKENS:
        return _TOKENS
    cache = OUTDIR / "_nse_tokens.json"
    today = datetime.now().strftime("%Y-%m-%d")
    if cache.exists():
        try:
            blob = json.loads(cache.read_text())
            if blob.get("date") == today:
                _TOKENS = blob["tokens"]
                return _TOKENS
        except Exception:
            pass
    inst = kite().instruments("NSE")
    _TOKENS = {i["tradingsymbol"]: i["instrument_token"] for i in inst
               if i.get("segment") == "NSE" and i.get("instrument_type") == "EQ"}
    OUTDIR.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps({"date": today, "tokens": _TOKENS}))
    return _TOKENS


def kite_candles(sym: str, interval: str = "5minute", days: int = 1) -> list:
    """OHLCV candles from Kite. Returns [] on failure — callers must treat an empty
    list as 'unknown', never as 'nothing happening'."""
    tok = instrument_tokens().get(sym)
    if not tok:
        return []
    to = datetime.now()
    frm = to - _td(days=days)
    for attempt in range(3):
        try:
            return kite().historical_data(tok, frm, to, interval)
        except Exception:
            if attempt == 2:
                return []
            time.sleep(1.2 * (attempt + 1))
    return []


def read_patterns(c: list) -> dict:
    """Name the formations a chart reader would name on the last CLOSED candle.

    These are descriptive, not predictive on their own — a hammer in a downtrend and a
    hammer in a range mean different things. They are surfaced so an entry can be
    justified by structure rather than by a single close-position number.
    """
    if len(c) < 3:
        return {}
    cur, prev = c[-2], c[-3]           # [-1] is still forming; judging it is self-deception
    o, h, l, cl = cur["open"], cur["high"], cur["low"], cur["close"]
    po, ph, pl, pc = prev["open"], prev["high"], prev["low"], prev["close"]
    rng = h - l
    if rng <= 0:
        return {}
    body = abs(cl - o)
    upper, lower = h - max(cl, o), min(cl, o) - l
    pats = []
    if cl > o and po > pc and cl >= po and o <= pc:
        pats.append("bullish_engulfing")
    if cl < o and pc > po and cl <= po and o >= pc:
        pats.append("bearish_engulfing")
    if body > 0 and lower >= 2 * body and upper <= body:
        pats.append("hammer")           # rejection of lower prices
    if body > 0 and upper >= 2 * body and lower <= body:
        pats.append("shooting_star")    # rejection of higher prices
    if body <= 0.1 * rng:
        pats.append("doji")             # indecision — the opposite of a signal
    if h <= ph and l >= pl:
        pats.append("inside_bar")       # compression, not direction
    if body >= 0.7 * rng:
        pats.append("marubozu")         # one side in complete control
    return {"patterns": pats, "body_pct": round(body / rng * 100, 1),
            "upper_wick_pct": round(upper / rng * 100, 1),
            "lower_wick_pct": round(lower / rng * 100, 1)}


# ── candle signals ───────────────────────────────────────────────────────────
# Operator directive 2026-08-18: "enter when candles give signals, not randomly".
# A snapshot (chg%, vs-VWAP, range position) says where price IS. A candle says what
# price just DID. The difference matters most exactly where I was about to be wrong
# this morning: ANGELONE showed -3.58% and range-position 12 (looks like a collapsing
# short) while its last three bars read 288.2 / 283.4 / 283.6 — the selling had already
# stopped. The snapshot was describing a move that was over.
#
# A bar qualifies only if ALL of these hold. Each one removes a specific way of being
# wrong; none is decorative:
#   1 BREAK      close beyond the prior bar's extreme      -> something changed, vs drift
#   2 CONVICTION close in the outer 40% of its own range   -> rejects long-wick reversals
#   3 SIDE       agrees with VWAP                          -> not fighting the day's mean
#   4 RANGE      bar range >= 60% of recent average        -> rejects dead/doji bars
#   5 VOLUME     >= 1.1x recent average                    -> someone actually participated
def candle_signal(sym: str, lookback: int = 12) -> dict:
    """Evaluate the most recent CLOSED 5-minute candle from KITE data.

    Same five gates as before (break / conviction / VWAP-side / range / volume) — they
    are unchanged so today's results stay comparable to yesterday's — plus two additions
    the switch to real chart data makes possible:
      - named patterns from read_patterns(), so a verdict can be read the way a chart is
      - a 15-minute trend check, because a 5m breakout against the 15m direction is the
        classic false break, and yesterday's GESHIP had exactly that shape
    """
    c = kite_candles(sym, "5minute", 1)
    if not c:
        return {"symbol": sym, "signal": None,
                "why": "DATA UNAVAILABLE from Kite — not a verdict"}
    # keep only today's candles; a 1-day window can straddle the previous session
    today = datetime.now().date()
    c = [x for x in c if x["date"].date() == today]
    if len(c) < 3:
        return {"symbol": sym, "signal": None, "why": f"only {len(c)} candles — too early"}

    cur, prev = c[-2], c[-3]
    hist = c[:-1]
    o, h, l, cl, v = (cur["open"], cur["high"], cur["low"], cur["close"], cur["volume"])
    rng = h - l
    if rng <= 0:
        return {"symbol": sym, "signal": None, "why": "zero-range candle"}

    rr = [x["high"] - x["low"] for x in hist[-lookback:]]
    vv = [x["volume"] for x in hist[-lookback:]]
    avg_rng = sum(rr) / len(rr) if rr else 0
    avg_vol = sum(vv) / len(vv) if vv else 0
    close_pos = (cl - l) / rng
    broke_up, broke_dn = cl > prev["high"], cl < prev["low"]
    fat = rng >= 0.60 * avg_rng if avg_rng > 0 else False
    heavy = v >= 1.10 * avg_vol if avg_vol > 0 else False

    # 15-minute context. A 5m break fighting the 15m direction is the textbook false
    # break; requiring agreement is what a chart reader does by zooming out.
    c15 = kite_candles(sym, "15minute", 1)
    c15 = [x for x in c15 if x["date"].date() == today]
    trend15 = None
    if len(c15) >= 3:
        trend15 = "UP" if c15[-2]["close"] > c15[-3]["close"] else "DOWN"

    pat = read_patterns(c)
    names = pat.get("patterns", [])

    sig, why = None, []
    if broke_up and close_pos >= 0.60 and fat and heavy:
        sig = "LONG"
    elif broke_dn and close_pos <= 0.40 and fat and heavy:
        sig = "SHORT"
    else:
        if not (broke_up or broke_dn): why.append("no break of prior candle")
        elif broke_up and close_pos < 0.60: why.append(f"broke up, closed weak ({close_pos:.0%})")
        elif broke_dn and close_pos > 0.40: why.append(f"broke down, closed strong ({close_pos:.0%})")
        if not fat: why.append(f"range {rng:.2f} < 60% of avg {avg_rng:.2f}")
        if not heavy: why.append(f"volume {v:,.0f} < 1.1x avg {avg_vol:,.0f}")

    # veto on structure the raw numbers do not capture
    if sig and "doji" in names:
        sig, why = None, ["doji — indecision, not a signal"]
    if sig == "LONG" and "shooting_star" in names:
        sig, why = None, ["shooting star — upper wick rejected the highs"]
    if sig == "SHORT" and "hammer" in names:
        sig, why = None, ["hammer — lower wick rejected the lows"]
    if sig == "LONG" and trend15 == "DOWN":
        sig, why = None, ["5m break UP against a 15m DOWN trend — false-break shape"]
    if sig == "SHORT" and trend15 == "UP":
        sig, why = None, ["5m break DOWN against a 15m UP trend — false-break shape"]

    return {"symbol": sym, "signal": sig, "bar_close": round(cl, 2),
            "close_pos": round(close_pos, 2), "range": round(rng, 2),
            "avg_range": round(avg_rng, 2), "bar_high": h, "bar_low": l,
            "vol_ratio": round(v / avg_vol, 2) if avg_vol else None,
            "candles": len(c), "trend15": trend15, "patterns": names,
            "why": ("CONFIRMED " + "/".join(names) if sig else "; ".join(why))}


def cmd_signal(args) -> int:
    """Report candle verdicts for the watchlist. VWAP agreement is applied here too,
    so what prints is what would actually be allowed through enter()."""
    syms = [s.upper() for s in args.symbols]
    q = full_quotes(syms)
    print(f"{'SYM':<13}{'SIG':<7}{'close':>9}{'pos':>6}{'vol x':>7}  verdict")
    print("-" * 78)
    for s in syms:
        try:
            r = candle_signal(s)
        except Exception as e:
            print(f"{s:<13}{'ERR':<7}{'':>9}{'':>6}{'':>7}  {type(e).__name__}: {str(e)[:32]}")
            continue
        sig = r["signal"]
        if sig and s in q and q[s]["vwap"]:
            px, vw = q[s]["price"], q[s]["vwap"]
            if sig == "LONG" and px < vw:
                sig, r["why"] = None, f"candle LONG but price {px} below VWAP {vw}"
            if sig == "SHORT" and px >= vw:
                sig, r["why"] = None, f"candle SHORT but price {px} above VWAP {vw}"
        print(f"{s:<13}{(sig or '-'):<7}{r.get('bar_close', 0):>9}"
              f"{r.get('close_pos', 0):>6}{(r.get('vol_ratio') or 0):>7}  {r['why'][:44]}")
    return 0


# ── state ────────────────────────────────────────────────────────────────────
def load() -> dict:
    if STATE.exists():
        st = json.loads(STATE.read_text())
        today = datetime.now().strftime("%Y-%m-%d")
        if st.get("date") == today:
            return st
        # DAY ROLL. Without this, day 2 loads day 1's closed trades and every P&L
        # figure silently becomes cumulative while still being labelled a daily.
        # Any position left open across a day boundary is a bug, not a swing trade —
        # this book squares off at 15:15 by construction — so warn loudly rather
        # than carrying it or discarding it quietly.
        if st.get("positions"):
            print(f"  WARNING: {len(st['positions'])} position(s) left open from "
                  f"{st.get('date')} — archived, not carried", file=sys.stderr)
        archive = OUTDIR / f"state_{st.get('date')}.json"
        archive.write_text(json.dumps(st, indent=2))
        print(f"  new session {today}; previous state archived to {archive.name}")
    return {"engine": ENGINE, "date": datetime.now().strftime("%Y-%m-%d"),
            "capital": CAPITAL, "positions": {}, "closed": [], "log": []}


def save(st: dict) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    st["updated"] = datetime.now().isoformat(timespec="seconds")
    STATE.write_text(json.dumps(st, indent=2))


def note(st: dict, event: str, **kw) -> None:
    st.setdefault("log", []).append(
        {"t": datetime.now().isoformat(timespec="seconds"), "event": event, **kw})


# ── commands ─────────────────────────────────────────────────────────────────
def cmd_scan(args) -> int:
    """Live structure table. This does NOT rank or recommend — ranking is the
    discretionary act and it belongs to the operator, not to a hidden formula
    that would quietly turn this back into a systematic engine."""
    syms = universe()
    q = full_quotes(syms)
    if not q:
        print("no quotes — token dead or market closed", file=sys.stderr)
        return 1
    rows = [dict(sym=s, **v) for s, v in q.items()]
    rows = [r for r in rows if r["volume"] and r["price"] * r["volume"] > 5e7]
    rows.sort(key=lambda r: -abs(r["chg_pct"]))
    n = args.top
    print(f"{'SYM':<14}{'LAST':>9}{'CHG%':>7}{'vsVWAP%':>9}{'RNGpos':>8}{'TURNOVER':>12}")
    print("-" * 59)
    for r in rows[:n]:
        to = r["price"] * r["volume"] / 1e7
        print(f"{r['sym']:<14}{r['price']:>9.2f}{r['chg_pct']:>7.2f}"
              f"{(r['vs_vwap_pct'] if r['vs_vwap_pct'] is not None else 0):>9.2f}"
              f"{(r['day_range_pos'] if r['day_range_pos'] is not None else -1):>8.1f}"
              f"{to:>11.1f}Cr")
    print(f"\n{len(rows)} names passed the Rs5Cr turnover floor.")
    return 0


def cmd_enter(args) -> int:
    st = load()
    sym, side = args.symbol.upper(), args.side.upper()
    if side not in ("LONG", "SHORT"):
        print("side must be LONG or SHORT", file=sys.stderr); return 1
    if sym in st["positions"]:
        print(f"{sym} already open", file=sys.stderr); return 1
    if len(st["positions"]) >= MAX_POSITIONS:
        print(f"at MAX_POSITIONS={MAX_POSITIONS}", file=sys.stderr); return 1
    if not args.thesis or len(args.thesis) < 25:
        print("thesis required (>=25 chars) — pre-registration is the point",
              file=sys.stderr); return 1

    if datetime.now().strftime("%H:%M") > NO_ENTRY_AFTER and not args.allow_late:
        print(f"past NO_ENTRY_AFTER={NO_ENTRY_AFTER} — yesterday every late candidate "
              f"failed on volume. Use --allow-late with a reason.", file=sys.stderr)
        return 1

    q = full_quotes([sym])
    if sym not in q:
        print(f"no live quote for {sym}", file=sys.stderr); return 1
    d = q[sym]
    px = d["price"]

    blocked, note_ = regime_blocks(side)
    if blocked and not args.allow_countertide:
        print(f"REGIME GATE blocks {sym} {side}: {note_}", file=sys.stderr)
        return 1
    print(f"  regime: {note_}")

    # BREAKOUT CONFIRMATION — the GESHIP rule. A "confirmed" candle only means the bar
    # closed beyond the PRIOR bar. It says nothing about whether price has since fallen
    # back inside that signal bar, which is what happened to GESHIP and cost 2.55x its
    # planned risk. Demand that price is still beyond the signal bar's own extreme.
    if REQUIRE_BREAKOUT and not args.allow_inside:
        try:
            # same Kite feed the signal engine uses. Two data sources here would mean a
            # gate that passes on one and fails on the other, which is worse than none.
            _c = kite_candles(sym, "5minute", 1)
            _today = datetime.now().date()
            _c = [x for x in _c if x["date"].date() == _today]
            bars = _c
            if len(bars) >= 2:
                bar = bars[-2]
                hi, lo = float(bar["high"]), float(bar["low"])
                if side == "LONG" and px <= hi:
                    print(f"BREAKOUT GATE blocks {sym}: {px} is not above the signal "
                          f"bar high {hi:.2f} — inside the bar, breakout unconfirmed",
                          file=sys.stderr)
                    return 1
                if side == "SHORT" and px >= lo:
                    print(f"BREAKOUT GATE blocks {sym}: {px} is not below the signal "
                          f"bar low {lo:.2f} — inside the bar, breakdown unconfirmed",
                          file=sys.stderr)
                    return 1
            else:
                print(f"  breakout gate: only {len(bars)} bars, cannot verify — "
                      f"proceeding on the candle verdict alone", file=sys.stderr)
        except Exception as e:
            print(f"  breakout gate: data unavailable ({type(e).__name__}) — "
                  f"NOT waving it through; re-run when data returns", file=sys.stderr)
            return 1

    # SHORT_VWAP_GATE — enforced, not remembered (2026-07-24: VWAP-only was
    # net-negative; it only pays as an AND-gate with the directional call)
    if side == "SHORT" and d["vwap"] and px >= d["vwap"]:
        print(f"SHORT_VWAP_GATE blocks {sym}: {px} >= VWAP {d['vwap']}", file=sys.stderr)
        return 1

    value = args.qty * px
    if value < MIN_POSITION_VALUE and not args.allow_small:
        print(f"position Rs{value:,.0f} < Rs{MIN_POSITION_VALUE:,.0f} cliff — "
              f"would pay 0.1060%. Raise qty to >= {int(MIN_POSITION_VALUE/px)+1} "
              f"or pass --allow-small with a reason.", file=sys.stderr)
        return 1

    deployed = sum(p["qty"] * p["entry"] for p in st["positions"].values())
    if deployed + value > CAPITAL:
        print(f"Rs{value:,.0f} would exceed the Rs{CAPITAL:,.0f} book "
              f"(Rs{deployed:,.0f} already deployed)", file=sys.stderr)
        return 1

    # stop must be on the losing side of entry, or it is not a stop
    if side == "LONG" and args.stop >= px:
        print(f"LONG stop {args.stop} must be below entry {px}", file=sys.stderr); return 1
    if side == "SHORT" and args.stop <= px:
        print(f"SHORT stop {args.stop} must be above entry {px}", file=sys.stderr); return 1

    risk = abs(px - args.stop) * args.qty
    st["positions"][sym] = {
        "side": side, "qty": args.qty, "entry": px,
        "entered_at": datetime.now().isoformat(timespec="seconds"),
        "stop": args.stop, "initial_stop": args.stop,
        "thesis": args.thesis,                   # written BEFORE the position exists
        "invalidation": args.invalidation or f"close beyond {args.stop}",
        "value": round(value, 2), "risk_inr": round(risk, 2),
        "entry_vwap": d["vwap"], "entry_chg_pct": d["chg_pct"],
        "high_water": px, "trail_armed": False, "peak_pnl_pct": 0.0,
    }
    note(st, "ENTRY", symbol=sym, side=side, qty=args.qty, price=px,
         stop=args.stop, value=round(value, 2), thesis=args.thesis)
    save(st)
    print(f"ENTERED {side} {args.qty} {sym} @ {px}  value Rs{value:,.0f}  "
          f"stop {args.stop}  risk Rs{risk:,.0f} ({risk/CAPITAL*100:.2f}% of book)")
    return 0


def _pnl_pct(p: dict, px: float) -> float:
    raw = (px - p["entry"]) / p["entry"] * 100
    return raw if p["side"] == "LONG" else -raw


def cmd_mark(args) -> int:
    """Mark to market and run exits. Trailing logic mirrors the arm0.3/step0.25
    variant from 770e0be — the only trail that cleared the pre-registered gate."""
    st = load()
    if not st["positions"]:
        print("no open positions"); return 0
    q = full_quotes(list(st["positions"].keys()))
    now = datetime.now().strftime("%H:%M")
    exits = []

    # DATA GAP ACCOUNTING. Observed live 2026-08-18 from ~10:05: the machine is on a
    # phone hotspot (router 172.20.10.1, ping 175-947ms) and api.kite.trade drops out
    # for minutes at a time. While that lasts, stops CANNOT fire — the book is open and
    # unmanaged. We refuse to substitute yfinance here: its NSE feed is ~15 minutes
    # delayed, so it would record exits at prices that never existed, and a corrupted
    # record is worse than an honest hole. Instead the hole is measured and carried into
    # the daily artifact, so EOD P&L is never read as if the book was supervised
    # throughout. This is the same lesson as the Jul 8/10 outage: the danger was not the
    # missing data, it was that the artifacts still looked complete.
    stamp = datetime.now().isoformat(timespec="seconds")
    if not q:
        gap = st.setdefault("data_gaps", {})
        if not gap.get("open_since"):
            gap["open_since"] = stamp
            note(st, "DATA_GAP_START", detail="quotes unavailable — stops cannot fire")
        st["blind_marks"] = st.get("blind_marks", 0) + 1
        save(st)
        print(f"  DATA GAP since {gap['open_since']} — book is UNMANAGED "
              f"({st['blind_marks']} blind checks)")
    else:
        gap = st.setdefault("data_gaps", {})
        if gap.get("open_since"):
            started = gap.pop("open_since")
            secs = int((datetime.fromisoformat(stamp) -
                        datetime.fromisoformat(started)).total_seconds())
            gap.setdefault("closed", []).append(
                {"from": started, "to": stamp, "seconds": secs})
            note(st, "DATA_GAP_END", started=started, seconds=secs)
            print(f"  data restored — book was blind for {secs}s")

    for sym, p in list(st["positions"].items()):
        if sym not in q:
            print(f"  {sym}: NO QUOTE — holding, not guessing"); continue
        px = q[sym]["price"]
        pnl_pct = _pnl_pct(p, px)
        p["peak_pnl_pct"] = max(p.get("peak_pnl_pct", 0.0), pnl_pct)

        # arm the trail only once the 1.3% floor is banked
        if not p["trail_armed"] and pnl_pct >= TARGET_FLOOR_PCT:
            p["trail_armed"] = True
            note(st, "TRAIL_ARMED", symbol=sym, at_pct=round(pnl_pct, 2))
        if p["trail_armed"]:
            give_back = p["peak_pnl_pct"] - TRAIL_STEP_PCT
            trail_px = (p["entry"] * (1 + give_back / 100) if p["side"] == "LONG"
                        else p["entry"] * (1 - give_back / 100))
            p["stop"] = (max(p["stop"], round(trail_px, 2)) if p["side"] == "LONG"
                         else min(p["stop"], round(trail_px, 2)))

        # TIME EXIT — the KFINTECH rule. A position that has not reached the 1.3%
        # floor within MAX_HOLD_MIN is not being patient, it is occupying a slot.
        # Deliberately only applies BELOW the floor: once the trail is armed the
        # position has proved itself and is allowed to run to the close.
        held_min = (datetime.now() -
                    datetime.fromisoformat(p["entered_at"])).total_seconds() / 60
        stale = (held_min >= MAX_HOLD_MIN and not p["trail_armed"])

        hit = ((p["side"] == "LONG" and px <= p["stop"]) or
               (p["side"] == "SHORT" and px >= p["stop"]))
        forced = now >= SQUARE_OFF
        if hit or forced or stale:
            if hit:
                reason = "TRAIL" if p["trail_armed"] else "STOP"
            elif forced:
                reason = "SQUARE_OFF"
            else:
                reason = f"TIME_EXIT_{int(held_min)}m"
            exits.append((sym, px, reason))
        else:
            print(f"  {sym:<12} {p['side']:<5} {px:>9.2f}  P&L {pnl_pct:+6.2f}%  "
                  f"stop {p['stop']:>8.2f}  {'trailing' if p['trail_armed'] else 'initial'}")

    for sym, px, reason in exits:
        _close(st, sym, px, reason)
    save(st)
    _print_book(st, q)
    return 0


def _close(st: dict, sym: str, px: float, reason: str) -> None:
    p = st["positions"].pop(sym)
    qty, entry, side = p["qty"], p["entry"], p["side"]
    gross = (px - entry) * qty if side == "LONG" else (entry - px) * qty
    rc = real_cost(qty, entry, px, side)
    fc = fleet_cost(qty, entry, px)
    # symbol lives in the positions dict KEY, so **p alone loses it and the daily
    # artifact ends up recording trades that do not say what was traded.
    rec = {"symbol": sym, **p, "exit": px, "exit_at": datetime.now().isoformat(timespec="seconds"),
           "exit_reason": reason,
           "gross_pnl": round(gross, 2),
           "real_cost": rc, "net_pnl_real": round(gross - rc["total"], 2),
           "fleet_cost": fc, "net_pnl_fleet": round(gross - fc, 2),
           "pnl_pct": round(_pnl_pct(p, px), 3)}
    st.setdefault("closed", []).append(rec)
    note(st, "EXIT", symbol=sym, price=px, reason=reason,
         gross=round(gross, 2), net_real=rec["net_pnl_real"])
    print(f"  CLOSED {sym} {reason} @ {px}  gross Rs{gross:+,.0f}  "
          f"cost Rs{rc['total']:,.0f} ({rc['pct_of_turnover']}%)  "
          f"net Rs{rec['net_pnl_real']:+,.0f}")


def cmd_close(args) -> int:
    st = load()
    sym = args.symbol.upper()
    if sym not in st["positions"]:
        print(f"{sym} not open", file=sys.stderr); return 1
    q = full_quotes([sym])
    if sym not in q:
        print(f"no quote for {sym} — refusing to close at a made-up price", file=sys.stderr)
        return 1
    _close(st, sym, q[sym]["price"], args.reason or "MANUAL")
    save(st)
    return 0


def _print_book(st: dict, q: dict | None = None) -> None:
    closed = st.get("closed", [])
    real = sum(c["net_pnl_real"] for c in closed)
    fleetp = sum(c["net_pnl_fleet"] for c in closed)
    gross = sum(c["gross_pnl"] for c in closed)
    open_mtm = 0.0
    for sym, p in st["positions"].items():
        if q and sym in q:
            px = q[sym]["price"]
            open_mtm += ((px - p["entry"]) * p["qty"] if p["side"] == "LONG"
                         else (p["entry"] - px) * p["qty"])
    print(f"\n  closed {len(closed)}  gross Rs{gross:+,.0f}  "
          f"net(real) Rs{real:+,.0f}  net(fleet 12bps) Rs{fleetp:+,.0f}")
    if st["positions"]:
        print(f"  open {len(st['positions'])}  unrealised Rs{open_mtm:+,.0f}")
    print(f"  book Rs{CAPITAL:,.0f}  return {(real + open_mtm)/CAPITAL*100:+.3f}%")


def cmd_eod(args) -> int:
    """Daily artifact in fleet format + an honest scorecard. Writes the day's
    reasoning alongside the P&L, because the reasoning is the part with a shelf
    life longer than one session."""
    st = load()
    if st["positions"]:
        print(f"WARNING: {len(st['positions'])} position(s) still open — "
              f"run mark after {SQUARE_OFF} or close them first", file=sys.stderr)
    closed = st.get("closed", [])
    gross = sum(c["gross_pnl"] for c in closed)
    real = sum(c["net_pnl_real"] for c in closed)
    fleetp = sum(c["net_pnl_fleet"] for c in closed)
    cost_real = sum(c["real_cost"]["total"] for c in closed)
    wins = [c for c in closed if c["net_pnl_real"] > 0]
    turnover = sum(c["qty"] * (c["entry"] + c["exit"]) for c in closed)
    sizes = sorted(c["qty"] * c["entry"] for c in closed)
    med = sizes[len(sizes) // 2] if sizes else 0

    day = {
        "engine": ENGINE,
        "date": st.get("date"),
        "mandate": "discretionary (LLM), full NIFTY-200, long+short, SHORT_VWAP_GATE on",
        "capital": CAPITAL,
        "trades": len(closed),
        "wins": len(wins),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "gross_pnl": round(gross, 2),
        "cost_real": round(cost_real, 2),
        "net_pnl": round(real, 2),
        "net_pnl_fleet_model": round(fleetp, 2),
        "return_pct": round(real / CAPITAL * 100, 3),
        "median_position_value": round(med, 2),
        "above_cost_cliff": med > MIN_POSITION_VALUE,
        "cost_pct_of_turnover": round(cost_real / turnover * 100, 4) if turnover else None,
        "closed": closed,
        "data_gaps": (st.get("data_gaps", {}) or {}).get("closed", []),
        "blind_marks": st.get("blind_marks", 0),
        "blind_seconds_total": sum(g["seconds"] for g in
                                   (st.get("data_gaps", {}) or {}).get("closed", [])),
        "log": st.get("log", []),
        "caveat": ("Single session, n={} trades. This stack's measured gross edge is "
                   "+0.069% against a 0.1060% toll and no searched variant survived "
                   "holdout at real fees (02565eb). Nothing here is evidence of an "
                   "edge; it is one sample of a logged decision process."
                   .format(len(closed))),
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    f = OUTDIR / f"{st.get('date')}.json"
    f.write_text(json.dumps(day, indent=2))

    print(f"v5_god — {st.get('date')}")
    print("=" * 58)
    print(f"  trades        {len(closed)}   wins {len(wins)}"
          + (f"   WR {day['win_rate']}%" if closed else ""))
    print(f"  gross         Rs{gross:+,.2f}")
    print(f"  real cost     Rs{cost_real:,.2f}"
          + (f"  ({day['cost_pct_of_turnover']}% of turnover)" if turnover else ""))
    print(f"  NET           Rs{real:+,.2f}   ({day['return_pct']:+.3f}% on Rs{CAPITAL:,.0f})")
    print(f"  net @12bps    Rs{fleetp:+,.2f}   (fleet-comparable)")
    print(f"  median size   Rs{med:,.0f}   cliff cleared: {day['above_cost_cliff']}")
    print(f"\n  written: {f}")
    return 0


def cmd_enter(args) -> int:
    st = load()
    sym, side = args.symbol.upper(), args.side.upper()
    if side not in ("LONG", "SHORT"):
        print("side must be LONG or SHORT", file=sys.stderr); return 1
    if sym in st["positions"]:
        print(f"{sym} already open", file=sys.stderr); return 1
    if len(st["positions"]) >= MAX_POSITIONS:
        print(f"at MAX_POSITIONS={MAX_POSITIONS}", file=sys.stderr); return 1
    if not args.thesis or len(args.thesis) < 25:
        print("thesis required (>=25 chars) — pre-registration is the point",
              file=sys.stderr); return 1

    if datetime.now().strftime("%H:%M") > NO_ENTRY_AFTER and not args.allow_late:
        print(f"past NO_ENTRY_AFTER={NO_ENTRY_AFTER} — yesterday every late candidate "
              f"failed on volume. Use --allow-late with a reason.", file=sys.stderr)
        return 1

    q = full_quotes([sym])
    if sym not in q:
        print(f"no live quote for {sym}", file=sys.stderr); return 1
    d = q[sym]
    px = d["price"]

    # BREAKOUT CONFIRMATION — the GESHIP rule. A "confirmed" candle only means the bar
    # closed beyond the PRIOR bar. It says nothing about whether price has since fallen
    # back inside that signal bar, which is what happened to GESHIP and cost 2.55x its
    # planned risk. Demand that price is still beyond the signal bar's own extreme.
    if REQUIRE_BREAKOUT and not args.allow_inside:
        try:
            # same Kite feed the signal engine uses. Two data sources here would mean a
            # gate that passes on one and fails on the other, which is worse than none.
            _c = kite_candles(sym, "5minute", 1)
            _today = datetime.now().date()
            _c = [x for x in _c if x["date"].date() == _today]
            bars = _c
            if len(bars) >= 2:
                bar = bars[-2]
                hi, lo = float(bar["high"]), float(bar["low"])
                if side == "LONG" and px <= hi:
                    print(f"BREAKOUT GATE blocks {sym}: {px} is not above the signal "
                          f"bar high {hi:.2f} — inside the bar, breakout unconfirmed",
                          file=sys.stderr)
                    return 1
                if side == "SHORT" and px >= lo:
                    print(f"BREAKOUT GATE blocks {sym}: {px} is not below the signal "
                          f"bar low {lo:.2f} — inside the bar, breakdown unconfirmed",
                          file=sys.stderr)
                    return 1
            else:
                print(f"  breakout gate: only {len(bars)} bars, cannot verify — "
                      f"proceeding on the candle verdict alone", file=sys.stderr)
        except Exception as e:
            print(f"  breakout gate: data unavailable ({type(e).__name__}) — "
                  f"NOT waving it through; re-run when data returns", file=sys.stderr)
            return 1

    # SHORT_VWAP_GATE — enforced, not remembered (2026-07-24: VWAP-only was
    # net-negative; it only pays as an AND-gate with the directional call)
    if side == "SHORT" and d["vwap"] and px >= d["vwap"]:
        print(f"SHORT_VWAP_GATE blocks {sym}: {px} >= VWAP {d['vwap']}", file=sys.stderr)
        return 1

    value = args.qty * px
    if value < MIN_POSITION_VALUE and not args.allow_small:
        print(f"position Rs{value:,.0f} < Rs{MIN_POSITION_VALUE:,.0f} cliff — "
              f"would pay 0.1060%. Raise qty to >= {int(MIN_POSITION_VALUE/px)+1} "
              f"or pass --allow-small with a reason.", file=sys.stderr)
        return 1

    deployed = sum(p["qty"] * p["entry"] for p in st["positions"].values())
    if deployed + value > CAPITAL:
        print(f"Rs{value:,.0f} would exceed the Rs{CAPITAL:,.0f} book "
              f"(Rs{deployed:,.0f} already deployed)", file=sys.stderr)
        return 1

    # stop must be on the losing side of entry, or it is not a stop
    if side == "LONG" and args.stop >= px:
        print(f"LONG stop {args.stop} must be below entry {px}", file=sys.stderr); return 1
    if side == "SHORT" and args.stop <= px:
        print(f"SHORT stop {args.stop} must be above entry {px}", file=sys.stderr); return 1

    risk = abs(px - args.stop) * args.qty
    st["positions"][sym] = {
        "side": side, "qty": args.qty, "entry": px,
        "entered_at": datetime.now().isoformat(timespec="seconds"),
        "stop": args.stop, "initial_stop": args.stop,
        "thesis": args.thesis,                   # written BEFORE the position exists
        "invalidation": args.invalidation or f"close beyond {args.stop}",
        "value": round(value, 2), "risk_inr": round(risk, 2),
        "entry_vwap": d["vwap"], "entry_chg_pct": d["chg_pct"],
        "high_water": px, "trail_armed": False, "peak_pnl_pct": 0.0,
    }
    note(st, "ENTRY", symbol=sym, side=side, qty=args.qty, price=px,
         stop=args.stop, value=round(value, 2), thesis=args.thesis)
    save(st)
    print(f"ENTERED {side} {args.qty} {sym} @ {px}  value Rs{value:,.0f}  "
          f"stop {args.stop}  risk Rs{risk:,.0f} ({risk/CAPITAL*100:.2f}% of book)")
    return 0


def _pnl_pct(p: dict, px: float) -> float:
    raw = (px - p["entry"]) / p["entry"] * 100
    return raw if p["side"] == "LONG" else -raw


def cmd_mark(args) -> int:
    """Mark to market and run exits. Trailing logic mirrors the arm0.3/step0.25
    variant from 770e0be — the only trail that cleared the pre-registered gate."""
    st = load()
    if not st["positions"]:
        print("no open positions"); return 0
    q = full_quotes(list(st["positions"].keys()))
    now = datetime.now().strftime("%H:%M")
    exits = []

    # DATA GAP ACCOUNTING. Observed live 2026-08-18 from ~10:05: the machine is on a
    # phone hotspot (router 172.20.10.1, ping 175-947ms) and api.kite.trade drops out
    # for minutes at a time. While that lasts, stops CANNOT fire — the book is open and
    # unmanaged. We refuse to substitute yfinance here: its NSE feed is ~15 minutes
    # delayed, so it would record exits at prices that never existed, and a corrupted
    # record is worse than an honest hole. Instead the hole is measured and carried into
    # the daily artifact, so EOD P&L is never read as if the book was supervised
    # throughout. This is the same lesson as the Jul 8/10 outage: the danger was not the
    # missing data, it was that the artifacts still looked complete.
    stamp = datetime.now().isoformat(timespec="seconds")
    if not q:
        gap = st.setdefault("data_gaps", {})
        if not gap.get("open_since"):
            gap["open_since"] = stamp
            note(st, "DATA_GAP_START", detail="quotes unavailable — stops cannot fire")
        st["blind_marks"] = st.get("blind_marks", 0) + 1
        save(st)
        print(f"  DATA GAP since {gap['open_since']} — book is UNMANAGED "
              f"({st['blind_marks']} blind checks)")
    else:
        gap = st.setdefault("data_gaps", {})
        if gap.get("open_since"):
            started = gap.pop("open_since")
            secs = int((datetime.fromisoformat(stamp) -
                        datetime.fromisoformat(started)).total_seconds())
            gap.setdefault("closed", []).append(
                {"from": started, "to": stamp, "seconds": secs})
            note(st, "DATA_GAP_END", started=started, seconds=secs)
            print(f"  data restored — book was blind for {secs}s")

    for sym, p in list(st["positions"].items()):
        if sym not in q:
            print(f"  {sym}: NO QUOTE — holding, not guessing"); continue
        px = q[sym]["price"]
        pnl_pct = _pnl_pct(p, px)
        p["peak_pnl_pct"] = max(p.get("peak_pnl_pct", 0.0), pnl_pct)

        # arm the trail only once the 1.3% floor is banked
        if not p["trail_armed"] and pnl_pct >= TARGET_FLOOR_PCT:
            p["trail_armed"] = True
            note(st, "TRAIL_ARMED", symbol=sym, at_pct=round(pnl_pct, 2))
        if p["trail_armed"]:
            give_back = p["peak_pnl_pct"] - TRAIL_STEP_PCT
            trail_px = (p["entry"] * (1 + give_back / 100) if p["side"] == "LONG"
                        else p["entry"] * (1 - give_back / 100))
            p["stop"] = (max(p["stop"], round(trail_px, 2)) if p["side"] == "LONG"
                         else min(p["stop"], round(trail_px, 2)))

        # TIME EXIT — the KFINTECH rule. A position that has not reached the 1.3%
        # floor within MAX_HOLD_MIN is not being patient, it is occupying a slot.
        # Deliberately only applies BELOW the floor: once the trail is armed the
        # position has proved itself and is allowed to run to the close.
        held_min = (datetime.now() -
                    datetime.fromisoformat(p["entered_at"])).total_seconds() / 60
        stale = (held_min >= MAX_HOLD_MIN and not p["trail_armed"])

        hit = ((p["side"] == "LONG" and px <= p["stop"]) or
               (p["side"] == "SHORT" and px >= p["stop"]))
        forced = now >= SQUARE_OFF
        if hit or forced or stale:
            if hit:
                reason = "TRAIL" if p["trail_armed"] else "STOP"
            elif forced:
                reason = "SQUARE_OFF"
            else:
                reason = f"TIME_EXIT_{int(held_min)}m"
            exits.append((sym, px, reason))
        else:
            print(f"  {sym:<12} {p['side']:<5} {px:>9.2f}  P&L {pnl_pct:+6.2f}%  "
                  f"stop {p['stop']:>8.2f}  {'trailing' if p['trail_armed'] else 'initial'}")

    for sym, px, reason in exits:
        _close(st, sym, px, reason)
    save(st)
    _print_book(st, q)
    return 0


def _close(st: dict, sym: str, px: float, reason: str) -> None:
    p = st["positions"].pop(sym)
    qty, entry, side = p["qty"], p["entry"], p["side"]
    gross = (px - entry) * qty if side == "LONG" else (entry - px) * qty
    rc = real_cost(qty, entry, px, side)
    fc = fleet_cost(qty, entry, px)
    # symbol lives in the positions dict KEY, so **p alone loses it and the daily
    # artifact ends up recording trades that do not say what was traded.
    rec = {"symbol": sym, **p, "exit": px, "exit_at": datetime.now().isoformat(timespec="seconds"),
           "exit_reason": reason,
           "gross_pnl": round(gross, 2),
           "real_cost": rc, "net_pnl_real": round(gross - rc["total"], 2),
           "fleet_cost": fc, "net_pnl_fleet": round(gross - fc, 2),
           "pnl_pct": round(_pnl_pct(p, px), 3)}
    st.setdefault("closed", []).append(rec)
    note(st, "EXIT", symbol=sym, price=px, reason=reason,
         gross=round(gross, 2), net_real=rec["net_pnl_real"])
    print(f"  CLOSED {sym} {reason} @ {px}  gross Rs{gross:+,.0f}  "
          f"cost Rs{rc['total']:,.0f} ({rc['pct_of_turnover']}%)  "
          f"net Rs{rec['net_pnl_real']:+,.0f}")


def cmd_close(args) -> int:
    st = load()
    sym = args.symbol.upper()
    if sym not in st["positions"]:
        print(f"{sym} not open", file=sys.stderr); return 1
    q = full_quotes([sym])
    if sym not in q:
        print(f"no quote for {sym} — refusing to close at a made-up price", file=sys.stderr)
        return 1
    _close(st, sym, q[sym]["price"], args.reason or "MANUAL")
    save(st)
    return 0


def _print_book(st: dict, q: dict | None = None) -> None:
    closed = st.get("closed", [])
    real = sum(c["net_pnl_real"] for c in closed)
    fleetp = sum(c["net_pnl_fleet"] for c in closed)
    gross = sum(c["gross_pnl"] for c in closed)
    open_mtm = 0.0
    for sym, p in st["positions"].items():
        if q and sym in q:
            px = q[sym]["price"]
            open_mtm += ((px - p["entry"]) * p["qty"] if p["side"] == "LONG"
                         else (p["entry"] - px) * p["qty"])
    print(f"\n  closed {len(closed)}  gross Rs{gross:+,.0f}  "
          f"net(real) Rs{real:+,.0f}  net(fleet 12bps) Rs{fleetp:+,.0f}")
    if st["positions"]:
        print(f"  open {len(st['positions'])}  unrealised Rs{open_mtm:+,.0f}")
    print(f"  book Rs{CAPITAL:,.0f}  return {(real + open_mtm)/CAPITAL*100:+.3f}%")


def cmd_eod(args) -> int:
    """Daily artifact in fleet format + an honest scorecard. Writes the day's
    reasoning alongside the P&L, because the reasoning is the part with a shelf
    life longer than one session."""
    st = load()
    if st["positions"]:
        print(f"WARNING: {len(st['positions'])} position(s) still open — "
              f"run mark after {SQUARE_OFF} or close them first", file=sys.stderr)
    closed = st.get("closed", [])
    gross = sum(c["gross_pnl"] for c in closed)
    real = sum(c["net_pnl_real"] for c in closed)
    fleetp = sum(c["net_pnl_fleet"] for c in closed)
    cost_real = sum(c["real_cost"]["total"] for c in closed)
    wins = [c for c in closed if c["net_pnl_real"] > 0]
    turnover = sum(c["qty"] * (c["entry"] + c["exit"]) for c in closed)
    sizes = sorted(c["qty"] * c["entry"] for c in closed)
    med = sizes[len(sizes) // 2] if sizes else 0

    day = {
        "engine": ENGINE,
        "date": st.get("date"),
        "mandate": "discretionary (LLM), full NIFTY-200, long+short, SHORT_VWAP_GATE on",
        "capital": CAPITAL,
        "trades": len(closed),
        "wins": len(wins),
        "win_rate": round(len(wins) / len(closed) * 100, 1) if closed else None,
        "gross_pnl": round(gross, 2),
        "cost_real": round(cost_real, 2),
        "net_pnl": round(real, 2),
        "net_pnl_fleet_model": round(fleetp, 2),
        "return_pct": round(real / CAPITAL * 100, 3),
        "median_position_value": round(med, 2),
        "above_cost_cliff": med > MIN_POSITION_VALUE,
        "cost_pct_of_turnover": round(cost_real / turnover * 100, 4) if turnover else None,
        "closed": closed,
        "data_gaps": (st.get("data_gaps", {}) or {}).get("closed", []),
        "blind_marks": st.get("blind_marks", 0),
        "blind_seconds_total": sum(g["seconds"] for g in
                                   (st.get("data_gaps", {}) or {}).get("closed", [])),
        "log": st.get("log", []),
        "caveat": ("Single session, n={} trades. This stack's measured gross edge is "
                   "+0.069% against a 0.1060% toll and no searched variant survived "
                   "holdout at real fees (02565eb). Nothing here is evidence of an "
                   "edge; it is one sample of a logged decision process."
                   .format(len(closed))),
    }
    OUTDIR.mkdir(parents=True, exist_ok=True)
    f = OUTDIR / f"{st.get('date')}.json"
    f.write_text(json.dumps(day, indent=2))

    print(f"v5_god — {st.get('date')}")
    print("=" * 58)
    print(f"  trades        {len(closed)}   wins {len(wins)}"
          + (f"   WR {day['win_rate']}%" if closed else ""))
    print(f"  gross         Rs{gross:+,.2f}")
    print(f"  real cost     Rs{cost_real:,.2f}"
          + (f"  ({day['cost_pct_of_turnover']}% of turnover)" if turnover else ""))
    print(f"  NET           Rs{real:+,.2f}   ({day['return_pct']:+.3f}% on Rs{CAPITAL:,.0f})")
    print(f"  net @12bps    Rs{fleetp:+,.2f}   (fleet-comparable)")
    print(f"  median size   Rs{med:,.0f}   cliff cleared: {day['above_cost_cliff']}")
    print(f"\n  written: {f}")
    return 0


def cmd_compare(args) -> int:
    """Score v5_god against every systematic engine on the SAME day.

    Deliberately unflattering to this book. Engines are ranked on net P&L as a RETURN
    ON THEIR OWN CAPITAL, never in rupees, because v5_god runs Rs2L while the fleet runs
    Rs10L pools. And v5_god is scored on its net_pnl_fleet_model column — the same flat
    12bps everyone else is charged — rather than its more accurate real-cost figure, so
    it cannot win on fee modelling the others do not have.

    Schema verified against real dailies 2026-08-18: fleet engines nest results in
    summary{total_pnl, total_pnl_net, total_cost, trades} with capital at total_capital.
    us_v1 has no total_pnl_net and is skipped rather than guessed at — it is a US
    long-only cash book and does not belong in a same-tape comparison anyway.
    """
    import glob
    date = args.date or datetime.now().strftime("%Y-%m-%d")
    rows, skipped = [], []
    for f in sorted(glob.glob(str(ROOT / "docs" / "paper-trades" / "*" / f"{date}.json"))):
        eng = Path(f).parent.name
        try:
            d = json.loads(Path(f).read_text())
        except Exception as e:
            skipped.append(f"{eng} (unreadable: {type(e).__name__})"); continue
        if eng == ENGINE:
            net, cap = d.get("net_pnl_fleet_model"), d.get("capital")
            n, cost = d.get("trades"), d.get("cost_real")
        else:
            summ = d.get("summary") or {}
            if "total_pnl_net" not in summ:
                skipped.append(eng); continue
            net, cost = summ.get("total_pnl_net"), summ.get("total_cost")
            n, cap = summ.get("trades"), d.get("total_capital")
        if net is None or not cap:
            skipped.append(eng); continue
        try:
            rows.append({"engine": eng, "net": float(net), "capital": float(cap),
                         "trades": n or 0, "cost": float(cost or 0),
                         "ret_pct": float(net) / float(cap) * 100})
        except (TypeError, ValueError):
            skipped.append(eng)

    rows.sort(key=lambda r: -r["ret_pct"])
    print(f"engine comparison - {date}   (net on own capital, all at 12bps)")
    print(f"{'ENGINE':<14}{'TRADES':>7}{'NET Rs':>11}{'COST Rs':>10}{'CAPITAL':>12}{'RETURN%':>9}")
    print("-" * 64)
    for r in rows:
        mark = "  <-- discretionary" if r["engine"] == ENGINE else ""
        print(f"{r['engine']:<14}{r['trades']:>7}{r['net']:>11,.0f}{r['cost']:>10,.0f}"
              f"{r['capital']:>12,.0f}{r['ret_pct']:>+9.3f}{mark}")
    if skipped:
        print(f"\n  skipped (no comparable schema): {', '.join(skipped)}")
    me = [r for r in rows if r["engine"] == ENGINE]
    if me:
        print(f"\n  v5_god ranked {rows.index(me[0]) + 1} of {len(rows)} on {me[0]['trades']} "
              f"trades. One session — rank here is noise, not skill.")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan"); s.add_argument("--top", type=int, default=40)
    s.set_defaults(fn=cmd_scan)

    e = sub.add_parser("enter")
    e.add_argument("symbol"); e.add_argument("side")
    e.add_argument("--qty", type=int, required=True)
    e.add_argument("--stop", type=float, required=True)
    e.add_argument("--thesis", required=True)
    e.add_argument("--invalidation")
    e.add_argument("--allow-small", action="store_true")
    e.add_argument("--allow-late", action="store_true")
    e.add_argument("--allow-inside", action="store_true")
    e.add_argument("--allow-countertide", action="store_true")
    e.set_defaults(fn=cmd_enter)

    g = sub.add_parser("signal"); g.add_argument("symbols", nargs="+")
    g.set_defaults(fn=cmd_signal)

    rg = sub.add_parser("regime")
    rg.set_defaults(fn=lambda a: (print(json.dumps(market_regime(), indent=2)), 0)[1])

    m = sub.add_parser("mark"); m.set_defaults(fn=cmd_mark)

    c = sub.add_parser("close"); c.add_argument("symbol")
    c.add_argument("--reason"); c.set_defaults(fn=cmd_close)

    d = sub.add_parser("eod"); d.set_defaults(fn=cmd_eod)

    cp = sub.add_parser("compare"); cp.add_argument("--date")
    cp.set_defaults(fn=cmd_compare)

    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
