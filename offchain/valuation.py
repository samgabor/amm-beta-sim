from decimal import Decimal


def lp_value_usdc(
    weth_balance: int,
    usdc_balance: int,
    price_usdc_per_weth: Decimal,
    weth_decimals: int = 18,
    usdc_decimals: int = 6,
) -> Decimal:
    """
    Mark LP portfolio to market in USDC.
    """
    weth = Decimal(weth_balance) / (Decimal(10) ** weth_decimals)
    usdc = Decimal(usdc_balance) / (Decimal(10) ** usdc_decimals)
    return usdc + weth * price_usdc_per_weth
