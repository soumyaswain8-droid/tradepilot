"""
floor_live — reconstruct the agent floor's live state for the visual console.

DESIGN CONSTRAINT (Soumya, 2026-08-26): the floor is RUNNING with real data being
collected. Restarting it to add a state feed would reset every agent's tenure, open
a data gap, and cost part of the session. So this reads only what the floor already
emits — its log and its escalation journal — plus its own cheap live quotes.

Nothing here writes. Nothing here can crash the floor.

    log  ->  roster, levels, swaps, gaps, tick rate
    jsonl ->  the escalation stream
    quote ->  where each agent's price sits RIGHT NOW against its levels
    sweep ->  the wider market the scouts are scanning (the radar)

Phase 2 will have the floor publish structured state directly, which gives exact
internals (per-agent tick counts, cooldown timers) instead of this reconstruction —
but that needs a restart, so it waits for a session boundary.
"""
from __future__ import annotations

import json, re, time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# Flask runs with prototype/ as its cwd, so "prototype.v4" does not resolve there
# while "v4" does; run from the repo root it is the other way round. Both paths are
# put on sys.path and every import below tries both — the first version failed
# silently inside a broad except and the console rendered an empty board and no live
# prices, which looked like a quiet market rather than a broken import.
import sys as _sys
for _p in (str(ROOT), str(ROOT / "prototype")):
    if _p not in _sys.path:
        _sys.path.insert(0, _p)
LOGS = ROOT / "logs"
ESC = ROOT / "docs" / "sarathi" / "knowledge" / "escalations"

_CACHE = {"board": None, "board_at": 0, "quotes": None, "quotes_at": 0}
BOARD_TTL = 25.0          # the scouts themselves only re-rank every 120s
QUOTE_TTL = 2.0           # 20 symbols per call; 0.5 req/s is well inside the limit

RE_SEED = re.compile(r"^\s{4}(\S+)\s+\[(\d+) scouts,\s*([\d.]+)\]\s*(.*)$")
RE_ESC = re.compile(r"^\s*>>\s*(\d\d:\d\d:\d\d)\s+(\S+)\s+(\S+)\s+([\d.]+)\s+(.*)$")
RE_SWAP = re.compile(r"(\d\d:\d\d:\d\d) REASSIGN (\S+) \(([\d.]+), (\d+) scouts\)"
                     r" -> (\S+) \(([\d.]+), (\d+) scouts\) — (.*)$")
RE_BEAT = re.compile(r"\[(\d\d:\d\d:\d\d)\] ([\d,]+) ticks \| (\d+) escalations \| "
                     r"(\d+) reassignments \| (\d+) in position \| (\d+) data gaps")
RE_GAP_O = re.compile(r"(\d\d:\d\d:\d\d) DATA GAP OPENED \(([A-Z_]+)\): (.*)$")
RE_GAP_C = re.compile(r"(\d\d:\d\d:\d\d) DATA GAP CLOSED after ([\d.]+)s")
RE_LIVE = re.compile(r"STREAM LIVE — (\d+) agents.*\((\d\d:\d\d:\d\d)\)")
# A run BEGINS at the seeding banner, not at STREAM LIVE — the floor seeds all twenty
# agents and prints them BEFORE the socket connects. Resetting on STREAM LIVE threw
# away every seed line and left a roster containing only stocks that had been swapped
# in: 5 agents where there were 20.
RE_SEEDBANNER = re.compile(r"seeding theses for (\d+) agents")
RE_NEAR = re.compile(r"\((\d+) near-misses, closest: (\S+) short by ([\d.]+)\)")


def _today():
    return datetime.now().strftime("%Y-%m-%d")


