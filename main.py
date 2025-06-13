import asyncio
import requests
from dotenv import load_dotenv
from datetime import datetime

from pandas import DataFrame

from clients.kalshi import KalshiClient
from clients.polymarket import PolymarketClient

load_dotenv()

def arbitrage_check(kalshi_market_data: dict, polymarket_market_data: dict) -> bool:
    
    # DAYS_TO_RESOLUTION = (datetime.strptime(polymarket_market_data["end_date_iso"], "%Y-%m-%dT%H:%M:%SZ") - datetime.now()).days
    # print(f"{DAYS_TO_RESOLUTION=}")
    
    kalshi_yes_price, kalshi_no_price = kalshi_market_data["yes_price"], kalshi_market_data["no_price"]
    polymarket_yes_price, polymarket_no_price = polymarket_market_data["yes_price"], polymarket_market_data["no_price"]
    
    yes_cheapest = min(kalshi_yes_price, polymarket_yes_price)
    no_cheapest = min(kalshi_no_price, polymarket_no_price)
    
    bundle_cost = yes_cheapest + no_cheapest
    profit = 1 - bundle_cost
    
    return profit > 0

async def main():
    """Test the API endpoint via HTTP request"""
    grouped_markets_url = "https://api.okaybet.app/api/v1/grouped-markets/groups/markets"
    
    kalshi_client = KalshiClient()
    polymarket_client = PolymarketClient()
    
    try:
        print(f"Making GET request to: {grouped_markets_url}")
        response = requests.get(grouped_markets_url, timeout=10)
        # print(f"{response=}")
        
        if response.status_code == 200:
            # print(f"{response.json()=}")
            markets = response.json()
            for market in markets[2:3]:
                market_ids: dict[str, list[str]] = market["market_ids"]
                
                ### DELETE THIS LATER
                if not(market_ids.get('kalshi') and market_ids.get('polymarket')): # if no kalshi or polymarket market, skip
                    continue
                
                kalshi_market_id: str = market_ids['kalshi'][0]
                polymarket_market_id: str = market_ids['polymarket'][0]
                
                print(f"{kalshi_market_id=}")
                print(f"{polymarket_market_id=}")
                kalshi_market_data: dict = kalshi_client.get_market_encriched(market_id=kalshi_market_id)
                polymarket_market_data: dict = polymarket_client.get_market_encriched(market_id=polymarket_market_id)
                
                arbitrage_found: bool = arbitrage_check(kalshi_market_data, polymarket_market_data)
                if arbitrage_found:
                    print(f"Arbitrage found for market: {market['title']}")
                
                # print(f"{kalshi_market_data=}")
                # print(f"{polymarket_market_data=}")
            
        else:
            print(f"Error {response.status_code}: {response.text}")
            
    except requests.exceptions.ConnectionError:
        print("❌ Connection failed! Make sure your FastAPI server is running:")
        print("   Run: make dev")
    except requests.exceptions.Timeout:
        print("❌ Request timed out")
    except Exception as e:
        print(f"❌ Request failed: {e}")

if __name__ == "__main__":
    asyncio.run(main())
