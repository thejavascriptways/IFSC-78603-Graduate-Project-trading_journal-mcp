from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.config import settings


ALPACA_STOCK_FEEDS = ("iex", "sip")
ALPACA_OPTION_FEEDS = ("indicative", "opra")
LOCAL_SETTINGS_FILE_NAME = "alpaca_market_data.json"


class MarketDataSettingsError(Exception):
    """Raised when market-data settings cannot be saved or loaded."""


@dataclass(frozen=True)
class AlpacaMarketDataSettings:
    api_key_id: str | None
    api_secret_key: str | None
    stock_feed: str
    option_feed: str
    base_url: str
    local_file_exists: bool
    storage_path: Path

    @property
    def configured(self) -> bool:
        return bool(self.api_key_id and self.api_secret_key)

    @property
    def masked_api_key_id(self) -> str:
        return _mask_value(self.api_key_id)

    @property
    def secret_status(self) -> str:
        return "Saved" if self.api_secret_key else "Not saved"

    @property
    def source(self) -> str:
        if self.local_file_exists:
            return "Local settings file"
        if settings.alpaca_api_key_id or settings.alpaca_api_secret_key:
            return "Environment variables"
        return "Defaults only"


def get_alpaca_market_data_settings() -> AlpacaMarketDataSettings:
    saved = _read_saved_settings()
    storage_path = _settings_file_path()
    return AlpacaMarketDataSettings(
        api_key_id=_coalesce_saved(saved, "api_key_id", settings.alpaca_api_key_id),
        api_secret_key=_coalesce_saved(saved, "api_secret_key", settings.alpaca_api_secret_key),
        stock_feed=_coalesce_saved(saved, "stock_feed", settings.alpaca_stock_feed),
        option_feed=_coalesce_saved(saved, "option_feed", settings.alpaca_option_feed),
        base_url=_coalesce_saved(saved, "base_url", settings.alpaca_market_data_base_url),
        local_file_exists=storage_path.exists(),
        storage_path=storage_path,
    )


def get_alpaca_settings_view_model() -> dict[str, Any]:
    current = get_alpaca_market_data_settings()
    return {
        "configured": current.configured,
        "source": current.source,
        "masked_api_key_id": current.masked_api_key_id,
        "secret_status": current.secret_status,
        "stock_feed": current.stock_feed,
        "option_feed": current.option_feed,
        "base_url": current.base_url,
        "local_file_exists": current.local_file_exists,
        "storage_path": str(current.storage_path),
        "stock_feed_options": ALPACA_STOCK_FEEDS,
        "option_feed_options": ALPACA_OPTION_FEEDS,
    }


def save_alpaca_market_data_settings(
    *,
    api_key_id: str | None,
    api_secret_key: str | None,
    stock_feed: str,
    option_feed: str,
    base_url: str,
) -> AlpacaMarketDataSettings:
    existing_saved = _read_saved_settings()
    normalized_stock_feed = _validate_choice(stock_feed, ALPACA_STOCK_FEEDS, "stock feed")
    normalized_option_feed = _validate_choice(option_feed, ALPACA_OPTION_FEEDS, "option feed")
    normalized_base_url = _normalize_base_url(base_url)

    next_saved = {
        "stock_feed": normalized_stock_feed,
        "option_feed": normalized_option_feed,
        "base_url": normalized_base_url,
    }

    next_api_key_id = _clean_optional(api_key_id) or _clean_optional(existing_saved.get("api_key_id"))
    next_api_secret_key = _clean_optional(api_secret_key) or _clean_optional(existing_saved.get("api_secret_key"))

    if next_api_key_id:
        next_saved["api_key_id"] = next_api_key_id
    if next_api_secret_key:
        next_saved["api_secret_key"] = next_api_secret_key

    _write_saved_settings(next_saved)
    return get_alpaca_market_data_settings()


def clear_alpaca_market_data_settings() -> None:
    settings_file = _settings_file_path()
    if settings_file.exists():
        settings_file.unlink()


def _settings_file_path() -> Path:
    return settings.local_settings_dir / LOCAL_SETTINGS_FILE_NAME


def _read_saved_settings() -> dict[str, str]:
    settings_file = _settings_file_path()
    if not settings_file.exists():
        return {}

    try:
        payload = json.loads(settings_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise MarketDataSettingsError("Could not read saved Alpaca settings.") from exc

    if not isinstance(payload, dict):
        raise MarketDataSettingsError("Saved Alpaca settings file is not valid.")

    return {str(key): str(value) for key, value in payload.items() if value is not None}


def _write_saved_settings(payload: dict[str, str]) -> None:
    settings_file = _settings_file_path()
    try:
        settings_file.parent.mkdir(parents=True, exist_ok=True)
        settings_file.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        settings_file.chmod(0o600)
    except OSError as exc:
        raise MarketDataSettingsError("Could not save Alpaca settings.") from exc


def _coalesce_saved(saved: dict[str, str], key: str, fallback: str | None) -> str:
    return _clean_optional(saved.get(key)) or _clean_optional(fallback) or ""


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _validate_choice(value: str, allowed_values: tuple[str, ...], field_name: str) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed_values:
        allowed = ", ".join(allowed_values)
        raise MarketDataSettingsError(f"Invalid {field_name}. Allowed values: {allowed}.")
    return normalized


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    if not normalized:
        raise MarketDataSettingsError("Alpaca market-data base URL is required.")
    if not normalized.startswith(("https://", "http://")):
        raise MarketDataSettingsError("Alpaca market-data base URL must start with http:// or https://.")
    return normalized


def _mask_value(value: str | None) -> str:
    cleaned = _clean_optional(value)
    if not cleaned:
        return "Not saved"
    if len(cleaned) <= 8:
        return "****"
    return f"{cleaned[:4]}...{cleaned[-4:]}"
