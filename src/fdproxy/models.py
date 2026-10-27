"""Data models for snapshots and JSON envelopes."""

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class JsonEnvelope(BaseModel):
    """Standard JSON envelope for all commands."""
    ok: bool
    command: str
    collector_version: str
    data: Dict[str, Any] = Field(default_factory=dict)
    errors: List[str] = Field(default_factory=list)


class DoctorCheck(BaseModel):
    """Single check result for doctor command."""
    name: str
    ok: bool
    detail: str = ""


class UnderlyingSnapshot(BaseModel):
    """Underlying quote snapshot."""
    symbol: str
    quoted_at: datetime
    last: Optional[float] = None
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    volume: Optional[float] = None
    day_open: Optional[float] = None
    day_high: Optional[float] = None
    day_low: Optional[float] = None
    delay_seconds: int = 900
    raw: Dict[str, Any] = Field(default_factory=dict)


class OptionSnapshot(BaseModel):
    """Option quote snapshot."""
    symbol: str
    expiry: date
    dte: int
    right: str  # 'C' or 'P'
    strike: float
    bid: Optional[float] = None
    ask: Optional[float] = None
    mid: Optional[float] = None
    last: Optional[float] = None
    volume: Optional[float] = None
    open_interest: Optional[float] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    iv: Optional[float] = None
    delta_bucket: Optional[float] = None
    is_bucket_pick: bool = False
    delta_source: str = "unknown"
    quoted_at: datetime
    delay_seconds: int = 900
    raw: Dict[str, Any] = Field(default_factory=dict)


class CollectResult(BaseModel):
    """Result of a collect operation."""
    session_date: date
    slot: str
    status: str
    symbols_attempted: List[str]
    symbols_success: List[str]
    underlying_count: int
    option_count: int
    bucket_picks_count: int
    run_id: Optional[str] = None
