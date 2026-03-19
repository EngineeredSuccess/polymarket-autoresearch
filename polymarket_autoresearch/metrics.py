#!/usr/bin/env python3
"""
Metrics and utilities for Polymarket trading backtests.
"""

import os
import json
from datetime import datetime
from typing import Dict, List
import numpy as np


def compute_sharpe_ratio(returns: np.ndarray, risk_free: float = 0.0) -> float:
    """
    Compute Sharpe ratio.

    Args:
        returns: Array of returns
        risk_free: Risk-free rate (default 0)

    Returns:
        Sharpe ratio (annualized)
    """
    if len(returns) < 2 or np.std(returns) == 0:
        return 0.0

    excess_returns = returns - risk_free
    return np.mean(excess_returns) / np.std(excess_returns) * np.sqrt(252)


def compute_sortino_ratio(returns: np.ndarray, target: float = 0.0) -> float:
    """
    Compute Sortino ratio (downside deviation).

    Args:
        returns: Array of returns
        target: Target return (default 0)

    Returns:
        Sortino ratio (annualized)
    """
    if len(returns) < 2:
        return 0.0

    downside_returns = returns[returns < target]
    if len(downside_returns) == 0 or np.std(downside_returns) == 0:
        return 0.0

    excess_returns = returns - target
    return np.mean(excess_returns) / np.std(downside_returns) * np.sqrt(252)


def compute_max_drawdown(equity_curve: List[float]) -> Dict:
    """
    Compute drawdown metrics.

    Args:
        equity_curve: List of equity values

    Returns:
        Dict with drawdown metrics
    """
    equity = np.array(equity_curve)
    running_max = np.maximum.accumulate(equity)
    drawdowns = (running_max - equity) / running_max

    max_dd = float(np.max(drawdowns))
    max_dd_idx = int(np.argmax(drawdowns))

    peak_idx = 0
    for i in range(max_dd_idx):
        if equity[i] == running_max[max_dd_idx]:
            peak_idx = i
            break

    return {
        "max_drawdown": max_dd,
        "max_drawdown_pct": max_dd * 100,
        "drawdown_start": peak_idx,
        "drawdown_end": max_dd_idx,
        "recovery_time": len(equity) - max_dd_idx if max_dd_idx > 0 else 0,
    }


def compute_calmar_ratio(equity_curve: List[float], annual_return: float) -> float:
    """
    Compute Calmar ratio.

    Args:
        equity_curve: List of equity values
        annual_return: Annualized return

    Returns:
        Calmar ratio
    """
    dd = compute_max_drawdown(equity_curve)
    if dd["max_drawdown"] == 0:
        return 0.0
    return annual_return / dd["max_drawdown"]


def format_metrics(metrics: Dict) -> str:
    """
    Format metrics for display.

    Args:
        metrics: Metrics dictionary

    Returns:
        Formatted string
    """
    lines = [
        f"Total Trades:    {metrics.get('total_trades', 0)}",
        f"Win Rate:        {metrics.get('win_rate', 0):.1f}%",
        f"ROI:             {metrics.get('roi', 0):.2f}%",
        f"Sharpe Ratio:    {metrics.get('sharpe', 0):.2f}",
        f"Max Drawdown:    {metrics.get('max_drawdown', 0):.1f}%",
        f"Final Bankroll:  ${metrics.get('final_bankroll', 0):,.2f}",
    ]
    return "\n".join(lines)


class ExperimentLogger:
    """Log experiments to file."""

    def __init__(self, log_dir: str = None):
        if log_dir is None:
            log_dir = os.path.join(os.path.dirname(__file__), "results")

        self.log_dir = log_dir
        self.log_file = os.path.join(log_dir, "experiments.jsonl")
        self.best_file = os.path.join(log_dir, "best_params.json")

        os.makedirs(log_dir, exist_ok=True)

    def log(self, result: Dict):
        """
        Log experiment result.

        Args:
            result: Dict with params and metrics
        """
        with open(self.log_file, "a") as f:
            f.write(json.dumps(result) + "\n")

        self._update_best(result)

    def _update_best(self, result: Dict):
        """Update best parameters if improved."""
        metrics = result.get("metrics", {})
        roi = metrics.get("roi", 0)

        # Load existing best
        best = self.load_best()
        best_roi = best.get("metrics", {}).get("roi", 0) if best else 0

        if roi > best_roi:
            with open(self.best_file, "w") as f:
                json.dump(result, f, indent=2)
            print(f"\n>>> NEW BEST! ROI: {roi:.2f}%")

    def load_best(self) -> Dict:
        """Load best parameters."""
        if os.path.exists(self.best_file):
            with open(self.best_file, "r") as f:
                return json.load(f)
        return None

    def load_all(self) -> List[Dict]:
        """Load all experiments."""
        results = []
        if os.path.exists(self.log_file):
            with open(self.log_file, "r") as f:
                for line in f:
                    try:
                        results.append(json.loads(line.strip()))
                    except:
                        pass
        return results


def compare_params(baseline: Dict, current: Dict) -> Dict:
    """
    Compare two parameter sets.

    Args:
        baseline: Baseline parameters
        current: Current parameters

    Returns:
        Dict with differences
    """
    changes = {}

    for key in set(baseline.keys()) | set(current.keys()):
        b_val = baseline.get(key)
        c_val = current.get(key)

        if b_val != c_val:
            changes[key] = {
                "before": b_val,
                "after": c_val,
                "diff": c_val - b_val if isinstance(b_val, (int, float)) else None,
            }

    return changes


def is_improvement(baseline_roi: float, new_roi: float, threshold: float = 5.0) -> bool:
    """
    Check if new result is an improvement.

    Args:
        baseline_roi: Baseline ROI
        new_roi: New ROI
        threshold: Minimum improvement threshold (%)

    Returns:
        True if improved
    """
    return new_roi - baseline_roi >= threshold


if __name__ == "__main__":
    # Test metrics
    equity = [10000, 10500, 10200, 10800, 10600, 11200]
    dd = compute_max_drawdown(equity)
    print("Drawdown metrics:", dd)
