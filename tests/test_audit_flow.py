from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select

from app.audit.context import CORRELATION_ID_HEADER
from app.audit.service import redact_sensitive_data
from app.db import session_scope
from app.models.entities import MCPRequestLog, UserActionLog


def test_http_requests_get_correlation_id_and_persistent_user_action_log(app_instance):
    correlation_id = "test-correlation-accounts"

    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        response = client.get("/api/accounts", headers={CORRELATION_ID_HEADER: correlation_id})

    assert response.status_code == 200
    assert response.headers[CORRELATION_ID_HEADER] == correlation_id

    with session_scope() as session:
        log = session.scalars(
            select(UserActionLog).where(UserActionLog.correlation_id == correlation_id)
        ).one()
        assert log.path == "/api/accounts"
        assert log.method == "GET"
        assert log.status_code == 200
        assert log.client_type.value == "API"


def test_mcp_console_catalog_creates_internal_mcp_audit_log(app_instance):
    correlation_id = "test-correlation-mcp-catalog"

    with TestClient(app_instance, base_url="http://127.0.0.1:8000") as client:
        response = client.get(
            "/api/mcp-console/catalog",
            params={"server_id": "trading"},
            headers={CORRELATION_ID_HEADER: correlation_id},
        )

    assert response.status_code == 200

    with session_scope() as session:
        logs = session.scalars(
            select(MCPRequestLog).where(MCPRequestLog.correlation_id == correlation_id)
        ).all()
        assert any(log.server_id == "trading" and log.operation == "list_catalog" for log in logs)
        assert any(log.server_id == "trading" and "trading-mcp" in (log.target or "") for log in logs)


def test_audit_redaction_masks_nested_secrets():
    payload = {
        "api_key": "abc",
        "nested": {
            "Authorization": "Bearer secret",
            "safe": "visible",
        },
        "items": [{"alpaca_api_secret_key": "should-not-leak"}],
    }

    redacted = redact_sensitive_data(payload)

    assert redacted["api_key"] == "[REDACTED]"
    assert redacted["nested"]["Authorization"] == "[REDACTED]"
    assert redacted["nested"]["safe"] == "visible"
    assert redacted["items"][0]["alpaca_api_secret_key"] == "[REDACTED]"
