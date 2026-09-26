from __future__ import annotations

import asyncio

import httpx
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


def _fake_articles(symbol: str, *, limit: int = 10):
    return [
        {
            "symbol": symbol,
            "headline": f"{symbol} Yahoo Finance news item",
            "publisher": "Yahoo Finance Test News",
            "published_at": "2026-09-26T12:00:00Z",
            "summary": "A mocked Yahoo Finance news item for Trading Journal tests.",
            "url": "https://example.com/news",
            "language": "English",
            "source_country": "US",
            "provider": "yahoo_finance",
        }
        for _ in range(limit)
    ]


def test_news_mcp_returns_global_stock_news(app_instance, monkeypatch):
    monkeypatch.setattr(
        "app.providers.news.yahoo.YahooFinanceNewsProvider.get_symbol_news",
        lambda self, symbol, limit=10: _fake_articles(symbol, limit=limit),
    )

    with TestClient(app_instance, base_url="http://127.0.0.1:8000"):

        async def scenario():
            transport = httpx.ASGITransport(app=app_instance)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://127.0.0.1:8000",
                follow_redirects=True,
            ) as http_client:
                async with streamable_http_client(
                    "http://127.0.0.1:8000/news-mcp/",
                    http_client=http_client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        capabilities = await session.call_tool("get_news_capabilities")
                        capabilities_payload = capabilities.model_dump(mode="json")["structuredContent"]
                        assert capabilities_payload["provider"] == "yahoo_finance"

                        news = await session.call_tool("get_symbol_news", {"symbol": "AAPL", "limit": 2})
                        news_payload = news.model_dump(mode="json")["structuredContent"]["result"]
                        assert len(news_payload) == 2
                        assert news_payload[0]["symbol"] == "AAPL"
                        assert news_payload[0]["headline"] == "AAPL Yahoo Finance news item"

        asyncio.run(scenario())


def test_news_page_shows_portfolio_and_search_news(app_instance, monkeypatch):
    monkeypatch.setattr(
        "app.providers.news.yahoo.YahooFinanceNewsProvider.get_symbol_news",
        lambda self, symbol, limit=10: _fake_articles(symbol, limit=limit),
    )
    monkeypatch.setattr(
        "app.providers.news.yahoo.YahooFinanceNewsProvider.get_portfolio_news",
        lambda self, symbols, limit_per_symbol=5: [
            article
            for symbol in symbols
            for article in _fake_articles(symbol, limit=limit_per_symbol)
        ],
    )

    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        accounts_response = client.get("/api/accounts")
        manual_account = next(account for account in accounts_response.json() if account["name"] == "Manual Fidelity")
        client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "MSFT",
                "description": "Microsoft Corporation",
                "asset_class": "STOCK",
                "opening_date": "2026-09-01",
                "quantity": "2",
                "average_cost": "400",
                "currency": "USD",
            },
        )
        client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "AAPL",
                "description": "Apple Inc.",
                "asset_class": "STOCK",
                "opening_date": "2026-09-01",
                "quantity": "1",
                "average_cost": "200",
                "currency": "USD",
            },
        )

        response = client.get("/news", params={"symbol": "AAPL"})

    assert response.status_code == 200
    assert "Stock News From Around The World" in response.text
    assert "AAPL Yahoo Finance news item" in response.text
    assert "MSFT Yahoo Finance news item" not in response.text
    assert 'href="/news?symbol=MSFT"' in response.text
    assert 'href="/news?symbol=AAPL"' in response.text
    assert "News MCP" in response.text
