# Recovered scripts — code that ran but lived outside the repo

Recovered 2026-09-01 from `~/Library/Application Support/tradepilot/`.

## Why

Three loaded launchd jobs execute Python from a directory outside this repository. A
migration survey found that **two of the three had no copy in git at all** — they ran
daily, produced artifacts the project depends on, and existed in exactly one place on one
machine. A disk failure would have deleted them with no record they had ever existed.

| Script | Job | Repo copy before recovery |
|---|---|---|
| `eod-comparison-daily.py` | `com.tradepilot.eod-comparison-daily`, 16:11 weekdays | yes — `scripts/external/` |
| `regime-switching-daily-research.py` | `com.tradepilot.regime-switching-daily` | **none** |
| `weekly-cron-renewal-reminder.py` | `com.tradepilot.cron-renewal-weekly` | **none** |

## A correction worth recording

The survey reported `eod-comparison-daily.py` as having *diverged* from its
`scripts/external/` mirror. It has not. The mirror is 326 lines against the deployed
314, and the entire difference is a 12-line `MIRROR — DEPLOYED COPY LIVES OUTSIDE THE
REPO` header. With that header stripped the two are **byte-identical**. A line-count
difference is not divergence, and the mirror discipline held.

## These are backups, not the running code

launchd executes the copies under `~/Library/Application Support/tradepilot/`. Editing a
file here changes nothing. Either edit the deployed copy and refresh this one, or — better
— move these into the repo properly and repoint the plists, which removes the split-brain
entirely.

## The real fix

This directory documents a problem rather than solving it. Executable code should not live
outside version control. The migration plan (`docs/research/cloud/migration-plan.md`)
treats relocating these into `scripts/` and updating the three plists as a prerequisite,
because a cloud VM has no `~/Library/Application Support` to copy from — on a rebuild these
would simply be gone.
