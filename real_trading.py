import os
import time
import logging
from typing import Optional, Dict, List
from dataclasses import dataclass

from dotenv import load_dotenv

load_dotenv("telegram_config.env")

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import (
        OrderArgs,
        MarketOrderArgs,
        OrderType,
        BalanceAllowanceParams,
        AssetType,
    )
    from py_clob_client.order_builder.constants import BUY, SELL

    HAS_CLOB_CLIENT = True
except ImportError:
    HAS_CLOB_CLIENT = False


logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


@dataclass
class WalletConfig:
    private_key: str
    funder_address: str
    signature_type: int = 1


class PolymarketCLOBTrader:
    """
    Real trading via Polymarket CLOB API.

    Requires:
    - py-clob-client installed
    - USDC on Polygon network
    - Private key from MetaMask/EOA wallet
    """

    CLOB_API = "https://clob.polymarket.com"
    CHAIN_ID = 137
    COLLATERAL_TOKEN = "0x4D97DCd97eC945f40cF65F87097ACe5EA0476045"

    def __init__(self):
        if not HAS_CLOB_CLIENT:
            raise ImportError(
                "py-clob-client not installed. Run: pip install py-clob-client"
            )

        pk = os.getenv("POLYMARKET_PRIVATE_KEY", "").strip()
        funder = os.getenv("POLYMARKET_FUNDER_ADDRESS", "").strip()
        sig_type = int(os.getenv("POLYMARKET_SIGNATURE_TYPE", "1"))
        host = os.getenv("POLYMARKET_HOST", self.CLOB_API)

        if not pk or not funder:
            raise ValueError(
                "Missing wallet config. Add to telegram_config.env:\n"
                "  POLYMARKET_PRIVATE_KEY=<your-private-key>\n"
                "  POLYMARKET_FUNDER_ADDRESS=<your-wallet-address>\n"
                "  POLYMARKET_SIGNATURE_TYPE=1"
            )

        self._wallet_config = WalletConfig(pk, funder, sig_type)
        self._client = None
        self._connected = False

    def connect(self) -> bool:
        """Initialize CLOB client and derive API credentials."""
        try:
            logger.info("Connecting to Polymarket CLOB...")
            self._client = ClobClient(
                host=self.CLOB_API,
                key=self._wallet_config.private_key,
                chain_id=self.CHAIN_ID,
                signature_type=self._wallet_config.signature_type,
                funder=self._wallet_config.funder_address,
            )
            self._client.set_api_creds(self._client.create_or_derive_api_creds())
            self._connected = True
            logger.info(
                f"Connected! Funder: {self._wallet_config.funder_address[:8]}..."
            )
            return True
        except Exception as e:
            logger.error(f"Connection failed: {e}")
            return False

    def get_balance(self) -> float:
        """Get USDC balance in dollars."""
        if not self._connected:
            return 0.0
        try:
            balance = self._client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            return float(balance) / 1e6
        except Exception as e:
            logger.error(f"Balance check failed: {e}")
            return 0.0

    def check_allowance(self) -> bool:
        """Check if exchange contract is approved to spend USDC."""
        if not self._connected:
            return False
        try:
            result = self._client.get_balance_allowance(
                BalanceAllowanceParams(asset_type=AssetType.COLLATERAL)
            )
            return float(result) > 0
        except Exception as e:
            logger.error(f"Allowance check failed: {e}")
            return False

    def set_allowance(self) -> bool:
        """Approve exchange contract to spend USDC."""
        if not self._connected:
            return False
        try:
            logger.info("Setting token allowance...")
            result = self._client.approve_token(
                token=self.COLLATERAL_TOKEN, amount=10_000_000_000_000
            )
            logger.info(f"Allowance set: {result}")
            time.sleep(2)
            return True
        except Exception as e:
            logger.error(f"Allowance failed: {e}")
            return False

    def get_token_id(self, condition_id: str, market: Dict) -> Optional[str]:
        """Extract YES token ID from market data."""
        outcomes = market.get("outcomes", [])
        if not outcomes:
            outcomes = market.get("outcome", [])

        tokens = market.get("conditionIds", [])
        if not tokens:
            return None

        return tokens[0]

    def place_market_buy(self, token_id: str, amount: float) -> Dict:
        """
        Place a market BUY order (FOK - fill or kill).

        Args:
            token_id: The market's YES token ID
            amount: Dollar amount of USDC to spend

        Returns:
            Order response dict
        """
        if not self._connected:
            if not self.connect():
                return {"success": False, "error": "Not connected"}

        try:
            order_args = MarketOrderArgs(
                token_id=token_id, amount=amount, side=BUY, order_type=OrderType.FOK
            )
            signed = self._client.create_market_order(order_args)
            response = self._client.post_market_order(signed)
            logger.info(f"Market order placed: {response}")
            return {"success": True, "response": response}
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"success": False, "error": str(e)}

    def place_limit_buy(self, token_id: str, size: float, price: float) -> Dict:
        """
        Place a limit BUY order (GTC - good till cancelled).

        Args:
            token_id: The market's YES token ID
            size: Number of shares to buy
            price: Limit price (0.0 - 1.0)
        """
        if not self._connected:
            if not self.connect():
                return {"success": False, "error": "Not connected"}

        try:
            order_args = OrderArgs(token_id=token_id, size=size, price=price, side=BUY)
            signed = self._client.create_order(order_args)
            response = self._client.post_order(signed, OrderType.GTC)
            logger.info(f"Limit order placed: {response}")
            return {"success": True, "response": response}
        except Exception as e:
            logger.error(f"Order failed: {e}")
            return {"success": False, "error": str(e)}

    def get_positions(self) -> List[Dict]:
        """Get current open positions."""
        if not self._connected:
            return []
        try:
            return self._client.get_positions() or []
        except Exception as e:
            logger.error(f"Positions fetch failed: {e}")
            return []

    def get_orders(self) -> List[Dict]:
        """Get open orders."""
        if not self._connected:
            return []
        try:
            return self._client.get_orders() or []
        except Exception as e:
            logger.error(f"Orders fetch failed: {e}")
            return []

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a specific order."""
        if not self._connected:
            return False
        try:
            self._client.cancel(order_id)
            return True
        except Exception as e:
            logger.error(f"Cancel failed: {e}")
            return False

    def cancel_all(self) -> bool:
        """Cancel all open orders."""
        if not self._connected:
            return False
        try:
            self._client.cancel_all()
            return True
        except Exception as e:
            logger.error(f"Cancel all failed: {e}")
            return False

    def get_order_book(self, token_id: str) -> Dict:
        """Get order book for a market."""
        if not self._connected:
            self.connect()
        try:
            return self._client.get_order_book(token_id)
        except Exception as e:
            logger.error(f"Order book fetch failed: {e}")
            return {}

    def trade_from_signal(self, signal: Dict, dry_run: bool = True) -> Dict:
        """
        Execute trade from a trading signal.

        Args:
            signal: Dict from TradingBot.analyze_market()
            dry_run: If True, simulate without placing order

        Returns:
            Result dict with success status
        """
        if signal.get("action") != "BET":
            return {"success": False, "error": "No BET signal"}

        token_id = signal.get("token_id") or signal.get("market_id")
        if not token_id:
            market = signal.get("market", {})
            token_id = self.get_token_id("", market)

        if not token_id:
            return {"success": False, "error": "No token_id found in signal"}

        bet_size = signal.get("bet_size", 0)
        price = signal.get("price", 0)

        if dry_run:
            logger.info(
                f"[DRY RUN] Would place market buy: {bet_size:.2f} USDC @ {price:.1%}"
            )
            return {
                "success": True,
                "dry_run": True,
                "token_id": token_id,
                "amount": bet_size,
                "price": price,
                "question": signal.get("question", "Unknown"),
            }

        return self.place_market_buy(token_id, bet_size)


def setup_wallet_instructions():
    """Print instructions for setting up wallet for trading."""
    print("""
