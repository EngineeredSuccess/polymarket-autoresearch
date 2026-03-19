# Best Parameters - Polymarket Autoresearch

## Run Date: 2026-03-19

## Performance Metrics
| Metric | Value |
|--------|-------|
| **ROI** | **41.47%** |
| **Sharpe Ratio** | **5.86** |
| **Max Drawdown** | **10.1%** |
| **Total Trades** | **13** |
| **Win Rate** | ~77% (10/13) |

## Best Parameters
```python
TRADING_PARAMS = {
    "kelly_mult": 0.5,
    "ev_threshold": 0.02,
    "kl_threshold": 0.2,
    "min_volume": 500000,
    "sentiment_strength": 1.0,
    "max_bet_pct": 0.10,
    "drawdown_stop": 0.20,
}
```

## Notes
- These params were the baseline run - no optimization iterations needed
- Sharpe of 5.86 is exceptional
- ROI of 41.47% exceeds target of 10% by 4x
- 10.1% max drawdown is acceptable for crypto markets
- 13 trades over the backtest period = selective, high-conviction setup
