"""
market_go — DAT-gated launch trigger for launchd.

Runs Sarathi DAT pre-launch check, then invokes scripts/launch-market.sh
only if DAT passes. Replaces the bash wrapper which hit launchd EX_CONFIG.

Python invocations under launchd have been more reliable than bash-script
invocations (some TCC quirk we never fully diagnosed — see Sprint 1 commit
6976823 for context).
"""
from __future__ import annotations
import os
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs" / "auto" / "v2"
LOG_DIR.mkdir(parents=True, exist_ok=True)
IST = timezone(timedelta(hours=5, minutes=30))


def _stamp() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def main() -> int:
    os.chdir(PROJECT_ROOT)

    print(f"[{_stamp()}] market_go: running DAT launch-gate")
    sys.stdout.flush()

    # Stage 1: DAT launch-gate via Sarathi verifier
    gate = subprocess.run(
        ["python3", "scripts/sarathi/verify.py",
         "--family", "DAT", "--check", "launch-gate"],
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )
    print(gate.stdout)
    if gate.stderr:
        print(gate.stderr, file=sys.stderr)

    if gate.returncode != 0:
        print(f"[{_stamp()}] market_go: DAT gate BLOCK (rc={gate.returncode}) — engines NOT launched")
        # Audit log
        sys.path.insert(0, str(PROJECT_ROOT))
        try:
            from scripts.team.log import log_audit
            log_audit("sarathi", action="launch-gate-block",
                      decision="BLOCK",
                      subject="launch-market.sh",
                      evidence={"gate_exit": gate.returncode},
                      reason="DAT pre-launch gate failed; engines not launched",
                      vetoable_by=["CEO"],
                      rule_family="SARATHI-DAT")
        except Exception as e:
            print(f"warn: audit log failed: {e}", file=sys.stderr)
        return 1

    # Stage 2: launch
    print(f"[{_stamp()}] market_go: DAT gate PASS — launching engines via launch-market.sh")
    sys.stdout.flush()

    # launch-market.sh is interactive-style (echoes to stdout/stderr).
    # We stream rather than capture so the launchd log file gets live output.
    launch = subprocess.run(
        ["bash", "scripts/launch-market.sh"],
        cwd=PROJECT_ROOT,
    )
    print(f"[{_stamp()}] market_go: launch-market.sh exit={launch.returncode}")
    return launch.returncode


if __name__ == "__main__":
    sys.exit(main())
