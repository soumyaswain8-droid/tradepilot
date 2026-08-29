# Calls capture pipeline

Records what TradePilot published, and what happened to it. The track record
shown to clients is a query over this and nothing else.

**This is time-sensitive.** Every day the publish job does not run is a day of
proof that cannot be recovered — the record cannot be backfilled without
retroactively labelling engine history as calls, which the design rejects.

## The jobs

| Job | When | What it does |
|:--|:--|:--|
| `scripts/publish-calls.py` | 09:20 IST, weekdays | Fetches `/api/picks?category=stocks` and writes one row per pick |
| `scripts/resolve-calls.py` | 18:30 IST, weekdays | Fills the outcome for calls whose horizon has elapsed |
| `scripts/calls-status.py` | on demand | Prints the state of the record; exits 1 if there are missing weekdays |

Both jobs require `prototype/app.py` to be running — they read the same HTTP
endpoints the product serves, so the record is by construction what was
published rather than a recomputation that might differ.

## Checking it is alive

```bash
python3 scripts/calls-status.py
```

Non-zero exit means missing weekdays. Investigate before they accumulate.

## Installing the schedule

The two launchd agents are checked into this repo as templates, not installed
automatically — writing into `~/Library/LaunchAgents` and scheduling a
recurring background job is a decision for whoever runs this on their own
machine, not something a task should do on their behalf.

Templates: `deploy/launchd/co.tradepilot.publish-calls.plist` and
`deploy/launchd/co.tradepilot.resolve-calls.plist`. Both contain the literal
placeholder `/Users/YOURNAME/...` in `ProgramArguments` — substitute your own
home directory before loading them.

```bash
# From the repo root. Substitutes YOURNAME with your actual home directory
# in a copy of each template, then installs the copies.
sed "s#/Users/YOURNAME#$HOME#" deploy/launchd/co.tradepilot.publish-calls.plist \
  > ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist
sed "s#/Users/YOURNAME#$HOME#" deploy/launchd/co.tradepilot.resolve-calls.plist \
  > ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist

launchctl load ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist
launchctl load ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist

launchctl list | grep tradepilot   # expect both labels listed
```

Both jobs will fail at their scheduled time unless `prototype/app.py` is
already running — they read `/api/picks` and the other HTTP endpoints the
product serves, not a direct DB or engine call. Make sure the app server is
up (or itself scheduled to start before 09:20 IST) before relying on the
schedule.

To remove the schedule later:

```bash
launchctl unload ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist
launchctl unload ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist
rm ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist \
   ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist
```

## Rules that must not be relaxed

- The publish job is the **only** writer of `calls`.
- **Stocks only.** `/api/picks?category=etfs` and `?category=mf` return
  hardcoded literal arrays with invented recommendation strings. They are not
  model output and must never be recorded as calls.
- A call inside its horizon stays `open` and is never counted in a hit rate.
- A hit requires reaching the target published with the call.
- A missing price leaves a call open rather than recording a miss it did not earn.
