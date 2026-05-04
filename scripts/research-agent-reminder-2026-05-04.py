#!/usr/bin/env python3
"""
Telegram reminder fired Mon 2026-05-04 at 08:43 IST.

Pings Soumya with the path to the research agent brief, in case the
in-session Claude cron didn't fire (or the session ended overnight).
"""
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")

env = ROOT / ".env"
token = chat = None
for line in env.read_text().splitlines():
    if line.startswith("TELEGRAM_BOT_TOKEN="):
        token = line.split("=", 1)[1].strip().strip('"')
    elif line.startswith("TELEGRAM_CHAT_ID="):
        chat = line.split("=", 1)[1].strip().strip('"')

msg = (
    "Reminder: SEBI compliance + v6.1 paper-trade feasibility research agent "
    "scheduled for today.\n\n"
    "If your Claude session was open at 08:43, the cron has already fired and "
    "you'll see deliverables in docs/reports/2026-05-04/ shortly.\n\n"
    "If not, open a Claude Code session in the tradepilot dir and paste the "
    "agent prompt from:\n"
    "docs/reports/2026-05-04/RESEARCH_AGENT_BRIEF.md\n\n"
    "Two deliverables:\n"
    "1. COMPLIANCE_ROADMAP.pdf (SEBI April 2026 algo rules)\n"
    "2. V6.1_PAPER_TRADE_FEASIBILITY.pdf (can we paper-trade the multi-agent "
    "system end-to-end)"
)

if token and chat:
    data = urllib.parse.urlencode({"chat_id": chat, "text": msg}).encode()
    urllib.request.urlopen(
        f"https://api.telegram.org/bot{token}/sendMessage",
        data=data, timeout=8,
    )
    print("reminder sent")
else:
    print("WARN: telegram credentials missing in .env")
