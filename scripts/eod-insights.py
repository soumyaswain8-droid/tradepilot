#!/usr/bin/env python3
"""EOD insights watchdog — runs after market close.

Reads today's trading data, compares to rolling baseline, and generates
improvement suggestions tied to the phased roadmap. Output:

  1. Text report sent to Telegram
  2. Markdown saved to docs/work-log/YYYY-MM-DD_eod_insights.md
  3. YAML learning saved to learnings/daily/YYYY-MM-DD.yaml

Designed to be called once by auto-stop-eod.sh at ~15:40 IST.
"""
from __future__ import annotations

import argparse
import json
import sys
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "docs" / "paper-trades"
OUT_DIR = ROOT / "docs" / "work-log"
LEARN_DIR = ROOT / "learnings" / "daily"

ENGINES = ["v4", "v5", "v5_classic", "v5_2", "v5_3", "v5_6", "v5_7"]

# Phased roadmap — update this as we progress
ROADMAP = [
    {
        "week": 1,
        "date_range": "2026-04-22 to 2026-04-25",  # this week
        "change": "Rust cap 30 → 150 (externalized)",
        "v5_target_min": 10000, "v5_target_max": 15000,
        "gate": "Does v5 match v5_classic within Rs 2k?",
    },
    {
        "week": 2,
        "date_range": "2026-04-28 to 2026-05-02",
        "change": "Position size 15% → 20% of pool budget",
        "v5_target_min": 18000, "v5_target_max": 22000,
        "gate": "P&L scales linearly with position size?",
    },
    {
        "week": 3,
        "date_range": "2026-05-05 to 2026-05-09",
        "change": "Universe 201 → 539 (tiered models)",
        "v5_target_min": 28000, "v5_target_max": 35000,
        "gate": "Tier models hold WR > 80%?",
    },
    {
        "week": 4,
        "date_range": "2026-05-12 to 2026-05-16",
        "change": "Capital Rs 10L → 15L per engine",
        "v5_target_min": 40000, "v5_target_max": 50000,
        "gate": "Full roadmap target met?",
    },
]


def load_engine_stats(engine, date_str):
    fp = DATA_DIR / engine / f"{date_str}.json"
    if not fp.exists():
        return None
    try:
        d = json.loads(fp.read_text())
    except Exception:
        return None
    if engine == "v4":
        closed = [p for p in d.get("positions", []) if p.get("status") == "closed"]
        wins = sum(1 for t in closed if t.get("pnl", 0) > 0)
        losses = sum(1 for t in closed if t.get("pnl", 0) < 0)
        return {
            "pnl": d.get("realized_pnl", 0),
            "trades": len(closed),
            "wins": wins,
            "losses": losses,
            "wr": (wins / len(closed) * 100) if closed else 0,
        }
    s = d.get("summary", {})
    trades = s.get("trades", 0)
    wins = s.get("wins", 0)
    return {
        "pnl": s.get("total_pnl", 0),
        "trades": trades,
        "wins": wins,
        "losses": s.get("losses", 0),
        "wr": (wins / trades * 100) if trades else 0,
    }


def current_phase(today=None):
    if today is None:
        today = datetime.now().date()
    for phase in ROADMAP:
        start, end = phase["date_range"].split(" to ")
        if datetime.strptime(start, "%Y-%m-%d").date() <= today <= datetime.strptime(end, "%Y-%m-%d").date():
            return phase
    # Default to earliest phase in the future
    for phase in ROADMAP:
        start = datetime.strptime(phase["date_range"].split(" to ")[0], "%Y-%m-%d").date()
        if start > today:
            return phase
    return ROADMAP[-1]


def baseline_avg(engine, days=3, today=None):
    if today is None:
        today = datetime.now().date()
    results = []
    for delta in range(1, days + 5):  # look back up to 8 calendar days
        d = (today - timedelta(days=delta)).strftime("%Y-%m-%d")
        stats = load_engine_stats(engine, d)
        if stats and stats["trades"] > 0:
            results.append(stats)
            if len(results) >= days:
                break
    if not results:
        return None
    return {
        "pnl": sum(r["pnl"] for r in results) / len(results),
        "trades": sum(r["trades"] for r in results) / len(results),
        "wr": sum(r["wr"] for r in results) / len(results),
        "days_sampled": len(results),
    }


