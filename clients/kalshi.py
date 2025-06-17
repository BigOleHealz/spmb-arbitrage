import os
import requests
from dotenv import load_dotenv
import time, base64
from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature

load_dotenv()

class KalshiClient:
    SANDBOX_URL = "https://demo-api.kalshi.co/trade-api/v2"
    BASE_API_URL = "https://api.elections.kalshi.com/trade-api/v2"
    
    KALSHI_API_PRIVATE_KEY_PATH = os.getenv("KALSHI_API_PRIVATE_KEY_PATH")
    KALSHI_API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")

    def __init__(self, sandbox: bool = True):
        self.api_url = self.SANDBOX_URL if sandbox else self.BASE_API_URL
        self.private_key = serialization.load_pem_private_key(
            open(self.KALSHI_API_PRIVATE_KEY_PATH, "rb").read(), password=None
        )
        self.session = requests.Session()

    def sign_pss_text(self, method: str, endpoint: str) -> str:
        # Before signing, we need to hash our message.
        # The hash is what we actually sign.
        # Convert the endpoint to bytes
        message = endpoint.encode('utf-8')

        try:
            signature = self.private_key.sign(
                message,
                padding.PSS(
                    mgf=padding.MGF1(hashes.SHA256()),
                    salt_length=padding.PSS.DIGEST_LENGTH
                ),
                hashes.SHA256()
            )
            ts = str(int(time.time() * 1000))
            return {
                "KALSHI-ACCESS-KEY": self.KALSHI_API_KEY_ID,
                "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode('utf-8'),
                "KALSHI-ACCESS-TIMESTAMP": ts,
            }
        except InvalidSignature as e:
            raise ValueError("RSA sign PSS failed") from e
    
    def _sign(self, method: str, path: str) -> dict:
        ts = str(int(time.time() * 1000))
        msg = f"{ts}{method.upper()}{path}".encode()
        sig = self.private_key.sign(
            msg,
            padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
            hashes.SHA256()
        )
        return {
            "KALSHI-ACCESS-KEY": self.KALSHI_API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }

    def get_market(self, market_id: str):
        url = f"{self.api_url}/markets/{market_id}"
        try:
            response = self.session.get(url, timeout=10)
            response.raise_for_status()
            market = response.json()
            market["yes_price"] = market["market"]["yes_ask"]
            market["no_price"] = market["market"]["no_ask"]
            market["end_date_iso"] = market["market"]["latest_expiration_time"]
            return market
        except requests.exceptions.RequestException as e:
            raise RuntimeError(f"Failed to fetch market '{market_id}': {e}")

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
        url = f"{self.api_url}/portfolio/orders"

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
    
    def get_balance(self):
        method = "GET"
        endpoint = "/trade-api/v2/portfolio/balance"
        # headers1 = self._sign("GET", endpoint)
        # res = self.session.get(self.api_url + endpoint, headers=headers1)
        
        # sig = self.sign_pss_text()
        timestampt_str = str(int(time.time() * 1000))
        headers = self.sign_pss_text(f"{timestampt_str}{method}{endpoint}")
        # headers2 = {
        #   'KALSHI-ACCESS-KEY': self.KALSHI_API_KEY_ID,
        #   'KALSHI-ACCESS-SIGNATURE': sig,
        #   'KALSHI-ACCESS-TIMESTAMP': timestampt_str
        # }
        res = self.session.get(self.api_url + endpoint, headers=headers)
        import pdb; pdb.set_trace()
        
        res.raise_for_status()
        return res.json()

if __name__ == "__main__":
    import json
    
    test_market_id = "KXLEAVEADMIN-26-TGAB"

    client = KalshiClient(sandbox=True)
    
    try:
        # market = client.get_market(test_market_id)
        # output = json.dumps(market, indent=4)
        # with open("kalshi_market.json", "w") as f:
        #     f.write(output)
        # print(f"{client.get_balance()=}")
        
        print(f"{client.get_balance()=}")
        # print(output)
        # client.place_order(
        #     market_ticker=test_market_id,
        #     side="yes",
        #     quantity=1,
        #     price=0.5,
        #     order_type="market"
        # )
    except Exception as e:
        print(f"Error fetching market: {e}")

