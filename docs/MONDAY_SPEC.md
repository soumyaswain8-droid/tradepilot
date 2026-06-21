# Monday 2026-06-08 — Market-Open Readiness Spec

**Verdict: READY — one dependency: the Mac must be awake at 09:10.** As of 2026-06-07
everything is automated and VERIFIED: live engines (launchd 09:10, fire confirmed via
kickstart), A/B challengers (launchd 09:12, new ab-engines job), preflight/exec-eod
plists fixed (exit 0, no more 78). The ONLY unreliable link left is the laptop waking
(pmset wake is set but has self-cleared before). So: **plug in + leave lid open Sun night.**
If the Mac is awake at 09:10, the whole stack comes up hands-off. Manual launch commands
below remain as a fallback only.

## What runs Monday (and the goal)
Goal = **collect A/B Day-2** for the model decisions, on a clean session:
- LIVE fleet: v4 (1,735-tree), v5 (with shorts), v5_classic — production engines.
- A/B challengers: old 5-tree v4, long-only v5 — the experiments we're judging.
Override (legacy-model freeze) expires **2026-07-15**; Monday is data-collection, not promotion.

## Automated (via launchd, IF Mac is awake)
| Time IST | Job | Brings up |
|---|---|---|
| 08:45 | pmset wakepoweron | wakes the Mac (⚠ flaky — see risks) |
| 08:50 | preflight plist | config checks (exit-78 — redundant; market_go re-checks) |
| 09:10 | engines-on → market_go.py → launch-market.sh | **caffeinate + wifi-watchdog(→"Pro") + 3 LIVE engines + crash-watchdog + dashboard** |
| 15:31/15:35 | exec-eod / auto-stop | EOD reports + shutdown |

## A/B challengers — NOW AUTOMATED (2026-06-07)
`com.tradepilot.v2.ab-engines` launchd job fires **09:12 weekdays** → runs
`scripts/launch-ab.sh` → both challengers (old-5tree-v4, long-only-v5), caffeinated.
No manual step needed. Fallback if it ever doesn't: `./scripts/launch-ab.sh`.

## Reliable fallback (recommended — don't trust the wake)
The wake/launchd chain failed before and pmset keeps clearing. Safest:
1. **Sun night: plug in AC + leave lid OPEN.**
2. **~09:05 Mon, run both yourself:**
   ```
   cd ~/Documents/tinker/projects/tradepilot
   ./scripts/launch-market.sh      # live stack (if launchd didn't already)
   ./scripts/launch-ab.sh          # A/B challengers
   ```
   (launch-market.sh skips if :5050/engines already running — safe to double-run.)

## Verify at ~09:20
```
pgrep -fl "paper-trade.py" | grep -v oldengine | grep -v longonly   # 3 live engines
pgrep -fl "oldengine-ab\|longonly-ab"                                # 2 A/B engines
```
Or open the dashboards:
- **/live** (FLEET COMMAND) — MARKET should read OPEN, livedot green, trades populate.
- **/lab** (A/B) — challenger vs live cards fill in; long-only gate badge "0 shorts".

## EOD (~15:35)
- /live + /lab show the day; session strip adds 06-08.
- Read the A/B deltas (old-v4 vs live-v4, long-only-v5 vs live-v5). 2-3 clean days → decide v4 model revert.

## Residual risks (be honest)
1. **pmset wake is unreliable** — re-set Sat, but it has cleared twice. If the Mac
   is asleep at 09:10 and doesn't wake, NOTHING launches. → plug in + lid open + manual launch.
2. **launchd engines-on** now exits 0 (fix applied) but hasn't been seen firing live
   since the fix. Monday is its first real test.
3. **preflight/exec-eod plists exit 78** — redundant (market_go + auto-stop cover them), non-fatal.
4. **Rust** intentionally off (optional) — engines run Python-only, fine.
5. **Disk 98% used (3.9G free)** — OK for a day; watch it.
6. A/B engines auto-stop at EOD and do NOT auto-restart next day — run launch-ab.sh each trading morning until moved to an always-on box.

## The durable fix (post-Monday)
The recurring wake/sleep/launchd fragility is the case for moving the engines off
the laptop to an always-on box (cloud VM / Mac mini) before 2026-07-15.
