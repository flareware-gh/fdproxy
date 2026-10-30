"""Time utilities for ET session dates, slots, and schedules."""

from datetime import datetime, time, timedelta

import pytz

from fdproxy.config import SLOTS

ET = pytz.timezone("America/New_York")


def now_et() -> datetime:
    """Get current time in ET timezone."""
    return datetime.now(ET)


def get_session_date(dt: datetime | None = None) -> datetime:
    """
    Get ET session date for a given datetime (or now).

    Session date is the calendar date in ET timezone.
    """
    if dt is None:
        dt = now_et()
    elif dt.tzinfo is None:
        dt = ET.localize(dt)
    else:
        dt = dt.astimezone(ET)

    return dt.date()


def slot_to_time(slot: str) -> time:
    """
    Convert slot name to target time (ET).

    Examples:
        m0935 -> 09:35
        t1530 -> 15:30
        close -> 16:00
    """
    if slot == "close":
        return time(16, 0)

    # Format: m0935 or t1530
    hour = int(slot[1:3])
    minute = int(slot[3:5])
    return time(hour, minute)


def find_nearest_slot(dt: datetime | None = None, window_minutes: int = 30) -> str | None:
    """
    Find the nearest planned slot to the given time (or now).

    Returns None if outside reasonable collection window or on weekend.
    Default window is ±30 minutes (generous for irregular schedulers).

    Args:
        dt: Datetime to check (defaults to now ET)
        window_minutes: Maximum minutes from slot to still match (default 30)
    """
    if dt is None:
        dt = now_et()

    # Check if weekend
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return None

    current_time = dt.time()

    # Find nearest slot within window
    min_delta = None
    nearest = None

    for slot in SLOTS:
        slot_time = slot_to_time(slot)

        # Convert to minutes since midnight for comparison
        current_mins = current_time.hour * 60 + current_time.minute
        slot_mins = slot_time.hour * 60 + slot_time.minute

        delta = abs(current_mins - slot_mins)

        if delta <= window_minutes:
            if min_delta is None or delta < min_delta:
                min_delta = delta
                nearest = slot

    return nearest


def is_rth(dt: datetime | None = None) -> bool:
    """
    Check if given time (or now) is during regular trading hours (09:30-16:00 ET).
    """
    if dt is None:
        dt = now_et()

    # Weekend check
    if dt.weekday() >= 5:
        return False

    current_time = dt.time()
    market_open = time(9, 30)
    market_close = time(16, 0)

    return market_open <= current_time <= market_close


def is_market_holiday(date_obj) -> bool:
    """
    Check if date is a US market holiday.

    For v1, this is a simple heuristic. Could be enhanced with a proper
    holiday calendar (pandas_market_calendars).
    """
    # TODO: Implement proper NYSE holiday calendar
    # For now, just check weekends
    if hasattr(date_obj, "weekday"):
        return date_obj.weekday() >= 5
    return False


def request_label_from_dt(dt: datetime) -> str:
    """
    Generate 5-minute request label from datetime.

    Converts to ET, floors minute to nearest 5-minute bucket, formats as rqHHmmtoHHmm
    where the second time is the last included minute of the half-open window [start, start+5min).

    Examples:
        2026-10-30 10:30:17 ET → 'rq1030to1034'
        2026-10-30 15:09:47 ET → 'rq1505to1509'
        2026-10-30 14:39:45 ET → 'rq1435to1439'
        2026-10-30 16:10:51 ET → 'rq1610to1614'

    Args:
        dt: Datetime to convert (any timezone or naive)

    Returns:
        Request label string in format rqHHmmtoHHmm
    """
    # Convert to ET
    if dt.tzinfo is None:
        dt_et = ET.localize(dt)
    else:
        dt_et = dt.astimezone(ET)

    # Floor minute to nearest 5-minute bucket
    floored_minute = (dt_et.minute // 5) * 5
    start_time = dt_et.replace(minute=floored_minute, second=0, microsecond=0)

    # End time is start + 5 minutes (half-open interval, so we show start+4 as the "to" minute)
    end_time = start_time + timedelta(minutes=4)

    # Format as rqHHmmtoHHmm
    start_str = start_time.strftime("%H%M")
    end_str = end_time.strftime("%H%M")

    return f"rq{start_str}to{end_str}"