def parse_log(day=None):
    """Replay the floor's narration into current state.

    The roster is REPLAYED rather than read: agents are seeded at start-up and then
    moved by REASSIGN lines, so the live twenty is the seed list with every swap
    applied in order. Reading only the seed lines would show a roster that stopped
    being true at the first reassignment.
    """
    day = day or _today()
    f = LOGS / f"agent-floor-{day}.log"
    st = {"roster": {}, "swaps": [], "gaps": [], "beats": [], "near": None,
          "stream_live_at": None, "agents_n": 0, "restarts": 0}
    if not f.exists():
        return st
    for line in f.read_text(errors="ignore").splitlines():
        m = RE_SEEDBANNER.search(line)
        if m:
            # a new run starts here: the previous roster belongs to a dead process
            st["roster"] = {}
            st["agents_n"] = int(m.group(1))
            st["restarts"] += 1
            continue
        m = RE_LIVE.search(line)
        if m:
            st["stream_live_at"] = m.group(2)
            for a in st["roster"].values():
                a.setdefault("since", m.group(2))
            continue
        m = RE_SEED.match(line)
        if m and "=" in m.group(4):
            lv = {}
            for kv in m.group(4).split():
                if "=" in kv:
                    k, v = kv.split("=", 1)
                    try:
                        lv[k] = float(v)
                    except ValueError:
                        pass
            st["roster"][m.group(1)] = {
                "symbol": m.group(1), "agree": int(m.group(2)),
                "score": float(m.group(3)), "levels": lv,
                "since": st["stream_live_at"], "escalations": 0}
            continue
        m = RE_SWAP.search(line)
        if m:
            out_s, in_s = m.group(2), m.group(5)
            st["swaps"].append({"at": m.group(1), "out": out_s,
                                "out_score": float(m.group(3)),
                                "out_agree": int(m.group(4)), "in": in_s,
                                "in_score": float(m.group(6)),
                                "agree": int(m.group(7)), "why": m.group(8)})
            st["roster"].pop(out_s, None)
            st["roster"][in_s] = {"symbol": in_s, "agree": int(m.group(7)),
                                  "score": float(m.group(6)), "levels": {},
                                  "since": m.group(1), "escalations": 0,
                                  "just_swapped": True}
            continue
        m = RE_BEAT.search(line)
        if m:
            st["beats"].append({"at": m.group(1),
                                "ticks": int(m.group(2).replace(",", "")),
                                "esc": int(m.group(3)), "swaps": int(m.group(4)),
                                "pos": int(m.group(5)), "gaps": int(m.group(6))})
            continue
        m = RE_GAP_O.search(line)
        if m:
            st["gaps"].append({"from": m.group(1), "kind": m.group(2),
                               "detail": m.group(3)[:70], "open": True})
            continue
        m = RE_GAP_C.search(line)
        if m and st["gaps"]:
            st["gaps"][-1].update({"to": m.group(1), "seconds": float(m.group(2)),
                                   "open": False})
            continue
        m = RE_NEAR.search(line)
        if m:
            st["near"] = {"count": int(m.group(1)), "closest": m.group(2),
                          "short_by": float(m.group(3))}
    return st


def stream(day=None, limit=60):
    """The most recent escalations, newest last."""
    day = day or _today()
    f = ESC / f"{day}.jsonl"
    if not f.exists():
        return []
    lines = f.read_text(errors="ignore").splitlines()[-limit:]
    out = []
    for l in lines:
        try:
            e = json.loads(l)
            out.append({"at": e.get("at"), "symbol": e.get("symbol"),
                        "trigger": e.get("trigger"), "ltp": e.get("ltp"),
                        "detail": e.get("detail", "")[:80]})
        except Exception:
            pass
    return out


def _kite():
    try:
        from prototype.v4 import kite_data as kd
    except Exception:
        from v4 import kite_data as kd
    return kd


def _scouts():
    try:
        from prototype.agents.scouts import ScoutTeam
    except Exception:
        from agents.scouts import ScoutTeam
    return ScoutTeam


def _quotes(symbols):
    now = time.time()
    if _CACHE["quotes"] and now - _CACHE["quotes_at"] < QUOTE_TTL:
        return _CACHE["quotes"]
    try:
        kd = _kite()
        q = kd.client().quote([f"NSE:{s}" for s in symbols])
        _CACHE["quotes"], _CACHE["quotes_at"] = q, now
        return q
    except Exception as e:
        _CACHE["quote_err"] = str(e)[:120]
        return _CACHE["quotes"] or {}


