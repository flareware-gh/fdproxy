"""Black-Scholes Greeks computation."""

import math

from scipy.stats import norm


def black_scholes_delta(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    div_yield: float,
    volatility: float,
    option_type: str,
) -> float:
    """
    Compute Black-Scholes delta.

    Args:
        spot: Current underlying price
        strike: Option strike
        time_to_expiry: Time to expiry in years
        rate: Risk-free rate
        div_yield: Dividend yield
        volatility: Implied volatility (annualized)
        option_type: 'C' for call, 'P' for put

    Returns:
        Delta value
    """
    if time_to_expiry <= 0:
        # At expiry, delta is 0 or 1 (or -1 for puts)
        if option_type == "C":
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0

    if volatility <= 0:
        # Intrinsic delta
        if option_type == "C":
            return 1.0 if spot > strike else 0.0
        else:
            return -1.0 if spot < strike else 0.0

    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * volatility**2) * time_to_expiry) / (
        volatility * math.sqrt(time_to_expiry)
    )

    if option_type == "C":
        delta = math.exp(-div_yield * time_to_expiry) * norm.cdf(d1)
    else:  # Put
        delta = -math.exp(-div_yield * time_to_expiry) * norm.cdf(-d1)

    return delta


def black_scholes_price(
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    div_yield: float,
    volatility: float,
    option_type: str,
) -> float:
    """
    Compute Black-Scholes option price.

    Args:
        spot: Current underlying price
        strike: Option strike
        time_to_expiry: Time to expiry in years
        rate: Risk-free rate
        div_yield: Dividend yield
        volatility: Implied volatility (annualized)
        option_type: 'C' for call, 'P' for put

    Returns:
        Option price
    """
    if time_to_expiry <= 0:
        # At expiry, return intrinsic value
        if option_type == "C":
            return max(0, spot - strike)
        else:
            return max(0, strike - spot)

    if volatility <= 0:
        # Return intrinsic value
        if option_type == "C":
            return max(0, spot - strike)
        else:
            return max(0, strike - spot)

    d1 = (math.log(spot / strike) + (rate - div_yield + 0.5 * volatility**2) * time_to_expiry) / (
        volatility * math.sqrt(time_to_expiry)
    )
    d2 = d1 - volatility * math.sqrt(time_to_expiry)

    if option_type == "C":
        price = spot * math.exp(-div_yield * time_to_expiry) * norm.cdf(d1) - strike * math.exp(
            -rate * time_to_expiry
        ) * norm.cdf(d2)
    else:  # Put
        price = strike * math.exp(-rate * time_to_expiry) * norm.cdf(-d2) - spot * math.exp(
            -div_yield * time_to_expiry
        ) * norm.cdf(-d1)

    return price


def implied_volatility_from_price(
    option_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    rate: float,
    div_yield: float,
    option_type: str,
    max_iterations: int = 100,
    tolerance: float = 1e-6,
) -> float | None:
    """
    Solve for implied volatility using bisection.

    Args:
        option_price: Market price of option
        spot: Current underlying price
        strike: Option strike
        time_to_expiry: Time to expiry in years
        rate: Risk-free rate
        div_yield: Dividend yield
        option_type: 'C' for call, 'P' for put
        max_iterations: Maximum bisection iterations
        tolerance: Price tolerance

    Returns:
        Implied volatility or None if not found
    """
    if option_price <= 0 or time_to_expiry <= 0:
        return None

    # Intrinsic value
    if option_type == "C":
        intrinsic = max(0, spot - strike)
    else:
        intrinsic = max(0, strike - spot)

    if option_price < intrinsic:
        return None

    # Bisection bounds
    vol_low = 0.001
    vol_high = 5.0

    for _ in range(max_iterations):
        vol_mid = (vol_low + vol_high) / 2
        price_mid = black_scholes_price(
            spot, strike, time_to_expiry, rate, div_yield, vol_mid, option_type
        )

        if abs(price_mid - option_price) < tolerance:
            return vol_mid

        if price_mid < option_price:
            vol_low = vol_mid
        else:
            vol_high = vol_mid

    # Return best estimate even if not converged
    return (vol_low + vol_high) / 2


def compute_delta_from_mid(
    mid_price: float,
    spot: float,
    strike: float,
    time_to_expiry: float,
    option_type: str,
    rate: float = 0.0,
    div_yield: float = 0.0,
) -> tuple[float | None, str]:
    """
    Compute delta from mid price.

    First attempts to solve for IV and compute BS delta.
    Falls back to intrinsic delta if that fails.

    Args:
        mid_price: Option mid price
        spot: Underlying spot price
        strike: Strike price
        time_to_expiry: Years to expiry
        option_type: 'C' or 'P'
        rate: Risk-free rate
        div_yield: Dividend yield

    Returns:
        Tuple of (delta, source) where source is 'bs' or 'intrinsic'
    """
    if mid_price <= 0 or time_to_expiry <= 0:
        # Use intrinsic
        if option_type == "C":
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0
        return delta, "intrinsic"

    # Try to solve for IV
    iv = implied_volatility_from_price(
        mid_price, spot, strike, time_to_expiry, rate, div_yield, option_type
    )

    if iv is not None and iv > 0:
        # Compute BS delta
        delta = black_scholes_delta(spot, strike, time_to_expiry, rate, div_yield, iv, option_type)
        return delta, "bs"
    else:
        # Fall back to intrinsic
        if option_type == "C":
            delta = 1.0 if spot > strike else 0.0
        else:
            delta = -1.0 if spot < strike else 0.0
        return delta, "intrinsic"
