"""Collect command implementation."""

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
from fdproxy.models import CollectResult, OptionSnapshot
from fdproxy.timeutil import (
    find_nearest_slot,
    get_session_date,
    is_market_holiday,
    now_et,
)


def run_collect(
    slot: str | None,
    symbols: list[str] | None,
    strict: bool,
    dry_run: bool,
) -> CollectResult:
    """
    Run collection for one slot.

    Args:
        slot: Slot name or 'auto' or None (uses auto)
        symbols: List of symbols to collect (None = all)
        strict: Exit 1 if any symbol fails
        dry_run: Don't write to database

    Returns:
        CollectResult with status and counts
    """
    now = now_et()
    session_date = get_session_date(now)

    # Resolve slot
    if slot is None or slot == "auto":
        resolved_slot = find_nearest_slot(now)
        if resolved_slot is None:
            raise ValueError(
                "No slot within ±10 minutes; use explicit --slot or wait for collection window"
            )
    else:
        resolved_slot = slot

    # Check if holiday/weekend
    if is_market_holiday(session_date):
        result = CollectResult(
            session_date=session_date,
            slot=resolved_slot,
            status="skipped_holiday",
            symbols_attempted=[],
            symbols_success=[],
            underlying_count=0,
            option_count=0,
            bucket_picks_count=0,
        )

        if not dry_run:
            # Still record the skip
            run_id = db.create_snapshot_run(
                session_date=session_date,
                slot=resolved_slot,
                scheduled_at=now,
                feed_name=FEED_NAME,
                collector_version=get_collector_version(),
                status="skipped_holiday",
            )
            result.run_id = run_id

        return result

    # Resolve symbols
    target_symbols = symbols if symbols else SYMBOLS

    # Initialize feed
    feed = YahooFeed()

    # Create run record
    scheduled_at = now
    run_id = None

    if not dry_run:
        run_id = db.create_snapshot_run(
            session_date=session_date,
            slot=resolved_slot,
            scheduled_at=scheduled_at,
            feed_name=FEED_NAME,
            collector_version=get_collector_version(),
            status="started",
        )

    # Collect data
    symbols_success = []
    symbols_failed = []

    all_underlyings = []
    all_options = []

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

                if not dry_run and run_id:
                    db.update_snapshot_run(run_id, status=status, error=error)

                return CollectResult(
                    session_date=session_date,
                    slot=resolved_slot,
                    status=status,
                    symbols_attempted=target_symbols,
                    symbols_success=symbols_success,
                    underlying_count=len(all_underlyings),
                    option_count=len(all_options),
                    bucket_picks_count=sum(1 for opt in all_options if opt.is_bucket_pick),
                    run_id=run_id,
                )

    # Determine final status
    if symbols_failed:
        status = "partial"
    else:
        status = "ok"

    # Write to database
    if not dry_run and run_id:
        db.upsert_underlying_snapshots(run_id, all_underlyings)
        db.upsert_option_snapshots(run_id, all_options)

        meta = {
            "symbols_success": symbols_success,
            "symbols_failed": symbols_failed,
        }

        db.update_snapshot_run(
            run_id,
            status=status,
            meta=meta,
        )

    bucket_picks_count = sum(1 for opt in all_options if opt.is_bucket_pick)

    return CollectResult(
        session_date=session_date,
        slot=resolved_slot,
        status=status,
        symbols_attempted=target_symbols,
        symbols_success=symbols_success,
        underlying_count=len(all_underlyings),
        option_count=len(all_options),
        bucket_picks_count=bucket_picks_count,
        run_id=run_id,
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
