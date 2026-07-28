#!/usr/bin/env python3
"""
cadence-guard.py (2026-07-28) — makes silent cadence failures loud.

WHY: Two failures found on 2026-07-28, both invisible because absence-of-signal was
never monitored.

  1. Mon 2026-07-27 the Mac was powered off through the 08:50 launch window. launchd
     replays a StartCalendarInterval missed while ASLEEP but silently drops one missed
     while POWERED OFF, so no engines ran. The EOD summary honestly reported
     "Rs +0 across 0 trades" — indistinguishable from a genuinely flat market.

  2. Every com.tradepilot.* cadence job was dying with exit 78 (EX_CONFIG) and writing
     NOTHING to its log. Root cause: the job's StandardOutPath file carried a stale
     `com.apple.macl` xattr (TCC's per-file access record) naming a code identity that
     no longer matched launchd's. TCC denied opening the file for stdout, so launchd
     aborted BEFORE exec — no process, therefore no output, therefore no error anyone
     could see. v2.* jobs had been dead since 2026-05-22, engine-compare since 07-03.
     The earlier fix (a fresh logs/auto/v2/ subdirectory) worked only because new files
     start clean; the taint is per-FILE, not per-directory, so it silently recurs.

This guard therefore asserts POSITIVE EVIDENCE OF WORK, rather than watching for errors —
a component that never starts emits no error to watch for.

  --check-cadence   heal TCC-tainted job logs (archive them so launchd recreates clean)
  --check-session   assert engines actually launched today; alarm + annotate if not
  (no flag)         run both

Read-only w.r.t. engines and trade data. Only ever MOVES log files (never deletes).

Run: python3 scripts/cadence-guard.py --check-session
"""
import argparse
import json
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ARCHIVE = ROOT / "logs" / "auto" / "v2" / "_tcc-tainted-archive"
LAUNCH_LOG = Path.home() / "Library" / "Logs" / "tradepilot-launch.log"
STATE = ROOT / "logs" / "cadence-guard-state.json"

JOB_PREFIXES = ("com.tradepilot.", "com.soumya.tradepilot")
# A launch is only expected on weekdays. NSE holidays are NOT modelled (the repo has no
# holiday calendar), so this can false-alarm ~10 days/year. That is the deliberate
# trade-off: a spurious ping is cheap, a silently lost session is not.
MARKET_OPEN_HHMM = (9, 15)


# ---------------------------------------------------------------- telegram

def telegram(msg: str) -> None:
    env = ROOT / ".env"
    if not env.exists():
        return
    tok = chat = None
    for ln in env.read_text().splitlines():
        if ln.startswith("TELEGRAM_BOT_TOKEN="):
            tok = ln.split("=", 1)[1].strip().strip('"')
        elif ln.startswith("TELEGRAM_CHAT_ID="):
            chat = ln.split("=", 1)[1].strip().strip('"')
    if not (tok and chat):
        return
    try:
        import urllib.request, urllib.parse
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{tok}/sendMessage", data=data, timeout=10)
    except Exception as e:
        print(f"telegram send failed: {e}", file=sys.stderr)


# ---------------------------------------------------------------- launchd helpers

def _uid() -> str:
    return subprocess.run(["id", "-u"], capture_output=True, text=True).stdout.strip()


def job_labels() -> list[str]:
    out = subprocess.run(["launchctl", "list"], capture_output=True, text=True).stdout
    labels = []
    for ln in out.splitlines():
        parts = ln.split("\t")
        if len(parts) >= 3 and parts[2].startswith(JOB_PREFIXES):
            labels.append(parts[2])
    return sorted(labels)


def job_info(label: str) -> dict:
    out = subprocess.run(
        ["launchctl", "print", f"gui/{_uid()}/{label}"],
        capture_output=True, text=True).stdout
    info = {"label": label, "exit": None, "stdout": None}
    for ln in out.splitlines():
        s = ln.strip()
        if s.startswith("last exit code =") and info["exit"] is None:
            info["exit"] = s.split("=", 1)[1].strip()
        elif s.startswith("stdout path =") and info["stdout"] is None:
            info["stdout"] = s.split("=", 1)[1].strip()
    return info


def has_stale_macl(path: Path) -> bool:
    """True if the file carries a com.apple.macl xattr (TCC per-file access record)."""
    if not path.is_file():
        return False
    out = subprocess.run(["xattr", str(path)], capture_output=True, text=True).stdout
    return "com.apple.macl" in out


# ---------------------------------------------------------------- check A: cadence

