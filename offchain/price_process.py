from __future__ import annotations

from dataclasses import dataclass
import math
import random


@dataclass
class PriceProcessState:
    """
    r : latent non-negative scale (e.g. volatility or intensity)
    S : fundamental ETH price in USDC (USDC per 1 WETH)
    """
    r: float
    S: float


def step_price(
    state: PriceProcessState,
    kappa: float,
    r_bar: float,
    sigma_s: float,
    rng: random.Random,
) -> PriceProcessState:
    """
    Mean-reverting Gaussian process for r_t (clipped at 0), then use r_t
    as a volatility scale for a signed log-return on S_t.

        r_t = max(0, κ r̄ + (1-κ) r_{t-1} + u_t),  u_t ~ N(0, σ_s^2)
        ε_t ~ N(0, r_t^2)
        S_t = S_{t-1} * exp(ε_t)

    Returns a new PriceProcessState.
    """
    # 1) update latent scale r_t
    u_t = rng.normalvariate(0.0, sigma_s)
    r_new = max(0.0, kappa * r_bar + (1.0 - kappa) * state.r + u_t)

    # 2) use r_t as volatility scale for a signed log-return
    eps_t = rng.normalvariate(0.0, r_new)
    S_new = state.S * math.exp(eps_t)

    return PriceProcessState(r=r_new, S=S_new)
