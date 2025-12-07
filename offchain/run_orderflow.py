from __future__ import annotations

import argparse
import json
import logging
import random
from dataclasses import dataclass
from decimal import Decimal, getcontext
from typing import Dict, Any, List, Tuple

import pandas as pd
from tqdm.auto import tqdm
from pathlib import Path

from sim_step import run_step
from state_snapshot import get_state
#from summarize_episode import summarize_episode

# high precision for price math
getcontext().prec = 60

# ------------------------- pool fee config ------------------------------

# Uniswap v3 fee tier in parts-per-million.
# For a 0.3% pool, this is 3000. For 0.05% use 500; for 1% use 10000.
POOL_FEE_PPM = Decimal("3000")
ONE_MILLION = Decimal("1000000")
WETH_DECIMALS = Decimal("1e18")
USDC_DECIMALS = Decimal("1e6")


# Path to the JSON file produced by generate_beta_ranges.py
JSON_PATH = (
    Path(__file__).resolve().parents[1]
    / "onchain"
    / "script"
    / "beta_ranges.json"
)


def compute_fee_usdc(
    amount_in_raw: int,
    zero_for_one: bool,
    market_price: Decimal,
) -> Decimal:
    """
    Compute LP fee value in USDC for a single swap, given:

      - amount_in_raw: token amount passed into run_step (raw units)
      - zero_for_one: True if WETH->USDC (token0->token1), False if USDC->WETH
      - market_price: USDC per WETH (external market price)

    Economics:
      fee_fraction = fee_tier / 1e6   (e.g. 3000 / 1e6 = 0.003 for 0.3%)
      fee_amount_token = amount_in_token * fee_fraction
      fee_value_usdc = fee_amount_token * price_token_in_in_USDC
    """
    if amount_in_raw <= 0:
        return Decimal(0)

    fee_fraction = POOL_FEE_PPM / ONE_MILLION

    if zero_for_one:
        # WETH -> USDC, token_in = WETH (18 decimals)
        amount_weth = Decimal(amount_in_raw) / WETH_DECIMALS
        fee_weth = amount_weth * fee_fraction
        fee_value_usdc = fee_weth * market_price
    else:
        # USDC -> WETH, token_in = USDC (6 decimals)
        amount_usdc = Decimal(amount_in_raw) / USDC_DECIMALS
        fee_usdc = amount_usdc * fee_fraction
        fee_value_usdc = fee_usdc  # already in USDC

    return fee_value_usdc


# ----------------------------- logging ---------------------------------


def setup_logger(log_path: str) -> logging.Logger:
    """Configure a file-only logger for the simulation."""
    logger = logging.getLogger("run_orderflow")
    logger.setLevel(logging.INFO)

    # Clear any existing handlers so repeated runs don't duplicate logs
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, mode="w", encoding="utf-8")
    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    # Do not propagate to root, so we don't spam stdout and interfere with tqdm
    logger.propagate = False

    return logger


# ---------------------- beta ranges / tick helpers ---------------------


def load_beta_ranges(path: Path) -> List[Tuple[int, int]]:
    """
    Load beta ranges from a JSON file with keys:
      - tickLowers: [int, ...]
      - tickUppers: [int, ...]
    and return a list of (lower, upper) tuples.
    """
    with open(path, "r") as f:
        data = json.load(f)

    lowers = data["tickLowers"]
    uppers = data["tickUppers"]

    if len(lowers) != len(uppers):
        raise ValueError("beta_ranges.json: tickLowers and tickUppers length mismatch")

    return [(int(lo), int(hi)) for lo, hi in zip(lowers, uppers)]


def is_tick_in_any_range(tick: int, ranges: List[Tuple[int, int]]) -> bool:
    """
    Return True if the given tick lies in at least one [lower, upper) range.
    """
    for lo, hi in ranges:
        if lo <= tick < hi:
            return True
    return False


# ------------------------- price process --------------------------------


@dataclass
class PriceProcessState:
    """Simple price process state for the external market price."""
    price: Decimal


