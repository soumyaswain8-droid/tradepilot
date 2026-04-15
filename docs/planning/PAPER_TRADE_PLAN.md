# TradePilot Paper Trading Plan

*Starting April 8, 2026*

## Capital Allocation

| Pool | Amount | Purpose |
|------|--------|---------|
| Paper Trading (Active) | Rs 5,00,000 | Intraday trades based on AI signals |
| Reserve | Rs 5,00,000 | Not deployed yet |
| **Total** | **Rs 10,00,000** | -- |

## Strategy: AI-Driven Intraday

### Entry Rules
- **Time:** 9:30-9:45 AM (15 min after market open for price discovery)
- **Signal:** Buy stocks with BUY signal from v3 engine (score >= 60 in BEAR, >= 50 in BULL)
- **Confirmation:** Only if stock is UP in first 15 min (momentum confirmation)
- **Position size:** Rs 1,00,000 per stock (max 5 positions = Rs 5L fully deployed)
- **If < 5 BUY signals:** Also consider top HOLD stocks with RS_5d > 3%

### Exit Rules
- **Target:** +1.5% from entry (profit booking)
- **Stop-loss:** -0.75% from entry (risk management, 1:2 risk-reward)
- **Time stop:** 3:15 PM forced exit (15 min before close, avoid closing auction volatility)
- **Trailing stop:** If stock hits +1%, move stop-loss to entry (breakeven protection)

### Position Sizing
- Max Rs 1,00,000 per stock (20% of active capital)
- Max 5 positions at any time
- Never more than Rs 5,00,000 deployed

## Daily Schedule

| Time | Action |
|------|--------|
| 09:15 | Market opens -- v2 + v3 scores captured |
| 09:30 | **ENTRY WINDOW OPENS** -- buy top signals with opening confirmation |
| 09:45 | Entry window closes -- all positions placed |
| 11:30 | Mid-morning check -- update trailing stops |
| 13:30 | Afternoon check -- update trailing stops |
| 15:15 | **FORCED EXIT** -- close all remaining positions |
| 15:30 | Market close -- capture final prices, compute P&L |
| 16:00 | EOD report -- daily P&L, comparison, learnings |

## Tracking: 3 Parallel Portfolios

We run 3 virtual portfolios simultaneously to compare:

| Portfolio | Engine | Entry Logic | Purpose |
|-----------|--------|-------------|---------|
| **v2-paper** | v2 scoring | Top v2 BUY signals | Baseline |
| **v3-paper** | v3 scoring | Top v3 BUY signals | New algorithm |
| **v3-rs** | v3 + RS filter | v3 BUY + RS_5d > 3% | High-conviction only |

Each portfolio starts with Rs 5,00,000. Same exit rules for all three.

## Risk Management

- **Daily loss limit:** Rs 15,000 (3% of capital) -- stop trading for the day
- **Per-trade max loss:** Rs 750 per lakh (0.75% stop-loss)
- **Max daily trades:** 5 entries per portfolio
- **No averaging down:** If stop-loss hit, don't re-enter same stock
- **Cash position OK:** If no good signals, stay in cash (0 trades = 0 loss)

## Success Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Daily win rate | > 60% | Winning trades / total trades |
| Average daily P&L | > Rs 2,500 (0.5%) | Net P&L after all trades |
| Max drawdown | < Rs 25,000 (5%) | Peak to trough |
| Sharpe (annualized) | > 2.0 | Daily returns / daily std |
| Best portfolio | v3-rs expected | Compare all 3 weekly |
