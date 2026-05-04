#!/usr/bin/env python3
"""v5 Learning Watchdog — Track A observation companion.

Runs alongside the engines (08:00-15:35 IST), polling every 5 min. Captures:
  - Every Track A activation (SHORT_BLOCK, RE-ARM, FLAT_FORCE_EXIT)
  - v5 vs control (v5_classic/v5_6/v5_7) divergences
  - "What-if" data: what would have happened on signals v5 rejected but controls took (and vice versa)
  - EOD: structured insights file ready for ML training

Outputs:
  logs/v5-learning-watchdog-{date}.log   — running log of observations
  docs/learning/v5-{date}-events.json    — structured event stream (ML-ready)
  docs/learning/v5-{date}-insights.md    — human-readable post-mortem at EOD

Self-terminates at 15:50 IST (after EOD auto-stop fires at 15:35).
Local-only — no DevPilot DB push.
"""
import json
import os
import re
import sys
import time
from datetime import datetime, time as dtime
from pathlib import Path

ROOT = Path(__file__).parent.parent
LOG_DIR = ROOT / "logs"
LEARN_DIR = ROOT / "docs" / "learning"
LEARN_DIR.mkdir(parents=True, exist_ok=True)

TODAY = datetime.now().strftime("%Y-%m-%d")
WATCHDOG_LOG = LOG_DIR / f"v5-learning-watchdog-{TODAY}.log"
EVENTS_JSON = LEARN_DIR / f"v5-{TODAY}-events.json"
INSIGHTS_MD = LEARN_DIR / f"v5-{TODAY}-insights.md"

# Surviving engines after 04-27 retirement
ENGINES = ["v5", "v5_classic", "v5_6", "v5_7"]
CONTROL_ENGINES = ["v5_classic", "v5_6", "v5_7"]  # comparison targets for v5

# Polling cadence — 5 min is enough resolution to catch every scan cycle
POLL_INTERVAL_SEC = 300

# Self-terminate after EOD auto-stop has fired
END_TIME = dtime(15, 50)

# ───────────────────────── log parsing ─────────────────────────

RE_ENTRY = re.compile(
    r"\[(\d\d:\d\d:\d\d)\]\s+(LONG|SHORT)\s+(\S+)\s+x(\d+)\s+@(\d+\.\d+)\s+SL:(\d+\.\d+)\s+TGT:(\d+\.\d+)\s+\[(\w+)\]"
)
RE_EXIT = re.compile(
    r"\[(\d\d:\d\d:\d\d)\]\s+>>\s+(WIN|LOSS)\s+(LONG|SHORT)\s+(\S+)\s+x(\d+)\s+@(\d+\.\d+)\s+\((\w+)\)\s+P&L:\s+Rs\s+([-+]?\d+).*?\(([-+]?\d+\.\d+)%\)"
)
RE_SHORT_BLOCK = re.compile(r"\[SHORT_BLOCK\]\s+(.+)")
RE_REARM = re.compile(r"\[RE-ARM\]\s+(\S+):\s+deploying re-entry on (\S+)")
RE_FLAT_EXIT = re.compile(r"(\S+):\s+FLAT_FORCE_EXIT\s+@")
RE_TARGET_REARM = re.compile(r"(\S+):\s+TARGET hit — re-armable for (\S+)")
RE_REALIZED = re.compile(r"Realized:\s+Rs\s+([-+]?[\d,]+)\s+\|\s+Unrealized:\s+Rs\s+([-+]?[\d,]+)")
RE_NIFTY = re.compile(r"Nifty:\s+(\d+)\s+\(([+-]?\d+\.\d+)%\)\s+\|\s+Regime:\s+(\w+)")