# import os
# import logging
# import uuid
# import kalshi_python
# from kalshi_python.models import (
#     LoginRequest, CreateOrderRequest
# )
# from dotenv import load_dotenv

# logging.basicConfig(level=logging.INFO)
# load_dotenv()

# class KalshiClient:
#     SANDBOX_URL = "https://demo-api.kalshi.co/trade-api/v2"
#     PROD_URL    = "https://api.elections.kalshi.com/trade-api/v2"

#     def __init__(self, sandbox: bool = True):
#         self.host = self.SANDBOX_URL if sandbox else self.PROD_URL
#         kalshi_api_private_key_path = os.getenv("KALSHI_API_PRIVATE_KEY_PATH")
#         kalshi_api_key_id = os.getenv("KALSHI_API_KEY_ID")
#         if not (kalshi_api_private_key_path and kalshi_api_key_id):
#             raise ValueError("Missing KALSHI_API_PRIVATE_KEY_PATH or KALSHI_API_KEY_ID in .env")
#         config = kalshi_python.Configuration()
#         config.host = self.host
#         config.private_key_path = kalshi_api_private_key_path
#         config.key_id = kalshi_api_key_id
#         config.debug = True
#         self.api = kalshi_python.ApiInstance(configuration=config)

#         # email = os.getenv("KALSHI_EMAIL")
#         # password = os.getenv("KALSHI_PASSWORD")
#         # if not (email and password):
#         #     raise ValueError("Missing KALSHI_EMAIL or KALSHI_PASSWORD in .env")
#         # resp = self.api.login(LoginRequest(email=email, password=password))
#         # self.api.set_api_token(resp.token)
#         # logging.info("🌟 Logged in; token expires in 30 minutes")

#     def get_markets(self, event_ticker: str = None) -> list:
#         return self.api.get_markets(event_ticker=event_ticker)

#     def get_market(self, market_ticker: str) -> dict:
#         return self.api.get_market(market_ticker)

#     def get_orderbook(self, market_ticker: str):
#         return self.api.get_market_orderbook(market_ticker)

#     def get_orders(self):
#         return self.api.get_orders()

#     def get_trades(self):
#         return self.api.get_fills()  # fetches trading history

#     def get_balance(self):
#         return self.api.get_balance()

#     # def place_limit_order(self, market_ticker: str, side: str, price_cents: int, count: int):
#     #     """
#     #     side: 'buy' or 'sell'
#     #     price_cents: integer price * 100 (e.g., 50 = $0.50)
#     #     count: how many contracts
#     #     """
#     #     order_id = str(uuid.uuid4())
#     #     resp = self.api.create_order(
#     #         CreateOrderRequest(
#     #             ticker=market_ticker,
#     #             action='buy' if side == 'buy' else 'sell',
#     #             type='limit',
#     #             yes_price=price_cents,
#     #             count=count,
#     #             client_order_id=order_id,
#     #             side=side
#     #         )
#     #     )
#     #     logging.info(f"✅ Placed {side.upper()} order {order_id} → {resp.status}")
#     #     return resp

#     # def cancel_order(self, order_id: str):
#     #     return self.api.cancel_order(order_id)

#     # def get_positions(self):
#     #     return self.api.get_positions()


# if __name__ == "__main__":
#     test_market_ticker = "KXLEAVEADMIN-26-TGAB"
#     client = KalshiClient(sandbox=True)
    
#     market = client.get_market(test_market_ticker)
#     print(f"{market=}")

#     print("Balance:", client.get_balance())
#     # print("Markets:", client.get_markets(test_market_ticker))
#     # book = client.get_orderbook(test_market_ticker)
#     # print("Orderbook:", book)

#     # order = client.place_limit_order(
#     #     market_ticker=test_market_ticker,
#     #     side="buy", price_cents=50, count=10
#     # )
#     # print("Order result:", order)

#     # positions = client.get_positions()
#     # print("Positions:", positions)

#     # cancel_resp = client.cancel_order(order.client_order_id)
#     # print("Cancel result:", cancel_resp)