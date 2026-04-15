# TradePilot v4 ML Training Pipeline Research — 2026-04-08

## Target Variable Decision

**Use: Intraday return magnitude (regression)**
```python
target = (close_1500 - open_0930) / open_0930
target = np.clip(target, target.quantile(0.01), target.quantile(0.99))  # winsorize
```

Why NOT classification (v3's mistake):
- Destroys magnitude info (5% up and 0.6% up both = label 1)
- Creates class imbalance → 96% AVOID
- Regression preserves the full signal → rank by predicted return

## 20 Most Predictive Features (by SHAP importance)

### Tier 1 (always include)
1. RSI(14) — mean-reversion signal
2. VWAP deviation — institutional reference price
3. ORB 15-min range — first 15min predicts day direction
4. Previous day return — short-term momentum
5. ATR(14)/close — normalized volatility
6. Volume ratio (today/20d avg) — unusual volume precedes moves
7. Gap % (open vs prev close) — gap behavior is predictive

### Tier 2 (include after validation)
8. MACD histogram — trend strength
9. Bollinger %B — mean-reversion at extremes
10. ADX(14) — trending vs ranging
11. FII/DII net flow — Indian market is FII-driven
12. Options OI PCR — contrarian at extremes
13. Sector relative strength — stock vs sector
14. 5-day return — medium momentum
15. Intraday volatility (H-L)/C

### Tier 3 (calendar/alternative)
16. Day of week — Tue-Thu stronger in India
17. Days to F&O expiry — expiry week patterns
18. Nifty 50 morning return — market regime
19. India VIX — fear gauge
20. Delivery % — conviction vs speculation

## LightGBM Regressor Settings

```python
LGBM_PARAMS = {
    'objective': 'regression',
    'metric': 'mae',
    'num_leaves': 31,
    'max_depth': 6,
    'min_child_samples': 100,    # HIGH — prevents noise fitting
    'reg_alpha': 0.1,
    'reg_lambda': 1.0,
    'subsample': 0.7,
    'colsample_bytree': 0.7,
    'learning_rate': 0.01,
    'n_estimators': 5000,        # early stopping cuts
}
```

## Validation: Walk-Forward (NOT k-fold)

```
Walk-forward (CORRECT for time series):
  Fold 1: [=====train 1yr=====]--5d embargo--[test 1mo]
  Fold 2:    [=====train 1yr=====]--5d embargo--[test 1mo]
  Fold 3:       [=====train 1yr=====]--5d embargo--[test 1mo]
```

Key metric: **Information Coefficient (IC)** = correlation(predicted, actual)
- IC > 0.05 consistently = tradeable signal
- IC > 0.10 consistently = strong signal
- IC positive in > 60% of folds = stable model

## Top 10 Pitfalls

1. Classification for returns (v3's error) → use regression
2. Standard k-fold CV → walk-forward with embargo
3. Survivorship bias → include delisted stocks
4. Look-ahead bias → lag ALL features by 1 bar
5. Overfitting to regime → train on 3+ years
6. Too many features → start with 10-15, add only if importance > 0
7. Ignoring transaction costs → subtract 0.1% per trade
8. Predicting absolute returns → predict market-relative
9. Retraining too rarely → retrain monthly
10. No position sizing → Kelly-like sizing by confidence

## Success Criteria

- Mean IC > 0.05 across walk-forward folds
- IC positive in > 60% of folds
- Long-short spread > 0 in > 70% of months after costs
- Hit rate > 53% (with good sizing = profitable)
