"""
TradePilot Prototype -- Flask web server.
Serves the HTML dashboard and API endpoints.
Transforms backend data to match frontend's expected format.
"""
from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from datetime import datetime
from pathlib import Path
import json
import os
import sys
import traceback

sys.path.insert(0, os.path.dirname(__file__))

from data_engine import get_market_indices, load_stock_data, NIFTY_STOCKS
from ai_scorer import score_stocks, train_model
from analytics import (track_visit, track_page_view, track_stock_view,
                       track_swipe, track_paper_trade, track_wizard_search,
                       track_feedback, get_dashboard_stats)

# Try to use v2 engine, fallback to v1
try:
    from trading_engine import score_stocks_v2, train_ensemble
    HAS_V2 = True
    print("[ENGINE] v2 ensemble loaded (XGBoost + LightGBM)")
except ImportError:
    HAS_V2 = False
    print("[ENGINE] v2 not available, using v1")

# Try to load v3 regime-aware engine
try:
    from trading_engine_v3 import score_stocks_v3
    HAS_V3 = True
    print("[ENGINE] v3 regime-aware engine loaded")
except ImportError:
    HAS_V3 = False
    print("[ENGINE] v3 not available")

# Try to load v4 composite scorer
try:
    from v4.composite_scorer import score_all_stocks as score_stocks_v4
    HAS_V4 = True
    print("[ENGINE] v4 composite scorer loaded")
except ImportError:
    HAS_V4 = False
    print("[ENGINE] v4 not available")

app = Flask(__name__,
            template_folder=os.path.join(os.path.dirname(__file__), "templates"),
            static_folder=os.path.join(os.path.dirname(__file__), "static"))
CORS(app, origins=["http://localhost:*", "http://127.0.0.1:*", "https://tradepilot.onrender.com"])  # Restricted CORS
app.config["TEMPLATES_AUTO_RELOAD"] = True  # pick up template edits without a process restart (debug stays off)


def get_model_meta():
    # Prefer v2 meta
    v2_path = os.path.join(os.path.dirname(__file__), "models", "model_meta_v2.json")
    v1_path = os.path.join(os.path.dirname(__file__), "models", "model_meta.json")
    for path in [v2_path, v1_path]:
        if os.path.exists(path):
            with open(path) as f:
                return json.load(f)
    return None


def get_model_meta_v3():
    """Load v3 model metadata."""
    v3_path = os.path.join(os.path.dirname(__file__), "models", "model_meta_v3.json")
    if os.path.exists(v3_path):
        with open(v3_path) as f:
            return json.load(f)
    return None


def get_backtest_results():
    path = os.path.join(os.path.dirname(__file__), "models", "backtest_results.json")
    if os.path.exists(path):
        with open(path) as f:
            return json.load(f)
    return None


@app.route("/")
def index():
    return render_template("index.html")

@app.route("/landing")
def landing():
    """Premium landing page for client demos."""
    return render_template("landing.html")


@app.route("/dashboard")
def dashboard():
    """Live trading desk — macOS-style multi-panel dashboard."""
    return render_template("dashboard.html")


@app.route("/live")
def live_view():
    """Live agent-network view — radial visualization of engines + open positions.
    Inspired by quant trading dashboards (inferencesaver style). Built 2026-05-12."""
    return render_template("live.html")


@app.route("/lab")
def lab_view():
    """A/B testing lab — challenger-vs-live experiments in one place."""
    return render_template("lab.html")

@app.route("/decisions")
def decisions_view():
    """Decision dashboard — root-cause verdict, engine roster, and the RC roadmap (TP-RCA)."""
    return render_template("decisions.html")


@app.route("/api/missed-opportunities")
def api_missed_opportunities():
    """Reads the missed-opportunities watchdog snapshot.
    The watchdog (scripts/missed-opportunities-watchdog.py) writes a JSON every
    3 min during market hours. This endpoint just serves the latest snapshot.
    Returns {} if watchdog hasn't run yet."""
    snap = os.path.join(os.path.dirname(__file__), "data", "missed-opportunities.json")
    if not os.path.exists(snap):
        return jsonify({"status": "no_snapshot_yet", "hint": "run scripts/missed-opportunities-watchdog.py"})
    try:
        with open(snap) as f:
            return jsonify(json.load(f))
    except (json.JSONDecodeError, IOError) as e:
        return jsonify({"status": "snapshot_unreadable", "error": str(e)}), 500


@app.route("/api/positions-live")
def api_positions_live():
    """Open positions for ALL 7 active engines (v4, v5, v5_classic, v5_6, v5_7, v5_8, v6).
    Reads each engine's state file directly:
      - v4 uses docs/paper-trades/v4/{YYYY-MM-DD}.json (date-stamped, list under 'positions')
      - v5 family uses docs/paper-trades/{engine}/positions_active.json (nested by pool)
    Normalizes both shapes to a flat {engine: [position]} dict.
    Replaces /api/engine-arena for /live (which only returned 5 legacy engines).
    Added 2026-05-12 to fix /live missing v4, v5, v6 positions.
    Read-only — does NOT touch engine state files."""
    from datetime import date
    from pathlib import Path

    TODAY = date.today().isoformat()
    BASE = Path(os.path.dirname(__file__)).parent / "docs" / "paper-trades"

    result = {}

    # v4: date-stamped state file
    v4_file = BASE / "v4" / f"{TODAY}.json"
    if v4_file.exists():
        try:
            with open(v4_file) as f:
                v4_state = json.load(f)
            v4_positions = []
            # v4 state has 'positions' key — list of position dicts
            for p in (v4_state.get("positions") or []):
                if p.get("status") != "open":
                    continue
                v4_positions.append({
                    "symbol": p.get("symbol", "?"),
                    "entry_price": p.get("entry_price", p.get("price", 0)),
                    "direction": p.get("direction", "LONG"),
                    "qty": p.get("qty", 0),
                    "unrealized_pnl": p.get("unrealized_pnl", 0),
                    "sl_price": p.get("sl_price", 0),
                    "target_price": p.get("target_price", 0),
                })
            result["v4"] = v4_positions
        except (json.JSONDecodeError, IOError):
            result["v4"] = []
    else:
        result["v4"] = []

    # v5 family + v6: positions_active.json with positions nested by pool
    for engine in ["v5", "v5_classic", "v5_6", "v5_7", "v5_8", "v6"]:
        f = BASE / engine / "positions_active.json"
        if not f.exists():
            result[engine] = []
            continue
        try:
            with open(f) as fp:
                data = json.load(fp)
            positions_by_pool = data.get("positions", {})
            flat = []
            # positions can be a dict {pool: [pos]} OR a flat list
            if isinstance(positions_by_pool, dict):
                for pool, plist in positions_by_pool.items():
                    if not isinstance(plist, list):
                        continue
                    for p in plist:
                        flat.append({
                            "symbol": p.get("symbol", "?"),
                            "entry_price": p.get("entry_price", 0),
                            "direction": p.get("direction", p.get("position_type", "LONG")),
                            "qty": p.get("qty", 0),
                            "unrealized_pnl": p.get("unrealized_pnl", 0),
                            "sl_price": p.get("sl_price", 0),
                            "target_price": p.get("target_price", 0),
                            "pool": pool,
                        })
            elif isinstance(positions_by_pool, list):
                for p in positions_by_pool:
                    flat.append({
                        "symbol": p.get("symbol", "?"),
                        "entry_price": p.get("entry_price", 0),
                        "direction": p.get("direction", "LONG"),
                        "qty": p.get("qty", 0),
                        "unrealized_pnl": p.get("unrealized_pnl", 0),
                    })
            result[engine] = flat
        except (json.JSONDecodeError, IOError):
            result[engine] = []

    return jsonify({
        "date": TODAY,
        "positions": result,
        "totals": {
            "engines": len(result),
            "open_total": sum(len(v) for v in result.values()),
        },
    })


# ── Live engine roster: single source of truth = launch-market.sh ENGINES array ──
# The /live dashboard derives its roster + colors from here so it auto-syncs when
# engines are added/retired in the launcher — it can never go stale again.
import re as _re_roster
_LAUNCH_SH = Path(os.path.dirname(__file__)).parent / "scripts" / "launch-market.sh"
ENGINE_COLORS = {
    "v5": "#c77dff", "v5_classic": "#5bf08a", "v7_regime": "#ff8c42",
    "v5_noml": "#ffce5b", "v5_apr": "#4dd0e1", "v4": "#28e0f0", "v6": "#ff5d73",
}
_FALLBACK_PALETTE = ["#c77dff", "#5bf08a", "#ff8c42", "#ffce5b", "#4dd0e1", "#ff5d73", "#7c9cff"]


def _active_engines():
    """Live roster = the uncommented "name|script" lines in launch-market.sh's
    ENGINES=( ... ) array. Falls back to the current set if the file can't be read."""
    default = ["v5", "v5_classic", "v5_noml", "v5_apr", "v7_regime"]
    try:
        txt = _LAUNCH_SH.read_text()
        m = _re_roster.search(r"^ENGINES=\((.*?)^\)", txt, _re_roster.S | _re_roster.M)
        if not m:
            return default
        out = []
        for line in m.group(1).splitlines():
            s = line.strip()
            if not s or s.startswith("#"):
                continue
            mm = _re_roster.match(r'"([^|"]+)\|', s)
            if mm:
                out.append(mm.group(1))
        return out or default
    except Exception:
        return default


def _roster_colors(engines):
    return {e: ENGINE_COLORS.get(e, _FALLBACK_PALETTE[i % len(_FALLBACK_PALETTE)])
            for i, e in enumerate(engines)}


@app.route("/api/live-trades")
def api_live_trades():
    """Full per-trade detail for the LIVE engines (v4, v5, v5_classic, v7_regime).
    Returns OPEN + CLOSED trades with entry/exit time, prices, realized P&L,
    exit reason, pool, plus per-engine regime + summary. Powers the redesigned
    /live (left list + right detail panel + centre scan). Read-only.
    Added 2026-06-06 (3-engine redesign — replaces 7-engine positions-live).
    2026-06-09: added v7_regime (4th main-stack engine, regime-gated long/short)."""
    from datetime import date
    from pathlib import Path

    TODAY = request.args.get("date") or date.today().isoformat()
    BASE = Path(os.path.dirname(__file__)).parent / "docs" / "paper-trades"
    ENGINES = _active_engines()
    out = {}

    def _trade(symbol, direction, qty, ep, et, xp, xt, pnl, pnlpct, status, reason, pool):
        return {
            "symbol": symbol or "?", "direction": (direction or "LONG"),
            "qty": qty or 0, "entry_price": ep or 0, "entry_time": et or "—",
            "exit_price": xp, "exit_time": xt or "—", "pnl": pnl,
            "pnl_pct": pnlpct, "status": status, "reason": reason or "—", "pool": pool or "—",
        }

    for eng in ENGINES:
        f = BASE / eng / f"{TODAY}.json"
        trades, regime = [], "—"
        realized = 0.0
        wins = closed = openn = 0
        if f.exists():
            try:
                d = json.load(open(f))
            except (json.JSONDecodeError, IOError):
                d = {}
            if eng == "v4":
                regime = "BEAR" if d.get("bear_mode") else ("VIX-HIGH" if d.get("vix_high_mode") else "NEUTRAL")
                realized = d.get("realized_pnl", 0) or 0
                for p in (d.get("positions") or []):
                    st = "open" if p.get("status") == "open" else "closed"
                    if st == "open":
                        openn += 1
                    else:
                        closed += 1
                        if (p.get("pnl") or 0) > 0:
                            wins += 1
                    trades.append(_trade(
                        p.get("symbol"), p.get("v4_direction") or p.get("direction"),
                        p.get("qty"), p.get("entry_price"), p.get("entry_time"),
                        p.get("exit_price"), p.get("exit_time"), p.get("pnl"),
                        p.get("pnl_pct"), st, p.get("exit_reason"), "INTRADAY"))
            else:  # v5 / v5_classic — multi-pool
                regime = d.get("regime", "—")
                s = d.get("summary", {})
                realized = s.get("total_pnl", 0) or 0
                closed = s.get("trades", 0)
                wins = s.get("wins", 0)
                for pool, pdata in (d.get("pools") or {}).items():
                    for p in pdata.get("closed", []):
                        trades.append(_trade(
                            p.get("symbol"), p.get("position_type") or p.get("direction"),
                            p.get("qty"), p.get("entry_price"), p.get("entry_time"),
                            p.get("exit_price"), p.get("exit_time"), p.get("pnl"),
                            p.get("pnl_pct"), "closed", p.get("reason"), pool))
                    for p in pdata.get("positions", []):
                        openn += 1
                        trades.append(_trade(
                            p.get("symbol"), p.get("position_type") or p.get("direction"),
                            p.get("qty"), p.get("entry_price"), p.get("entry_time"),
                            None, None, p.get("unrealized_pnl"), None, "open",
                            p.get("reason"), pool))
        # newest-first by exit_time then entry_time
        trades.sort(key=lambda t: (t["exit_time"] or "", t["entry_time"] or ""), reverse=True)
        out[eng] = {
            "regime": regime,
            "summary": {
                "realized_pnl": round(realized, 0), "closed": closed, "open": openn,
                "win_rate": round(100 * wins / closed) if closed else None,
            },
            "trades": trades,
        }

    fleet_realized = sum(e["summary"]["realized_pnl"] for e in out.values())
    fleet_open = sum(e["summary"]["open"] for e in out.values())
    fleet_closed = sum(e["summary"]["closed"] for e in out.values())
    fleet_wins = sum(round((e["summary"]["win_rate"] or 0) / 100 * e["summary"]["closed"]) for e in out.values())
    return jsonify({
        "date": TODAY,
        "engines": out,
        "roster": ENGINES,                    # dynamic order from launch-market.sh
        "colors": _roster_colors(ENGINES),    # so the frontend never hardcodes engines
        "fleet": {
            "realized_pnl": round(fleet_realized, 0), "open": fleet_open, "closed": fleet_closed,
            "win_rate": round(100 * fleet_wins / fleet_closed) if fleet_closed else None,
        },
    })


@app.route("/api/live-dates")
def api_live_dates():
    """Last N trading sessions that have data, for the /live day-wise history strip.
    Returns dates (desc) with fleet realized P&L + trade count per day. Read-only.
    Added 2026-06-06."""
    import re
    from pathlib import Path
    BASE = Path(os.path.dirname(__file__)).parent / "docs" / "paper-trades"
    ENGINES = _active_engines()
    try:
        limit = int(request.args.get("limit", 7))
    except ValueError:
        limit = 7
    # collect distinct dates that have a date-stamped file in any live engine
    dates = set()
    for eng in ENGINES:
        d = BASE / eng
        if not d.is_dir():
            continue
        for f in d.glob("2*.json"):
            m = re.match(r"(\d{4}-\d{2}-\d{2})\.json$", f.name)
            if m:
                dates.add(m.group(1))
    out = []
    for day in sorted(dates, reverse=True)[:limit]:
        pnl = 0.0
        trades = 0
        for eng in ENGINES:
            f = BASE / eng / f"{day}.json"
            if not f.exists():
                continue
            try:
                j = json.load(open(f))
            except (json.JSONDecodeError, IOError):
                continue
            if eng == "v4":
                pnl += j.get("realized_pnl", 0) or 0
                trades += len([p for p in (j.get("positions") or []) if p.get("status") != "open"])
            else:
                s = j.get("summary", {})
                pnl += s.get("total_pnl", 0) or 0
                trades += s.get("trades", 0)
        out.append({"date": day, "pnl": round(pnl, 0), "trades": trades})
    return jsonify({"sessions": out})


