"""MCP server factories for Trading Journal domains."""

from app.mcp_servers.broker import create_broker_mcp_server
from app.mcp_servers.market_data import create_market_data_mcp_server
from app.mcp_servers.news import create_news_mcp_server
from app.mcp_servers.portfolio import create_mcp_server
from app.mcp_servers.trading import create_trading_mcp_server

__all__ = [
    "create_broker_mcp_server",
    "create_market_data_mcp_server",
    "create_mcp_server",
    "create_news_mcp_server",
    "create_trading_mcp_server",
]
