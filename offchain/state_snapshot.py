# offchain/state_snapshot.py

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Dict, Any, List, Tuple
import json
from pathlib import Path

from web3 import Web3
from eth_account import Account

from config_dynamic import w3, ADDRESSES, load_abi  # make sure load_abi points to offchain/abi/*.json


DEPLOYER_PK = "0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"  # same key you use elsewhere
DEPLOYER = Account.from_key(DEPLOYER_PK).address

def get_lphelper_contract():
    abi = load_abi("LPHelper")
    return w3.eth.contract(
        address=Web3.to_checksum_address(ADDRESSES.lp_helper),
        abi=abi,
    )

import json
from pathlib import Path

# def _load_beta_ranges():
#     path = Path("script") / "beta_ranges.json"
#     data = json.loads(path.read_text())
#     lowers = data["tickLowers"]
#     uppers = data["tickUppers"]
#     return lowers, uppers

def get_lp_position_totals():
    """
    Return LPHelper's total position amounts across all configured ranges.

    Returns:
      principal0_raw: WETH principal (token0), 18-dec raw
      principal1_raw: USDC principal (token1), 6-dec raw
      fees0_raw:      uncollected WETH fees (token0), raw
      fees1_raw:      uncollected USDC fees (token1), raw
    """
    lp_helper = get_lphelper_contract()
    lowers, uppers = _load_beta_ranges()

    # Call the Solidity helper we just added
    principal0, principal1, fees0, fees1 = lp_helper.functions.getTotalPositionValue(
        lowers,
        uppers,
    ).call()

    return {
        "principal0": int(principal0),
        "principal1": int(principal1),
        "fees0": int(fees0),
        "fees1": int(fees1),
    }




def poke_all_positions():
    lowers, uppers = _load_beta_ranges()
    lp_helper = get_lphelper_contract()

    tx = lp_helper.functions.pokeRanges(lowers, uppers).build_transaction(
        {
            "from": DEPLOYER,
            "nonce": w3.eth.get_transaction_count(DEPLOYER),
            "gas": 2_000_000,
            "maxFeePerGas": w3.to_wei("2", "gwei"),
            "maxPriorityFeePerGas": w3.to_wei("1", "gwei"),
            "chainId": 31337,
        }
    )
    signed = w3.eth.account.sign_transaction(tx, private_key=DEPLOYER_PK)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    w3.eth.wait_for_transaction_receipt(tx_hash)
    return tx_hash.hex()



getcontext().prec = 60

# Uniswap Q192 = 2^192, used for price from sqrtPriceX96
Q192 = Decimal(2) ** 192


def price_from_sqrtPriceX96(
    sqrt_price_x96: int,
    decimals_token0: int = 18,  # WETH
    decimals_token1: int = 6,   # USDC
) -> Decimal:
    """
    Convert Uniswap v3 sqrtPriceX96 into a human-readable price of TOKEN1 per TOKEN0.

    For WETH/USDC with 18/6 decimals, this returns USDC per WETH.
    """
    sp = Decimal(sqrt_price_x96)
    raw_ratio = (sp * sp) / Q192  # token1_raw / token0_raw
    scale = Decimal(10) ** (decimals_token0 - decimals_token1)
    return raw_ratio * scale  # USDC per WETH


def get_pool_contract():
    abi = load_abi("IUniswapV3Pool")
    pool_addr = Web3.to_checksum_address(ADDRESSES.pool)
    return w3.eth.contract(address=pool_addr, abi=abi)


def get_erc20_contract(addr: str):
    abi = load_abi("MockERC20")  # or a generic ERC20 ABI
    return w3.eth.contract(address=Web3.to_checksum_address(addr), abi=abi)


def balances_for(addr: str) -> Dict[str, int]:
    """
    Return raw integer balances (no decimal scaling) for WETH and USDC.
    """
    acct = Web3.to_checksum_address(addr)
    weth = get_erc20_contract(ADDRESSES.weth)
    usdc = get_erc20_contract(ADDRESSES.usdc)

    return {
        "weth": weth.functions.balanceOf(acct).call(),
        "usdc": usdc.functions.balanceOf(acct).call(),
    }


# ---------- NEW: helpers for LP position fees ----------

def _load_beta_ranges() -> Tuple[List[int], List[int]]:
    """
    Load tickLowers/tickUppers from script/beta_ranges.json.

    Adjust the path if your file lives somewhere else.
    """
    path = Path("../onchain/script") / "beta_ranges.json"
    data = json.loads(path.read_text())
    lowers = data["tickLowers"]
    uppers = data["tickUppers"]
    return lowers, uppers


import eth_utils

def _encode_int24(x: int) -> bytes:
    """Pack a signed int24 into 3 bytes."""
    if x < -2**23 or x >= 2**23:
        raise ValueError(f"int24 out of range: {x}")
    if x < 0:
        x = (1 << 24) + x  # two's complement
    return x.to_bytes(3, "big")

# def get_lp_fees() -> Dict[str, int]:
#     pool = get_pool_contract()
#     lp_addr = Web3.to_checksum_address(ADDRESSES.lp_helper)

#     lowers, uppers = _load_beta_ranges()

#     fees0 = 0
#     fees1 = 0

#     for tick_lower, tick_upper in zip(lowers, uppers):
#         owner_bytes = Web3.to_bytes(hexstr=lp_addr)
#         key_bytes = owner_bytes + _encode_int24(int(tick_lower)) + _encode_int24(int(tick_upper))
#         key = eth_utils.keccak(key_bytes) # type: ignore

#         pos = pool.functions.positions(key).call()
#         tokens_owed0 = int(pos[3])
#         tokens_owed1 = int(pos[4])

#         fees0 += tokens_owed0
#         fees1 += tokens_owed1

#     return {"fees0": fees0, "fees1": fees1}

def get_lp_fees() -> Dict[str, int]:
    """
    Return *aggregated* uncollected fees for LPHelper across all ranges.

    Uses LPHelper.getTotalPositionValue, which already accounts for
    Uniswap v3 feeGrowth math, instead of relying on pool.positions().tokensOwed*,
    which only updates on collect/poke.
    """
    totals = get_lp_position_totals()
    # These are raw token amounts (before decimal scaling)
    return {
        "fees0": totals["fees0"],  # WETH fees (token0), 18-dec raw
        "fees1": totals["fees1"],  # USDC fees (token1), 6-dec raw
    }



# ---------- main state snapshot ----------

def get_state() -> Dict[str, Any]:
    """
    Snapshot of the current on-chain state relevant for the simulation.

    Returns a dict with:
      - tick
      - sqrtPriceX96
      - liquidity
      - price (Decimal USDC/WETH)
      - balances: { lp_helper, swap_helper, pool }
    """
    pool = get_pool_contract()
    slot0 = pool.functions.slot0().call()
    sqrt_price_x96 = int(slot0[0])
    tick = int(slot0[1])
    liquidity = pool.functions.liquidity().call()

    price_usdc_per_weth = price_from_sqrtPriceX96(sqrt_price_x96)

    state: Dict[str, Any] = {
        "tick": tick,
        "sqrtPriceX96": sqrt_price_x96,
        "liquidity": int(liquidity),
        "price": price_usdc_per_weth,  # Decimal USDC/WETH
        "balances": {
            # "deployer": balances_for(ADDRESSES.deployer),
            "lp_helper": balances_for(ADDRESSES.lp_helper),
            "swap_helper": balances_for(ADDRESSES.swap_helper),
            "pool": balances_for(ADDRESSES.pool),
        },
    }

    return state