@app.route("/api/lab")
def api_lab():
    """A/B experiments for the Lab page — challenger vs live. Reads the live engine
    dirs + the two sibling A/B dirs. Supports ?date=. Read-only. (re-added 2026-06-06)"""
    from datetime import date
    from pathlib import Path
    TODAY = request.args.get("date") or date.today().isoformat()
    HOME = Path.home() / "Documents" / "tinker" / "projects"

    def _v4(base):
        f = base / "docs" / "paper-trades" / "v4" / (TODAY + ".json")
        if not f.exists():
            return None
        try:
            d = json.load(open(f))
        except (json.JSONDecodeError, IOError):
            return None
        pos = d.get("positions", [])
        cl = [p for p in pos if p.get("status") != "open"]
        w = sum(1 for p in cl if (p.get("pnl") or 0) > 0)
        return {"realized_pnl": round(d.get("realized_pnl", 0) or 0), "closed": len(cl),
                "open": len(pos) - len(cl), "win_rate": round(100 * w / len(cl)) if cl else None,
                "longs": sum(1 for p in pos if p.get("v4_direction") == "BUY"),
                "shorts": sum(1 for p in pos if p.get("v4_direction") == "SELL"),
                "started": d.get("started_at", "—"), "session_date": TODAY,
                "regime": "BEAR" if d.get("bear_mode") else ("VIX-HIGH" if d.get("vix_high_mode") else "NEUTRAL")}

    def _v5(base):
        f = base / "docs" / "paper-trades" / "v5" / (TODAY + ".json")
        if not f.exists():
            return None
        try:
            d = json.load(open(f))
        except (json.JSONDecodeError, IOError):
            return None
        s = d.get("summary", {})
        openn = sum(len(p.get("positions", [])) for p in d.get("pools", {}).values())
        return {"realized_pnl": round(s.get("total_pnl", 0) or 0), "closed": s.get("trades", 0),
                "open": openn, "win_rate": round(100 * s.get("wins", 0) / s.get("trades", 1)) if s.get("trades") else None,
                "longs": s.get("longs", 0), "shorts": s.get("shorts", 0),
                "started": d.get("started_at", "—"), "session_date": TODAY, "regime": d.get("regime", "—")}

    LIVE = HOME / "tradepilot"
    OLD = HOME / "tradepilot-oldengine-ab"
    LO = HOME / "tradepilot-v5-longonly-ab"

    # BUGFIX (2026-07-21 forensic audit): cards previously showed challenger/baseline
    # stats with no indication of which day's file they came from — historical day
    # files (e.g. browsed via ?date=, or a stale carry-forward file under today's
    # name) rendered indistinguishable from a genuine live "today" result. Every
    # card now carries session_date (the filename actually read) + a stale flag
    # so the frontend can badge anything that isn't literally today.
    def card(label, stat, extra=None):
        if stat is None:
            return {"label": label, "live": False}
        c = {"label": label, "live": True}
        c.update(stat)
        if extra:
            c.update(extra)
        sd = c.get("session_date")
        c["stale"] = bool(sd and sd != date.today().isoformat())
        return c

    def delta(ch, bl):
        if ch and ch.get("live") and bl and bl.get("live"):
            return round(ch["realized_pnl"] - bl["realized_pnl"])
        return None

    v4_live, v4_old = _v4(LIVE), _v4(OLD)
    v5_live, v5_lo = _v5(LIVE), _v5(LO)
    ch4 = card("A/B · OLD 5-tree", v4_old)
    bl4 = card("LIVE · v5", v5_live)   # re-baselined 2026-07-01: the v4 1,735-tree baseline is retired; compare the simple 5-tree vs live v5
    ch5 = card("A/B · LONG-ONLY", v5_lo, {"gate_ok": (v5_lo or {}).get("shorts", 0) == 0})
    bl5 = card("LIVE · with shorts", v5_live)
    experiments = [
        {"id": "v4", "title": "OLD 5-tree (simple model) vs live v5",
         "hypothesis": "the simple 5-tree model beats the overfit 1,735-tree (note: leveraged/gross — read risk-adjusted)",
         "status": "TESTING", "challenger": ch4, "baseline": bl4, "delta": delta(ch4, bl4)},
        {"id": "v5", "title": "v5 short arm — long-only challenger vs live with-shorts",
         "hypothesis": "removing the edgeless short arm improves v5",
         "status": "TESTING", "challenger": ch5, "baseline": bl5, "delta": delta(ch5, bl5)},
    ]

    # --- our in-house shadow A/B (same project): v5_noml & v5_apr vs live v5 ---
    def _eng(eng):
        f = LIVE / "docs" / "paper-trades" / eng / (TODAY + ".json")
        if not f.exists():
            return None
        try:
            d = json.load(open(f))
        except (json.JSONDecodeError, IOError):
            return None
        s = d.get("summary", {})
        openn = sum(len(p.get("positions", [])) for p in d.get("pools", {}).values())
        return {"realized_pnl": round(s.get("total_pnl", 0) or 0), "closed": s.get("trades", 0),
                "open": openn, "win_rate": round(100 * s.get("wins", 0) / s.get("trades", 1)) if s.get("trades") else None,
                "longs": s.get("longs", 0), "shorts": s.get("shorts", 0),
                "started": d.get("started_at", "—"), "session_date": TODAY, "regime": d.get("regime", "—")}

    SHADOW_START = "2026-06-15"   # shadows began this day — only compare from here (apples-to-apples)
    def _cum(eng):  # running A/B total = gross P&L summed over the shadow period only
        import glob, re, os
        t = 0
        for f in glob.glob(str(LIVE / "docs" / "paper-trades" / eng / "2026-*.json")):
            b = os.path.basename(f)
            if not re.match(r"\d{4}-\d{2}-\d{2}\.json$", b) or b[:10] < SHADOW_START:
                continue
            try:
                t += json.load(open(f)).get("summary", {}).get("total_pnl", 0) or 0
            except Exception:
                pass
        return round(t)

    bl_v5 = card("LIVE · v5", _eng("v5"))
    cum_v5 = _cum("v5")
    experiments += [
        {"id": "v5_flip", "title": "v5_flip — fast intraday regime-flip vs live v5",
         "hypothesis": "activating the BEAR 8/12 tilt on confirmed hard-down (< -0.6%) cuts red-day losses without false-triggering on green days",
         "status": "TESTING", "challenger": card("A/B · FLIP", _eng("v5_flip")),
         "baseline": bl_v5, "delta": delta(card("x", _eng("v5_flip")), bl_v5),
         "cum_delta": _cum("v5_flip") - cum_v5},
        {"id": "v5_cut", "title": "v5_cut — faster wrong-way cut + tighter short + 450-name universe",
         "hypothesis": "cut losers fast + don't short strength + scan wider = better margin",
         "status": "TESTING", "challenger": card("A/B · CUT", _eng("v5_cut")),
         "baseline": bl_v5, "delta": delta(card("x", _eng("v5_cut")), bl_v5),
         "cum_delta": _cum("v5_cut") - cum_v5},
    ]
    return jsonify({"date": TODAY, "experiments": experiments})


@app.route("/api/recent-scans")
def api_recent_scans():
    """Recent scan + trade events across all 7 engines.
    Tails the engine log files and extracts interesting lines (scans, deploys,
    exits, watchlist additions). Returns last 60 events sorted newest first.
    Polled by /live every 5s for the event stream.
    Added 2026-05-12 (Option C in /live refinement)."""
    import re
    from pathlib import Path

    ENGINES = ['v5', 'v5_classic', 'v5_long', 'v5_cut', 'v5_flip']   # current roster (2026-07-01; retired v4/v5_6/v5_7/v5_8/v6)
    LOG_DIR = Path(os.path.dirname(__file__)).parent / "logs"

    # Patterns to extract — each tuple: (regex, event_type)
    # Handles BOTH log formats:
    #   v4: ">> LOSS: SYMBOL xQTY @ Rs PRICE (REASON) P&L: Rs -X"  (colon, no direction)
    #   v5: ">> WIN SHORT SYMBOL xQTY @PRICE (REASON) P&L: Rs +X"  (no colon, with direction)
    # Direction (SHORT/LONG) is optional via non-capturing group.
    PATTERNS = [
        (re.compile(r'\[(\d{2}:\d{2}:\d{2})\].*scorer:\s*(\d+)\s*scored\s*\|\s*BUY=(\d+)\s*HOLD=(\d+)\s*AVOID=(\d+)'), 'scan'),
        (re.compile(r'\[(\d{2}:\d{2}:\d{2})\]\s*DEPLOYING\s*Rs\s*([\d,]+)\s*into\s*(\d+)\s*v?\d*\s*BUY\s*signals'), 'deploy'),
        (re.compile(r'\[(\d{2}:\d{2}:\d{2})\]\s*>>\s*WIN:?\s+(?:(SHORT|LONG)\s+)?(\w+)\s+x(\d+)\s*@\s*(?:Rs\s*)?([\d.,]+)\s*\(([^)]+)\)\s*P&L:\s*Rs\s*([+-]?[\d,]+)'), 'win'),
        (re.compile(r'\[(\d{2}:\d{2}:\d{2})\]\s*>>\s*LOSS:?\s+(?:(SHORT|LONG)\s+)?(\w+)\s+x(\d+)\s*@\s*(?:Rs\s*)?([\d.,]+)\s*\(([^)]+)\)\s*P&L:\s*Rs\s*([+-]?[\d,]+)'), 'loss'),
        (re.compile(r'\[(\d{2}:\d{2}:\d{2})\]\s+(\w+):\s+added\s+to\s+watchlist'), 'watchlist'),
    ]

    events = []
    # Tail last ~200 lines from each engine log (fast — IO bound)
    for engine in ENGINES:
        log_file = LOG_DIR / f"{engine}-paper-trade.log"
        if not log_file.exists():
            continue
        try:
            # Read last 200 lines efficiently
            with open(log_file, 'rb') as f:
                f.seek(0, 2)  # seek to end
                size = f.tell()
                # Read last 30KB (~200 lines avg)
                read_from = max(0, size - 30_000)
                f.seek(read_from)
                lines = f.read().decode('utf-8', errors='ignore').split('\n')
        except (IOError, OSError):
            continue

        # Parse last 100 lines (most recent first if we reverse)
        for line in lines[-100:]:
            for pattern, evt_type in PATTERNS:
                m = pattern.search(line)
                if not m:
                    continue
                g = m.groups()
                event = {'time': g[0], 'engine': engine, 'type': evt_type}
                if evt_type == 'scan':
                    event['msg'] = f"scan: {g[1]} scored · BUY={g[2]} HOLD={g[3]} AVOID={g[4]}"
                    event['detail'] = {'scored': int(g[1]), 'buy': int(g[2]), 'hold': int(g[3]), 'avoid': int(g[4])}
                elif evt_type == 'deploy':
                    event['msg'] = f"DEPLOY Rs {g[1]} into {g[2]} BUYs"
                elif evt_type in ('win', 'loss'):
                    direction, symbol, qty, price, reason, pnl = g[1], g[2], g[3], g[4], g[5], g[6]
                    event['msg'] = f"{evt_type.upper()} {direction} {symbol} @{price} ({reason}) Rs {pnl}"
                    event['detail'] = {'symbol': symbol, 'direction': direction, 'reason': reason, 'pnl_rs': pnl}
                elif evt_type == 'watchlist':
                    event['msg'] = f"{g[1]} → watchlist"
                events.append(event)
                break  # one pattern per line

    # Sort newest first by time (lexicographic works for HH:MM:SS)
    events.sort(key=lambda e: e['time'], reverse=True)

    return jsonify({
        'events': events[:60],
        'count': len(events[:60]),
        'engines_scanned': ENGINES,
    })


@app.route("/api/preloaded-scores")
def api_preloaded():
    """Serve pre-computed scores (instant, no API delay)."""
    scores_path = os.path.join(os.path.dirname(__file__), "static", "preloaded-scores.json")
    if os.path.exists(scores_path):
        with open(scores_path) as f:
            return f.read(), 200, {'Content-Type': 'application/json'}
    return jsonify([])

@app.route("/api/rust-status")
def api_rust_status():
    """Proxy to Rust execution engine status."""
    import requests as _req
    rust_url = os.environ.get("RUST_ENGINE_URL", "http://localhost:8080")
    result = {"engine": "offline", "risk": None, "positions": None}
    try:
        health = _req.get(f"{rust_url}/health", timeout=2)
        if health.status_code == 200:
            result["engine"] = "online"
            risk = _req.get(f"{rust_url}/api/risk", timeout=2)
            if risk.status_code == 200:
                result["risk"] = risk.json()
            pos = _req.get(f"{rust_url}/api/positions", timeout=2)
            if pos.status_code == 200:
                result["positions"] = pos.json()
    except Exception:
        pass
    return jsonify(result)


@app.route("/pitch")
def pitch():
    """Serve the interactive pitch deck."""
    pitch_path = os.path.join(os.path.dirname(__file__), "..", "docs", "pitch", "pitch-deck.html")
    with open(pitch_path, "r") as f:
        return f.read()


_score_cache = {"data": None, "time": 0}
_data_ready = {"status": False, "loading": False}

def ensure_data():
    """Download stock data and train model if not present (runs once on Render)."""
    if _data_ready["status"] or _data_ready["loading"]:
        return _data_ready["status"]

    from data_engine import load_all_stock_data, download_stock_data, NIFTY_50
    data = load_all_stock_data()
    if len(data) >= 10:
        _data_ready["status"] = True
        return True

    # Need to download data (first run on Render)
    _data_ready["loading"] = True
    try:
        print("[INIT] Downloading NIFTY 50 stock data (first run)...")
        download_stock_data(NIFTY_50[:20], period="1y")  # Start with top 20 for speed
        print("[INIT] Training AI model...")
        train_model(load_all_stock_data())
        if HAS_V2:
            try:
                train_ensemble(load_all_stock_data())
            except Exception:
                pass
        _data_ready["status"] = True
        print("[INIT] Ready!")
    except Exception as e:
        print(f"[INIT] Error: {e}")
    finally:
        _data_ready["loading"] = False
    return _data_ready["status"]


def get_live_scores_fallback(symbols):
    """Fallback: get basic scores from live yfinance data when no trained model exists."""
    import yfinance as yf
    stocks = []
    for sym in symbols[:30]:  # Limit to 30 for speed
        try:
            name = sym.replace(".NS", "").replace(".BO", "")
            ticker = yf.Ticker(sym)
            hist = ticker.history(period="5d")
            if len(hist) < 2:
                continue
            price = round(float(hist.iloc[-1]["Close"]), 2)
            prev = float(hist.iloc[-2]["Close"])
            change = round((price - prev) / prev * 100, 2)

            # Simple score based on recent momentum
            returns_5d = (price / float(hist.iloc[0]["Close"]) - 1) * 100
            score = round(max(10, min(90, 50 + returns_5d * 5)), 1)
            direction = "BUY" if score >= 55 else "HOLD" if score >= 40 else "AVOID"

            stocks.append({
                "symbol": name, "name": name, "price": price,
                "change": change, "score": score, "direction": direction,
                "rsi": 50, "trend": "Sideways", "volatility": "Medium",
                "macd": "Neutral", "stopLoss": 3.0, "target": 6.0,
                "riskReward": 2.0,
                "reasons": [{"text": f"{'Positive' if change > 0 else 'Negative'} momentum ({change:+.1f}%)", "type": "positive" if change > 0 else "negative"}],
            })
        except Exception:
            pass
    stocks.sort(key=lambda x: x["score"], reverse=True)
    return stocks


@app.route("/api/scores")
def api_scores():
    """Get AI scores -- uses NIFTY 50 by default for speed, with caching."""
    import time
    category = request.args.get('category', 'nifty50')
    default_engine = "v4" if HAS_V4 else "v2"
    engine = request.args.get('engine', default_engine)

    # Cache for 5 minutes on Render (reduce API calls)
    cache_key = f"{category}_{engine}"
    now = time.time()
    if _score_cache["data"] and (now - _score_cache["time"]) < 300 and _score_cache.get("key") == cache_key:
        return jsonify(_score_cache["data"])

    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        # Try trained model first
        raw_scores = None
        if engine == "v4" and HAS_V4:
            try:
                raw_scores = score_stocks_v4(cat_stocks)
            except Exception:
                pass
        if not raw_scores and engine == "v3" and HAS_V3:
            try:
                raw_scores = score_stocks_v3(cat_stocks)
            except Exception:
                pass
        if not raw_scores and ensure_data():
            try:
                raw_scores = score_stocks_v2(cat_stocks) if HAS_V2 else score_stocks()
            except Exception:
                pass

        # Fallback to live yfinance if no model
        if not raw_scores:
            stocks = get_live_scores_fallback(cat_stocks)
            _score_cache["data"] = stocks
            _score_cache["time"] = now
            _score_cache["key"] = cache_key
            return jsonify(stocks)

        import math
        raw_scores = raw_scores  # Use model scores

        def safe(v, default=0):
            """Sanitize NaN/Inf values for JSON serialization."""
            if v is None:
                return default
            try:
                if math.isnan(v) or math.isinf(v):
                    return default
            except (TypeError, ValueError):
                pass
            return v

        # Transform to frontend format
        stocks = []
        for s in raw_scores:
            price = safe(s.get("price"), 0)
            score = safe(s.get("score"), 0)
            change = safe(s.get("change_pct"), 0)
            rsi = safe(s.get("rsi"), 50)
            vol_raw = s.get("volatility", 20)
            vol = safe(vol_raw, 20) if not isinstance(vol_raw, str) else 20

            # Skip entries with no valid price
            if price == 0:
                continue

            # Sanitize reasons — strip numeric values to prevent reverse engineering
            reasons = []
            for r in s.get("reasons", []):
                raw_text = r.get("text", "")
                # Remove specific numbers from reason text (e.g. "Price +1.43% above VWAP (7059)")
                import re
                sanitized = re.sub(r'\([\d,.]+\)', '', raw_text)  # strip parenthesized numbers
                sanitized = re.sub(r'[\d,.]+%', '%', sanitized)   # strip percentage values
                sanitized = re.sub(r'[\d,.]+\s*Cr', 'Cr', sanitized)  # strip crore values
                reasons.append({
                    "text": sanitized.strip(),
                    "type": r.get("type", r.get("impact", "neutral")),
                })

            entry = {
                "symbol": s.get("name", s.get("symbol", "").replace(".NS", "")),
                "name": s.get("name", s.get("symbol", "")),
                "price": round(price, 2),
                "change": round(change, 2),
                "score": round(score, 1),
                "direction": s.get("direction", "HOLD"),
                "rsi": round(rsi, 1),
                "trend": s.get("trend", "Sideways"),
                "volatility": "High" if vol > 25 else "Low" if vol < 15 else "Medium",
                "macd": s.get("macd_signal", "Neutral"),
                "stopLoss": round(safe(s.get("stop_loss_pct"), 2.0), 1),
                "target": round(safe(s.get("target_pct"), 4.0), 1),
                "riskReward": round(safe(s.get("risk_reward"), 2.0), 1),
                "reasons": reasons,
            }

            # Add v3/v4-specific fields when present
            if engine in ("v3", "v4"):
                entry["market_regime"] = s.get("market_regime", "unknown")
                entry["relative_strength_5d"] = safe(s.get("relative_strength_5d"), 0)
                entry["relative_strength_20d"] = safe(s.get("relative_strength_20d"), 0)
                entry["confidence"] = safe(s.get("confidence"), 0)
                entry["model_version"] = s.get("model_version", engine)

            stocks.append(entry)

        _score_cache["data"] = stocks
        _score_cache["time"] = now
        _score_cache["key"] = cache_key
        return jsonify(stocks)
    except Exception as e:
        traceback.print_exc()
        return jsonify([]), 500


