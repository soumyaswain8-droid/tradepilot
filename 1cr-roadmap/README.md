# ₹1 crore roadmap

Everything relating to the ₹1 crore target — trading profit and product revenue
together — lives here. Daily machine artifacts (standup, audit, missed-trades,
work-log, regime-switching dailies) stay in `docs/`; this folder is the hand-authored
thread only.

## The target, against where the engines actually are

Staged trading returns: 30% to begin, then 40%, then 50%, scale capital once 70% is
cleared.

| Return goal | Needed per day | Needed per trade | Versus today |
|:--|--:|--:|:--|
| 30% | 0.105% | ₹23.52 | 4.6× the current gross edge |
| 40% | 0.135% | ₹30.17 | 5.4× |
| 50% | 0.162% | ₹36.36 | 6.2× |
| 70% | 0.212% | ₹47.60 | 7.5× |

Today the primary engine returns **−0.031% per day**. The gross edge is 0.069% per
trade against a 0.120% cost, so **the first milestone is zero, not 30%** — every
multiple above assumes the edge first clears the toll, and it does not yet.

Revenue side, which does not depend on the strategy working: ₹1 crore is roughly
835 subscribers at ₹999/month held for a year, or 278 at ₹2,999.

## What is where

| Folder | Contents |
|:--|:--|
| `weekly-report/` | Weekly reviews on the TradePilot letterhead (`.md` + `.pdf`) |
| `plan/` | The active plan — signal rebuild |
| `research/` | Backtests, feasibility studies, gap analyses |
| `design/` | Design specs for sensors, gates and data guards |
| `us-market/` | US expansion: brokers, data sources, LRS/tax constraints |

## Regenerating a weekly report

```bash
scripts/render-weekly.sh 1cr-roadmap/weekly-report/<report>.md
```

Renders via `dp content render` (falls back to pandoc+weasyprint if the devpilot DB is
down), then verifies the letterhead mark actually drew and the report is within its
4-page budget. It exits non-zero on either failure — both of which otherwise pass
silently with exit code 0.

## Moving documents in or out

Use `scripts/consolidate-1cr-docs.py`. These files are cited from live code, tests and
each other; the script moves a file and rewrites every reference in the same pass so
the two cannot drift. Run it without `--apply` first to see the plan. Note it cannot
match a path that is **line-wrapped across two lines** in a comment — check for those
by hand afterwards.
