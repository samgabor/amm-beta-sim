from pydantic import BaseModel
from web3 import Web3

RPC_URL = "http://127.0.0.1:8545"

class ContractAddresses(BaseModel):
    weth: str
    usdc: str
    factory: str
    pool: str
    lp_helper: str
    swap_helper: str

ADDRESSES = ContractAddresses(
    weth="0x5FbDB2315678afecb367f032d93F642f64180aa3",
    usdc="0xe7f1725E7734CE288F8367e1Bb143E90bb3F0512",
    factory="0x9fE46736679d2D9a65F0992F2272dE9f3c7fa6e0",
    pool="0xC9d3DeaE8B6727bb9621b9cE83e77d229c332a38",
    lp_helper="0xe039608E695D21aB11675EBBA00261A0e750526c",
    swap_helper="0x4A679253410272dd5232B3Ff7cF5dbB88f295319",
)

w3 = Web3(Web3.HTTPProvider(RPC_URL))

if not w3.is_connected():
    raise RuntimeError("Web3 is not connected – is anvil running?")


import json
import os

# config.py (add this near the bottom)

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

