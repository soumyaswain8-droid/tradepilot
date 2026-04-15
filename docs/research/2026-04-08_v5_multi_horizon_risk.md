# TradePilot v5 — Multi-Horizon Risk Management & Portfolio Strategy

## 1. Multi-Horizon Capital Allocation (Rs 50L = Rs 50,00,000)

### Pool Structure

| Pool | Allocation | Amount | Purpose | Turnover |
|------|-----------|--------|---------|----------|
| Intraday | 30% | 15L | Same-day, close by 3:15 PM | Daily |
| Swing | 25% | 12.5L | 3-7 day momentum plays | Weekly |
| Positional | 25% | 12.5L | 2-4 week sector rotations | Bi-weekly |
| Investment | 15% | 7.5L | 1-6 month fundamental picks | Monthly |
| Reserve | 5% | 2.5L | Drawdown buffer, opportunity fund | On-demand |

### Dynamic Rebalancing Rules

1. **Weekly rebalance trigger**: If any pool drifts more than 5% from target, rebalance
2. **Profit waterfall**: Intraday profits above 2% daily -> 50% stays, 50% moves to swing pool
3. **Loss circuit**: If intraday pool drops 10% in a week, redirect 10% of its capital to reserve
4. **Regime shift**: In bear regime, reduce intraday to 20%, increase reserve to 15%
5. **Compounding cadence**: Monthly, realized profits from all pools feed investment pool

```python
def rebalance_pools(pools: dict, targets: dict, threshold: float = 0.05) -> dict:
    total = sum(pools.values())
    adjustments = {}
    for pool, target_pct in targets.items():
        current_pct = pools[pool] / total
        drift = abs(current_pct - target_pct)
        if drift > threshold:
            adjustments[pool] = (target_pct * total) - pools[pool]
    return adjustments
```

---

## 2. Risk Budgeting

### Max Drawdown Limits by Horizon

| Horizon | Max Daily DD | Max Weekly DD | Max Monthly DD | Kill Switch |
|---------|-------------|---------------|----------------|-------------|
| Intraday | 2% of pool | 5% of pool | 10% of pool | Pause 1 day |
| Swing | -- | 3% of pool | 8% of pool | Reduce size 50% |
| Positional | -- | -- | 10% of pool | Exit weakest 50% |
| Investment | -- | -- | 15% of pool | Review, no panic |
| Portfolio | 1% of total | 3% of total | 7% of total | All-stop |

### VaR / CVaR for Indian Markets

- **VaR (95%, 1-day)**: Nifty 50 historical ~1.8-2.2%. Use 2% as baseline.
- **CVaR (95%, 1-day)**: ~2.8-3.5% (tail risk beyond VaR). Use 3% as baseline.
- India VIX > 20 = elevated regime. Scale all position sizes by `15/VIX` ratio.

```python
import numpy as np
from scipy import stats

def calculate_var_cvar(returns: np.ndarray, confidence: float = 0.95):
    var = np.percentile(returns, (1 - confidence) * 100)
    cvar = returns[returns <= var].mean()
    return var, cvar

# Correlation-aware portfolio VaR
def portfolio_var(weights, cov_matrix, confidence=0.95):
    port_std = np.sqrt(weights.T @ cov_matrix @ weights)
    z = stats.norm.ppf(1 - confidence)
    return abs(z * port_std)
```

### Correlation-Aware Sizing

Never hold >3 stocks from the same sector across all pools. Cross-pool correlation check:

```python
# If correlation between two holdings > 0.7, treat as single position for risk
def adjusted_position_count(positions, corr_matrix, threshold=0.7):
    effective_positions = len(positions)
    for i in range(len(positions)):
        for j in range(i+1, len(positions)):
            if corr_matrix[i][j] > threshold:
                effective_positions -= 0.5  # Count correlated pair as 1.5, not 2
    return max(effective_positions, 1)
```

**Libraries**: `numpy`, `scipy.stats`, `riskfolio-lib` (risk parity), `pyportfolioopt`

---

## 3. Regime Detection

### Three-State Model: Bull / Bear / Sideways

| Indicator | Bull | Sideways | Bear |
|-----------|------|----------|------|
| Nifty 50 vs 50-DMA | >2% above | Within 2% | >2% below |
| Nifty 50 vs 200-DMA | Above | Above | Below |
| India VIX | <15 | 15-22 | >22 |
| Advance/Decline (5d avg) | >1.5 | 0.8-1.5 | <0.8 |
| FII flow (5d net) | >500Cr buy | -500 to +500 | >500Cr sell |
| Sector breadth (% above 20-DMA) | >65% | 35-65% | <35% |

