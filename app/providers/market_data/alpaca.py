from __future__ import annotations

from typing import Any

from app.services import market_data as market_data_service


class AlpacaMarketDataProvider:
    """Adapter for the existing Alpaca market-data implementation."""

    name = "alpaca"

    def get_capabilities(self) -> dict[str, Any]:
        return market_data_service._get_alpaca_capabilities()

    def get_equity_snapshots(self, symbols: list[str]) -> dict[str, Any]:
        return market_data_service._fetch_alpaca_equity_snapshots(symbols)

    def get_option_snapshots(self, symbols: list[str]) -> dict[str, Any]:
        return market_data_service._fetch_alpaca_option_snapshots(symbols)
