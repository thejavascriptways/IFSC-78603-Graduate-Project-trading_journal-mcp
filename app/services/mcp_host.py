from __future__ import annotations

from dataclasses import asdict, dataclass
from time import perf_counter
from typing import Any, Awaitable, Callable, TypeVar

import httpx
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from app.audit.context import CORRELATION_ID_HEADER, current_correlation_id
from app.audit.events import AuditEventStatus, ClientType
from app.audit.service import duration_ms_since, log_mcp_request


T = TypeVar("T")


class MCPHostError(Exception):
    """Raised when the in-app MCP host cannot complete an MCP client operation."""


@dataclass(frozen=True)
class MCPServerConfig:
    id: str
    name: str
    url: str
    description: str


REGISTERED_MCP_SERVERS: tuple[MCPServerConfig, ...] = (
    MCPServerConfig(
        id="trading_journal",
        name="Trading Journal MCP",
        url="http://127.0.0.1:8000/mcp/",
        description="Portfolio tools and resources for accounts, trades, and positions.",
    ),
    MCPServerConfig(
        id="market_data",
        name="Market Data MCP",
        url="http://127.0.0.1:8000/market-data-mcp/",
        description="Live market-data tools and provider capability resources.",
    ),
    MCPServerConfig(
        id="news",
        name="News MCP",
        url="http://127.0.0.1:8000/news-mcp/",
        description="Stock-news tools, resources, and review prompts.",
    ),
    MCPServerConfig(
        id="broker",
        name="Broker MCP",
        url="http://127.0.0.1:8000/broker-mcp/",
        description="Safe broker connectivity scaffolding for future IBKR sync.",
    ),
    MCPServerConfig(
        id="trading",
        name="Trading MCP",
        url="http://127.0.0.1:8000/trading-mcp/",
        description="Safe order-preview scaffolding; live trading is disabled.",
    ),
)


def list_registered_mcp_servers() -> list[dict[str, Any]]:
    return [asdict(server) for server in REGISTERED_MCP_SERVERS]


def get_registered_mcp_server(server_id: str) -> MCPServerConfig:
    for server in REGISTERED_MCP_SERVERS:
        if server.id == server_id:
            return server
    raise MCPHostError(f"Unknown MCP server '{server_id}'.")


async def list_server_catalog(app: FastAPI, server_id: str) -> dict[str, Any]:
    server = get_registered_mcp_server(server_id)
    started_at = perf_counter()

    async def operation(session: ClientSession) -> dict[str, Any]:
        tools_result = await session.list_tools()
        resources_result = await session.list_resources()
        prompts_result = await session.list_prompts()

        return {
            "server": asdict(server),
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": getattr(tool, "inputSchema", None),
                }
                for tool in tools_result.tools
            ],
            "resources": [
                {
                    "uri": str(resource.uri),
                    "name": resource.name,
                    "description": resource.description,
                    "mime_type": resource.mimeType,
                }
                for resource in resources_result.resources
            ],
            "prompts": [
                {
                    "name": prompt.name,
                    "description": prompt.description,
                    "arguments": [
                        {
                            "name": argument.name,
                            "description": argument.description,
                            "required": argument.required,
                        }
                        for argument in prompt.arguments
                    ],
                }
                for prompt in prompts_result.prompts
            ],
        }

    try:
        result = await _run_client_operation(app, server, operation)
    except MCPHostError:
        log_mcp_request(
            server_id=server_id,
            operation="list_catalog",
            target=server.url,
            client_type=ClientType.INTERNAL_MCP_CLIENT,
            status=AuditEventStatus.FAILURE,
            duration_ms=duration_ms_since(started_at),
            message=f"Failed to discover MCP catalog for {server.name}.",
        )
        raise
    log_mcp_request(
        server_id=server_id,
        operation="list_catalog",
        target=server.url,
        client_type=ClientType.INTERNAL_MCP_CLIENT,
        duration_ms=duration_ms_since(started_at),
        message=f"Discovered MCP catalog for {server.name}.",
        response_metadata={
            "tool_count": len(result["tools"]),
            "resource_count": len(result["resources"]),
            "prompt_count": len(result["prompts"]),
        },
    )
    return result


