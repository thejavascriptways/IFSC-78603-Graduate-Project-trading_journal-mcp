"""Shared MCP transport settings."""

from __future__ import annotations

from mcp.server.transport_security import TransportSecuritySettings


LOCAL_MCP_ALLOWED_HOSTS = [
    "127.0.0.1",
    "127.0.0.1:*",
    "localhost",
    "localhost:*",
    "testserver",
    "testserver:80",
]


def local_transport_security_settings() -> TransportSecuritySettings:
    """Return the local-development MCP transport security settings."""
    return TransportSecuritySettings(allowed_hosts=LOCAL_MCP_ALLOWED_HOSTS)
