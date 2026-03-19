# Polymarket Quant Bot

A quantitative trading bot for Polymarket prediction markets using 6 hedge fund-grade formulas and Fear & Greed sentiment analysis.

## Project Structure

```
polygon/
├── config.yaml            # Configuration settings
├── formulas.py            # 6 trading formulas
├── data_pipeline.py       # Polymarket API (no key needed)
├── sentiment.py           # Fear & Greed sentiment
├── backtest_scenarios.py  # Scenario analysis
├── trading_bot.py         # Main trading bot
├── backtest.py            # Historical backtesting
├── bot.py                 # Original bot
├── requirements.txt       # Dependencies
└── data/                  # Historical data
```

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Test sentiment (Fear & Greed)
python sentiment.py

# 3. Run scenario backtest
python backtest_scenarios.py

# 4. Scan for opportunities
python trading_bot.py --scan --keywords BTC ETH

# 5. Run full backtest
python trading_bot.py --backtest
```

## The Full System

### 1. Data Sources
- **Polymarket API** - Real prices, volumes (no API key)
- **Fear & Greed Index** - Market sentiment (free)

### 2. The 6 Formulas

| Formula | Purpose |
|---------|---------|
| **LMSR** | Price impact prediction |
| **Kelly Criterion** | Optimal bet sizing |
| **EV Gap** | Mispricing detection |
| **KL-Divergence** | Correlated arbitrage |
| **Bregman Projection** | Multi-outcome arb |
| **Bayesian Update** | Dynamic probability |

### 3. Sentiment Analysis
- Fear & Greed Index (alternative.me API)
- Converts sentiment to probability adjustment
- Applied via Bayesian update

## Example Output

```
======================================================================
POLYMARKET TRADING SCAN - 2026-03-19 20:45:20
======================================================================

Fear & Greed: 23 (Extreme Fear)
Adjustment: -0.08

Bankroll: $10,000.00
Min EV: 5%
Kelly Mult: 0.5x

>>> TOP 3 OPPORTUNITIES:

1. Will bitcoin hit $1m before GTA VI?
   Price: 50.0% | Your Prob: 52.0% | EV: 4.0%
   Bet: $200.00 (2.0% Kelly)
   Reason: F&G: -0.08
```

## Scenario Analysis Results

```
Scenario     Trades  Win%   ROI%    Sharpe
-------------------------------------------
Conservative   28    50%    10.1%    1.55
Moderate       37    73%   170.8%    7.98
Realistic      17    65%    42.2%    6.06
```

## Risk Controls

- Kelly fraction: 0.5x (safe)
- Max bet: 10% of bankroll
- Min volume: $1M
- Min EV: 5%
- Max drawdown stop: 20%

## Next Steps

1. **Paper trade** for 2 weeks
2. **Validate** your edge assumption
3. **Scale up** if ROI > 10%
