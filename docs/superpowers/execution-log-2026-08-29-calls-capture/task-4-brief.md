### Task 4: Scheduling and visibility

A pipeline nobody can see the state of is a pipeline that stops without anyone noticing. This task makes it observable, then schedules it.

**Files:**
- Create: `scripts/calls-status.py`
- Create: `docs/CALLS_PIPELINE.md`
- Create: `tests/test_calls_status.py`

**Interfaces:**
- Consumes: `app_store.get_db(path)`, `app_store.init_db(conn)`.
- Produces: `calls_status.summarise(conn, now)` → `dict` with keys `total`, `open`, `resolved`, `hit`, `miss`, `hit_rate`, `first_call`, `last_call`, `days_covered`, `gaps`. `hit_rate` is `None` when `resolved` is 0 — never `0.0`, which would read as "we get everything wrong".

- [ ] **Step 1: Write the failing tests**

Create `tests/test_calls_status.py`:

```python
"""Tests for the pipeline status summary."""
import importlib.util
import os
import sys

import pytest

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def _load(name, relpath):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(REPO_ROOT, relpath))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


calls_status = _load("calls_status", "scripts/calls-status.py")


@pytest.fixture
def conn(tmp_path):
    c = app_store.get_db(str(tmp_path / "test_app.db"))
    app_store.init_db(c)
    yield c
    c.close()


def _add(conn, cid, symbol, day, outcome="open"):
    conn.execute(
        "INSERT INTO calls (id, symbol, side, published_at, price_at_call, outcome)"
        " VALUES (?,?,?,?,?,?)",
        (cid, symbol, "BUY", day + "T09:20:00", 1000.0, outcome))
    conn.commit()


def test_empty_store_reports_zero_not_an_error(conn):
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert s["total"] == 0
    assert s["hit_rate"] is None


def test_hit_rate_is_none_when_nothing_resolved(conn):
    """None, never 0.0 -- zero would read as 'we get everything wrong'."""
    _add(conn, "c1", "CIPLA", "2026-08-28")
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert s["open"] == 1
    assert s["resolved"] == 0
    assert s["hit_rate"] is None


def test_hit_rate_counts_only_resolved_calls(conn):
    _add(conn, "c1", "CIPLA", "2026-08-26", "hit")
    _add(conn, "c2", "TITAN", "2026-08-26", "miss")
    _add(conn, "c3", "SUNTV", "2026-08-28", "open")
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert s["resolved"] == 2
    assert s["hit_rate"] == 50.0


def test_gaps_lists_weekdays_with_no_calls(conn):
    """A day the job did not run is the failure this whole script exists to show."""
    _add(conn, "c1", "CIPLA", "2026-08-26")   # Wednesday
    _add(conn, "c2", "TITAN", "2026-08-28")   # Friday
    s = calls_status.summarise(conn, "2026-08-28T18:00:00")
    assert "2026-08-27" in s["gaps"]


def test_weekends_are_not_gaps(conn):
    _add(conn, "c1", "CIPLA", "2026-08-28")   # Friday
    _add(conn, "c2", "TITAN", "2026-08-31")   # Monday
    s = calls_status.summarise(conn, "2026-08-31T18:00:00")
    assert "2026-08-29" not in s["gaps"]      # Saturday
    assert "2026-08-30" not in s["gaps"]      # Sunday
```

- [ ] **Step 2: Run to verify they fail**

```bash
python3 -m pytest tests/test_calls_status.py -q
```

Expected: collection error — `scripts/calls-status.py` does not exist.

- [ ] **Step 3: Write the status script**

Create `scripts/calls-status.py`:

```python
#!/usr/bin/env python3
"""Print the state of the calls record.

A capture pipeline nobody can see is a pipeline that stops without anyone
noticing -- and every day it is stopped is a day of proof that cannot be
recovered. Run this whenever you want to know the record is alive.
"""
import os
import sys
from datetime import datetime, timedelta

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)

from prototype import app_store


def summarise(conn, now):
    """Aggregate the record. `now` is supplied so this stays testable."""
    rows = conn.execute("SELECT published_at, outcome FROM calls").fetchall()
    total = len(rows)
    hit = sum(1 for r in rows if r["outcome"] == "hit")
    miss = sum(1 for r in rows if r["outcome"] == "miss")
    open_ = sum(1 for r in rows if r["outcome"] == "open")
    resolved = hit + miss

    days = sorted({r["published_at"][:10] for r in rows})
    gaps = []
    if days:
        cur = datetime.fromisoformat(days[0]).date()
        end = datetime.fromisoformat(now[:10]).date()
        have = set(days)
        while cur <= end:
            # Monday is 0, Saturday 5, Sunday 6. A closed market is not a gap.
            if cur.weekday() < 5 and cur.isoformat() not in have:
                gaps.append(cur.isoformat())
            cur += timedelta(days=1)

    return {
        "total": total, "open": open_, "resolved": resolved,
        "hit": hit, "miss": miss,
        # None, never 0.0 -- an unresolved record is not a record of failure.
        "hit_rate": round(100.0 * hit / resolved, 1) if resolved else None,
        "first_call": days[0] if days else None,
        "last_call": days[-1] if days else None,
        "days_covered": len(days),
        "gaps": gaps,
    }


def main():
    conn = app_store.get_db()
    app_store.init_db(conn)
    s = summarise(conn, datetime.now().isoformat(timespec="seconds"))
    conn.close()

    print("calls recorded    %d  (%d open, %d resolved)"
          % (s["total"], s["open"], s["resolved"]))
    print("hit rate          %s"
          % ("%.1f%% of %d resolved" % (s["hit_rate"], s["resolved"])
             if s["hit_rate"] is not None else "-- (nothing resolved yet)"))
    print("covering          %s to %s  (%d trading days)"
          % (s["first_call"] or "--", s["last_call"] or "--", s["days_covered"]))
    if s["gaps"]:
        print("MISSING DAYS      %d: %s" % (len(s["gaps"]), ", ".join(s["gaps"][:10])))
        return 1
    print("gaps              none")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run to verify they pass**

```bash
python3 -m pytest tests/test_calls_status.py -q
```

Expected: 5 passed.

- [ ] **Step 5: Write the operator documentation**

Create `docs/CALLS_PIPELINE.md`:

```markdown
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

