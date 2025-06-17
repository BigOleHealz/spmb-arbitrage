import logging
import os
import time, base64
import json
from uuid import uuid4
from datetime import datetime, timezone

import requests
from dotenv import load_dotenv
from numpy import int64

from cryptography.hazmat.primitives import serialization, hashes
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.exceptions import InvalidSignature

logging.basicConfig(level=logging.INFO)

load_dotenv()

class KalshiClient:
    SANDBOX_URL = "https://demo-api.kalshi.co"
    BASE_API_URL = "https://api.elections.kalshi.com"
    BASE_ENDPOINT = "/trade-api/v2"
    
    KALSHI_API_PRIVATE_KEY_PATH = os.getenv("KALSHI_API_PRIVATE_KEY_PATH")
    KALSHI_API_KEY_ID = os.getenv("KALSHI_API_KEY_ID")
    
    def __init__(self, sandbox: bool=False):
        self.sandbox = sandbox
        self.api_url = self.SANDBOX_URL if self.sandbox else self.BASE_API_URL
        self.private_key = self.__load_private_key_from_file(self.KALSHI_API_PRIVATE_KEY_PATH)
    
    def __load_private_key_from_file(self, file_path: str) -> rsa.RSAPrivateKey:
        with open(file_path, "rb") as key_file:
            private_key = serialization.load_pem_private_key(
                key_file.read(),
                password=None,  # or provide a password if your key is encrypted
                backend=default_backend()
            )
        return private_key

    def generate_headers(self, method: str, endpoint: str) -> dict:
        def sign_pss_text(method: str, endpoint: str, timestampt_str: str) -> str:
            # Before signing, we need to hash our message.
            # The hash is what we actually sign.
            # Convert the text to bytes
            message = f"{timestampt_str}{method}{self.BASE_ENDPOINT}{endpoint}".encode('utf-8')
            try:
                signature = self.private_key.sign(
                    message,
                    padding.PSS(
                        mgf=padding.MGF1(hashes.SHA256()),
                        salt_length=padding.PSS.DIGEST_LENGTH
                    ),
                    hashes.SHA256()
                )
                return base64.b64encode(signature).decode('utf-8')
            except InvalidSignature as e:
                raise ValueError("RSA sign PSS failed") from e

        timestampt_str = str(int(time.time() * 1000))
        return {
            "KALSHI-ACCESS-KEY": self.KALSHI_API_KEY_ID,
            "KALSHI-ACCESS-SIGNATURE": sign_pss_text(method, endpoint, timestampt_str),
            "KALSHI-ACCESS-TIMESTAMP": timestampt_str
        }
    
    def __submit_get_request(self, endpoint: str) -> dict:
        method = "GET"
        headers = self.generate_headers(method, endpoint)
        response = requests.get(self.api_url + self.BASE_ENDPOINT + endpoint, headers=headers)
        response.raise_for_status()
        return response.json()
    
    def get_balance(self) -> dict:
        endpoint = "/portfolio/balance"
        return self.__submit_get_request(endpoint)
    
    def get_market(self, market_id: str) -> dict:
        endpoint = f"/markets/{market_id}"
        return self.__submit_get_request(endpoint)
    
    def get_markets(self) -> list[dict]:
        endpoint = "/markets"
        return self.__submit_get_request(endpoint)

    def get_fills(self) -> list[dict]:
        endpoint = "/portfolio/fills"
        return self.__submit_get_request(endpoint)
    
    def get_orders(self) -> list[dict]:
        endpoint = "/portfolio/orders"
        return self.__submit_get_request(endpoint)
    
    def get_positions(self) -> list[dict]:
        endpoint = "/portfolio/positions"
        return self.__submit_get_request(endpoint)

    # New method to place single order
    def place_order(
        self,
        market_id: str,
        action: str,  # "buy" or "sell"
        order_type: str,  # "market" or "limit"
        side: str,  # "yes" or "no"
        count: int,
        client_order_id: str=str(uuid4()),
        price: float = None  # in cents, e.g. 50 for $0.50
    ) -> dict:
        endpoint = "/portfolio/orders"
        method = "POST"
        if order_type == "limit" and price is None:
            raise ValueError("Must specify 'price' for a limit order")

        payload = {
            "action": action,
            "client_order_id": client_order_id,
            "count": count,
            "ticker": market_id,
            "type": order_type,
            "side": side,
        }
        if order_type == "limit":
            payload["price"] = price
        
        headers = self.generate_headers(method, endpoint)
        headers.update({
            "Accept": "application/json",
            "Content-Type": "application/json"
        })

        url = self.api_url + self.BASE_ENDPOINT + endpoint
        response = requests.post(url, headers=headers, json=payload)
        try:
            response.raise_for_status()
            return response.json()
        except requests.HTTPError:
            print(response.status_code, response.json())
            raise

class TestNetFunctions:
    def __init__(self, client: KalshiClient):
        self.client = client

    def find_current_markets(self) -> list[dict]:
        markets = self.client.get_markets()["markets"]
        now = datetime.now(timezone.utc)
        result = []
        for m in markets:
            open_dt = datetime.fromisoformat(m["open_time"].replace("Z", "+00:00"))
            close_dt = datetime.fromisoformat(m["close_time"].replace("Z", "+00:00"))
            if open_dt <= now <= close_dt:
                result.append(m)
        return result

if __name__ == "__main__":
    client = KalshiClient(sandbox=True)
    
    try:
        markets = TestNetFunctions(client).find_current_markets()
        with open("markets.json", "w") as f:
            json.dump(markets, f, indent=4)
        
        test_market = markets[0]
        print(f"{test_market=}")
        test_market_id = test_market["ticker"]
        print(f"{test_market_id=}")
        # print(f"{markets=}")
        # market = client.get_market(test_market_id)
        print(f"{client.get_balance()=}")
        # print(f"{client.get_market(test_market_id)=}")
        # print(f"{client.get_fills()=}")
        resp1 = client.place_order(
            market_id=test_market_id,
            action="buy",
            order_type="market",
            count=1,
            side="yes"
        )
        print("Market order response:", resp1)
        print(f"{client.get_orders()=}")
        print(f"{client.get_positions()=}")
        
        
    except Exception as e:
        print(f"Error fetching market: {e}")
