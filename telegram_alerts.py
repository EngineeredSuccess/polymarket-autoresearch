#!/usr/bin/env python3
"""
Telegram Alerts for Polymarket Trading Bot

Send alerts when:
- Trading opportunity detected
- Trade executed
- Profit/loss threshold reached
- Drawdown warning

Setup:
1. Create bot: @BotFather on Telegram
2. Get bot token: xxxxx:yyyyyyyy
3. Get chat ID: @userinfobot or start conversation with @your_bot
4. Add token and chat ID to config or environment
"""

import os
import json
import time
import requests
from datetime import datetime
from typing import Optional, Dict, List


class TelegramAlerts:
    """Send alerts to Telegram when trading events occur."""

    def __init__(self, bot_token: str = None, chat_id: str = None):
        # Try environment variables first, then config file
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN")
        self.chat_id = chat_id or os.getenv("TELEGRAM_CHAT_ID")

        # Load from config file if not set
        if not self.bot_token or not self.chat_id:
            config_path = os.path.join(os.path.dirname(__file__), "telegram_config.env")
            if os.path.exists(config_path):
                with open(config_path) as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#"):
                            if "=" in line:
                                key, value = line.split("=", 1)
                                if key == "TELEGRAM_BOT_TOKEN":
                                    self.bot_token = value.strip()
                                elif key == "TELEGRAM_CHAT_ID":
                                    self.chat_id = value.strip()

        self.api_url = (
            f"https://api.telegram.org/bot{self.bot_token}" if self.bot_token else None
        )

    def send_message(self, text: str, parse_mode: str = "Markdown") -> bool:
        """
        Send message to Telegram.

        Args:
            text: Message text
            parse_mode: "Markdown" or "HTML"

        Returns:
            True if successful
        """
        if not self.api_url or not self.chat_id:
            print(f"[TELEGRAM DISABLED] {text}")
            return False

        try:
            url = f"{self.api_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": parse_mode}
            response = requests.post(url, json=data, timeout=10)
            return response.status_code == 200
        except Exception as e:
            print(f"Error sending Telegram message: {e}")
            return False

    def send_opportunity_alert(self, opportunity: Dict) -> bool:
        """
        Send alert when trading opportunity detected.

        Args:
            opportunity: Dict with market info

        Returns:
            True if successful
        """
        emoji = "[SIGNAL]"

        message = f"""
{emoji} *TRADING OPPORTUNITY*

*Market:* {opportunity.get("question", "N/A")[:50]}
*Price:* {opportunity.get("price", 0):.1%}
*Your Prob:* {opportunity.get("my_p", 0):.1%}
*EV:* {opportunity.get("ev", 0):.2%}
*Bet Size:* ${opportunity.get("bet_size", 0):.2f}

_Confidence:_ {"High" if opportunity.get("ev", 0) > 0.15 else "Medium"}
"""
        return self.send_message(message.strip())

    def send_trade_alert(self, trade: Dict) -> bool:
        """
        Send alert when trade executed.

        Args:
            trade: Dict with trade info
        """
        status = "[WIN]" if trade.get("won") else "[LOSS]"
        pnl = trade.get("profit", 0)
        pnl_str = f"+${pnl:.2f}" if pnl > 0 else f"-${abs(pnl):.2f}"

        message = f"""
[BELL] *TRADE {status}*

*Bet:* ${trade.get("bet_size", 0):.2f}
*P&L:* {pnl_str}
*Bankroll:* ${trade.get("bankroll", 0):,.2f}
"""
        return self.send_message(message.strip())

    def send_daily_summary(self, metrics: Dict) -> bool:
        """
        Send daily performance summary.

        Args:
            metrics: Dict with daily metrics
        """
        message = f"""
[CHART] *DAILY SUMMARY*

*Trades:* {metrics.get("total_trades", 0)}
*Win Rate:* {metrics.get("win_rate", 0):.1f}%
*ROI:* {metrics.get("roi", 0):.2f}%
*Sharpe:* {metrics.get("sharpe", 0):.2f}
*Max DD:* {metrics.get("max_drawdown", 0):.1f}%
*Bankroll:* ${metrics.get("final_bankroll", 0):,.2f}
"""
        return self.send_message(message.strip())

    def send_drawdown_warning(self, drawdown: float, bankroll: float) -> bool:
        """
        Send warning when drawdown threshold reached.

        Args:
            drawdown: Current drawdown percentage
            bankroll: Current bankroll
        """
        message = f"""
[WARN] *DRAWDOWN WARNING*

*Current DD:* {drawdown:.1f}%
*Bankroll:* ${bankroll:,.2f}

_Trading paused until drawdown recovers._
"""
        return self.send_message(message.strip())

    def send_error_alert(self, error: str) -> bool:
        """Send error notification."""
        message = f"""
[ERROR] *ERROR ALERT*

```
{error}
```
"""
        return self.send_message(message)


class TradingAlertManager:
    """Manage alerts for trading bot."""

    def __init__(self, telegram: TelegramAlerts = None):
        self.telegram = telegram or TelegramAlerts()
        self.min_opportunity_ev = 0.10  # Only alert for EV > 10%
        self.trade_count = 0
        self.daily_summary_time = None

    def check_and_alert_opportunity(self, opportunity: Dict) -> bool:
        """
        Check opportunity and send alert if significant.

        Args:
            opportunity: Trading opportunity dict

        Returns:
            True if alert sent
        """
        ev = opportunity.get("ev", 0)

        if ev >= self.min_opportunity_ev:
            return self.telegram.send_opportunity_alert(opportunity)

        return False

    def notify_trade(self, trade: Dict) -> bool:
        """Notify about executed trade."""
        self.trade_count += 1
        return self.telegram.send_trade_alert(trade)

    def check_drawdown(
        self, drawdown: float, bankroll: float, threshold: float = 0.20
    ) -> bool:
        """Check drawdown and warn if threshold exceeded."""
        if drawdown >= threshold:
            return self.telegram.send_drawdown_warning(drawdown, bankroll)
        return False


def test_telegram():
    """Test Telegram setup."""
    print("=" * 60)
    print("TELEGRAM ALERT TEST")
    print("=" * 60)

    # Test send - TelegramAlerts will load from env or config file
    telegram = TelegramAlerts()

    print(f"\nBot Token: {'[SET]' if telegram.bot_token else '[NOT SET]'}")
    print(f"Chat ID: {'[SET]' if telegram.chat_id else '[NOT SET]'}")

    if not telegram.bot_token or not telegram.chat_id:
        print("\n[!] Telegram not configured!")
        print("\nSetup instructions:")
        print("1. Message @BotFather on Telegram")
        print("2. Create new bot, get token")
        print("3. Message @userinfobot to get your chat ID")
        print("4. Set in telegram_config.env or environment variables")
        return False

    # Test opportunity
    print("\nTest: Sending opportunity alert...")
    test_opp = {
        "question": "Will BTC hit $100K by 2026?",
        "price": 0.45,
        "my_p": 0.55,
        "ev": 0.22,
        "bet_size": 500.0,
    }
    result = telegram.send_opportunity_alert(test_opp)
    print(f"Result: {'[OK]' if result else '[FAIL]'}")

    # Test trade
    print("\nTest: Sending trade alert...")
    test_trade = {"won": True, "bet_size": 500.0, "profit": 611.0, "bankroll": 10500.0}
    result = telegram.send_trade_alert(test_trade)
    print(f"Result: {'[OK]' if result else '[FAIL]'}")

    return True


if __name__ == "__main__":
    test_telegram()