**Composite score**: Assign +1/0/-1 per indicator. Sum of 6 indicators: Bull >= +3, Bear <= -3, else Sideways.

### Regime-Based Allocation Shift

| Pool | Bull | Sideways | Bear |
|------|------|----------|------|
| Intraday | 30% | 35% (more range trades) | 25% |
| Swing | 30% | 20% | 15% |
| Positional | 25% | 20% | 10% |
| Investment | 15% | 15% | 20% (buy dips) |
| Reserve/Cash | 0% | 10% | 30% |

### Implementation: Hidden Markov Model

```python
from hmmlearn.hmm import GaussianHMM

def detect_regime(returns, volatility, n_states=3):
    X = np.column_stack([returns, volatility])
    model = GaussianHMM(n_components=n_states, covariance_type="full", n_iter=100)
    model.fit(X)
    states = model.predict(X)
    return states[-1]  # Current regime

# Libraries: hmmlearn, sklearn (KMeans alternative), ta (technical indicators)
```

---

## 4. Stop-Loss Strategies by Horizon

| Horizon | Method | Formula | Example (Rs 1000 stock) |
|---------|--------|---------|------------------------|
| Intraday | ATR(14) x 1.5 | SL = Entry - 1.5 * ATR | ATR=12 -> SL=982 (1.8%) |
| Swing | ATR(14) x 2.5 + Support | SL = max(Entry - 2.5*ATR, Support - 0.5*ATR) | SL=960 (4%) |
| Positional | Weekly ATR x 2 + 200-DMA | SL = max(Entry - 2*WeeklyATR, 200-DMA * 0.97) | SL=930 (7%) |
| Investment | Fundamental floor | SL = 0.85 * fair_value_estimate | Fair=1100 -> SL=935 |

### Trailing Stop by Horizon

- **Intraday**: Trail at 1 ATR after 1:1 R:R achieved
- **Swing**: Trail at close below 8-EMA (daily)
- **Positional**: Trail at close below 21-EMA (daily) or weekly low
- **Investment**: No trail. Quarterly fundamental review. Exit if thesis breaks.

```python
def atr_stop(entry, atr, multiplier, direction='long'):
    if direction == 'long':
        return round(entry - multiplier * atr, 2)
    return round(entry + multiplier * atr, 2)

ATR_MULTIPLIERS = {'intraday': 1.5, 'swing': 2.5, 'positional': 2.0, 'investment': None}
```

---

## 5. Compounding Strategies

### Profit Waterfall (Monthly Cycle)

```
Intraday profits (realized weekly)
  |-- 50% stays in intraday pool (compound within)
  |-- 30% -> swing pool
  |-- 20% -> positional pool

Swing profits (realized bi-weekly)
  |-- 60% stays in swing pool
  |-- 40% -> investment pool

Positional profits (realized monthly)
  |-- 70% stays in positional pool
  |-- 30% -> investment pool

Investment: 100% reinvested (true compounding)
```

### Anti-Compounding After Losses

After any pool hits its monthly drawdown limit:
1. Reduce that pool's size to 75% of target for next 2 weeks
2. Excess capital moves to reserve
3. Only restore full size after 5 consecutive profitable days

### Kelly-Based Reinvestment

```python
def reinvestment_fraction(win_rate, avg_win, avg_loss, kelly_fraction_used=0.5):
    """How much of profits to reinvest vs withdraw."""
    full_kelly = win_rate - (1 - win_rate) / (avg_win / avg_loss)
    if full_kelly <= 0:
        return 0.0  # Don't reinvest, system is losing
    half_kelly = full_kelly * kelly_fraction_used
    # Reinvest up to half-Kelly fraction, withdraw rest
    return min(half_kelly, 0.25)
```

---

## 6. Tax Optimization (India, FY 2026-27)

### Tax Rates by Trading Type

| Type | Classification | Tax Rate | Holding Period |
|------|---------------|----------|----------------|
| Intraday equity | Speculative business income | Slab rate (up to 30%) | Same day |
| F&O (futures/options) | Non-speculative business income | Slab rate (up to 30%) | N/A |
| Swing (equity, <12m) | STCG u/s 111A | 20% flat | <12 months |
| Positional (equity, <12m) | STCG u/s 111A | 20% flat | <12 months |
| Investment (equity, >12m) | LTCG u/s 112A | 12.5% (above 1.25L) | >12 months |

### Tax-Aware Strategy

