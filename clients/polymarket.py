import os
import logging
from py_clob_client.client import ClobClient
from py_clob_client.clob_types import OpenOrderParams, OrderArgs, OrderType, TradeParams
from py_clob_client.order_builder.constants import BUY, SELL
from dotenv import load_dotenv

from web3 import Web3

logging.basicConfig(level=logging.INFO)
USDC_DECIMALS = 1_000_000

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
        self._private_key = os.getenv("POLYMARKET_PRIVATE_KEY")

        self.client = ClobClient(
            self.AUTH_URL,
            key=self._private_key,
            chain_id=self.CHAIN_ID,
            funder=os.getenv("POLYMARKET_PUBLIC_KEY")
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
            {
                "constant": False,
                "inputs": [
                    {"name": "_spender", "type": "address"},
                    {"name": "_value", "type": "uint256"},
                ],
                "name": "approve",
                "outputs": [{"name": "", "type": "bool"}],
                "type": "function",
            }
        ]
        self.usdc_contract = self.w3.eth.contract(
            address=self.USDC_ADDRESS,
            abi=self.erc20_abi
        )
        self.owner_address = self.client.get_address()

    def check_usdc_allowance(self) -> dict:
        owner = Web3.to_checksum_address(self.owner_address)
        allowances = {}
        for spender in self.CLOB_SPENDERS:
            spender_cs = Web3.to_checksum_address(spender)
            raw = self.usdc_contract.functions.allowance(owner, spender_cs).call()
            allowances[spender_cs] = raw / USDC_DECIMALS  # USDC has 6 decimals

        return allowances

    def check_usdc_balance(self) -> float:
        owner = Web3.to_checksum_address(self.owner_address)
        balance_raw = self.usdc_contract.functions.balanceOf(owner).call()
        balance = balance_raw / USDC_DECIMALS  # USDC has 6 decimals
        logging.info(f"USDC.e balance for {owner}: {balance:.6f} USDC")
        return balance
    
    def approve_usdc_spender(self, spender: str, amount: float) -> str:
        amount_wei = int(amount * USDC_DECIMALS)
        nonce = self.w3.eth.get_transaction_count(self.owner_address, 'pending')
        tx = self.usdc_contract.functions.approve(spender, amount_wei).build_transaction({
            "from": self.owner_address,
            "nonce": nonce,
            "gas": 110_000,
            "gasPrice": self.w3.eth.gas_price,
        })
        signed = self.w3.eth.account.sign_transaction(tx, self._private_key)
        receipt = self.w3.eth.send_raw_transaction(signed.raw_transaction)
        logging.info(f"Approved spender {spender}: tx {receipt.hex()}")
        return receipt.hex()

    def get_market(self, market_id: str) -> dict:
        market = self.client.get_market(condition_id=market_id)
        yes_no_tokens = market["tokens"]
        yes_token = next((token for token in yes_no_tokens if token["outcome"] == "Yes"), None)
        no_token = next((token for token in yes_no_tokens if token["outcome"] == "No"), None)
        market["yes_price"] = yes_token["price"]
        market["yes_token_id"] = yes_token["token_id"]
        market["no_price"] = no_token["price"]
        market["no_token_id"] = no_token["token_id"]
        return market
    
    def get_orders(self, market_id: str=None, asset_id: str=None) -> list:
        params = OpenOrderParams(
            market=market_id,
            asset_id=asset_id,
        )
        open_orders = self.client.get_orders(params)
        return open_orders
    
    def get_trades(self, market_id: str=None, asset_id: str=None) -> list:
        params = TradeParams(
            market=market_id,
            maker_address=self.client.get_address(),
            asset_id=asset_id,
        )
        trades = self.client.get_trades(params)
        return trades
    
    def cancel_order(self, order_id: str) -> dict:
        resp = self.client.cancel(order_id=order_id)
        return resp
    
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
    
    def sell_position(self, market_id: str, outcome: str = "Yes") -> dict:
        """
        Consolidates and sells your full open position on `outcome` in `market_id` at the midpoint price.

        Returns the order response dict.
        """
        # 1️⃣ Fetch positions
        positions = self.get_trades(market_id=market_id)
        # 2️⃣ Find the outcome you hold
        pos = next((p for p in positions if p["outcome"] == outcome and float(p["size"]) > 0), None)
        if not pos:
            raise ValueError(f"No open position found for {outcome} in market {market_id}")

        token_id = pos["asset_id"]  # token ID for the conditional outcome
        size = float(pos["size"])
        logging.info(f"Preparing to sell {size} shares of {outcome} (token {token_id})")
        
        import pdb; pdb.set_trace()
        
        # 3️⃣ Get current midpoint price
        mid = self.client.get_midpoint(token_id)["mid"]
        price = float(mid)
        logging.info(f"Current midpoint price: {price}")

        # 4️⃣ Place sell limit order
        resp = self.place_order(
            token_id=token_id,
            price=price,
            size=size,
            side=SELL,
            order_type=OrderType.GTC
        )
        logging.info(f"Sell order submitted: {resp}")
        return resp


if __name__ == "__main__":
    import json

    market_id = "0x9d98dacc9621503dce2382ab9eefbdbebea43a20af9b8e90c1112e649ee39cb6"
    
    client = PolymarketClient()
    
    market = client.get_market(market_id)
    
    logging.info(f"{client.client.get_address()=}")
    logging.info(f"USDC balance: {client.check_usdc_balance()}")
    logging.info(f"USDC allowance: {client.check_usdc_allowance()}")
    
    for spender in client.CLOB_SPENDERS:
        client.approve_usdc_spender(spender, 1000)

    open_orders = client.get_orders(market_id=market_id)
    logging.info(f"open_orders: {open_orders}=")
    
    trades = client.get_trades(market_id=market_id)
    logging.info(f"trades: {trades}=")
    
    for trade in trades:
        client.sell_position(market_id=trade['market'], outcome="Yes")
    
    # order = client.place_order(
    #     token_id=market["yes_token_id"],
    #     price=0.15,
    #     size=7,
    #     side=BUY,
    #     order_type=OrderType.GTC
    # )
    # logging.info(f"{order}=")
    # logging.info(client.cancel_order(open_orders[0]['id']))