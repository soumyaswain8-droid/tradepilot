#!/usr/bin/env python3
"""
Cleanup agent for one-shot TradePilot LaunchAgents.

Fires Mon 2026-05-11 at 09:17 IST. By then the EOD comparison (Apr 29) and
research-agent reminder (May 4) have both fired and are dormant. Removes all
three plists (including this one) and sends a Telegram confirmation.

Idempotent — re-running is safe (already-removed files are skipped).
"""
import os
import subprocess
import urllib.parse
import urllib.request
from pathlib import Path

HOME = Path.home()
LAUNCH_DIR = HOME / "Library" / "LaunchAgents"
PROJECT = Path("/Users/soumyaswain/Documents/tinker/projects/tradepilot")

# All one-shot agents to remove. Self-cleanup last.
TARGETS = [
    "com.tradepilot.eod-comparison-2026-04-29",
    "com.tradepilot.research-agent-reminder-2026-05-04",
    "com.tradepilot.cleanup-2026-05-11",
]


def unload_and_remove(label: str) -> str:
    plist = LAUNCH_DIR / f"{label}.plist"
    if not plist.exists():
        return f"{label}: already gone"
    try:
        subprocess.run(
            ["launchctl", "unload", "-w", str(plist)],
            check=False, capture_output=True, timeout=10,
        )
    except Exception as e:
        print(f"  warn: unload {label} -> {e}")
    try:
        plist.unlink()
        return f"{label}: removed"
    except Exception as e:
        return f"{label}: rm failed ({e})"


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
        print(f"  warn: telegram -> {e}")


def main() -> int:
    print("[cleanup] start")
    results = [unload_and_remove(label) for label in TARGETS]
    for r in results:
        print(f"  {r}")
    msg = (
        "🧹 TradePilot cleanup done — one-shot LaunchAgents removed.\n\n"
        + "\n".join(f"• {r}" for r in results)
        + "\n\nWeekly tracker (com.tradepilot.weekly-tracker) preserved."
    )
    telegram(msg)
    print("[cleanup] done")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
