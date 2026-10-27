"""Time utilities for ET session dates, slots, and schedules."""

from datetime import datetime, time

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


def find_nearest_slot(dt: datetime | None = None) -> str | None:
    """
    Find the nearest planned slot to the given time (or now).

    Returns None if outside reasonable collection window or on weekend.
    Accepts slots within ±10 minutes of the target time.
    """
    if dt is None:
        dt = now_et()

    # Check if weekend
    if dt.weekday() >= 5:  # Saturday=5, Sunday=6
        return None

    current_time = dt.time()

    # Find nearest slot within ±10 minutes
    min_delta = None
    nearest = None

    for slot in SLOTS:
        slot_time = slot_to_time(slot)

        # Convert to minutes since midnight for comparison
        current_mins = current_time.hour * 60 + current_time.minute
        slot_mins = slot_time.hour * 60 + slot_time.minute

        delta = abs(current_mins - slot_mins)

        if delta <= 10:  # Within 10 minutes
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
