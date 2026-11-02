from __future__ import annotations

from dataclasses import replace

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.db import session_scope
from app.models.entities import ExternalAPICallLog
from app.providers.market_data.yahoo import YahooFinanceMarketDataProvider
from app.services import market_data


def chart_payload(**overrides):
    meta = {
        "regularMarketPrice": 210,
        "regularMarketTime": 1792440001,
        "previousClose": 200,
        "currency": "USD",
        "exchangeName": "NMS",
    }
    meta.update(overrides)
    return {"chart": {"error": None, "result": [{"meta": meta}]}}


def yahoo_provider(handler):
    return YahooFinanceMarketDataProvider(transport=httpx.MockTransport(handler))


def test_yahoo_normalizes_symbols_prices_timestamps_and_audits():
    requested = []

    def handler(request):
        requested.append(request.url.path)
        assert request.url.params["range"] == "1d"
        assert "APCA-API-KEY-ID" not in request.headers
        return httpx.Response(200, json=chart_payload())

    result = yahoo_provider(handler).get_equity_snapshots([" aapl ", "AAPL", "BRK.B", "VOD.L"])
    assert requested == ["/v8/finance/chart/AAPL", "/v8/finance/chart/BRK-B", "/v8/finance/chart/VOD.L"]
    assert [q["symbol"] for q in result["quotes"]] == ["AAPL", "BRK.B", "VOD.L"]
    quote = result["quotes"][0]
    assert quote["mark_price"] == "210.000000"
    assert quote["change_percent"] == "5.0000"
    assert quote["as_of"] == "2026-10-19T20:00:01+00:00"
    assert quote["data_status"] == "SNAPSHOT"
    assert quote["bid_price"] is None and quote["ask_price"] is None
    assert result["missing_symbols"] == []
    with session_scope() as session:
        logs = session.scalars(select(ExternalAPICallLog)).all()
        assert len(logs) == 3
        assert all(log.provider == "yahoo_finance" and log.status.value == "SUCCESS" for log in logs)


@pytest.mark.parametrize("bad_price", [None, 0, -10, "NaN", "Infinity", True, "bad"])
def test_yahoo_never_returns_invalid_prices(bad_price):
    provider = yahoo_provider(lambda request: httpx.Response(200, json=chart_payload(regularMarketPrice=bad_price)))
    result = provider.get_equity_snapshots(["AAPL"])
    assert result["missing_symbols"] == ["AAPL"]
    assert result["quotes"][0]["mark_price"] is None
    with session_scope() as session:
        assert session.scalars(select(ExternalAPICallLog)).one().status.value == "FAILURE"


def test_yahoo_does_not_invent_quote_timestamp():
    provider = yahoo_provider(lambda request: httpx.Response(200, json=chart_payload(regularMarketTime=None)))
    quote = provider.get_equity_snapshots(["AAPL"])["quotes"][0]
    assert quote["found"] is False
    assert quote["as_of"] is None


def test_yahoo_network_failure_is_reported_and_audited():
    def handler(request):
        raise httpx.ConnectError("Offline", request=request)

    quote = yahoo_provider(handler).get_equity_snapshots(["AAPL"])["quotes"][0]
    assert quote["data_status"] == "ERROR"
    assert quote["mark_price"] is None
    with session_scope() as session:
        assert session.scalars(select(ExternalAPICallLog)).one().status.value == "FAILURE"


def test_yahoo_keeps_valid_quotes_when_another_symbol_is_missing_or_rate_limited():
    def handler(request):
        symbol = request.url.path.rsplit("/", 1)[-1]
        if symbol == "MISSING":
            return httpx.Response(404)
        if symbol == "LIMITED":
            return httpx.Response(429)
        return httpx.Response(200, json=chart_payload())

    result = yahoo_provider(handler).get_equity_snapshots(["AAPL", "MISSING", "LIMITED"])
    quotes = {q["symbol"]: q for q in result["quotes"]}
    assert quotes["AAPL"]["found"] is True
    assert quotes["MISSING"]["data_status"] == "NO_DATA"
    assert quotes["LIMITED"]["data_status"] == "ERROR"
    assert "rate-limited" in quotes["LIMITED"]["note"]


@pytest.mark.parametrize("response", [
    httpx.Response(200, text="not JSON"),
    httpx.Response(200, json={"chart": {"result": "bad"}}),
    httpx.Response(200, json={"chart": {"result": [{}]}}),
    httpx.Response(200, json={"chart": {"error": {"code": "Not Found"}}}),
    httpx.Response(403),
])
def test_yahoo_invalid_responses_are_visible_failures(response):
    quote = yahoo_provider(lambda request: response).get_equity_snapshots(["AAPL"])["quotes"][0]
    assert quote["found"] is False
    assert quote["note"]


