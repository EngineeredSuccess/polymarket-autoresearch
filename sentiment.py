import requests
from datetime import datetime
from typing import Dict, Optional
import re


class CryptoSentiment:
    """
    Crypto sentiment analysis for Polymarket trading.

    Uses Fear & Greed Index and simple heuristics to estimate
    market sentiment and adjust probability estimates.
    """

    FEAR_GREED_API = "https://api.alternative.me/fng/"

    def __init__(self):
        self.last_update = None
        self.cached_sentiment = None

    def get_fear_greed(self) -> Optional[Dict]:
        """
        Fetch current Fear & Greed Index.

        Returns:
            Dict with value (0-100), classification, timestamp
        """
        try:
            response = requests.get(self.FEAR_GREED_API, timeout=10)
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

        return None

    def fear_greed_to_probability(self, fg_value: int) -> float:
        """
        Convert Fear & Greed Index to probability adjustment.

        Logic:
        - Extreme Fear (F&G < 30): YES underpriced - positive adjustment
        - Extreme Greed (F&G > 70): YES overpriced - negative adjustment

        Args:
            fg_value: Fear & Greed value (0-100)

        Returns:
            Probability adjustment to ADD to market price
        """
        if fg_value <= 25:
            # Extreme Fear: YES underpriced - buy YES (positive edge)
            return 0.08
        elif fg_value <= 45:
            # Fear: Slight edge to YES
            return 0.03
        elif fg_value <= 55:
            # Neutral: No edge
            return 0.0
        elif fg_value <= 75:
            # Greed: Slight edge to NO
            return -0.03
        else:
            # Extreme Greed: YES overpriced - sell YES (negative edge)
            return -0.08

    def get_btc_probability_adjustment(self) -> float:
        """
        Get BTC probability adjustment based on Fear & Greed.

        Returns:
            Adjustment factor to add to market price
        """
        fg = self.get_fear_greed()

        if not fg:
            return 0.0

        return self.fear_greed_to_probability(fg["value"])

    def estimate_btc_direction_probability(self, market_price: float) -> float:
        """
        Estimate true probability for BTC markets based on sentiment.

        Args:
            market_price: Current Polymarket price

        Returns:
            Estimated true probability
        """
        adjustment = self.get_btc_probability_adjustment()

        adjusted_prob = market_price + adjustment
        adjusted_prob = max(0.05, min(0.95, adjusted_prob))

        return adjusted_prob

    def get_sentiment_summary(self) -> Dict:
        """
        Get full sentiment summary for trading decisions.

        Returns:
            Dict with sentiment data and probability adjustment
        """
        fg = self.get_fear_greed()

        if not fg:
            return {
                "fear_greed": None,
                "adjustment": 0.0,
                "sentiment": "Unknown",
                "recommendation": "No data - use market price",
            }

        adjustment = self.fear_greed_to_probability(fg["value"])

        if fg["value"] <= 25:
            sentiment = "Extreme Fear - YES underpriced (buy signal)"
        elif fg["value"] <= 45:
            sentiment = "Fear - slight edge to YES"
        elif fg["value"] <= 55:
            sentiment = "Neutral - no edge"
        elif fg["value"] <= 75:
            sentiment = "Greed - slight edge to NO"
        else:
            sentiment = "Extreme Greed - YES overpriced (sell signal)"

        if abs(adjustment) >= 0.05:
            rec = "STRONG EDGE" if adjustment > 0 else "MARKET OVERBOUGHT"
        elif abs(adjustment) >= 0.03:
            rec = "Minor edge" if adjustment > 0 else "Minor overweight"
        else:
            rec = "No edge - neutral"

        return {
            "fear_greed": fg,
            "adjustment": adjustment,
            "sentiment": sentiment,
            "recommendation": rec,
        }


def analyze_market_sentiment(symbol: str = "BTC") -> Dict:
    """
    Quick function to analyze market sentiment.

    Args:
        symbol: Crypto symbol (default BTC)

    Returns:
        Sentiment analysis results
    """
    sentiment = CryptoSentiment()
    summary = sentiment.get_sentiment_summary()

    print(f"\n{'=' * 50}")
    print(f"CRYPTO SENTIMENT ANALYSIS - {symbol}")
    print(f"{'=' * 50}")

    if summary["fear_greed"]:
        fg = summary["fear_greed"]
        print(f"Fear & Greed Index: {fg['value']}")
        print(f"Classification: {fg['classification']}")
        print(f"Adjustment: {summary['adjustment']:+.2f}")
        print(f"Sentiment: {summary['sentiment']}")
        print(f"Recommendation: {summary['recommendation']}")
    else:
        print("Could not fetch sentiment data")

    print(f"{'=' * 50}\n")

    return summary


def bayesian_sentiment_update(
    prior: float, fear_greed_value: int, strength: float = 0.3
) -> float:
    """
    Apply Bayesian update using Fear & Greed sentiment.

    Logic:
    - Extreme Fear (F&G < 30): YES outcomes more likely (contrarian = buy YES)
    - Extreme Greed (F&G > 70): NO outcomes more likely (sell YES)

    Args:
        prior: Prior probability (e.g., market price)
        fear_greed_value: Fear & Greed Index (0-100)
        strength: How much to weight the evidence (0-1)

    Returns:
        Posterior probability
    """
    if fear_greed_value <= 25:
        # Extreme Fear: YES underpriced - buy YES
        likelihood = 0.60
    elif fear_greed_value <= 45:
        # Fear: Slight edge to YES
        likelihood = 0.53
    elif fear_greed_value <= 55:
        # Neutral: No edge
        likelihood = 0.50
    elif fear_greed_value <= 75:
        # Greed: Slight edge to NO
        likelihood = 0.47
    else:
        # Extreme Greed: NO overpriced - sell YES
        likelihood = 0.40

    likelihood = strength * likelihood + (1 - strength) * 0.50

    evidence_prob = 0.50

    posterior = (likelihood * prior) / evidence_prob
    posterior = max(0.01, min(0.99, posterior))

    return posterior


if __name__ == "__main__":
    analyze_market_sentiment("BTC")
