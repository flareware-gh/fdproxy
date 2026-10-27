"""Yahoo Finance feed implementation via yfinance."""

import time
from datetime import date, datetime

import pandas as pd
import yfinance as yf

from fdproxy.models import OptionSnapshot, UnderlyingSnapshot


class YahooFeed:
    """Yahoo Finance data feed."""

    def __init__(self, delay_seconds: int = 900, rate_limit_sleep: float = 0.3):
        """
        Initialize Yahoo feed.

        Args:
            delay_seconds: Assumed data delay (default 15 minutes)
            rate_limit_sleep: Sleep between requests to avoid rate limits
        """
        self.delay_seconds = delay_seconds
        self.rate_limit_sleep = rate_limit_sleep

    def fetch_underlying(self, symbol: str) -> UnderlyingSnapshot:
        """
        Fetch underlying quote for symbol.

        Args:
            symbol: Ticker symbol

        Returns:
            UnderlyingSnapshot with current quote
        """
        ticker = yf.Ticker(symbol)

        # Get fast_info for current data
        info = ticker.fast_info

        # Get recent history for OHLC
        hist = ticker.history(period="1d", interval="1m")

        quoted_at = datetime.utcnow()

        # Extract values
        last = getattr(info, "last_price", None)

        # Try to get bid/ask if available
        bid = None
        ask = None

        # Calculate mid from bid/ask if available, else use last
        mid = None
        if bid is not None and ask is not None:
            mid = (bid + ask) / 2
        elif last is not None:
            mid = last

        # Get day OHLC from history
        day_open = None
        day_high = None
        day_low = None

        if not hist.empty:
            day_open = hist["Open"].iloc[0] if len(hist) > 0 else None
            day_high = hist["High"].max()
            day_low = hist["Low"].min()

        # Volume
        volume = getattr(info, "last_volume", None)

        snapshot = UnderlyingSnapshot(
            symbol=symbol,
            quoted_at=quoted_at,
            last=last,
            bid=bid,
            ask=ask,
            mid=mid,
            volume=volume,
            day_open=day_open,
            day_high=day_high,
            day_low=day_low,
            delay_seconds=self.delay_seconds,
            raw={"source": "yfinance"},
        )

        # Rate limit
        time.sleep(self.rate_limit_sleep)

        return snapshot

    def fetch_chain_0dte(self, symbol: str, session_date: date) -> list[OptionSnapshot]:
        """
        Fetch 0DTE option chain.

        Args:
            symbol: Ticker symbol
            session_date: Target expiration date

        Returns:
            List of OptionSnapshot for 0DTE options
        """
        ticker = yf.Ticker(symbol)

        # Get available expiration dates
        expirations = ticker.options

        if not expirations:
            return []

        # Find matching expiration
        target_date_str = session_date.strftime("%Y-%m-%d")

        matching_exp = None
        for exp_str in expirations:
            if exp_str == target_date_str:
                matching_exp = exp_str
                break

        if not matching_exp:
            # No 0DTE available
            return []

        # Fetch option chain
        try:
            chain = ticker.option_chain(matching_exp)
        except Exception:
            return []

        quoted_at = datetime.utcnow()

        snapshots = []

        # Process calls
        if chain.calls is not None and not chain.calls.empty:
            snapshots.extend(
                self._parse_chain_df(
                    chain.calls,
                    symbol=symbol,
                    expiry=session_date,
                    right="C",
                    quoted_at=quoted_at,
                )
            )

        # Process puts
        if chain.puts is not None and not chain.puts.empty:
            snapshots.extend(
                self._parse_chain_df(
                    chain.puts,
                    symbol=symbol,
                    expiry=session_date,
                    right="P",
                    quoted_at=quoted_at,
                )
            )

        # Rate limit
        time.sleep(self.rate_limit_sleep)

        return snapshots

    def _parse_chain_df(
        self,
        df: pd.DataFrame,
        symbol: str,
        expiry: date,
        right: str,
        quoted_at: datetime,
    ) -> list[OptionSnapshot]:
        """Parse option chain DataFrame into snapshots."""
        snapshots = []

        for _, row in df.iterrows():
            strike = row.get("strike")
            if strike is None or pd.isna(strike):
                continue

            bid = row.get("bid")
            ask = row.get("ask")
            last = row.get("lastPrice")
            volume = row.get("volume")
            open_interest = row.get("openInterest")
            iv = row.get("impliedVolatility")

            # Calculate mid
            mid = None
            if bid is not None and ask is not None and not pd.isna(bid) and not pd.isna(ask):
                mid = (bid + ask) / 2
            elif last is not None and not pd.isna(last):
                mid = last

            # Get delta if available (Yahoo sometimes provides Greeks)
            delta = None
            delta_source = "unknown"

            # Yahoo doesn't typically provide delta in the standard chain
            # We'll compute it later with greeks.py

            snapshot = OptionSnapshot(
                symbol=symbol,
                expiry=expiry,
                dte=0,  # 0DTE by definition
                right=right,
                strike=float(strike),
                bid=self._clean_float(bid),
                ask=self._clean_float(ask),
                mid=self._clean_float(mid),
                last=self._clean_float(last),
                volume=self._clean_float(volume),
                open_interest=self._clean_float(open_interest),
                delta=delta,
                iv=self._clean_float(iv),
                delta_source=delta_source,
                quoted_at=quoted_at,
                delay_seconds=self.delay_seconds,
                raw={"source": "yfinance"},
            )

            snapshots.append(snapshot)

        return snapshots

    @staticmethod
    def _clean_float(value) -> float | None:
        """Clean float value, handling NaN and None."""
        if value is None:
            return None
        if pd.isna(value):
            return None
        try:
            return float(value)
        except (ValueError, TypeError):
            return None
