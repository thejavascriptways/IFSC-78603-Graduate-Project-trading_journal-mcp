from __future__ import annotations

from time import perf_counter
from uuid import uuid4

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.audit.context import CORRELATION_ID_HEADER, correlation_id_context
from app.audit.events import AuditEventStatus, ClientType
from app.audit.service import duration_ms_since, log_mcp_request, log_user_action
from app.db import session_scope


MCP_PATH_PREFIXES = ("/mcp", "/market-data-mcp", "/news-mcp", "/broker-mcp", "/trading-mcp")
SKIPPED_PATH_PREFIXES = ("/static", "/favicon.ico")


class AuditMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if request.url.path.startswith(SKIPPED_PATH_PREFIXES):
            return await call_next(request)

        correlation_id = request.headers.get(CORRELATION_ID_HEADER) or str(uuid4())
        token = correlation_id_context.set(correlation_id)
        started_at = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            self._record_request(
                request,
                correlation_id=correlation_id,
                status=AuditEventStatus.FAILURE,
                status_code=500,
                duration_ms=duration_ms_since(started_at),
            )
            correlation_id_context.reset(token)
            raise

        response.headers[CORRELATION_ID_HEADER] = correlation_id
        self._record_request(
            request,
            correlation_id=correlation_id,
            status=_status_from_code(response.status_code),
            status_code=response.status_code,
            duration_ms=duration_ms_since(started_at),
        )
        correlation_id_context.reset(token)
        return response

    def _record_request(
        self,
        request: Request,
        *,
        correlation_id: str,
        status: AuditEventStatus,
        status_code: int,
        duration_ms: int,
    ) -> None:
        path = request.url.path
        metadata = {
            "query": dict(request.query_params),
            "client_host": request.client.host if request.client else None,
        }

        if path.startswith(MCP_PATH_PREFIXES):
            log_mcp_request(
                correlation_id=correlation_id,
                client_type=ClientType.EXTERNAL_MCP_CLIENT,
                server_id=_server_id_from_path(path),
                operation=f"{request.method} {path}",
                target=path,
                status=status,
                duration_ms=duration_ms,
                message=f"MCP transport request completed with HTTP {status_code}.",
                request_metadata=metadata,
                response_metadata={"status_code": status_code},
            )
            return

        with session_scope() as session:
            log_user_action(
                session,
                correlation_id=correlation_id,
                client_type=ClientType.API if path.startswith("/api") else ClientType.WEB_UI,
                action=f"{request.method} {path}",
                method=request.method,
                path=path,
                status=status,
                status_code=status_code,
                duration_ms=duration_ms,
                message=f"HTTP request completed with status {status_code}.",
                metadata=metadata,
            )


def _status_from_code(status_code: int) -> AuditEventStatus:
    if status_code >= 500:
        return AuditEventStatus.FAILURE
    if status_code >= 400:
        return AuditEventStatus.DENIED
    return AuditEventStatus.SUCCESS


def _server_id_from_path(path: str) -> str | None:
    if path.startswith("/market-data-mcp"):
        return "market_data"
    if path.startswith("/news-mcp"):
        return "news"
    if path.startswith("/broker-mcp"):
        return "broker"
    if path.startswith("/trading-mcp"):
        return "trading"
    if path.startswith("/mcp"):
        return "trading_journal"
    return None
