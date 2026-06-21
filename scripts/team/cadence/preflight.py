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

Modes:
  python3 scripts/team/cadence/preflight.py                 # default: monday-check.sh
  python3 scripts/team/cadence/preflight.py --smoke-engine  # dry-boot each active engine

--smoke-engine (S2-PM-001, added after the 2026-05-18 incident):
  The 08:50 static preflight passed 27/27 checks on 2026-05-18 but never tried
  to actually BOOT the engines — so a startup SystemExit from a tight model-
  staleness check (check_model_freshness, v5-paper-trade.py:run() first line)
  slipped through and v5 died at 09:30 market open. sarathi-verify.sh --smoke
  only import/compile-checks; it never executes run(). --smoke-engine closes
  that gap: it actually starts each active engine in an isolated, no-trade,
  short-timeout dry boot and FAILS if the engine raises during startup.
"""
from __future__ import annotations
import os
import re
import subprocess
import sys
import tempfile
import shutil
from datetime import datetime, timezone, timedelta
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
IST = timezone(timedelta(hours=5, minutes=30))

# How long to let an engine boot before we conclude "it got past all startup
# guards and into its warm-up/main loop" (= a clean boot). The startup failure
# class we care about (SystemExit from check_model_freshness, missing model,
# bad import resolved at call-time, etc.) fires within the first moment of
# run(), long before the 09:30 warm-up sleep — so a non-zero exit BEFORE this
# deadline is a real startup failure, while still-running AT the deadline means
# the engine booted cleanly and is now blocked on its warm-up/scan timer.
SMOKE_BOOT_TIMEOUT_SEC = 25


def _stamp() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d %H:%M:%S")


def _date() -> str:
    return datetime.now(IST).strftime("%Y-%m-%d")


# ──────────────────────────────────────────────────────────────────────────
# S2-PM-001 — --smoke-engine dry-boot mode
# ──────────────────────────────────────────────────────────────────────────

def _active_engines() -> list[tuple[str, str]]:
    """Derive the active engine set from launch-market.sh rather than hardcoding.

    launch-market.sh owns the source of truth: an ENGINES=(...) bash array whose
    *uncommented* entries look like  "name|scripts/xxx-paper-trade.py". Retired
    engines are commented out (leading #). We parse only the uncommented entries
    inside the ENGINES=( ... ) block so this never drifts when the active set
    changes (it derived 3 — v4, v5, v5_classic — at the time of writing).

    Returns list of (name, script_relpath). Empty list if the array can't be found.
    """
    launch = PROJECT_ROOT / "scripts" / "launch-market.sh"
    engines: list[tuple[str, str]] = []
    try:
        text = launch.read_text(encoding="utf-8")
    except OSError:
        return engines

    in_block = False
    entry_re = re.compile(r'"\s*([A-Za-z0-9_]+)\s*\|\s*(scripts/[^"|]+\.py)\s*"')
    for raw in text.splitlines():
        line = raw.strip()
        if not in_block:
            if line.startswith("ENGINES=("):
                in_block = True
            continue
        if line.startswith(")"):
            break
        if line.startswith("#"):   # retired / commented-out engine — skip
            continue
        m = entry_re.search(line)
        if m:
            engines.append((m.group(1), m.group(2)))
    return engines


def _smoke_boot_one(name: str, script: str, state_dir: Path) -> tuple[str, str]:
    """Dry-boot a single engine in an isolated, no-trade mode under a short timeout.

    SAFETY — this must NEVER place a paper trade, write to the live trade JSONs,
    or talk to the live Rust engine on :8080. We enforce that two ways:

      1. Isolation env: TRADEPILOT_STATE_DIR points the engine at a throwaway tmp
         dir, and TRADEPILOT_SMOKE=1 / TRADEPILOT_SMOKE_NO_NET=1 tell the engine
         to short-circuit before any order, network call, or live-state write.
      2. Detection-by-exit-timing: a startup failure (e.g. check_model_freshness's
         SystemExit on a stale model) makes the process exit non-zero almost
         immediately — well before run() reaches the 09:30 warm-up sleep or any
         deploy. So we run the boot under a hard subprocess timeout:
            - exit != 0 BEFORE the deadline  -> startup error -> FAIL
            - still running AT the deadline   -> booted past all startup guards,
                                                 now parked on warm-up/scan timer
                                                 -> we kill it and PASS
            - exit == 0 quickly               -> clean early exit -> PASS

    NOTE FOR ENGINE OWNERS (engine code is NOT edited by this task):
      For the dry boot to be fully self-isolating, each engine MUST honor:
        TRADEPILOT_SMOKE=1        -> after running all startup guards
                                     (check_model_freshness, import/init, premarket
                                     wiring) exit 0 BEFORE the warm-up sleep and
                                     BEFORE any deploy / Rust :8080 call / live write.
        TRADEPILOT_STATE_DIR=<d>  -> read/write state under <d> instead of
                                     docs/paper-trades/<engine>/.
        TRADEPILOT_SMOKE_NO_NET=1 -> skip yfinance + Rust :8080 entirely.
      Until engines honor TRADEPILOT_SMOKE (follow-up — see report), this smoke
      still works as a *startup-crash* detector via the exit-timing logic above:
      the isolation env vars + short timeout + throwaway state dir keep it from
      reaching live trades within SMOKE_BOOT_TIMEOUT_SEC. The kill-on-timeout
      branch is the safety net for engines that haven't wired the early exit yet.

    Returns (status, detail) where status is "PASS" or "FAIL".
    """
    script_path = PROJECT_ROOT / script
    if not script_path.exists():
        return ("FAIL", f"{name}: engine script missing at {script}")

    env = dict(os.environ)
    env["TRADEPILOT_SMOKE"] = "1"
    env["TRADEPILOT_SMOKE_NO_NET"] = "1"
    env["TRADEPILOT_STATE_DIR"] = str(state_dir)
    # Defensive: never let a smoke boot page the team or hit external APIs.
    env["TRADEPILOT_NO_TELEGRAM"] = "1"
    env["PYTHONUNBUFFERED"] = "1"

    try:
        proc = subprocess.run(
            ["python3", str(script_path)],
            cwd=str(PROJECT_ROOT),
            env=env,
            capture_output=True,
            text=True,
            timeout=SMOKE_BOOT_TIMEOUT_SEC,
        )
    except subprocess.TimeoutExpired as te:
        # Still running at the deadline => booted cleanly past every startup
        # guard and is now parked on its warm-up / scan timer. subprocess.run
        # has already terminated the child for us. This is the PASS case.
        stderr_tail = (te.stderr or b"")
        if isinstance(stderr_tail, bytes):
            stderr_tail = stderr_tail.decode("utf-8", "replace")
        # Be paranoid: if it somehow logged a startup error before hanging, surface it.
        if "SystemExit" in stderr_tail or "Traceback" in stderr_tail:
            return ("FAIL", f"{name}: error during startup before timeout:\n"
                            f"{stderr_tail.strip()[-800:]}")
        return ("PASS", f"{name}: booted past all startup guards "
                        f"(still alive at {SMOKE_BOOT_TIMEOUT_SEC}s — killed)")

    if proc.returncode == 0:
        return ("PASS", f"{name}: clean startup (exited 0 in smoke mode)")

    # Non-zero exit before the deadline => startup failure. THIS is the
    # 2026-05-18 incident signature (SystemExit from check_model_freshness).
    tail = (proc.stderr or proc.stdout or "").strip()[-1200:]
    return ("FAIL", f"{name}: engine errored during startup "
                    f"(exit {proc.returncode}):\n{tail}")


def run_smoke_engine() -> int:
    """Boot each active engine in an isolated dry/no-trade mode; fail on any startup error.

    Returns 0 if every active engine boots cleanly, else the number of failures.
    """
    os.chdir(PROJECT_ROOT)
    print(f"[{_stamp()}] preflight --smoke-engine: dry-booting active engines")
    sys.stdout.flush()

    engines = _active_engines()
    if not engines:
        print("ERROR: could not derive active engines from scripts/launch-market.sh "
              "(ENGINES=(...) block not found). Refusing to claim PASS.", file=sys.stderr)
        return 1

    print(f"  active engines (from launch-market.sh): "
          f"{', '.join(n for n, _ in engines)}")

    results: list[tuple[str, str, str]] = []   # (name, status, detail)
    # One throwaway state root for the whole run; per-engine subdirs inside.
    state_root = Path(tempfile.mkdtemp(prefix="tradepilot-smoke-"))
    try:
        for name, script in engines:
            eng_state = state_root / name
            eng_state.mkdir(parents=True, exist_ok=True)
            print(f"  → booting {name} ({script}) "
                  f"[TRADEPILOT_SMOKE=1, isolated state, {SMOKE_BOOT_TIMEOUT_SEC}s cap]...")
            sys.stdout.flush()
            status, detail = _smoke_boot_one(name, script, eng_state)
            mark = "✓" if status == "PASS" else "✗"
            print(f"    {mark} [{status}] {detail}")
            sys.stdout.flush()
            results.append((name, status, detail))
    finally:
        shutil.rmtree(state_root, ignore_errors=True)

    fails = [r for r in results if r[1] == "FAIL"]
    print("")
    print(f"  smoke-engine summary: {len(results) - len(fails)} PASS / "
          f"{len(fails)} FAIL / {len(results)} total")

    rc = len(fails)

    # Persist a copy into today's standup folder (same convention as default mode).
    standup_path = PROJECT_ROOT / "docs" / "team" / "standup" / f"{_date()}_preflight-smoke-engine.md"
    standup_path.parent.mkdir(parents=True, exist_ok=True)
    body_lines = [f"# Preflight --smoke-engine — {_date()}", "",
                  f"_Generated {_stamp()}_  ·  exit={rc}", "",
                  "| Engine | Result | Detail |", "|--------|--------|--------|"]
    for name, status, detail in results:
        body_lines.append(f"| {name} | {status} | {detail.replace(chr(10), ' ⏎ ')[:300]} |")
    standup_path.write_text("\n".join(body_lines) + "\n", encoding="utf-8")

    # Audit + page on failure, mirroring main()'s pager wiring.
    sys.path.insert(0, str(PROJECT_ROOT))
    try:
        from scripts.team.log import log_audit, log_activity
        if rc != 0:
            log_audit(
                "sarathi", action="preflight-smoke-engine-fail",
                decision="BLOCK",
                subject="engine dry-boot",
                evidence={"failures": [n for n, s, _ in results if s == "FAIL"],
                          "report": str(standup_path.relative_to(PROJECT_ROOT))},
                reason=(f"--smoke-engine detected {rc} engine(s) failing during startup "
                        f"dry-boot. This is the 2026-05-18 incident class (startup "
                        f"SystemExit). Engines would die at market open. "
                        f"Review {standup_path.relative_to(PROJECT_ROOT)}."),
                vetoable_by=["CEO"],
                rule_family="SARATHI-CDE",
            )
        else:
            log_activity("knowledge-archivist", "preflight-smoke-engine",
                         f"--smoke-engine PASS — {len(results)} engines booted clean; "
                         f"see {standup_path.relative_to(PROJECT_ROOT)}",
                         links={"report": str(standup_path.relative_to(PROJECT_ROOT))})
    except Exception as e:
        print(f"warn: audit/activity log failed: {e}", file=sys.stderr)

    return rc


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
    if "--smoke-engine" in sys.argv:
        sys.exit(run_smoke_engine())
    sys.exit(main())
