from __future__ import annotations

from typing import Any

from app.providers.news import NewsProvider, NewsProviderError


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
