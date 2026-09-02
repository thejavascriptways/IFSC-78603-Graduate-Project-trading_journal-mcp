from __future__ import annotations

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.market_data import create_market_data_mcp_server as create_market_data_mcp_server_impl
from app.services.market_data import (
    fetch_live_equity_snapshots,
    fetch_live_option_snapshots,
    get_market_data_capabilities,
)


def create_market_data_mcp_server() -> FastMCP:
    """Create the Market Data MCP server using the app's configured provider functions."""
    return create_market_data_mcp_server_impl(
        capabilities_reader=lambda: get_market_data_capabilities(),
        equity_snapshot_fetcher=lambda symbols: fetch_live_equity_snapshots(symbols),
        option_snapshot_fetcher=lambda symbols: fetch_live_option_snapshots(symbols),
    )


__all__ = [
    "create_market_data_mcp_server",
    "fetch_live_equity_snapshots",
    "fetch_live_option_snapshots",
    "get_market_data_capabilities",
]
