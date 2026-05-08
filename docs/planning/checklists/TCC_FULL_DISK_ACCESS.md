# Task #22 — Grant Full Disk Access to /bin/bash

**Status:** Awaiting manual user action — cannot be scripted (macOS Privacy & Security model).

## Why this matters

The `launchd` job at `~/Library/LaunchAgents/com.soumya.tradepilot-launch.plist`
fires Mon-Fri 08:45 IST and runs `scripts/launch-market.sh`. macOS TCC blocks
launchd-spawned bash from reading `.py` files in `~/Documents/`, causing the
auto-launched engines to fail silently. Yesterday morning's auto-launch hit this.

Without this fix, every Monday morning the auto-launch may fail and you'll need
to manually re-launch from Terminal at 08:50 IST.

## The fix (30 seconds, one-time)

1. Open **System Settings**
2. Click **Privacy & Security** (left sidebar)
3. Scroll down and click **Full Disk Access**
4. Click the **+** button (you may need to authenticate with Touch ID / password)
5. Press **Cmd+Shift+G** to bring up the path input
6. Type `/bin/bash` and press Return
7. Click **Open**
8. Toggle the switch ON for `/bin/bash`
9. Repeat steps 4-8 for `/bin/zsh` (belt + suspenders for hybrid scripts)
10. **No restart needed.** Changes take effect immediately for new processes.

## Verify

Run:
```bash
~/Documents/tinker/projects/tradepilot/scripts/launch-market.sh --status
```

You should see all 7 engines reported as alive when launched via launchd next Monday.

## If you skip this

Each Monday morning, after 08:45 IST, check:
```bash
tail -20 ~/Library/Logs/tradepilot-launch.log
```

If you see "Engines: 0/7" or "Engines: 1/7" instead of "Engines: 7/7", manually run:
```bash
~/Documents/tinker/projects/tradepilot/scripts/launch-market.sh
```

## Background

Documented in `~/.claude/projects/-Users-soumyaswain/memory/project_tradepilot_autolaunch.md`.
Same TCC issue affects OmniPilot (different memory note) — and is the reason
launchd stdout/stderr paths in `~/Documents/` always fail with exit code 78.
