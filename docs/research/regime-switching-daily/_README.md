# Daily Regime-Switching Research — Watchdog

## What lives here

One file per calendar date in `YYYY-MM-DD.md` format. Each file contains:

1. The day's topic (picked by date hash from a 30-topic rotation)
2. The agent prompt to run that day's research
3. The agent's findings (filled by Claude when the cron fires OR when you paste the prompt manually)
4. Sources and comparison notes against prior coverage of the same topic

After ~30 days the rotation cycles, and we accumulate a longitudinal record of how the regime-switching research field evolves — week-over-week, month-over-month.

## Files

| File | Purpose |
|---|---|
| `_README.md` | This file |
| `_topics.md` | The 30-topic rotation, with rationale |
| `YYYY-MM-DD.md` | Daily research entry |

## How it runs

| Layer | Where | When | What it does |
|---|---|---|---|
| LaunchAgent | `~/Library/LaunchAgents/com.tradepilot.regime-switching-daily.plist` | Daily 07:00 IST | Runs the script |
| Script | `~/Library/Application Support/tradepilot/regime-switching-daily-research.py` | Same | Picks today's topic, writes starter file with prompt, sends Telegram |
| In-session cron | session-bound, recurring 07:23 IST | Daily for 7 days, then renew | Auto-fires Claude research agent if a session is open |
| Manual fallback | you | Anytime | Paste the prompt block from today's starter file into Claude |

## Why three layers

- **LaunchAgent** is durable — survives Mac restart, sleep, Claude session death. It always writes the starter file, always sends the Telegram. No autonomous research, but the prompt is on disk waiting.
- **In-session cron** is autonomous — if Claude is running at 07:23 IST it'll do the research itself and update the file. Auto-expires after 7 days; renew weekly with a fresh `CronCreate`.
- **Manual fallback** always works. If both the cron and you forget, the starter file still contains the prompt — just paste it next time you open Claude.

## How to add / remove topics

Edit `_topics.md` (the human-readable index) and the `TOPICS` list in `~/Library/Application Support/tradepilot/regime-switching-daily-research.py`. The next run will pick from the new list.

## How to retire the watchdog

```bash
launchctl unload -w ~/Library/LaunchAgents/com.tradepilot.regime-switching-daily.plist
rm ~/Library/LaunchAgents/com.tradepilot.regime-switching-daily.plist
# Optionally delete script and topic file:
rm ~/Library/Application\ Support/tradepilot/regime-switching-daily-research.py
```

The accumulated daily files in this folder are research artifacts — keep them.

## Comparison workflow

After 7+ days of accumulated research:

```bash
# See all daily research at a glance
ls -la docs/research/regime-switching-daily/20*.md

# See how a specific topic has evolved
grep -l "BOCPD" docs/research/regime-switching-daily/*.md
# Then diff the matching files

# Generate a weekly digest (manually or via prompt)
# Prompt to Claude: "summarise the last 7 days of regime-switching research from
# docs/research/regime-switching-daily/ and identify patterns"
```

## Topic rotation rationale

The 30 topics are chosen so a complete cycle (~30 days) gives a meaningful cross-section of:

- Academic state-of-the-art (topics 1, 24, 28, 29, 30)
- Implementation libraries (2, 3, 7, 25, 26, 27)
- Indian-specific market behaviour (4, 5, 6, 10, 11, 17, 18, 19, 20, 21)
- Industry intelligence (14, 15, 16, 17)
- Microstructure (22, 23)
- Audit / overfitting tools (8, 25, 26)
- Sub-regime features (12, 18, 19, 20, 21)
- Architecture patterns (13, 28, 29, 30)

A second cycle after Day 30 revisits each topic with a fresh search, and the comparison-notes section tracks what's changed.
