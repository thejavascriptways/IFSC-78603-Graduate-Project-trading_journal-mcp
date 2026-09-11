from __future__ import annotations

import json

from fastapi.testclient import TestClient

from app.services.market_data import get_market_data_capabilities
from app.services.market_data_settings import get_alpaca_market_data_settings


def test_alpaca_settings_page_saves_masks_and_clears_credentials(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        page_response = client.get("/settings/market-data/alpaca")
        assert page_response.status_code == 200
        assert "Alpaca Settings" in page_response.text
        assert "Configured" in page_response.text

        save_response = client.post(
            "/settings/market-data/alpaca",
            data={
                "api_key_id": "PKTEST123456",
                "api_secret_key": "SUPER-SECRET-VALUE",
                "stock_feed": "iex",
                "option_feed": "indicative",
                "base_url": "https://data.alpaca.markets",
            },
        )
        assert save_response.status_code == 200
        assert "Alpaca settings saved" in save_response.text
        assert "PKTE...3456" in save_response.text
        assert "SUPER-SECRET-VALUE" not in save_response.text

        saved_settings = get_alpaca_market_data_settings()
        assert saved_settings.configured is True
        assert saved_settings.api_key_id == "PKTEST123456"
        assert saved_settings.api_secret_key == "SUPER-SECRET-VALUE"
        assert saved_settings.storage_path.exists()

        saved_payload = json.loads(saved_settings.storage_path.read_text(encoding="utf-8"))
        assert saved_payload["api_key_id"] == "PKTEST123456"
        assert saved_payload["api_secret_key"] == "SUPER-SECRET-VALUE"

        capabilities = get_market_data_capabilities()
        assert capabilities["configured"] is True
        assert capabilities["source"] == "Local settings file"
        assert capabilities["api_key_id"] == "PKTE...3456"
        assert capabilities["stock_feed"] == "iex"

        clear_response = client.post("/settings/market-data/alpaca/clear")
        assert clear_response.status_code == 200
        assert "Saved Alpaca settings cleared" in clear_response.text
        assert get_alpaca_market_data_settings().configured is False


def test_alpaca_settings_page_can_update_feeds_without_resubmitting_secret(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        client.post(
            "/settings/market-data/alpaca",
            data={
                "api_key_id": "PKTEST123456",
                "api_secret_key": "SUPER-SECRET-VALUE",
                "stock_feed": "iex",
                "option_feed": "indicative",
                "base_url": "https://data.alpaca.markets",
            },
        )

        update_response = client.post(
            "/settings/market-data/alpaca",
            data={
                "api_key_id": "",
                "api_secret_key": "",
                "stock_feed": "sip",
                "option_feed": "opra",
                "base_url": "https://data.alpaca.markets/",
            },
        )

        assert update_response.status_code == 200
        saved_settings = get_alpaca_market_data_settings()
        assert saved_settings.api_key_id == "PKTEST123456"
        assert saved_settings.api_secret_key == "SUPER-SECRET-VALUE"
        assert saved_settings.stock_feed == "sip"
        assert saved_settings.option_feed == "opra"
        assert saved_settings.base_url == "https://data.alpaca.markets"


def test_alpaca_settings_page_rejects_invalid_feeds(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        response = client.post(
            "/settings/market-data/alpaca",
            data={
                "api_key_id": "PKTEST123456",
                "api_secret_key": "SUPER-SECRET-VALUE",
                "stock_feed": "invalid",
                "option_feed": "indicative",
                "base_url": "https://data.alpaca.markets",
            },
        )

    assert response.status_code == 400
    assert "Invalid stock feed" in response.text
