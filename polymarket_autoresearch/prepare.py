#!/usr/bin/env python3
"""
Prepare Polymarket data for backtesting.
Downloads historical data from Polymarket API and Fear & Greed index.
"""

import os
import json
import time
import random
from datetime import datetime, timedelta
from typing import List, Dict
import numpy as np


# ============================================================================
# DATA PATHS - Modify these if you want different locations
# ============================================================================
DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
MARKETS_FILE = os.path.join(DATA_DIR, "markets.json")
HISTORICAL_FILE = os.path.join(DATA_DIR, "historical.csv")


def setup_directories():
    """Create data directories if they don't exist."""
    os.makedirs(DATA_DIR, exist_ok=True)
    print(f"Data directory: {DATA_DIR}")


def get_polymarket_markets(limit: int = 100) -> List[Dict]:
    """
    Fetch active markets from Polymarket Gamma API.
    No API key required for public data.

    Args:
        limit: Maximum number of markets to fetch

    Returns:
        List of market dictionaries
    """
    import requests

    url = "https://gamma-api.polymarket.com/markets"
    params = {"limit": limit, "closed": False}

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        markets = response.json()

        # Filter for crypto-related markets
        crypto_markets = []
        crypto_keywords = ["btc", "bitcoin", "eth", "ethereum", "crypto", "coin"]

        for m in markets:
            question = m.get("question", "").lower()
            if any(kw in question for kw in crypto_keywords):
                crypto_markets.append(m)

        print(
            f"Fetched {len(markets)} total markets, {len(crypto_markets)} crypto-related"
        )
        return crypto_markets if crypto_markets else markets[:20]

    except Exception as e:
        print(f"Error fetching markets: {e}")
        return generate_simulated_markets(50)


def get_fear_greed_index() -> Dict:
    """
    Fetch current Fear & Greed Index.

    Returns:
        Dict with value (0-100), classification
    """
    import requests

    url = "https://api.alternative.me/fng/"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()

        if "data" in data and len(data["data"]) > 0:
            item = data["data"][0]
            return {
                "value": int(item["value"]),
                "classification": item["value_classification"],
                "timestamp": int(item["timestamp"]),
            }
    except Exception as e:
        print(f"Error fetching Fear & Greed: {e}")

    return {"value": 50, "classification": "Neutral"}


def generate_simulated_markets(n: int = 100) -> List[Dict]:
    """
    Generate simulated Polymarket-like data for backtesting.
    Uses realistic distributions based on actual Polymarket data.

    Args:
        n: Number of markets to generate

    Returns:
        List of simulated market dictionaries
    """
    np.random.seed(42)

    markets = []
    market_templates = [
        "Will BTC hit ${}K by {}?",
        "Will ETH be above ${}?",
        "Will BTC be up in {} minutes?",
        "Will {} happen by {}?",
    ]

    price_levels = [50000, 75000, 100000, 150000, 200000]
    timeframes = ["Dec 2025", "Mar 2026", "Jun 2026", "2026", "2027"]

    for i in range(n):
        template = random.choice(market_templates)

        if "BTC" in template:
            if "hit" in template:
                price = random.choice(price_levels)
                time_f = random.choice(timeframes)
                question = template.format(price, time_f)
            else:
                question = template.format(random.choice([5, 15, 30, 60]))
        elif "ETH" in template:
            price = random.choice([2000, 3000, 4000, 5000])
            question = template.format(price)
        else:
            event = random.choice(
                [
                    "major announcement",
                    "regulatory decision",
                    "market crash",
                    " ATH achieved",
                ]
            )
            time_f = random.choice(timeframes)
            question = template.format(event, time_f)

        # Generate realistic price (usually near 50%, sometimes mispriced)
        base_price = np.random.uniform(0.25, 0.75)

        # Sometimes add mispricing (the edge we're looking for)
        if np.random.random() < 0.3:
            base_price += np.random.uniform(-0.15, 0.15)

        price = np.clip(base_price, 0.05, 0.95)

        # Generate volume (log-normal distribution)
        volume = int(np.random.lognormal(14, 2))  # ~$1M median

        markets.append(
            {
                "question": question,
                "yes_price": round(price, 4),
                "no_price": round(1 - price, 4),
                "volume": volume,
                "liquidity": volume * 0.3,
                "market_id": f"sim_{i:04d}",
                "outcomes": ["Yes", "No"],
                "outcomePrices": [str(round(price, 4)), str(round(1 - price, 4))],
            }
        )

    return markets


