from __future__ import annotations

from typing import Any

from fastapi import FastAPI
from sqlalchemy.orm import Session

from app.config import settings
from app.providers.news import DemoNewsProvider, GdeltNewsProvider, NewsProvider, NewsProviderError, YahooFinanceNewsProvider
from app.services.mcp_host import MCPHostError, call_server_tool
from app.services.portfolio import list_closed_positions, list_positions


class NewsServiceError(Exception):
    """Domain-level error for news workflows."""


class NewsService:
    """Coordinates stock-news workflows without tying routes to one provider."""

    def __init__(self, provider: NewsProvider | None = None) -> None:
        self.provider = provider

    def get_capabilities(self) -> dict[str, Any]:
        if self.provider is None:
            return {
                "configured": False,
                "provider": None,
                "notes": ["No news provider is configured yet."],
            }
        return self.provider.get_capabilities()

    def get_symbol_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, Any]]:
        if self.provider is None:
            raise NewsServiceError("No news provider is configured yet.")
        try:
            return self.provider.get_symbol_news(symbol.strip().upper(), limit=limit)
        except NewsProviderError as exc:
            raise NewsServiceError(str(exc)) from exc

    def get_portfolio_news(self, symbols: list[str], *, limit_per_symbol: int = 5) -> list[dict[str, Any]]:
        if self.provider is None:
            raise NewsServiceError("No news provider is configured yet.")
        normalized_symbols = sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
        try:
            return self.provider.get_portfolio_news(normalized_symbols, limit_per_symbol=limit_per_symbol)
        except NewsProviderError as exc:
            raise NewsServiceError(str(exc)) from exc


def create_default_news_service() -> NewsService:
    provider_name = settings.news_provider.strip().lower()
    if provider_name == "demo":
        return NewsService(provider=DemoNewsProvider())
    if provider_name == "gdelt":
        return NewsService(provider=GdeltNewsProvider())
    return NewsService(provider=YahooFinanceNewsProvider())


def build_portfolio_news_symbols(session: Session) -> list[str]:
    symbols = {position.instrument.symbol for position in list_positions(session)}
    symbols.update(position["symbol"] for position in list_closed_positions(session))
    return sorted(symbol for symbol in symbols if symbol)


async def fetch_news_from_mcp(
    app: FastAPI,
    symbols: list[str],
    *,
    search_symbol: str | None = None,
    limit_per_symbol: int = 3,
) -> dict[str, Any]:
    capabilities_payload = await call_server_tool(app, "news", "get_news_capabilities", {})
    capabilities = _extract_structured_content(capabilities_payload)

    portfolio_articles: list[dict[str, Any]] = []
    normalized_symbols = sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
    normalized_search_symbol = (search_symbol or "").strip().upper()
    request_symbols = [normalized_search_symbol] if normalized_search_symbol else normalized_symbols
    combined_articles: list[dict[str, Any]] = []
    if request_symbols:
        portfolio_payload = await call_server_tool(
            app,
            "news",
            "get_portfolio_news",
            {"symbols": request_symbols, "limit_per_symbol": limit_per_symbol},
        )
        combined_articles = _extract_structured_result(portfolio_payload)
        if normalized_search_symbol:
            portfolio_articles = [
                article for article in combined_articles if article.get("symbol") == normalized_search_symbol
            ]
        else:
            portfolio_articles = [
                article for article in combined_articles if article.get("symbol") in set(normalized_symbols)
            ]

    search_articles: list[dict[str, Any]] = []
    if normalized_search_symbol:
        search_articles = portfolio_articles

    return {
        "capabilities": capabilities,
        "portfolio_symbols": normalized_symbols,
        "portfolio_articles": portfolio_articles,
        "search_symbol": normalized_search_symbol,
        "search_articles": search_articles,
    }


def _extract_structured_content(payload: dict[str, Any]) -> Any:
    if payload.get("isError"):
        raise NewsServiceError(_extract_error_text(payload))
    structured = payload.get("structuredContent")
    return structured if structured is not None else payload


def _extract_structured_result(payload: dict[str, Any]) -> list[dict[str, Any]]:
    structured = _extract_structured_content(payload)
    if isinstance(structured, dict) and isinstance(structured.get("result"), list):
        return structured["result"]
    if isinstance(structured, list):
        return structured
    return []


def _extract_error_text(payload: dict[str, Any]) -> str:
    content = payload.get("content")
    if isinstance(content, list):
        for item in content:
            if isinstance(item, dict) and item.get("text"):
                return str(item["text"])
    return "News MCP returned an error."
