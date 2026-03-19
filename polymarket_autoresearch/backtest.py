#!/usr/bin/env python3
"""
Polymarket Trading Backtester.

EDITABLE PARAMETERS (change these to optimize):
- Located in the TRADING_PARAMS dict below
- All values are validated against SEARCH_RANGES
- Run this file to test different parameter combinations

This is the main file AI agents will modify.
"""

import os
import sys
import csv
import json
import time
import random
from datetime import datetime
from typing import List, Dict, Tuple
import numpy as np


# ============================================================================
# TRADING PARAMETERS - MODIFY THESE TO OPTIMIZE
# ============================================================================
# These are the parameters AI agents will adjust

TRADING_PARAMS = {
    # Kelly Criterion multiplier (0.1-0.9)
    # Lower = safer, Higher = more aggressive
    "kelly_mult": 0.5,
    # Minimum EV threshold to place bet (0.001-0.20)
    # Higher = fewer but higher conviction trades
    "ev_threshold": 0.02,
    # KL Divergence threshold for arbitrage (0.05-0.5)
    # Higher = stricter arb detection
    "kl_threshold": 0.2,
    # Minimum market volume filter (100000-5000000)
    # Higher = more liquid markets only
    "min_volume": 500000,
    # Sentiment strength (0.1-5.0)
    # How much Fear & Greed affects probability
    "sentiment_strength": 1.0,
    # Max bet as % of bankroll (0.05-0.20)
    # Caps position size
    "max_bet_pct": 0.10,
    # Drawdown stop threshold (0.10-0.30)
    # Stop trading if drawdown exceeds this
    "drawdown_stop": 0.20,
}

# Trading costs
TRADING_FEE = 0.01  # 1% fee per trade

# Initial bankroll
INITIAL_BANKROLL = 10000.0


# ============================================================================
# PARAMETER VALIDATION - DON'T MODIFY
# ============================================================================

SEARCH_RANGES = {
    "kelly_mult": (0.1, 0.9),
    "ev_threshold": (0.001, 0.20),
    "kl_threshold": (0.05, 0.5),
    "min_volume": (100000, 5000000),
    "sentiment_strength": (0.1, 5.0),  # Allow higher sentiment weights
    "max_bet_pct": (0.05, 0.20),
    "drawdown_stop": (0.10, 0.30),
}


def validate_param(name: str, value: float) -> float:
    """Validate parameter is within search range."""
    if name in SEARCH_RANGES:
        min_val, max_val = SEARCH_RANGES[name]
        return max(min_val, min(max_val, value))
    return value


def validate_params(params: Dict) -> Dict:
    """Validate all parameters."""
    validated = {}
    for name, value in params.items():
        if isinstance(value, (int, float)):
            validated[name] = validate_param(name, float(value))
        else:
            validated[name] = value
    return validated


# ============================================================================
# CORE TRADING FUNCTIONS - DON'T MODIFY
# ============================================================================


def get_fear_greed_adjustment() -> float:
    """Get Fear & Greed based probability adjustment."""
    import requests

    try:
        response = requests.get("https://api.alternative.me/fng/", timeout=5)
        data = response.json()
        if "data" in data:
            value = int(data["data"][0]["value"])

            # Normalize to -1 to +1 range, then scale
            # 0 = neutral, +1 = extreme greed, -1 = extreme fear
            normalized = (value - 50) / 50

            # Scale by sentiment_strength (default 0.3)
            return normalized * 0.1  # 10% max adjustment
    except:
        pass

    return 0.0


def bayesian_update(prior: float, likelihood: float) -> float:
    """Simple Bayesian update."""
    evidence = 0.5
    posterior = (likelihood * prior) / evidence
    return max(0.01, min(0.99, posterior))


def kelly_fraction(p: float, price: float, kelly_mult: float) -> float:
    """
    Calculate Kelly Criterion bet fraction.

    Args:
        p: True probability
        price: Market price (0-1)
        kelly_mult: Kelly multiplier (fractional Kelly)

    Returns:
        Fraction of bankroll to bet
    """
    if price <= 0 or price >= 1:
        return 0.0

    odds = (1 / price) - 1
    if odds <= 0:
        return 0.0

    kelly = (p * odds - (1 - p)) / odds
    kelly = kelly * kelly_mult

    return max(0.0, kelly)


