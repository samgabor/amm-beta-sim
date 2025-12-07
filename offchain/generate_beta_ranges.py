# offchain/generate_beta_ranges.py

import argparse
import json
from pathlib import Path

import numpy as np
from web3 import Web3

from config_dynamic import w3, ADDRESSES
from beta_policy import make_beta_ranges


def get_current_tick() -> int:
    """Read current tick from the on-chain pool, with a sanity check."""
    abi_path = Path(__file__).parent / "abi" / "IUniswapV3Pool.json"
    abi_json = json.loads(abi_path.read_text())
    abi = abi_json["abi"]

    pool_addr = Web3.to_checksum_address(ADDRESSES.pool)
    print(f"Using pool address: {pool_addr}")

    code = w3.eth.get_code(pool_addr)
    if code in (b"", b"\x00"):
        raise RuntimeError(
            f"No contract code at {pool_addr}. "
            "Did you restart Anvil or forget to rerun BootstrapAll?"
        )

    pool = w3.eth.contract(address=pool_addr, abi=abi)
    slot0 = pool.functions.slot0().call()
    return slot0[1]  # tick


def generate_beta_ranges_json(
    alpha: float,
    beta_param: float,
    total_liquidity: float,
    desired_ranges: int,
    separation_ticks: int,
    range_width_ticks: int,
    out_path: Path,
):
    current_tick = get_current_tick()
    print(f"Current tick: {current_tick}")
    print(
        f"Using alpha={alpha}, beta={beta_param}, ranges={desired_ranges}, "
        f"separation_ticks={separation_ticks}, range_width_ticks={range_width_ticks}"
    )

    tick_spacing = 60

    ranges = make_beta_ranges(
        alpha=alpha,
        beta_param=beta_param,
        current_tick=current_tick,
        total_liquidity=total_liquidity,
        tick_spacing=tick_spacing,
        desired_ranges=desired_ranges,
        range_width_ticks=range_width_ticks,
        separation_ticks=separation_ticks,
        min_group_liq=1e-3,
    )

    tick_lowers = []
    tick_uppers = []
    liquidities = []

    for (tl, tu, L) in ranges:
        tl = int(tl)
        tu = int(tu)

        # Snap to tick_spacing just in case
        tl = (tl // tick_spacing) * tick_spacing
        tu = (tu // tick_spacing) * tick_spacing

        tick_lowers.append(tl)
        tick_uppers.append(tu)

        liq_int = max(1, int(np.floor(L)))
        liquidities.append(liq_int)

    print(
        f"Generated {len(tick_lowers)} ranges with separation_ticks={separation_ticks}, "
        f"range_width_ticks={range_width_ticks}"
    )

    data = {
        "tickLowers": tick_lowers,
        "tickUppers": tick_uppers,
        "liquidities": liquidities,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(data, indent=2))
    print(f"Wrote beta ranges to: {out_path}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--alpha", type=float, default=2.0, help="Beta distribution alpha")
    parser.add_argument(
        "--beta",
        type=float,
        dest="beta_param",
        default=5.0,
        help="Beta distribution beta",
    )
    parser.add_argument(
        "--total-liquidity",
        type=float,
        default=50_000,
        help="Total liquidity budget for Beta policy",
    )
    parser.add_argument(
        "--ranges",
        type=int,
        default=10,
        help="Number of liquidity ranges around the current price",
    )
    parser.add_argument(
        "--inter-range-separation",
        type=int,
        default=120,
        dest="separation_ticks",
        help="Gap in ticks between adjacent ranges (multiple of tick spacing).",
    )
    parser.add_argument(
        "--range-width",
        type=int,
        default=60,
        dest="range_width_ticks",
        help="Width in ticks of each liquidity range (multiple of tick spacing).",
    )

    args = parser.parse_args()

    out_path = Path(__file__).parent.parent / "onchain" / "script" / "beta_ranges.json"
    generate_beta_ranges_json(
        alpha=args.beta_param,          # keeping your previous alpha/beta wiring
        beta_param=args.alpha,
        total_liquidity=args.total_liquidity,
        desired_ranges=args.ranges,
        separation_ticks=args.separation_ticks,
        range_width_ticks=args.range_width_ticks,
        out_path=out_path,
    )


if __name__ == "__main__":
    main()
