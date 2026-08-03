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
# v1 labels during the migration debugging on 2026-05-16.
#
# CORRECTION (2026-07-28): do NOT bump to v3 if a job starts failing. The taint
# is NOT on the label — it is on the StandardOutPath FILE. Each log file carries a
# `com.apple.macl` xattr recording which code identity may open it; when that stops
# matching launchd's, TCC denies the open, launchd aborts BEFORE exec, and the job
# reports exit 78 (EX_CONFIG) having written nothing. Renaming the label or the log
# filename only ever "worked" because it produced a NEW, clean file as a side effect.
#
# The actual fix is to remove/rotate the tainted file — the label can stay put.
# `scripts/cadence-guard.py --check-cadence` does this automatically and is scheduled
# below. Diagnosed by bisection: a bare `bash -c echo` probe exits 0, and flips to 78
# purely by pointing its StandardOutPath at a tainted file.
LABEL_PREFIX = "com.tradepilot.v2"

# launchd weekday: Sunday=0, Monday=1, ..., Saturday=6.
WEEKDAYS = [1, 2, 3, 4, 5]   # Mon-Fri
SUNDAY = [0]
DAILY = list(range(7))        # 0..6

# Schedule table
# (name, command_args, hour, minute, weekdays, log_filename)
JOBS = [
    # Preflight — 08:50 IST weekdays. Runs the 27-check self-test;
    # pages Telegram via Sarathi BLOCK audit entry on any FAIL.
    # Fires 5 min before DAT (08:55) so issues surface before trading chain.
    # Fresh log filename to avoid TCC taint pattern seen with other jobs.
    ("preflight",
     ["python3", "scripts/team/cadence/preflight.py"],
     8, 50, WEEKDAYS, "preflight-v1.log"),

    ("dqo-premarket",
     ["python3", "scripts/sarathi/verify.py", "--family", "DAT", "--check", "pre-market"],
     8, 55, WEEKDAYS, "dqo-premarket.log"),

    # 3rd Label rename (market-go also TCC-tainted somehow). Fresh names
    # for both Label and log file. Python launcher inside.
    # abandon_process_group=True is CRITICAL: launch-market.sh spawns
    # ~10 nohup'd background processes (engines, watchdogs, telegram).
    # Without it, when market_go.py returns, launchd SIGTERMs the entire
    # group and engines die seconds after start.
    ("engines-on",
     ["python3", "scripts/team/cadence/market_go.py"],
     9, 10, WEEKDAYS, "engines-on.log",
     True),  # abandon_process_group

    ("dqo-mid",
     ["python3", "scripts/sarathi/verify.py", "--family", "DAT", "--check", "mid-market"],
     11, 0, WEEKDAYS, "dqo-mid.log"),

    ("exec-eod",
     ["python3", "scripts/team/slippage.py", "--aggregate"],
     15, 31, WEEKDAYS, "exec-eod.log"),

    ("standup",
     ["bash", ".claude/team/cadence/daily-standup.sh"],
     15, 50, WEEKDAYS, "standup.log"),

    # EOD artifact auto-commit + push (2026-07-24): commits the day's
    # generated artifacts (dailies/audits/EOD summaries/dashboard scores),
    # pushes dev, fast-forwards main. 17:30 = well after the audit (~15:35)
    # and eod-comparison (~16:11) writers. -DRAFT files excluded in-script
    # (pending-review docs must never auto-publish).
    ("eod-git-commit",
     ["bash", "scripts/eod-git-commit.sh"],
     17, 30, WEEKDAYS, "eod-git-commit.log"),

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

    # Fleet card to Telegram, 16:15 — just after eod-comparison writes at ~16:11,
    # so the image reflects the finished day rather than a mid-write snapshot.
    # Renders /fleet with headless Chrome and sends the PNG. Falls back to a text
    # summary if the render fails, so a broken Chrome never means silent nothing.
    # Uses :5050/fleet when the optional :5051 mobile server is not running —
    # verified with :5051 deliberately down.
    ("fleet-telegram",
     ["python3", "scripts/fleet-telegram.py"],
     16, 15, WEEKDAYS, "fleet-telegram.log"),

    # --- Kite token reminders (2026-08-03) ----------------------------------
    # Zerodha invalidates the access_token at 06:00 daily ("regulatory
    # requirement" — their words). Re-auth needs interactive 2FA, so it cannot be
    # automated without storing a password + TOTP seed on disk, which collapses 2FA
    # into 1FA and exposes the ACCOUNT rather than a scoped, revocable API key.
    # We chose notification over automation. Three escalating nudges, and each is
    # SILENT when the token is valid — a reminder that fires daily regardless is one
    # people learn to ignore (preflight's stale ML failures are the live example).
    ("kite-token-morning",
     ["python3", "scripts/kite-token-reminder.py", "--stage", "morning"],
     6, 5, WEEKDAYS, "kite-token-morning.log"),

    ("kite-token-preflight",
     ["python3", "scripts/kite-token-reminder.py", "--stage", "preflight"],
     8, 50, WEEKDAYS, "kite-token-preflight.log"),

    ("kite-token-lastcall",
     ["python3", "scripts/kite-token-reminder.py", "--stage", "lastcall"],
     9, 10, WEEKDAYS, "kite-token-lastcall.log"),

    # --- cadence-guard (2026-07-28) — makes silent failures loud -------------
    # 08:40: heal TCC-tainted logs BEFORE the 08:50 preflight / 09:10 engines-on
    # fire, so a tainted file can never silently kill the trading chain.
    ("guard-cadence",
     ["python3", "scripts/cadence-guard.py", "--check-cadence", "--quiet"],
     8, 40, WEEKDAYS, "guard-cadence.log"),

    # 09:30: assert the session actually started (engines alive / launcher ran
    # today). Catches the 2026-07-27 case: Mac powered off through the 08:50
    # window, launchd silently dropped the missed calendar job, zero trades.
    ("guard-session",
     ["python3", "scripts/cadence-guard.py", "--check-session", "--quiet"],
     9, 30, WEEKDAYS, "guard-session.log"),

    # 15:45: re-assert before the EOD summary is generated, so a lost session is
    # annotated as an outage rather than banked as a genuine flat day.
    ("guard-eod",
     ["python3", "scripts/cadence-guard.py", "--check-session", "--quiet"],
     15, 45, WEEKDAYS, "guard-eod.log"),
]

