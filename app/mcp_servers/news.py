from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.security import local_transport_security_settings
from app.providers.news import DemoNewsProvider
from app.services.news import NewsService, NewsServiceError


def _normalize_error(exc: Exception) -> ValueError:
    return ValueError(str(exc))


def create_news_mcp_server(news_service: NewsService | None = None) -> FastMCP:
    service = news_service or NewsService(provider=DemoNewsProvider())
    news_mcp = FastMCP(
        "Trading Journal News MCP",
        instructions=(
            "News MCP server for Trading Journal. "
            "Use it to inspect provider capabilities and retrieve symbol or portfolio news."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=local_transport_security_settings(),
    )

    @news_mcp.tool(name="get_news_capabilities", structured_output=True)
    def get_news_capabilities_tool() -> dict[str, Any]:
        """Describe the configured news provider and supported news workflows."""
        return service.get_capabilities()

    @news_mcp.tool(name="get_symbol_news", structured_output=True)
    def get_symbol_news_tool(symbol: str, limit: int = 5) -> list[dict[str, Any]]:
        """Return recent news for one symbol."""
        try:
            return service.get_symbol_news(symbol, limit=limit)
        except NewsServiceError as exc:
            raise _normalize_error(exc) from exc

    @news_mcp.tool(name="get_portfolio_news", structured_output=True)
    def get_portfolio_news_tool(symbols: list[str], limit_per_symbol: int = 3) -> list[dict[str, Any]]:
        """Return recent news for a portfolio symbol list."""
        try:
            return service.get_portfolio_news(symbols, limit_per_symbol=limit_per_symbol)
        except NewsServiceError as exc:
            raise _normalize_error(exc) from exc

    @news_mcp.resource("news://capabilities", mime_type="application/json")
    def news_capabilities_resource() -> str:
        """Read current news provider capabilities as JSON."""
        return json.dumps(service.get_capabilities(), indent=2)

    @news_mcp.prompt(
        name="portfolio_news_review",
        description="Create a prompt for reviewing portfolio news and possible position follow-up.",
    )
    def portfolio_news_review_prompt(symbols: str = "AAPL,MSFT") -> str:
        """Build a reusable prompt for reviewing portfolio-related news."""
        return (
            "Review recent news for these Trading Journal symbols: "
            f"{symbols}. Identify which positions may need follow-up, which headlines are likely noise, "
            "and what journal questions the investor should answer before changing a position."
        )

    return news_mcp
