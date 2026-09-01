from __future__ import annotations

from fastapi.testclient import TestClient

from app.services.market_data import fetch_live_equity_snapshots

def test_manual_trade_updates_position_and_requires_reason(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        accounts_response = client.get("/api/accounts")
        accounts = accounts_response.json()
        manual_account = next(account for account in accounts if account["name"] == "Manual Fidelity")

        trade_response = client.post(
            "/api/trades",
            json={
                "account_id": manual_account["id"],
                "symbol": "VTI",
                "description": "Vanguard Total Stock Market ETF",
                "asset_class": "ETF",
                "trade_date": "2026-05-21",
                "side": "BUY",
                "quantity": "10",
                "price": "250",
                "fees": "1",
                "reason": "Building a long-term core allocation.",
                "currency": "USD",
            },
        )
        assert trade_response.status_code == 201

        positions_response = client.get("/api/positions")
        positions = positions_response.json()
        assert len(positions) == 1
        assert positions[0]["account_name"] == "Manual Fidelity"
        assert positions[0]["symbol"] == "VTI"
        assert positions[0]["asset_class"] == "ETF"
        assert positions[0]["description"] == "Vanguard Total Stock Market ETF"
        assert positions[0]["quantity"] == "10.000000"
        assert positions[0]["average_cost"] == "250.100000"
        assert positions[0]["cost_basis"] == "2501.000000"

        missing_reason_response = client.post(
            "/api/trades",
            json={
                "account_id": manual_account["id"],
                "symbol": "VTI",
                "asset_class": "ETF",
                "trade_date": "2026-05-21",
                "side": "BUY",
                "quantity": "1",
                "price": "250",
                "fees": "0",
                "reason": "  ",
                "currency": "USD",
            },
        )
        assert missing_reason_response.status_code == 422

def test_opening_holding_import_seeds_position_and_supports_future_trades(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        accounts_response = client.get("/api/accounts")
        accounts = accounts_response.json()
        manual_account = next(account for account in accounts if account["name"] == "Manual Fidelity")

        import_response = client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "VOO",
                "description": "Vanguard S&P 500 ETF",
                "asset_class": "ETF",
                "opening_date": "2026-01-02",
                "quantity": "100",
                "average_cost": "500",
                "notes": "Imported opening Fidelity position.",
                "currency": "USD",
            },
        )
        assert import_response.status_code == 201
        assert import_response.json()["origin"] == "OPENING"

        duplicate_response = client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "VOO",
                "asset_class": "ETF",
                "opening_date": "2026-01-02",
                "quantity": "1",
                "average_cost": "500",
                "currency": "USD",
            },
        )
        assert duplicate_response.status_code == 400

        sell_response = client.post(
            "/api/trades",
            json={
                "account_id": manual_account["id"],
                "symbol": "VOO",
                "asset_class": "ETF",
                "trade_date": "2026-05-22",
                "side": "SELL",
                "quantity": "20",
                "price": "550",
                "fees": "2",
                "reason": "Trimming after a strong run.",
                "currency": "USD",
            },
        )
        assert sell_response.status_code == 201

        positions_response = client.get("/api/positions")
        positions = positions_response.json()
        assert len(positions) == 1
        assert positions[0]["account_name"] == "Manual Fidelity"
        assert positions[0]["symbol"] == "VOO"
        assert positions[0]["asset_class"] == "ETF"
        assert positions[0]["description"] == "Vanguard S&P 500 ETF"
        assert positions[0]["quantity"] == "80.000000"
        assert positions[0]["average_cost"] == "500.000000"
        assert positions[0]["cost_basis"] == "40000.000000"

        trades_response = client.get("/api/trades")
        trades = trades_response.json()
        sell_trade = next(trade for trade in trades if trade["origin"] == "MANUAL")
        assert sell_trade["realized_pnl"] == "998.000000"


