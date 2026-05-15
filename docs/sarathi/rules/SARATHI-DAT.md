# SARATHI-DAT — Data Verification

**Triggered on:** pre-market (09:00 IST), mid-market (11:00 IST), post-close (15:30 IST), and before any cache write.

**Veto power:** YES — REJECTS engine starts on poisoned data; REJECTS cache writes outside safe windows.

## Rules

### DAT-001 — Feed NaN rate
< 5% NaN in `nifty50_quotes_batch.json`. On fail, fall back to per-symbol fetch path (the May-9 fix).

- **Check:** at every batch quote fetch, count NaN/zero `Close` prices vs total entries.
- **Action:**
  - 0–5%: `PASS`
  - 5–20%: `WARN`, log to ledger, fall back to per-symbol fetch
  - > 20%: `REJECT` — engine refuses to start this scan cycle.

### DAT-002 — Cache TTL
Reject cache files older than 5 minutes. Formalises the May-8 fix (cache written at 03:04 IST being served all day).

- **Check:** `mtime(cache_file)` vs `now()`; reject if older than 300s.
- **Action:** `REJECT` cache read; force fresh fetch.

### DAT-003 — Pre-market write block
Reject cache writes outside 09:15–15:30 IST. Pre-market hits cannot poison cache for live trading.

- **Check:** at every `_write_cache` call, compare current IST time to window.
- **Action:** `REJECT` write; data discarded.

### DAT-004 — Signal direction sanity
Reject signal sets where > 80% are same direction (likely scorer bug — the SHORT-cascade pattern from Apr-28 BEAR-regime forced shorts).

- **Check:** in `signal_engine.generate_signals`, count BUY/SELL/HOLD; if `max(BUY, SELL) / (BUY + SELL) > 0.80` AND total signals > 20 → flag.
- **Action:** `REJECT` deploy this scan cycle; engine logs reason, waits for next scan.

## Companion Rules (advisory, not blocking)

### DAT-005 — GIFT Nifty staleness
GIFT Nifty premium pulled before 09:00 IST; if not available, engine runs in "no premarket signal" mode.

- **Action:** `INFO`.

### DAT-006 — FII/DII feed availability
FII flow data is daily EOD (T+1). Engines using FII features at intraday should use yesterday's number; flag if more than 24h stale.

- **Action:** `WARN`.

## Output Schema

Append to `docs/sarathi/ledger/YYYY-MM-DD.jsonl`:
```json
{"ts":"...","family":"SARATHI-DAT","rule":"DAT-001","subject":"nifty50_quotes_batch","result":"PASS","evidence":{"nan_rate": 0.012, "total": 200}}
```

## Engine Integration

Every engine, at scan-start, calls:
```python
from scripts.sarathi.verify import verify_data_feed
verify_data_feed()  # raises SarathiBlock on REJECT
```

DQO runs DAT-001 / DAT-002 / DAT-003 independently at 09:00, 11:00, 15:30 IST and writes findings to standup card.