def test_yahoo_options_keep_contract_and_report_missing_data():
    requested = []

    def handler(request):
        requested.append(request.url.path)
        return httpx.Response(404)

    result = yahoo_provider(handler).get_option_snapshots(["O:AAPL261023C00210000"])
    assert requested == ["/v8/finance/chart/AAPL261023C00210000"]
    assert result["quotes"][0]["asset_class"] == "OPTION"
    assert result["missing_symbols"] == ["O:AAPL261023C00210000"]


def test_explicit_yahoo_provider_works_through_real_mcp_and_refresh(app_instance, monkeypatch):
    monkeypatch.setattr(market_data, "settings", replace(market_data.settings, market_data_provider="yahoo"))
    provider = yahoo_provider(lambda request: httpx.Response(200, json=chart_payload()))
    monkeypatch.setattr("app.providers.market_data.yahoo.YahooFinanceMarketDataProvider", lambda: provider)
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        page = client.get("/settings/market-data")
        assert "yahoo_finance" in page.text and "No API key" in page.text
        accounts = client.get("/api/accounts").json()
        account_id = next(a["id"] for a in accounts if a["source"] == "MANUAL")
        trade = client.post("/api/trades", json={
            "account_id": account_id, "symbol": "AAPL", "asset_class": "STOCK",
            "trade_date": "2026-10-19", "side": "BUY", "quantity": "2", "price": "200",
            "fees": "0", "reason": "Test Yahoo MCP path", "currency": "USD",
        })
        assert trade.status_code == 201
        page = client.get("/market-data")
        assert page.status_code == 200 and "SNAPSHOT" in page.text
        assert "may be delayed" in page.text
        result = client.get("/api/market-data/live").json()
        assert result["capabilities"]["provider"] == "yahoo_finance"
        assert result["rows"][0]["live_unrealized_pnl"] == "20.000000"
        refreshed = client.post("/api/positions/refresh-market-data")
        assert refreshed.status_code == 200
        assert refreshed.json()["updated_position_count"] == 1
        assert float(client.get("/api/positions").json()[0]["market_price"]) == 210
        console = client.post("/api/mcp-console/call-tool", json={
            "server_id": "market_data", "tool_name": "get_equity_snapshots", "arguments": {"symbols": ["AAPL"]},
        })
        assert console.status_code == 200
        assert "yahoo_finance" in console.text


def test_currency_mismatch_does_not_calculate_or_apply_pnl():
    targets = [{"symbol": "VOD.L", "asset_class": "STOCK", "currency": "USD", "status": "OPEN", "quantity": "2", "cost_basis": "200"}]
    quote = {"found": True, "mark_price": "100", "currency": "GBp", "data_status": "SNAPSHOT"}
    rows = market_data.build_live_market_data_rows(targets, {("VOD.L", "STOCK"): quote}, {})
    assert rows[0]["market_data_status"] == "CURRENCY_MISMATCH"
    assert rows[0]["live_unrealized_pnl"] is None


def test_refresh_rejects_currency_mismatch(app_instance, monkeypatch):
    monkeypatch.setattr(market_data, "settings", replace(market_data.settings, market_data_provider="yahoo"))
    provider = yahoo_provider(lambda request: httpx.Response(200, json=chart_payload(currency="GBp")))
    monkeypatch.setattr("app.providers.market_data.yahoo.YahooFinanceMarketDataProvider", lambda: provider)
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        account_id = next(a["id"] for a in client.get("/api/accounts").json() if a["source"] == "MANUAL")
        assert client.post("/api/trades", json={
            "account_id": account_id, "symbol": "VOD.L", "asset_class": "STOCK", "currency": "USD",
            "trade_date": "2026-10-19", "side": "BUY", "quantity": "2", "price": "200",
            "reason": "Currency check",
        }).status_code == 201
        refresh = client.post("/api/positions/refresh-market-data").json()
        assert refresh["updated_position_count"] == 0
        assert refresh["missing_symbols"] == ["VOD.L"]


def test_provider_selection_is_explicit(monkeypatch):
    assert market_data.get_market_data_capabilities()["provider"] == "alpaca"
    monkeypatch.setattr(market_data, "settings", replace(market_data.settings, market_data_provider="yahoo"))
    assert market_data.get_market_data_capabilities()["provider"] == "yahoo_finance"
    monkeypatch.setattr(market_data, "settings", replace(market_data.settings, market_data_provider="invalid"))
    with pytest.raises(market_data.MarketDataError, match="Unknown"):
        market_data.get_market_data_capabilities()
