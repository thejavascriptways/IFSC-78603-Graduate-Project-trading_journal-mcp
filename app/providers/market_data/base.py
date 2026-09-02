from __future__ import annotations

from typing import Any, Protocol


class MarketDataProviderError(Exception):
    """Raised when a market-data provider cannot satisfy a request."""


class MarketDataProvider(Protocol):
    """Contract implemented by market-data providers such as Alpaca or IBKR."""

    name: str

    def get_capabilities(self) -> dict[str, Any]:
        """Return provider feed status, entitlements, and asset-class coverage."""

    def get_equity_snapshots(self, symbols: list[str]) -> dict[str, Any]:
        """Return stock/ETF quote snapshots for the requested symbols."""

    def get_option_snapshots(self, symbols: list[str]) -> dict[str, Any]:
        """Return option quote snapshots for the requested option symbols."""
