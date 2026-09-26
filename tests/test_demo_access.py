from __future__ import annotations

import base64
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import settings


@pytest.fixture
def demo_password_enabled() -> Iterator[None]:
    original_username = settings.demo_username
    original_password = settings.demo_password
    object.__setattr__(settings, "demo_username", "demo")
    object.__setattr__(settings, "demo_password", "professor-demo")
    yield
    object.__setattr__(settings, "demo_username", original_username)
    object.__setattr__(settings, "demo_password", original_password)


def _basic_auth(username: str, password: str) -> str:
    encoded = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    return f"Basic {encoded}"


def test_demo_password_blocks_unauthorized_browser_access(app_instance, demo_password_enabled):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/")

    assert response.status_code == 401
    assert response.headers["www-authenticate"] == 'Basic realm="Trading Journal Demo"'


def test_demo_password_allows_authorized_browser_access(app_instance, demo_password_enabled):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/", headers={"Authorization": _basic_auth("demo", "professor-demo")})

    assert response.status_code == 200


def test_demo_password_allows_local_app_when_disabled(app_instance):
    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/")

    assert response.status_code == 200
