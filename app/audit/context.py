from __future__ import annotations

from contextvars import ContextVar
from uuid import uuid4


CORRELATION_ID_HEADER = "X-Correlation-ID"
correlation_id_context: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def current_correlation_id() -> str:
    return correlation_id_context.get() or str(uuid4())