def check_cadence(quiet: bool = False) -> int:
    """Heal jobs stuck at EX_CONFIG by archiving their TCC-tainted stdout file."""
    healed, still_broken, pending = [], [], []
    for label in job_labels():
        info = job_info(label)
        if not info["exit"] or "78" not in info["exit"]:
            continue
        p = Path(info["stdout"]) if info["stdout"] else None
        if p and has_stale_macl(p):
            ARCHIVE.mkdir(parents=True, exist_ok=True)
            dest = ARCHIVE / f"{p.name}.tainted-{datetime.now():%Y-%m-%d-%H%M%S}"
            try:
                p.rename(dest)
                healed.append((label, p.name))
            except OSError as e:
                still_broken.append((label, f"archive failed: {e}"))
        elif p and not p.exists():
            # Already healed: the tainted file is gone, so launchd will recreate it
            # clean on the next fire. The 78 here is just a stale last-exit code.
            pending.append(label)
        else:
            still_broken.append((label, "exit 78 but log not macl-tainted — investigate"))

    for label, name in healed:
        print(f"[healed] {label}: archived tainted {name}")
    for label in pending:
        print(f"[pending] {label}: already healed, awaiting next scheduled fire")
    for label, why in still_broken:
        print(f"[BROKEN] {label}: {why}", file=sys.stderr)

    if healed or still_broken:
        lines = ["TradePilot cadence-guard"]
        if healed:
            lines.append(f"Healed {len(healed)} TCC-tainted job log(s):")
            lines += [f"  - {l}" for l, _ in healed]
            lines.append("They will run clean at their next scheduled fire.")
        if still_broken:
            lines.append(f"STILL BROKEN ({len(still_broken)}) — needs a human:")
            lines += [f"  - {l}: {w}" for l, w in still_broken]
        telegram("\n".join(lines))
    elif not quiet:
        print("[ok] no cadence jobs stuck at EX_CONFIG")
    return 1 if still_broken else 0


# ---------------------------------------------------------------- check B: session

# Engines are started by launch-market.sh as `python3 scripts/<name>-paper-trade.py`.
# Deliberately NOT pgrep: macOS pgrep has no -a flag (it is a Linux-ism, silently
# ignored), and `pgrep -f` also matches the invoking shell whose argv contains the
# pattern — which yields a FALSE "session is live" and would silence the very alarm
# this script exists to raise. ps + explicit regex + self-exclusion is unambiguous.
ENGINE_RE = re.compile(r"python[\d.]*\s+\S*scripts/[\w.]+-paper-trade\.py")


def engine_procs() -> list[str]:
    out = subprocess.run(["ps", "-Ao", "pid=,command="],
                         capture_output=True, text=True).stdout
    me = {str(os.getpid()), str(os.getppid())}
    found = []
    for ln in out.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        pid, _, cmd = ln.partition(" ")
        if pid in me:
            continue
        if ENGINE_RE.search(cmd):
            found.append(f"{pid} {cmd[:90]}")
    return found


def engines_running() -> int:
    return len(engine_procs())


def launched_today(today: str) -> bool:
    """The launcher writes a completion banner per run; look for today's date in its log."""
    if not LAUNCH_LOG.exists():
        return False
    try:
        tail = LAUNCH_LOG.read_text(errors="replace").splitlines()[-400:]
    except OSError:
        return False
    return any(today in ln for ln in tail)


def annotate_summary(today: str, reason: str) -> Path | None:
    """Prepend a banner to the day's EOD summary so a lost session is never later
    misread as a genuinely flat market."""
    summary = ROOT / "docs" / "learning" / f"{today}-eod-summary.md"
    if not summary.exists():
        return None
    body = summary.read_text()
    if "NO TRADING SESSION" in body:
        return summary
    banner = (
        f"> **WARNING — NO TRADING SESSION ON {today}.** {reason}\n"
        f"> Any zero/blank P&L below is an artifact of the engines never running, "
        f"NOT a flat market. Do not use this day in any performance comparison.\n"
        f"> _Flagged automatically by `scripts/cadence-guard.py`._\n\n"
    )
    summary.write_text(banner + body)
    return summary


def check_session(quiet: bool = False) -> int:
    now = datetime.now()
    today = f"{now:%Y-%m-%d}"

    if now.weekday() >= 5:
        if not quiet:
            print(f"[skip] {today} is a weekend")
        return 0
    if (now.hour, now.minute) < MARKET_OPEN_HHMM:
        if not quiet:
            print(f"[skip] before market open, nothing to assert yet")
        return 0

    n_eng = engines_running()
    did_launch = launched_today(today)

    if n_eng > 0 or did_launch:
        if not quiet:
            print(f"[ok] session live — engines={n_eng}, launch-log-today={did_launch}")
        STATE.parent.mkdir(parents=True, exist_ok=True)
        STATE.write_text(json.dumps(
            {"date": today, "engines": n_eng, "launched": did_launch,
             "checked_at": now.isoformat()}, indent=2))
        return 0

    # No positive evidence the session ever started.
    reason = ("The launcher never fired — most often the Mac was powered off through the "
              "08:50 window (launchd drops a calendar job missed while off, though it "
              "replays one missed while asleep).")
    marked = annotate_summary(today, reason)
    msg = (f"TradePilot ALARM — NO SESSION {today}\n"
           f"No engines running and no launcher entry for today.\n"
           f"{reason}\n"
           f"{'Annotated ' + marked.name if marked else 'No EOD summary to annotate yet.'}\n"
           f"(Weekday check; NSE holidays are not modelled — ignore if today is a holiday.)")
    print(msg, file=sys.stderr)
    telegram(msg)
    return 1


# ---------------------------------------------------------------- main

def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check-cadence", action="store_true", help="heal TCC-tainted job logs")
    ap.add_argument("--check-session", action="store_true", help="assert engines ran today")
    ap.add_argument("--quiet", action="store_true", help="only print on problems")
    a = ap.parse_args()

    run_all = not (a.check_cadence or a.check_session)
    rc = 0
    if a.check_cadence or run_all:
        rc |= check_cadence(a.quiet)
    if a.check_session or run_all:
        rc |= check_session(a.quiet)
    return rc


if __name__ == "__main__":
    sys.exit(main())