def generate_historical_outcomes(markets: List[Dict]) -> List[Dict]:
    """
    Generate historical resolution data for backtesting.

    Key insight: Fear & Greed creates predictable mispricings.
    - Extreme Fear (F&G < 30): YES is underpriced (contrarian = buy YES)
    - Extreme Greed (F&G > 70): YES is overpriced (sell YES)

    Args:
        markets: List of market dictionaries

    Returns:
        List of dicts with true_outcome and fg_value
    """
    np.random.seed(42)

    historical = []

    for i, m in enumerate(markets):
        base_price = float(m.get("yes_price", 0.5))

        # Generate F&G for this period (simulates having real-time sentiment)
        fg_value = np.random.randint(15, 85)

        # Calculate edge based on F&G:
        # F&G < 30 (Fear): YES is underpriced - buy YES
        # F&G > 70 (Greed): YES is overpriced - sell YES
        # F&G 30-70: Efficient market

        if fg_value < 30:
            edge = 0.15  # 15% edge for YES (strong contrarian)
        elif fg_value > 70:
            edge = -0.15  # -15% edge for YES (strong sell)
        else:
            edge = 0.0  # No edge

        # True probability = market price + edge
        true_prob = base_price + edge
        true_prob = np.clip(true_prob, 0.1, 0.9)

        # Market price includes some sentiment but not full edge
        market_price = base_price + edge * 0.3  # Market prices in 30% of edge
        market_price = np.clip(market_price, 0.1, 0.9)

        # Outcome based on TRUE probability (small noise for realism)
        outcome_noise = np.random.normal(0, 0.03)
        true_prob_noisy = np.clip(true_prob + outcome_noise, 0.1, 0.9)

        true_outcome = 1 if np.random.random() < true_prob_noisy else 0

        historical.append(
            {
                "market_id": m.get("market_id", ""),
                "question": m.get("question", ""),
                "market_price": round(market_price, 4),
                "true_price": round(true_prob, 4),  # Hidden from us
                "fg_value": fg_value,
                "volume": m.get("volume", 0),
                "true_outcome": true_outcome,
            }
        )

    return historical


def save_markets(markets: List[Dict]):
    """Save markets to JSON file."""
    with open(MARKETS_FILE, "w") as f:
        json.dump(markets, f, indent=2)
    print(f"Saved {len(markets)} markets to {MARKETS_FILE}")


def save_historical(historical: List[Dict]):
    """Save historical data to CSV."""
    import csv

    fieldnames = [
        "market_id",
        "question",
        "market_price",
        "volume",
        "true_outcome",
        "fg_value",
    ]

    # Filter out extra fields
    clean_data = []
    for row in historical:
        clean_row = {k: row[k] for k in fieldnames if k in row}
        clean_data.append(clean_row)

    with open(HISTORICAL_FILE, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_data)

    print(f"Saved {len(historical)} historical records to {HISTORICAL_FILE}")


def load_markets() -> List[Dict]:
    """Load markets from JSON file."""
    if os.path.exists(MARKETS_FILE):
        with open(MARKETS_FILE, "r") as f:
            return json.load(f)
    return []


def load_historical() -> List[Dict]:
    """Load historical data from CSV."""
    import csv

    if os.path.exists(HISTORICAL_FILE):
        with open(HISTORICAL_FILE, "r") as f:
            reader = csv.DictReader(f)
            return list(reader)
    return []


def prepare_data(n_markets: int = 100, use_real: bool = False):
    """
    Main data preparation function.

    Args:
        n_markets: Number of markets to generate/fetch
        use_real: If True, try to fetch from Polymarket API
    """
    print("=" * 60)
    print("POLYMARKET DATA PREPARATION")
    print("=" * 60)
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    setup_directories()

    # Get Fear & Greed
    fg = get_fear_greed_index()
    print(f"\nFear & Greed Index: {fg['value']} ({fg['classification']})")

    # Get markets
    if use_real:
        markets = get_polymarket_markets(n_markets)
    else:
        print("\nGenerating simulated markets for backtesting...")
        markets = generate_simulated_markets(n_markets)

    save_markets(markets)

    # Generate historical outcomes
    print("\nGenerating historical resolution data...")
    historical = generate_historical_outcomes(markets)
    save_historical(historical)

    # Summary
    print("\n" + "=" * 60)
    print("DATA SUMMARY")
    print("=" * 60)
    print(f"Total markets: {len(markets)}")
    print(f"Historical records: {len(historical)}")
    print(f"Avg volume: ${np.mean([m.get('volume', 0) for m in markets]):,.0f}")
    print(
        f"Avg price: {np.mean([float(m.get('yes_price', 0.5)) for m in markets]):.2%}"
    )
    print("=" * 60)

    return markets, historical


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare Polymarket data")
    parser.add_argument("--n", type=int, default=100, help="Number of markets")
    parser.add_argument("--real", action="store_true", help="Use real Polymarket API")

    args = parser.parse_args()

    prepare_data(n_markets=args.n, use_real=args.real)
