import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL

from dotenv import load_dotenv

load_dotenv()

class PolymarketClient:
    AUTH_URL = "https://clob.polymarket.com"
    CHAIN_ID = 137  # Polygon mainnet

    def __init__(self):
        key_path = os.getenv("POLYMARKET_API_PRIVATE_KEY_PATH")
        if not key_path:
            raise ValueError("Environment variable POLYMARKET_API_PRIVATE_KEY_PATH is not set.")

        try:
            with open(key_path, "r") as f:
                private_key = f.read()
        except FileNotFoundError:
            raise FileNotFoundError(f"Private key file not found at: {key_path}")

        self.client = ClobClient(
            self.AUTH_URL,
            key=private_key,
            chain_id=self.CHAIN_ID
        )

        self.api_creds = self.client.create_or_derive_api_creds()
        self.client.set_api_creds(self.api_creds)

    def get_market(self, market_id: str):
        return self.client.get_market(condition_id=market_id)
    
    def get_market_encriched(self, market_id: str) -> dict:
        market = self.get_market(market_id)
        yes_no_tokens = market["tokens"]
        yes_token = next((token for token in yes_no_tokens if token["outcome"] == "Yes"), None)
        no_token = next((token for token in yes_no_tokens if token["outcome"] == "No"), None)
        market["yes_price"] = yes_token["price"]
        market["yes_token_id"] = yes_token["token_id"]
        market["no_price"] = no_token["price"]
        market["no_token_id"] = no_token["token_id"]
        return market
    
    def place_order(self, token_id: str, price: float, size: float, side: str = BUY, order_type: OrderType = OrderType.GTC) -> dict:
      """
      Places a limit order on the given token.
      """
      order_args = OrderArgs(
          price=price,
          size=size,
          side=side,
          token_id=token_id,
      )
      signed = self.client.create_order(order_args)
      resp = self.client.post_order(signed, order_type)
      return resp


if __name__ == "__main__":
    import json

    market_id = "0x9d98dacc9621503dce2382ab9eefbdbebea43a20af9b8e90c1112e649ee39cb6"
    
    try:
        client = PolymarketClient()
        market = client.get_market_encriched(market_id)
        
        output = json.dumps(market, indent=4)
        with open("polymarket_market.json", "w") as f:
            f.write(output)
        # print(output)
        client.place_order(
            token_id=market["yes_token_id"],
            price=0.5,
            size=1.0,
            side=BUY,
            order_type=OrderType.FOK
        )
    except Exception as e:
        print(f"Error fetching market: {e}")