"""Delta bucket assignment for option chains."""

from fdproxy.config import DELTA_BUCKETS
from fdproxy.models import OptionSnapshot


def assign_bucket_picks(
    options: list[OptionSnapshot],
    spot_price: float,
) -> None:
    """
    Assign delta_bucket and is_bucket_pick to options in place.

    For each right (C/P) independently, pick strikes closest to target
    delta buckets among OTM options.

    Args:
        options: List of OptionSnapshot (modified in place)
        spot_price: Current underlying price
    """
    # Separate calls and puts
    calls = [opt for opt in options if opt.right == "C"]
    puts = [opt for opt in options if opt.right == "P"]

    # Process calls (OTM: K > S)
    _assign_buckets_for_side(
        calls,
        spot_price,
        is_call=True,
    )

    # Process puts (OTM: K < S)
    _assign_buckets_for_side(
        puts,
        spot_price,
        is_call=False,
    )


def _assign_buckets_for_side(
    options: list[OptionSnapshot],
    spot_price: float,
    is_call: bool,
) -> None:
    """Assign buckets for one side (calls or puts)."""
    # Filter OTM options with valid delta
    if is_call:
        otm_options = [opt for opt in options if opt.strike > spot_price and opt.delta is not None]
    else:
        otm_options = [opt for opt in options if opt.strike < spot_price and opt.delta is not None]

    if not otm_options:
        return

    # For each target bucket, find closest option
    for target_delta in DELTA_BUCKETS:
        best_option = None
        best_distance = float("inf")

        for opt in otm_options:
            abs_delta = abs(opt.delta)
            distance = abs(abs_delta - target_delta)

            if distance < best_distance:
                best_distance = distance
                best_option = opt
            elif distance == best_distance and best_option is not None:
                # Tie-breaker: prefer closer to ATM (higher strike for calls, lower for puts)
                if is_call:
                    if opt.strike < best_option.strike:
                        best_option = opt
                else:
                    if opt.strike > best_option.strike:
                        best_option = opt

        if best_option is not None:
            best_option.delta_bucket = target_delta
            best_option.is_bucket_pick = True

    # For non-picks, still set delta_bucket to nearest (optional)
    for opt in otm_options:
        if not opt.is_bucket_pick and opt.delta is not None:
            abs_delta = abs(opt.delta)
            nearest_bucket = min(DELTA_BUCKETS, key=lambda b: abs(abs_delta - b))
            opt.delta_bucket = nearest_bucket
