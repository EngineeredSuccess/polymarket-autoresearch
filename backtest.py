import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
import matplotlib.pyplot as plt
from datetime import datetime


class Backtester:
    """
    Walk-forward backtesting for Polymarket trading strategies.
    """

    def __init__(self, initial_bankroll: float = 10000, fee: float = 0.01):
        self.initial_bankroll = initial_bankroll
        self.fee = fee
        self.trades = []
        self.equity_curve = []

    def run_backtest(
        self,
        markets_df: pd.DataFrame,
        signal_func,
        kelly_mult: float = 0.5,
        min_ev: float = 0.05,
        min_volume: float = 1000000,
    ) -> Dict:
        """
        Run backtest on historical market data.

        Args:
            markets_df: DataFrame with columns:
                - event_name
                - market_price
                - true_outcome
                - volume
            signal_func: Function that takes (price, volume, my_p) and returns signals
            kelly_mult: Kelly multiplier
            min_ev: Minimum EV threshold
            min_volume: Minimum volume filter

        Returns:
            Dict with backtest metrics
        """
        bankroll = self.initial_bankroll
        self.trades = []
        self.equity_curve = [bankroll]

        for idx, row in markets_df.iterrows():
            price = row["market_price"]
            volume = row["volume"]
            true_outcome = row["true_outcome"]

            if volume < min_volume:
                continue

            my_p = price + np.random.uniform(-0.1, 0.1)
            my_p = max(0.1, min(0.9, my_p))

            signals = signal_func(price, volume, my_p, kelly_mult)

            if signals["ev_gap"]["recommendation"] == "BET":
                bet_size = signals["kelly"]["bet_size"]

                if bet_size > bankroll * 0.1:
                    bet_size = bankroll * 0.1

                if bet_size > 0:
                    win = true_outcome == 1
                    payout = bet_size * (1 / price - 1) if win else -bet_size
                    fee_cost = bet_size * self.fee

                    profit = payout - fee_cost
                    bankroll += profit

                    self.trades.append(
                        {
                            "event": row["event_name"],
                            "price": price,
                            "bet_size": bet_size,
                            "win": win,
                            "profit": profit,
                            "bankroll_after": bankroll,
                        }
                    )

            self.equity_curve.append(bankroll)

        return self._compute_metrics()

    def _compute_metrics(self) -> Dict:
        """Compute backtest performance metrics."""
        if not self.trades:
            return {
                "total_trades": 0,
                "win_rate": 0.0,
                "total_profit": 0.0,
                "roi": 0.0,
                "sharpe_ratio": 0.0,
                "max_drawdown": 0.0,
            }

        wins = [t["win"] for t in self.trades]
        profits = [t["profit"] for t in self.trades]

        win_rate = sum(wins) / len(wins)
        total_profit = sum(profits)
        roi = (total_profit / self.initial_bankroll) * 100

        equity = np.array(self.equity_curve)
        running_max = np.maximum.accumulate(equity)
        drawdowns = (running_max - equity) / running_max
        max_drawdown = np.max(drawdowns) if len(drawdowns) > 0 else 0

        returns = np.diff(equity) / equity[:-1]
        returns = returns[returns != 0]
        if len(returns) > 1:
            sharpe = (
                np.mean(returns) / np.std(returns) * np.sqrt(252)
                if np.std(returns) > 0
                else 0
            )
        else:
            sharpe = 0.0

        return {
            "total_trades": len(self.trades),
            "win_rate": win_rate,
            "total_profit": total_profit,
            "roi": roi,
            "sharpe_ratio": sharpe,
            "max_drawdown": max_drawdown,
            "final_bankroll": self.equity_curve[-1],
            "trades": self.trades,
        }

    def plot_equity_curve(self, save_path: str = None):
        """Plot equity curve."""
        plt.figure(figsize=(10, 6))
        plt.plot(self.equity_curve, linewidth=2)
        plt.axhline(y=self.initial_bankroll, color="r", linestyle="--", alpha=0.5)
        plt.xlabel("Trade Number")
        plt.ylabel("Bankroll ($)")
        plt.title("Equity Curve - Polymarket Quant Bot")
        plt.grid(True, alpha=0.3)

        if save_path:
            plt.savefig(save_path)
        else:
            plt.show()
        plt.close()


def run_walk_forward_backtest(
    markets_df: pd.DataFrame,
    train_size: int = 30,
    test_size: int = 10,
    signal_func=None,
) -> List[Dict]:
    """
    Run walk-forward backtest.

    Args:
        markets_df: Historical markets data
        train_size: Number of markets for training
        test_size: Number of markets for testing
        signal_func: Signal generation function

    Returns:
        List of backtest results for each window
    """
    results = []
    n = len(markets_df)

    for i in range(0, n - train_size - test_size, test_size):
        train_df = markets_df.iloc[i : i + train_size]
        test_df = markets_df.iloc[i + train_size : i + train_size + test_size]

        backtester = Backtester()
        metrics = backtester.run_backtest(test_df, signal_func)

        results.append(
            {
                "window": i // test_size,
                "train_period": f"{i}-{i + train_size}",
                "test_period": f"{i + train_size}-{i + train_size + test_size}",
                **metrics,
            }
        )

    return results


def apply_risk_controls(metrics: Dict, max_drawdown: float = 0.20) -> Dict:
    """
    Apply risk controls to backtest results.

    Args:
        metrics: Backtest metrics
        max_drawdown: Maximum allowed drawdown

    Returns:
        Updated metrics with risk controls applied
    """
    if metrics["max_drawdown"] > max_drawdown:
        metrics["risk_warning"] = (
            f"Max drawdown {metrics['max_drawdown']:.1%} exceeds {max_drawdown:.1%}"
        )
        metrics["kelly_multiplier_reduced"] = True
    else:
        metrics["risk_warning"] = None
        metrics["kelly_multiplier_reduced"] = False

    return metrics
