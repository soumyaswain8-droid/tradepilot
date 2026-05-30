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

    # S2-PM-006: any non-zero exit from launch is a silent-failure class bug
    # (caught after the Wed 2026-05-27 sleep-through + the 26/28 quiet-day class).
    # Page Sarathi and log a CDE BLOCK so the day doesn't pass unnoticed.
    if launch.returncode != 0:
        _alert_launch_failure(launch.returncode)

    return launch.returncode


def _alert_launch_failure(rc: int) -> None:
    """SARATHI-CDE BLOCK + Telegram page on any non-zero launch exit.

    Implements S2-PM-006 from the Sprint 2 backlog — promoted to high priority
    on 2026-05-23 after Week 1's review, shipped 2026-05-30 after Week 2
    produced three silent-failure days (26 / 27 / 28).
    """
    # Audit BLOCK (best-effort; audit must never raise back up the stack)
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.team.log import log_audit  # type: ignore
        log_audit(
            "sarathi",
            action="launch-market-failure",
            decision="BLOCK",
            subject="scripts/launch-market.sh",
            evidence={"exit_code": rc},
            reason=(
                f"launch-market.sh exited {rc} — engines may not be running. "
                "Manual intervention required before 09:15 IST open."
            ),
            vetoable_by=["CEO"],
            rule_family="SARATHI-CDE",
        )
    except Exception as e:  # noqa: BLE001
        print(f"warn: BLOCK audit log failed: {e}", file=sys.stderr)

    # Telegram page (best-effort; pure stdlib so no extra import risk)
    try:
        token = chat = None
        env_path = PROJECT_ROOT / ".env"
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                if line.startswith("TELEGRAM_BOT_TOKEN="):
                    token = line.split("=", 1)[1].strip().strip('"')
                elif line.startswith("TELEGRAM_CHAT_ID="):
                    chat = line.split("=", 1)[1].strip().strip('"')
        if token and chat:
            import urllib.parse, urllib.request
            msg = (
                f"🚨 SARATHI-CDE BLOCK · launch-market.sh exit={rc}\n"
                f"Time: {_stamp()} IST\n"
                "Engines may not be running. Manual check required before 09:15 open."
            )
            data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", data=data
            )
            urllib.request.urlopen(req, timeout=5)
    except Exception as e:  # noqa: BLE001
        print(f"warn: Telegram page failed: {e}", file=sys.stderr)


if __name__ == "__main__":
    sys.exit(main())