1. **Hold winners past 12 months**: Move investment pool picks toward LTCG (12.5%) vs STCG (20%)
2. **Harvest losses in March**: Book STCG losses to offset STCG/LTCG gains. From FY 2026-27: long-term loss can only offset once (no multi-year carry for same loss)
3. **Intraday as business**: Maintain books. Claim expenses (data feeds, software, internet). If turnover >10Cr, audit required.
4. **F&O STT hike**: Budget 2026 raised STT on F&O. Factor this into edge calculations.
5. **Segregate accounts**: Use separate demat for investment (LTCG) vs trading (STCG/business).

### Effective Tax Comparison

| Strategy | Pre-tax Rs 5L profit | Tax | Net |
|----------|---------------------|-----|-----|
| Intraday (30% slab) | 5,00,000 | 1,50,000 | 3,50,000 |
| Swing STCG (20%) | 5,00,000 | 1,00,000 | 4,00,000 |
| Investment LTCG (12.5%) | 5,00,000 | 46,875* | 4,53,125 |

*LTCG: (5L - 1.25L exempt) x 12.5% = 46,875

---

## 7. Drawdown Recovery

### Position Sizing After Losses (Anti-Martingale)

```python
def adjusted_position_size(base_size, current_dd_pct, max_dd_pct):
    """Reduce position size proportionally to drawdown depth."""
    if current_dd_pct <= 0:
        return base_size
    reduction = current_dd_pct / max_dd_pct  # 0 to 1
    # At 50% of max DD, trade at 50% size. At max DD, trade at 0%.
    return base_size * max(1 - reduction, 0)
```

### Circuit Breaker Rules

| Trigger | Action | Duration |
|---------|--------|----------|
| Pool daily DD > 2% | Pause pool for rest of day | 1 day |
| Pool weekly DD > 5% | Reduce pool to 50% size | 1 week |
| Portfolio weekly DD > 3% | Pause all intraday/swing | 2 days |
| Portfolio monthly DD > 7% | All-stop. Reserve only. | Until review |
| 5 consecutive losing days | Reduce all pools to 50% | 3 days |
| Single trade loss > 1% of total capital | Review sizing model | Immediate |

### Recovery Ladder

After circuit breaker triggers, recovery is graduated:
- Day 1-3 after reset: Trade at 25% normal size
- Day 4-7: Trade at 50%
- Day 8-14: Trade at 75%
- Day 15+: Full size if no new drawdown

---

## 8. Performance Metrics

### Key Metrics by Horizon

| Metric | Formula | Target |
|--------|---------|--------|
| **Sharpe Ratio** | (Return - Rf) / StdDev | >1.5 (intraday), >1.0 (swing) |
| **Sortino Ratio** | (Return - Rf) / DownsideDev | >2.0 (better for asymmetric) |
| **Calmar Ratio** | AnnualReturn / MaxDrawdown | >2.0 |
| **Max Drawdown** | Peak-to-trough % | <10% per pool, <7% portfolio |
| **Win Rate** | Winners / Total trades | >55% (intraday), >50% (swing) |
| **Profit Factor** | GrossProfit / GrossLoss | >1.5 |
| **Expectancy** | (WR * AvgWin) - (LR * AvgLoss) | >0.5% per trade |
| **Recovery Factor** | NetProfit / MaxDrawdown | >3.0 |

```python
def sharpe_ratio(returns, risk_free_rate=0.065/252):  # India ~6.5% annual
    excess = returns - risk_free_rate
    return np.sqrt(252) * excess.mean() / excess.std()

def sortino_ratio(returns, risk_free_rate=0.065/252):
    excess = returns - risk_free_rate
    downside = excess[excess < 0].std()
    return np.sqrt(252) * excess.mean() / downside if downside > 0 else 0

def calmar_ratio(returns, window=252):
    annual_ret = (1 + returns).prod() ** (252/len(returns)) - 1
    cumulative = (1 + returns).cumprod()
    max_dd = (cumulative / cumulative.cummax() - 1).min()
    return annual_ret / abs(max_dd) if max_dd != 0 else 0

# Libraries: quantstats (full tearsheet), empyrical, pyfolio
```

---

## 9. Proven Multi-Strategy Hedge Fund Approaches

### How Top Funds Combine Timeframes

| Fund | AUM | Approach | Timeframes | 2024 Return |
|------|-----|----------|------------|-------------|
| **Renaissance (Medallion)** | ~$10B | Statistical arbitrage, mean reversion | Seconds to days | ~30% |
| **Two Sigma** | ~$60B | ML + fundamental + macro | Days to months | 10-14% |
| **DE Shaw** | ~$60B | Hybrid quant + discretionary | Days to quarters | 18% |
| **AQR** | ~$100B | Factor + risk parity | Weeks to years | 12% |
| **Citadel (Wellington)** | ~$65B | Multi-strategy, relative value | Hours to months | 15% |