def test_mark_price_updates_unrealized_pnl_and_full_close_moves_position_to_closed_history(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        accounts_response = client.get("/api/accounts")
        accounts = accounts_response.json()
        manual_account = next(account for account in accounts if account["name"] == "Manual Fidelity")

        import_response = client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "MSFT",
                "description": "Microsoft Corp.",
                "asset_class": "STOCK",
                "opening_date": "2026-04-01",
                "quantity": "10",
                "average_cost": "100",
                "currency": "USD",
            },
        )
        assert import_response.status_code == 201

        positions = client.get("/api/positions").json()
        position_id = positions[0]["id"]

        mark_response = client.post(
            f"/api/positions/{position_id}/mark",
            json={"market_price": "110"},
        )
        assert mark_response.status_code == 200
        mark_payload = mark_response.json()
        assert mark_payload["market_price"] == "110.000000"
        assert mark_payload["market_value"] == "1100.000000"
        assert mark_payload["unrealized_pnl"] == "100.000000"

        close_response = client.post(
            "/api/trades",
            json={
                "account_id": manual_account["id"],
                "symbol": "MSFT",
                "asset_class": "STOCK",
                "trade_date": "2026-05-23",
                "side": "SELL",
                "quantity": "10",
                "price": "120",
                "fees": "0",
                "reason": "Closing the full position.",
                "currency": "USD",
            },
        )
        assert close_response.status_code == 201
        assert close_response.json()["realized_pnl"] == "200.000000"

        open_positions = client.get("/api/positions").json()
        assert open_positions == []

        closed_positions = client.get("/api/closed-positions").json()
        assert len(closed_positions) == 1
        assert closed_positions[0]["symbol"] == "MSFT"
        assert closed_positions[0]["realized_pnl_total"] == "200.000000"
        assert closed_positions[0]["closed_on"] == "2026-05-23"

        summary = client.get("/api/portfolio-summary").json()
        assert summary["open_position_count"] == 0
        assert summary["closed_position_count"] == 1
        assert summary["realized_pnl_total"] == "200.000000"
        assert summary["unrealized_pnl_total"] == "0"


def test_dashboard_summary_reports_overall_account_and_account_asset_class_pnl(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        manual_account = next(
            account
            for account in client.get("/api/accounts").json()
            if account["name"] == "Manual Fidelity"
        )

        client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "VOO",
                "description": "Vanguard S&P 500 ETF",
                "asset_class": "ETF",
                "opening_date": "2026-01-02",
                "quantity": "10",
                "average_cost": "100",
                "currency": "USD",
            },
        )
        client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "UST10Y",
                "description": "US Treasury 10Y",
                "asset_class": "BOND",
                "opening_date": "2026-01-02",
                "quantity": "20",
                "average_cost": "50",
                "currency": "USD",
            },
        )

        positions = client.get("/api/positions").json()
        voo_position = next(position for position in positions if position["symbol"] == "VOO")
        bond_position = next(position for position in positions if position["symbol"] == "UST10Y")

        client.post(f"/api/positions/{voo_position['id']}/mark", json={"market_price": "110"})
        client.post(f"/api/positions/{bond_position['id']}/mark", json={"market_price": "45"})
        client.post(
            "/api/trades",
            json={
                "account_id": manual_account["id"],
                "symbol": "VOO",
                "asset_class": "ETF",
                "trade_date": "2026-05-23",
                "side": "SELL",
                "quantity": "4",
                "price": "130",
                "fees": "0",
                "reason": "Taking some profits.",
                "currency": "USD",
            },
        )

        summary = client.get("/api/portfolio-summary").json()

        overall = summary["performance_overall"]
        assert overall["open_cost_basis"] == "1600.000000"
        assert overall["market_value"] == "1680.000000"
        assert overall["unrealized_pnl"] == "80.000000"
        assert overall["unrealized_pct"] == "5.0000"
        assert overall["realized_cost_basis"] == "400.000000"
        assert overall["realized_pnl"] == "120.000000"
        assert overall["realized_pct"] == "30.0000"
        assert overall["total_basis"] == "2000.000000"
        assert overall["total_pnl"] == "200.000000"
        assert overall["total_pct"] == "10.0000"

        by_account = summary["performance_by_account"]
        assert len(by_account) == 1
        assert by_account[0]["account_name"] == "Manual Fidelity"
        assert by_account[0]["total_pnl"] == "200.000000"

        by_account_asset_class = summary["performance_by_account_asset_class"]
        assert len(by_account_asset_class) == 2
        bond_row = next(row for row in by_account_asset_class if row["asset_class"] == "BOND")
        etf_row = next(row for row in by_account_asset_class if row["asset_class"] == "ETF")
        assert bond_row["total_pnl"] == "-100.000000"
        assert bond_row["total_pct"] == "-10.0000"
        assert etf_row["total_pnl"] == "300.000000"
        assert etf_row["total_pct"] == "30.0000"


