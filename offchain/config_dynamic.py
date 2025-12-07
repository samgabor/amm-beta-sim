from dataclasses import dataclass
from pathlib import Path
import json
from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"


@dataclass
class ContractAddresses:
    weth: str
    usdc: str
    factory: str
    router: str
    pool: str
    lp_helper: str
    swap_helper: str


def load_addresses() -> ContractAddresses:
    """
    Load contract addresses written by BootstrapAll.s.sol
    from onchain/script/addresses.json
    """
    here = Path(__file__).resolve()
    json_path = here.parent.parent / "onchain" / "script" / "addresses.json"
    data = json.loads(json_path.read_text())
    return ContractAddresses(**data)


ADDRESSES = load_addresses()
w3 = Web3(Web3.HTTPProvider(RPC_URL))



import json
import os

# Directory that holds JSON ABI files, e.g. IUniswapV3Pool.json, MockERC20.json
ABI_DIR = os.path.join(os.path.dirname(__file__), "abi")

def load_abi(contract_name: str):
    """
    Load ABI from offchain/abi/<contract_name>.json

    Example:
        load_abi("IUniswapV3Pool") -> offchain/abi/IUniswapV3Pool.json
        load_abi("MockERC20")      -> offchain/abi/MockERC20.json
    """
    path = os.path.join(ABI_DIR, f"{contract_name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"ABI file not found: {path}")
    with open(path, "r") as f:
        data = json.load(f)
    # If the JSON is a full artifact, it usually has {"abi": [...]}
    return data.get("abi", data)

