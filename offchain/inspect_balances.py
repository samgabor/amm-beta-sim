import json
from pathlib import Path

from web3 import Web3
from config_dynamic import w3, ADDRESSES

DEPLOYER = "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"  # anvil account[0]

def load_erc20(address: str):
    abi_path = Path(__file__).parent / "abi" / "MockERC20.json"
    abi_json = json.loads(abi_path.read_text())
    abi = abi_json["abi"]

    return w3.eth.contract(
        address=Web3.to_checksum_address(address),
        abi=abi,
    )

def main():
    weth = load_erc20(ADDRESSES.weth)
    usdc = load_erc20(ADDRESSES.usdc)

    actors = {
        "deployer": DEPLOYER,
        "lp_helper": ADDRESSES.lp_helper,
        "swap_helper": ADDRESSES.swap_helper,
        "pool": ADDRESSES.pool,
    }

    print("=== WETH balances ===")
    for name, addr in actors.items():
        bal = weth.functions.balanceOf(Web3.to_checksum_address(addr)).call()
        print(f"{name:12s}: {bal}")

    print("\n=== USDC balances ===")
    for name, addr in actors.items():
        bal = usdc.functions.balanceOf(Web3.to_checksum_address(addr)).call()
        print(f"{name:12s}: {bal}")

if __name__ == "__main__":
    main()