# Standard PATH a launchd job sees (it's minimal by default; we extend for tooling).
# anaconda3 FIRST — system /usr/local/bin/python3 is x86_64 numpy on this arm64 Mac
# and crashes engines that import numpy via subprocess (caught: v5_classic 2026-05-17).
ENV_PATH = "/Users/soumyaswain/anaconda3/bin:/usr/local/bin:/usr/bin:/bin"


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
               weekdays: list[int], log_file: str,
               abandon_process_group: bool = False) -> str:
    label = f"{LABEL_PREFIX}.{name}"
    # Logs go under logs/auto/v2/ so each plist Label gets a TCC-virgin
    # log path. Earlier launchd failures tainted file paths in TCC's cache
    # such that subsequent writes returned EX_CONFIG with no log output —
    # extremely confusing. A fresh subdirectory sidesteps that entirely.
    log_path = PROJECT_ROOT / "logs" / "auto" / "v2" / log_file
    abandon_xml = ("    <key>AbandonProcessGroup</key>\n    <true/>\n"
                   if abandon_process_group else "")
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
{abandon_xml}  </dict>
</plist>
"""


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--print", action="store_true",
                   help="Dry-run: print plists to stdout instead of writing")
    args = p.parse_args()

    out = []
    for job in JOBS:
        # Optional 7th element: abandon_process_group flag (defaults False)
        if len(job) == 7:
            name, cmd_args, h, m, wds, log_fn, abandon = job
        else:
            name, cmd_args, h, m, wds, log_fn = job
            abandon = False
        plist = make_plist(name, cmd_args, h, m, wds, log_fn,
                           abandon_process_group=abandon)
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
