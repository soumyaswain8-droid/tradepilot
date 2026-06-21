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
import re
import subprocess
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LOG_DIR = PROJECT_ROOT / "logs" / "auto" / "v2"
LOG_DIR.mkdir(parents=True, exist_ok=True)
IST = timezone(timedelta(hours=5, minutes=30))

LAUNCH_SCRIPT = PROJECT_ROOT / "scripts" / "launch-market.sh"
# A live paper-trade engine process matches this pattern (mirrors the pkill/pgrep
# pattern used inside launch-market.sh: "scripts/v[0-9].*paper-trade.py").
ENGINE_PGREP_PATTERN = r"scripts/v[0-9].*paper-trade\.py"


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

    # S2-PM-002: independent of launch's own exit code, verify the engines are
    # *actually* running. launch-market.sh can exit 0 yet an engine die seconds
    # later on boot. pgrep the live processes and compare to the expected count.
    engines_ok = _assert_engines_running()

    # Fail the run if either signal is bad. Preserve launch's specific code when
    # it was non-zero; otherwise surface an engine-shortfall as exit 4
    # (matches launch-market.sh EX_ENGINE_MISSING for a consistent pager story).
    if launch.returncode != 0:
        return launch.returncode
    if not engines_ok:
        return 4
    return 0


def _block_and_page(action: str, subject: str, evidence: dict,
                     reason: str, page_msg: str) -> None:
    """Log a SARATHI-CDE BLOCK and page Telegram. Shared by S2-PM-006 / S2-PM-002.

    Two layers, both best-effort (neither may raise back up the stack):
      1. log_audit(decision="BLOCK") — writes the audit + Sarathi ledger entry
         AND triggers the team pager (prototype.v5.telegram_bot.send_alert) for
         any BLOCK/REJECT/ESCALATE. This is the primary path.
      2. A pure-stdlib Telegram fallback page — belt-and-suspenders for the case
         where the prototype import chain is unavailable under launchd (the same
         TCC quirk that forced this script to be Python in the first place).
    """
    # Layer 1: audit BLOCK (also pages via log_audit's built-in send_alert)
    try:
        sys.path.insert(0, str(PROJECT_ROOT))
        from scripts.team.log import log_audit  # type: ignore
        log_audit(
            "sarathi",
            action=action,
            decision="BLOCK",
            subject=subject,
            evidence=evidence,
            reason=reason,
            vetoable_by=["CEO"],
            rule_family="SARATHI-CDE",
        )
    except Exception as e:  # noqa: BLE001
        print(f"warn: BLOCK audit log failed: {e}", file=sys.stderr)

    # Layer 2: stdlib Telegram fallback (no extra import risk under launchd)
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
            data = urllib.parse.urlencode({"chat_id": chat, "text": page_msg}).encode()
            req = urllib.request.Request(
                f"https://api.telegram.org/bot{token}/sendMessage", data=data
            )
            urllib.request.urlopen(req, timeout=5)
    except Exception as e:  # noqa: BLE001
        print(f"warn: Telegram page failed: {e}", file=sys.stderr)


def _alert_launch_failure(rc: int) -> None:
    """SARATHI-CDE BLOCK + Telegram page on any non-zero launch exit (S2-PM-006).

    Implements S2-PM-006 from the Sprint 2 backlog — promoted to high priority
    on 2026-05-23 after Week 1's review, shipped 2026-05-30 after Week 2
    produced three silent-failure days (26 / 27 / 28).
    """
    _block_and_page(
        action="launch-market-failure",
        subject="scripts/launch-market.sh",
        evidence={"exit_code": rc},
        reason=(
            f"launch-market.sh exited {rc} — engines may not be running. "
            "Manual intervention required before 09:15 IST open."
        ),
        page_msg=(
            f"🚨 SARATHI-CDE BLOCK · launch-market.sh exit={rc}\n"
            f"Time: {_stamp()} IST\n"
            "Engines may not be running. Manual check required before 09:15 open."
        ),
    )


def _expected_engine_count() -> int:
    """Count active (uncommented) entries in launch-market.sh's ENGINES array.

    Parsing the array keeps this assertion in lock-step with the launch script
    rather than hardcoding 3 — when an engine is revived/retired there, this
    follows automatically. Falls back to 3 (the post-Sprint-1 active set) if the
    script can't be read or parsed.
    """
    try:
        in_array = False
        count = 0
        for raw in LAUNCH_SCRIPT.read_text().splitlines():
            line = raw.strip()
            if not in_array:
                if line.startswith("ENGINES=("):
                    in_array = True
                continue
            if line.startswith(")"):
                break
            # Active entries look like:  "v4|scripts/v4-paper-trade.py"
            # Skip comments and blank lines.
            if line.startswith("#") or not line:
                continue
            if re.match(r'"[^"|]+\|scripts/.*paper-trade\.py"', line):
                count += 1
        return count if count > 0 else 3
    except Exception as e:  # noqa: BLE001
        print(f"warn: could not parse ENGINES array ({e}); defaulting to 3",
              file=sys.stderr)
        return 3


def _running_engine_count() -> int:
    """Number of live paper-trade engine processes (pgrep -f, count of PIDs)."""
    proc = subprocess.run(
        ["pgrep", "-f", ENGINE_PGREP_PATTERN],
        capture_output=True, text=True,
    )
    # pgrep exits 1 with no output when nothing matches — that's a 0 count.
    pids = [p for p in proc.stdout.split() if p.strip()]
    return len(pids)


def _assert_engines_running() -> bool:
    """S2-PM-002: post-launch, assert the live engine count meets expectation.

    pgreps the actual running engines and compares to the expected active count
    parsed from launch-market.sh. On a shortfall, logs a SARATHI-CDE BLOCK and
    pages Telegram. Returns True if the count is satisfied, False otherwise.
    """
    expected = _expected_engine_count()
    running = _running_engine_count()
    print(f"[{_stamp()}] market_go: engine assertion — {running}/{expected} alive")

    if running >= expected:
        return True

    _block_and_page(
        action="engine-count-shortfall",
        subject="paper-trade engines",
        evidence={"expected": expected, "running": running,
                  "pattern": ENGINE_PGREP_PATTERN},
        reason=(
            f"Only {running}/{expected} paper-trade engines alive after launch. "
            "At least one engine failed to start or died on boot — the A/B set "
            "is incomplete for today's session. Manual check required before "
            "09:15 IST open."
        ),
        page_msg=(
            f"🚨 SARATHI-CDE BLOCK · engines {running}/{expected} alive\n"
            f"Time: {_stamp()} IST\n"
            "One or more paper-trade engines did not start. Manual check "
            "required before 09:15 open."
        ),
    )
    return False


if __name__ == "__main__":
    sys.exit(main())
