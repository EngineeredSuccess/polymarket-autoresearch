# Polymarket Autoresearch

AI agents that automatically optimize trading parameters overnight on RunPod GPU.

## Quick Start

```bash
cd polymarket_autoresearch
pip install -r requirements.txt
python prepare.py
python backtest.py
```

## Example Output

```
======================================================================
POLYMARKET BACKTEST
======================================================================
PARAMETERS:
  kelly_mult: 0.4
  ev_threshold: 0.01
  sentiment_strength: 4.0
  ...

RESULTS:
  Total Trades:    19
  Win Rate:        63.2%
  ROI:             115.09%
  Sharpe Ratio:    5.73
  Final Bankroll:   $20,442.21
======================================================================
```

## Parameters to Optimize

| Parameter | Default | Range | Best Found | Impact |
|-----------|---------|-------|------------|--------|
| `kelly_mult` | 0.3 | 0.1-0.9 | 0.4 | HIGH |
| `sentiment_strength` | 1.0 | 0.1-5.0 | 4.0 | HIGH |
| `ev_threshold` | 0.01 | 0.001-0.20 | 0.01 | MEDIUM |
| `min_volume` | 500000 | 100K-5M | 500000 | LOW |

## Run Different Configurations

```bash
# Test specific parameters
python backtest.py --kelly 0.5 --sent 3.0 --ev 0.01

# High risk / high reward
python backtest.py --kelly 0.8 --sent 5.0

# Conservative
python backtest.py --kelly 0.2 --sent 2.0 --ev 0.05
```

## Deploy to RunPod

1. Create RunPod Workspace with RTX 4090
2. Clone repo, install deps
3. Run: `python prepare.py && python backtest.py`

## AI Agent Workflow

1. Read `program.md`
2. Modify ONE parameter in `backtest.py`
3. Run experiment
4. Compare ROI to baseline
5. Keep if improved, revert if not
6. Repeat for 5-10 minutes

## Cost

- RTX 4090: ~$0.0065/min
- Full optimization run (50 experiments): ~$5-15
