# offchain/lp_fee_accounting.py

from dataclasses import dataclass

FEE_TIER = 3000           # Uniswap v3 fee = 0.3%
FEE_DENOMINATOR = 1_000_000  # v3 uses 1e6 for fee calculation


@dataclass
class LPFeeState:
    """
    Tracks cumulative fees earned by the LP in token units.

    fee_weth: total WETH fees earned so far
    fee_usdc: total USDC fees earned so far (6 decimals)
    """
    fee_weth: float = 0.0
    fee_usdc: float = 0.0


def apply_swap_fee(direction: str, amount_in_wei: int, fee_state: LPFeeState) -> None:
    """
    Update fee_state given a swap:
      - direction == "sell_weth"  => WETH -> USDC, fee paid in WETH
      - direction == "buy_weth"   => USDC -> WETH, fee paid in USDC

    amount_in_wei is the full input amount passed to SwapHelper.
    """
    fee_raw = amount_in_wei * FEE_TIER / FEE_DENOMINATOR  # float is fine for sim

    if direction == "sell_weth":
        # fee in WETH (18 decimals)
        fee_state.fee_weth += fee_raw
    elif direction == "buy_weth":
        # fee in USDC (6 decimals)
        fee_state.fee_usdc += fee_raw
    else:
        # unknown direction, ignore
        pass


def lp_fee_value_usdc(fee_state: LPFeeState, price_usdc_per_weth: float) -> float:
    """
    Convert accumulated fee tokens to USDC value.

    price_usdc_per_weth: current pool price (USDC per 1 WETH)
    """
    # fee_weth is in wei (1e18), but price_usdc_per_weth is in "human" units.
    # If you already convert token balances to human units elsewhere, you should
    # keep the same convention. For simplicity we treat fee_raw/1e18 * price.
    weth_human = fee_state.fee_weth / 1e18
    usdc_human = fee_state.fee_usdc / 1e6

    return usdc_human + weth_human * price_usdc_per_weth
