"""Database operations for Supabase."""

import uuid
from datetime import date, datetime
from typing import Any

from fdproxy.config import get_supabase_service_role_key, get_supabase_url
from fdproxy.models import OptionSnapshot, UnderlyingSnapshot
from supabase import Client, create_client


def get_client() -> Client:
    """Get Supabase client with service role."""
    url = get_supabase_url()
    key = get_supabase_service_role_key()

    if not url or not key:
        raise ValueError("SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY must be set")

    return create_client(url, key)


def ping() -> bool:
    """Test Supabase connectivity."""
    try:
        client = get_client()
        # Simple query to test connection
        client.table("instruments").select("symbol").limit(1).execute()
        return True
    except Exception:
        return False


def list_tables() -> list[str]:
    """List available tables (via information_schema)."""
    try:
        client = get_client()
        # Use raw SQL query to list tables
        result = client.rpc("list_tables").execute()
        return result.data if result.data else []
    except Exception:
        return []


def create_snapshot_run(
    session_date: date,
    slot: str,
    scheduled_at: datetime,
    feed_name: str,
    collector_version: str,
    status: str = "started",
) -> str:
    """
    Create or update a snapshot run.

    Returns run_id (uuid as string).
    """
    client = get_client()

    run_id = str(uuid.uuid4())

    data = {
        "id": run_id,
        "session_date": session_date.isoformat(),
        "slot": slot,
        "scheduled_at": scheduled_at.isoformat(),
        "started_at": datetime.utcnow().isoformat(),
        "status": status,
        "feed_name": feed_name,
        "collector_version": collector_version,
    }

    client.table("snapshot_runs").upsert(data, on_conflict="session_date,slot").execute()

    return run_id


def update_snapshot_run(
    run_id: str,
    status: str,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    """Update snapshot run status."""
    client = get_client()

    data = {
        "id": run_id,
        "finished_at": datetime.utcnow().isoformat(),
        "status": status,
    }

    if error:
        data["error"] = error

    if meta:
        data["meta"] = meta

    client.table("snapshot_runs").update(data).eq("id", run_id).execute()


def upsert_underlying_snapshots(
    run_id: str,
    snapshots: list[UnderlyingSnapshot],
) -> int:
    """
    Upsert underlying snapshots.

    Returns count of rows affected.
    """
    if not snapshots:
        return 0

    client = get_client()

    data = []
    for snap in snapshots:
        row = {
            "run_id": run_id,
            "symbol": snap.symbol,
            "quoted_at": snap.quoted_at.isoformat(),
            "last": snap.last,
            "bid": snap.bid,
            "ask": snap.ask,
            "mid": snap.mid,
            "volume": snap.volume,
            "day_open": snap.day_open,
            "day_high": snap.day_high,
            "day_low": snap.day_low,
            "delay_seconds": snap.delay_seconds,
            "raw": snap.raw,
        }
        data.append(row)

    result = (
        client.table("underlying_snapshots").upsert(data, on_conflict="run_id,symbol").execute()
    )

    return len(result.data) if result.data else 0


def upsert_option_snapshots(
    run_id: str,
    snapshots: list[OptionSnapshot],
    batch_size: int = 500,
) -> int:
    """
    Upsert option snapshots in batches.

    Returns total count of rows affected.
    """
    if not snapshots:
        return 0

    client = get_client()
    total = 0

    # Process in batches
    for i in range(0, len(snapshots), batch_size):
        batch = snapshots[i : i + batch_size]

        data = []
        for snap in batch:
            row = {
                "run_id": run_id,
                "symbol": snap.symbol,
                "expiry": snap.expiry.isoformat(),
                "dte": snap.dte,
                "right": snap.right,
                "strike": float(snap.strike),
                "bid": snap.bid,
                "ask": snap.ask,
                "mid": snap.mid,
                "last": snap.last,
                "volume": snap.volume,
                "open_interest": snap.open_interest,
                "delta": snap.delta,
                "gamma": snap.gamma,
                "iv": snap.iv,
                "delta_bucket": snap.delta_bucket,
                "is_bucket_pick": snap.is_bucket_pick,
                "quoted_at": snap.quoted_at.isoformat(),
                "delay_seconds": snap.delay_seconds,
                "raw": snap.raw,
            }
            data.append(row)

        result = (
            client.table("option_snapshots")
            .upsert(data, on_conflict="run_id,symbol,expiry,right,strike")
            .execute()
        )

        total += len(result.data) if result.data else 0

    return total
