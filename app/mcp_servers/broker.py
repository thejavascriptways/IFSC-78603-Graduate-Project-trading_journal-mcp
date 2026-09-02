from __future__ import annotations

import json
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.security import local_transport_security_settings
from app.providers.broker import IBKRBrokerProvider
from app.services.broker import BrokerService, BrokerServiceError


def _normalize_error(exc: Exception) -> ValueError:
    return ValueError(str(exc))


def create_broker_mcp_server(broker_service: BrokerService | None = None) -> FastMCP:
    service = broker_service or BrokerService(provider=IBKRBrokerProvider())
    broker_mcp = FastMCP(
        "Trading Journal Broker MCP",
        instructions=(
            "Broker MCP server for Trading Journal. "
            "This server is currently read-only/not-configured scaffolding for future IBKR sync."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=local_transport_security_settings(),
    )

    @broker_mcp.tool(name="get_broker_status", structured_output=True)
    def get_broker_status_tool() -> dict[str, Any]:
        """Describe configured broker provider and connection status."""
        return service.get_status()

    @broker_mcp.tool(name="list_broker_accounts", structured_output=True)
    def list_broker_accounts_tool() -> list[dict[str, Any]]:
        """List broker accounts when a broker provider is configured."""
        try:
            return service.list_accounts()
        except BrokerServiceError as exc:
            raise _normalize_error(exc) from exc

    @broker_mcp.resource("broker://status", mime_type="application/json")
    def broker_status_resource() -> str:
        """Read broker configuration and status as JSON."""
        return json.dumps(service.get_status(), indent=2)

    @broker_mcp.prompt(
        name="broker_sync_readiness",
        description="Create a prompt for reviewing broker sync readiness and missing configuration.",
    )
    def broker_sync_readiness_prompt() -> str:
        """Build a reusable prompt for broker integration planning."""
        status = service.get_status()
        return (
            "Review the Trading Journal broker integration readiness.\n"
            f"Provider: {status.get('provider')}.\n"
            f"Configured: {status.get('configured')}.\n"
            "Identify what is required before syncing real broker accounts, positions, executions, or orders."
        )

    return broker_mcp
