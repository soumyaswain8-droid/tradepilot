#!/usr/bin/env python3
"""
Weekly cron-renewal reminder.

Fires every Sunday at 06:50 IST. Sends a Telegram with the exact prompt to
paste into Claude to renew the autonomous daily-research cron for another 7
days (CronCreate auto-expires after 7 days, so weekly renewal is needed if
you want the autonomous research layer to stay alive).

The LaunchAgent layer (regime-switching-daily-research.py) keeps running
without renewal — it's the in-session cron that needs weekly poking.
"""
from __future__ import annotations

import sys
import urllib.parse
import urllib.request
from datetime import date
from pathlib import Path

PROJECT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")

RENEWAL_PROMPT = """Renew the daily regime-switching research cron for another 7 days.

Use CronCreate with these exact parameters:
- cron: "23 7 * * *"
- recurring: true
- durable: true
- prompt: (the exact same daily-research prompt — see docs/research/regime-switching-daily/_README.md and the prior week's cron job for the canonical prompt)

After scheduling, send me a Telegram confirming the new cron ID.

Also: run a quick health check on the daily watchdog:
- LaunchAgent loaded? launchctl list | grep regime-switching-daily
- Last 3 daily files exist? ls docs/research/regime-switching-daily/20*.md | tail -3
- Any failures in ~/Library/Logs/tradepilot-regime-switching-daily.err?"""


def telegram(msg: str) -> None:
    env = PROJECT / ".env"
    if not env.exists():
        return
    token = chat = None
    for line in env.read_text().splitlines():
        if line.startswith("TELEGRAM_BOT_TOKEN="):
            token = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("TELEGRAM_CHAT_ID="):
            chat = line.split("=", 1)[1].strip().strip('"')
    if not (token and chat):
        return
    try:
        data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
        urllib.request.urlopen(
            f"https://api.telegram.org/bot{token}/sendMessage",
            data=data, timeout=8,
        )
    except Exception as e:
        print(f"warn: telegram failed: {e}", file=sys.stderr)


def main() -> int:
    today = date.today()
    msg = (
        f"🔁 Sunday {today.isoformat()} — weekly cron renewal reminder.\n\n"
        "The autonomous daily regime-switching research cron expires after 7 days. "
        "Open Claude in the tradepilot project and paste:\n\n"
        f"{RENEWAL_PROMPT}\n\n"
        "(The LaunchAgent layer runs daily without renewal. Only the in-session "
        "cron needs weekly poking.)"
    )
    telegram(msg)
    print(f"[renewal-reminder] sent for {today.isoformat()}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