def board():
    """The scouts' current ranking. Cached — the floor only re-ranks every 120s, so
    sweeping faster than that shows motion that isn't really there."""
    now = time.time()
    if _CACHE["board"] and now - _CACHE["board_at"] < BOARD_TTL:
        return _CACHE["board"]
    try:
        ScoutTeam = _scouts()
        t = ScoutTeam(verbose=False)
        b = {"rows": t.scan(top=40), "universe": len(t.universe),
             "screened": len(t.sweep()), "at": datetime.now().strftime("%H:%M:%S")}
        _CACHE["board"], _CACHE["board_at"] = b, now
        return b
    except Exception as e:
        return _CACHE["board"] or {"rows": [], "universe": 0, "screened": 0,
                                   "error": str(e)[:80]}


def snapshot(day=None, with_board=True):
    """Everything the console needs, in one payload."""
    day = day or _today()
    st = parse_log(day)
    ev = stream(day)
    for e in ev:
        if e["symbol"] in st["roster"]:
            st["roster"][e["symbol"]]["escalations"] += 1

    # tick rate from the last two heartbeats — the floor's pulse
    beats = st["beats"]
    rate = None
    if len(beats) >= 2:
        dt_ = 30.0
        rate = max(0.0, (beats[-1]["ticks"] - beats[-2]["ticks"]) / dt_)
    last = beats[-1] if beats else {}

    syms = list(st["roster"])
    q = _quotes(syms) if syms else {}
    agents = []
    for s, a in st["roster"].items():
        d = q.get(f"NSE:{s}") or {}
        ltp = float(d.get("last_price") or 0)
        nearest, ndist = None, None
        for name, lvl in (a.get("levels") or {}).items():
            if not lvl or not ltp:
                continue
            bps = abs(ltp - lvl) / lvl * 10000
            if ndist is None or bps < ndist:
                nearest, ndist = name, bps
        ohlc = d.get("ohlc") or {}
        prev = float(ohlc.get("close") or 0)
        agents.append({**a, "ltp": ltp,
                       "chg_pct": round((ltp / prev - 1) * 100, 2) if prev and ltp else None,
                       "nearest": nearest,
                       "dist_bps": round(ndist, 1) if ndist is not None else None,
                       # 8 bps is the floor's own LEVEL_TOUCH threshold
                       "armed": (ndist is not None and ndist <= 25)})
    agents.sort(key=lambda a: (a["dist_bps"] is None, a["dist_bps"]))

    b = board() if with_board else (_CACHE["board"] or {})
    open_gap = any(g.get("open") for g in st["gaps"])
    return {
        "day": day,
        "now": datetime.now().strftime("%H:%M:%S"),
        "session": {
            "running": bool(beats) and not open_gap,
            "ticks": last.get("ticks", 0),
            "tick_rate": round(rate, 1) if rate is not None else None,
            "escalations": last.get("esc", len(ev)),
            "swaps": last.get("swaps", len(st["swaps"])),
            "positions": last.get("pos", 0),
            "gaps": len(st["gaps"]),
            "blind_open": open_gap,
            "restarts": max(0, st["restarts"] - 1),
            "last_beat": last.get("at"),
        },
        "funnel": {
            "universe": b.get("universe", 0),
            "screened": b.get("screened", 0),
            "board": len(b.get("rows", [])),
            "agents": len(agents),
            "positions": last.get("pos", 0),
        },
        "agents": agents,
        "board": b.get("rows", [])[:40],
        "board_at": b.get("at"),
        "stream": ev[-40:],
        "swaps": st["swaps"][-12:],
        "gaps": st["gaps"][-6:],
        "near": st["near"],
        "errors": {k: v for k, v in
                   {"quotes": _CACHE.get("quote_err"),
                    "board": b.get("error")}.items() if v},
    }
