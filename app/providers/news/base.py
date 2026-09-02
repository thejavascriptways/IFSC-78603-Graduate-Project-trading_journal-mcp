from __future__ import annotations

from typing import Any, Protocol


class NewsProviderError(Exception):
    """Raised when a news provider cannot satisfy a request."""


class NewsProvider(Protocol):
    """Contract implemented by stock-news providers."""

    name: str

    def get_capabilities(self) -> dict[str, Any]:
        """Return provider status, limits, and supported news features."""

    def get_symbol_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent news articles for one symbol."""

    def get_portfolio_news(self, symbols: list[str], *, limit_per_symbol: int = 5) -> list[dict[str, Any]]:
        """Return recent news articles for a list of portfolio symbols."""
