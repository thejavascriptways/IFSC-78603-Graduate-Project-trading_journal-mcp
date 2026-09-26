from __future__ import annotations

import base64
import secrets

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.config import settings


class DemoAccessMiddleware(BaseHTTPMiddleware):
    """Optional HTTP Basic gate for temporary public demo tunnels."""

    async def dispatch(self, request: Request, call_next):
        if not settings.demo_password:
            return await call_next(request)

        if _is_authorized(request.headers.get("authorization")):
            return await call_next(request)

        return Response(
            content="Demo access password required.",
            status_code=401,
            headers={"WWW-Authenticate": 'Basic realm="Trading Journal Demo"'},
        )


def _is_authorized(authorization: str | None) -> bool:
    if not authorization:
        return False

    scheme, _, value = authorization.partition(" ")
    if scheme.lower() != "basic" or not value:
        return False

    try:
        decoded = base64.b64decode(value).decode("utf-8")
    except (ValueError, UnicodeDecodeError):
        return False

    username, separator, password = decoded.partition(":")
    if not separator:
        return False

    return secrets.compare_digest(username, settings.demo_username) and secrets.compare_digest(
        password,
        settings.demo_password,
    )
