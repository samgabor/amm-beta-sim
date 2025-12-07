import sys
import os
import csv
import argparse
from typing import Sequence
import pandas as pd


WETH_DECIMALS = 18
USDC_DECIMALS = 6


def _require_columns(df: pd.DataFrame, cols: Sequence[str]) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        print("ERROR: episode file is missing required columns:")
        for c in missing:
            print(f"  - {c}")
        print("\nAvailable columns are:")
        for c in df.columns:
            print(f"  - {c}")
        sys.exit(1)


def summarize_episode(
    num_steps: int,
    alpha: float,
    beta: float,
    num_ranges: int,
    range_width: int,
    range_sep: int,
    volatility: float,
    path: str = "episode.csv",
    summary_out: str | None = "summary.csv",
) -> None:
    df = pd.read_csv(path)
    if df.empty:
        print("Episode file is empty.")
        return

    # Required columns
    price_col = "market_price_usdc_per_weth"
    strategy_value_col = "lp_value_usdc"       # strategy value (pre-fees)
    fees_col = "fees_value_usdc"              # cumulative strategy-level fees (in USDC)

    _require_columns(df, [price_col, strategy_value_col, fees_col])

    init = df.iloc[0]
    final = df.iloc[-1]

    # Strategy (LPHelper) value (pre-fees)
    strategy_init_value = float(init[strategy_value_col])
    strategy_final_value = float(final[strategy_value_col])

    # Total fees collected by the LP strategy in the Uniswap pool (cumulative)
    strategy_total_fees = float(final[fees_col])

    init_price = float(init[price_col])
    final_price = float(final[price_col])

    # === Investor definition: 10 ETH + 50,000 USDC ===
    investor_init_weth = 10.0
    investor_init_usdc = 50_000.0

    investor_init_value = investor_init_weth * init_price + investor_init_usdc

    # Fractional ownership of strategy (linear) based on initial value
    if strategy_init_value == 0:
        print("ERROR: strategy_init_value is 0; cannot compute investor scaling.")
        return

    fraction = investor_init_value / strategy_init_value

    # Investor pre-fee LP value at the end (their share of the strategy LP)
    investor_lp_final_value = fraction * strategy_final_value

    # Investor fee income (their pro-rata share of strategy_total_fees)
    investor_fees = fraction * strategy_total_fees

    # Investor total final value INCLUDING fees
    investor_final_value = investor_lp_final_value + investor_fees

    # HODL benchmark: just keep 10 ETH + 50,000 USDC
    investor_hodl_final_value = investor_init_weth * final_price + investor_init_usdc

    # Net P&L vs initial portfolio (after fees)
    investor_pnl = investor_final_value - investor_init_value
    investor_net_return = (investor_final_value / investor_init_value) - 1.0

    # LP vs HODL (after fees)
    investor_pnl_vs_hodl = investor_final_value - investor_hodl_final_value

    # Pre-fee IL (absolute, positive means loss vs HODL ignoring fees)
    investor_il_abs = investor_hodl_final_value - investor_lp_final_value
    investor_il_pct = (
        investor_il_abs / investor_hodl_final_value
        if investor_hodl_final_value != 0
        else 0.0
    )

    # -------- Print textual summary --------
    print("=== Investor-view episode summary ===\n")

    print(f"Steps:                         {len(df)}\n")

    print("Strategy (LPHelper) portfolio")
    print(f"  Initial value (pre-fees):    {strategy_init_value:,.6f} USDC")
    print(f"  Final value (pre-fees):      {strategy_final_value:,.6f} USDC")
    print(f"  Strategy return (pre-fees):  {((strategy_final_value / strategy_init_value) - 1):.4%}")
    print(f"  Strategy total fees:         {strategy_total_fees:,.6f} USDC\n")

    print("Investor portfolio (10 ETH + 50,000 USDC)")
    print(f"  Initial ETH:                 {investor_init_weth:,.6f} ETH")
    print(f"  Initial USDC:                {investor_init_usdc:,.2f} USDC")
    print(f"  Initial ETH price:           {init_price:,.4f} USDC/ETH")
    print(f"  Initial portfolio value:     {investor_init_value:,.6f} USDC\n")

    print(f"  Final ETH price:             {final_price:,.4f} USDC/ETH")
    print(f"  HODL final value:            {investor_hodl_final_value:,.6f} USDC")
    print(f"  LP final value (pre-fees):   {investor_lp_final_value:,.6f} USDC")
    print(f"  Investor total fees:         {investor_fees:,.6f} USDC")
    print(f"  Final portfolio value:       {investor_final_value:,.6f} USDC")
    print(f"  Net P&L (after fees):        {investor_pnl:,.6f} USDC")
    print(f"  Net return (after fees):     {investor_net_return:.4%}")
    print(f"  Investor P&L LP vs HODL:     {investor_pnl_vs_hodl:,.6f} USDC")
    print(f"  Investor IL (pre-fees, abs): {investor_il_abs:,.6f} USDC")
    print(f"  Investor IL (pre-fees, %):   {investor_il_pct:.4%}")

    # Optional debug info
    try:
        final_pool_price = float(final.get("pool_price_usdc_per_weth", float("nan")))
        final_tick = int(final.get("tick", 0))
        print("\n--- Debug info (optional) ---")
        if not pd.isna(final_pool_price):
            print(f"  Final pool price:            {final_pool_price:,.4f} USDC/ETH")
        print(f"  Final tick:                  {final_tick}")
    except Exception:
        pass

    # -------- Append/create summary CSV if requested --------
    if summary_out is not None:
        header = [
            "num_steps",
            "alpha",
            "beta",
            "num_ranges",
            "range_width",
            "range_sep",
            "volatility",
            "init_price",
            "investor_init_value",
            "final_price",
            "investor_final_value",
            "investor_pnl",
            "net_return",
            "investor_il_abs",
            "investor_il_pct",
            "strategy_total_fees",
            "investor_fees",
        ]
        row = [
            num_steps,
            alpha,
            beta,
            num_ranges,
            range_width,
            range_sep,
            volatility,
            init_price,
            investor_init_value,
            final_price,
            investor_final_value,
            investor_pnl,
            investor_net_return,
            investor_il_abs,
            investor_il_pct,
            strategy_total_fees,
            investor_fees,
        ]

        file_exists = os.path.exists(summary_out)

        with open(summary_out, mode="a", newline="") as f:
            writer = csv.writer(f)
            if not file_exists:
                writer.writerow(header)
            writer.writerow(row)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Print a summary for an episode.csv and optionally append to a summary CSV."
    )
    parser.add_argument(
        "--path",
        nargs="?",
        default="episode.csv",
        help="Path to episode CSV (default: episode.csv)",
    )
    parser.add_argument(
        "--summary-out",
        type=str,
        default="summary.csv",
        help=(
            "Optional path to a summary CSV file. "
            "If it does not exist, it will be created with a header; "
            "if it exists, a new summary row will be appended."
        ),
    )
    parser.add_argument(
        "--num-steps",
        type=int,
        default=None,
        help=(
            "# of steps in the episode (for recording in summary CSV)."
        ),
    )
    parser.add_argument(
        "--alpha",
        type=float,
        default=None,
        help=(
            "Beta distribution alpha."
        ),
    )
    parser.add_argument(
        "--beta",
        type=float,
        default=None,
        help=(
            "Beta distribution beta."
        ),
    )
    parser.add_argument(
        "--num-ranges",
        type=int,
        default=None,
        help=(
            "# of ranges for the histogram."
        ),
    )
    parser.add_argument(
        "--range-width",
        type=int,
        default=None,
        help=(
            "Width of each range (in basis points)."
        ),
    )
    parser.add_argument(
        "--range-sep",
        type=int,
        default=None,
        help=(
            "Separation between ranges (in basis points)."
        ),
    )
    parser.add_argument(
        "--volatility",
        type=float,
        default=None,
        help=(
            "Volatility (annualized standard deviation of returns)."
        ),
    )

    args = parser.parse_args()
    summarize_episode(
        num_steps=args.num_steps,
        alpha=args.alpha,
        beta=args.beta,
        num_ranges=args.num_ranges,
        range_width=args.range_width,
        range_sep=args.range_sep,
        volatility=args.volatility,
        path=args.path,
        summary_out=args.summary_out,
    )


if __name__ == "__main__":
    main()