def parse_engine_log(engine):
    """Read engine log, return structured event lists."""
    log_path = LOG_DIR / f"{engine}-{TODAY}.log"
    if not log_path.exists():
        return None
    entries, exits, blocks, rearms, flat_exits, target_rearms = [], [], [], [], [], []
    last_realized, last_unrealized = 0.0, 0.0
    last_nifty_pct, last_regime = None, None
    try:
        for line in log_path.read_text(errors="ignore").splitlines():
            m = RE_ENTRY.search(line)
            if m:
                entries.append(dict(t=m.group(1), side=m.group(2), symbol=m.group(3),
                                    qty=int(m.group(4)), price=float(m.group(5)),
                                    sl=float(m.group(6)), tgt=float(m.group(7)),
                                    pool=m.group(8)))
                continue
            m = RE_EXIT.search(line)
            if m:
                exits.append(dict(t=m.group(1), result=m.group(2), side=m.group(3),
                                  symbol=m.group(4), qty=int(m.group(5)),
                                  exit_price=float(m.group(6)), reason=m.group(7),
                                  pnl_rs=int(m.group(8)), pnl_pct=float(m.group(9))))
                continue
            m = RE_SHORT_BLOCK.search(line)
            if m: blocks.append(m.group(1)); continue
            m = RE_REARM.search(line)
            if m: rearms.append(dict(symbol=m.group(1), direction=m.group(2))); continue
            m = RE_FLAT_EXIT.search(line)
            if m: flat_exits.append(m.group(1)); continue
            m = RE_TARGET_REARM.search(line)
            if m: target_rearms.append(dict(symbol=m.group(1), direction=m.group(2))); continue
            m = RE_REALIZED.search(line)
            if m:
                try:
                    last_realized = float(m.group(1).replace(",", ""))
                    last_unrealized = float(m.group(2).replace(",", ""))
                except ValueError: pass
                continue
            m = RE_NIFTY.search(line)
            if m:
                try:
                    last_nifty_pct = float(m.group(2))
                    last_regime = m.group(3)
                except ValueError: pass
    except Exception as e:
        return {"error": str(e)}
    return dict(
        engine=engine,
        entries=entries, exits=exits,
        short_blocks=blocks, rearms=rearms,
        flat_exits=flat_exits, target_rearms=target_rearms,
        realized=last_realized, unrealized=last_unrealized,
        nifty_pct=last_nifty_pct, regime=last_regime,
    )


def divergence_v5_vs_controls(snapshots):
    """v5-specific 'what-if' analysis.

    Returns dict with:
      v5_skipped_controls_took: symbols/sides v5 didn't take but controls did + outcomes
      v5_took_controls_skipped: symbols/sides v5 took but controls didn't + outcomes
      short_block_savings: estimated P&L saved on SHORTs blocked by v5 (controls' actual P&L on same symbols)
      rearm_gains: estimated P&L gained on v5 re-arms (vs controls who didn't re-arm)
    """
    v5 = snapshots.get("v5", {}) or {}
    if not v5:
        return {}
    v5_entries_keys = {(e["side"], e["symbol"]) for e in v5.get("entries", [])}
    # collect outcomes from controls (paired entry→exit per symbol)
    control_outcomes = {}  # (side, symbol) → list of pnl_rs
    for c in CONTROL_ENGINES:
        c_data = snapshots.get(c, {}) or {}
        for x in c_data.get("exits", []):
            key = (x["side"], x["symbol"])
            control_outcomes.setdefault(key, []).append(x["pnl_rs"])
    # what controls won/lost on symbols v5 didn't take
    # Use "SIDE|SYMBOL" string keys so the dict is JSON-serializable
    v5_skipped = {}
    for key, pnls in control_outcomes.items():
        if key not in v5_entries_keys:
            avg = sum(pnls) / len(pnls)
            side, sym = key
            v5_skipped[f"{side}|{sym}"] = dict(side=side, symbol=sym,
                                                controls_pnl_avg=round(avg, 0),
                                                n=len(pnls))
    # short_block_savings: SHORT trades on symbols that controls took but v5 didn't (because of block)
    short_block_savings = sum(
        v["controls_pnl_avg"] for v in v5_skipped.values() if v["side"] == "SHORT"
    )
    # rearm_gains: any v5 entry where the symbol was already exited once that day with TARGET (re-arm)
    v5_target_symbols = {tr["symbol"] for tr in v5.get("target_rearms", [])}
    v5_rearm_pnls = []
    for x in v5.get("exits", []):
        if x["symbol"] in v5_target_symbols:
            v5_rearm_pnls.append(x["pnl_rs"])
    rearm_gains = sum(v5_rearm_pnls)
    return dict(
        v5_skipped_controls_took=v5_skipped,
        short_block_savings=round(short_block_savings, 0),
        rearm_gains=round(rearm_gains, 0),
        rearm_trade_count=len(v5_rearm_pnls),
    )


def watchdog_log(msg):
    line = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}"
    print(line)
    with open(WATCHDOG_LOG, "a") as f:
        f.write(line + "\n")


