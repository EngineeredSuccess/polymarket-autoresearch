import os
import sys
import time
import logging
from datetime import datetime
from typing import Optional, Dict, List

import yaml
import numpy as np

from formulas import (
    compute_all_signals,
    kelly_fraction,
    ev_gap,
    lmsr_price_impact,
    bayesian_update,
)
from data_pipeline import PolymarketData
from sentiment import CryptoSentiment, bayesian_sentiment_update
from backtest_scenarios import PolymarketBacktester
from telegram_alerts import TelegramAlerts, TradingAlertManager


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class TradingBot:
    """
    Complete Polymarket trading bot with:
    - Real Polymarket data
    - Fear & Greed sentiment
    - 6 formula signals
    - Kelly bet sizing
    - Telegram alerts
    """

    def __init__(self, config_path: str = "config.yaml"):
        self.config = self._load_config(config_path)
        self.data = PolymarketData()
        self.sentiment = CryptoSentiment()
        self.bankroll = self.config.get("INITIAL_BANKROLL", 10000)
        self.running = False
        self.trade_log = []

        # Initialize Telegram alerts
        self.telegram = TelegramAlerts()
        self.alert_manager = TradingAlertManager(self.telegram)

        # Track daily summary
        self.trades_today = 0
        self.last_daily_summary = datetime.now()

    def _load_config(self, config_path: str) -> dict:
        """Load configuration."""
        if os.path.exists(config_path):
            with open(config_path, "r") as f:
                return yaml.safe_load(f)
        return {}

    def analyze_market(self, market: Dict) -> Dict:
        """
        Analyze a market and generate trading signals.

        Args:
            market: Market data dict from PolymarketData

        Returns:
            Analysis with signals and recommendation
        """
        price = float(market.get("yes_price", market.get("close_price", 0.5)))
        volume = float(market.get("volume", 0))
        question = market.get("question", "Unknown")
        market_id = market.get("market_id", "")
        b = market.get("b", 100)

        if volume < self.config.get("MIN_VOLUME", 1000000):
            return {"action": "SKIP", "reason": "Volume too low"}

        sentiment_summary = self.sentiment.get_sentiment_summary()

        if sentiment_summary["fear_greed"]:
            fg_value = sentiment_summary["fear_greed"]["value"]
            my_p = bayesian_sentiment_update(
                prior=price,
                fear_greed_value=fg_value,
                strength=self.config.get("SENTIMENT_STRENGTH", 1.0),
            )
        else:
            my_p = price

        ev = ev_gap(my_p, price)
        min_ev = self.config.get("EV_THRESHOLD", 0.05)

        kelly_frac = kelly_fraction(
            my_p, price, kelly_mult=self.config.get("KELLY_MULTIPLIER", 0.5)
        )

        kelly_dollars = kelly_frac * self.bankroll
        kelly_dollars = min(kelly_dollars, self.bankroll * 0.1)

        action = "PASS"
        bet_size = 0
        reason = []

        if ev > min_ev:
            action = "BET"
            bet_size = kelly_dollars
            reason.append(f"EV: {ev:.2%}")

        if sentiment_summary["adjustment"] != 0:
            reason.append(f"F&G: {sentiment_summary['adjustment']:+.2f}")

        return {
            "action": action,
            "market_id": market_id,
            "question": question,
            "price": price,
            "volume": volume,
            "my_p": my_p,
            "ev": ev,
            "kelly_frac": kelly_frac,
            "bet_size": bet_size,
            "fear_greed": sentiment_summary.get("fear_greed"),
            "reason": "; ".join(reason) if reason else "No signal",
            "recommendation": sentiment_summary.get("recommendation", ""),
        }

    def scan_markets(self, keywords: List[str] = None) -> List[Dict]:
        """
        Scan markets for opportunities.

        Args:
            keywords: Keywords to filter (e.g., ["BTC", "ETH"])

        Returns:
            List of market analyses
        """
        if keywords is None:
            keywords = ["BTC", "ETH", "Bitcoin", "Ethereum"]

        results = []

        markets = self.data.get_markets(limit=100)

        for mkt in markets:
            if isinstance(mkt, dict):
                question = mkt.get("question", "").lower()
                if any(kw.lower() in question for kw in keywords):
                    analysis = self.analyze_market(mkt)
                    results.append(analysis)

        results.sort(key=lambda x: x.get("ev", 0), reverse=True)

        return results

    def run_live_scan(
        self, keywords: List[str] = None, limit: int = 5, interval: int = 300
    ):
        """
        Run live scan and show top opportunities.

        Args:
            keywords: Keywords to search
            limit: Max opportunities to show

        Returns:
            List of opportunities
        """
        logger.info("Scanning Polymarket for opportunities...")

        opportunities = self.scan_markets(keywords)

        opportunities = [o for o in opportunities if o["action"] == "BET"][:limit]

        print(f"\n{'=' * 70}")
        print(
            f"POLYMARKET TRADING SCAN - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        print(f"{'=' * 70}")

        sentiment = self.sentiment.get_sentiment_summary()
        if sentiment["fear_greed"]:
            fg = sentiment["fear_greed"]
            print(f"\nFear & Greed: {fg['value']} ({fg['classification']})")
            print(f"Adjustment: {sentiment['adjustment']:+.2f}")

        print(f"\nBankroll: ${self.bankroll:,.2f}")
        print(f"Min EV: {self.config.get('EV_THRESHOLD', 0.02):.0%}")
        print(f"Kelly Mult: {self.config.get('KELLY_MULTIPLIER', 0.5):.1f}x")
        print(f"Min Volume: ${self.config.get('MIN_VOLUME', 500000):,}")
        print(f"Sentiment Strength: {self.config.get('SENTIMENT_STRENGTH', 1.0):.1f}")

        print(f"\n{'=' * 70}")

        if opportunities:
            print(f"\n>>> TOP {len(opportunities)} OPPORTUNITIES:\n")

            for i, opp in enumerate(opportunities, 1):
                print(f"{i}. {opp['question'][:60]}")
                print(
                    f"   Price: {opp['price']:.1%} | Your Prob: {opp['my_p']:.1%} | EV: {opp['ev']:.1%}"
                )
                print(f"   Bet: ${opp['bet_size']:.2f} ({opp['kelly_frac']:.1%} Kelly)")
                print(f"   Reason: {opp['reason']}")
                print()

                # Send Telegram alert for high EV opportunities
                self.alert_manager.check_and_alert_opportunity(opp)
        else:
            print("\n*** No opportunities found (no markets meet your criteria)")

        print(f"{'=' * 70}\n")

        return opportunities

    def backtest_with_sentiment(self):
        """Run backtest using sentiment-adjusted probabilities."""
        print("\n" + "=" * 60)
        print("BACKTEST WITH SENTIMENT ADJUSTMENT")
        print("=" * 60)

        backtester = PolymarketBacktester()
        results = backtester.run_scenario_analysis(n_markets=50)

        print(f"\nScenario Analysis (50 markets):\n")
        print(f"{'Scenario':<15} {'Trades':<8} {'Win%':<8} {'ROI%':<10} {'Sharpe':<8}")
        print("-" * 60)

        for name, res in results.items():
            print(
                f"{name.capitalize():<15} {res['total_trades']:<8} "
                f"{res['win_rate'] * 100:.1f}%   {res['roi']:.1f}%      {res['sharpe_ratio']:.2f}"
            )

        print("-" * 60)

        best = max(results.items(), key=lambda x: x[1]["roi"])
        print(f"\n>>> Best case ROI: {best[1]['roi']:.1f}% ({best[0]})")
        print(f"   Sharpe: {best[1]['sharpe_ratio']:.2f}")

        return results


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Polymarket Trading Bot")
    parser.add_argument("--scan", action="store_true", help="Scan for opportunities")
    parser.add_argument(
        "--keywords", nargs="+", default=["BTC", "ETH"], help="Keywords"
    )
    parser.add_argument("--backtest", action="store_true", help="Run backtest")
    parser.add_argument("--test", action="store_true", help="Test sentiment")
    parser.add_argument("--loop", action="store_true", help="Run continuously")
    parser.add_argument(
        "--interval", type=int, default=300, help="Loop interval in seconds"
    )

    args = parser.parse_args()

    bot = TradingBot()

    if args.test:
        from sentiment import analyze_market_sentiment

        analyze_market_sentiment("BTC")

    elif args.loop:
        print(f"\nStarting continuous loop (interval: {args.interval}s)")
        print("Press Ctrl+C to stop\n")
        while True:
            bot.run_live_scan(keywords=args.keywords, interval=args.interval)
            time.sleep(args.interval)

    elif args.scan:
        bot.run_live_scan(keywords=args.keywords)

    elif args.backtest:
        bot.backtest_with_sentiment()

    else:
        print("""
Polymarket Trading Bot
====================

Usage:
  python trading_bot.py --scan       # Single scan
  python trading_bot.py --scan --loop # Continuous scan
  python trading_bot.py --backtest   # Run backtest
  python trading_bot.py --test       # Test sentiment

Examples:
  python trading_bot.py --scan
  python trading_bot.py --scan --loop --interval 180 --keywords BTC ETH
        """)


if __name__ == "__main__":
    main()
