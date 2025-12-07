# offchain/beta_policy.py

import math
from typing import List, Tuple


def make_beta_ranges(
    *,
    alpha: float,
    beta_param: float,
    current_tick: int,
    total_liquidity: float,
    tick_spacing: int,
    desired_ranges: int,
    range_width_ticks: int,
    separation_ticks: int,
    min_group_liq: float = 1e-3,
) -> List[Tuple[int, int, float]]:
    """
    Construct symmetric Uniswap v3 tick ranges around the current price, with
    liquidity weights shaped by a Beta(alpha, beta_param) distribution.

    - Ranges are symmetric around the nearest tick multiple of `tick_spacing`.
    - Each range has approximately `range_width_ticks` width (snapped to tick_spacing).
    - Adjacent ranges are separated by `separation_ticks` ticks (snapped to tick_spacing),
      i.e. there is a gap of `separation_ticks` ticks between the end of one band and the
      start of the next.
    - More liquidity is allocated to ranges closer to the current tick.
    - Liquidity per range is proportional to a Beta-shaped weight, then
      normalized to sum to `total_liquidity`.

    Args:
        alpha, beta_param: parameters of the Beta distribution.
        current_tick: pool's current tick.
        total_liquidity: total "virtual" liquidity budget to allocate.
        tick_spacing: Uniswap v3 tick spacing (e.g. 60).
        desired_ranges: total number of ranges (ideally even so we get
                        perfect symmetry).
        range_width_ticks: nominal width in ticks of each range (multiple of tick_spacing).
        separation_ticks: nominal gap in ticks between adjacent ranges
                          (multiple of tick_spacing).
        min_group_liq: minimum liquidity per range (to avoid zeros).

    Returns:
        List of (tickLower, tickUpper, liquidity) tuples, sorted by tickLower.
    """

    if desired_ranges < 1:
        raise ValueError("desired_ranges must be >= 1")

    # Snap to nearest valid tick multiple
    center_tick = (current_tick // tick_spacing) * tick_spacing

    # Normalize range width to a multiple of tick_spacing and at least one spacing.
    if range_width_ticks <= 0:
        raise ValueError("range_width_ticks must be > 0")

    range_width_ticks = max(
        tick_spacing,
        (range_width_ticks // tick_spacing) * tick_spacing,
    )

    # Normalize separation to a multiple of tick_spacing (can be zero).
    if separation_ticks < 0:
        raise ValueError("separation_ticks must be >= 0")

    if separation_ticks > 0:
        separation_ticks = (separation_ticks // tick_spacing) * tick_spacing

    # Number of bands on each side (for even desired_ranges).
    half = desired_ranges // 2

    # Effective step from the start of one band to the start of the next.
    # Each band has width = range_width_ticks, and the empty region between
    # bands is separation_ticks wide:
    #   [band width] + [gap] + [next band width] + ...
    step = range_width_ticks + separation_ticks

    bands: List[Tuple[int, int, int]] = []

    # Build symmetric bands around center_tick.
    # For each distance index j from 0..half-1:
    #   - below center:
    #         lower_b = center - (j+1)*step
    #         upper_b = lower_b + range_width_ticks
    #   - above center:
    #         lower_a = center + j*step + separation_ticks
    #         upper_a = lower_a + range_width_ticks
    for j in range(half):
        # Below center
        lower_b = center_tick - (j + 1) * step
        upper_b = lower_b + range_width_ticks
        bands.append((lower_b, upper_b, j))

        # Above center
        lower_a = center_tick + j * step + separation_ticks
        upper_a = lower_a + range_width_ticks
        bands.append((lower_a, upper_a, j))

    # If desired_ranges is odd, add a center band around the center_tick.
    if desired_ranges % 2 == 1:
        halfw = range_width_ticks // 2
        bands.append((center_tick - halfw, center_tick + halfw, -1))  # j = -1 → exact center

    # Assign Beta-shaped weights: ranges closer to center (small j)
    # get larger weights.
    weights: List[float] = []
    for _, _, j in bands:
        if j == -1:
            # Center band: place near the mode of the Beta on [0,1].
            x = 0.999
        else:
            # Map distance index j into (0,1], then invert so that
            # j=0 (closest to center) has x near 1, and larger j have smaller x.
            d = (j + 0.5) / max(1, half)  # avoid div by zero if half=0
            x = 1.0 - d                   # j=0 → x close to 1; j=half-1 → x ~ 0.5
            if x <= 0.0:
                x = 1e-6
            if x >= 1.0:
                x = 1.0 - 1e-6

        w = (x ** (alpha - 1.0)) * ((1.0 - x) ** (beta_param - 1.0))
        weights.append(max(w, 0.0))

    weight_sum = sum(weights)
    if weight_sum == 0.0:
        # Fallback: equal weights
        weights = [1.0] * len(bands)
        weight_sum = float(len(bands))

    scale = total_liquidity / weight_sum
    liquidities = [max(min_group_liq, w * scale) for w in weights]

    ranges = [
        (bands[i][0], bands[i][1], liquidities[i])
        for i in range(len(bands))
    ]
    ranges.sort(key=lambda r: r[0])

    return ranges
