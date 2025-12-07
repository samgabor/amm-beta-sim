import json
from pathlib import Path

from web3 import Web3
from config_dynamic import w3, ADDRESSES


def load_pool_contract() -> Web3.contract:
    abi_path = Path(__file__).parent / "abi" / "IUniswapV3Pool.json"
    abi_json = json.loads(abi_path.read_text())
    abi = abi_json["abi"]

    pool = w3.eth.contract(
        address=Web3.to_checksum_address(ADDRESSES.pool),
        abi=abi,
    )
    return pool


def main():
    pool = load_pool_contract()

    slot0 = pool.functions.slot0().call()
    liquidity = pool.functions.liquidity().call()
    fee = pool.functions.fee().call()
    tick_spacing = pool.functions.tickSpacing().call()

    print("Pool:", ADDRESSES.pool)
    print("slot0:", slot0)
    print("liquidity:", liquidity)
    print("fee:", fee)
    print("tickSpacing:", tick_spacing)


if __name__ == "__main__":
    main()