async def call_server_tool(app: FastAPI, server_id: str, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    server = get_registered_mcp_server(server_id)
    started_at = perf_counter()

    async def operation(session: ClientSession) -> dict[str, Any]:
        result = await session.call_tool(tool_name, arguments=arguments)
        return result.model_dump(mode="json")

    try:
        result = await _run_client_operation(app, server, operation)
    except MCPHostError:
        log_mcp_request(
            server_id=server_id,
            operation="call_tool",
            target=tool_name,
            client_type=ClientType.INTERNAL_MCP_CLIENT,
            status=AuditEventStatus.FAILURE,
            duration_ms=duration_ms_since(started_at),
            message=f"Failed to call MCP tool {tool_name}.",
            request_metadata={"arguments": arguments},
        )
        raise
    log_mcp_request(
        server_id=server_id,
        operation="call_tool",
        target=tool_name,
        client_type=ClientType.INTERNAL_MCP_CLIENT,
        duration_ms=duration_ms_since(started_at),
        message=f"Called MCP tool {tool_name}.",
        request_metadata={"arguments": arguments},
        response_metadata={"has_structured_content": bool(result.get("structuredContent"))},
    )
    return result


async def read_server_resource(app: FastAPI, server_id: str, uri: str) -> dict[str, Any]:
    server = get_registered_mcp_server(server_id)
    started_at = perf_counter()

    async def operation(session: ClientSession) -> dict[str, Any]:
        result = await session.read_resource(uri)
        return result.model_dump(mode="json")

    try:
        result = await _run_client_operation(app, server, operation)
    except MCPHostError:
        log_mcp_request(
            server_id=server_id,
            operation="read_resource",
            target=uri,
            client_type=ClientType.INTERNAL_MCP_CLIENT,
            status=AuditEventStatus.FAILURE,
            duration_ms=duration_ms_since(started_at),
            message=f"Failed to read MCP resource {uri}.",
        )
        raise
    log_mcp_request(
        server_id=server_id,
        operation="read_resource",
        target=uri,
        client_type=ClientType.INTERNAL_MCP_CLIENT,
        duration_ms=duration_ms_since(started_at),
        message=f"Read MCP resource {uri}.",
        response_metadata={"content_count": len(result.get("contents", []))},
    )
    return result


async def get_server_prompt(
    app: FastAPI,
    server_id: str,
    prompt_name: str,
    arguments: dict[str, str],
) -> dict[str, Any]:
    server = get_registered_mcp_server(server_id)
    started_at = perf_counter()

    async def operation(session: ClientSession) -> dict[str, Any]:
        result = await session.get_prompt(prompt_name, arguments=arguments or None)
        return result.model_dump(mode="json")

    try:
        result = await _run_client_operation(app, server, operation)
    except MCPHostError:
        log_mcp_request(
            server_id=server_id,
            operation="get_prompt",
            target=prompt_name,
            client_type=ClientType.INTERNAL_MCP_CLIENT,
            status=AuditEventStatus.FAILURE,
            duration_ms=duration_ms_since(started_at),
            message=f"Failed to render MCP prompt {prompt_name}.",
            request_metadata={"arguments": arguments},
        )
        raise
    log_mcp_request(
        server_id=server_id,
        operation="get_prompt",
        target=prompt_name,
        client_type=ClientType.INTERNAL_MCP_CLIENT,
        duration_ms=duration_ms_since(started_at),
        message=f"Rendered MCP prompt {prompt_name}.",
        request_metadata={"arguments": arguments},
        response_metadata={"message_count": len(result.get("messages", []))},
    )
    return result


async def _run_client_operation(
    app: FastAPI,
    server: MCPServerConfig,
    operation: Callable[[ClientSession], Awaitable[T]],
) -> T:
    try:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
            follow_redirects=True,
            headers={CORRELATION_ID_HEADER: current_correlation_id()},
        ) as http_client:
            async with streamable_http_client(server.url, http_client=http_client) as (read, write, _):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return await operation(session)
    except Exception as exc:  # pragma: no cover - exercised via HTTP API integration tests
        raise MCPHostError(f"Could not complete MCP operation against {server.name}.") from exc
