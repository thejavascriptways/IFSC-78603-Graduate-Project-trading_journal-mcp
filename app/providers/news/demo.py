from __future__ import annotations

from datetime import UTC, datetime
from typing import Any


class DemoNewsProvider:
    """Deterministic news provider for local demos before a real API is selected."""

    name = "demo"

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "configured": True,
            "provider": self.name,
            "supports_symbol_news": True,
            "supports_portfolio_news": True,
            "notes": ["Demo news provider returns synthetic articles for workflow testing."],
        }

    def get_symbol_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, Any]]:
        normalized_symbol = symbol.strip().upper()
        return [
            {
                "symbol": normalized_symbol,
                "headline": f"{normalized_symbol} demo news item {index + 1}",
                "publisher": "Trading Journal Demo News",
                "published_at": datetime.now(UTC).isoformat(),
                "summary": "Synthetic article used to test the future News MCP workflow.",
                "url": None,
                "provider": self.name,
            }
            for index in range(max(limit, 0))
        ]

    def get_portfolio_news(self, symbols: list[str], *, limit_per_symbol: int = 5) -> list[dict[str, Any]]:
        articles: list[dict[str, Any]] = []
        for symbol in symbols:
            articles.extend(self.get_symbol_news(symbol, limit=limit_per_symbol))
        return articles
