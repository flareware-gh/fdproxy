"""Tests for bucket assignment."""

from datetime import date, datetime

from fdproxy.buckets import assign_bucket_picks
from fdproxy.models import OptionSnapshot


def test_assign_bucket_picks_calls():
    """Test bucket assignment for calls."""
    # Create mock call options - need more to cover buckets 0.025, 0.05, 0.10, 0.20, 0.30
    options = [
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="C",
            strike=585.0,
            mid=0.20,
            delta=0.025,
            quoted_at=datetime.utcnow(),
        ),
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="C",
            strike=580.0,
            mid=0.50,
            delta=0.05,
            quoted_at=datetime.utcnow(),
        ),
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="C",
            strike=575.0,
            mid=1.00,
            delta=0.10,
            quoted_at=datetime.utcnow(),
        ),
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="C",
            strike=570.0,
            mid=2.00,
            delta=0.20,
            quoted_at=datetime.utcnow(),
        ),
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="C",
            strike=568.0,
            mid=3.00,
            delta=0.30,
            quoted_at=datetime.utcnow(),
        ),
    ]

    spot = 565.0

    assign_bucket_picks(options, spot)

    # Check that bucket picks were assigned
    bucket_picks = [opt for opt in options if opt.is_bucket_pick]
    # Should pick one for each bucket target
    assert len(bucket_picks) == 5

    # Check delta_bucket values exist in picks
    bucket_values = {opt.delta_bucket for opt in bucket_picks}
    assert 0.025 in bucket_values
    assert 0.05 in bucket_values
    assert 0.10 in bucket_values
    assert 0.20 in bucket_values
    assert 0.30 in bucket_values


def test_assign_bucket_picks_puts():
    """Test bucket assignment for puts."""
    # Create mock put options
    options = [
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="P",
            strike=555.0,
            mid=0.50,
            delta=-0.025,
            quoted_at=datetime.utcnow(),
        ),
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="P",
            strike=560.0,
            mid=1.00,
            delta=-0.05,
            quoted_at=datetime.utcnow(),
        ),
    ]

    spot = 565.0

    assign_bucket_picks(options, spot)

    # Check that bucket picks were assigned
    bucket_picks = [opt for opt in options if opt.is_bucket_pick]
    assert len(bucket_picks) == 2


def test_assign_bucket_picks_mixed():
    """Test bucket assignment with mixed calls and puts."""
    options = [
        # Calls (OTM: K > S)
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="C",
            strike=570.0,
            mid=1.00,
            delta=0.10,
            quoted_at=datetime.utcnow(),
        ),
        # Puts (OTM: K < S)
        OptionSnapshot(
            symbol="SPY",
            expiry=date(2026, 10, 27),
            dte=0,
            right="P",
            strike=560.0,
            mid=1.00,
            delta=-0.10,
            quoted_at=datetime.utcnow(),
        ),
    ]

    spot = 565.0

    assign_bucket_picks(options, spot)

    # Both should be picked
    bucket_picks = [opt for opt in options if opt.is_bucket_pick]
    assert len(bucket_picks) == 2
