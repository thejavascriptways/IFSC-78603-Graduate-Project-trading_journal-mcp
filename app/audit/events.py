from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4


class ClientType(StrEnum):
    WEB_UI = "WEB_UI"
    API = "API"
    INTERNAL_MCP_CLIENT = "INTERNAL_MCP_CLIENT"
    EXTERNAL_MCP_CLIENT = "EXTERNAL_MCP_CLIENT"
    CLI = "CLI"


class AuditEventStatus(StrEnum):
    SUCCESS = "SUCCESS"
    FAILURE = "FAILURE"
    DENIED = "DENIED"
    PENDING = "PENDING"
    SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class AuditEvent:
    """Transport-neutral audit event shape used before persistence is added."""

    event_type: str
    message: str
    client_type: ClientType
    status: AuditEventStatus = AuditEventStatus.SUCCESS
    correlation_id: str = field(default_factory=lambda: str(uuid4()))
    occurred_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = field(default_factory=dict)
