from __future__ import annotations

import os
import shutil
from pathlib import Path

import pytest


DB_PATH = Path(__file__).resolve().parent / "test_trading_journal.db"
LOCAL_SETTINGS_DIR = Path(__file__).resolve().parent / "test_instance"
os.environ["TRADING_JOURNAL_DATABASE_URL"] = f"sqlite:///{DB_PATH}"
os.environ["TRADING_JOURNAL_LOCAL_SETTINGS_DIR"] = str(LOCAL_SETTINGS_DIR)
os.environ.pop("ALPACA_API_KEY_ID", None)
os.environ.pop("ALPACA_API_SECRET_KEY", None)

from app.db import Base, engine, session_scope  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.portfolio import seed_default_accounts  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    if LOCAL_SETTINGS_DIR.exists():
        shutil.rmtree(LOCAL_SETTINGS_DIR)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with session_scope() as session:
        seed_default_accounts(session)
    yield
    Base.metadata.drop_all(bind=engine)
    if LOCAL_SETTINGS_DIR.exists():
        shutil.rmtree(LOCAL_SETTINGS_DIR)


@pytest.fixture
def app_instance():
    return create_app()
