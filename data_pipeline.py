import os
import requests
import pandas as pd
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import time


class PolymarketData:
    """
    Data pipeline for fetching Polymarket data via Polymarket APIs.
    No API key required for market data.
    """

    GAMMA_API = "https://gamma-api.polymarket.com"
    CLOB_API = "https://clob.polymarket.com"

    def __init__(self, api_key: str = None):
        self.api_key = api_key

    def get_markets(self, limit: int = 50, closed: bool = False) -> List[Dict]:
        """
        Fetch active markets from Gamma API.

        Args:
            limit: Number of markets to fetch
            closed: Include closed markets

        Returns:
            List of market dictionaries
        """
        try:
            url = f"{self.GAMMA_API}/markets"
            params = {
                "limit": limit,
                "closed": closed,
            }
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching markets: {e}")
            return self._mock_market_list()

    def get_events(self, limit: int = 50) -> List[Dict]:
        """
        Fetch events from Gamma API.

        Args:
            limit: Number of events to fetch

        Returns:
            List of event dictionaries
        """
        try:
            url = f"{self.GAMMA_API}/events"
            params = {"limit": limit}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching events: {e}")
            return []

    def get_market_prices(self, market_ids: List[str]) -> Dict[str, float]:
        """
        Fetch current prices for markets from CLOB API.

        Args:
            market_ids: List of market condition IDs

        Returns:
            Dict mapping market_id to price
        """
        try:
            url = f"{self.CLOB_API}/prices"
            params = {"market": ",".join(market_ids)}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            prices = {}
            for item in data:
                if "market" in item and "price" in item:
                    prices[item["market"]] = float(item["price"])
            return prices
        except Exception as e:
            print(f"Error fetching prices: {e}")
            return {}

    def get_market_data(
        self, market_id: str = None, question: str = None
    ) -> Optional[Dict]:
        """
        Fetch detailed market data for a specific market.

        Args:
            market_id: Market condition ID
            question: Market question (for searching)

        Returns:
            Dict with price, volume, liquidity data
        """
        try:
            markets = self.get_markets(limit=100)

            if market_id:
                for m in markets:
                    if m.get("condition_id") == market_id:
                        return self._parse_market(m)
            elif question:
                for m in markets:
                    if question.lower() in m.get("question", "").lower():
                        return self._parse_market(m)

            if markets:
                return self._parse_market(markets[0])

        except Exception as e:
            print(f"Error fetching market data: {e}")

        return self._mock_market_data(market_id or "default")

    def _parse_market(self, market: Dict) -> Dict:
        """
        Parse Polymarket market data into standard format.

        Args:
            market: Raw market data from API

        Returns:
            Standardized market dict
        """
        question = market.get("question", "")

        outcomes = market.get("outcomes", ["Yes", "No"])
        outcome_prices = market.get("outcomePrices", ["0.5", "0.5"])

        yes_price = 0.5
        no_price = 0.5

        for i, outcome in enumerate(outcomes):
            if "yes" in outcome.lower():
                try:
                    yes_price = float(outcome_prices[i])
                except:
                    pass
            elif "no" in outcome.lower():
                try:
                    no_price = float(outcome_prices[i])
                except:
                    pass

        volume = float(market.get("volume", 0) or 0)
        liquidity = float(market.get("liquidity", 0) or 0)

        b = liquidity / 10 if liquidity > 0 else 100

        return {
            "market_id": market.get("condition_id", ""),
            "question": question,
            "ticker": market.get("slug", ""),
            "close_price": yes_price,
            "yes_price": yes_price,
            "no_price": no_price,
            "volume": volume,
            "liquidity": liquidity,
            "b": b,
            "pending_orders": market.get("pendingOrders", False),
            "closed": market.get("closed", False),
            "end_date": market.get("end_date", ""),
            "timestamp": int(datetime.now().timestamp() * 1000),
        }

    def get_orderbook(self, market_id: str) -> Optional[Dict]:
        """
        Fetch orderbook data from CLOB API.

        Args:
            market_id: Market condition ID

        Returns:
            Dict with bids and asks
        """
        try:
            url = f"{self.CLOB_API}/book"
            params = {"market": market_id}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error fetching orderbook: {e}")
            return None

    def get_price_history(self, market_id: str, resolution: str = "1D") -> pd.DataFrame:
        """
        Fetch historical price data.

        Args:
            market_id: Market condition ID
            resolution: Time resolution (1D, 1H, etc.)

        Returns:
            DataFrame with price history
        """
        try:
            url = f"{self.CLOB_API}/history"
            params = {"market": market_id, "resolution": resolution}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            data = response.json()

            if "ticks" in data and "prices" in data:
                return pd.DataFrame(
                    {
                        "timestamp": pd.to_datetime(data["ticks"], unit="ms"),
                        "price": data["prices"],
                    }
                )
        except Exception as e:
            print(f"Error fetching price history: {e}")

        return pd.DataFrame()

    def search_markets(self, query: str, limit: int = 10) -> List[Dict]:
        """
        Search markets by keyword.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of matching markets
        """
        try:
            url = f"{self.GAMMA_API}/search"
            params = {"query": query, "limit": limit}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            print(f"Error searching markets: {e}")
            return []

    def get_crypto_markets(self, limit: int = 20) -> List[Dict]:
        """
        Get crypto-related markets (BTC, ETH, etc.).

        Args:
            limit: Number of markets

        Returns:
            List of crypto market dictionaries
        """
        try:
            url = f"{self.GAMMA_API}/events"
            params = {"limit": 100}
            response = requests.get(url, params=params, timeout=10)
            response.raise_for_status()
            events = response.json()

            crypto_keywords = ["btc", "bitcoin", "eth", "ethereum", "crypto", "price"]
            crypto_markets = []

            for event in events:
                if isinstance(event, dict):
                    question = event.get("question", "").lower()
                    if any(kw in question for kw in crypto_keywords):
                        markets = event.get("markets", [])
                        if markets and isinstance(markets, list):
                            for m in markets:
                                if isinstance(m, dict):
                                    parsed = self._parse_market(m)
                                    parsed["question"] = question
                                    crypto_markets.append(parsed)
                                    if len(crypto_markets) >= limit:
                                        break
                    if len(crypto_markets) >= limit:
                        break

            if not crypto_markets:
                all_markets = self.get_markets(limit=100)
                for m in all_markets:
                    if isinstance(m, dict):
                        question = m.get("question", "").lower()
                        if any(kw in question for kw in crypto_keywords):
                            crypto_markets.append(self._parse_market(m))
                            if len(crypto_markets) >= limit:
                                break

            return crypto_markets
        except Exception as e:
            print(f"Error fetching crypto markets: {e}")
            return []

    def _mock_market_data(self, ticker: str) -> Dict:
        """Generate mock market data for testing."""
        import numpy as np

        base_price = 0.5
        if "up" in ticker.lower() or "yes" in ticker.lower():
            base_price = 0.45 + np.random.random() * 0.1
        elif "down" in ticker.lower() or "no" in ticker.lower():
            base_price = 0.45 + np.random.random() * 0.1

        return {
            "ticker": ticker,
            "close_price": round(base_price, 2),
            "volume": int(1000000 + np.random.random() * 5000000),
            "b": 100,
            "timestamp": int(datetime.now().timestamp() * 1000),
        }

    def _mock_market_list(self) -> List[Dict]:
        """Generate mock market list."""
        return [
            {"question": "Will BTC be up in 5 minutes?", "market_id": "mock-1"},
            {"question": "Will BTC be up in 1 hour?", "market_id": "mock-2"},
            {"question": "Will ETH be up in 5 minutes?", "market_id": "mock-3"},
            {"question": "Will BTC hit $100K by Jan 2026?", "market_id": "mock-4"},
        ]


