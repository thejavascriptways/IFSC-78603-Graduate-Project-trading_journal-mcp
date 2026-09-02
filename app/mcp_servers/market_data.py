from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.security import local_transport_security_settings
from app.services.market_data import MarketDataError


CapabilitiesReader = Callable[[], dict[str, Any]]
SnapshotFetcher = Callable[[list[str]], dict[str, Any]]


def _normalize_error(exc: Exception) -> ValueError:
    return ValueError(str(exc))


def create_market_data_mcp_server(
    *,
    capabilities_reader: CapabilitiesReader,
    equity_snapshot_fetcher: SnapshotFetcher,
    option_snapshot_fetcher: SnapshotFetcher,
) -> FastMCP:
    market_data_mcp = FastMCP(
        "Trading Journal Market Data MCP",
        instructions=(
            "Market data MCP server for Trading Journal. "
            "Use it to fetch live stock, ETF, and option data from the configured external provider."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=local_transport_security_settings(),
    )

    @market_data_mcp.tool(name="get_market_data_capabilities", structured_output=True)
    def get_market_data_capabilities_tool() -> dict[str, Any]:
        """Describe the configured market-data provider, feeds, and asset-class limitations."""
        return capabilities_reader()

    @market_data_mcp.tool(name="get_equity_snapshots", structured_output=True)
    def get_equity_snapshots_tool(symbols: list[str]) -> dict[str, Any]:
        """Fetch live stock and ETF snapshots from the external market-data provider."""
        try:
            return equity_snapshot_fetcher(symbols)
        except MarketDataError as exc:
            raise _normalize_error(exc) from exc

    @market_data_mcp.tool(name="get_option_snapshots", structured_output=True)
    def get_option_snapshots_tool(symbols: list[str]) -> dict[str, Any]:
        """Fetch live option snapshots from the external market-data provider."""
        try:
            return option_snapshot_fetcher(symbols)
        except MarketDataError as exc:
            raise _normalize_error(exc) from exc

    @market_data_mcp.resource("market-data://capabilities", mime_type="application/json")
    def capabilities_resource() -> str:
        """Read current market-data provider capabilities as JSON."""
        return json.dumps(capabilities_reader(), indent=2)

    @market_data_mcp.prompt(
        name="market_data_health_check",
        description="Create a prompt for reviewing the configured market-data provider and feed limitations.",
    )
    def market_data_health_check_prompt(symbols: str = "SPY,QQQ") -> str:
        """Build a reusable prompt for market-data troubleshooting and feed review."""
        capabilities = capabilities_reader()
        return (
            "Review the current Trading Journal market-data setup.\n"
            f"Provider: {capabilities['provider']}.\n"
            f"Configured: {capabilities['configured']}.\n"
            f"Stock feed: {capabilities['stock_feed']}.\n"
            f"Option feed: {capabilities['option_feed']}.\n"
            f"Symbols to inspect: {symbols}.\n"
            "Explain the likely quote coverage, likely delays or entitlement gaps, and any asset classes "
            "that will not return live data."
        )

    return market_data_mcp