def test_live_market_data_page_and_refresh_via_mcp_updates_open_positions(app_instance, monkeypatch):
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
                    "found": True,
                    "provider": "alpaca",
                    "feed": "iex",
                    "mark_price": "125.500000" if symbol == "AAPL" else "410.000000",
                    "last_trade_price": "125.500000" if symbol == "AAPL" else "410.000000",
                    "bid_price": "125.450000" if symbol == "AAPL" else "409.900000",
                    "ask_price": "125.550000" if symbol == "AAPL" else "410.100000",
                    "change_percent": "1.2500",
                    "as_of": "2026-05-24T14:30:00Z",
                    "note": None,
                }
                for symbol in symbols
            ],
            "missing_symbols": [],
        },
    )
    monkeypatch.setattr(
        "app.market_data_mcp.fetch_live_option_snapshots",
        lambda symbols: {
            "provider": "alpaca",
            "asset_class": "OPTION",
            "feed": "indicative",
            "quotes": [],
            "missing_symbols": [],
        },
    )

    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        manual_account = next(
            account
            for account in client.get("/api/accounts").json()
            if account["name"] == "Manual Fidelity"
        )

        import_response = client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "AAPL",
                "description": "Apple Inc.",
                "asset_class": "STOCK",
                "opening_date": "2026-05-01",
                "quantity": "5",
                "average_cost": "100",
                "currency": "USD",
            },
        )
        assert import_response.status_code == 201

        closed_import_response = client.post(
            "/api/opening-holdings",
            json={
                "account_id": manual_account["id"],
                "symbol": "MSFT",
                "description": "Microsoft Corp.",
                "asset_class": "STOCK",
                "opening_date": "2026-04-01",
                "quantity": "2",
                "average_cost": "400",
                "currency": "USD",
            },
        )
        assert closed_import_response.status_code == 201

        close_response = client.post(
            "/api/trades",
            json={
                "account_id": manual_account["id"],
                "symbol": "MSFT",
                "asset_class": "STOCK",
                "trade_date": "2026-05-23",
                "side": "SELL",
                "quantity": "2",
                "price": "420",
                "fees": "0",
                "reason": "Closed for the market-data page test.",
                "currency": "USD",
            },
        )
        assert close_response.status_code == 201

        market_data_page = client.get("/market-data")
        assert market_data_page.status_code == 200
        assert "AAPL" in market_data_page.text
        assert "MSFT" in market_data_page.text
        assert "Live Market Data" in market_data_page.text

        refresh_response = client.post("/api/positions/refresh-market-data")
        assert refresh_response.status_code == 200

        refresh_payload = refresh_response.json()
        assert refresh_payload["updated_position_count"] == 1
        assert refresh_payload["updated_symbols"] == ["AAPL"]
        assert refresh_payload["missing_symbols"] == []
        assert refresh_payload["capabilities"]["provider"] == "alpaca"

        positions = client.get("/api/positions").json()
        assert len(positions) == 1
        assert positions[0]["market_price"] == "125.500000"
        assert positions[0]["market_value"] == "627.500000"
        assert positions[0]["unrealized_pnl"] == "127.500000"


def test_fetch_live_equity_snapshots_accepts_top_level_alpaca_payload(monkeypatch):
    class DummyClient:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    class DummyResponse:
        def json(self):
            return {
                "TSLA": {
                    "dailyBar": {"c": 425.95, "t": "2026-05-22T04:00:00Z"},
                    "latestQuote": {
                        "bp": 409.91,
                        "ap": 426.15,
                        "t": "2026-05-22T20:00:01.070257351Z",
                    },
                    "latestTrade": {
                        "p": 425.04,
                        "t": "2026-05-22T20:53:25.766292216Z",
                    },
                    "prevDailyBar": {"c": 417.785},
                }
            }

    monkeypatch.setattr(
        "app.services.market_data.get_market_data_capabilities",
        lambda: {
            "provider": "alpaca",
            "configured": True,
            "stock_feed": "iex",
            "option_feed": "indicative",
            "notes": [],
        },
    )
    monkeypatch.setattr("app.services.market_data._alpaca_client", lambda: DummyClient())
    monkeypatch.setattr("app.services.market_data._request_alpaca", lambda client, path, params: DummyResponse())

    payload = fetch_live_equity_snapshots(["TSLA"])

    assert payload["missing_symbols"] == []
    assert payload["quotes"][0]["symbol"] == "TSLA"
    assert payload["quotes"][0]["found"] is True
    assert payload["quotes"][0]["mark_price"] == "425.040000"