def step_price(
    state: PriceProcessState,
    rng: random.Random,
    sigma: Decimal = Decimal("0.01"),
) -> PriceProcessState:
    """Lognormal price step for the external market."""
    from math import exp

    p = state.price
    if p <= 0:
        p = Decimal("1000")

    z = rng.normalvariate(0.0, 1.0)
    factor = Decimal(str(exp(float(sigma) * z)))
    new_price = p * factor
    return PriceProcessState(price=new_price)


# --------------------------- arbitrage ----------------------------------


def run_arbitrage_step(
    logger: logging.Logger,
    pool_price_start: Decimal,
    market_price: Decimal,
    rng: random.Random,
    beta_ranges: List[Tuple[int, int]],
    max_arb_trades: int = 3,
    band: float = 0.001,
) -> tuple[Decimal, int, Decimal]:
    """
    Internal arb that nudges the pool price toward the external market price.

    Only accrues fees for arb trades when the current tick lies within
    at least one of the beta ranges.

    Returns:
      (final_pool_price, n_arb_trades, arb_fees_usdc)
    """
    from state_snapshot import get_state
    from sim_step import run_step

    pool_price = pool_price_start
    n_trades = 0
    arb_fees_usdc = Decimal(0)

    p_pool = pool_price
    p_mkt = market_price

    if p_pool <= 0 or p_mkt <= 0:
        print("[arb warn] invalid prices, aborting arb")
        return pool_price, n_trades, arb_fees_usdc

    rel_diff = (p_pool - p_mkt) / p_mkt
    if abs(rel_diff) <= band:
        logger.info(f"[arb info] pool price within band (rel_diff={rel_diff:.6f}), no arb")
        return pool_price, n_trades, arb_fees_usdc

    sell_weth = rel_diff > 0  # pool > market → WETH too expensive → sell WETH
    state = get_state()
    swap_bal = state["balances"].get("swap_helper", {})
    weth_bal = int(swap_bal.get("weth", 0))
    usdc_bal = int(swap_bal.get("usdc", 0))

    if sell_weth:
        token_in_bal = weth_bal
        zero_for_one = True   # WETH -> USDC
        direction_str = "WETH->USDC"
    else:
        token_in_bal = usdc_bal
        zero_for_one = False  # USDC -> WETH
        direction_str = "USDC->WETH"

    if token_in_bal <= 0:
        logger.info("[arb info] no balance for arbitrage, aborting")
        return pool_price, n_trades, arb_fees_usdc

    max_affordable = token_in_bal // 2
    if max_affordable <= 0:
        logger.info("[arb info] max_affordable <= 0, aborting arb")
        return pool_price, n_trades, arb_fees_usdc

    # Probe trade
    probe_frac = Decimal("0.05")
    probe_amount = int(max(1, (Decimal(max_affordable) * probe_frac)))
    logger.info(
        f"[arb info] probe {direction_str}: probe_amount={probe_amount}, "
        f"max_affordable={max_affordable}"
    )

    try:
        probe_result = run_step(probe_amount, zero_for_one=zero_for_one, logger=logger)
    except Exception as e:
        print(f"[arb warn] probe trade failed: {e}")
        return pool_price, n_trades, arb_fees_usdc

    n_trades += 1

    # Only accrue fees if tick after this trade is inside any LP range
    st_after_probe = get_state()
    tick_after_probe = int(st_after_probe["tick"])
    if is_tick_in_any_range(tick_after_probe, beta_ranges):
        arb_fees_usdc += compute_fee_usdc(probe_amount, zero_for_one, market_price)

    p_after_probe = Decimal(str(probe_result["price"]))
    rel_diff_after_probe = (p_after_probe - p_mkt) / p_mkt
    logger.info(
        f"[arb info] after probe: pool_price={p_after_probe}, "
        f"rel_diff={rel_diff_after_probe:.6f}"
    )

    if abs(rel_diff_after_probe) <= band or n_trades >= max_arb_trades:
        return p_after_probe, n_trades, arb_fees_usdc

    delta_p = p_after_probe - p_pool
    delta_q = Decimal(probe_amount)

    if delta_q == 0 or delta_p == 0:
        logger.info("[arb info] no slope from probe, doing naive arb")
        naive_amount = int(max(1, max_affordable // 4))
        try:
            naive_res = run_step(naive_amount, zero_for_one=zero_for_one, logger=logger)
            n_trades += 1

            st_after_naive = get_state()
            tick_after_naive = int(st_after_naive["tick"])
            if is_tick_in_any_range(tick_after_naive, beta_ranges):
                arb_fees_usdc += compute_fee_usdc(naive_amount, zero_for_one, market_price)

            return Decimal(str(naive_res["price"])), n_trades, arb_fees_usdc
        except Exception as e:
            print(f"[arb warn] naive arb failed: {e}")
            return p_after_probe, n_trades, arb_fees_usdc

    slope = delta_p / delta_q
    logger.info(f"[arb info] estimated slope dP/dq ≈ {slope}")

    if slope == 0:
        logger.info("[arb info] slope=0, cannot improve further")
        return p_after_probe, n_trades, arb_fees_usdc

    remaining_delta_p = p_mkt - p_after_probe
    q_target = remaining_delta_p / slope

    if q_target <= 0:
        logger.info("[arb info] q_target <= 0 after probe; no further arb")
        return p_after_probe, n_trades, arb_fees_usdc

    remaining_budget = max_affordable - probe_amount
    if remaining_budget <= 0:
        logger.info("[arb info] no remaining token budget, stopping arb")
        return p_after_probe, n_trades, arb_fees_usdc

    q_target_int = int(q_target)
    q_target_int = max(1, min(q_target_int, remaining_budget))

    logger.info(
        f"[arb info] main {direction_str} trade: q_target≈{q_target}, "
        f"clamped to {q_target_int}, remaining_budget={remaining_budget}"
    )

    try:
        main_result = run_step(q_target_int, zero_for_one=zero_for_one, logger=logger)
    except Exception as e:
        print(f"[arb warn] main arb trade failed: {e}")
        return p_after_probe, n_trades, arb_fees_usdc

    n_trades += 1

    st_after_main = get_state()
    tick_after_main = int(st_after_main["tick"])
    if is_tick_in_any_range(tick_after_main, beta_ranges):
        arb_fees_usdc += compute_fee_usdc(q_target_int, zero_for_one, market_price)

    p_after_main = Decimal(str(main_result["price"]))
    rel_diff_after_main = (p_after_main - p_mkt) / p_mkt
    logger.info(
        f"[arb info] after main trade: pool_price={p_after_main}, "
        f"rel_diff={rel_diff_after_main:.6f}"
    )

    if abs(rel_diff_after_main) <= band or n_trades >= max_arb_trades:
        return p_after_main, n_trades, arb_fees_usdc

    remaining_budget = max_affordable - probe_amount - q_target_int
    if remaining_budget <= 0:
        return p_after_main, n_trades, arb_fees_usdc

    nudge_amount = int(max(1, remaining_budget // 10))
    logger.info(
        f"[arb info] final nudge {direction_str}: nudge_amount={nudge_amount}, "
        f"remaining_budget={remaining_budget}"
    )

    try:
        nudge_res = run_step(nudge_amount, zero_for_one=zero_for_one, logger=logger)
        n_trades += 1

        st_after_nudge = get_state()
        tick_after_nudge = int(st_after_nudge["tick"])
        if is_tick_in_any_range(tick_after_nudge, beta_ranges):
            arb_fees_usdc += compute_fee_usdc(nudge_amount, zero_for_one, market_price)

        final_price = Decimal(str(nudge_res["price"]))
        return final_price, n_trades, arb_fees_usdc
    except Exception as e:
        print(f"[arb warn] final nudge failed: {e}")
        return p_after_main, n_trades, arb_fees_usdc


# ----------------------- valuation helpers ------------------------------


def value_position_usdc(
    weth_raw: int,
    usdc_raw: int,
    price_usdc_per_weth: Decimal,
    weth_decimals: int = 18,
    usdc_decimals: int = 6,
) -> Decimal:
    """Value a WETH/USDC position in USDC at the given price."""
    weth = Decimal(weth_raw) / (Decimal(10) ** weth_decimals)
    usdc = Decimal(usdc_raw) / (Decimal(10) ** usdc_decimals)
    return weth * price_usdc_per_weth + usdc


# ------------------------- main simulation ------------------------------


def run_episode(
    n_steps: int = 250,
    seed: int = 42,
    outfile: str = "episode.csv",
    log_path: str = "simlog.txt",
    volatility: Decimal = Decimal("0.01"),
) -> pd.DataFrame:
    """Run a full simulation episode."""
    logger = setup_logger(log_path)
    logger.info("Starting episode: n_steps=%s seed=%s outfile=%s", n_steps, seed, outfile)

    rng = random.Random(seed)

    # Load beta ranges once
    try:
        beta_ranges = load_beta_ranges(JSON_PATH)
        logger.info("Loaded %s beta ranges from beta_ranges.json", len(beta_ranges))
    except Exception as e:
        logger.exception("Failed to load beta_ranges.json, assuming no ranges. Error: %s", e)
        beta_ranges = []

    # --- initial on-chain state ---
    state0 = get_state()
    init_pool_price = Decimal(str(state0["price"]))  # USDC per WETH from pool
    init_tick = int(state0["tick"])

    logger.info("Initial pool price: %s USDC/WETH", init_pool_price)
    logger.info("Initial tick: %s", init_tick)

    # external market price starts at the pool price
    price_state = PriceProcessState(price=init_pool_price)

    # LPHelper + pool as the "strategy" portfolio
    init_lp_helper = state0["balances"]["lp_helper"]
    init_pool = state0["balances"]["pool"]

    weth0 = init_lp_helper["weth"] + init_pool["weth"]
    usdc0 = init_lp_helper["usdc"] + init_pool["usdc"]

    init_strategy_value = value_position_usdc(weth0, usdc0, init_pool_price)
    logger.info("Initial strategy WETH raw=%s USDC raw=%s", weth0, usdc0)
    logger.info("Initial strategy value (USDC): %s", init_strategy_value)

    rows: List[Dict[str, Any]] = []

    # cumulative LP fees (strategy-level), valued in USDC at trade-time prices
    cumulative_fees_usdc = Decimal(0)

    # ------------------ main loop with tqdm progress bar -----------------
    for step_idx in tqdm(range(n_steps), desc="Simulating", unit="step"):
        # 1) advance external market price
        price_state = step_price(price_state, rng, sigma=volatility)
        market_price = price_state.price

        # 2) read current pool state
        st = get_state()
        pool_price = Decimal(str(st["price"]))
        tick = int(st["tick"])

        # 3) choose trade direction and size in notional USDC
        direction = rng.choice(["buy_weth", "sell_weth"])

        base_notional_usdc = max(Decimal("100"), init_strategy_value * Decimal("0.01"))
        base_notional_usdc = min(base_notional_usdc, Decimal("10000"))

        # Track the trade we actually did for fee computation
        last_amount_in_raw = 0
        last_zero_for_one = False

        if direction == "buy_weth":
            # USDC -> WETH (token1 -> token0)
            amount_usdc = int(base_notional_usdc * USDC_DECIMALS)
            zero_for_one = False
            last_amount_in_raw = amount_usdc
            last_zero_for_one = zero_for_one

            logger.info(
                "step %s: BUY WETH notional=%s USDC amount_usdc_raw=%s",
                step_idx,
                base_notional_usdc,
                amount_usdc,
            )
            try:
                res = run_step(amount_usdc, zero_for_one=zero_for_one, logger=logger)
            except Exception as e:
                logger.exception("step %s: buy_weth swap failed: %s", step_idx, e)
                continue
        else:
            # WETH -> USDC (token0 -> token1)
            weth_amount = (base_notional_usdc / max(market_price, Decimal("1")))
            amount_weth = int(weth_amount * WETH_DECIMALS)
            zero_for_one = True
            last_amount_in_raw = amount_weth
            last_zero_for_one = zero_for_one

            logger.info(
                "step %s: SELL WETH notional=%s USDC amount_weth_raw=%s",
                step_idx,
                base_notional_usdc,
                amount_weth,
            )
            try:
                res = run_step(amount_weth, zero_for_one=zero_for_one, logger=logger)
            except Exception as e:
                logger.exception("step %s: sell_weth swap failed: %s", step_idx, e)
                continue

        # 3b) after the flow trade, see if tick is inside any LP range; only then accrue fees
        post_flow = get_state()
        post_flow_tick = int(post_flow["tick"])
        if is_tick_in_any_range(post_flow_tick, beta_ranges):
            cumulative_fees_usdc += compute_fee_usdc(
                last_amount_in_raw, last_zero_for_one, market_price
            )

        # 4) after swap, read new pool state for valuation and arb
        post = post_flow
        post_pool_price = Decimal(str(post["price"]))
        post_tick = int(post["tick"])

        # 5) internal arbitrage towards market price (also generates fees, but only in-range)
        pool_price_after_arb, n_arb_trades, arb_fees_usdc = run_arbitrage_step(
            pool_price_start=post_pool_price,
            market_price=market_price,
            rng=rng,
            beta_ranges=beta_ranges,
            max_arb_trades=10,
            logger=logger,
        )
        cumulative_fees_usdc += arb_fees_usdc
        logger.info(
            "Pool price after %s arb trades is %s",
            n_arb_trades,
            pool_price_after_arb,
        )

        # 6) recompute simple LP holdings (lp_helper + pool)
        lp_helper_bal = post["balances"]["lp_helper"]
        pool_bal = post["balances"]["pool"]
        lp_weth_total = lp_helper_bal["weth"] + pool_bal["weth"]
        lp_usdc_total = lp_helper_bal["usdc"] + pool_bal["usdc"]

        lp_value_usdc = value_position_usdc(lp_weth_total, lp_usdc_total, market_price)
        hodl_value_usdc = value_position_usdc(weth0, usdc0, market_price)
        lp_vs_hodl = lp_value_usdc - hodl_value_usdc

        # 7) Decompose LP vs HODL into Fees + IL
        fees_value_usdc = cumulative_fees_usdc
        il_value_usdc = lp_vs_hodl - fees_value_usdc

        row: Dict[str, Any] = {
            "step": step_idx,
            "direction": direction,
            "tick": post_tick,
            "pool_price_usdc_per_weth": float(pool_price_after_arb),
            "market_price_usdc_per_weth": float(market_price),
            "n_arb_trades": n_arb_trades,
            "lp_weth": lp_weth_total,
            "lp_usdc": lp_usdc_total,
            "lp_value_usdc": float(lp_value_usdc),
            "hodl_value_usdc": float(hodl_value_usdc),
            "lp_vs_hodl": float(lp_vs_hodl),
            "fees_value_usdc": float(fees_value_usdc),
            "il_value_usdc": float(il_value_usdc),
        }

        # Include swap details if run_step returned them
        if isinstance(res, dict):
            if "amount_in_wei" in res:
                row["amount_in_wei"] = int(res["amount_in_wei"])
            if "tx_hash" in res:
                txh = res["tx_hash"]
                if hasattr(txh, "hex"):
                    txh = txh.hex()
                row["tx_hash"] = txh

        rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(outfile, index=False)
    logger.info("Episode finished. Wrote %s rows to %s", len(df), outfile)
    return df


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Uniswap v3 beta-range simulation episode.")
    parser.add_argument("--steps", type=int, default=250, help="Number of simulation steps.")
    parser.add_argument("--seed", type=int, default=42, help="Random seed.")
    parser.add_argument("--volatility", type=Decimal, default=0.01, help="Volatility of price process.")
    parser.add_argument("--out", type=str, default="episode.csv", help="Output CSV path.")
    parser.add_argument(
        "--log",
        type=str,
        default="simlog.txt",
        help="Log file to write all console output (default: simlog.txt)",
    )
    args = parser.parse_args()

    df = run_episode(
        n_steps=args.steps,
        seed=args.seed,
        outfile=args.out,
        log_path=args.log,
        volatility=Decimal(str(args.volatility)),
    )

    print(f"\nSaved episode to {args.out}")
    print(f"Detailed log written to {args.log}")


if __name__ == "__main__":
    main()
