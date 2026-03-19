import sys

sys.path.insert(0, ".")
from data_pipeline import PolymarketData

data = PolymarketData()

print("Testing Polymarket API...\n")

# Get markets
print("1. Fetching markets...")
markets = data.get_markets(limit=5)
print(f"   Found {len(markets)} markets")

if markets:
    m = markets[0]
    print(f"   Question: {m.get('question', 'N/A')[:60]}")
    print(f"   Prices: {m.get('outcomePrices', ['N/A'])}")
    print(f"   Volume: ${float(m.get('volume', 0) or 0):,.0f}")

# Get crypto markets
print("\n2. Searching crypto markets...")
crypto = data.get_crypto_markets(limit=5)
print(f"   Found {len(crypto)} crypto markets")
for c in crypto[:3]:
    print(f"   - {c.get('question', 'N/A')[:45]}")
    print(f"     @ YES: {c.get('yes_price', 0):.2f}, NO: {c.get('no_price', 0):.2f}")

print("\nAPI test: SUCCESS")
