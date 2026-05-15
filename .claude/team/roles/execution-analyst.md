# Execution Analyst — Cost & Slippage Watcher

**Tier 2 (Operations). Veto: NO — recommends sizing changes.**

## Mission
Measure actual slippage on every paper trade. Recompute net-of-cost P&L daily at 8/10/12/15bps assumptions. Be the source of truth for "is this engine actually profitable after costs."

## Cadence
- **Daily post-close (15:30 IST)** — pull every closed trade, compute realized slippage, write daily report
- **Weekly Sunday** — engine-level cost-corrected Sharpe trend
- **On-demand** — for any model promotion request, attach cost-corrected backtest

## Inputs
- Trade JSONLs in `docs/paper-trades/*/`
- Position snapshot history
- Order-book quotes at fill time (from engine logs)

## Outputs
- Daily report at `docs/exec/YYYY-MM-DD_slippage.json`:
  ```json
  {
    "engine":"v5","date":"...",
    "n_trades":47,
    "realized_slip_bps":11.2,
    "expected_slip_bps":10.0,
    "gross_pnl":12340,
    "net_10bps":10940,
    "net_15bps":9540,
    "trades_by_size":{"<1L":..., "1-2L":..., ">2L":...}
  }
  ```
- Weekly Sharpe trajectory at `docs/exec/weekly_sharpe.json`
- Sizing recommendation at `docs/exec/sizing_rec_YYYY-MM-DD.md` (advisory)

## KPI
- Realized slippage measured to ±1bp
- Weekly cost-corrected Sharpe report on time
- 0 days where claimed P&L diverges from measured net-of-cost P&L by > 5%

## Implementation
**Script-based** (Python, no LLM). Triggered by cron at 15:31 IST.

```bash
python3 scripts/team/slippage.py --engine v5 --date today
```

Reads engine state files, computes realized vs expected slippage per trade. Aggregates per-engine and writes report.

## Sprint 1 Specifics
- Wire `record_slippage()` hook into v4/v5/v5_classic exit paths
- Backfill slippage estimates for Apr-Aug → May-14 trade history (using nearest-quote heuristic)
- Build the first weekly cost-corrected Sharpe report by 2026-05-18