### Common Patterns

1. **Timeframe diversification**: No single horizon dominates. Typically 40% short-term, 35% medium, 25% long-term.
2. **Risk parity across strategies**: Each strategy gets equal risk budget, not equal capital.
3. **Decorrelation requirement**: New strategy must have <0.3 correlation with existing book.
4. **Adaptive sizing**: All funds use volatility-targeting. When vol rises, positions shrink automatically.
5. **Factor exposure limits**: Net market exposure capped (typically 10-30% net long).

### Risk Parity Implementation

```python
# riskfolio-lib: full risk parity optimization
import riskfolio as rp

def risk_parity_weights(returns_df):
    port = rp.Portfolio(returns=returns_df)
    port.assets_stats(method_mu='hist', method_cov='hist')
    weights = port.rp_optimization(
        model='Classic', rm='MV', hist=True,
        rf=0.065/252, b=None  # Equal risk contribution
    )
    return weights
```

---

## 10. Monte Carlo & Advanced Techniques

### Monte Carlo for Portfolio Risk

```python
def monte_carlo_portfolio(returns_df, weights, n_sims=10000, n_days=252):
    """Simulate portfolio paths and compute risk metrics."""
    mean = returns_df.mean().values
    cov = returns_df.cov().values
    results = np.zeros((n_sims, n_days))
    
    for i in range(n_sims):
        daily_returns = np.random.multivariate_normal(mean, cov, n_days)
        portfolio_returns = daily_returns @ weights
        results[i] = np.cumprod(1 + portfolio_returns)
    
    final_values = results[:, -1]
    var_95 = np.percentile(final_values, 5)
    cvar_95 = final_values[final_values <= var_95].mean()
    max_dds = [(r / np.maximum.accumulate(r) - 1).min() for r in results]
    
    return {
        'median_return': np.median(final_values) - 1,
        'var_95': 1 - var_95,
        'cvar_95': 1 - cvar_95,
        'worst_dd_95': np.percentile(max_dds, 5),
        'prob_loss': (final_values < 1).mean()
    }
```

### Kelly Criterion for Multiple Correlated Bets

Standard Kelly assumes independent bets. For correlated positions, use the matrix form:

```python
def multi_kelly(expected_returns, cov_matrix, kelly_fraction=0.5):
    """
    Multivariate Kelly: f* = Sigma^{-1} * mu
    Use half-Kelly for safety.
    """
    cov_inv = np.linalg.inv(cov_matrix)
    full_kelly = cov_inv @ expected_returns
    return full_kelly * kelly_fraction
```

**Critical**: Without correlation adjustment, you over-lever correlated positions. If HDFCBANK and ICICIBANK have 0.8 correlation, Kelly treats the combined position as 1.3 effective positions, not 2.

---

## Python Libraries Summary

| Library | Purpose | Install |
|---------|---------|---------|
| `riskfolio-lib` | Risk parity, CVaR optimization | `pip install riskfolio-lib` |
| `pyportfolioopt` | Mean-variance, Black-Litterman | `pip install pyportfolioopt` |
| `quantstats` | Performance tearsheets | `pip install quantstats` |
| `hmmlearn` | Hidden Markov regime detection | `pip install hmmlearn` |
| `empyrical` | Sharpe, Sortino, drawdown | `pip install empyrical` |
| `ta` | Technical indicators (ATR, etc.) | `pip install ta` |
| `scipy` | VaR, optimization, statistics | `pip install scipy` |
| `arch` | GARCH volatility models | `pip install arch` |

---

## India-Specific Considerations

1. **Market hours**: 9:15 AM - 3:30 PM IST. ORB window 9:15-9:30. Last hour (2:30-3:30) most volatile.
2. **India VIX**: Primary volatility gauge. Mean ~14, >20 = caution, >25 = crisis mode.
3. **FII/DII flows**: Single biggest short-term driver. FII selling + DII buying = sideways. Both selling = bear.
4. **Expiry effects**: Weekly options expiry (Thursday) creates synthetic support/resistance.
5. **Circuit limits**: NSE has 10%/15%/20% circuit breakers on index. Individual stocks have 5%/10%/20%.
6. **Liquidity**: Nifty 50 liquid for all horizons. Midcap/smallcap: avoid intraday, suitable for swing/positional.
7. **Margin rules**: SEBI peak margin rules require upfront margin. Intraday leverage ~5x (broker dependent).
8. **Tax audit**: If F&O turnover >10Cr or total income >50L with business income, mandatory audit u/s 44AB.
