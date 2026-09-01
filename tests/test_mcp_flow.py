from __future__ import annotations

import asyncio
import json

import httpx
from fastapi.testclient import TestClient
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

def test_mcp_server_exposes_tools_resources_and_portfolio_state(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        accounts_response = client.get("/api/accounts")
        accounts = accounts_response.json()
        manual_account = next(account for account in accounts if account["name"] == "Manual Fidelity")

        import_response = client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "QQQ",
                "description": "Invesco QQQ Trust",
                "asset_class": "ETF",
                "opening_date": "2026-03-03",
                "quantity": "12",
                "average_cost": "480",
                "currency": "USD",
            },
        )
        assert import_response.status_code == 201

        async def scenario():
            transport = httpx.ASGITransport(app=app_instance)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://127.0.0.1:8000",
                follow_redirects=True,
            ) as http_client:
                async with streamable_http_client(
                    "http://127.0.0.1:8000/mcp/",
                    http_client=http_client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        tools = await session.list_tools()
                        tool_names = {tool.name for tool in tools.tools}
                        assert {
                            "get_portfolio_summary",
                            "list_accounts",
                            "list_positions",
                            "list_trades",
                            "add_opening_holding",
                            "add_manual_trade",
                        }.issubset(tool_names)

                        resources = await session.list_resources()
                        resource_uris = {str(resource.uri) for resource in resources.resources}
                        assert {"portfolio://summary", "portfolio://positions"}.issubset(resource_uris)

                        summary = await session.call_tool("get_portfolio_summary")
                        summary_payload = summary.model_dump(mode="json")
                        assert summary_payload["structuredContent"]["open_position_count"] == 1

                        positions = await session.call_tool("list_positions", {"symbol": "QQQ"})
                        positions_payload = positions.model_dump(mode="json")
                        assert positions_payload["structuredContent"]["result"][0]["symbol"] == "QQQ"

                        add_trade = await session.call_tool(
                            "add_manual_trade",
                            {
                                "account_id": manual_account["id"],
                                "symbol": "QQQ",
                                "asset_class": "ETF",
                                "trade_date": "2026-05-22",
                                "side": "SELL",
                                "quantity": "2",
                                "price": "510",
                                "fees": "1",
                                "reason": "Taking a small profit into strength.",
                                "currency": "USD",
                            },
                        )
                        add_trade_payload = add_trade.model_dump(mode="json")
                        assert add_trade_payload["structuredContent"]["origin"] == "MANUAL"

                        resource = await session.read_resource("portfolio://summary")
                        resource_payload = resource.model_dump(mode="json")
                        text = resource_payload["contents"][0]["text"]
                        summary_from_resource = json.loads(text)
                        assert summary_from_resource["open_position_count"] == 1

        asyncio.run(scenario())


def test_market_data_mcp_server_exposes_live_tools_and_capabilities(app_instance, monkeypatch):
    monkeypatch.setattr(
        "app.market_data_mcp.get_market_data_capabilities",
        lambda: {
            "provider": "alpaca",
            "configured": True,
            "stock_feed": "iex",
            "option_feed": "indicative",
            "notes": ["Stocks and ETFs are fetched from Alpaca Market Data."],
        },
    )
    monkeypatch.setattr(
        "app.market_data_mcp.fetch_live_equity_snapshots",
        lambda symbols: {
            "provider": "alpaca",
            "asset_class": "STOCK",
            "feed": "iex",
            "quotes": [
                {
                    "symbol": symbol,
                    "asset_class": "STOCK",
                    "found": symbol == "NVDA",
                    "provider": "alpaca",
                    "feed": "iex",
                    "mark_price": "1180.250000" if symbol == "NVDA" else None,
                    "last_trade_price": "1180.250000" if symbol == "NVDA" else None,
                    "bid_price": "1180.000000" if symbol == "NVDA" else None,
                    "ask_price": "1180.500000" if symbol == "NVDA" else None,
                    "change_percent": "2.5000" if symbol == "NVDA" else None,
                    "as_of": "2026-05-24T14:30:00Z" if symbol == "NVDA" else None,
                    "note": None if symbol == "NVDA" else "No market data was returned for this symbol.",
                }
                for symbol in symbols
            ],
            "missing_symbols": [symbol for symbol in symbols if symbol != "NVDA"],
        },
    )
    monkeypatch.setattr(
        "app.market_data_mcp.fetch_live_option_snapshots",
        lambda symbols: {
            "provider": "alpaca",
            "asset_class": "OPTION",
            "feed": "indicative",
            "quotes": [],
            "missing_symbols": symbols,
        },
    )

    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:

        async def scenario():
            transport = httpx.ASGITransport(app=app_instance)
            async with httpx.AsyncClient(
                transport=transport,
                base_url="http://127.0.0.1:8000",
                follow_redirects=True,
            ) as http_client:
                async with streamable_http_client(
                    "http://127.0.0.1:8000/market-data-mcp/",
                    http_client=http_client,
                ) as (read, write, _):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        tools = await session.list_tools()
                        tool_names = {tool.name for tool in tools.tools}
                        assert {
                            "get_market_data_capabilities",
                            "get_equity_snapshots",
                            "get_option_snapshots",
                        }.issubset(tool_names)

                        resources = await session.list_resources()
                        resource_uris = {str(resource.uri) for resource in resources.resources}
                        assert "market-data://capabilities" in resource_uris

                        capabilities = await session.call_tool("get_market_data_capabilities")
                        capabilities_payload = capabilities.model_dump(mode="json")
                        assert capabilities_payload["structuredContent"]["provider"] == "alpaca"

                        batch_quotes = await session.call_tool("get_equity_snapshots", {"symbols": ["NVDA", "AMD"]})
                        batch_quotes_payload = batch_quotes.model_dump(mode="json")
                        assert batch_quotes_payload["structuredContent"]["missing_symbols"] == ["AMD"]
                        assert {
                            quote["symbol"]
                            for quote in batch_quotes_payload["structuredContent"]["quotes"]
                        } == {"AMD", "NVDA"}
                        assert sum(
                            1
                            for quote in batch_quotes_payload["structuredContent"]["quotes"]
                            if quote["found"] is True
                        ) == 1

                        resource = await session.read_resource("market-data://capabilities")
                        resource_payload = resource.model_dump(mode="json")
                        text = resource_payload["contents"][0]["text"]
                        capabilities_from_resource = json.loads(text)
                        assert capabilities_from_resource["provider"] == "alpaca"

        asyncio.run(scenario())
