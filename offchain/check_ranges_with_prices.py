import json
import math
from pathlib import Path

# ---- Config ----

JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "onchain"
    / "script"
    / "beta_ranges.json"
)

BASE = 1.0001  # Uniswap v3 tick base

# >>> IMPORTANT: update to pool-initialized values <<<
START_PRICE = 3200.0                 # price (USDC/WETH) when pool initialized
CURRENT_TICK_AT_START = -195611      # tick at that price from inspect_price.py


def tick_to_price_usdc_per_weth(tick: float) -> float:
    return START_PRICE * (BASE ** (tick - CURRENT_TICK_AT_START))


def fmt_number(x: float) -> str:
    """Return pretty number: normal style for moderate values, sci for tiny/huge."""
    if x == 0:
        return "0.0"
    ax = abs(x)
    if 1e-4 <= ax <= 1e6:
        return f"{x:,.6f}"
    return f"{x:.3e}"


def main():
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"Could not find {JSON_PATH}")

    data = json.loads(JSON_PATH.read_text())

    tick_lowers = data["tickLowers"]
    tick_uppers = data["tickUppers"]
    liquidities = data["liquidities"]

    # ---- Column Widths ----
    idx_w = 4
    tick_w = 10
    price_w = 14
    liq_w = 18

    # ---- Header ----
    print("\n=== Liquidity Ranges (USDC per 1 WETH) ===")
    print(f"Anchored price: {START_PRICE} USDC/WETH at tick {CURRENT_TICK_AT_START}\n")

    header = (
        f"{'Idx':<{idx_w}} | "
        f"{'tickLower':>{tick_w}} → {'tickUpper':<{tick_w}} | "
        f"{'USDC/WETH [low, high]':<{price_w*2+3}} | "
        f"{'LiquidityProvided':>{liq_w}}"
    )
    print(header)
    print("-" * len(header))

    # ---- Rows ----
    for i, (lo, hi, L) in enumerate(zip(tick_lowers, tick_uppers, liquidities)):

        p_lo = tick_to_price_usdc_per_weth(lo)
        p_hi = tick_to_price_usdc_per_weth(hi)

        p_lo_s = fmt_number(p_lo)
        p_hi_s = fmt_number(p_hi)

        row = (
            f"{str(i):<{idx_w}} | "
            f"{lo:>{tick_w}} → {hi:<{tick_w}} | "
            f"[{p_lo_s:>{price_w}}, {p_hi_s:<{price_w}}] | "
            f"{str(L):>{liq_w}}"
        )
        print(row)

    print("\nNOTE:")
    print("  • LiquidityProvided is the raw Uniswap v3 liquidity parameter L.")
    print("  • Higher L = deeper liquidity around that price band.")
    print("  • Price bands are derived from ticks relative to START_PRICE.")
    print("  • Formatting now uses fixed column widths for perfect alignment.")


if __name__ == "__main__":
    main()
