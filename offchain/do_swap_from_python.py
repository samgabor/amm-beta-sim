import json
from pathlib import Path
from web3 import Web3
from eth_account import Account

from config_dynamic import w3, ADDRESSES

# anvil default[0] private key (same as scripts)
DEPLOYER_PK = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
DEPLOYER = Account.from_key(DEPLOYER_PK).address

def load_swap_helper():
    abi_path = Path(__file__).parent / "abi" / "SwapHelper.json"
    abi_json = json.loads(abi_path.read_text())
    abi = abi_json["abi"]

    return w3.eth.contract(
        address=Web3.to_checksum_address(ADDRESSES.swap_helper),
        abi=abi,
    )

def main():
    swap_helper = load_swap_helper()

    amount_in = Web3.to_wei(0.001, "ether")  # swap 0.1 WETH -> USDC

    print("Deployer:", DEPLOYER)
    print("SwapHelper:", ADDRESSES.swap_helper)
    print("Amount in (wei):", amount_in)

    tx = swap_helper.functions.swapExact0For1(amount_in).build_transaction(
        {
            "from": DEPLOYER,
            "nonce": w3.eth.get_transaction_count(DEPLOYER),
            "gas": 1_000_000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
            "chainId": 31337,  # anvil default
        }
    )

    signed = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash)

    print("Swap tx hash:", tx_hash.hex())
    print("Status:", receipt.status)

if __name__ == "__main__":
    main()
