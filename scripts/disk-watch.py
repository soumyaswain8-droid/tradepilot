#!/usr/bin/env python3
"""
disk-watch — alert before the volume fills, because filling it is unrecoverable.

WHY. On 2026-08-28 an overnight research run took the root volume to zero bytes. On macOS
every write path needs to create a temp file first, so at zero bytes NOTHING could run —
not the analysis, not the editor, not even the `rm` that would have cleared it. Six hours
of scheduled jobs failed silently and the machine had to be rescued through a tool that
happened to use a different code path.

A grep across scripts/ and prototype/ for `df`, `shutil.disk_usage` and `statvfs` returned
NOTHING before this file. quant/diskguard.py refuses to START a research job below 2 GB,
which is a guard on one entry point; it cannot see the volume filling from any other
cause, and it says nothing until something tries to run.

THE POINT IS THE WARNING, NOT THE CHECK. A disk alert is only useful with enough headroom
left to act. Zero bytes is not a state you recover from gracefully — you recover from
5 GB by deleting something. So this alerts EARLY and names the largest consumers, because
an alert that says "disk full" without saying what filled it just moves the diagnosis to
the worst possible moment.

    python3 scripts/disk-watch.py            # check, alert if needed
    python3 scripts/disk-watch.py --report   # always print, never alert
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
STATE = ROOT / "logs" / ".disk-watch-state"

# Two thresholds, deliberately generous. The research jobs routinely allocate a few GB,
# so "critical" is set where a single ordinary job could still tip the volume over.
WARN_GB = 12.0
CRIT_GB = 5.0

# Where the space actually goes on this machine, measured. Checked in this order so the
# alert can name a culprit instead of just a number.
SUSPECTS = [
    ("Docker",       Path.home() / "Library/Containers/com.docker.docker"),
    ("Downloads",    Path.home() / "Downloads"),
    ("Caches",       Path.home() / "Library/Caches"),
    ("market data",  ROOT / "quant/data"),
    ("logs",         ROOT / "logs"),
    ("git objects",  ROOT / ".git"),
]


def free_gb() -> float:
    return shutil.disk_usage(str(ROOT)).free / 1e9


def used_pct() -> float:
    u = shutil.disk_usage(str(ROOT))
    return 100.0 * u.used / u.total


def biggest(n: int = 3) -> list:
    """The largest reclaimable directories, so the alert is actionable.

    `du` on a large tree is slow, so this is only called when an alert is actually
    firing — never on the healthy path, which runs every hour.
    """
    out = []
    for label, p in SUSPECTS:
        if not p.exists():
            continue
        try:
            r = subprocess.run(["du", "-sk", str(p)], capture_output=True,
                               text=True, timeout=90)
            kb = int((r.stdout or "0").split()[0])
            out.append((label, kb / 1e6))
        except Exception:
            continue
    return sorted(out, key=lambda x: -x[1])[:n]


def last_level() -> str:
    try:
        return STATE.read_text().strip()
    except Exception:
        return "OK"


def save_level(lvl: str) -> None:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(lvl)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--report", action="store_true", help="print only, never alert")
    a = ap.parse_args()

    gb, pct = free_gb(), used_pct()
    level = "CRIT" if gb < CRIT_GB else "WARN" if gb < WARN_GB else "OK"

    if a.report:
        print(f"  free {gb:.1f} GB ({pct:.0f}% used) — {level}")
        for label, sz in biggest(6):
            print(f"    {label:<14} {sz:>6.1f} GB")
        return 0

    prev = last_level()
    save_level(level)
    print(f"  {datetime.now():%H:%M} free {gb:.1f} GB ({pct:.0f}% used) — {level}", flush=True)

    # Alert on the way DOWN, and once on recovery. Re-alerting every hour at the same
    # level trains you to ignore it, which is how a real warning gets missed.
    order = {"OK": 0, "WARN": 1, "CRIT": 2}
    if level == prev or (order[level] < order[prev] and level != "OK"):
        return 0

    if level == "OK":
        msg = f"Disk recovered: {gb:.1f} GB free ({pct:.0f}% used)"
    else:
        top = biggest()
        detail = "\n".join(f"  {l}: {s:.1f} GB" for l, s in top)
        msg = (f"DISK {level}: {gb:.1f} GB free ({pct:.0f}% used)\n"
               f"Largest:\n{detail}\n"
               f"At zero bytes nothing can run, including the cleanup.")
    try:
        from prototype.v5 import telegram_bot as tb
        tb.send_alert(msg)
        print("  alert sent", flush=True)
    except Exception as e:
        # An alerting failure must be loud in the log — a silent alerter is worse than
        # none, because it looks like everything is fine.
        print(f"  ALERT FAILED to send: {str(e)[:80]}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
