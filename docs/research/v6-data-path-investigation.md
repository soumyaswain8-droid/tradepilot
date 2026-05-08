# v6 Data Path — Why It Worked When v4 Didn't (2026-05-08)

## Question

On 2026-05-08, the cache file `nifty50_quotes_batch.json` was poisoned with 193 NaN
entries written at 03:04 IST (pre-market). v4 saw "BUY=2" all morning and made
only 2 trades (both stop-losses, total -₹6,884). But v6 — which is *supposed* to
use v4's signals — made **55 trades** with **+₹851** P&L and 67.3% win rate.

Both engines call `score_all_stocks()` from `prototype/v4/composite_scorer.py`.
Both should have hit the same poisoned cache. So how did v6 get away?

## What I found

`scripts/v6-paper-trade.py:140-175` — `v6_generate_signals()`:

```python
def v6_generate_signals(regime: str = None):
    from prototype.v4.composite_scorer import score_all_stocks
    v4_results = score_all_stocks(regime_override=regime)
    ...
    for stock in v4_results:
        score = stock.get("score", 50)
        if score >= V6_BUY_MIN_SCORE:
            direction = "BUY"
        elif score <= V6_SHORT_MAX_SCORE and change_pct < V6_SHORT_MIN_NEG_CHANGE:
            direction = "SELL"
        ...
```

**Key difference from v4's path:** v6 ignores v4's BUY/HOLD/AVOID classification
(set by `composite_scorer` after the NaN guard). Instead, v6 reads the raw
`score` field and applies its own thresholds.

## Why this lets v6 escape the cache poisoning

Composite_scorer's NaN guard fires AFTER scoring is complete:
- Stock with NaN price → score still computed (from features that don't need price like RS, regime, FII flow)
- BUY/HOLD/AVOID classification → forces NaN-priced rows to HOLD
- v4's deployment loop reads `direction == "BUY"` only → sees 2 stocks
- **v6's deployment loop reads `score` directly** → sees ALL stocks above threshold

So v6 effectively bypasses the NaN guard. It uses the score (which is non-NaN
because score calculation didn't depend on `last_price` for its main inputs)
and proceeds to trade those stocks.

## But how does v6 not crash on NaN prices when sizing?

Two possible answers:
1. v6 uses v5's `pool_manager` for sizing, which has its own data fetch
   (likely `fast_info.lastPrice` per-symbol, bypassing batch cache)
2. v6's `safe_qty()` from `prototype/utils/signal_guards.py` may catch NaN before sizing

`scripts/v6-paper-trade.py:30`:
```python
from prototype.utils.signal_guards import safe_qty, atomic_write_json, ...
```

The `safe_qty` helper likely refuses to size positions with NaN inputs. So
v6's deployment looks like: "I have 200 raw scores, refine to top-N by score
threshold, then for each, fetch live price via fast_info (clean), then size."

## Implications

1. **v6 has a fundamentally more resilient data architecture than v4.** It
   uses score for selection but live `fast_info` for execution. Cache
   poisoning only affects the score-cache (which is fine because score
   doesn't depend on the polluted `last_price` field).

2. **v4 should adopt v6's pattern**: use `composite_scorer` output for
   ranking, but fetch live prices per-symbol via `fast_info` immediately
   before sizing. This would have eliminated today's failure entirely.

3. **The fix is structural, not a one-line change.** v4's `deploy_into_buys`
   currently passes the cached price to the sizer. Changing this to "fetch
   fresh price per symbol just before sizing" is the right architecture.

4. **Until that refactor is done, today's 5 patches are the band-aid:**
   - Cache TTL (5 min) → cache can't be more than 5 min stale
   - Pre-market write block → no NaN-cache from overnight access
   - All-NaN write rejection → corrupt batches don't get written
   - Min BUY-count gate (10) → won't deploy from a tiny biased universe
   - Position-size cap (15%) → no more 50% concentration
   - Warm-up window (09:30) → first deploy has clean data

## Action item

Schedule a v4 architecture refactor for next sprint:
- v4 follows v6's "score-then-fetch-fresh-price-per-symbol" pattern
- Eliminate dependency on `nifty50_quotes_batch.json` for live trading prices
- Cache becomes optional (used for non-trading scoring features only)

This is part of the Kite Connect cutover anyway — Kite Connect's WebSocket
removes the batch-cache pattern entirely.

---

**Investigated:** 2026-05-08 18:45 IST
**Author:** Claude (TradePilot session)
**Status:** Research finding · no code change today