@app.route("/api/model")
def api_model():
    """Get model metadata -- sanitized for public consumption."""
    try:
        default_engine = "v4" if HAS_V4 else "v2"
        engine = request.args.get('engine', default_engine)

        # Return v4 metadata if requested and available
        if engine == "v4" and HAS_V4:
            return jsonify({
                "accuracy": 0,
                "version": "v4",
                "trainingSamples": 0,
                "lastTrained": datetime.now().strftime("%Y-%m-%d"),
                "features": [],
                "backtest": [],
                "model_type": "composite_scorer",
                "description": "Multi-signal composite scorer (technical + momentum + regime)",
                "target_metric": "precision (80% profitable trades)",
            })

        # Return v3 metadata if requested and available
        if engine == "v3" and HAS_V3:
            meta_v3 = get_model_meta_v3()
            if meta_v3:
                trained_at = meta_v3.get("trained_at", "Unknown")
                if "T" in trained_at:
                    trained_at = trained_at.split("T")[0]
                return jsonify({
                    "accuracy": round(meta_v3.get("accuracy", 0) * 100, 1) if meta_v3.get("accuracy", 0) < 1 else meta_v3.get("accuracy", 0),
                    "version": "v3",
                    "trainingSamples": meta_v3.get("train_samples", 0) + meta_v3.get("test_samples", 0),
                    "lastTrained": trained_at,
                    "features": [],  # populated below if available
                    "backtest": [],
                    "market_regime": meta_v3.get("market_regime", "unknown"),
                    "precision": meta_v3.get("precision", 0),
                    "target_metric": "precision (80% profitable trades)",
                })

        # SECURITY-006: Strip all IP-sensitive data from public response
        # No feature importances, no backtest metrics, no ensemble weights
        return jsonify({
            "accuracy": 0,
            "version": "v2",
            "trainingSamples": 0,
            "lastTrained": datetime.now().strftime("%Y-%m-%d"),
            "features": [],
            "backtest": [],
            "model_type": "ensemble",
            "description": "ML ensemble scorer",
            "status": "active",
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"accuracy": 0, "trainingSamples": 0, "lastTrained": "Error"})


@app.route("/api/compare")
def api_compare():
    """Return v2 and v3 scores side by side for comparison."""
    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        category = request.args.get('category', 'nifty50')
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        v2_scores = []
        v3_scores = []

        # Get v2 scores
        if HAS_V2 and ensure_data():
            try:
                v2_scores = score_stocks_v2(cat_stocks) or []
            except Exception:
                pass

        # Get v3 scores
        if HAS_V3:
            try:
                v3_scores = score_stocks_v3(cat_stocks) or []
            except Exception:
                pass

        # Index by symbol for side-by-side
        v2_map = {s.get("symbol", s.get("name", "")): s for s in v2_scores}
        v3_map = {s.get("symbol", s.get("name", "")): s for s in v3_scores}
        all_symbols = sorted(set(list(v2_map.keys()) + list(v3_map.keys())))

        comparison = []
        for sym in all_symbols:
            v2 = v2_map.get(sym, {})
            v3 = v3_map.get(sym, {})
            comparison.append({
                "symbol": sym.replace(".NS", ""),
                "v2_score": round(v2.get("score", 0), 1),
                "v2_direction": v2.get("direction", "N/A"),
                "v3_score": round(v3.get("score", 0), 1),
                "v3_direction": v3.get("direction", "N/A"),
                "v3_confidence": v3.get("confidence", 0),
                "v3_market_regime": v3.get("market_regime", "unknown"),
                "score_diff": round(v3.get("score", 0) - v2.get("score", 0), 1),
            })

        comparison.sort(key=lambda x: abs(x["score_diff"]), reverse=True)

        return jsonify({
            "comparison": comparison,
            "v2_available": HAS_V2,
            "v3_available": HAS_V3,
            "total_stocks": len(comparison),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"comparison": [], "error": str(e)}), 500


@app.route("/api/compare-v4")
def api_compare_v4():
    """Return v3 and v4 scores side by side for comparison."""
    try:
        from data_engine import STOCK_CATEGORIES, NIFTY_50
        category = request.args.get('category', 'nifty50')
        cat_stocks = STOCK_CATEGORIES.get(category, {}).get('stocks', NIFTY_50)

        v3_scores = []
        v4_scores = []

        if HAS_V3:
            try:
                v3_scores = score_stocks_v3(cat_stocks) or []
            except Exception:
                pass

        if HAS_V4:
            try:
                v4_scores = score_stocks_v4(cat_stocks) or []
            except Exception:
                pass

        v3_map = {s.get("symbol", s.get("name", "")): s for s in v3_scores}
        v4_map = {s.get("symbol", s.get("name", "")): s for s in v4_scores}
        all_symbols = sorted(set(list(v3_map.keys()) + list(v4_map.keys())))

        comparison = []
        for sym in all_symbols:
            v3 = v3_map.get(sym, {})
            v4 = v4_map.get(sym, {})
            comparison.append({
                "symbol": sym.replace(".NS", ""),
                "v3_score": round(v3.get("score", 0), 1),
                "v3_direction": v3.get("direction", "N/A"),
                "v3_confidence": v3.get("confidence", 0),
                "v4_score": round(v4.get("score", 0), 1),
                "v4_direction": v4.get("direction", "N/A"),
                "v4_confidence": v4.get("confidence", 0),
                "v4_market_regime": v4.get("market_regime", "unknown"),
                "score_diff": round(v4.get("score", 0) - v3.get("score", 0), 1),
            })

        comparison.sort(key=lambda x: abs(x["score_diff"]), reverse=True)

        return jsonify({
            "comparison": comparison,
            "v3_available": HAS_V3,
            "v4_available": HAS_V4,
            "total_stocks": len(comparison),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"comparison": [], "error": str(e)}), 500


@app.route("/api/engine-status")
def api_engine_status():
    """Per-engine live state for the dashboard. Reads each engine's state JSON file
    directly — same source of truth used by the engines themselves and the
    eod-comparison report.

    Returns combined view: P&L, trades, WR, open positions, watchlist, kill switch
    tier — for ALL 7 engines (v4 + v5 family) in one call.

    Used by:
      - Dashboard "Live Status" panel (replaces bash status command)
      - Dashboard "Engine P&L Comparison" panel (v4 vs v5 family)
      - Dashboard "Watchlist & Revival Gate" panel
      - Dashboard "Kill Switch Tier" panel
    """
    try:
        from datetime import date as _date
        target = request.args.get('date') or _date.today().isoformat()
        project_root = Path(__file__).resolve().parent.parent
        engines = ['v4', 'v5', 'v5_classic', 'v5_6', 'v5_7', 'v5_8', 'v6']

        result = []
        fleet_pnl = 0.0
        fleet_trades = 0
        fleet_open = 0

        for eng in engines:
            f = project_root / 'docs' / 'paper-trades' / eng / f'{target}.json'
            if not f.exists():
                result.append({
                    'engine': eng, 'status': 'no_data',
                    'pnl': 0, 'trades': 0, 'wins': 0, 'losses': 0,
                    'wr': 0, 'open': 0, 'watchlist': [], 'loss_counts': {},
                    'kill_switch_tier': 0, 'capital': 0, 'cash': 0,
                })
                continue
            try:
                d = json.loads(f.read_text())
            except Exception:
                continue

            # v5 family — pools shape
            if 'pools' in d:
                s = d.get('summary', {}) or {}
                pnl = float(s.get('total_pnl', 0) or 0)
                trades = int(s.get('trades', 0) or 0)
                wins = int(s.get('wins', 0) or 0)
                losses = int(s.get('losses', 0) or 0)
                open_count = sum(len(p.get('positions', []) or []) for p in d.get('pools', {}).values())
                capital = float(d.get('total_capital', 0) or 0)
                # v5 family doesn't have watchlist in current code; leave empty
                watchlist = []
                loss_counts = {}
                kill_switch_tier = 0
            else:
                # v4 flat shape
                ct = d.get('closed_trades', []) or []
                pnl = float(d.get('realized_pnl', 0) or 0)
                trades = len(ct)
                wins = sum(1 for t in ct if (t.get('pnl') or 0) > 0)
                losses = trades - wins
                open_count = sum(1 for p in (d.get('positions') or []) if p.get('status') == 'open')
                capital = float(d.get('daily_pool', 0) or 0)
                watchlist_raw = d.get('watchlist', {}) or {}
                # Normalize watchlist for frontend
                watchlist = [
                    {
                        'symbol': sym,
                        'exit_time': info.get('exit_time'),
                        'exit_price': info.get('exit_price'),
                        'post_drop_low': info.get('post_drop_low'),
                        'exit_reason': info.get('exit_reason'),
                        'loss_pct': info.get('loss_pct'),
                    }
                    for sym, info in watchlist_raw.items()
                ]
                loss_counts = d.get('stock_loss_count', {}) or {}
                kill_switch_tier = int(d.get('kill_switch_tier', 0) or 0)

            wr = round(100.0 * wins / trades, 1) if trades > 0 else 0.0
            cash = float(d.get('cash', 0) or 0)
            row = {
                'engine': eng,
                'status': 'ok',
                'pnl': round(pnl, 2),
                'trades': trades,
                'wins': wins,
                'losses': losses,
                'wr': wr,
                'open': open_count,
                'capital': capital,
                'cash': round(cash, 2),
                'watchlist': watchlist,
                'loss_counts': loss_counts,
                'kill_switch_tier': kill_switch_tier,
            }
            result.append(row)
            fleet_pnl += pnl
            fleet_trades += trades
            fleet_open += open_count

        # Rank engines by P&L for the comparison panel
        result_sorted = sorted(result, key=lambda r: r.get('pnl', 0), reverse=True)
        for i, r in enumerate(result_sorted, 1):
            r['rank'] = i

        # Derive v4 vs v5_family summary
        v4_pnl = next((r['pnl'] for r in result if r['engine'] == 'v4'), 0)
        v5_family_pnl = sum(r['pnl'] for r in result if r['engine'] != 'v4')

        return jsonify({
            'date': target,
            'engines': result_sorted,
            'fleet': {
                'total_pnl': round(fleet_pnl, 2),
                'total_trades': fleet_trades,
                'total_open': fleet_open,
                'v4_pnl': round(v4_pnl, 2),
                'v5_family_pnl': round(v5_family_pnl, 2),
            },
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({'engines': [], 'error': str(e)}), 500


@app.route("/api/system-health")
def api_system_health():
    """Aggregate system-health events for the dashboard notification surface.

    Sources scanned (each cheap — last N lines / single state-file read):
      - engine logs (logs/v4-DATE.log etc.) for NaN rate, empty sizer, staleness
      - state files (docs/paper-trades/v4/DATE.json etc.) for kill switch tier,
        watchlist size, large losses, recent risk events
      - process list (subprocess pgrep) for engine/Rust liveness

    Severity tiers: info / warn / error / critical.
    Overall status = highest severity present.

    Used by:
      - /dashboard top-of-page status banner
      - /dashboard "System Health" panel (event list)
    """
    try:
        import subprocess as _sp
        import time as _time
        from datetime import datetime as _dt, time as _time_t, timedelta as _td

        project_root = Path(__file__).resolve().parent.parent
        today = _dt.now().strftime("%Y-%m-%d")
        engines = ['v4', 'v5', 'v5_classic', 'v5_6', 'v5_7', 'v5_8', 'v6']

        events = []
        # Severity rank for sorting / overall calc
        sev_rank = {"info": 0, "warn": 1, "error": 2, "critical": 3}

        # Are we in market hours? (09:15-15:30 IST)
        now = _dt.now()
        market_open = now.replace(hour=9, minute=15, second=0, microsecond=0)
        market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
        in_market = market_open <= now <= market_close

        # --- 1. Process liveness (only flag during market hours) ---
        try:
            ps = _sp.run(['pgrep', '-fl', 'scripts/v.*-paper-trade.py|tradepilot-engine'],
                         capture_output=True, text=True, timeout=3)
            running = ps.stdout
        except Exception:
            running = ""
        if in_market:
            for eng in engines:
                if f"scripts/{eng}-paper-trade.py" not in running:
                    events.append({
                        "ts": now.strftime("%H:%M:%S"),
                        "severity": "critical",
                        "code": "ENGINE_DOWN",
                        "source": eng,
                        "message": f"{eng} engine process not running during market hours",
                    })
            if "tradepilot-engine" not in running:
                events.append({
                    "ts": now.strftime("%H:%M:%S"),
                    "severity": "critical",
                    "code": "RUST_DOWN",
                    "source": "rust",
                    "message": "Rust execution engine not running",
                })

        # --- 2. Per-engine state file scan ---
        for eng in engines:
            sf = project_root / 'docs' / 'paper-trades' / eng / f'{today}.json'
            if not sf.exists():
                continue
            try:
                d = json.loads(sf.read_text())
            except Exception:
                continue

            # Kill switch tier (v4 only — v5 family doesn't track this currently)
            tier = int(d.get('kill_switch_tier', 0) or 0)
            if tier > 0:
                tier_severity = ['info', 'warn', 'error', 'critical'][min(tier, 3)]
                tier_label = ['CLEAR', 'WARN', 'SOFT_HOLD', 'HARD_KILL'][tier]
                events.append({
                    "ts": now.strftime("%H:%M:%S"),
                    "severity": tier_severity,
                    "code": "KILL_SWITCH_ACTIVE",
                    "source": eng,
                    "message": f"{eng} kill switch at tier {tier} ({tier_label})",
                })

            # Watchlist size
            wl = d.get('watchlist', {}) or {}
            if len(wl) > 5:
                events.append({
                    "ts": now.strftime("%H:%M:%S"),
                    "severity": "info",
                    "code": "WATCHLIST_LARGE",
                    "source": eng,
                    "message": f"{eng} watchlist has {len(wl)} symbols ({', '.join(sorted(wl.keys())[:5])}{'...' if len(wl) > 5 else ''})",
                })

            # Large single-trade losses (> Rs 10K)
            closed = d.get('closed_trades', []) or []
            for t in closed[-30:]:  # only recent 30 trades
                if (t.get('pnl') or 0) <= -10000:
                    events.append({
                        "ts": t.get('exit_time', '—'),
                        "severity": "warn",
                        "code": "LARGE_LOSS",
                        "source": eng,
                        "message": f"{eng} {t.get('symbol', '?')} closed at Rs {t['pnl']:+,.0f} ({t.get('reason', '?')})",
                    })

        # --- 3. Engine log scans (NaN rate, empty sizer, staleness) ---
        # Only scan v4 + v5 (cheap); pattern same across family
        for eng in ['v4', 'v5']:
            lf = project_root / 'logs' / f'{eng}-{today}.log'
            if not lf.exists():
                continue
            # Last 200 lines
            try:
                ps = _sp.run(['tail', '-n', '200', str(lf)],
                             capture_output=True, text=True, timeout=3)
                tail = ps.stdout.splitlines()
            except Exception:
                continue
            # NaN rate from latest "NaN-priced (downgraded to HOLD): N" line
            for line in reversed(tail):
                if "NaN-priced (downgraded to HOLD):" in line:
                    try:
                        n = int(line.split("NaN-priced (downgraded to HOLD):")[1].split("|")[0].strip())
                        # Look for total scored (e.g. "200 scored")
                        scored = 200  # default
                        for prev in reversed(tail):
                            if "scored," in prev and "Scoring complete" in prev:
                                try:
                                    scored = int(prev.split("Scoring complete:")[1].split("scored")[0].strip())
                                except Exception:
                                    pass
                                break
                        rate = (n / scored * 100) if scored else 0
                        if rate >= 50:
                            sev = "error"
                        elif rate >= 20:
                            sev = "warn"
                        elif rate > 0:
                            sev = "info"
                        else:
                            sev = None
                        if sev:
                            events.append({
                                "ts": line[1:9] if line.startswith("[") else now.strftime("%H:%M:%S"),
                                "severity": sev,
                                "code": "DATA_NAN",
                                "source": eng,
                                "message": f"{eng} yfinance NaN rate {rate:.0f}% ({n} of {scored}). Strategy unaffected; data quality flag.",
                            })
                    except Exception:
                        pass
                    break

            # Empty sizer returns in last 30 minutes (during market hours)
            if in_market:
                cutoff = now - _td(minutes=30)
                cutoff_str = cutoff.strftime("%H:%M")
                empty_count = 0
                for line in tail:
                    if "Position sizer returned no positions" in line and line.startswith("["):
                        ts = line[1:9]
                        if ts >= cutoff_str:
                            empty_count += 1
                if empty_count >= 3:
                    events.append({
                        "ts": now.strftime("%H:%M:%S"),
                        "severity": "warn",
                        "code": "SIZER_EMPTY",
                        "source": eng,
                        "message": f"{eng} sizer returned 0 positions {empty_count}× in last 30 min (idle capital risk)",
                    })

            # Staleness: last log line older than 35 min
            if in_market and tail:
                last_line = tail[-1]
                if last_line.startswith("["):
                    last_ts_str = last_line[1:9]
                    try:
                        h, m, s = last_ts_str.split(':')
                        last_ts = now.replace(hour=int(h), minute=int(m), second=int(s),
                                              microsecond=0)
                        if (now - last_ts).total_seconds() > 2100:  # 35 min
                            events.append({
                                "ts": now.strftime("%H:%M:%S"),
                                "severity": "error",
                                "code": "STALE_SCAN",
                                "source": eng,
                                "message": f"{eng} last log entry was {int((now-last_ts).total_seconds()//60)} min ago — scan may be hung",
                            })
                    except Exception:
                        pass

            # Watchdog restarts in last 30 min
            wf = project_root / 'logs' / f'watchdog-{today}.log'
            if in_market and wf.exists():
                try:
                    ps = _sp.run(['tail', '-n', '50', str(wf)],
                                 capture_output=True, text=True, timeout=3)
                    cutoff = now - _td(minutes=30)
                    cutoff_str = cutoff.strftime("%H:%M")
                    for line in ps.stdout.splitlines():
                        if "restart" in line.lower() and line.startswith("["):
                            ts = line[1:9]
                            if ts >= cutoff_str:
                                events.append({
                                    "ts": ts,
                                    "severity": "warn",
                                    "code": "WATCHDOG_RESTART",
                                    "source": "watchdog",
                                    "message": line.split("] ", 1)[-1][:120] if "] " in line else line[:120],
                                })
                                break  # only one notification per restart event
                except Exception:
                    pass

        # Deduplicate events by (code, source) — keep highest-severity copy
        seen = {}
        for ev in events:
            key = (ev['code'], ev['source'])
            if key not in seen or sev_rank[ev['severity']] > sev_rank[seen[key]['severity']]:
                seen[key] = ev
        deduped = list(seen.values())

        # Sort by severity (highest first), then time
        deduped.sort(key=lambda e: (-sev_rank[e['severity']], e['ts']), reverse=False)
        deduped.sort(key=lambda e: -sev_rank[e['severity']])

        # Overall status = highest severity, or 'ok' if no events
        if not deduped:
            overall = "ok"
        else:
            top_sev = max(sev_rank[e['severity']] for e in deduped)
            overall = ["info", "warn", "error", "critical"][top_sev]
            if top_sev == 0 and not in_market:
                overall = "ok"  # info-only outside market hours = effectively OK

        return jsonify({
            "overall_status": overall,
            "in_market_hours": in_market,
            "events": deduped[:30],
            "event_count": len(deduped),
            "checked_at": now.strftime("%H:%M:%S"),
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"overall_status": "error", "events": [], "error": str(e)}), 500


@app.route("/api/indices")
def api_indices():
    """Get market indices -- formatted for frontend."""
    try:
        raw = get_market_indices()
        result = {}
        for idx in raw:
            name = idx.get("name", "")
            # Provenance travels WITH the number. Tracking source/stale and then
            # dropping them here would leave the UI unable to distinguish a live
            # Kite quote from an 18-day-old CSV row — which is exactly how the
            # 2026-08-04 wrong-index bug stayed invisible.
            entry = {
                "price": idx.get("value", 0),
                "change": idx.get("change", 0),
                "changePct": idx.get("change_pct", 0),
                "source": idx.get("source", "unknown"),
                "stale": bool(idx.get("stale", False)),
            }
            if idx.get("prev_close_date"):
                entry["prevCloseDate"] = idx["prev_close_date"]
            if "NIFTY" in name.upper():
                result["nifty"] = entry
            elif "SENSEX" in name.upper():
                result["sensex"] = entry

        # CSV FALLBACK — now age-checked.
        #
        # This block is what actually put a wrong number on the dashboard. On
        # 2026-08-04 the live path returned [], this fired, and ^NSEI.csv's last row
        # was 2026-07-17 — so the header read "NIFTY 24,334.30 +1.09%", a level and
        # a move from eighteen days earlier, styled exactly like live data. The real
        # market was DOWN 1.04% at that moment. Nothing in the payload said "stale",
        # so nothing downstream could have known.
        #
        # A cached price is only a price while it is current. Past a trading day plus
        # a weekend it is a historical record, and presenting it as the market is
        # simply false. Old data is now REFUSED and labelled rather than shown.
        MAX_CSV_AGE_DAYS = 4        # Friday close read on Tuesday is the limit

        def _from_csv(sym):
            # pandas is imported HERE: app.py has no module-level `pd`, and the first
            # draft of this guard used pd.Timestamp — which would have raised
            # NameError on precisely the path that exists to catch stale data,
            # restoring the silent failure it was written to remove.
            import pandas as pd

            df = load_stock_data(sym)
            if df is None or len(df) < 2:
                return None, "no local history"
            try:
                if isinstance(df.index, pd.RangeIndex) or df.index.dtype == "int64":
                    last_date = pd.to_datetime(df.iloc[-1].get("Date"))
                else:
                    last_date = pd.to_datetime(df.index[-1])
            except Exception:
                last_date = None
            if last_date is not None:
                age = (pd.Timestamp.now().normalize() - pd.Timestamp(last_date).normalize()).days
                if age > MAX_CSV_AGE_DAYS:
                    return None, f"local CSV is {age}d old (newest {str(last_date)[:10]})"
            last, prev = df.iloc[-1], df.iloc[-2]
            chg = float(last["Close"] - prev["Close"])
            return {"price": round(float(last["Close"]), 2), "change": round(chg, 2),
                    "changePct": round(chg / float(prev["Close"]) * 100, 2),
                    "source": "local-csv", "stale": True}, None

        for key, sym in (("nifty", "^NSEI"), ("sensex", "^BSESN")):
            if key in result and result.get(key, {}).get("price", 0) != 0:
                continue
            try:
                val, why = _from_csv(sym)
                if val:
                    result[key] = val
                    app.logger.warning(f"/api/indices: {key} served from local CSV")
                else:
                    app.logger.error(f"/api/indices: {key} unavailable — {why}")
            except Exception as e:
                app.logger.error(f"/api/indices: {key} CSV read failed: {type(e).__name__}: {e}")

        # Unavailable is reported as unavailable. A zero was previously rendered as a
        # real quote; `available:false` lets the UI say "no data" instead of "0.00".
        for key in ("nifty", "sensex"):
            if key not in result:
                result[key] = {"price": 0, "change": 0, "changePct": 0,
                               "available": False, "source": "none"}

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "nifty": {"price": 0, "change": 0, "changePct": 0},
            "sensex": {"price": 0, "change": 0, "changePct": 0},
        })