=== POLYMARKET REAL TRADING SETUP ===

1. GET METAMASK (if you don't have it)
   https://metamask.io/download/

2. ADD POLYGON NETWORK TO METAMASK
   Network Name: Polygon Mainnet
   RPC URL: https://polygon-rpc.com/
   Chain ID: 137
   Currency: MATIC
   Block Explorer: https://polygonscan.com/

3. GET USDC ON POLYGON
   - Option A: Buy USDC on Coinbase, withdraw to Polygon
   - Option B: Bridge ETH to Polygon, swap to USDC
   - Option C: Use Multichain/Stargate bridge
   - Recommended: Start with $100-500 for testing

4. EXPORT PRIVATE KEY FROM METAMASK
   - Open MetaMask
   - Click account icon -> Account Details
   - Click "Export Private Key"
   - Copy the 64-character hex string

5. ADD CREDENTIALS TO telegram_config.env
   Add these lines:
   
   POLYMARKET_PRIVATE_KEY=your-64-char-private-key-here
   POLYMARKET_FUNDER_ADDRESS=0xYourWalletAddressHere
   POLYMARKET_SIGNATURE_TYPE=1

6. VERIFY SETUP
   python real_trading.py --status

7. SET ALLOWANCE (first time only)
   python real_trading.py --approve

8. START TRADING
   python real_trading.py --trade
   python real_trading.py --trade --auto  # Auto-confirm trades
""")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Polymarket Real Trading")
    parser.add_argument(
        "--status", action="store_true", help="Check balance and allowance"
    )
    parser.add_argument("--approve", action="store_true", help="Set token allowance")
    parser.add_argument("--trade", action="store_true", help="Run trading loop")
    parser.add_argument("--dry", action="store_true", help="Dry run mode")
    parser.add_argument("--setup", action="store_true", help="Show setup instructions")

    args = parser.parse_args()

    if args.setup:
        setup_wallet_instructions()
    elif args.status or args.approve or args.trade:
        try:
            trader = PolymarketCLOBTrader()
            if args.status:
                trader.connect()
                bal = trader.get_balance()
                allow = trader.check_allowance()
                print(f"\nBalance: ${bal:,.2f} USDC")
                print(f"Allowance: {'OK' if allow else 'NEEDS APPROVAL'}")
            elif args.approve:
                trader.connect()
                if trader.set_allowance():
                    print("Allowance set successfully!")
                else:
                    print("Allowance failed. Check your balance.")
            elif args.trade:
                trader.connect()
                from trading_bot import TradingBot

                bot = TradingBot()
                opportunities = bot.run_live_scan(limit=3)

                if opportunities:
                    for opp in opportunities:
                        result = trader.trade_from_signal(opp, dry_run=not args.dry)
                        print(f"\nResult: {result}")
                        if not args.dry and result.get("success"):
                            break
        except (ImportError, ValueError) as e:
            print(f"Error: {e}")
            print("\nRun: pip install py-clob-client")
            print("Then add wallet credentials to telegram_config.env")
    else:
        setup_wallet_instructions()