def generate_insights(today_str=None):
    if today_str is None:
        today_str = datetime.now().strftime("%Y-%m-%d")
    today_date = datetime.strptime(today_str, "%Y-%m-%d").date()
    today_stats = {e: load_engine_stats(e, today_str) for e in ENGINES}
    baselines = {e: baseline_avg(e, today=today_date) for e in ENGINES}
    phase = current_phase(today=today_date)

    insights = []

    # 1. Combined P&L check
    today_combined = sum(s["pnl"] for s in today_stats.values() if s)
    baseline_combined = sum(b["pnl"] for b in baselines.values() if b)
    if baseline_combined > 0:
        delta_pct = (today_combined - baseline_combined) / baseline_combined * 100
        if today_combined > baseline_combined * 1.2:
            insights.append(f"✅ Combined P&L Rs {today_combined:+,.0f} is +{delta_pct:.0f}% vs 3-day baseline. Strong day.")
        elif today_combined < baseline_combined * 0.5:
            insights.append(f"⚠ Combined P&L Rs {today_combined:+,.0f} is {delta_pct:+.0f}% vs baseline. Investigate.")
        else:
            insights.append(f"● Combined P&L Rs {today_combined:+,.0f} ({delta_pct:+.0f}% vs baseline).")

    # 2. v5 vs v5_classic A/B
    v5 = today_stats.get("v5")
    vc = today_stats.get("v5_classic")
    if v5 and vc:
        gap = vc["pnl"] - v5["pnl"]
        if abs(gap) < 2000:
            insights.append(f"✅ v5 vs v5_classic gap closed to Rs {gap:+,.0f}. Rust fix holding.")
        elif gap > 5000:
            insights.append(f"⚠ v5_classic still ahead by Rs {gap:+,.0f}. Rust fix may be insufficient — check rejection log.")
        else:
            insights.append(f"● v5 vs v5_classic gap Rs {gap:+,.0f} (narrowing but not closed).")

    # 3. Win rate sanity
    for engine in ["v4", "v5_6", "v5_7", "v5_classic"]:
        s = today_stats.get(engine)
        if s and s["trades"] >= 5:
            if s["wr"] < 60:
                insights.append(f"⚠ {engine} win rate dropped to {s['wr']:.0f}% ({s['wins']}W/{s['losses']}L). Below 60% is abnormal.")
            elif s["wr"] > 90:
                insights.append(f"✅ {engine} win rate {s['wr']:.0f}% — elite session.")

    # 4. Trade count vs baseline (detect engine throttling)
    for engine in ["v5", "v5_6", "v5_7", "v5_classic"]:
        s = today_stats.get(engine)
        b = baselines.get(engine)
        if s and b and b["trades"] > 5:
            if s["trades"] < b["trades"] * 0.4:
                insights.append(f"⚠ {engine} trade count {s['trades']} vs baseline {b['trades']:.0f}. May be throttled — check rejection logs.")

    # 5. Roadmap phase assessment
    v5_pnl = v5["pnl"] if v5 else 0
    if phase["v5_target_min"] <= v5_pnl <= phase["v5_target_max"]:
        insights.append(f"✅ Week {phase['week']} target hit: v5 Rs {v5_pnl:+,.0f} in [{phase['v5_target_min']:,}-{phase['v5_target_max']:,}] range. Consider next phase.")
    elif v5_pnl > phase["v5_target_max"]:
        insights.append(f"🚀 Week {phase['week']} target exceeded: v5 Rs {v5_pnl:+,.0f} > Rs {phase['v5_target_max']:,}. Over-performing!")
    elif v5_pnl < phase["v5_target_min"]:
        insights.append(f"● Week {phase['week']} target not yet hit: v5 Rs {v5_pnl:+,.0f} < Rs {phase['v5_target_min']:,}. Need: {phase['gate']}")

    # 6. Dormant engine detection
    for engine in ENGINES:
        s = today_stats.get(engine)
        if s and s["trades"] == 0 and engine not in ("v5_2",):  # v5_2 is weekly options
            insights.append(f"⚠ {engine} took 0 trades today. Likely dormant or over-filtered.")

    return insights, today_stats, baselines, phase


