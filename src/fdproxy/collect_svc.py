"""Collect command implementation."""

import logging
from datetime import datetime

from fdproxy import db
from fdproxy.buckets import assign_bucket_picks
from fdproxy.config import (
    FEED_NAME,
    SYMBOLS,
    get_collector_version,
)
from fdproxy.feeds.yahoo import YahooFeed
from fdproxy.greeks import compute_delta_from_mid
from fdproxy.models import CollectResult, OptionSnapshot, TriggerEnvelope
from fdproxy.timeutil import (
    find_nearest_slot,
    get_session_date,
    is_market_holiday,
    is_rth,
    now_et,
)

logger = logging.getLogger(__name__)


def run_collect(
    slot: str | None,
    symbols: list[str] | None,
    strict: bool,
    dry_run: bool,
    trigger: TriggerEnvelope | None = None,
) -> CollectResult:
    """
    Run collection with timestamp-first logic.

    Args:
        slot: Optional intended slot label or 'auto' (assigns nearest if within ±30 min, else None)
        symbols: List of symbols to collect (None = all)
        strict: Exit 1 if any symbol fails
        dry_run: Don't write to database
        trigger: Optional trigger metadata (source, id, intended_at)

    Returns:
        CollectResult with status, counts, and timestamps
    """
    now = now_et()
    session_date = get_session_date(now)

    # Initialize trigger envelope if not provided
    if trigger is None:
        trigger = TriggerEnvelope()

    # Resolve intended_slot (soft label, never an error)
    if slot is None or slot == "auto":
        # Try to assign nearest slot within ±30 minutes
        intended_slot = find_nearest_slot(now, window_minutes=30)
    else:
        # Use explicit slot as intended label
        intended_slot = slot

    # Override from trigger envelope if provided
    if trigger.intended_slot:
        intended_slot = trigger.intended_slot

    # Check if holiday/weekend
    if is_market_holiday(session_date):
        result = CollectResult(
            session_date=session_date,
            intended_slot=intended_slot,
            status="skipped_holiday",
            symbols_attempted=[],
            symbols_success=[],
            underlying_count=0,
            option_count=0,
            bucket_picks_count=0,
            trigger_source=trigger.trigger_source,
            trigger_id=trigger.trigger_id,
            intended_at=trigger.intended_at,
        )

        if not dry_run:
            # Still record the skip
            run_id = db.create_snapshot_run(
                session_date=session_date,
                intended_slot=intended_slot,
                scheduled_at=now,
                feed_name=FEED_NAME,
                collector_version=get_collector_version(),
                status="skipped_holiday",
                trigger_source=trigger.trigger_source,
                trigger_id=trigger.trigger_id,
                intended_at=trigger.intended_at,
            )
            result.run_id = run_id

        return result

    # Warn if outside RTH (but don't fail - manual tests must work)
    if not is_rth(now):
        logger.warning(
            "Collection outside regular trading hours (09:30-16:00 ET). "
            "Proceeding for manual/test purposes."
        )

    # Resolve symbols
    target_symbols = symbols if symbols else trigger.symbols if trigger.symbols else SYMBOLS

    # Initialize feed
    feed = YahooFeed()

    # Create run record
    scheduled_at = now
    run_id = None
    request_started_at = None
    request_finished_at = None

    if not dry_run:
        run_id = db.create_snapshot_run(
            session_date=session_date,
            intended_slot=intended_slot,
            scheduled_at=scheduled_at,
            feed_name=FEED_NAME,
            collector_version=get_collector_version(),
            status="started",
            trigger_source=trigger.trigger_source,
            trigger_id=trigger.trigger_id,
            intended_at=trigger.intended_at,
        )

    # Collect data
    symbols_success = []
    symbols_failed = []

    all_underlyings = []
    all_options = []

    # Record request_started_at immediately before first API call
    request_started_at = now_et()

    for symbol in target_symbols:
        try:
            # Fetch underlying
            underlying = feed.fetch_underlying(symbol)
            all_underlyings.append(underlying)

            # Fetch 0DTE chain
            options = feed.fetch_chain_0dte(symbol, session_date)

            if options and underlying.mid:
                # Compute deltas for options missing them
                _compute_missing_deltas(options, underlying.mid, session_date, now)

                # Assign bucket picks
                assign_bucket_picks(options, underlying.mid)

            all_options.extend(options)
            symbols_success.append(symbol)

        except Exception as e:
            symbols_failed.append(symbol)
            if strict:
                # In strict mode, fail immediately
                status = "failed"
                error = f"Symbol {symbol} failed: {e}"

                # Record request_finished_at even on failure
                request_finished_at = now_et()

                if not dry_run and run_id:
                    db.update_snapshot_run(
                        run_id,
                        status=status,
                        error=error,
                        request_started_at=request_started_at,
                        request_finished_at=request_finished_at,
                    )

                return CollectResult(
                    session_date=session_date,
                    intended_slot=intended_slot,
                    status=status,
                    symbols_attempted=target_symbols,
                    symbols_success=symbols_success,
                    underlying_count=len(all_underlyings),
                    option_count=len(all_options),
                    bucket_picks_count=sum(1 for opt in all_options if opt.is_bucket_pick),
                    run_id=run_id,
                    request_started_at=request_started_at,
                    request_finished_at=request_finished_at,
                    trigger_source=trigger.trigger_source,
                    trigger_id=trigger.trigger_id,
                    intended_at=trigger.intended_at,
                )

    # Record request_finished_at after last API call
    request_finished_at = now_et()

    # Determine final status
    if symbols_failed:
        status = "partial"
    else:
        status = "ok"

    # Write to database
    if not dry_run and run_id:
        db.upsert_underlying_snapshots(run_id, all_underlyings)
        db.upsert_option_snapshots(run_id, all_options)

        # Optionally include per-symbol timings in meta
        meta = {
            "symbols_success": symbols_success,
            "symbols_failed": symbols_failed,
        }

        db.update_snapshot_run(
            run_id,
            status=status,
            meta=meta,
            request_started_at=request_started_at,
            request_finished_at=request_finished_at,
        )

    bucket_picks_count = sum(1 for opt in all_options if opt.is_bucket_pick)

    return CollectResult(
        session_date=session_date,
        intended_slot=intended_slot,
        status=status,
        symbols_attempted=target_symbols,
        symbols_success=symbols_success,
        underlying_count=len(all_underlyings),
        option_count=len(all_options),
        bucket_picks_count=bucket_picks_count,
        run_id=run_id,
        request_started_at=request_started_at,
        request_finished_at=request_finished_at,
        trigger_source=trigger.trigger_source,
        trigger_id=trigger.trigger_id,
        intended_at=trigger.intended_at,
    )


def _compute_missing_deltas(
    options: list[OptionSnapshot],
    spot_price: float,
    session_date,
    current_time: datetime,
) -> None:
    """
    Compute deltas for options that don't have them.

    Modifies options in place.
    """
    # Calculate time to expiry (to market close at 16:00 ET)
    from datetime import datetime, time

    from fdproxy.timeutil import ET

    close_time = datetime.combine(session_date, time(16, 0))
    close_time = ET.localize(close_time)

    time_delta = close_time - current_time
    time_to_expiry = time_delta.total_seconds() / (365.25 * 24 * 3600)

    # Ensure non-negative
    time_to_expiry = max(time_to_expiry, 0)

    for opt in options:
        if opt.delta is None and opt.mid is not None and opt.mid > 0:
            delta, source = compute_delta_from_mid(
                mid_price=opt.mid,
                spot=spot_price,
                strike=opt.strike,
                time_to_expiry=time_to_expiry,
                option_type=opt.right,
            )

            opt.delta = delta
            opt.delta_source = source
