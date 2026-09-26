from __future__ import annotations

from datetime import UTC, datetime
from time import perf_counter
from typing import Any

import httpx

from app.audit.events import AuditEventStatus
from app.audit.service import duration_ms_since, log_external_api_call
from app.config import settings
from app.providers.news.base import NewsProviderError


class YahooFinanceNewsProvider:
    """Demo stock-news provider backed by Yahoo Finance public search results."""

    name = "yahoo_finance"
    endpoint_path = "/v1/finance/search"

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "configured": True,
            "provider": self.name,
            "base_url": settings.yahoo_finance_base_url,
            "supports_symbol_news": True,
            "supports_portfolio_news": True,
            "notes": [
                "Uses Yahoo Finance public search results for Phase 1 demo stock news.",
                "This is an unofficial demo source and should be replaced before production use.",
                "No Trading Journal API key is required for this demo provider.",
            ],
        }

    def get_symbol_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, Any]]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise NewsProviderError("Symbol is required for news lookup.")

        max_records = min(max(limit, 1), 25)
        payload = self._request(
            {
                "q": normalized_symbol,
                "quotesCount": 0,
                "newsCount": max_records,
                "enableFuzzyQuery": "false",
                "quotesQueryId": "tss_match_phrase_query",
                "multiQuoteQueryId": "multi_quote_single_token_query",
                "newsQueryId": "news_cie_vespa",
            }
        )
        news_items = payload.get("news", [])
        if not isinstance(news_items, list):
            raise NewsProviderError("Yahoo Finance returned an unexpected news response.")

        return [_normalize_article(normalized_symbol, item) for item in news_items[:max_records]]

    def get_portfolio_news(self, symbols: list[str], *, limit_per_symbol: int = 5) -> list[dict[str, Any]]:
        articles: list[dict[str, Any]] = []
        for symbol in sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()}):
            articles.extend(self.get_symbol_news(symbol, limit=limit_per_symbol))
        return articles

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        headers = {"User-Agent": "Mozilla/5.0 TradingJournalMCP/0.1"}
        try:
            with httpx.Client(
                base_url=settings.yahoo_finance_base_url,
                timeout=settings.news_timeout_seconds,
                headers=headers,
                follow_redirects=True,
            ) as client:
                response = client.get(self.endpoint_path, params=params)
                response.raise_for_status()
                payload = response.json()
        except httpx.HTTPStatusError as exc:
            log_external_api_call(
                provider=self.name,
                operation="news_search",
                endpoint=self.endpoint_path,
                status=AuditEventStatus.FAILURE,
                status_code=exc.response.status_code,
                duration_ms=duration_ms_since(started_at),
                message="Yahoo Finance news request failed with an HTTP status error.",
                request_metadata={"params": params},
                response_metadata={"status_code": exc.response.status_code},
            )
            if exc.response.status_code == 429:
                raise NewsProviderError("Yahoo Finance rate-limited the news request. Please try again later.") from exc
            raise NewsProviderError("Yahoo Finance news request failed.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            log_external_api_call(
                provider=self.name,
                operation="news_search",
                endpoint=self.endpoint_path,
                status=AuditEventStatus.FAILURE,
                duration_ms=duration_ms_since(started_at),
                message="Could not retrieve or parse Yahoo Finance news.",
                request_metadata={"params": params},
            )
            raise NewsProviderError("Could not retrieve stock news from Yahoo Finance.") from exc

        log_external_api_call(
            provider=self.name,
            operation="news_search",
            endpoint=self.endpoint_path,
            status=AuditEventStatus.SUCCESS,
            status_code=response.status_code,
            duration_ms=duration_ms_since(started_at),
            message="Yahoo Finance news request completed.",
            request_metadata={"params": params},
            response_metadata={
                "status_code": response.status_code,
                "article_count": len(payload.get("news", [])) if isinstance(payload.get("news"), list) else None,
            },
        )
        return payload


def _normalize_article(symbol: str, item: dict[str, Any]) -> dict[str, Any]:
    published_at = None
    publish_timestamp = item.get("providerPublishTime")
    if publish_timestamp is not None:
        try:
            published_at = datetime.fromtimestamp(int(publish_timestamp), UTC).isoformat()
        except (TypeError, ValueError, OSError):
            published_at = None

    thumbnail = item.get("thumbnail") or {}
    resolutions = thumbnail.get("resolutions") if isinstance(thumbnail, dict) else []
    image_url = None
    if isinstance(resolutions, list) and resolutions:
        first_resolution = resolutions[0]
        if isinstance(first_resolution, dict):
            image_url = first_resolution.get("url")

    return {
        "symbol": symbol,
        "headline": item.get("title") or "Untitled Yahoo Finance news item",
        "publisher": item.get("publisher") or "Yahoo Finance",
        "published_at": published_at,
        "summary": item.get("summary") or item.get("title") or "",
        "url": item.get("link"),
        "language": None,
        "source_country": None,
        "image_url": image_url,
        "related_tickers": item.get("relatedTickers") or [],
        "provider": "yahoo_finance",
    }
