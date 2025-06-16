import os
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OrderArgs, OrderType
from py_clob_client.order_builder.constants import BUY, SELL
from dotenv import load_dotenv

from web3 import Web3

load_dotenv()

class PolymarketClient:
    AUTH_URL = "https://clob.polymarket.com"
    CHAIN_ID = 137  # Polygon mainnet
    USDC_ADDRESS = Web3.to_checksum_address("0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174")

    CLOB_SPENDERS = [
        "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E",
        "0xC5d563A36AE78145C45a50134d48A1215220f80a",
        "0xd91E80cF2E7be2e162c6513ceD06f1dD0dA35296",
    ]

    def __init__(self):
        private_key = os.getenv("POLYMARKET_PRIVATE_KEY")

        self.client = ClobClient(
            self.AUTH_URL,
            key=private_key,
            chain_id=self.CHAIN_ID
        )
        self.api_creds = self.client.create_or_derive_api_creds()
        self.client.set_api_creds(self.api_creds)

        # Web3 setup for balance and allowance checks
        self.w3 = Web3(Web3.HTTPProvider("https://polygon-rpc.com"))
        self.erc20_abi = [
            {
                "constant": True,
                "inputs": [{"name": "_owner", "type": "address"}],
                "name": "balanceOf",
                "outputs": [{"name": "balance", "type": "uint256"}],
                "type": "function",
            },
            {
                "constant": True,
                "inputs": [
                    {"name": "_owner", "type": "address"},
                    {"name": "_spender", "type": "address"},
                ],
                "name": "allowance",
                "outputs": [{"name": "remaining", "type": "uint256"}],
                "type": "function",
            },
            # optional: decimals
            {
                "constant": True,
                "inputs": [],
                "name": "decimals",
                "outputs": [{"name": "", "type": "uint8"}],
                "type": "function",
            },
        ]
        self.usdc_contract = self.w3.eth.contract(
            address=self.USDC_ADDRESS,
            abi=self.erc20_abi
        )

    def check_usdc_allowance(self, owner_address: str):
        """
        Returns a dict mapping each Polymarket spender to their USDC allowance (in USDC decimals).
        """
        owner = Web3.to_checksum_address(owner_address)
        allowances = {}
        for spender in self.CLOB_SPENDERS:
            spender_cs = Web3.to_checksum_address(spender)
            raw = self.usdc_contract.functions.allowance(owner, spender_cs).call()
            allowances[spender_cs] = raw / 1e6  # USDC has 6 decimals

        return allowances

    def check_usdc_balance(self, owner_address: str):
        owner = Web3.to_checksum_address(owner_address)
        balance_raw = self.usdc_contract.functions.balanceOf(owner).call()
        balance = balance_raw / 1e6  # USDC has 6 decimals
        print(f"USDC.e balance for {owner}: {balance:.6f} USDC")
        return balance

    def get_market(self, market_id: str):
        return self.client.get_market(condition_id=market_id)
    
    def get_market_encriched(self, market_id: str) -> dict:
        try:
            market = self.get_market(market_id)
            yes_no_tokens = market["tokens"]
            yes_token = next((token for token in yes_no_tokens if token["outcome"] == "Yes"), None)
            no_token = next((token for token in yes_no_tokens if token["outcome"] == "No"), None)
            market["yes_price"] = yes_token["price"]
            market["yes_token_id"] = yes_token["token_id"]
            market["no_price"] = no_token["price"]
            market["no_token_id"] = no_token["token_id"]
            return market
        except Exception as e:
            raise Exception(f"Error in get_market_encriched: {e}")
    
    def place_order(self, token_id: str, price: float, size: float, side: str = BUY, order_type: OrderType = OrderType.GTC) -> dict:
        try:
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
        except Exception as e:
            raise e


if __name__ == "__main__":
    import json

    market_id = "0x9d98dacc9621503dce2382ab9eefbdbebea43a20af9b8e90c1112e649ee39cb6"
    
    try:
        client = PolymarketClient()
        
        market = client.get_market_encriched(market_id)
        
        output = json.dumps(market, indent=4)
        
        client.check_usdc_balance(client.client.get_address())
        
        allowances = client.check_usdc_allowance(client.client.get_address())
        
        print(f"{client.client.get_address()=}")
        print("USDC allowances (in USDC):")
        for spender, amt in allowances.items():
            print(f"{spender}: {amt}")
            
            
        # with open("polymarket_market.json", "w") as f:
        #     f.write(output)
        # # print(output)
        # client.place_order(
        #     token_id=market["yes_token_id"],
        #     price=0.11,
        #     size=10.0,
        #     side=BUY,
        #     order_type=OrderType.FOK
        # )
    except Exception as e:
        raise e