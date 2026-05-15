# Data Quality Officer (DQO)

**Tier 3 (Background). Veto: YES (data-block authority).**

## Mission
Feed integrity. NaN watchdog. Cache freshness. Refuse to start engines on poisoned data. The May-8 cache-TTL bug is the canonical lesson.

## Cadence
- **09:00 IST** — pre-market: full feed health scan; report goes into pre-launch
- **11:00 IST** — mid-market: NaN rate, stale quotes, missing symbols
- **15:30 IST** — post-close: feed integrity summary, any drift
- **On-demand** — before every engine launch (called by `launch-market.sh`)

## Rule Family Owned (with Sarathi)
- `SARATHI-DAT` — 4 rules → `docs/sarathi/rules/SARATHI-DAT.md`

## Inputs
- `prototype/v4/cache/nifty50_quotes_batch.json`
- Live broker quote feed (Yahoo / Zerodha Kite / Fyers)
- GIFT Nifty feed
- FII/DII daily CSV (when ready, T+1)

## Outputs
- `docs/team/status/data-quality-officer.json` — current feed health
- `docs/team/activity/YYYY-MM-DD.jsonl` — entries on every check
- `docs/sarathi/ledger/YYYY-MM-DD.jsonl` — entries on every BLOCK / WARN

## Veto Authority
**BLOCK** engine start if:
- > 20% NaN in batch quote feed (DAT-001)
- Cache age > 5 min on critical files (DAT-002)
- > 80% signal-direction skew suggesting scorer bug (DAT-004)

## KPI
- Zero engine starts on poisoned feed
- > 99% data feed uptime during market hours
- Detected feed issues catalogued for post-mortem

## Implementation
**Script-based**, no LLM. Runs as scheduled cron jobs at 09:00 / 11:00 / 15:30 IST. Pre-launch check is synchronous (blocks `launch-market.sh`).

```bash
python3 scripts/team/gates/data-quality-gate.py --check pre-market
# exit 0 = PASS / exit 1 = BLOCK
```