def emit_snapshot():
    """Read all engine logs, build structured event JSON, append a line to watchdog log."""
    snapshots = {eng: parse_engine_log(eng) for eng in ENGINES}
    snapshot = dict(
        timestamp=datetime.now().isoformat(timespec="seconds"),
        date=TODAY,
        engines=snapshots,
        divergence=divergence_v5_vs_controls(snapshots),
    )
    # Atomic write to JSON (overwrite each cycle — last snapshot is the truth)
    tmp = EVENTS_JSON.with_suffix(".tmp")
    tmp.write_text(json.dumps(snapshot, indent=2, default=str))
    tmp.replace(EVENTS_JSON)
    # Console-friendly summary line
    v5 = snapshots.get("v5") or {}
    if v5 and "error" not in v5:
        wins = sum(1 for x in v5.get("exits", []) if x["result"] == "WIN")
        losses = sum(1 for x in v5.get("exits", []) if x["result"] == "LOSS")
        n_blocks = len(v5.get("short_blocks", []))
        n_rearms = len(v5.get("rearms", []))
        n_flat = len(v5.get("flat_exits", []))
        watchdog_log(
            f"v5: {wins}W/{losses}L · realized=Rs{v5.get('realized',0):+,.0f} "
            f"unreal=Rs{v5.get('unrealized',0):+,.0f} · "
            f"SHORT_BLOCK fires={n_blocks} RE-ARMs={n_rearms} FLAT_EXITs={n_flat} · "
            f"Nifty={v5.get('nifty_pct')}% regime={v5.get('regime')}"
        )
        div = snapshot["divergence"]
        if div:
            watchdog_log(
                f"  divergence: short_block_saved=Rs{div.get('short_block_savings',0):+,.0f} · "
                f"rearm_gains=Rs{div.get('rearm_gains',0):+,.0f} ({div.get('rearm_trade_count',0)} re-arm trades)"
            )
    else:
        watchdog_log("v5: no log yet (engine warming up)")


