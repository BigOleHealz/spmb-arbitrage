import os
import requests
from dotenv import load_dotenv

load_dotenv()

class KalshiClient:
    BASE_API_URL = "https://api.elections.kalshi.com/trade-api/v2"

    def __init__(self):
        self.session = requests.Session()
        self.api_key = os.getenv("KALSHI_API_KEY_ID")
        if not self.api_key:
            raise ValueError("Missing KALSHI_API_KEY_ID in environment.")
        self.session.headers.update({
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        })

    def get_market(self, market_id: str):
        url = f"{self.BASE_API_URL}/markets/{market_id}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch market '{market_id}': {e}")

    def get_market_encriched(self, market_id: str) -> dict:
        market = self.get_market(market_id)
        yes_price = market["market"]["yes_ask"]
        no_price = market["market"]["no_ask"]
        market["yes_price"] = yes_price
        market["no_price"] = no_price
        market["end_date_iso"] = market["market"]["latest_expiration_time"]
        return market
    
    def place_order(
        self,
        market_ticker: str,
        side: str,
        quantity: int,
        price: float = None,  # Required for limit orders
        order_type: str = "limit",  # "limit" or "market"
        client_order_id: str = None
    ):
        """
        Submit an order to Kalshi.

        side: "yes" or "no"
        order_type: "limit" or "market"
        """
        url = f"{self.BASE_API_URL}/portfolio/orders"

        payload = {
            "type": order_type,
            "ticker": market_ticker,
            "action": side.lower(),
            "quantity": quantity
        }

        if order_type == "limit":
            if price is None:
                raise ValueError("Limit orders require a price.")
            payload["price"] = price

        if client_order_id:
            payload["client_order_id"] = client_order_id

        try:
            response = self.session.post(url, json=payload, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Order failed: {e}")

if __name__ == "__main__":
    import json

    client = KalshiClient()
    market_id = "KXLEAVEADMIN-26-TGAB"
    try:
        market = client.get_market_encriched(market_id)
        output = json.dumps(market, indent=4)
        with open("kalshi_market.json", "w") as f:
            f.write(output)
        # print(output)
        client.place_order(
            market_ticker=market_id,
            side="yes",
            quantity=1,
            price=0.5,
            order_type="limit"
        )
    except Exception as e:
        print(f"Error fetching market: {e}")
