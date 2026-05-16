#!/usr/bin/env bash
# Pre-launch gate wrapper for launchd.
# Runs Sarathi DAT check first; only invokes launch-market.sh if PASS.
# This replaces the cron `&&` chain (launchd has no native chaining).
set -u
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
cd "$PROJECT_ROOT"

mkdir -p logs/auto

if python3 scripts/sarathi/verify.py --family DAT --check launch-gate >> logs/auto/launch.log 2>&1; then
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] DAT gate PASS — launching engines" >> logs/auto/launch.log
  bash scripts/launch-market.sh >> logs/auto/launch.log 2>&1
else
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] DAT gate BLOCK — engines NOT launched" >> logs/auto/launch.log
  python3 -c "
import sys; sys.path.insert(0, '$PROJECT_ROOT')
from scripts.team.log import log_audit
log_audit('sarathi', action='launch-gate-block', decision='BLOCK',
          subject='launch-market.sh',
          evidence={'reason':'DAT pre-launch gate failed'},
          reason='Engines not launched; check logs/auto/launch.log',
          vetoable_by=['CEO'], rule_family='SARATHI-DAT')
"
  exit 1
fi
