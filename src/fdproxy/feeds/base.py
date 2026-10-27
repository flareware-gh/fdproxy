"""Base protocol for market data feeds."""

from datetime import date
from typing import Protocol

from fdproxy.models import OptionSnapshot, UnderlyingSnapshot


class Feed(Protocol):
    """Protocol for market data feeds."""

    def fetch_underlying(self, symbol: str) -> UnderlyingSnapshot:
        """Fetch underlying quote."""
        ...

    def fetch_chain_0dte(self, symbol: str, session_date: date) -> list[OptionSnapshot]:
        """Fetch 0DTE option chain for given session date."""
        ...
