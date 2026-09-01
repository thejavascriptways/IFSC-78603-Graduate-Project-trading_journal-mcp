from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Settings:
    app_name: str = "Trading Journal"
    database_url: str = os.getenv(
        "TRADING_JOURNAL_DATABASE_URL",
        f"sqlite:///{BASE_DIR / 'trading_journal.db'}",
    )
    secret_key: str = os.getenv("TRADING_JOURNAL_SECRET_KEY", "dev-secret-key")
    templates_dir: Path = BASE_DIR / "app" / "templates"
    static_dir: Path = BASE_DIR / "app" / "static"
    market_data_provider: str = os.getenv("TRADING_JOURNAL_MARKET_DATA_PROVIDER", "alpaca")
    alpaca_market_data_base_url: str = os.getenv("ALPACA_MARKET_DATA_BASE_URL", "https://data.alpaca.markets")
    alpaca_api_key_id: str | None = os.getenv("ALPACA_API_KEY_ID")
    alpaca_api_secret_key: str | None = os.getenv("ALPACA_API_SECRET_KEY")
    alpaca_stock_feed: str = os.getenv("ALPACA_STOCK_FEED", "iex")
    alpaca_option_feed: str = os.getenv("ALPACA_OPTION_FEED", "indicative")
    market_data_timeout_seconds: float = float(os.getenv("TRADING_JOURNAL_MARKET_DATA_TIMEOUT_SECONDS", "10"))


settings = Settings()
