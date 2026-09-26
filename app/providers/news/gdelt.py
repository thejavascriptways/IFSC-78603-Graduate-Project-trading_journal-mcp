from __future__ import annotations

from time import perf_counter
from typing import Any

import httpx

from app.audit.events import AuditEventStatus
from app.audit.service import duration_ms_since, log_external_api_call
from app.config import settings
from app.providers.news.base import NewsProviderError


class GdeltNewsProvider:
    """Global stock-news provider backed by the public GDELT DOC endpoint."""

    name = "gdelt"
    endpoint_path = "/api/v2/doc/doc"

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "configured": True,
            "provider": self.name,
            "base_url": settings.gdelt_doc_base_url,
            "supports_symbol_news": True,
            "supports_portfolio_news": True,
            "default_timespan": settings.gdelt_news_timespan,
            "notes": [
                "Uses GDELT DOC API article search for global news coverage.",
                "No Trading Journal API key is required for this public endpoint.",
                "Results are news-search matches, not financial advice or broker research.",
            ],
        }

    def get_symbol_news(self, symbol: str, *, limit: int = 10) -> list[dict[str, Any]]:
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise NewsProviderError("Symbol is required for news lookup.")

        max_records = min(max(limit, 1), 25)
        params = {
            "query": _build_symbol_query(normalized_symbol),
            "mode": "ArtList",
            "format": "json",
            "sort": "datedesc",
            "timespan": settings.gdelt_news_timespan,
            "maxrecords": max_records,
        }
        payload = self._request(params)
        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise NewsProviderError("GDELT returned an unexpected news response.")

        return [_normalize_article(normalized_symbol, article) for article in articles[:max_records]]

    def get_portfolio_news(self, symbols: list[str], *, limit_per_symbol: int = 5) -> list[dict[str, Any]]:
        normalized_symbols = sorted({symbol.strip().upper() for symbol in symbols if symbol.strip()})
        if not normalized_symbols:
            return []

        max_records = min(max(len(normalized_symbols) * max(limit_per_symbol, 1), 1), 50)
        params = {
            "query": _build_portfolio_query(normalized_symbols),
            "mode": "ArtList",
            "format": "json",
            "sort": "datedesc",
            "timespan": settings.gdelt_news_timespan,
            "maxrecords": max_records,
        }
        payload = self._request(params)
        articles = payload.get("articles", [])
        if not isinstance(articles, list):
            raise NewsProviderError("GDELT returned an unexpected news response.")

        grouped_counts = {symbol: 0 for symbol in normalized_symbols}
        normalized_articles: list[dict[str, Any]] = []
        for article in articles:
            for symbol in _matched_symbols(article, normalized_symbols):
                if grouped_counts[symbol] >= limit_per_symbol:
                    continue
                normalized_articles.append(_normalize_article(symbol, article))
                grouped_counts[symbol] += 1
        return normalized_articles

    def _request(self, params: dict[str, Any]) -> dict[str, Any]:
        started_at = perf_counter()
        try:
            with httpx.Client(base_url=settings.gdelt_doc_base_url, timeout=settings.news_timeout_seconds) as client:
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
                message="GDELT news request failed with an HTTP status error.",
                request_metadata={"params": params},
                response_metadata={"status_code": exc.response.status_code},
            )
            if exc.response.status_code == 429:
                raise NewsProviderError("GDELT rate-limited the news request. Please try again later.") from exc
            raise NewsProviderError("GDELT news request failed.") from exc
        except (httpx.HTTPError, ValueError) as exc:
            log_external_api_call(
                provider=self.name,
                operation="news_search",
                endpoint=self.endpoint_path,
                status=AuditEventStatus.FAILURE,
                duration_ms=duration_ms_since(started_at),
                message="Could not retrieve or parse GDELT news.",
                request_metadata={"params": params},
            )
            raise NewsProviderError("Could not retrieve global stock news from GDELT.") from exc

        log_external_api_call(
            provider=self.name,
            operation="news_search",
            endpoint=self.endpoint_path,
            status=AuditEventStatus.SUCCESS,
            status_code=response.status_code,
            duration_ms=duration_ms_since(started_at),
            message="GDELT news request completed.",
            request_metadata={"params": params},
            response_metadata={
                "status_code": response.status_code,
                "article_count": len(payload.get("articles", [])) if isinstance(payload.get("articles"), list) else None,
            },
        )
        return payload


def _build_symbol_query(symbol: str) -> str:
    # Pair the ticker with market terms to reduce unrelated short-symbol matches.
    return f'"{symbol}" (stock OR shares OR earnings OR investors OR market)'


def _build_portfolio_query(symbols: list[str]) -> str:
    symbol_query = " OR ".join(f'"{symbol}"' for symbol in symbols)
    return f"({symbol_query}) (stock OR shares OR earnings OR investors OR market)"


def _matched_symbols(article: dict[str, Any], symbols: list[str]) -> list[str]:
    searchable_text = " ".join(
        str(article.get(key) or "")
        for key in ("title", "snippet", "url", "domain")
    ).upper()
    matched = [symbol for symbol in symbols if symbol in searchable_text]
    return matched or symbols[:1]


def _normalize_article(symbol: str, article: dict[str, Any]) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "headline": article.get("title") or "Untitled news item",
        "publisher": article.get("domain") or article.get("sourceDomain") or "Unknown source",
        "published_at": article.get("seendate"),
        "summary": article.get("snippet") or article.get("title") or "",
        "url": article.get("url"),
        "language": article.get("language"),
        "source_country": article.get("sourcecountry") or article.get("sourceCountry"),
        "image_url": article.get("socialimage"),
        "provider": "gdelt",
    }
