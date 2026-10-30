"""Tests for timeutil module."""

from datetime import datetime, time

from fdproxy.timeutil import (
    ET,
    find_nearest_slot,
    get_session_date,
    is_rth,
    request_label_from_dt,
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
    """Test finding nearest slot with default ±30 min window."""
    # Near t1530 (within 1 minute)
    near_slot = ET.localize(datetime(2026, 10, 27, 15, 31))
    assert find_nearest_slot(near_slot) == "t1530"

    # 8 minutes from m1200 - should match with ±30 min window
    near_m1200 = ET.localize(datetime(2026, 10, 27, 12, 8))
    assert find_nearest_slot(near_m1200) == "m1200"

    # 25 minutes from close (16:00) - should match close within ±30 min window
    within_30 = ET.localize(datetime(2026, 10, 27, 15, 35))
    assert find_nearest_slot(within_30) == "t1530"

    # Far from any slot (more than 30 minutes)
    far_slot = ET.localize(datetime(2026, 10, 27, 12, 45))
    assert find_nearest_slot(far_slot) is None

    # Test with custom window (stricter ±10 min)
    far_with_strict = ET.localize(datetime(2026, 10, 27, 12, 25))
    assert find_nearest_slot(far_with_strict, window_minutes=10) is None
    assert find_nearest_slot(far_with_strict, window_minutes=30) == "m1200"

    # Weekend
    weekend = ET.localize(datetime(2026, 10, 31, 15, 30))
    assert find_nearest_slot(weekend) is None


def test_request_label_from_dt():
    """Test request label generation from datetime."""
    # Test exact hour boundary (:00)
    dt_1030 = ET.localize(datetime(2026, 10, 30, 10, 30, 17))
    assert request_label_from_dt(dt_1030) == "rq1030to1034"

    # Test :04 (last minute of window)
    dt_1004 = ET.localize(datetime(2026, 10, 30, 10, 4, 59))
    assert request_label_from_dt(dt_1004) == "rq1000to1004"

    # Test :05 (first minute of next window)
    dt_1005 = ET.localize(datetime(2026, 10, 30, 10, 5, 0))
    assert request_label_from_dt(dt_1005) == "rq1005to1009"

    # Test :59 (near next hour)
    dt_1459 = ET.localize(datetime(2026, 10, 30, 14, 59, 45))
    assert request_label_from_dt(dt_1459) == "rq1455to1459"

    # Test mid-window
    dt_1507 = ET.localize(datetime(2026, 10, 30, 15, 9, 47))
    assert request_label_from_dt(dt_1507) == "rq1505to1509"

    # Test late afternoon
    dt_1439 = ET.localize(datetime(2026, 10, 30, 14, 39, 45))
    assert request_label_from_dt(dt_1439) == "rq1435to1439"

    # Test close time
    dt_1610 = ET.localize(datetime(2026, 10, 30, 16, 10, 51))
    assert request_label_from_dt(dt_1610) == "rq1610to1614"

    # Test morning slots
    dt_0935 = ET.localize(datetime(2026, 10, 30, 9, 35, 0))
    assert request_label_from_dt(dt_0935) == "rq0935to0939"

    dt_0937 = ET.localize(datetime(2026, 10, 30, 9, 37, 22))
    assert request_label_from_dt(dt_0937) == "rq0935to0939"

    # Test Friday examples
    # Friday 10:32 -> rq1030to1034
    dt_fri_1032 = ET.localize(datetime(2026, 10, 30, 10, 32, 15))
    assert request_label_from_dt(dt_fri_1032) == "rq1030to1034"

    # Friday 15:28 -> rq1525to1529
    dt_fri_1528 = ET.localize(datetime(2026, 10, 30, 15, 28, 44))
    assert request_label_from_dt(dt_fri_1528) == "rq1525to1529"
