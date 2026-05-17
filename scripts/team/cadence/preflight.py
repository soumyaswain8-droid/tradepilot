"""
Pre-flight launcher: runs monday-check.sh, captures output, pages Telegram on FAIL.

Fires weekdays at 08:50 IST via launchd (com.tradepilot.v2.preflight).
That's 5 min before the 08:55 DAT pre-market check and 20 min before the
09:10 engines-on launch — enough lead time to notice a FAIL before
trading would have started.

Behaviour:
  - PASS  (exit 0): writes summary to standup card, logs activity, silent
  - WARN: same as PASS (acceptable)
  - FAIL  (exit 1): Sarathi BLOCK audit entry → triggers Telegram via
                    log_audit() existing pager
"""
from __future__ import annotations
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IST = timezone(timedelta(hours=5, minutes=30))


def _stamp() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _date() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


def main() -> int:
    os.chdir(PROJECT_ROOT)
    print(f"[{_stamp()}] preflight: running monday-check.sh")
    sys.stdout.flush()

    proc = subprocess.run(
        ["bash", "scripts/team/cadence/monday-check.sh"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    out = proc.stdout + proc.stderr
    print(out)
    rc = proc.returncode

    # Write tagged copy of the check into today's standup folder
    standup_path = PROJECT_ROOT / "docs" / "team" / "standup" / f"{_date()}_preflight.md"
    standup_path.parent.mkdir(parents=True, exist_ok=True)
    standup_path.write_text(
        f"# Preflight — {_date()}\n\n"
        f"_Generated {_stamp()}_  ·  exit={rc}\n\n"
        f"```\n{out}\n```\n",
        encoding="utf-8",
    )

    # Audit + page
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from scripts.team.log import log_audit, log_activity
        if rc != 0:
            log_audit(
                "sarathi", action="preflight-fail",
                decision="BLOCK",
                subject="monday-check.sh",
                evidence={"exit_code": rc,
                          "report": str(standup_path.relative_to(PROJECT_ROOT))},
                reason=(f"Pre-flight check failed (rc={rc}). "
                        f"Engines may not launch cleanly at 09:10. "
                        f"Review {standup_path.relative_to(PROJECT_ROOT)}."),
                vetoable_by=["CEO"],
                rule_family="SARATHI-CDE",
            )
        else:
            # Count pass/warn from output for friendly summary
            log_activity("knowledge-archivist", "preflight",
                         f"Preflight PASS — see {standup_path.relative_to(PROJECT_ROOT)}",
                         links={"report": str(standup_path.relative_to(PROJECT_ROOT))})
    except Exception as e:
        print(f"warn: audit/activity log failed: {e}", file=sys.stderr)

    return rc


if __name__ == "__main__":
    sys.exit(main())
