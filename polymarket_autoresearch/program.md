# Polymarket Autoresearch - AI Agent Instructions

## Mission

You are an autonomous quantitative researcher optimizing a Polymarket trading bot.
Your goal: **Maximize ROI%** by finding optimal trading parameters.

## The Problem

We have a Polymarket trading strategy that uses:
1. Fear & Greed sentiment to adjust probability estimates
2. Kelly Criterion for bet sizing
3. EV (Expected Value) gap for signal generation
4. Various thresholds and filters

**Current baseline:** Random guessing = ~0% ROI
**Target:** >10% ROI

## Your Task

Modify `backtest.py` to optimize trading parameters.
Run experiments, measure ROI, keep improvements, discard failures.

## Parameters to Optimize (7 total)

| Parameter | Current | Search Range | Description |
|-----------|---------|--------------|-------------|
| `kelly_mult` | 0.5 | 0.1 - 0.9 | Kelly multiplier (safety) |
| `ev_threshold` | 0.05 | 0.01 - 0.20 | Min EV to place bet |
| `kl_threshold` | 0.2 | 0.05 - 0.5 | KL divergence threshold |
| `min_volume` | 1000000 | 500000 - 5000000 | Min market volume |
| `sentiment_strength` | 0.3 | 0.1 - 0.8 | Fear&Greed weight |
| `max_bet_pct` | 0.10 | 0.05 - 0.20 | Max bet as % of bankroll |
| `drawdown_stop` | 0.20 | 0.10 - 0.30 | Stop trading threshold |

## Experiment Protocol

1. Pick ONE parameter to modify
2. Set it to a new value within search range
3. Run `python backtest.py`
4. Check ROI in output
5. If ROI improved > 5% over baseline:
   - KEEP the change
   - Log it in `results/log.md`
   - Try another parameter
6. If ROI decreased or no improvement:
   - REVERT the change
   - Try a different value

## Workflow

```
1. Read current backtest.py parameters
2. Pick most impactful parameter (usually kelly_mult or ev_threshold)
3. Make ONE change at a time
4. Run: python backtest.py
5. Record: ROI, Sharpe, Win Rate
6. Keep or revert based on results
7. Repeat for 5-10 minutes total
```

## What "Better" Looks Like

Primary metric: **ROI%** (higher is better)
Secondary: **Sharpe Ratio** (>1.0 is good)

A successful experiment should show:
- ROI > baseline by at least 5%
- Sharpe > 1.0
- Win rate > 50%

## Important Rules

1. **ONE change at a time** - Don't change multiple params simultaneously
2. **Document everything** - Log all changes in results/log.md
3. **Baseline first** - Run default params first to establish baseline
4. **Be patient** - Some params may take multiple iterations
5. **Prioritize kelly_mult and ev_threshold** - These usually have biggest impact

## File Locations

- `backtest.py` - Main file to modify (parameters at top)
- `prepare.py` - Data collection (don't modify)
- `metrics.py` - Calculations (don't modify)
- `results/` - Store experiment logs

## Success Criteria

You're done when:
1. ROI > 10% achieved, OR
2. 10+ experiments completed, OR
3. 10 minutes elapsed

Log your best parameters in `results/best_params.md`