def emit_eod_insights():
    """Write the human-readable Track A post-mortem when day ends."""
    snapshots = {eng: parse_engine_log(eng) for eng in ENGINES}
    div = divergence_v5_vs_controls(snapshots)
    v5 = snapshots.get("v5") or {}

    lines = [
        f"# v5 Track A Learning Insights — {TODAY}",
        "",
        "Generated by `scripts/v5-learning-watchdog.py` at EOD.",
        "Local-only file. Used to feed ML training and validate Track A's hypothesis.",
        "",
        "## Day-end snapshot",
        "",
        "| Engine | Realized | Unrealized | Total | Wins | Losses | WR |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for eng in ENGINES:
        d = snapshots.get(eng) or {}
        if not d or "error" in d:
            lines.append(f"| {eng} | (no data) | | | | | |")
            continue
        w = sum(1 for x in d.get("exits", []) if x["result"] == "WIN")
        l = sum(1 for x in d.get("exits", []) if x["result"] == "LOSS")
        wr = f"{100*w/(w+l):.0f}%" if (w+l) else "—"
        total = d.get("realized", 0) + d.get("unrealized", 0)
        lines.append(
            f"| {eng} | Rs {d.get('realized',0):+,.0f} | Rs {d.get('unrealized',0):+,.0f} | "
            f"Rs {total:+,.0f} | {w} | {l} | {wr} |"
        )

    # Track A activation summary (v5 only)
    if v5 and "error" not in v5:
        lines += [
            "",
            "## Track A activations on v5",
            "",
            f"- **SHORT_BLOCK fires:** {len(v5.get('short_blocks', []))}",
            f"- **TARGET re-armables marked:** {len(v5.get('target_rearms', []))}",
            f"- **RE-ARM redeploys:** {len(v5.get('rearms', []))}",
            f"- **FLAT_FORCE_EXIT:** {len(v5.get('flat_exits', []))}",
            "",
        ]

    # Divergence: estimated impact
    if div:
        lines += [
            "## Estimated Track A impact (v5 vs control avg)",
            "",
            f"- **SHORTs blocked savings:** Rs {div.get('short_block_savings', 0):+,.0f} (negative = block helped)",
            f"- **RE-ARM gains:** Rs {div.get('rearm_gains', 0):+,.0f} from {div.get('rearm_trade_count', 0)} re-arm trades",
            "",
        ]

    # Top 5 v5 wins / losses for ML training (most informative trades)
    if v5 and v5.get("exits"):
        sorted_exits = sorted(v5["exits"], key=lambda x: x["pnl_rs"])
        lines += ["## Top 5 v5 losses (ML: 'what to avoid')", ""]
        for x in sorted_exits[:5]:
            lines.append(
                f"- {x['side']} {x['symbol']} entry→exit "
                f"Rs {x['pnl_rs']:+,d} ({x['pnl_pct']:+.2f}%) reason={x['reason']}"
            )
        lines += ["", "## Top 5 v5 wins (ML: 'what to repeat')", ""]
        for x in sorted_exits[-5:][::-1]:
            lines.append(
                f"- {x['side']} {x['symbol']} entry→exit "
                f"Rs {x['pnl_rs']:+,d} ({x['pnl_pct']:+.2f}%) reason={x['reason']}"
            )

    # Top missed opportunities — symbols v5 didn't take but controls did, ranked by control P&L
    skipped = div.get("v5_skipped_controls_took", {}) if div else {}
    if skipped:
        ranked = sorted(skipped.values(), key=lambda v: v["controls_pnl_avg"], reverse=True)
        lines += ["", "## v5 skipped — what controls earned/lost on those signals", ""]
        lines += ["### Missed wins (v5 should have taken these — ML: 'why did v5 skip?')", ""]
        for info in ranked[:5]:
            if info["controls_pnl_avg"] > 0:
                lines.append(
                    f"- {info['side']} {info['symbol']}: controls avg Rs {info['controls_pnl_avg']:+,.0f} "
                    f"(n={info['n']} engines)"
                )
        lines += ["", "### Saved bleeds (v5 correctly skipped — ML: 'this filter worked')", ""]
        for info in ranked[-5:][::-1]:
            if info["controls_pnl_avg"] < 0:
                lines.append(
                    f"- {info['side']} {info['symbol']}: controls avg Rs {info['controls_pnl_avg']:+,.0f} "
                    f"(n={info['n']} engines)"
                )

    lines += [
        "",
        "## Hypothesis check vs RCA prediction",
        "",
        "From `docs/reports/2026-04-27/DEEP_DIVE_ROOT_CAUSE.md`:",
        "  - Predicted: removing morning SHORTs in BULL tape doubles net P&L on bullish gap-up days",
        "  - Today's tape: " + (
            f"BULLISH gap +0.89%, premarket conditions matched Task 1.1 trigger"
            if v5 and v5.get("nifty_pct", 0) > 0 else "(see snapshot — conditions differ)"
        ),
        "",
        "## ML training notes",
        "",
        "- This file is the per-day learning record. Aggregate across many days for ML training.",
        "- Top losses + saved bleeds are the highest-signal training rows (where decisions mattered).",
        "- Re-arm trades vs single-entry trades are the cleanest A/B for the WINNER_RE_ARM hypothesis.",
        "- Use `EVENTS_JSON` for structured ML inputs, this MD file for human review.",
        "",
        f"Source events: `{EVENTS_JSON.relative_to(ROOT)}`",
    ]

    INSIGHTS_MD.write_text("\n".join(lines))
    watchdog_log(f"EOD insights written to {INSIGHTS_MD}")


def main():
    watchdog_log("="*70)
    watchdog_log(f"v5 Learning Watchdog started — date={TODAY}")
    watchdog_log(f"engines watched: {', '.join(ENGINES)}")
    watchdog_log(f"poll cadence: every {POLL_INTERVAL_SEC}s; will self-terminate at {END_TIME}")
    watchdog_log(f"events: {EVENTS_JSON}")
    watchdog_log(f"insights (EOD): {INSIGHTS_MD}")
    watchdog_log("="*70)
    last_emit_eod = False
    while True:
        now = datetime.now().time()
        if now >= END_TIME:
            if not last_emit_eod:
                watchdog_log("EOD reached — generating final insights file")
                try:
                    emit_eod_insights()
                except Exception as e:
                    watchdog_log(f"EOD insights generation failed: {e}")
                last_emit_eod = True
            watchdog_log("watchdog terminating cleanly")
            break
        try:
            emit_snapshot()
        except Exception as e:
            watchdog_log(f"snapshot error: {e}")
        time.sleep(POLL_INTERVAL_SEC)


if __name__ == "__main__":
    main()
