import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional
import json

import yaml
import numpy as np
import pandas as pd

from formulas import (
    compute_all_signals,
    kelly_fraction,
    ev_gap,
    ev_recommendation,
    lmsr_price_impact,
    kl_arbitrage_opportunity,
    bayesian_chain_update,
)
from data_pipeline import PolymarketData, load_historical_markets, prepare_market_data
from backtest import Backtester, apply_risk_controls


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class PolymarketBot:
    """
    Main quant bot for Polymarket trading.
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.data = PolymarketData()
        self.bankroll = self.config.get("INITIAL_BANKROLL", 10000)
        self.running = False
        self.trade_log = []

    def _load_config(self, config_path: str) -> dict:
        """Load configuration from YAML file."""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        return {}

    def check_market(
        self, market_id: str = None, question: str = None, my_p: float = None
    ) -> dict:
        """
        Check a market for trading opportunities.

        Args:
            market_id: Polymarket condition ID
            question: Market question for searching
            my_p: Your estimated probability (optional, will use market price if not provided)

        Returns:
            Dict with signals and recommendations
        """
        market_data = self.data.get_market_data(market_id=market_id, question=question)

        if not market_data:
            logger.warning(f"No data found")
            return {"error": "No data available"}

        price = market_data.get("close_price", market_data.get("yes_price", 0.5))
        volume = market_data.get("volume", 0)
        b = market_data.get("b", self.config.get("B_PARAMETER", 100))

        if my_p is None:
            my_p = price

        if volume < self.config.get("MIN_VOLUME", 1000000):
            logger.info(f"Skipping: volume ${volume:,} below minimum")
            return {"error": "Volume too low"}

        signal_input = prepare_market_data(price=price, volume=volume, my_p=my_p, b=b)
        signal_input["bankroll"] = self.bankroll

        signals = compute_all_signals(signal_input)

        decision = self._make_decision(signals)

        return {
            "market_id": market_data.get("market_id", ""),
            "question": market_data.get("question", ""),
            "market_data": market_data,
            "signals": signals,
            "decision": decision,
        }

    def _make_decision(self, signals: dict) -> dict:
        """Make trading decision based on signals."""
        ev = signals["ev_gap"]["ev"]
        kl = signals["kl_divergence"]["kl_value"]

        bet_size = 0
        action = "PASS"

        min_ev = self.config.get("EV_THRESHOLD", 0.05)
        kl_threshold = self.config.get("KL_THRESHOLD", 0.2)

        if signals["ev_gap"]["recommendation"] == "BET":
            kelly_frac = signals["kelly"]["fraction"]

            max_drawdown = self._get_current_drawdown()
            if max_drawdown > self.config.get("KELLY_HALVE_DRAWDOWN", 0.20):
                kelly_frac *= 0.5
                logger.warning("Kelly halved due to drawdown")

            bet_size = kelly_frac * self.bankroll
            bet_size = min(bet_size, self.bankroll * 0.1)

            if bet_size > 0:
                action = "BET"

        return {
            "action": action,
            "bet_size": bet_size,
            "ev": ev,
            "kl": kl,
            "reason": self._get_decision_reason(signals, ev, kl),
        }

    def _get_current_drawdown(self) -> float:
        """Calculate current drawdown from peak."""
        if not self.trade_log:
            return 0.0

        equity = [self.config.get("INITIAL_BANKROLL", 10000)]
        for trade in self.trade_log:
            equity.append(equity[-1] + trade.get("profit", 0))

        peak = max(equity)
        current = equity[-1]

        return (peak - current) / peak if peak > 0 else 0.0

    def _get_decision_reason(self, signals: dict, ev: float, kl: float) -> str:
        """Get human-readable reason for decision."""
        reasons = []

        if ev > self.config.get("EV_THRESHOLD", 0.05):
            reasons.append(f"EV gap: {ev:.2%}")

        if kl > self.config.get("KL_THRESHOLD", 0.2):
            reasons.append(f"KL divergence: {kl:.3f}")

        if signals["bayesian"]["posterior"] > signals["bayesian"]["prior"] * 1.1:
            reasons.append("Bayesian update positive")

        return "; ".join(reasons) if reasons else "No signal"

    def execute_trade(
        self, market_id: str, bet_size: float, question: str = "", outcome: str = "YES"
    ) -> dict:
        """
        Execute a trade (placeholder - requires Polymarket API integration).

        Args:
            market_id: Market condition ID
            bet_size: Amount to bet
            question: Market question
            outcome: "YES" or "NO"

        Returns:
            Trade confirmation
        """
        logger.info(f"TRADE SIGNAL: {question[:50]}... - ${bet_size:.2f} on {outcome}")

        trade = {
            "timestamp": datetime.now().isoformat(),
            "market_id": market_id,
            "question": question,
            "bet_size": bet_size,
            "outcome": outcome,
            "bankroll_before": self.bankroll,
            "status": "SIMULATED",
        }

        self.trade_log.append(trade)

        return trade

    def run_backtest(
        self, historical_file: str = "data/historical_markets.csv"
    ) -> dict:
        """
        Run backtest on historical data.

        Args:
            historical_file: Path to historical data CSV

        Returns:
            Backtest results
        """
        logger.info("Starting backtest...")

        df = load_historical_markets(historical_file)

        def signal_fn(price, volume, my_p, kelly_mult):
            data = prepare_market_data(price, volume, my_p)
            data["bankroll"] = self.bankroll
            return compute_all_signals(data)

        backtester = Backtester(
            initial_bankroll=self.bankroll, fee=self.config.get("TRADING_FEE", 0.01)
        )

        results = backtester.run_backtest(
            df,
            signal_fn,
            kelly_mult=self.config.get("KELLY_MULTIPLIER", 0.5),
            min_ev=self.config.get("EV_THRESHOLD", 0.05),
            min_volume=self.config.get("MIN_VOLUME", 1000000),
        )

        results = apply_risk_controls(results, self.config.get("MAX_DRAWDOWN", 0.20))

        logger.info(
            f"Backtest complete: {results['total_trades']} trades, "
            f"ROI: {results['roi']:.1f}%, Sharpe: {results['sharpe_ratio']:.2f}"
        )

        return results

    def start(
        self, market_ids: list = None, keywords: list = None, interval: int = 300
    ):
        """
        Start the trading bot.

        Args:
            market_ids: List of market condition IDs to monitor
            keywords: Keywords to search markets (e.g., ["BTC", "ETH"])
            interval: Check interval in seconds
        """
        self.running = True
        logger.info(f"Starting Polymarket bot, interval: {interval}s")

        while self.running:
            try:
                markets_to_check = []

                if market_ids:
                    for mid in market_ids:
                        markets_to_check.append(
                            self.data.get_market_data(market_id=mid)
                        )

                if keywords:
                    for kw in keywords:
                        found = self.data.search_markets(kw, limit=5)
                        markets_to_check.extend(found)

                for market in markets_to_check:
                    if not market:
                        continue

                    result = self.check_market(market_id=market.get("market_id"))

                    if "error" not in result and result["decision"]["action"] == "BET":
                        self.execute_trade(
                            result["market_id"],
                            result["decision"]["bet_size"],
                            result.get("question", ""),
                        )
                        self._send_alert(result)

            except Exception as e:
                logger.error(f"Error in main loop: {e}")

            time.sleep(interval)

    def stop(self):
        """Stop the bot."""
        self.running = False
        logger.info("Bot stopped")

    def _send_alert(self, result: dict):
        """Send Telegram alert (placeholder)."""
        if self.config.get("TELEGRAM_BOT_TOKEN"):
            logger.info(
                f"ALERT: {result.get('question', 'N/A')[:50]} - {result['decision']}"
            )
        else:
            logger.info(f"Alert: {result.get('question', 'N/A')[:50]}...")


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Polymarket Quant Bot")
    parser.add_argument(
        "--mode",
        choices=["backtest", "live"],
        default="backtest",
        help="Run mode: backtest or live",
    )
    parser.add_argument("--config", default="config.yaml", help="Config file path")
    parser.add_argument(
        "--keywords", nargs="+", help="Keywords to search markets (e.g., BTC ETH)"
    )
    parser.add_argument(
        "--test", action="store_true", help="Test Polymarket API connection"
    )

    args = parser.parse_args()

    bot = PolymarketBot(args.config)

    if args.test:
        from data_pipeline import test_polymarket_api

        test_polymarket_api()
        return

    if args.mode == "backtest":
        results = bot.run_backtest()

        print("\n" + "=" * 50)
        print("BACKTEST RESULTS")
        print("=" * 50)
        print(f"Total Trades: {results['total_trades']}")
        print(f"Win Rate: {results['win_rate']:.1%}")
        print(f"Total Profit: ${results['total_profit']:.2f}")
        print(f"ROI: {results['roi']:.1f}%")
        print(f"Sharpe Ratio: {results['sharpe_ratio']:.2f}")
        print(f"Max Drawdown: {results['max_drawdown']:.1%}")
        print(f"Final Bankroll: ${results['final_bankroll']:.2f}")
        print("=" * 50)

        if results.get("risk_warning"):
            print(f"\n⚠️  {results['risk_warning']}")

    elif args.mode == "live":
        keywords = args.keywords or ["BTC", "ETH", "crypto"]
        bot.start(keywords=keywords)


if __name__ == "__main__":
    main()