## Rules that must not be relaxed

- The publish job is the **only** writer of `calls`.
- **Stocks only.** `/api/picks?category=etfs` and `?category=mf` return
  hardcoded literal arrays with invented recommendation strings. They are not
  model output and must never be recorded as calls.
- A call inside its horizon stays `open` and is never counted in a hit rate.
- A hit requires reaching the target published with the call.
- A missing price leaves a call open rather than recording a miss it did not earn.
```

- [ ] **Step 6: Schedule both jobs**

Create the two launchd agents. Replace `YOURNAME` with the output of `whoami`:

```bash
cat > ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>co.tradepilot.publish-calls</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOURNAME/Documents/tinker/projects/tradepilot/scripts/publish-calls.py</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>1</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>2</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>3</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>9</integer><key>Minute</key><integer>20</integer><key>Weekday</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/tradepilot-publish-calls.log</string>
  <key>StandardErrorPath</key><string>/tmp/tradepilot-publish-calls.log</string>
</dict></plist>
EOF

cat > ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
  <key>Label</key><string>co.tradepilot.resolve-calls</string>
  <key>ProgramArguments</key><array>
    <string>/usr/bin/python3</string>
    <string>/Users/YOURNAME/Documents/tinker/projects/tradepilot/scripts/resolve-calls.py</string>
  </array>
  <key>StartCalendarInterval</key><array>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>1</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>2</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>3</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>4</integer></dict>
    <dict><key>Hour</key><integer>18</integer><key>Minute</key><integer>30</integer><key>Weekday</key><integer>5</integer></dict>
  </array>
  <key>StandardOutPath</key><string>/tmp/tradepilot-resolve-calls.log</string>
  <key>StandardErrorPath</key><string>/tmp/tradepilot-resolve-calls.log</string>
</dict></plist>
EOF

launchctl load ~/Library/LaunchAgents/co.tradepilot.publish-calls.plist
launchctl load ~/Library/LaunchAgents/co.tradepilot.resolve-calls.plist
launchctl list | grep tradepilot
```

Expected: both labels listed. Both plists are written out in full rather than
derived from one another — a `sed` that rewrites `<integer>` values would also
match the `Weekday` entries.

- [ ] **Step 7: Confirm the whole suite passes, then commit**

```bash
python3 -m pytest tests/ -q
git add scripts/calls-status.py tests/test_calls_status.py docs/CALLS_PIPELINE.md
git commit -m "feat(calls): make the pipeline observable, and schedule it

A capture pipeline nobody can see is one that stops without anyone noticing,
and every stopped day is proof that cannot be recovered. calls-status prints
the record and exits non-zero on missing weekdays, so a silence becomes a
signal.

Weekends are not gaps. An unresolved record reports a hit rate of None rather
than 0.0, which would read as getting everything wrong."
```

---

## Verification

```bash
cd ~/Documents/tinker/projects/tradepilot
python3 -m pytest tests/ -q
```

Expected: **219 passing** (184 existing + 7 + 10 + 13 + 5).

The plan is complete when all of the following also hold:

| | Check |
|:---:|:--|
| ☐ | `python3 scripts/publish-calls.py` twice in a row inserts N then 0 |
| ☐ | `python3 scripts/calls-status.py` prints a record and exits 0 |
| ☐ | `prototype/tradepilot_app.db` exists and is separate from `tradepilot_analytics.db` |
| ☐ | `launchctl list \| grep tradepilot` shows both agents |
| ☐ | No `.NS` suffix appears in any recorded symbol |
| ☐ | No ETF or mutual-fund symbol appears in `calls` |

## Not in this plan

The `/app` client dashboard — five screens and eight endpoints — is the second
plan against this spec. It consumes the `calls` and `positions` tables this plan
creates, and can be built against a stubbed `current_user()` without waiting for
project B. Nothing in the dashboard is a prerequisite for this pipeline; the
reverse is not true, which is why this one ships first.
