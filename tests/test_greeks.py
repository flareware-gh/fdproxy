"""Tests for Greeks computation."""

from fdproxy.greeks import (
    black_scholes_delta,
    black_scholes_price,
    compute_delta_from_mid,
    implied_volatility_from_price,
)


def test_black_scholes_call_delta():
    """Test call delta computation."""
    delta = black_scholes_delta(
        spot=100.0,
        strike=100.0,
        time_to_expiry=0.25,
        rate=0.0,
        div_yield=0.0,
        volatility=0.2,
        option_type="C",
    )

    # ATM call delta should be around 0.5
    assert 0.4 < delta < 0.6


def test_black_scholes_put_delta():
    """Test put delta computation."""
    delta = black_scholes_delta(
        spot=100.0,
        strike=100.0,
        time_to_expiry=0.25,
        rate=0.0,
        div_yield=0.0,
        volatility=0.2,
        option_type="P",
    )

    # ATM put delta should be around -0.5
    assert -0.6 < delta < -0.4


def test_black_scholes_price():
    """Test option pricing."""
    price = black_scholes_price(
        spot=100.0,
        strike=100.0,
        time_to_expiry=0.25,
        rate=0.0,
        div_yield=0.0,
        volatility=0.2,
        option_type="C",
    )

    # ATM call with 20% vol should have reasonable premium
    assert 2.0 < price < 6.0


def test_implied_volatility():
    """Test IV solving."""
    # Price a call
    true_iv = 0.25
    price = black_scholes_price(
        spot=100.0,
        strike=105.0,
        time_to_expiry=0.083,  # ~1 month
        rate=0.0,
        div_yield=0.0,
        volatility=true_iv,
        option_type="C",
    )

    # Solve for IV
    solved_iv = implied_volatility_from_price(
        option_price=price,
        spot=100.0,
        strike=105.0,
        time_to_expiry=0.083,
        rate=0.0,
        div_yield=0.0,
        option_type="C",
    )

    assert solved_iv is not None
    assert abs(solved_iv - true_iv) < 0.001


def test_compute_delta_from_mid():
    """Test delta computation from mid price."""
    # OTM call with reasonable price
    delta, source = compute_delta_from_mid(
        mid_price=2.0,
        spot=100.0,
        strike=105.0,
        time_to_expiry=0.083,
        option_type="C",
    )

    assert delta is not None
    assert source == "bs"
    assert 0.2 < delta < 0.5


def test_compute_delta_intrinsic():
    """Test intrinsic delta fallback."""
    # Zero price should use intrinsic
    delta, source = compute_delta_from_mid(
        mid_price=0.0,
        spot=100.0,
        strike=110.0,
        time_to_expiry=0.01,
        option_type="C",
    )

    assert delta == 0.0
    assert source == "intrinsic"
