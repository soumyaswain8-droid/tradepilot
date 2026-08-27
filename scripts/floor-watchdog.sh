#!/bin/bash
# floor-watchdog — is the agent floor still alive, and restart it once if not.
#
# WHY THIS EXISTS. The floor is scheduled at 09:16 and nothing checked on it
# afterwards; crash-watchdog.sh covers the paper engines and is not itself scheduled
# by any launchd job. A mid-session crash would therefore be invisible until the EOD
# summary came back empty — and an empty summary on an observation day is
# indistinguishable from "the market was quiet", which is precisely the failure that
# voided a v5_size experiment day once already.
#
# LIVENESS SIGNAL: the floor prints a status line to its log every 30 seconds. A log
# untouched for STALE_S during the session means it is dead, whatever `pgrep` thinks
# — a hung process that has stopped consuming ticks is just as broken as an absent
# one, and pgrep cannot tell them apart.
#
# Restarts are capped so a crash-on-startup cannot become a restart loop that spends
# the session relaunching instead of watching.
set -u
cd "$(dirname "$0")/.." || exit 1

DAY=$(date +%Y-%m-%d)
LOG="logs/agent-floor-$DAY.log"
WLOG="logs/floor-watchdog-$DAY.log"
STAMP="logs/.floor-restarts-$DAY"
STALE_S=210            # 3.5 min — the floor speaks every 30s
# Raised from 2 on 2026-08-27: both of that day's restarts were legitimate and both
# succeeded, so the cap became the binding constraint rather than a runaway guard.
# It is safer to raise now because the script VERIFIES each relaunch took — a restart
# loop would be visible in the log rather than silent.
MAX_RESTARTS=4
PY=/Users/soumyaswain/anaconda3/bin/python3
mkdir -p logs

say(){ echo "$(date '+%H:%M:%S') $*" | tee -a "$WLOG"; }

# only meaningful inside the session.
# 10# forces base 10: date pads to "08"/"09", which bash parses as OCTAL, and 08 is
# not a valid octal literal — so this arithmetic aborted the script at every check
# before 10:00, exactly when the floor most needs watching.
mins=$(( 10#$(date +%H) * 60 + 10#$(date +%M) ))
if [ "$(date +%u)" -ge 6 ] || [ "$mins" -lt 560 ] || [ "$mins" -ge 930 ]; then
  exit 0
fi

alive=0
pgrep -f "prototype.agents.floor" > /dev/null 2>&1 && alive=1

fresh=0
if [ -f "$LOG" ]; then
  age=$(( $(date +%s) - $(stat -f %m "$LOG") ))
  [ "$age" -lt "$STALE_S" ] && fresh=1
else
  age=-1
fi

# THE TICK COUNTER IS THE ONLY REAL LIVENESS SIGNAL.
#
# Measured 2026-08-25, first live session: the WebSocket went silent at 10:44 and
# stayed silent for 15 minutes while REST showed SAIL trading 44,471 shares in six
# seconds. The process held its PID and the main loop kept printing its status line
# every 30s, so BOTH earlier checks — pgrep and log freshness — reported healthy
# throughout. The socket was a zombie: alive to the OS, silent to us.
#
# The status line carries a running tick total. If that number has not moved across
# the last few lines, no data is arriving, whatever else looks fine.
# Scope to the CURRENT run only. The counter restarts at zero on every relaunch, so
# a window straddling a restart reads 48120 -> 353 and looks like death — which made
# this watchdog restart a floor it had just started, one check away from burning its
# own restart budget. Everything before the last STREAM LIVE belongs to a dead run.
ticks_moving=0
first=""; last=""
if [ -f "$LOG" ]; then
  vals=$(awk '/STREAM LIVE/{buf=""} /\] [0-9,]+ ticks/{buf=buf $0 "\n"} END{printf "%s", buf}' \
         "$LOG" 2>/dev/null | grep -oE '\] [0-9,]+ ticks' | tr -d ',' \
         | awk '{print $2}' | tail -4)
  n_vals=$(echo "$vals" | grep -c . )
  first=$(echo "$vals" | head -1); last=$(echo "$vals" | tail -1)
  if [ "${n_vals:-0}" -lt 3 ]; then
    ticks_moving=1                      # too early in this run to judge
  elif [ -n "$first" ] && [ -n "$last" ] && [ "$last" -gt "$first" ]; then
    ticks_moving=1
  fi
fi

if [ "$alive" -eq 1 ] && [ "$fresh" -eq 1 ] && [ "$ticks_moving" -eq 1 ]; then
  say "OK — floor running, log ${age}s old, ticks advancing (${first:-?} -> ${last:-?})"
  exit 0
fi

n=$(cat "$STAMP" 2>/dev/null || echo 0)
say "DEAD — process=$alive log_age=${age}s ticks_moving=$ticks_moving \
(${first:-?} -> ${last:-?}) (restarts so far: $n)"

if [ "$n" -ge "$MAX_RESTARTS" ]; then
  say "restart cap reached — NOT relaunching. Investigate $LOG"
  exit 1
fi

pkill -f "prototype.agents.floor" 2>/dev/null
sleep 2

# RESTART VIA LAUNCHD, NOT nohup.
#
# Measured 2026-08-25: this watchdog is itself a launchd job, and both of its
# nohup'd relaunches were dead within ten minutes having written NOTHING to the log
# — not even a traceback. launchd tracks the job's process group and reaps what is
# left when the script exits, so a background child of a launchd job cannot outlive
# its parent. The watchdog reported "relaunched", the floor was already gone, and
# the session lost 2h40m.
#
# kickstart -k restarts the floor's OWN launchd job, which launchd then owns and
# keeps alive independently of this script.
LABEL="gui/$(id -u)/com.tradepilot.agent-floor"
if launchctl kickstart -k "$LABEL" 2>>"$WLOG"; then
  say "relaunched via launchd $LABEL (restart $((n + 1))/$MAX_RESTARTS)"
else
  # fall back to a detached process, disowned so it survives this shell
  setsid $PY -m prototype.agents.floor --dry >> "$LOG" 2>&1 < /dev/null &
  disown 2>/dev/null || true
  say "launchctl kickstart failed — fell back to setsid (restart $((n + 1))/$MAX_RESTARTS)"
fi
echo $((n + 1)) > "$STAMP"

# Verify the relaunch actually took. "I issued a restart" is not "it is running" —
# that gap is precisely what hid the failure for two and a half hours.
sleep 12
if pgrep -f "prototype.agents.floor" > /dev/null 2>&1; then
  say "verified: floor process is up after restart"
else
  say "RESTART DID NOT TAKE — no floor process 12s after relaunch. Investigate $LOG"
fi
exit 1