def _valid_symbol(symbol):
    """Validate stock symbol — only uppercase letters, numbers, &, -, . (max 20 chars)."""
    import re
    return bool(re.match(r'^[A-Z0-9&\-\.]{1,20}$', symbol))

@app.route("/api/stock/<symbol>")
def api_stock(symbol):
    """Get detailed data for a single stock."""
    if not _valid_symbol(symbol.replace(".NS", "").upper()):
        return jsonify({"error": "Invalid symbol"}), 400
    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        scores = score_stocks_v2([full_symbol]) if HAS_V2 else score_stocks([full_symbol])
        if scores:
            return jsonify(scores[0])
        return jsonify({"error": "Stock not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/stock/<symbol>/history")
def api_stock_history(symbol):
    """Return OHLC history for charting."""
    period = request.args.get("period", "1y")
    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        import yfinance as yf
        ticker = yf.Ticker(full_symbol)

        # Map period to yfinance interval
        interval_map = {
            "1d": ("1d", "5m"),
            "1w": ("5d", "15m"),
            "1m": ("1mo", "1d"),
            "3m": ("3mo", "1d"),
            "6m": ("6mo", "1d"),
            "ytd": ("ytd", "1d"),
            "1y": ("1y", "1d"),
            "2y": ("2y", "1wk"),
        }
        yf_period, yf_interval = interval_map.get(period, ("1y", "1d"))

        hist = ticker.history(period=yf_period, interval=yf_interval)
        hist.index = hist.index.tz_localize(None)

        data = []
        for idx, row in hist.iterrows():
            data.append({
                "date": idx.strftime("%Y-%m-%d %H:%M") if yf_interval in ["5m", "15m"] else idx.strftime("%Y-%m-%d"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        return jsonify({"data": data, "period": period, "interval": yf_interval})
    except Exception as e:
        traceback.print_exc()
        return jsonify({"data": [], "error": str(e)}), 500


@app.route("/api/stock/<symbol>/info")
def api_stock_info(symbol):
    """Return market stats for a stock."""
    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol
    try:
        import yfinance as yf
        ticker = yf.Ticker(full_symbol)
        info = ticker.info
        hist = ticker.history(period="2d")

        current = hist.iloc[-1] if len(hist) > 0 else {}
        prev = hist.iloc[-2] if len(hist) > 1 else {}

        result = {
            "symbol": symbol,
            "name": info.get("shortName", info.get("longName", symbol)),
            "fullName": info.get("longName", symbol),
            "price": round(float(current.get("Close", 0)), 2),
            "change": round(float(current.get("Close", 0)) - float(prev.get("Close", 0)), 2) if len(hist) > 1 else 0,
            "changePct": round((float(current.get("Close", 0)) - float(prev.get("Close", 0))) / float(prev.get("Close", 1)) * 100, 2) if len(hist) > 1 else 0,
            "open": round(float(current.get("Open", 0)), 2),
            "high": round(float(current.get("High", 0)), 2),
            "low": round(float(current.get("Low", 0)), 2),
            "volume": int(current.get("Volume", 0)),
            "avgVolume": info.get("averageVolume", 0),
            "marketCap": info.get("marketCap", 0),
            "pe": info.get("trailingPE", 0),
            "high52w": info.get("fiftyTwoWeekHigh", 0),
            "low52w": info.get("fiftyTwoWeekLow", 0),
            "exchange": "Bombay" if ".NS" in full_symbol or ".BO" in full_symbol else "NSE",
            "currency": "INR",
            "marketState": "closed",  # simplified for prototype
        }

        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/fno/chain/<index>")
def api_fno_chain(index):
    """Get options chain for NIFTY50 or BANKNIFTY."""
    from data_engine import get_options_chain_data
    try:
        data = get_options_chain_data(index.upper())
        if data:
            return jsonify(data)
        return jsonify({"error": "Index not found"}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/index/<index>/intraday")
def api_index_intraday(index):
    """Get intraday data for NIFTY50 or BANKNIFTY."""
    from data_engine import INDEX_SYMBOLS
    import yfinance as yf

    symbol = INDEX_SYMBOLS.get(index.upper())
    if not symbol:
        return jsonify({"error": "Index not found"}), 404

    try:
        ticker = yf.Ticker(symbol)
        hist = ticker.history(period="1d", interval="5m")
        hist.index = hist.index.tz_localize(None)

        data = []
        for idx, row in hist.iterrows():
            data.append({
                "time": idx.strftime("%H:%M"),
                "date": idx.strftime("%Y-%m-%d %H:%M"),
                "open": round(float(row["Open"]), 2),
                "high": round(float(row["High"]), 2),
                "low": round(float(row["Low"]), 2),
                "close": round(float(row["Close"]), 2),
                "volume": int(row["Volume"]),
            })

        # Get previous close for reference line
        hist2d = ticker.history(period="2d", interval="1d")
        prev_close = round(float(hist2d.iloc[-2]["Close"]), 2) if len(hist2d) > 1 else 0

        return jsonify({
            "index": index.upper(),
            "prevClose": prev_close,
            "data": data,
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"data": [], "error": str(e)}), 500


_news_cache = {"global": None, "local": None, "time": 0}

@app.route("/api/bots/geopolitical")
def api_bots_geopolitical():
    """Geopolitical analysis bot - fetches LIVE news affecting Indian markets."""
    import time as _time
    now = _time.time()

    # Cache for 30 minutes
    if _news_cache["global"] and (now - _news_cache["time"]) < 1800:
        return jsonify(_news_cache["global"])

    events = []
    try:
        import requests as req

        # Source 1: Google News RSS for market keywords
        # when:1d = Google-side recency filter. Without it the relevance-ranked feed
        # surfaces re-crawled evergreen items re-stamped with fresh pubDates (an April
        # "Good Friday" story showed as "4h ago" on 2026-07-12).
        rss_feeds = [
            # Topic feed, not search: search relevance ranking resurfaces re-crawled
            # evergreen items (pubDate re-stamped to today), topic headlines are real news.
            ("https://news.google.com/rss/headlines/section/topic/BUSINESS?hl=en-IN&gl=IN&ceid=IN:en", "India Market"),
            ("https://news.google.com/rss/search?q=nifty+sensex+today+when:1d&hl=en-IN&gl=IN", "India Market"),
            ("https://news.google.com/rss/search?q=RBI+policy+india+when:1d&hl=en-IN&gl=IN", "RBI Policy"),
            ("https://news.google.com/rss/search?q=FII+DII+india+market+when:1d&hl=en-IN&gl=IN", "FII/DII"),
            ("https://news.google.com/rss/search?q=global+markets+recession+fed+when:1d&hl=en-IN&gl=IN", "Global"),
            ("https://news.google.com/rss/search?q=crude+oil+price+today+when:1d&hl=en-IN&gl=IN", "Commodities"),
        ]

        import xml.etree.ElementTree as ET
        from datetime import datetime, timedelta
        seen_titles = set()

        for feed_url, category in rss_feeds[:4]:  # Limit to 4 feeds
            try:
                resp = req.get(feed_url, timeout=8, headers={"User-Agent": "TradePilot/1.0"})
                if resp.status_code != 200:
                    continue
                root = ET.fromstring(resp.content)
                items = root.findall(".//item")[:3]  # Top 3 per feed

                for item in items:
                    title = item.findtext("title", "")
                    if not title or title in seen_titles:
                        continue
                    seen_titles.add(title)

                    desc = item.findtext("description", "")
                    pub_date = item.findtext("pubDate", "")

                    # Belt-and-braces with when:1d — drop anything Google still
                    # serves with an old (or unparseable) pubDate.
                    from news_utils import clean_summary, is_recent
                    if not is_recent(pub_date, max_age_h=48):
                        continue
                    desc = clean_summary(desc)

                    # Parse time ago
                    time_ago = "recently"
                    try:
                        from email.utils import parsedate_to_datetime
                        dt = parsedate_to_datetime(pub_date)
                        diff = datetime.now(dt.tzinfo) - dt
                        hours = diff.total_seconds() / 3600
                        if hours < 1: time_ago = f"{int(diff.total_seconds()/60)}m ago"
                        elif hours < 24: time_ago = f"{int(hours)}h ago"
                        else: time_ago = f"{int(hours/24)}d ago"
                    except Exception:
                        pass

                    # Determine impact from keywords
                    title_lower = title.lower()
                    if any(w in title_lower for w in ["crash", "fall", "drop", "recession", "fear", "tension", "war"]):
                        impact = "negative"
                    elif any(w in title_lower for w in ["rally", "surge", "rise", "gain", "bull", "record", "buying"]):
                        impact = "positive"
                    else:
                        impact = "neutral"

                    # Determine affected sectors
                    sectors = []
                    if any(w in title_lower for w in ["bank", "rbi", "rate", "nbfc"]): sectors.append("Banking")
                    if any(w in title_lower for w in ["it", "tech", "infosys", "tcs"]): sectors.append("IT")
                    if any(w in title_lower for w in ["oil", "crude", "ongc", "bpcl"]): sectors.append("Oil & Gas")
                    if any(w in title_lower for w in ["pharma", "drug", "health"]): sectors.append("Pharma")
                    if any(w in title_lower for w in ["auto", "car", "ev"]): sectors.append("Auto")
                    if any(w in title_lower for w in ["fii", "dii", "foreign"]): sectors.append("FII/DII")
                    if not sectors: sectors = [category]

                    events.append({
                        "title": title[:120],
                        "impact": impact,
                        "severity": "high" if any(w in title_lower for w in ["crash", "surge", "record", "rbi", "fed"]) else "medium",
                        "affected_sectors": sectors[:3],
                        "summary": desc[:200] if desc else title,
                        "market_impact": "",
                        "timestamp": time_ago,
                        "source": "Google News",
                    })
            except Exception:
                continue

    except Exception:
        pass

    # Fallback if no news fetched
    if not events:
        events = [
            {"title": "Market data loading...", "impact": "neutral", "severity": "low",
             "affected_sectors": ["General"], "summary": "Live news feed is being refreshed. Check back in a few minutes.",
             "market_impact": "", "timestamp": "now", "source": "system"}
        ]

    # Determine overall sentiment
    pos = sum(1 for e in events if e["impact"] == "positive")
    neg = sum(1 for e in events if e["impact"] == "negative")
    if pos > neg + 1: sentiment = "bullish"
    elif neg > pos + 1: sentiment = "bearish"
    else: sentiment = "neutral"

    result = {"events": events[:8], "overall_sentiment": sentiment, "confidence": min(max(len(events) * 10, 30), 85)}
    _news_cache["global"] = result
    _news_cache["time"] = now
    return jsonify(result)


@app.route("/api/bots/market-pulse")
def api_bots_market_pulse():
    """Market prediction bot - next move analysis."""
    try:
        scores = score_stocks_v2() if HAS_V2 else score_stocks()

        # Find bullish and bearish stocks
        bullish = [s for s in scores if s.get('score', 0) >= 65]
        bearish = [s for s in scores if s.get('score', 0) < 35]
        neutral = [s for s in scores if 35 <= s.get('score', 0) < 65]

        # Top recommendations (ONLY if potential loss < 10%)
        safe_picks = []
        for s in bullish:
            sl = s.get('stop_loss_pct', 10)
            target = s.get('target_pct', 5)
            # Only recommend if stop loss < 10% AND target > stop loss
            if sl <= 10 and target > sl:
                safe_picks.append({
                    "symbol": s.get('name', s.get('symbol', '')),
                    "price": s.get('price', 0),
                    "score": s.get('score', 0),
                    "direction": s.get('direction', 'HOLD'),
                    "target_pct": target,
                    "stop_loss_pct": sl,
                    "risk_reward": s.get('risk_reward', 1),
                    "potential_profit": round(target, 1),
                    "max_loss": round(sl, 1),
                    "safe": True,
                    "reason": s.get('reasons', [{}])[0].get('text', '') if s.get('reasons') else ''
                })

        # Sort by score
        safe_picks.sort(key=lambda x: x['score'], reverse=True)

        # Dangerous stocks (loss > 10% - DO NOT RECOMMEND)
        dangerous = []
        for s in scores:
            sl = s.get('stop_loss_pct', 10)
            if sl > 10:
                dangerous.append({
                    "symbol": s.get('name', s.get('symbol', '')),
                    "price": s.get('price', 0),
                    "score": s.get('score', 0),
                    "stop_loss_pct": sl,
                    "warning": "High risk - potential loss exceeds 10%"
                })

        return jsonify({
            "market_mood": "Bullish" if len(bullish) > len(bearish) else "Bearish" if len(bearish) > len(bullish) else "Neutral",
            "bullish_count": len(bullish),
            "bearish_count": len(bearish),
            "neutral_count": len(neutral),
            "safe_picks": safe_picks[:8],
            "dangerous_count": len(dangerous),
            "analysis": "AI has identified " + str(len(safe_picks)) + " safe picks with <10% downside risk and strong upside potential.",
            "timestamp": "Just now"
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({
            "market_mood": "Neutral",
            "bullish_count": 0, "bearish_count": 0, "neutral_count": 0,
            "safe_picks": [], "dangerous_count": 0,
            "analysis": "Unable to load market pulse data.",
            "timestamp": "Just now"
        })


# ═══════════════════════════════════════════════════════════
# LIVE ENGINE PICKS — what the engines actually hold right now
# Added 2026-04-22 (tonight queue Item #2). Reads paper-trade
# JSON state files. No live mark-to-market — shows entries +
# day-level realized P&L from engine summary.
# ═══════════════════════════════════════════════════════════

LIVE_ENGINES = ["v5", "v5_6", "v5_7"]
PAPER_TRADES_DIR = Path(__file__).resolve().parent.parent / "docs" / "paper-trades"


def _load_engine_state_for(engine):
    """Read the most recent state JSON for an engine. Returns dict or {}."""
    today = datetime.now().strftime("%Y-%m-%d")
    p = PAPER_TRADES_DIR / engine / f"{today}.json"
    if not p.exists():
        # Fall back to most recent file
        files = sorted(PAPER_TRADES_DIR.glob(f"{engine}/2026-*.json"))
        if not files:
            return {}
        p = files[-1]
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


@app.route("/api/live-engine-picks")
def api_live_engine_picks():
    """What v5 / v5_6 / v5_7 are holding right now (live position snapshot).

    Powers the 'Live Engine Picks' dashboard tab + the per-card holding
    indicator on the Stocks tab. Group-by-symbol surfaces consensus picks.
    """
    by_symbol = {}            # symbol -> {engines:[], pools:set, entries:[], total_qty}
    by_engine = {}            # engine -> summary dict
    state_files_used = []

    for eng in LIVE_ENGINES:
        state = _load_engine_state_for(eng)
        if not state:
            by_engine[eng] = {"open": 0, "realized": 0.0, "trades": 0, "win_rate": 0,
                              "regime": "?", "available": False}
            continue
        state_files_used.append(eng)

        summary = state.get("summary", {}) or {}
        wins = int(summary.get("wins", 0))
        trades = int(summary.get("trades", 0))
        wr = round(100.0 * wins / trades, 1) if trades else 0.0

        open_count = 0
        for pname, pool in (state.get("pools") or {}).items():
            for pos in (pool.get("positions") or []):
                sym = pos.get("symbol", "?")
                open_count += 1
                rec = by_symbol.setdefault(sym, {
                    "symbol": sym,
                    "engines": [],
                    "pools": set(),
                    "entries": [],
                    "total_qty": 0,
                })
                if eng not in rec["engines"]:
                    rec["engines"].append(eng)
                rec["pools"].add(pname)
                rec["entries"].append({
                    "engine": eng,
                    "pool": pname,
                    "entry_price": pos.get("entry_price"),
                    "qty": pos.get("qty"),
                    "cost": pos.get("cost"),
                    "entry_time": pos.get("entry_time", ""),
                    "entry_date": pos.get("entry_date", ""),
                    "sl_price": pos.get("sl_price"),
                    "target_price": pos.get("target_price"),
                    "score": pos.get("score"),
                    "direction": pos.get("direction", "LONG"),
                })
                rec["total_qty"] += int(pos.get("qty") or 0)

        by_engine[eng] = {
            "open": open_count,
            "realized": round(float(summary.get("total_pnl", 0) or 0), 2),
            "trades": trades,
            "win_rate": wr,
            "regime": state.get("regime", "?"),
            "available": True,
        }

    # Convert by_symbol to a sorted list — consensus picks first
    positions = []
    for sym, rec in by_symbol.items():
        rec["pools"] = sorted(rec["pools"])
        rec["consensus_count"] = len(rec["engines"])
        positions.append(rec)
    positions.sort(key=lambda r: (-r["consensus_count"], r["symbol"]))

    total_open = sum(e.get("open", 0) for e in by_engine.values())
    total_realized = round(sum(e.get("realized", 0) for e in by_engine.values()), 2)

    return jsonify({
        "as_of": datetime.now().strftime("%H:%M:%S"),
        "engines": LIVE_ENGINES,
        "engines_with_data": state_files_used,
        "total_open_positions": total_open,
        "total_unique_symbols": len(positions),
        "total_realized_pnl": total_realized,
        "by_engine": by_engine,
        "positions": positions,
    })


@app.route("/api/trade/calculate")
def api_trade_calculate():
    """Calculate potential profit/loss for a trade."""
    symbol = request.args.get('symbol', '')
    investment = float(request.args.get('investment', 10000))

    full_symbol = f"{symbol}.NS" if not symbol.endswith(".NS") else symbol

    try:
        scores = score_stocks_v2([full_symbol]) if HAS_V2 else score_stocks([full_symbol])
        if not scores:
            return jsonify({"error": "Stock not found"}), 404

        s = scores[0]
        price = s.get('price', 0)
        if price <= 0:
            return jsonify({"error": "Invalid price"}), 400

        qty = int(investment / price)
        actual_investment = round(qty * price, 2)

        target_pct = float(s.get('target_pct', 5))
        sl_pct = float(s.get('stop_loss_pct', 3))
        score = float(s.get('score', 50))

        potential_profit = round(actual_investment * target_pct / 100, 2)
        max_loss = round(actual_investment * sl_pct / 100, 2)
        max_loss_pct = sl_pct

        # Risk assessment (cast to Python bool to avoid numpy bool_ serialization error)
        safe = bool(max_loss_pct <= 10)
        recommended = bool(safe and score >= 50 and target_pct > sl_pct)

        # Risk level
        if max_loss_pct <= 5:
            risk_level = "Low"
        elif max_loss_pct <= 10:
            risk_level = "Moderate"
        elif max_loss_pct <= 20:
            risk_level = "High"
        else:
            risk_level = "Very High"

        return jsonify({
            "symbol": s.get('name', symbol),
            "price": price,
            "investment": actual_investment,
            "quantity": qty,
            "score": score,
            "direction": s.get('direction', 'HOLD'),
            "target_pct": target_pct,
            "target_price": round(price * (1 + target_pct/100), 2),
            "potential_profit": potential_profit,
            "stop_loss_pct": sl_pct,
            "stop_loss_price": round(price * (1 - sl_pct/100), 2),
            "max_loss": max_loss,
            "max_loss_pct": max_loss_pct,
            "risk_level": risk_level,
            "safe": safe,
            "recommended": recommended,
            "risk_reward": s.get('risk_reward', 1),
            "warning": None if safe else "DANGER: Potential loss exceeds 10% of investment. Not recommended."
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route("/api/wizard/recommend")
def api_wizard_recommend():
    """Investment Wizard: given a budget, recommend the best stocks to buy.
    Shows only stocks the user can actually afford, sorted by AI score.
    Filters out anything with >10% risk.
    """
    budget = float(request.args.get('budget', 5000))
    category = request.args.get('category', 'all')

    try:
        from data_engine import STOCK_CATEGORIES
        # Get stocks for this category
        cat_stocks = STOCK_CATEGORIES.get(category, STOCK_CATEGORIES['all'])['stocks']

        # Score all stocks in category
        all_scores = score_stocks_v2(cat_stocks) if HAS_V2 else score_stocks()

        # Filter: affordable (price <= budget) + safe (loss < 10%) + BUY direction
        affordable = []
        for s in all_scores:
            price = s.get('price', 0)
            if not price or price != price or price <= 0 or price > budget:  # NaN check: x != x
                continue
            qty = int(budget / price)
            if qty < 1:
                continue

            investment = round(qty * price, 2)
            target_pct = float(s.get('target_pct', 5))
            sl_pct = float(s.get('stop_loss_pct', 3))
            potential_profit = round(investment * target_pct / 100, 2)
            max_loss = round(investment * sl_pct / 100, 2)
            safe = bool(sl_pct <= 10)

            affordable.append({
                "symbol": s.get('name', s.get('symbol', '')),
                "name": s.get('name', ''),
                "price": price,
                "score": s.get('score', 0),
                "direction": s.get('direction', 'HOLD'),
                "quantity": qty,
                "investment": investment,
                "change_left": round(budget - investment, 2),
                "target_pct": target_pct,
                "stop_loss_pct": sl_pct,
                "potential_profit": potential_profit,
                "max_loss": max_loss,
                "risk_reward": s.get('risk_reward', 1),
                "safe": safe,
                "recommended": bool(safe and s.get('score', 0) >= 55),
                "reasons": s.get('reasons', [])[:3],
                "trend": s.get('trend', 'Sideways'),
                "rsi": s.get('rsi', 50),
            })

        # Sort: recommended first, then by score
        affordable.sort(key=lambda x: (x['recommended'], x['score']), reverse=True)

        # Stats
        total_available = len(affordable)
        recommended_count = sum(1 for s in affordable if s['recommended'])
        risky_excluded = len(all_scores) - total_available

        return jsonify({
            "budget": budget,
            "category": category,
            "total_available": total_available,
            "recommended_count": recommended_count,
            "risky_excluded": risky_excluded,
            "stocks": affordable[:30],  # top 30
        })
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e), "stocks": []}), 500


_movers_cache = {"data": None, "time": 0}

@app.route("/api/gainers-losers")
def api_gainers_losers():
    """Get top 50 gainers and top 50 losers from the full universe."""
    import math, time as _time
    now = _time.time()

    # Cache for 10 minutes (heavy endpoint)
    if _movers_cache["data"] and (now - _movers_cache["time"]) < 600:
        return jsonify(_movers_cache["data"])

    try:
        from data_engine import STOCK_CATEGORIES
        all_stocks = STOCK_CATEGORIES.get('all', {}).get('stocks', [])

        raw_scores = None
        if ensure_data():
            try:
                raw_scores = score_stocks_v2(all_stocks) if HAS_V2 else score_stocks()
            except Exception:
                pass

        if not raw_scores:
            return jsonify({"gainers": [], "losers": []})

        def safe(v, default=0):
            if v is None:
                return default
            try:
                if math.isnan(v) or math.isinf(v):
                    return default
            except (TypeError, ValueError):
                pass
            return v

        # Build clean list
        clean = []
        for s in raw_scores:
            price = safe(s.get("price"), 0)
            change = safe(s.get("change_pct"), 0)
            score = safe(s.get("score"), 0)
            if price == 0:
                continue
            clean.append({
                "symbol": s.get("name", s.get("symbol", "").replace(".NS", "")),
                "name": s.get("name", s.get("symbol", "")),
                "price": round(price, 2),
                "change": round(change, 2),
                "score": round(score, 1),
                "direction": s.get("direction", "HOLD"),
                "rsi": round(safe(s.get("rsi"), 50), 1),
                "trend": s.get("trend", "Sideways"),
                "volatility": "High" if safe(s.get("volatility"), 20) > 25 else "Low" if safe(s.get("volatility"), 20) < 15 else "Medium",
                "macd": s.get("macd_signal", "Neutral"),
            })

        # Index filter
        idx_filter = request.args.get("index", "all").lower()
        if idx_filter != "all":
            try:
                from v4.config import NIFTY_50_SYMBOLS, NIFTY_200_SYMBOLS
                idx_sets = {
                    "nifty50": set(NIFTY_50_SYMBOLS),
                    "nifty100": set(NIFTY_50_SYMBOLS),  # approximate
                    "nifty200": set(NIFTY_200_SYMBOLS),
                    "midcap": set(NIFTY_200_SYMBOLS) - set(NIFTY_50_SYMBOLS),
                    "smallcap": set(),  # needs separate list
                    "total": set(),  # show all
                }
                filter_set = idx_sets.get(idx_filter)
                if filter_set:
                    clean = [s for s in clean if s["symbol"].replace(".NS", "") in filter_set
                             or s["name"].replace(".NS", "") in filter_set]
            except ImportError:
                pass

        gainers = sorted(clean, key=lambda x: x["change"], reverse=True)[:50]
        losers = sorted(clean, key=lambda x: x["change"])[:50]

        result = {"gainers": gainers, "losers": losers, "index": idx_filter}
        _movers_cache["data"] = result
        _movers_cache["time"] = now
        return jsonify(result)
    except Exception as e:
        traceback.print_exc()
        return jsonify({"gainers": [], "losers": []}), 500


@app.route("/api/categories")
def api_categories():
    """Return available stock categories."""
    from data_engine import STOCK_CATEGORIES
    cats = []
    for key, val in STOCK_CATEGORIES.items():
        cats.append({
            "id": key,
            "name": val["name"],
            "desc": val["desc"],
            "count": len(val["stocks"]),
        })
    return jsonify(cats)


# ---------------------------------------------------------------------------
# Paper Trading System -- simulated trading with virtual Rs 10 Lakh
# ---------------------------------------------------------------------------

INITIAL_CASH = 1000000  # Rs 10,00,000

paper_portfolio = {
    "cash": INITIAL_CASH,
    "initial_cash": INITIAL_CASH,
    "positions": {},   # {symbol: {qty, avg_price, current_price, pnl, pnl_pct}}
    "history": [],     # [{type, symbol, qty, price, total, pnl, timestamp}]
    "trades_today": 0,
    "win_count": 0,
    "loss_count": 0,
}


def get_stock_price(symbol):
    """Get current price for a stock from scored data or yfinance fallback."""
    clean = symbol.replace(".NS", "")
    full = clean + ".NS"
    try:
        scores = score_stocks_v2([full]) if HAS_V2 else score_stocks([full])
        for s in scores:
            p = s.get("price", 0)
            if p and p > 0:
                return round(float(p), 2)
    except Exception:
        pass
    # Fallback: yfinance
    try:
        import yfinance as yf
        t = yf.Ticker(full)
        h = t.history(period="1d")
        if len(h) > 0:
            return round(float(h.iloc[-1]["Close"]), 2)
    except Exception:
        pass
    return 0


def _refresh_positions():
    """Update current_price and pnl for all held positions."""
    for sym, pos in paper_portfolio["positions"].items():
        price = get_stock_price(sym)
        if price > 0:
            pos["current_price"] = price
        pos["pnl"] = round((pos["current_price"] - pos["avg_price"]) * pos["qty"], 2)
        pos["pnl_pct"] = round((pos["current_price"] - pos["avg_price"]) / pos["avg_price"] * 100, 2) if pos["avg_price"] else 0


def calculate_portfolio_value():
    total = paper_portfolio["cash"]
    for pos in paper_portfolio["positions"].values():
        total += pos["qty"] * pos["current_price"]
    return round(total, 2)


def calculate_total_pnl():
    return round(calculate_portfolio_value() - paper_portfolio["initial_cash"], 2)


def calculate_total_pnl_pct():
    initial = paper_portfolio["initial_cash"]
    if initial == 0:
        return 0
    return round(calculate_total_pnl() / initial * 100, 2)


def _execute_buy(symbol, quantity):
    """Core buy logic shared by /buy and /swipe. Returns (response_dict, status_code)."""
    price = get_stock_price(symbol)
    if price <= 0:
        return {"error": f"Cannot get price for {symbol}"}, 400

    total_cost = round(price * quantity, 2)
    if total_cost > paper_portfolio["cash"]:
        return {"error": "Insufficient cash", "available": paper_portfolio["cash"], "required": total_cost}, 400

    # 10% risk guardrail -- check stop_loss_pct from scoring
    clean = symbol.replace(".NS", "")
    full = clean + ".NS"
    try:
        scores = score_stocks_v2([full]) if HAS_V2 else score_stocks([full])
        if scores:
            sl_pct = scores[0].get("stop_loss_pct", 5)
            if sl_pct > 10:
                return {
                    "error": "Risk guardrail: stop loss exceeds 10%",
                    "stop_loss_pct": sl_pct,
                    "symbol": clean,
                }, 400
    except Exception:
        pass  # proceed without guardrail if scoring fails

    # Update or create position
    if clean in paper_portfolio["positions"]:
        pos = paper_portfolio["positions"][clean]
        old_total = pos["avg_price"] * pos["qty"]
        new_total = old_total + total_cost
        pos["qty"] += quantity
        pos["avg_price"] = round(new_total / pos["qty"], 2)
        pos["current_price"] = price
    else:
        paper_portfolio["positions"][clean] = {
            "qty": quantity,
            "avg_price": price,
            "current_price": price,
            "pnl": 0,
            "pnl_pct": 0,
        }

    paper_portfolio["cash"] = round(paper_portfolio["cash"] - total_cost, 2)
    paper_portfolio["trades_today"] += 1

    trade_record = {
        "type": "buy",
        "symbol": clean,
        "qty": quantity,
        "price": price,
        "total": total_cost,
        "pnl": None,
        "timestamp": datetime.now().isoformat(),
    }
    paper_portfolio["history"].append(trade_record)

    return {
        "action": "bought",
        "symbol": clean,
        "quantity": quantity,
        "price": price,
        "total": total_cost,
        "cash_remaining": paper_portfolio["cash"],
    }, 200


@app.route("/api/paper/portfolio")
def api_paper_portfolio():
    """Return current paper trading portfolio with live prices."""
    _refresh_positions()
    return jsonify({
        "cash": paper_portfolio["cash"],
        "initial_cash": paper_portfolio["initial_cash"],
        "positions": paper_portfolio["positions"],
        "total_value": calculate_portfolio_value(),
        "total_pnl": calculate_total_pnl(),
        "total_pnl_pct": calculate_total_pnl_pct(),
        "trades_today": paper_portfolio["trades_today"],
        "win_count": paper_portfolio["win_count"],
        "loss_count": paper_portfolio["loss_count"],
    })


@app.route("/api/paper/buy", methods=["POST"])
def api_paper_buy():
    """Paper buy a stock."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    quantity = int(data.get("quantity", 1))
    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if quantity < 1:
        return jsonify({"error": "quantity must be >= 1"}), 400

    result, status = _execute_buy(symbol, quantity)
    return jsonify(result), status


@app.route("/api/paper/sell", methods=["POST"])
def api_paper_sell():
    """Paper sell a position (partial or full)."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "").replace(".NS", "")
    quantity = int(data.get("quantity", 0))  # 0 = sell all

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if symbol not in paper_portfolio["positions"]:
        return jsonify({"error": f"No position in {symbol}"}), 400

    pos = paper_portfolio["positions"][symbol]
    sell_qty = quantity if quantity > 0 else pos["qty"]
    if sell_qty > pos["qty"]:
        return jsonify({"error": f"Only hold {pos['qty']} shares of {symbol}"}), 400

    # Get current price for sale
    price = get_stock_price(symbol)
    if price <= 0:
        price = pos["current_price"]  # fallback to last known

    total_sale = round(price * sell_qty, 2)
    pnl = round((price - pos["avg_price"]) * sell_qty, 2)
    pnl_pct = round((price - pos["avg_price"]) / pos["avg_price"] * 100, 2) if pos["avg_price"] else 0

    # Update win/loss counts
    if pnl >= 0:
        paper_portfolio["win_count"] += 1
    else:
        paper_portfolio["loss_count"] += 1

    # Update cash
    paper_portfolio["cash"] = round(paper_portfolio["cash"] + total_sale, 2)
    paper_portfolio["trades_today"] += 1

    # Update or remove position
    if sell_qty >= pos["qty"]:
        del paper_portfolio["positions"][symbol]
    else:
        pos["qty"] -= sell_qty

    trade_record = {
        "type": "sell",
        "symbol": symbol,
        "qty": sell_qty,
        "price": price,
        "total": total_sale,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "timestamp": datetime.now().isoformat(),
    }
    paper_portfolio["history"].append(trade_record)

    return jsonify({
        "action": "sold",
        "symbol": symbol,
        "quantity": sell_qty,
        "price": price,
        "total": total_sale,
        "pnl": pnl,
        "pnl_pct": pnl_pct,
        "cash_remaining": paper_portfolio["cash"],
    })


@app.route("/api/paper/reset", methods=["POST"])
def api_paper_reset():
    """Reset paper trading account to initial Rs 10 Lakh."""
    paper_portfolio["cash"] = INITIAL_CASH
    paper_portfolio["initial_cash"] = INITIAL_CASH
    paper_portfolio["positions"] = {}
    paper_portfolio["history"] = []
    paper_portfolio["trades_today"] = 0
    paper_portfolio["win_count"] = 0
    paper_portfolio["loss_count"] = 0
    return jsonify({"action": "reset", "cash": INITIAL_CASH})


@app.route("/api/paper/history")
def api_paper_history():
    """Return paper trade history (newest first)."""
    return jsonify(list(reversed(paper_portfolio["history"])))


@app.route("/api/paper/swipe", methods=["POST"])
def api_paper_swipe():
    """Swipe right = buy with auto-calculated qty (5% of cash), swipe left = skip."""
    data = request.get_json() or {}
    symbol = data.get("symbol", "")
    direction = data.get("direction", "")

    if not symbol:
        return jsonify({"error": "symbol is required"}), 400
    if direction not in ("right", "left"):
        return jsonify({"error": "direction must be 'right' or 'left'"}), 400

    clean = symbol.replace(".NS", "")

    if direction == "left":
        paper_portfolio["history"].append({
            "type": "skip",
            "symbol": clean,
            "timestamp": datetime.now().isoformat(),
        })
        return jsonify({"action": "skipped", "symbol": clean})

    # direction == "right" -- auto-buy 5% of available cash
    price = get_stock_price(clean)
    if price <= 0:
        return jsonify({"error": f"Cannot get price for {clean}"}), 400

    invest_amount = paper_portfolio["cash"] * 0.05
    qty = max(1, int(invest_amount / price))

    result, status = _execute_buy(clean, qty)
    if status == 200:
        result["auto_invest_amount"] = round(invest_amount, 2)
    return jsonify(result), status


@app.route("/api/analytics/track", methods=["POST"])
def api_track():
    """Track user events."""
    try:
        data = request.get_json() or {}
        event = data.get("event", "")
        user_id = data.get("user_id", "anon")

        if event == "visit":
            track_visit(user_id, data.get("device"), data.get("user_agent"))
        elif event == "page_view":
            track_page_view(user_id, data.get("page", "/"))
        elif event == "stock_view":
            track_stock_view(user_id, data.get("symbol"), data.get("score"), data.get("direction"))
        elif event == "swipe":
            track_swipe(user_id, data.get("symbol"), data.get("action"), data.get("score"), data.get("price"), data.get("quantity"))
        elif event == "paper_trade":
            track_paper_trade(user_id, data.get("symbol"), data.get("action"), data.get("quantity", 0), data.get("price", 0), data.get("pnl"), data.get("source", "manual"))
        elif event == "wizard_search":
            track_wizard_search(user_id, data.get("budget", 0), data.get("category", ""), data.get("results_count", 0), data.get("recommended_count", 0))
        elif event == "feedback":
            track_feedback(user_id, data.get("type", "general"), data.get("message", ""), data.get("page"))

        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@app.route("/admin")
def admin_dashboard():
    """Analytics dashboard for founders — localhost only."""
    # Security: only allow from localhost
    if request.remote_addr not in ('127.0.0.1', '::1', 'localhost'):
        return jsonify({"error": "Forbidden"}), 403
    stats = get_dashboard_stats()
    return jsonify(stats)


# ═══════════════════════════════════════════════════════
# TRADE LAB — v4 vs v5 daily trade tracking
# ═══════════════════════════════════════════════════════

@app.route("/api/tradelab/days")
def api_tradelab_days():
    """List all trading days with summary P&L for v4 and v5."""
    import glob
    base = os.path.join(os.path.dirname(__file__), "..", "docs", "paper-trades")
    days = {}

    # v4 days (only date-named files like 2026-04-10.json)
    import re as _re
    for f in sorted(glob.glob(os.path.join(base, "v4", "*.json"))):
        if not _re.match(r'^\d{4}-\d{2}-\d{2}\.json$', os.path.basename(f)):
            continue
        try:
            with open(f) as fh:
                s = json.load(fh)
            date = s.get("date") or os.path.basename(f).replace(".json", "")
            if date not in days:
                days[date] = {"date": date, "v4": None, "v5": None}
            cl = s.get("closed_trades", [])
            w = sum(1 for t in cl if t.get("pnl", 0) > 0)
            days[date]["v4"] = {
                "pnl": round(s.get("realized_pnl", 0), 2),
                "pnl_pct": round(s.get("realized_pnl", 0) / max(s.get("daily_pool", 1000000), 1) * 100, 2),
                "trades": len(cl), "wins": w,
                "win_rate": round(w / len(cl) * 100, 1) if cl else 0,
                "pool": s.get("daily_pool", 1000000),
            }
        except Exception:
            pass

    # v5 days (only date-named files)
    for f in sorted(glob.glob(os.path.join(base, "v5", "*.json"))):
        if not _re.match(r'^\d{4}-\d{2}-\d{2}\.json$', os.path.basename(f)):
            continue
        try:
            with open(f) as fh:
                s = json.load(fh)
            date = s.get("date") or os.path.basename(f).replace(".json", "")
            if date not in days:
                days[date] = {"date": date, "v4": None, "v5": None}
            sm = s.get("summary", {})
            days[date]["v5"] = {
                "pnl": round(sm.get("total_pnl", 0), 2),
                "pnl_pct": round(sm.get("total_pnl", 0) / max(s.get("total_capital", 5000000), 1) * 100, 2),
                "trades": sm.get("trades", 0), "wins": sm.get("wins", 0),
                "win_rate": round(sm.get("wins", 0) / max(sm.get("trades", 1), 1) * 100, 1),
                "longs": sm.get("longs", 0), "shorts": sm.get("shorts", 0),
                "pool": s.get("total_capital", 5000000),
                "regime": s.get("regime", "UNKNOWN"),
            }
        except Exception:
            pass

    return jsonify(sorted(days.values(), key=lambda d: d["date"], reverse=True))


@app.route("/api/engine-arena")
def api_engine_arena():
    """Live status for v5.2, v5.3, v5.4 engines."""
    import json as _json
    from pathlib import Path as _Path
    base = _Path(__file__).parent.parent / "docs" / "paper-trades"
    today = __import__('datetime').datetime.now().strftime("%Y-%m-%d")
    result = {}

    for eng, dirname in [("v5.2", "v5_2"), ("v5.3", "v5_3"), ("v5.6", "v5_6"), ("v5.7", "v5_7"), ("v5_classic", "v5_classic")]:
        state_file = base / dirname / f"{today}.json"
        info = {"pnl": 0, "trades": 0, "wins": 0, "losses": 0, "longs": 0, "shorts": 0,
                "long_pnl": 0, "short_pnl": 0, "regime": "?", "positions": [],
                "confirmed": 0, "cancelled": 0, "capital": 1000000,
                "direction_budget": {"long": 0.5, "short": 0.5}}
        if state_file.exists():
            try:
                d = _json.loads(state_file.read_text())
                s = d.get("summary", {})
                info["pnl"] = s.get("total_pnl", 0)
                info["trades"] = s.get("trades", 0)
                info["wins"] = s.get("wins", 0)
                info["losses"] = s.get("losses", 0)
                info["longs"] = s.get("longs", 0)
                info["shorts"] = s.get("shorts", 0)
                info["long_pnl"] = s.get("long_pnl", 0)
                info["short_pnl"] = s.get("short_pnl", 0)
                info["regime"] = d.get("regime", "?")
                info["confirmed"] = s.get("confirmed", 0)
                info["cancelled"] = s.get("cancelled", 0)
                info["capital"] = d.get("total_capital", 1000000)
                info["direction_budget"] = d.get("direction_budget", {"long": 0.5, "short": 0.5})
                # Collect open positions
                for pn, pd in d.get("pools", {}).items():
                    for p in pd.get("positions", []):
                        info["positions"].append({
                            "engine": eng, "symbol": p.get("symbol"),
                            "direction": p.get("position_type", "LONG"),
                            "pool": pn, "entry_price": p.get("entry_price", 0),
                            "sl_price": p.get("sl_price", 0),
                            "target_price": p.get("target_price", 0),
                            "trailing": p.get("trailing_activated", False)})
            except Exception:
                pass
        # Also check carry forward for cumulative
        cf_file = base / dirname / f"carry_forward_{dirname}.json"
        if cf_file.exists():
            try:
                cf = _json.loads(cf_file.read_text())
                info["cumulative_pnl"] = cf.get("cumulative_pnl", 0)
                info["capital"] = cf.get("closing_balance", 1000000)
            except Exception:
                pass
        result[eng] = info
    return jsonify(result)


@app.route("/api/tradelab/trades/<date>")
def api_tradelab_trades(date):
    """Get all individual trades for a specific date, both v4 and v5."""
    base = os.path.join(os.path.dirname(__file__), "..", "docs", "paper-trades")
    result = {"date": date, "v4_trades": [], "v5_trades": [], "v4_open": [], "v5_open": []}

    # v4
    v4f = os.path.join(base, "v4", f"{date}.json")
    if os.path.exists(v4f):
        with open(v4f) as fh:
            s = json.load(fh)
        result["v4_trades"] = s.get("closed_trades", [])
        result["v4_open"] = [p for p in s.get("positions", []) if p.get("status") == "open"]
        result["v4_summary"] = {
            "pnl": round(s.get("realized_pnl", 0), 2),
            "pool": s.get("daily_pool", 1000000),
            "scans": s.get("scan_count", 0),
            "rescores": s.get("rescore_count", 0),
        }

    # v5
    v5f = os.path.join(base, "v5", f"{date}.json")
    if os.path.exists(v5f):
        with open(v5f) as fh:
            s = json.load(fh)
        for pool_name, pool_data in s.get("pools", {}).items():
            for t in pool_data.get("closed", []):
                t["pool"] = pool_name
                result["v5_trades"].append(t)
            for p in pool_data.get("positions", []):
                p["pool"] = pool_name
                result["v5_open"].append(p)
        result["v5_summary"] = s.get("summary", {})
        result["v5_regime"] = s.get("regime", "UNKNOWN")
        result["v5_premarket"] = s.get("premarket", {})

    return jsonify(result)


# ═══════════════ AI PICKS & ADVISOR ═══════════════

@app.route("/api/picks")
def api_picks():
    """Get AI-powered top picks across categories."""
    category = request.args.get("category", "stocks")  # stocks, etfs, mf
    count = int(request.args.get("count", 10))
    horizon = request.args.get("horizon", "intraday")  # intraday, swing, investment

    if category == "stocks":
        try:
            scores = score_stocks_v4() if HAS_V4 else (score_stocks_v2(NIFTY_STOCKS) if HAS_V2 else score_stocks())
            # Sort by score, take top N
            picks = sorted(scores, key=lambda x: x.get("score", 0), reverse=True)[:count]
            # Add recommendation context
            for p in picks:
                score = p.get("score", 0)
                if score > 70: p["recommendation"] = "Strong Buy"
                elif score > 60: p["recommendation"] = "Buy"
                elif score > 50: p["recommendation"] = "Hold"
                else: p["recommendation"] = "Watch"

                # Add horizon-specific advice
                if horizon == "intraday":
                    p["strategy"] = f"Entry near {p.get('price', 0):.0f}, SL {p.get('price', 0) * 0.985:.0f}, Target {p.get('price', 0) * 1.02:.0f}"
                elif horizon == "swing":
                    p["strategy"] = f"Buy on dips near support. Hold 3-7 days. Target +3-5%"
                else:
                    p["strategy"] = f"Accumulate over next month. Long-term outlook positive"

            return jsonify({"picks": picks, "category": category, "horizon": horizon, "count": len(picks), "engine": "v4" if HAS_V4 else "v2"})
        except Exception as e:
            return jsonify({"picks": [], "error": str(e)})

    elif category == "etfs":
        # Top ETFs for Indian market
        etfs = [
            {"symbol": "NIFTYBEES", "name": "Nippon Nifty 50 ETF", "price": 240, "change": -0.9, "recommendation": "Buy on dips", "why": "Core portfolio holding. Low cost Nifty 50 exposure."},
            {"symbol": "BANKBEES", "name": "Nippon Bank Nifty ETF", "price": 555, "change": -0.8, "recommendation": "Hold", "why": "Banking sector volatile. Wait for RBI clarity."},
            {"symbol": "GOLDBEES", "name": "Nippon Gold ETF", "price": 58, "change": 0.5, "recommendation": "Strong Buy", "why": "Gold rallying globally. Safe haven in uncertainty."},
            {"symbol": "ITBEES", "name": "Nippon IT ETF", "price": 38, "change": -1.5, "recommendation": "Watch", "why": "IT sector under pressure. Wait for earnings season."},
            {"symbol": "JUNIORBEES", "name": "Nippon Junior Nifty ETF", "price": 680, "change": 0.3, "recommendation": "Buy", "why": "Nifty Next 50 has higher growth potential."},
            {"symbol": "LIQUIDBEES", "name": "Nippon Liquid ETF", "price": 1000, "change": 0.02, "recommendation": "Park Cash", "why": "Park idle trading capital. Better than savings account."},
            {"symbol": "SILVERBEES", "name": "Nippon Silver ETF", "price": 88, "change": 1.2, "recommendation": "Buy", "why": "Silver undervalued vs gold. Industrial demand rising."},
            {"symbol": "PSUBNKBEES", "name": "Nippon PSU Bank ETF", "price": 72, "change": 0.8, "recommendation": "Strong Buy", "why": "PSU banks showing strong NPA recovery."},
        ]
        return jsonify({"picks": etfs[:count], "category": "etfs", "count": min(count, len(etfs))})

    elif category == "mf":
        # Top mutual funds
        mfs = [
            {"symbol": "PPFAS", "name": "Parag Parikh Flexi Cap", "nav": 82, "returns_1y": 18.5, "recommendation": "Strong Buy", "why": "Best diversified fund. US + India exposure. Consistent alpha."},
            {"symbol": "HDFC_MID", "name": "HDFC Mid-Cap Opportunities", "nav": 175, "returns_1y": 22.3, "recommendation": "Buy (SIP)", "why": "Top mid-cap fund. SIP for 3+ years."},
            {"symbol": "AXIS_SMALL", "name": "Axis Small Cap Fund", "nav": 92, "returns_1y": 28.1, "recommendation": "Buy (SIP)", "why": "High growth potential. Only via SIP (volatile)."},
            {"symbol": "ICICI_BLUE", "name": "ICICI Pru Bluechip Fund", "nav": 95, "returns_1y": 12.8, "recommendation": "Core Holding", "why": "Large cap stability. Good for risk-averse investors."},
            {"symbol": "KOTAK_FLEX", "name": "Kotak Flexicap Fund", "nav": 68, "returns_1y": 16.2, "recommendation": "Buy", "why": "Flexible allocation across market caps."},
            {"symbol": "SBI_CONTRA", "name": "SBI Contra Fund", "nav": 350, "returns_1y": 20.5, "recommendation": "Strong Buy", "why": "Value investing. Buys beaten-down stocks."},
            {"symbol": "NIFTY_INDEX", "name": "UTI Nifty 50 Index Fund", "nav": 150, "returns_1y": 11.5, "recommendation": "Best for Beginners", "why": "Lowest cost. Just tracks Nifty 50."},
            {"symbol": "QUANT_SMALL", "name": "Quant Small Cap Fund", "nav": 220, "returns_1y": 35.2, "recommendation": "High Risk Buy", "why": "Top performer but very volatile. Only 5-10% of portfolio."},
        ]
        return jsonify({"picks": mfs[:count], "category": "mf", "count": min(count, len(mfs))})

    return jsonify({"picks": [], "error": "Unknown category"})


@app.route("/api/ask", methods=["POST"])
def api_ask():
    """Answer market questions using available data."""
    data = request.get_json() or {}
    question = data.get("question", "").strip()
    if not question:
        return jsonify({"error": "No question provided"}), 400

    # Build context from available data
    answer = generate_market_answer(question)
    return jsonify({"question": question, "answer": answer})


def generate_market_answer(question):
    """Generate answer using available market data. Smart keyword matching + data-driven."""
    import re
    q = question.lower().strip()

    # Build stock name → symbol mapping for fuzzy matching
    _name_map = {
        "tata steel": "TATASTEEL", "tata motors": "TATAMOTORS", "tata power": "TATAPOWER",
        "tata consumer": "TATACONSUM", "tata chemicals": "TATACHEM", "tata elxsi": "TATAELXSI",
        "tata investment": "TATAINVEST", "tata comm": "TATACOMM",
        "reliance": "RELIANCE", "infosys": "INFY", "hdfc bank": "HDFCBANK", "hdfc": "HDFCBANK",
        "icici bank": "ICICIBANK", "icici": "ICICIBANK", "sbi": "SBIN", "state bank": "SBIN",
        "kotak": "KOTAKBANK", "kotak bank": "KOTAKBANK", "axis bank": "AXISBANK", "axis": "AXISBANK",
        "bajaj finance": "BAJFINANCE", "bajaj finserv": "BAJAJFINSV", "bajaj auto": "BAJAJ-AUTO",
        "asian paints": "ASIANPAINT", "asian paint": "ASIANPAINT", "maruti": "MARUTI",
        "maruti suzuki": "MARUTI", "hero moto": "HEROMOTOCO", "hero motocorp": "HEROMOTOCO",
        "eicher motors": "EICHERMOT", "eicher": "EICHERMOT", "m&m": "M&M", "mahindra": "M&M",
        "sun pharma": "SUNPHARMA", "dr reddy": "DRREDDY", "dr reddys": "DRREDDY",
        "ultratech": "ULTRACEMCO", "ultra tech": "ULTRACEMCO", "titan": "TITAN",
        "wipro": "WIPRO", "hcl tech": "HCLTECH", "hcltech": "HCLTECH", "hcl": "HCLTECH",
        "tech mahindra": "TECHM", "tech m": "TECHM", "l&t": "LT", "larsen": "LT",
        "adani enterprises": "ADANIENT", "adani ports": "ADANIPORTS", "adani green": "ADANIGREEN",
        "adani power": "ADANIPOWER", "power grid": "POWERGRID", "ntpc": "NTPC",
        "coal india": "COALINDIA", "ongc": "ONGC", "bpcl": "BPCL", "ioc": "IOC",
        "indusind bank": "INDUSINDBK", "indusind": "INDUSINDBK",
        "nestle": "NESTLEIND", "britannia": "BRITANNIA", "itc": "ITC", "hindustan unilever": "HINDUNILVR",
        "hul": "HINDUNILVR", "bharti airtel": "BHARTIARTL", "airtel": "BHARTIARTL",
        "jio financial": "JIOFIN", "jio": "JIOFIN", "zomato": "ZOMATO",
        "paytm": "PAYTM", "nykaa": "NYKAA", "delhivery": "DELHIVERY",
        "jsw steel": "JSWSTEEL", "jsw energy": "JSWENERGY", "jsw": "JSWSTEEL",
        "hindalco": "HINDALCO", "vedanta": "VEDL", "vedl": "VEDL",
        "grasim": "GRASIM", "shriram finance": "SHRIRAMFIN", "shriram": "SHRIRAMFIN",
        "apollo hospital": "APOLLOHOSP", "apollo": "APOLLOHOSP",
        "cipla": "CIPLA", "divis lab": "DIVISLAB", "divis": "DIVISLAB",
        "sbi life": "SBILIFE", "hdfc life": "HDFCLIFE",
        "mcx": "MCX", "voltas": "VOLTAS", "bhel": "BHEL", "zydus": "ZYDUSLIFE",
        "zydus life": "ZYDUSLIFE", "zydus wellness": "ZYDUSLIFE",
        "waaree": "WAAREEENER", "waaree energies": "WAAREEENER",
        "page industries": "PAGEIND", "coforge": "COFORGE",
        "nifty": "^NSEI", "sensex": "^BSESN", "bank nifty": "^NSEBANK",
    }

    # Try to find a stock in the query
    def find_stock(query):
        q_lower = query.lower().strip()
        # 1. Exact name match (longest first)
        for name in sorted(_name_map.keys(), key=len, reverse=True):
            if name in q_lower:
                return _name_map[name]
        # 2. Try each word as a symbol directly
        for word in q_lower.replace("?", "").replace(".", "").split():
            sym = word.upper()
            if len(sym) >= 2:
                try:
                    scores = score_stocks_v4() if HAS_V4 else []
                    match = next((s for s in scores if s.get("symbol", "").replace(".NS", "") == sym), None)
                    if match:
                        return sym
                except Exception:
                    pass
        return None

    # Stock lookup
    sym = find_stock(q)
    if sym and not sym.startswith("^"):
        try:
            scores = score_stocks_v4() if HAS_V4 else []
            stock_data = next((s for s in scores if s.get("symbol", "").replace(".NS", "") == sym), None)
            if stock_data:
                score = stock_data.get("score", 0)
                price = stock_data.get("price", 0)
                change = stock_data.get("change_pct", 0)
                direction = stock_data.get("direction", "HOLD")
                rsi = stock_data.get("rsi", 50)
                vol = stock_data.get("volatility", "Medium")

                # Build rich response
                if score > 70: rec, rec_detail = "Strong Buy", "High composite score across multiple signals. Consider entry."
                elif score > 60: rec, rec_detail = "Buy", "Above-average signal strength. Good for swing or intraday."
                elif score > 50: rec, rec_detail = "Hold", "Moderate signal. Wait for stronger confirmation before entering."
                elif score > 40: rec, rec_detail = "Weak", "Below average. Not recommended for fresh entry."
                else: rec, rec_detail = "Avoid", "Weak on most signals. Stay away or consider shorting."

                lines = [
                    f"**{sym}** -- Rs {price:.2f} ({change:+.2f}%)",
                    "",
                    f"AI Score: **{score:.0f}/100** | Signal: **{direction}**",
                    f"RSI: {rsi:.0f} ({'Overbought - may correct' if rsi > 70 else 'Oversold - bounce possible' if rsi < 30 else 'Neutral range'})",
                    f"Volatility: {vol}",
                    "",
                    f"**Recommendation: {rec}**",
                    f"{rec_detail}",
                    "",
                ]
                if direction == "BUY":
                    sl = price * 0.985
                    tgt = price * 1.02
                    lines.append(f"**Intraday Strategy:**")
                    lines.append(f"Entry: Rs {price:.0f} | SL: Rs {sl:.0f} (-1.5%) | Target: Rs {tgt:.0f} (+2%)")
                    lines.append(f"Risk:Reward = 1:1.3")
                    lines.append("")
                    lines.append(f"**Swing Strategy (3-7 days):**")
                    lines.append(f"Buy on dips near Rs {price*0.97:.0f}. Target Rs {price*1.05:.0f} (+5%)")
                elif direction == "AVOID":
                    lines.append(f"**Strategy:** No entry recommended. Wait for score > 60.")
                    lines.append(f"If you hold, set SL at Rs {price*0.95:.0f} (-5%)")
                else:
                    lines.append(f"**Strategy:** Hold if already in position. Fresh entry at Rs {price*0.98:.0f} support.")

                return "\n".join(lines)
        except Exception:
            pass

        # Stock found in name map but not in scorer — try basic info
        return f"**{sym}** is recognized but not currently in our scoring universe or data is loading.\n\nTry refreshing or ask about a Nifty 200 stock."

    # Market regime questions
    if any(w in q for w in ["market", "nifty", "regime", "bull", "bear", "today"]):
        try:
            from v5.regime_detector import detect_regime
            r = detect_regime()
            regime = r.get("regime", "SIDEWAYS")
            score = r.get("score", 0)
            alloc = r.get("allocation", 0.75)
            return (f"**Market Regime: {regime}** (score {score}/6)\n"
                    f"Recommended allocation: {alloc:.0%}\n\n"
                    f"{'Market is in fear mode. Reduce equity exposure. Keep 30-50% cash.' if regime == 'BEAR' else 'Market is neutral. Normal position sizing. Watch for breakout direction.' if regime == 'SIDEWAYS' else 'Market is bullish. Full deployment. Ride the momentum.'}")
        except Exception:
            pass

    # VIX questions
    if "vix" in q:
        return ("**India VIX** measures market fear/greed.\n"
                "- VIX < 13: Very calm, full risk-on\n"
                "- VIX 13-18: Normal, standard positions\n"
                "- VIX 18-25: Elevated fear, reduce size 50%\n"
                "- VIX > 25: High fear, only 30-40% deployed\n\n"
                "Current TradePilot strategy: Automatically adjusts position sizes based on VIX level.")

    # Best stocks to buy
    if any(w in q for w in ["best", "top", "pick", "recommend", "which"]):
        try:
            scores = score_stocks_v4() if HAS_V4 else []
            top5 = sorted(scores, key=lambda x: x.get("score", 0), reverse=True)[:5]
            lines = ["**Top 5 AI Picks Right Now:**\n"]
            for i, s in enumerate(top5, 1):
                lines.append(f"{i}. **{s.get('symbol','?').replace('.NS','')}** -- Score {s.get('score',0):.0f} | Rs {s.get('price',0):.0f} ({s.get('change_pct',0):+.2f}%)")
            lines.append("\n*Scores update every 30 minutes during market hours.*")
            return "\n".join(lines)
        except Exception:
            pass

    # SIP / investment questions
    if any(w in q for w in ["sip", "invest", "long term", "mutual fund", "etf"]):
        return ("**For Long-Term Investment (3+ years):**\n\n"
                "1. **Nifty 50 Index Fund** (UTI/HDFC) -- Safest, lowest cost\n"
                "2. **Parag Parikh Flexi Cap** -- Best diversified fund\n"
                "3. **HDFC Mid-Cap Opportunities** -- Growth potential\n"
                "4. **Gold ETF (GOLDBEES)** -- 10% allocation for hedging\n\n"
                "**SIP Strategy:** Start with Rs 5,000/month across 2-3 funds. Increase annually.\n"
                "**Rule:** Never stop SIP during crashes -- that's when you get the best units.")

    # Default
    return ("I can help with:\n"
            "- **Stock analysis**: 'Tell me about RELIANCE'\n"
            "- **Market regime**: 'How is the market today?'\n"
            "- **Top picks**: 'Best stocks to buy'\n"
            "- **Investment advice**: 'Best SIP mutual funds'\n"
            "- **VIX analysis**: 'What does VIX mean?'\n\n"
            "Try asking one of these questions!")


# ═══════════════════════════ TEAM DASHBOARD ════════════════════════════
# Added 2026-05-15 (Sprint 1). Reads from docs/team/{status,activity,audit}
# and docs/sarathi/ledger. Append-only — never writes here.

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_TEAM_STATUS_DIR   = _PROJECT_ROOT / "docs" / "team" / "status"
_TEAM_ACTIVITY_DIR = _PROJECT_ROOT / "docs" / "team" / "activity"
_TEAM_AUDIT_DIR    = _PROJECT_ROOT / "docs" / "team" / "audit"
_SARATHI_LEDGER    = _PROJECT_ROOT / "docs" / "sarathi" / "ledger"

_TEAM_AGENTS = [
    "ceo", "sarathi", "architect", "alpha-hunter", "mlops-sentinel",
    "execution-analyst", "drift-watcher", "data-quality-officer",
    "competitive-intel", "knowledge-archivist",
]


def _team_read_jsonl_tail(directory: Path, n: int = 60,
                          since_ts: str | None = None,
                          filter_decision: list | None = None) -> list:
    out = []
    if not directory.exists():
        return out
    files = sorted(directory.glob("*.jsonl"))[-2:]
    for f in files:
        try:
            for line in f.read_text(encoding="utf-8").splitlines():
                if not line.strip():
                    continue
                r = json.loads(line)
                if since_ts and r.get("ts", "") <= since_ts:
                    continue
                if filter_decision and r.get("decision") not in filter_decision:
                    continue
                out.append(r)
        except Exception:
            continue
    out.sort(key=lambda r: r.get("ts", ""), reverse=True)
    return out[:n]


@app.route("/team")
def team_dashboard():
    """Permanent agent team dashboard."""
    return render_template("team.html")


@app.route("/team/sarathi")
def team_sarathi():
    """Sarathi verification ledger — drill-down on gate decisions."""
    return render_template("team_sarathi.html")


@app.route("/api/team/status")
def api_team_status():
    """Aggregate snapshot for the dashboard. One round-trip per 5-s poll."""
    agents_status = []
    for a in _TEAM_AGENTS:
        p = _TEAM_STATUS_DIR / f"{a}.json"
        if p.exists():
            try:
                agents_status.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                agents_status.append({"agent": a, "status": "unknown", "ts": None})
        else:
            agents_status.append({"agent": a, "status": "scheduled", "ts": None,
                                  "last_action": None, "next_due": "not yet bootstrapped"})

    # Recent feeds
    activity = _team_read_jsonl_tail(_TEAM_ACTIVITY_DIR, n=30)
    audit = _team_read_jsonl_tail(_TEAM_AUDIT_DIR, n=20)
    sarathi_recent = _team_read_jsonl_tail(_SARATHI_LEDGER, n=10)

    # Quick KPI counts (today)
    today = datetime.now().strftime("%Y-%m-%d")
    today_audit = []
    p_audit_today = _TEAM_AUDIT_DIR / f"{today}.jsonl"
    if p_audit_today.exists():
        for line in p_audit_today.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    today_audit.append(json.loads(line))
                except Exception:
                    pass
    kpi = {
        "today_audit_total": len(today_audit),
        "today_blocks": sum(1 for r in today_audit if r.get("decision") in ("BLOCK", "REJECT")),
        "today_warns":  sum(1 for r in today_audit if r.get("decision") == "WARN"),
        "today_passes": sum(1 for r in today_audit if r.get("decision") == "PASS"),
    }

    # Pending LLM-agent tasks (due markers — cron-written, surfaced for human)
    due_dir = _PROJECT_ROOT / "docs" / "team" / "due"
    due_markers = []
    if due_dir.exists():
        for p in sorted(due_dir.glob("*.due")):
            try:
                due_markers.append(json.loads(p.read_text(encoding="utf-8")))
            except Exception:
                pass

    return jsonify({
        "ts": datetime.now().isoformat(timespec="seconds"),
        "agents": agents_status,
        "activity": activity,
        "audit": audit,
        "sarathi_recent": sarathi_recent,
        "kpi": kpi,
        "due": due_markers,
    })


@app.route("/api/team/agent/<name>")
def api_team_agent(name):
    """Drill-down on a single agent: recent activity + audit decisions."""
    safe_name = name.replace("/", "_").replace("..", "_")
    status_p = _TEAM_STATUS_DIR / f"{safe_name}.json"
    status = json.loads(status_p.read_text(encoding="utf-8")) if status_p.exists() else None
    # Filter activity for this agent
    activity = [r for r in _team_read_jsonl_tail(_TEAM_ACTIVITY_DIR, n=200)
                if r.get("agent") == safe_name][:50]
    audit = [r for r in _team_read_jsonl_tail(_TEAM_AUDIT_DIR, n=200)
             if r.get("agent") == safe_name][:50]
    return jsonify({"agent": safe_name, "status": status,
                    "activity": activity, "audit": audit})


@app.route("/api/team/audit")
def api_team_audit():
    """Audit log with optional filtering. Used by /team/sarathi page."""
    fam = request.args.get("family")  # e.g. SARATHI-ML
    decision = request.args.get("decision")
    decision_filter = decision.split(",") if decision else None
    all_audit = _team_read_jsonl_tail(_TEAM_AUDIT_DIR, n=500,
                                       filter_decision=decision_filter)
    if fam:
        all_audit = [r for r in all_audit if r.get("rule_family") == fam]
    return jsonify({"audit": all_audit[:100], "total": len(all_audit)})


# ═══════════════════════ US MARKET MODULE ═══════════════════════
# Isolated from the India endpoints: own data layer (prototype/us/data_us.py),
# own cache namespace, own universe. Read-only for now — no US engine is running
# and no orders are placed anywhere. See docs/research/us-market/ for the
# broker, data, regulatory and methodology research behind this.

def _us():
    """Import the US data layer lazily so a failure here can never break the
    India endpoints that the live fleet depends on."""
    import sys
    from pathlib import Path as _P
    root = str(_P(__file__).resolve().parent.parent)
    if root not in sys.path:
        sys.path.insert(0, root)
    from prototype.us import data_us
    return data_us


@app.route("/api/us/universe")
def api_us_universe():
    try:
        u = _us().load_universe("nasdaq100")
        return jsonify({"ok": True, "count": len(u), "symbols": u})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/us/quotes")
def api_us_quotes():
    """Latest price + day change. `syms` query param, else the top of the universe."""
    try:
        d = _us()
        req = request.args.get("syms", "")
        syms = [x.strip().upper() for x in req.split(",") if x.strip()] or d.load_universe("nasdaq100")[:30]
        q = d.get_quotes(syms)
        movers = sorted(q.items(), key=lambda kv: kv[1]["change_pct"], reverse=True)
        return jsonify({
            "ok": True, "count": len(q), "quotes": q,
            "gainers": [{"symbol": k, **v} for k, v in movers[:8]],
            "losers":  [{"symbol": k, **v} for k, v in movers[-8:]][::-1],
            "session_ist": d.US_SESSION_IST,
        })
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


@app.route("/api/us/coverage")
def api_us_coverage():
    """Prove the 2-3yr data claim rather than asserting it — powers the UI panel."""
    try:
        d = _us()
        yrs = int(request.args.get("years", "3"))
        syms = d.load_universe("nasdaq100")[:int(request.args.get("n", "25"))]
        return jsonify({"ok": True, **d.history_stats(syms, years=yrs)})
    except Exception as e:
        return jsonify({"ok": False, "error": f"{type(e).__name__}: {e}"}), 500


# ═══════════════════════ MOBILE FLEET VIEW ═══════════════════════
# A phone-sized, self-contained view of the whole engine fleet. Deliberately its own
# route rather than a tab inside index.html: that page is ~7,000 lines built for a
# desktop grid, and this needs to render on a phone and be showable to someone in
# ten seconds. Serves live data on every request — no build step, no snapshot.

@app.route("/portfolio")
def portfolio_view():
    """Soumya's whole book in one place — settled trades, swing, carried holds.

    Rebuilt on each request from the engine artifacts rather than cached: a stale
    portfolio is the one kind that is actively misleading, and the build takes well
    under a second. Costs are corrected for engines that never booked any, and
    VOID sessions are excluded — see scripts/portfolio.py for both.
    """
    import sys as _s
    from pathlib import Path as _P
    _r = _P(__file__).resolve().parent.parent
    if str(_r / "scripts") not in _s.path:
        _s.path.insert(0, str(_r / "scripts"))
    try:
        import portfolio as _pf
        import importlib
        importlib.reload(_pf)
        p = _pf.build()
    except Exception as e:
        return f"<h3>Portfolio unavailable</h3><p>{type(e).__name__}: {e}</p>", 500

    holdings = []
    for e in p["engines"]:
        if e["status"] != "active":
            continue
        for h in e["open_positions"]:
            try:
                qty = float(h.get("qty") or 0)
                px = float(h.get("entry_price") or 0)
            except (TypeError, ValueError):
                continue
            holdings.append({
                "symbol": h.get("symbol", "?"), "engine": e["engine"],
                "pool": h.get("pool", "?"), "qty": int(qty),
                "entry_price": px, "value": abs(qty * px),
                "since": str(h.get("entry_date") or h.get("entry_time") or "")[:10] or "-",
            })
    holdings.sort(key=lambda x: -x["value"])
    return render_template("portfolio.html", p=p, holdings=holdings)


@app.route("/fleet")
def fleet_view():
    import json as _j, glob as _g, os as _os
    from datetime import datetime as _dt
    from pathlib import Path as _P

    root = _P(__file__).resolve().parent.parent
    today = _dt.now().strftime("%Y-%m-%d")
    CPT = 14.30   # v5's measured cost per trade — used to correct engines that book none

    engines = []
    for f in sorted(_g.glob(str(root / "docs" / "paper-trades" / "*" / f"{today}.json"))):
        name = _os.path.basename(_os.path.dirname(f))
        try:
            d = _j.load(open(f))
        except Exception:
            continue
        sm = d.get("summary") or {}
        pools = d.get("pools") or {}
        npos = sum(len(p.get("positions") or []) for p in pools.values())
        gross = sm.get("total_pnl") or 0
        net = sm.get("total_pnl_net")
        cost = sm.get("total_cost") or 0
        trades = sm.get("trades") or 0
        wins = sm.get("wins") or 0
        books = cost > 0
        true = net if (books and net is not None) else (gross - trades * CPT if not books else gross)
        cap = d.get("total_capital") or 0
        if cap <= 0:
            continue                      # US module and empty state files
        tier = "1L" if 90000 <= cap <= 110000 else "10L"
        engines.append({"name": name, "cap": cap, "tier": tier, "pos": npos,
                        "trades": trades, "wr": round(wins / trades * 100) if trades else 0,
                        "net": round(true), "books": books})
    engines.sort(key=lambda e: -e["net"])
    fleet = {"n": len(engines),
             "pos": sum(e["pos"] for e in engines),
             "trades": sum(e["trades"] for e in engines),
             "net": round(sum(e["net"] for e in engines)),
             "green": sum(1 for e in engines if e["net"] > 0)}
    return render_template("fleet.html", engines=engines, fleet=fleet,
                           stamp=_dt.now().strftime("%d %b %Y, %H:%M IST"),
                           mx=max([abs(e["net"]) for e in engines] or [1]))


# ═══════════════════════ KITE CONNECT LOGIN CALLBACK ═══════════════════════
# Zerodha's login flow redirects here with ?request_token=... after you authenticate.
# The request_token is short-lived and must be exchanged for an access_token, which
# is then valid ONLY for the rest of that trading day. Catching the redirect here
# means you never copy-paste a token out of a URL bar.
#
# SECURITY: this endpoint writes a credential to .env. It is bound to 127.0.0.1 only
# (see the app.run host), so it is not reachable from the network.

@app.route("/kite/callback")
def kite_callback():
    """Exchange Kite's request_token for a daily access_token and persist it."""
    from pathlib import Path as _P
    req_tok = request.args.get("request_token")
    status = request.args.get("status")
    if not req_tok:
        return (f"<h3>Kite callback: no request_token</h3>"
                f"<p>status={status}. Start the login at "
                f"<a href='/kite/login'>/kite/login</a>.</p>"), 400

    root = _P(__file__).resolve().parent.parent
    import sys as _sys
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    from prototype.v5 import kite_broker as kb

    c = kb.credentials()
    if not (c["api_key"] and c["api_secret"]):
        return ("<h3>Missing KITE_API_KEY / KITE_API_SECRET in .env</h3>"
                "<p>Add them, restart Flask, and retry.</p>"), 400
    if not kb.sdk_available():
        return "<h3>kiteconnect not installed</h3><p>pip install kiteconnect</p>", 400

    try:
        from kiteconnect import KiteConnect
        k = KiteConnect(api_key=c["api_key"])
        data = k.generate_session(req_tok, api_secret=c["api_secret"])
        access = data["access_token"]
    except Exception as e:
        return f"<h3>Token exchange failed</h3><pre>{type(e).__name__}: {e}</pre>", 400

    # persist to .env, replacing any previous token (it changes daily)
    envf = root / ".env"
    lines = envf.read_text().splitlines() if envf.exists() else []
    lines = [l for l in lines if not l.startswith("KITE_ACCESS_TOKEN=")]
    lines.append(f"KITE_ACCESS_TOKEN={access}")
    envf.write_text("\n".join(lines) + "\n")

    return (f"<h3>Kite connected</h3>"
            f"<p>Access token saved to .env. It expires at end of today's trading "
            f"session — re-run <a href='/kite/login'>/kite/login</a> tomorrow.</p>"
            f"<p>Verify with: <code>python3 scripts/kite-check.py</code></p>")


@app.route("/kite/login")
def kite_login():
    """Redirect into Kite's login. Bookmark this — it is the daily ritual."""
    import sys as _sys
    from pathlib import Path as _P
    root = _P(__file__).resolve().parent.parent
    if str(root) not in _sys.path:
        _sys.path.insert(0, str(root))
    from prototype.v5 import kite_broker as kb
    c = kb.credentials()
    if not c["api_key"]:
        return "<h3>KITE_API_KEY missing from .env</h3>", 400
    url = f"https://kite.zerodha.com/connect/login?v=3&api_key={c['api_key']}"
    return f'<h3>Kite login</h3><p><a href="{url}">Click to authenticate with Zerodha</a></p>'


@app.route("/api/us/engine")
def api_us_engine():
    """US paper engine state — positions, P&L, closed trades. Reads the engine's
    own state file; returns running=False when it has never run rather than
    inventing an empty portfolio."""
    import json as _j
    from pathlib import Path as _P
    eng = os.environ.get("US_ENGINE_NAME", "us_v1")
    f = _P(__file__).resolve().parent.parent / "docs" / "paper-trades" / eng / "positions_active.json"
    if not f.exists():
        return jsonify({"ok": True, "has_run": False, "engine": eng,
                        "note": "engine has never run"})
    try:
        st = _j.loads(f.read_text())
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500
    pos = st.get("positions", {}) or {}
    return jsonify({
        "ok": True, "has_run": True, "engine": eng,
        "summary": st.get("summary", {}),
        "updated": st.get("updated"),
        "positions": [{"symbol": k, **v} for k, v in pos.items()],
        "closed": (st.get("closed") or [])[-20:],
        "lane": "long-only cash (RBI: no margin, no FX)",
    })


@app.route("/api/us/status")
def api_us_status():
    """Module status. Deliberately explicit that nothing is live — this panel is
    how the UI avoids implying a US engine is trading when none exists."""
    from datetime import datetime as _dt
    try:
        d = _us()
        n = len(d.load_universe("nasdaq100"))
    except Exception:
        n = 0
    return jsonify({
        "ok": True,
        "phase": "research + data shell",
        "engine_running": False,
        "orders_enabled": False,
        "broker": None,
        "paper_broker_candidate": "Alpaca (free paper API, no KYC) — not yet integrated",
        "data_source": "yfinance (v1, unofficial — see docs/research/us-market/02-data-sources.md)",
        "universe_size": n,
        "session_ist": "19:00-01:30 IST (EDT) / 20:00-02:30 IST (EST)",
        "compliance_note": "Long-only cash only. RBI bars LRS remittance for FX trading and for "
                           "margin/margin calls. Day-trading frequency under LRS is an unresolved "
                           "gray zone — see docs/research/us-market/04-regulatory-lrs-tax.md",
        "as_of": _dt.now().strftime("%H:%M:%S"),
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  TradePilot Prototype")
    print("  AI-Powered Trading Platform for Indian Markets")
    print("=" * 60)

    # Check if model exists
    model_path = os.path.join(os.path.dirname(__file__), "models", "xgb_scorer.pkl")
    if not os.path.exists(model_path):
        print("\nNo trained model found. Training now...")
        print("This will download stock data and train the AI model.")
        print("First run takes 2-5 minutes.\n")

        from data_engine import download_stock_data
        data = download_stock_data()
        train_model(data)

    print("\nStarting server at http://localhost:5050")
    print("Open your browser to http://localhost:5050\n")

    app.run(host="127.0.0.1", port=5050, debug=False, threaded=True)
