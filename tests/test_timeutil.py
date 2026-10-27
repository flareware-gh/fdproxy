"""Tests for timeutil module."""

from datetime import datetime, time

import pytest
import pytz

from fdproxy.timeutil import (
    ET,
    find_nearest_slot,
    get_session_date,
    is_rth,
    slot_to_time,
)


def test_slot_to_time():
    """Test slot name to time conversion."""
    assert slot_to_time("m0935") == time(9, 35)
    assert slot_to_time("t1530") == time(15, 30)
    assert slot_to_time("close") == time(16, 0)


def test_get_session_date():
    """Test session date extraction."""
    dt = ET.localize(datetime(2026, 10, 27, 14, 30))
    session_date = get_session_date(dt)
    assert session_date.year == 2026
    assert session_date.month == 10
    assert session_date.day == 27


def test_is_rth():
    """Test regular trading hours check."""
    # During market hours
    market_time = ET.localize(datetime(2026, 10, 27, 14, 30))
    assert is_rth(market_time) is True
    
    # Before market
    before_market = ET.localize(datetime(2026, 10, 27, 8, 0))
    assert is_rth(before_market) is False
    
    # After market
    after_market = ET.localize(datetime(2026, 10, 27, 17, 0))
    assert is_rth(after_market) is False
    
    # Weekend
    weekend = ET.localize(datetime(2026, 10, 31, 14, 30))  # Saturday
    assert is_rth(weekend) is False


def test_find_nearest_slot():
    """Test finding nearest slot."""
    # Near t1530
    near_slot = ET.localize(datetime(2026, 10, 27, 15, 31))
    assert find_nearest_slot(near_slot) == "t1530"
    
    # Far from any slot
    far_slot = ET.localize(datetime(2026, 10, 27, 12, 30))
    # Should return None or m1200 depending on distance
    result = find_nearest_slot(far_slot)
    assert result is None or result == "m1200"
    
    # Weekend
    weekend = ET.localize(datetime(2026, 10, 31, 15, 30))
    assert find_nearest_slot(weekend) is None
