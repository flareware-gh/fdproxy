"""Data models for snapshots and JSON envelopes."""

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, Field


class TriggerEnvelope(BaseModel):
    """Trigger metadata for a collection run."""

    trigger_source: str | None = None
    trigger_id: str | None = None
    intended_at: datetime | None = None
    symbols: list[str] | None = None


class JsonEnvelope(BaseModel):
    """Standard JSON envelope for all commands."""

    ok: bool
    command: str
    collector_version: str
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)


class DoctorCheck(BaseModel):
    """Single check result for doctor command."""

    name: str
    ok: bool
    detail: str = ""


class UnderlyingSnapshot(BaseModel):
    """Underlying quote snapshot."""

    symbol: str
    quoted_at: datetime
    last: float | None = None
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    volume: float | None = None
    day_open: float | None = None
    day_high: float | None = None
    day_low: float | None = None
    delay_seconds: int = 900
    raw: dict[str, Any] = Field(default_factory=dict)


class OptionSnapshot(BaseModel):
    """Option quote snapshot."""

    symbol: str
    expiry: date
    dte: int
    right: str  # 'C' or 'P'
    strike: float
    bid: float | None = None
    ask: float | None = None
    mid: float | None = None
    last: float | None = None
    volume: float | None = None
    open_interest: float | None = None
    delta: float | None = None
    gamma: float | None = None
    iv: float | None = None
    delta_bucket: float | None = None
    is_bucket_pick: bool = False
    delta_source: str = "unknown"
    quoted_at: datetime
    delay_seconds: int = 900
    raw: dict[str, Any] = Field(default_factory=dict)


class CollectResult(BaseModel):
    """Result of a collect operation."""

    session_date: date
    request_label: str | None
    status: str
    symbols_attempted: list[str]
    symbols_success: list[str]
    underlying_count: int
    option_count: int
    bucket_picks_count: int
    run_id: str | None = None
    request_started_at: datetime | None = None
    request_finished_at: datetime | None = None
    trigger_source: str | None = None
    trigger_id: str | None = None
    intended_at: datetime | None = None