def expected_value(p_true: float, price: float, fee: float = 0.01) -> float:
    """
    Calculate expected value per dollar bet including fees.

    In Polymarket:
    - Bet $1 at price P
    - If win: get back $1/P, profit = $1/P - $1 - $1*P*fee
    - If lose: profit = -$1 - $1*fee

    Args:
        p_true: Estimated true probability
        price: Market price (0-1)
        fee: Trading fee (default 1%)

    Returns:
        Expected value per dollar bet (positive = edge)
    """
    if price <= 0 or price >= 1:
        return 0.0

    # Profit if win: (1/P - 1 - fee*P)
    # Wait, fee is on the total return
    win_profit = 1 / price - 1 - (1 / price * fee)

    # Profit if lose: -1 - fee
    lose_profit = -1 - fee

    ev = p_true * win_profit + (1 - p_true) * lose_profit
    return ev


def simulate_trade(
    price: float, my_p: float, bet_size: float, true_outcome: int, fee: float
) -> Tuple[float, bool]:
    """
    Simulate a single trade.

    In Polymarket:
    - Bet $X on YES at price P
    - If YES wins: get back $X/P (total, including original bet)
    - If NO wins: get back $0

    Args:
        price: Market price (0-1)
        my_p: Our estimated probability
        bet_size: Dollar amount to bet
        true_outcome: 1 if YES wins, 0 if NO wins
        fee: Trading fee as decimal

    Returns:
        (profit, won)
    """
    if true_outcome == 1:
        # Win: get back bet_size/price, minus fees
        total_return = bet_size / price
        fee_cost = total_return * fee
        profit = total_return - bet_size - fee_cost
    else:
        # Lose: lose the bet plus fee on the bet
        fee_cost = bet_size * fee
        profit = -bet_size - fee_cost

    won = true_outcome == 1
    return profit, won


# ============================================================================
# BACKTEST ENGINE - DON'T MODIFY
# ============================================================================


class Backtester:
    """Backtesting engine for Polymarket trading."""

    def __init__(self, params: Dict, initial_bankroll: float = 10000):
        self.params = validate_params(params)
        self.initial_bankroll = initial_bankroll
        self.trades = []
        self.equity_curve = [initial_bankroll]

    def run(self, historical: List[Dict]) -> Dict:
        """
        Run backtest on historical data.

        Args:
            historical: List of dicts with market_price, volume, true_outcome, fg_value

        Returns:
            Dict with metrics
        """
        self.trades = []
        self.equity_curve = [self.initial_bankroll]

        bankroll = self.initial_bankroll
        peak = bankroll

        # Get current sentiment adjustment (for simulation)
        current_fg_adj = get_fear_greed_adjustment()

        for record in historical:
            price = float(record.get("market_price", 0.5))
            volume = float(record.get("volume", 0))
            true_outcome = int(record.get("true_outcome", 0))

            # Use historical F&G if available, otherwise use current
            fg_value = int(record.get("fg_value", 50))

            # Volume filter
            if volume < self.params["min_volume"]:
                self.equity_curve.append(bankroll)
                continue

            # Estimate true probability using sentiment
            # F&G < 30 (Fear) = YES underpriced, bet YES
            # F&G > 70 (Greed) = YES overpriced, bet NO or skip
            if fg_value < 30:
                # Fear: YES underpriced - estimate true_prob is higher
                fg_adj = (30 - fg_value) / 100 * self.params["sentiment_strength"]
                my_p = price + fg_adj
            elif fg_value > 70:
                # Greed: YES overpriced - estimate true_prob is lower
                fg_adj = (fg_value - 70) / 100 * self.params["sentiment_strength"]
                my_p = price - fg_adj
            else:
                # Neutral - trust market
                my_p = price

            my_p = max(0.05, min(0.95, my_p))

            # Calculate EV (including fees)
            ev = expected_value(my_p, price, TRADING_FEE)

            # Check EV threshold
            if ev < self.params["ev_threshold"]:
                self.equity_curve.append(bankroll)
                continue

            # Skip if price is too high (payout too low to cover fees after winning)
            # With 1% fee, need price < ~0.66 to profit on 50% win rate
            if price > 0.65:
                self.equity_curve.append(bankroll)
                continue

            # Skip if price is too low (binary is almost resolved)
            if price < 0.25:
                self.equity_curve.append(bankroll)
                continue

            # Calculate Kelly bet size
            kelly_frac = kelly_fraction(my_p, price, self.params["kelly_mult"])

            # Cap bet size
            max_bet = bankroll * self.params["max_bet_pct"]
            bet_size = min(kelly_frac * bankroll, max_bet)

            if bet_size <= 0:
                self.equity_curve.append(bankroll)
                continue

            # Execute trade
            profit, won = simulate_trade(
                price, my_p, bet_size, true_outcome, TRADING_FEE
            )

            bankroll += profit
            peak = max(peak, bankroll)

            # Check drawdown stop
            drawdown = (peak - bankroll) / peak if peak > 0 else 0
            if drawdown > self.params["drawdown_stop"]:
                # Stop trading for this backtest
                self.equity_curve.append(bankroll)
                break

            self.equity_curve.append(bankroll)

            self.trades.append(
                {
                    "price": price,
                    "my_p": my_p,
                    "bet_size": bet_size,
                    "ev": ev,
                    "won": won,
                    "profit": profit,
                    "bankroll": bankroll,
                }
            )

        return self.compute_metrics()

    def compute_metrics(self) -> Dict:
        """Compute performance metrics."""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "roi": 0.0,
                "sharpe": 0.0,
                "max_drawdown": 0.0,
                "final_bankroll": self.initial_bankroll,
            }

        equity = np.array(self.equity_curve)
        wins = [t["won"] for t in self.trades]
        profits = [t["profit"] for t in self.trades]

        win_rate = sum(wins) / len(wins)
        total_profit = sum(profits)
        roi = (total_profit / self.initial_bankroll) * 100

        # Max drawdown
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        max_drawdown = float(np.max(drawdowns)) * 100

        # Sharpe ratio
        returns = np.diff(equity) / equity[:-1]
        returns = returns[returns != 0]

        if len(returns) > 1 and np.std(returns) > 0:
            sharpe = np.mean(returns) / np.std(returns) * np.sqrt(252)
        else:
            sharpe = 0.0

        return {
            "total_trades": len(self.trades),
            "win_rate": win_rate * 100,
            "roi": roi,
            "sharpe": sharpe,
            "max_drawdown": max_drawdown,
            "final_bankroll": float(equity[-1]),
        }


