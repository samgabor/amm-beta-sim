import json
import logging
from pathlib import Path
from decimal import Decimal

from web3 import Web3
from eth_account import Account

from config_dynamic import w3, ADDRESSES
from pool_math import sqrt_price_x96_to_price

# anvil default[0] private key
DEPLOYER_PK = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEPLOYER = Account.from_key(DEPLOYER_PK).address


def load_abi(name: str):
    abi_path = Path(__file__).parent / "abi" / f"{name}.json"
    abi_json = json.loads(abi_path.read_text())
    return abi_json["abi"]


def load_pool():
    abi = load_abi("IUniswapV3Pool")
    return w3.eth.contract(
        address=Web3.to_checksum_address(ADDRESSES.pool),
        abi=abi,
    )


def load_swap_helper():
    abi = load_abi("SwapHelper")
    return w3.eth.contract(
        address=Web3.to_checksum_address(ADDRESSES.swap_helper),
        abi=abi,
    )


def run_step(amount_in_wei: int, zero_for_one: bool, logger: logging.Logger):
    """
    One simulation step:
      - if zero_for_one=True:  swap TOKEN0 (WETH) -> TOKEN1 (USDC)
      - if zero_for_one=False: swap TOKEN1 (USDC) -> TOKEN0 (WETH)
      then read new slot0 and convert to price.
    """
    swap_helper = load_swap_helper()
    pool = load_pool()

    direction = "0->1 (WETH->USDC)" if zero_for_one else "1->0 (USDC->WETH)"

    logger.info("=== Simulation step ===")
    #print("Deployer:", DEPLOYER)
    #print("SwapHelper:", ADDRESSES.swap_helper)
    logger.info("Amount in (wei): %s", amount_in_wei)
    logger.info("Direction: %s", direction)

    if zero_for_one:
        fn = swap_helper.functions.swapExact0For1(amount_in_wei)
    else:
        fn = swap_helper.functions.swapExact1For0(amount_in_wei)

    tx = fn.build_transaction(
        {
            "from": DEPLOYER,
            "nonce": w3.eth.get_transaction_count(DEPLOYER),
            "gas": 1_000_000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
            "chainId": 31337,
        }
    )

    signed = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    #print("Swap tx hash:", tx_hash.hex())
    logger.info("Status: %s", receipt.status) # type: ignore

    slot0 = pool.functions.slot0().call()
    sqrt_price_x96 = slot0[0]
    tick = slot0[1]
    price = sqrt_price_x96_to_price(sqrt_price_x96)

    #print("New sqrtPriceX96:", sqrt_price_x96)
    #print("New tick:", tick)
    logger.info("New price (USDC per WETH): %s", price)

    return {
        "tx_hash": tx_hash.hex(),
        "status": receipt.status, # type: ignore
        "sqrtPriceX96": sqrt_price_x96,
        "tick": tick,
        "price": Decimal(price),
        "direction": direction,
        "amount_in_wei": amount_in_wei,
    }


def main():
    # WETH amount (18 decimals)
    amount_weth = Web3.to_wei(0.02, "ether")  # 0.02 WETH

    # USDC amount (6 decimals) – e.g. 20 USDC
    amount_usdc = 20 * 10**6  # 20 USDC

    # print("\n--- Sell WETH for USDC ---")
    # run_step(amount_weth, zero_for_one=True)

    # print("\n--- Buy WETH with USDC ---")
    # run_step(amount_usdc, zero_for_one=False)


if __name__ == "__main__":
    main()
