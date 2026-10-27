"""Configuration constants and environment loading."""

import os
from pathlib import Path

from dotenv import load_dotenv

# Universe constants
SYMBOLS: list[str] = ["SPY", "QQQ", "SMH", "XLF", "XLE", "HYG"]

# Delta bucket targets
DELTA_BUCKETS: list[float] = [0.025, 0.05, 0.10, 0.20, 0.30]

# Feed identifier
FEED_NAME: str = "yahoo"

# Snapshot slots (ET)
SLOTS: list[str] = [
    "m0935",
    "m1030",
    "m1200",
    "m1400",
    "m1445",
    "t1500",
    "t1515",
    "t1530",
    "t1545",
    "t1550",
    "t1555",
    "close",
]


def load_env(env_file: str = ".env") -> None:
    """Load environment variables from dotenv file if it exists."""
    env_path = Path(env_file)
    if env_path.exists():
        load_dotenv(env_path)


def get_supabase_url() -> str | None:
    """Get Supabase URL from environment."""
    return os.getenv("SUPABASE_URL")


def get_supabase_service_role_key() -> str | None:
    """Get Supabase service role key from environment."""
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY")


def get_collector_version() -> str:
    """Get collector version."""
    from fdproxy import __version__

    return __version__