def send_telegram(msg):
    env_file = ROOT / ".env"
    if not env_file.exists():
        return False
    env = dict(
        line.split("=", 1)
        for line in env_file.read_text().splitlines()
        if "=" in line and not line.startswith("#")
    )
    token = env.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat = env.get("TELEGRAM_CHAT_ID", "").strip()
    if not token or not chat:
        return False
    try:
        subprocess.run(
            ["curl", "-s", "-X", "POST",
             f"https://api.telegram.org/bot{token}/sendMessage",
             "--data-urlencode", f"chat_id={chat}",
             "--data-urlencode", f"text={msg}"],
            timeout=10, check=False, capture_output=True,
        )
        return True
    except Exception:
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=None, help="YYYY-MM-DD (default: today)")
    parser.add_argument("--no-telegram", action="store_true", help="Skip Telegram send")
    args = parser.parse_args()

    today = args.date or datetime.now().strftime("%Y-%m-%d")
    insights, today_stats, baselines, phase = generate_insights(today_str=today)

    # Build the report
    lines = [f"📡 EOD INSIGHTS — {today}", ""]

    lines.append(f"Current phase: Week {phase['week']} — {phase['change']}")
    lines.append(f"Target range: Rs {phase['v5_target_min']:,} to Rs {phase['v5_target_max']:,}")
    lines.append(f"Gate: {phase['gate']}")
    lines.append("")

    lines.append("═══ TODAY vs 3-DAY BASELINE ═══")
    for eng in ENGINES:
        s = today_stats.get(eng)
        b = baselines.get(eng)
        if not s:
            continue
        b_pnl = f"(avg {b['pnl']:+,.0f})" if b else "(no baseline)"
        lines.append(f"  {eng:11s} Rs {s['pnl']:+7,.0f}  {s['trades']:3d}t  {s['wr']:3.0f}% WR  {b_pnl}")

    lines.append("")
    lines.append("═══ INSIGHTS & ACTIONS ═══")
    if insights:
        for ins in insights:
            lines.append(f"  {ins}")
    else:
        lines.append("  ● No notable anomalies.")

    report = "\n".join(lines)
    print(report)

    # Save markdown
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    md_file = OUT_DIR / f"{today}_eod_insights.md"
    md_content = f"""# EOD Insights — {today}

## Current Roadmap Phase
- **Week {phase['week']}** — {phase['change']}
- **Target**: Rs {phase['v5_target_min']:,} to Rs {phase['v5_target_max']:,}
- **Gate**: {phase['gate']}

## Today vs 3-Day Baseline

| Engine | Today P&L | Trades | WR | Baseline avg |
|--------|----------:|-------:|---:|-------------:|
"""
    for eng in ENGINES:
        s = today_stats.get(eng)
        b = baselines.get(eng)
        if not s:
            continue
        b_pnl = f"Rs {b['pnl']:+,.0f}" if b else "—"
        md_content += f"| {eng} | Rs {s['pnl']:+,.0f} | {s['trades']} | {s['wr']:.0f}% | {b_pnl} |\n"

    md_content += "\n## Insights & Actions\n\n"
    for ins in insights:
        md_content += f"- {ins}\n"
    if not insights:
        md_content += "- No notable anomalies.\n"

    md_file.write_text(md_content)
    print(f"\n→ saved: {md_file}")

    # Save YAML learning (local only)
    LEARN_DIR.mkdir(parents=True, exist_ok=True)
    yaml_file = LEARN_DIR / f"{today}.yaml"
    import yaml  # type: ignore
    try:
        yaml_file.write_text(yaml.safe_dump({
            "date": today,
            "phase_week": phase["week"],
            "phase_change": phase["change"],
            "combined_pnl": sum(s["pnl"] for s in today_stats.values() if s),
            "per_engine": {e: today_stats[e] for e in ENGINES if today_stats.get(e)},
            "insights": insights,
            "storage": "local-only per project rule",
        }, default_flow_style=False, allow_unicode=True))
        print(f"→ saved: {yaml_file}")
    except ImportError:
        # YAML optional
        yaml_file.with_suffix(".json").write_text(json.dumps({
            "date": today,
            "phase_week": phase["week"],
            "combined_pnl": sum(s["pnl"] for s in today_stats.values() if s),
            "insights": insights,
        }, indent=2, default=str))

    # Telegram
    if args.no_telegram:
        print("→ telegram: skipped (--no-telegram)")
    else:
        sent = send_telegram(report)
        print(f"→ telegram: {'sent' if sent else 'skipped (no env)'}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
