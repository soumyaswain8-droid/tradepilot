"""
Generates launchd plist files for the TradePilot Quant Desk schedule.

Plists go to ~/Library/LaunchAgents/com.tradepilot.<name>.plist
Each plist runs as the user (no FDA needed; user permissions inherited).

Usage:
  python3 scripts/team/cadence/_plist_gen.py            # generate
  python3 scripts/team/cadence/_plist_gen.py --print    # dry-run, print to stdout
"""
from __future__ import annotations
import argparse
import os
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[3]
LAUNCH_AGENTS = Path.home() / "Library" / "LaunchAgents"
LAUNCH_AGENTS.mkdir(parents=True, exist_ok=True)
# v2: bumped from "com.tradepilot" because macOS TCC cached denials against
# v1 labels during the migration debugging on 2026-05-16. Bumping the
# namespace gives all jobs a fresh TCC slate. If any v2 label gets denied
# in future, bump to v3.
LABEL_PREFIX = "com.tradepilot.v2"

# launchd weekday: Sunday=0, Monday=1, ..., Saturday=6.
WEEKDAYS = [1, 2, 3, 4, 5]   # Mon-Fri
SUNDAY = [0]
DAILY = list(range(7))        # 0..6

# Schedule table
# (name, command_args, hour, minute, weekdays, log_filename)
JOBS = [
    ("dqo-premarket",
     ["python3", "scripts/sarathi/verify.py", "--family", "DAT", "--check", "pre-market"],
     8, 55, WEEKDAYS, "dqo-premarket.log"),

    ("launch-market",
     ["bash", ".claude/team/cadence/launch-with-gate.sh"],
     9, 10, WEEKDAYS, "launch.log"),

    ("dqo-mid",
     ["python3", "scripts/sarathi/verify.py", "--family", "DAT", "--check", "mid-market"],
     11, 0, WEEKDAYS, "dqo-mid.log"),

    ("exec-eod",
     ["python3", "scripts/team/slippage.py", "--aggregate"],
     15, 31, WEEKDAYS, "exec-eod.log"),

    ("standup",
     ["bash", ".claude/team/cadence/daily-standup.sh"],
     15, 50, WEEKDAYS, "standup.log"),

    ("due-alpha-hunter",
     ["python3", "scripts/team/cadence/check-due.py", "--mark", "alpha-hunter",
      "Weekly IC + feature drift audit"],
     16, 0, [5], "due.log"),    # Friday only

    ("due-competitive-intel",
     ["python3", "scripts/team/cadence/check-due.py", "--mark", "competitive-intel",
      "Weekly Qlib/FinRL/arxiv scan"],
     19, 0, SUNDAY, "due.log"),

    ("due-architect",
     ["python3", "scripts/team/cadence/check-due.py", "--mark", "architect",
      "Sprint review + next week planning"],
     19, 5, SUNDAY, "due.log"),

    # Python rewrite — bash version hit inconsistent macOS TCC EX_CONFIG
    # under launchd. See nightly_backup.py header for context.
    ("bk-daily",
     ["python3", "scripts/team/cadence/nightly_backup.py"],
     23, 0, DAILY, "backup.log"),
]

# Standard PATH a launchd job sees (it's minimal by default; we extend for tooling)
ENV_PATH = "/usr/local/bin:/usr/bin:/bin:/Users/soumyaswain/anaconda3/bin"


def cal_intervals_xml(hour: int, minute: int, weekdays: list[int]) -> str:
    parts = ["    <key>StartCalendarInterval</key>", "    <array>"]
    for d in weekdays:
        parts.append("      <dict>")
        parts.append(f"        <key>Weekday</key><integer>{d}</integer>")
        parts.append(f"        <key>Hour</key><integer>{hour}</integer>")
        parts.append(f"        <key>Minute</key><integer>{minute}</integer>")
        parts.append("      </dict>")
    parts.append("    </array>")
    return "\n".join(parts)


def _xml_esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def program_args_xml(args: list[str]) -> str:
    """
    Wrap every command in `bash -c "cd <project> && <command>"` so launchd
    spawns /bin/bash (system-trusted) rather than directly exec'ing user
    scripts. The `cd` ensures relative paths inside the inner command
    resolve correctly even though WorkingDirectory is also set as belt
    and suspenders.
    """
    inline = " ".join(_shellquote(a) for a in args)
    cmd = f"cd {_shellquote(str(PROJECT_ROOT))} && {inline}"
    parts = [
        "    <key>ProgramArguments</key>",
        "    <array>",
        "      <string>/bin/bash</string>",
        "      <string>-c</string>",
        f"      <string>{_xml_esc(cmd)}</string>",
        "    </array>",
    ]
    return "\n".join(parts)


def _shellquote(s: str) -> str:
    """Minimal shell quoting for arguments inside a bash -c string."""
    if not s or any(c in s for c in " \t\"'\\$`"):
        # Wrap in single quotes; escape any embedded single quotes
        return "'" + s.replace("'", "'\\''") + "'"
    return s


def make_plist(name: str, args: list[str], hour: int, minute: int,
               weekdays: list[int], log_file: str) -> str:
    label = f"{LABEL_PREFIX}.{name}"
    # Logs go under logs/auto/v2/ so each plist Label gets a TCC-virgin
    # log path. Earlier launchd failures tainted file paths in TCC's cache
    # such that subsequent writes returned EX_CONFIG with no log output —
    # extremely confusing. A fresh subdirectory sidesteps that entirely.
    log_path = PROJECT_ROOT / "logs" / "auto" / "v2" / log_file
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>{label}</string>

{program_args_xml(args)}

    <key>WorkingDirectory</key>
    <string>{PROJECT_ROOT}</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>{ENV_PATH}</string>
    </dict>

{cal_intervals_xml(hour, minute, weekdays)}

    <key>StandardOutPath</key>
    <string>{log_path}</string>
    <key>StandardErrorPath</key>
    <string>{log_path}</string>

    <key>RunAtLoad</key>
    <false/>
    <key>ProcessType</key>
    <string>Background</string>
  </dict>
</plist>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--print", action="store_true",
                   help="Dry-run: print plists to stdout instead of writing")
    args = p.parse_args()

    out = []
    for (name, cmd_args, h, m, wds, log_fn) in JOBS:
        plist = make_plist(name, cmd_args, h, m, wds, log_fn)
        path = LAUNCH_AGENTS / f"{LABEL_PREFIX}.{name}.plist"
        if args.print:
            out.append(f"# === {path.name} ===\n{plist}")
        else:
            path.write_text(plist, encoding="utf-8")
            out.append(f"wrote {path}")

    print("\n".join(out))
    print(f"\n{len(JOBS)} plist(s) {'previewed' if args.print else 'written'}.")


if __name__ == "__main__":
    main()
