# Incident record — 2026-07-28: three stacked silent failures

**Author:** Soumya Swain <soumya@suryaai.co.in>
**Status:** Resolved, with 2 open follow-ups
**Theme:** every failure below was invisible because *absence of a signal* was never monitored.

---

## 1. Monday 2026-07-27 — a whole trading session was lost

The Mac was powered off through the 08:50 launch window; boot was 12:25, after market open.
**launchd replays a `StartCalendarInterval` firing missed while the machine was ASLEEP, but
silently drops one missed while it was POWERED OFF.** No engines ran. The EOD summary
honestly reported "Rs +0 across 0 trades" — indistinguishable from a genuinely flat market.

`docs/learning/2026-07-27-eod-summary.md` now carries an outage banner. Do not use 07-27 in
any performance comparison.

## 2. Every cadence job had been dead for up to 9 weeks

`com.tradepilot.v2.*` since **2026-05-22**, `engine-compare` since **2026-07-03**. All exited
**78 (EX_CONFIG)** having written **nothing** to their logs.

**Root cause:** the job's `StandardOutPath` file carried a stale `com.apple.macl` xattr —
TCC's *per-file* access record — naming a code identity that no longer matched launchd's.
TCC denied opening the file for stdout, so launchd aborted **before `exec`**. No process,
therefore no output, therefore no error anyone could see.

**Proven by bisection:** a bare `bash -c echo` probe plist exits 0, and flips to 78 purely by
pointing its `StandardOutPath` at a tainted file. Archiving the file restores exit 0.

Three hypotheses were refuted first — TCC on the *directory*, `WorkingDirectory`, and a stale
LWCR (LightWeight Code Requirement). Recording them because each looked plausible.

**Correction to prior repo guidance:** `_plist_gen.py` said to bump the label prefix to `v3`
on TCC denial. The taint is per-**file**, not per-label — that remedy only ever appeared to
work because it produced a new, clean file as a side effect, so it silently rotted again.
Header corrected in place.

**Fix:** tainted logs archived (moved, never deleted) to
`logs/auto/v2/_tcc-tainted-archive/`. `scripts/cadence-guard.py` now self-heals this
automatically at 08:40 daily.

**Verified same day** — all five previously-dead jobs ran unattended and exited 0:
`exec-eod` 15:31, `engine-compare` 15:40, `guard-eod` 15:45, `standup` 15:50,
`eod-git-commit` 17:30 (which committed and pushed `463f84d`).

## 3. Mid-session engine outage — the rescue mechanism was the failure

| Time | Event |
|---|---|
| 08:50 | 9 engines launch healthy via `bash -l` → anaconda python3 |
| 09:25 | `v5_cut` dies. `post-open-check` runs the **full** `launch-market.sh` under `bash -c` → `/usr/bin/python3`, **no numpy**. Spawns a *second* fleet of 9 crippled engines; the `>` redirect truncates the originals' day logs |
| 09:25–10:10 | Two fleets share the same `positions_active.json` / carry-forward state |
| ~10:11 | 17 of 18 processes dead; 8 open positions unmanaged |
| 10:47 | Clean stop + relaunch with anaconda forced → 9/9 healthy, positions resumed |

**Root cause:** `launch-market.sh` spawns engines with a bare `python3` and sets no PATH, so
the interpreter comes from whoever invoked it. `post-open-check`'s plist had no
`EnvironmentVariables` at all.

**Measurement trap:** you cannot measure a launchd job's PATH from your own shell. An
interactive-shell test reported the *opposite* answer (that `bash -l` gave the broken
interpreter) because the ambient PATH leaked in. Only this reproduces what the job sees:

```bash
env -i PATH=<plist PATH> HOME=$HOME /bin/bash [-l] -c 'which python3'
```

**Fix:** anaconda-first PATH added to the plist; copy kept at
`scripts/launchagents/com.tradepilot.post-open-check.plist` (the live plist is otherwise
untracked and one machine-rebuild from being lost).

---

## Data integrity — today is NOT clean

Two fleets shared state 09:25–10:10, then a 36-minute gap to 10:47. **2026-07-28 paper-trade
numbers are not trustworthy** — exclude from the v5_chop / v5_rrg / v5_gate shadow comparison
due ~2026-08-04. 2026-07-27 is a total loss (see §1).

## Open follow-ups

1. **crash-watchdog's inaction is UNEXPLAINED.** It was alive from 09:25, engines died ~10:11,
   and it restarted nothing. Ruled out: engine coverage (the array lists all 9 — the
   `# Active engines (5)` comment is stale and misled the first diagnosis) and the `is_alive`
   gate (pgrep on script path, then heartbeat-freshness fallback; a missing file correctly
   falls through to restart). Cause still unknown — do not "fix" it without root cause.
2. **`post-open-check` duplicate-fleet bug.** Restarts *everything* when *one* engine dies,
   with no already-running guard, and truncates logs with `>`. Documented in the script
   header; not yet fixed.

## Deliberately NOT changed

`preflight.py` does not consult the `retired` marker in `verification_report.json`, so it
fails daily on a model retired 2026-07-23 (MLOps gate BLOCKED / CEO override expired 07-25).
**Soumya chose to keep this as a deliberate nag** until ML-001 is settled. Leave it.