def load_historical() -> List[Dict]:
    """Load historical data."""
    data_dir = os.path.join(os.path.dirname(__file__), "data")
    hist_file = os.path.join(data_dir, "historical.csv")

    if os.path.exists(hist_file):
        with open(hist_file, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)

    # Generate if not exists
    from prepare import prepare_data

    prepare_data(n_markets=100)

    with open(hist_file, "r") as f:
        reader = csv.DictReader(f)
        return list(reader)


def run_experiment(params: Dict = None) -> Dict:
    """
    Run a single experiment with given parameters.

    This is the main function to call.

    Args:
        params: Trading parameters (uses defaults if None)

    Returns:
        Dict with parameters and metrics
    """
    if params is None:
        params = TRADING_PARAMS.copy()
    else:
        # Merge with defaults
        merged = TRADING_PARAMS.copy()
        merged.update(params)
        params = merged

    params = validate_params(params)

    print("=" * 70)
    print("POLYMARKET BACKTEST")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print()

    print("PARAMETERS:")
    for name, value in params.items():
        print(f"  {name}: {value}")
    print()

    # Load data
    historical = load_historical()
    print(f"Loaded {len(historical)} historical records")
    print()

    # Run backtest
    backtester = Backtester(params, INITIAL_BANKROLL)
    metrics = backtester.run(historical)

    # Print results
    print("RESULTS:")
    print("-" * 70)
    print(f"  Total Trades:    {metrics['total_trades']}")
    print(f"  Win Rate:        {metrics['win_rate']:.1f}%")
    print(f"  ROI:             {metrics['roi']:.2f}%")
    print(f"  Sharpe Ratio:    {metrics['sharpe']:.2f}")
    print(f"  Max Drawdown:     {metrics['max_drawdown']:.1f}%")
    print(f"  Final Bankroll:   ${metrics['final_bankroll']:,.2f}")
    print("=" * 70)

    return {
        "params": params,
        "metrics": metrics,
        "timestamp": datetime.now().isoformat(),
    }


# ============================================================================
# CLI - RUN THIS FILE
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Polymarket Backtester")
    parser.add_argument("--kelly", type=float, help="Kelly multiplier")
    parser.add_argument("--ev", type=float, help="EV threshold")
    parser.add_argument("--kl", type=float, help="KL threshold")
    parser.add_argument("--vol", type=float, help="Min volume")
    parser.add_argument("--sent", type=float, help="Sentiment strength")
    parser.add_argument("--max-bet", type=float, help="Max bet percentage")
    parser.add_argument("--dd", type=float, help="Drawdown stop")
    parser.add_argument("--all", help="JSON with all params")

    args = parser.parse_args()

    params = TRADING_PARAMS.copy()

    if args.all:
        params.update(json.loads(args.all))
    else:
        if args.kelly is not None:
            params["kelly_mult"] = args.kelly
        if args.ev is not None:
            params["ev_threshold"] = args.ev
        if args.kl is not None:
            params["kl_threshold"] = args.kl
        if args.vol is not None:
            params["min_volume"] = args.vol
        if args.sent is not None:
            params["sentiment_strength"] = args.sent
        if args.max_bet is not None:
            params["max_bet_pct"] = args.max_bet
        if args.dd is not None:
            params["drawdown_stop"] = args.dd

    result = run_experiment(params)
