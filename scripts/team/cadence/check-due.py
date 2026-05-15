"""
Due-task marker checker.

LLM-driven agents (Alpha Hunter, Competitive Intel, Architect code reviews)
cannot be cron-triggered directly — cron can't invoke Claude Code.

Instead, cron writes a "due" marker file under docs/team/due/<agent>.due
with a timestamp + reason. The dashboard (and Knowledge Archivist scan)
surfaces these markers as "pending" so the human + Claude session can
clear them on next invocation.

CLI:
  python3 scripts/team/cadence/check-due.py             # show pending
  python3 scripts/team/cadence/check-due.py --mark <agent> <reason>
  python3 scripts/team/cadence/check-due.py --clear <agent>
"""
from __future__ import annotations
import argparse
import json
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DUE_DIR = PROJECT_ROOT / "docs" / "team" / "due"
DUE_DIR.mkdir(parents=True, exist_ok=True)

IST = timezone(timedelta(hours=5, minutes=30))


def _ts() -> str:
    return datetime.now(IST).isoformat(timespec="seconds")


def mark(agent: str, reason: str) -> Path:
    """Cron writes a marker. Format: <agent>.due"""
    path = DUE_DIR / f"{agent}.due"
    payload = {"agent": agent, "marked_at": _ts(), "reason": reason}
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    # Activity-log it
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from scripts.team.log import log_activity
        log_activity(agent, "marked-due", reason, links={"marker": str(path.relative_to(PROJECT_ROOT))})
    except Exception:
        pass
    return path


def clear(agent: str) -> bool:
    path = DUE_DIR / f"{agent}.due"
    if path.exists():
        path.unlink()
        return True
    return False


def list_due() -> list[dict]:
    out = []
    for p in sorted(DUE_DIR.glob("*.due")):
        try:
            out.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:
            continue
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--mark", nargs=2, metavar=("AGENT", "REASON"))
    p.add_argument("--clear", metavar="AGENT")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    if args.mark:
        agent, reason = args.mark
        path = mark(agent, reason)
        print(f"Marked {agent} due: {path}")
        return

    if args.clear:
        ok = clear(args.clear)
        print(f"Cleared {args.clear}: {'YES' if ok else 'not-present'}")
        return

    due = list_due()
    if args.json:
        print(json.dumps(due, indent=2))
        return

    if not due:
        print("No pending LLM-agent tasks.")
        return
    print(f"{len(due)} pending LLM-agent task(s):")
    for d in due:
        print(f"  - {d['agent']:<20} marked {d['marked_at']}: {d['reason']}")


if __name__ == "__main__":
    main()