def load_historical_markets(filepath: str) -> pd.DataFrame:
    """
    Load historical market resolution data.

    Expected columns:
    - event_name
    - market_price
    - true_outcome (0 or 1)
    - volume

    Args:
        filepath: Path to CSV file

    Returns:
        DataFrame with historical data
    """
    if os.path.exists(filepath):
        return pd.read_csv(filepath)

    print(f"Creating sample historical data at {filepath}")

    import numpy as np

    np.random.seed(42)
    n_markets = 50

    events = [f"BTC direction {i}" for i in range(n_markets)]

    df = pd.DataFrame(
        {
            "event_name": events,
            "market_price": np.random.uniform(0.3, 0.7, n_markets),
            "true_outcome": np.random.randint(0, 2, n_markets),
            "volume": np.random.randint(100000, 10000000, n_markets),
        }
    )

    os.makedirs(
        os.path.dirname(filepath) if os.path.dirname(filepath) else ".", exist_ok=True
    )
    df.to_csv(filepath, index=False)

    return df


def prepare_market_data(
    price: float, volume: float, my_p: float, b: float = 100, q=None
) -> dict:
    """
    Prepare market data dict for signal computation.

    Args:
        price: Current market price
        volume: Trading volume
        my_p: Your estimated true probability
        b: Liquidity parameter
        q: Current shares (optional)

    Returns:
        Dict ready for compute_all_signals()
    """
    import numpy as np

    if q is None:
        q = np.array([0, 0])

    return {
        "price": price,
        "volume": volume,
        "my_p": my_p,
        "b": b,
        "q": q,
        "bankroll": 10000,
        "correlated_p": np.array([my_p, 1 - my_p]),
    }


def test_polymarket_api():
    """Test the Polymarket API connection."""
    data = PolymarketData()

    print("Testing Polymarket API...")

    print("\n1. Fetching markets...")
    markets = data.get_markets(limit=5)
    print(f"   Found {len(markets)} markets")

    if markets:
        print(f"\n2. Sample market: {markets[0].get('question', 'N/A')[:50]}...")
        parsed = data._parse_market(markets[0])
        print(f"   Yes price: {parsed.get('yes_price', 'N/A')}")
        print(f"   Volume: ${parsed.get('volume', 0):,.0f}")

    print("\n3. Searching for crypto markets...")
    crypto = data.get_crypto_markets(limit=3)
    print(f"   Found {len(crypto)} crypto markets")

    for market in crypto[:2]:
        print(
            f"   - {market.get('question', 'N/A')[:40]}... @ {market.get('yes_price', 0):.2f}"
        )

    print("\nAPI test complete!")


if __name__ == "__main__":
    test_polymarket_api()
