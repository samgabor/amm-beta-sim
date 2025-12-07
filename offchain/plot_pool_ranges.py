#!/usr/bin/env python3
"""
Plot the Uniswap v3 beta liquidity ranges stored in onchain/script/beta_ranges.json.

Bottom x-axis:
    Tick distance from the "center tick" implied by the ranges themselves (0 at center).

Top x-axis:
    ETH price in USDC, assuming price at tick distance 0 is 3200 USDC/ETH
    and evolving via Uniswap v3's price-per-tick rule:
        P(delta_tick) = 3200 * 1.0001 ** delta_tick
"""

import json
import math
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np  # <-- important for vectorized mapping


# Path to the JSON file produced by generate_beta_ranges.py
JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "onchain"
    / "script"
    / "beta_ranges.json"
)

# Assumed ETH price (in USDC) at tick distance 0
PRICE_AT_CENTER = 3200.0

# Uniswap v3 per-tick price ratio
TICK_RATIO = 1.0001


def load_beta_ranges(path: Path):
    """Load tick ranges and liquidities from beta_ranges.json."""
    data = json.loads(path.read_text())
    tick_lowers = data["tickLowers"]
    tick_uppers = data["tickUppers"]
    liquidities = data["liquidities"]
    return tick_lowers, tick_uppers, liquidities


def main():
    if not JSON_PATH.exists():
        raise FileNotFoundError(f"Could not find {JSON_PATH}")

    tick_lowers, tick_uppers, liquidities = load_beta_ranges(JSON_PATH)

    if not (len(tick_lowers) == len(tick_uppers) == len(liquidities)):
        raise ValueError("tickLowers, tickUppers, and liquidities must have same length")

    # Compute mid-ticks for each range
    mid_ticks = [(lo + hi) / 2 for lo, hi in zip(tick_lowers, tick_uppers)]

    # Derive a natural "center tick" from the ranges themselves
    # (average midpoint). This is what we'll call "0" on the x-axis.
    center_tick = sum(mid_ticks) / len(mid_ticks)

    # Build plotting data: each bar is an interval [lo, hi] with height ~ liquidity
    rel_starts = []   # start of each bar relative to center (in ticks)
    widths = []       # width in ticks of each range
    liqs_scaled = []  # scaled liquidity for nicer plotting

    # Simple scaling factor so extremely large liquidity numbers look reasonable;
    # adjust if you want different magnitudes on the y-axis.
    scale = 1e9

    for lo, hi, L in zip(tick_lowers, tick_uppers, liquidities):
        start_rel = lo - center_tick      # left edge relative to center (ticks)
        width = hi - lo                   # span of the range (ticks)
        rel_starts.append(start_rel)
        widths.append(width)
        liqs_scaled.append(L / scale)

    # Sort by start for a clean plot
    combined = sorted(zip(rel_starts, widths, liqs_scaled), key=lambda x: x[0])
    rel_starts_sorted, widths_sorted, liqs_scaled_sorted = zip(*combined)

    fig, ax = plt.subplots(figsize=(12, 6))

    # Plot each range as a bar spanning its full tick width
    for x0, w, h in zip(rel_starts_sorted, widths_sorted, liqs_scaled_sorted):
        ax.bar(x0, h, width=w, align="edge")

    # Vertical line at 0 = center tick
    ax.axvline(0, linestyle="--")

    ax.set_title("Beta Liquidity Ranges vs Tick Distance from Center Tick")
    ax.set_xlabel("Tick distance from center (ticks)")
    ax.set_ylabel("Liquidity (scaled by 1e9)")

    # --- Add top x-axis: ETH price in USDC ---

    # Vectorized: ticks (array-like) -> price (array-like)
    def ticks_to_price(delta_ticks):
        delta_ticks = np.asarray(delta_ticks)
        return PRICE_AT_CENTER * np.power(TICK_RATIO, delta_ticks)

    # Vectorized: price (array-like) -> ticks (array-like)
    def price_to_ticks(prices):
        prices = np.asarray(prices)
        # Avoid log of non-positive values
        safe = np.maximum(prices, 1e-18)
        # delta_tick = log(price / P0) / log(1.0001)
        return np.log(safe / PRICE_AT_CENTER) / math.log(TICK_RATIO)

    secax = ax.secondary_xaxis(
        "top",
        functions=(ticks_to_price, price_to_ticks),
    )

    secax.set_xlabel(
        f"ETH price (USDC), price at tick distance 0 = {PRICE_AT_CENTER:.0f} USDC"
    )

    # Custom formatter (just numbers)
    from matplotlib.ticker import FuncFormatter
    secax.xaxis.set_major_formatter(FuncFormatter(lambda x, pos: f"{x:.0f}"))

    # Hide offset text if it appears
    secax.xaxis.get_offset_text().set_visible(False)

    # <<< MOVE LABELS UP TO COVER THE "1e-5" >>>
    secax.tick_params(axis="x", pad=8)
    # <<< END FIX >>>




    #secax.ticklabel_format(axis="x", style="plain", useOffset=False)

    # from matplotlib.ticker import ScalarFormatter

    # formatter = ScalarFormatter()
    # formatter.set_scientific(False)
    # formatter.set_useOffset(False)

    # secax.xaxis.set_major_formatter(formatter)

    # fig.tight_layout()
    # plt.show()

    # from matplotlib.ticker import FuncFormatter

    # secax = ax.secondary_xaxis(
    #     "top",
    #     functions=(ticks_to_price, price_to_ticks),
    # )
    # secax.set_xlabel(
    #     f"ETH price (USDC), price at tick distance 0 = {PRICE_AT_CENTER:.0f} USDC"
    # )

    # # <<< NEW: force plain tick labels, no exponent, no offset >>>
    # price_formatter = FuncFormatter(lambda x, pos: f"{x:.0f}")   # or "{x:.2f}" if you want decimals
    # secax.xaxis.set_major_formatter(price_formatter)
    # secax.xaxis.get_offset_text().set_visible(False)
    # # <<< END NEW >>>

    fig.tight_layout()
    plt.show()


if __name__ == "__main__":
    main()
