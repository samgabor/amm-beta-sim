from decimal import Decimal, getcontext

# plenty of precision for 128.128 fixed math
getcontext().prec = 50

Q96 = Decimal(2) ** 96

def sqrt_price_x96_to_price(sqrt_price_x96: int, decimals0: int = 18, decimals1: int = 6) -> Decimal:
    """
    Convert Uniswap v3 sqrtPriceX96 to token1 per token0 price, adjusting for token decimals.
    Default assumes token0=WETH(18), token1=USDC(6).
    """
    sp = Decimal(sqrt_price_x96)
    price_x128 = (sp * sp) / (Q96 * Q96)  # this is price in raw units
    scale = Decimal(10) ** Decimal(decimals0 - decimals1)
    return price_x128 * scale
