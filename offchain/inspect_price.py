import json
from pathlib import Path
from web3 import Web3

from config_dynamic import w3, ADDRESSES
from pool_math import sqrt_price_x96_to_price


def load_pool():
    abi_path = Path(__file__).parent / "abi" / "IUniswapV3Pool.json"
    abi_json = json.loads(abi_path.read_text())
    abi = abi_json["abi"]

    return w3.eth.contract(
        address=Web3.to_checksum_address(ADDRESSES.pool),
        abi=abi,
    )


def main():
    pool = load_pool()
    slot0 = pool.functions.slot0().call()
    sqrt_price_x96 = slot0[0]
    tick = slot0[1]

    price = sqrt_price_x96_to_price(sqrt_price_x96)

    print("sqrtPriceX96:", sqrt_price_x96)
    print("tick:", tick)
    print("implied price (USDC per WETH):", price)


if __name__ == "__main__":
    main()
