from __future__ import annotations

import os
from pathlib import Path

import pytest


DB_PATH = Path(__file__).resolve().parent / "test_trading_journal.db"
os.environ["TRADING_JOURNAL_DATABASE_URL"] = f"sqlite:///{DB_PATH}"

from app.db import Base, engine, session_scope  # noqa: E402
from app.main import create_app  # noqa: E402
from app.services.portfolio import seed_default_accounts  # noqa: E402


@pytest.fixture(autouse=True)
def reset_database():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    with session_scope() as session:
        seed_default_accounts(session)
    yield
    Base.metadata.drop_all(bind=engine)


@pytest.fixture
def app_instance():
    return create_app()
