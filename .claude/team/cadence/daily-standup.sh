#!/usr/bin/env bash
# Daily 15:50 IST automated standup card.
# Reads docs/team/status/*.json + activity + audit, emits docs/team/standup/YYYY-MM-DD.md
# Scheduled via launchd: com.tradepilot.v2.standup (Weekday 1-5, 15:50 IST)
#
# CADENCE RESILIENCE (2026-05-30):
#   This script MUST always produce a card, even if:
#   - no engines ran today (silent-failure days 26/27/28 May produced nothing)
#   - team status JSON files are missing or malformed
#   - the audit/activity JSONL files don't exist
#   A missing standup card is the worst signal — silence looks like "nothing happened"
#   when often the truth is "nothing was *recorded*". Always speak.

# NOTE: deliberately NOT `set -euo pipefail` — we want the script to push through
# missing inputs and emit a card describing what's missing, not abort silently.
set -u
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

python3 - <<'PYEOF'
import json, sys, os
from datetime import datetime, timezone, timedelta
from pathlib import Path

ist = timezone(timedelta(hours=5, minutes=30))
today = datetime.now(ist).strftime("%Y-%m-%d")
PR = Path(".")
status_dir = PR / "docs/team/status"
activity_p  = PR / f"docs/team/activity/{today}.jsonl"
audit_p     = PR / f"docs/team/audit/{today}.jsonl"


def safe_jsonl(p):
    """Read JSONL, skipping malformed lines instead of aborting."""
    if not p.exists():
        return []
    out, bad = [], 0
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            bad += 1
    if bad:
        sys.stderr.write(f"warn: {bad} malformed line(s) in {p}\n")
    return out


def safe_status_files():
    """Read each agent status JSON independently — a single malformed file
    must not poison the whole card."""
    out, errors = [], []
    if not status_dir.exists():
        return out, errors
    for p in sorted(status_dir.glob("*.json")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception as e:  # noqa: BLE001
            errors.append(f"{p.name}: {e}")
    return sorted(out, key=lambda r: r.get("agent", "")), errors


def engines_ran_today():
    """Did engines actually run today?

    Truth source: any v[45]*-paper-trade.py log file for today with >50 lines
    (banner alone is ~20 lines; >50 means we got past warm-up). Returns
    (ran: bool, evidence: list[str]).
    """
    logs = sorted(PR.glob(f"logs/v*-{today}.log"))
    if not logs:
        return False, []
    real = []
    for lg in logs:
        try:
            n = sum(1 for _ in lg.open("r", encoding="utf-8", errors="replace"))
            if n > 50:
                real.append(f"{lg.stem} ({n} lines)")
        except Exception:  # noqa: BLE001
            pass
    return (len(real) > 0), real


# ───────────────────────── Gather ─────────────────────────
agents, status_errors = safe_status_files()
audit  = safe_jsonl(audit_p)
activity = safe_jsonl(activity_p)
ran, engine_evidence = engines_ran_today()

blocks    = [r for r in audit if r.get("decision") in ("BLOCK", "REJECT")]
warns     = [r for r in audit if r.get("decision") == "WARN"]
passes    = [r for r in audit if r.get("decision") == "PASS"]
overrides = [r for r in audit if r.get("decision") == "OVERRIDE"]

# ───────────────────────── Render ─────────────────────────
out = []
out.append(f"# TradePilot Standup — {today}\n")
out.append(f"_Generated {datetime.now(ist).isoformat(timespec='seconds')}_\n")

# Engine-run banner — the most important line on silent-failure days.
if ran:
    out.append("\n## Engines\n")
    out.append(f"✓ **Engines ran today** — {len(engine_evidence)} logs with substantive activity:")
    for ev in engine_evidence:
        out.append(f"- {ev}")
else:
    out.append("\n## ⚠ Engines\n")
    out.append("**Engines did NOT run with substantive activity today.**")
    out.append("Possible causes: laptop slept through the session, launch-market.sh exited non-zero,")
    out.append("launchd job in EX_CONFIG state, or it's a market holiday.")
    out.append("\nDiagnostics:")
    out.append("- `./scripts/launch-market.sh --status`  — what's alive now")
    out.append("- `launchctl list | grep tradepilot`     — launchd job exit codes (78 = EX_CONFIG)")
    out.append("- `tail logs/auto/v2/*.log`              — most recent launchd attempts")
    out.append("- `pmset -g log | grep -E 'Sleep|Wake' | tail` — sleep history")

# Agent status
out.append("\n## Agent Status\n")
if agents:
    out.append("| Agent | Status | Last action |")
    out.append("|---|---|---|")
    for a in agents:
        out.append(
            f"| {a.get('agent', '?')} | {a.get('status', '?')} | "
            f"{a.get('last_action', '—')} |"
        )
else:
    out.append("_No agent status files found._")
if status_errors:
    out.append("\n_Status files with parse errors (skipped, not fatal):_")
    for e in status_errors:
        out.append(f"- {e}")

# Audit summary
out.append("\n## Audit Today\n")
out.append(
    f"- **{len(passes)} passes** · **{len(warns)} warns** · "
    f"**{len(blocks)} BLOCKs** · **{len(overrides)} overrides**"
)
if blocks:
    out.append("\n### BLOCKs (action required)\n")
    for b in blocks:
        out.append(
            f"- `{b.get('rule_family', '?')}` · {b.get('action', '?')} · "
            f"{b.get('subject', '?')} — {b.get('reason', '?')}"
        )

# Recent activity
out.append("\n## Activity (last 10)\n")
if activity:
    for r in activity[-10:][::-1]:
        out.append(
            f"- `{r.get('ts', '?')}` **{r.get('agent', '?')}** · "
            f"{r.get('summary', '?')}"
        )
else:
    out.append("_No activity recorded today._")

# Write — wrap the I/O too so a write failure doesn't lose the card.
out_path = PR / f"docs/team/standup/{today}.md"
try:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"Standup written: {out_path}")
except Exception as e:  # noqa: BLE001
    sys.stderr.write(f"FATAL: could not write standup card: {e}\n")
    sys.exit(2)

# Telegram on engine silence — bring the failure into the user's view.
if not ran:
    try:
        token = chat = None
        env_path = PR / ".env"
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("TELEGRAM_CHAT_ID="):
                    chat = line.split("=", 1)[1].strip().strip('"')
        if token and chat:
            import urllib.parse, urllib.request
            msg = (
                f"⚠ TradePilot standup {today}: engines did NOT run today.\n"
                f"Card: docs/team/standup/{today}.md\n"
                "Check launch-market.sh --status and launchctl list."
            )
            data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
            urllib.request.urlopen(
                urllib.request.Request(
                    f"https://api.telegram.org/bot{token}/sendMessage", data=data
                ),
                timeout=5,
            )
    except Exception:  # noqa: BLE001 — best-effort; the card is the primary artifact
        pass

sys.exit(0)
PYEOF
