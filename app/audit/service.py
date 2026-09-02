from __future__ import annotations

from collections.abc import Mapping
from time import perf_counter
from typing import Any

from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.audit.context import current_correlation_id
from app.audit.events import AuditEventStatus, ClientType
from app.db import session_scope
from app.models.entities import ApplicationEventLog, ExternalAPICallLog, MCPRequestLog, UserActionLog


SENSITIVE_KEYS = {
    "api_key",
    "apikey",
    "authorization",
    "cookie",
    "password",
    "secret",
    "token",
    "alpaca_api_key_id",
    "alpaca_api_secret_key",
    "apca-api-key-id",
    "apca-api-secret-key",
}


def redact_sensitive_data(value: Any) -> Any:
    if isinstance(value, Mapping):
        redacted: dict[str, Any] = {}
        for key, item in value.items():
            if _is_sensitive_key(str(key)):
                redacted[str(key)] = "[REDACTED]"
            else:
                redacted[str(key)] = redact_sensitive_data(item)
        return redacted
    if isinstance(value, list):
        return [redact_sensitive_data(item) for item in value]
    if isinstance(value, tuple):
        return [redact_sensitive_data(item) for item in value]
    return value


def _is_sensitive_key(key: str) -> bool:
    normalized_dash = key.lower().replace("_", "-")
    normalized_underscore = key.lower().replace("-", "_")
    return any(
        sensitive in normalized_dash or sensitive in normalized_underscore
        for sensitive in SENSITIVE_KEYS
    )


def log_user_action(
    session: Session,
    *,
    action: str,
    message: str,
    client_type: ClientType,
    status: AuditEventStatus = AuditEventStatus.SUCCESS,
    method: str | None = None,
    path: str | None = None,
    status_code: int | None = None,
    duration_ms: int | None = None,
    metadata: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> UserActionLog:
    entry = UserActionLog(
        correlation_id=correlation_id or current_correlation_id(),
        client_type=client_type,
        action=action,
        method=method,
        path=path,
        status=status,
        status_code=status_code,
        duration_ms=duration_ms,
        message=message,
        metadata_json=redact_sensitive_data(metadata or {}),
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)
    return entry


def log_mcp_request(
    *,
    server_id: str | None,
    operation: str,
    target: str | None,
    message: str,
    client_type: ClientType,
    status: AuditEventStatus = AuditEventStatus.SUCCESS,
    request_metadata: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
    duration_ms: int | None = None,
    correlation_id: str | None = None,
) -> MCPRequestLog:
    with session_scope() as session:
        entry = MCPRequestLog(
            correlation_id=correlation_id or current_correlation_id(),
            client_type=client_type,
            server_id=server_id,
            operation=operation,
            target=target,
            status=status,
            duration_ms=duration_ms,
            message=message,
            request_metadata_json=redact_sensitive_data(request_metadata or {}),
            response_metadata_json=redact_sensitive_data(response_metadata or {}),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def log_external_api_call(
    *,
    provider: str,
    operation: str,
    endpoint: str | None,
    message: str,
    status: AuditEventStatus = AuditEventStatus.SUCCESS,
    status_code: int | None = None,
    duration_ms: int | None = None,
    request_metadata: dict[str, Any] | None = None,
    response_metadata: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> ExternalAPICallLog:
    with session_scope() as session:
        entry = ExternalAPICallLog(
            correlation_id=correlation_id or current_correlation_id(),
            provider=provider,
            operation=operation,
            endpoint=endpoint,
            status=status,
            status_code=status_code,
            duration_ms=duration_ms,
            message=message,
            request_metadata_json=redact_sensitive_data(request_metadata or {}),
            response_metadata_json=redact_sensitive_data(response_metadata or {}),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def log_application_event(
    *,
    event_type: str,
    message: str,
    status: AuditEventStatus = AuditEventStatus.SUCCESS,
    metadata: dict[str, Any] | None = None,
    correlation_id: str | None = None,
) -> ApplicationEventLog:
    with session_scope() as session:
        entry = ApplicationEventLog(
            correlation_id=correlation_id or current_correlation_id(),
            event_type=event_type,
            status=status,
            message=message,
            metadata_json=redact_sensitive_data(metadata or {}),
        )
        session.add(entry)
        session.commit()
        session.refresh(entry)
        return entry


def serialize_audit_log(entry: Any, *, category: str) -> dict[str, Any]:
    payload = {
        "category": category,
        "id": entry.id,
        "correlation_id": entry.correlation_id,
        "occurred_at": entry.occurred_at.isoformat() if entry.occurred_at else None,
        "status": entry.status.value,
        "message": entry.message,
    }

    if isinstance(entry, UserActionLog):
        payload.update(
            {
                "client_type": entry.client_type.value,
                "action": entry.action,
                "method": entry.method,
                "path": entry.path,
                "status_code": entry.status_code,
                "duration_ms": entry.duration_ms,
                "metadata": entry.metadata_json or {},
            }
        )
    elif isinstance(entry, MCPRequestLog):
        payload.update(
            {
                "client_type": entry.client_type.value,
                "server_id": entry.server_id,
                "operation": entry.operation,
                "target": entry.target,
                "duration_ms": entry.duration_ms,
                "request_metadata": entry.request_metadata_json or {},
                "response_metadata": entry.response_metadata_json or {},
            }
        )
    elif isinstance(entry, ExternalAPICallLog):
        payload.update(
            {
                "provider": entry.provider,
                "operation": entry.operation,
                "endpoint": entry.endpoint,
                "status_code": entry.status_code,
                "duration_ms": entry.duration_ms,
                "request_metadata": entry.request_metadata_json or {},
                "response_metadata": entry.response_metadata_json or {},
            }
        )
    elif isinstance(entry, ApplicationEventLog):
        payload.update(
            {
                "event_type": entry.event_type,
                "metadata": entry.metadata_json or {},
            }
        )

    return payload


def list_recent_audit_logs(session: Session, *, limit: int = 100) -> dict[str, list[dict[str, Any]]]:
    return {
        "user_actions": [
            serialize_audit_log(entry, category="user_action")
            for entry in session.scalars(select(UserActionLog).order_by(desc(UserActionLog.id)).limit(limit)).all()
        ],
        "mcp_requests": [
            serialize_audit_log(entry, category="mcp_request")
            for entry in session.scalars(select(MCPRequestLog).order_by(desc(MCPRequestLog.id)).limit(limit)).all()
        ],
        "external_api_calls": [
            serialize_audit_log(entry, category="external_api_call")
            for entry in session.scalars(select(ExternalAPICallLog).order_by(desc(ExternalAPICallLog.id)).limit(limit)).all()
        ],
        "application_events": [
            serialize_audit_log(entry, category="application_event")
            for entry in session.scalars(select(ApplicationEventLog).order_by(desc(ApplicationEventLog.id)).limit(limit)).all()
        ],
    }


def duration_ms_since(start: float) -> int:
    return max(0, round((perf_counter() - start) * 1000))
