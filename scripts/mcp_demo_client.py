from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client


DEFAULT_BASE_URL = os.getenv("TRADING_JOURNAL_BASE_URL", "http://127.0.0.1:8000")


@dataclass(frozen=True)
class MCPServerTarget:
    id: str
    name: str
    url: str
    purpose: str


def build_server_registry(base_url: str) -> dict[str, MCPServerTarget]:
    normalized_base_url = base_url.rstrip("/")
    return {
        "journal": MCPServerTarget(
            id="journal",
            name="Trading Journal MCP",
            url=f"{normalized_base_url}/mcp/",
            purpose="Portfolio accounts, trades, positions, resources, and journal prompts.",
        ),
        "market": MCPServerTarget(
            id="market",
            name="Market Data MCP",
            url=f"{normalized_base_url}/market-data-mcp/",
            purpose="External market-data capabilities, equity snapshots, option snapshots, and quote prompts.",
        ),
        "news": MCPServerTarget(
            id="news",
            name="News MCP",
            url=f"{normalized_base_url}/news-mcp/",
            purpose="Stock-news capabilities, symbol news, portfolio news, and review prompts.",
        ),
        "broker": MCPServerTarget(
            id="broker",
            name="Broker MCP",
            url=f"{normalized_base_url}/broker-mcp/",
            purpose="Safe broker connectivity scaffolding for future IBKR account and execution sync.",
        ),
        "trading": MCPServerTarget(
            id="trading",
            name="Trading MCP",
            url=f"{normalized_base_url}/trading-mcp/",
            purpose="Safe order-preview scaffolding; live trading is disabled.",
        ),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Command-line MCP client for the Trading Journal application. "
            "Use this as an external client to discover and call the app's MCP capabilities."
        )
    )
    parser.add_argument(
        "--base-url",
        default=DEFAULT_BASE_URL,
        help="Base URL where the Trading Journal web app is running.",
    )
    parser.add_argument(
        "--server",
        choices=["journal", "market", "news", "broker", "trading"],
        default="journal",
        help="Named MCP server to use for single-server commands.",
    )
    parser.add_argument(
        "--url",
        default=None,
        help="Direct MCP server URL. Overrides --base-url and --server for single-server commands.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Print full raw MCP JSON responses instead of friendly summaries where supported.",
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("explain", help="Explain what this CLI is demonstrating about MCP.")
    subparsers.add_parser("servers", help="Show the MCP servers exposed by the app.")
    subparsers.add_parser("discover", help="Discover tools, resources, and prompts from the selected MCP server.")
    subparsers.add_parser("tools", help="List tools from the selected MCP server.")
    subparsers.add_parser("resources", help="List resources from the selected MCP server.")
    subparsers.add_parser("prompts", help="List prompts from the selected MCP server.")
    subparsers.add_parser("summary", help="Shortcut for calling get_portfolio_summary on the journal server.")

    read_resource = subparsers.add_parser("read-resource", help="Read an MCP resource from the selected server.")
    read_resource.add_argument("uri", help="Resource URI, for example portfolio://summary")

    get_prompt = subparsers.add_parser("get-prompt", help="Render an MCP prompt from the selected server.")
    get_prompt.add_argument("prompt", help="Prompt name, for example daily_portfolio_review")
    get_prompt.add_argument(
        "--arguments",
        default="{}",
        help='JSON object for prompt arguments, for example \'{"focus":"risk"}\'',
    )

    call = subparsers.add_parser("call", help="Call an MCP tool with optional JSON arguments.")
    call.add_argument("tool", help="Tool name, for example list_positions")
    call.add_argument(
        "--arguments",
        default="{}",
        help='JSON object for tool arguments, for example \'{"symbol":"VOO"}\'',
    )

    portfolio_review = subparsers.add_parser(
        "portfolio-review",
        help="Run a guided MCP workflow against the Trading Journal MCP server.",
    )
    portfolio_review.add_argument("--focus", default="overall", help="Focus value for the daily_portfolio_review prompt.")

    market_check = subparsers.add_parser(
        "market-check",
        help="Run a guided MCP workflow against the Market Data MCP server.",
    )
    market_check.add_argument(
        "--symbols",
        default="AAPL,MSFT",
        help="Comma-separated stock/ETF symbols to request from the market-data MCP server.",
    )

    subparsers.add_parser(
        "client-demo",
        help="Run a complete multi-server demo showing discovery, tools, resources, and prompts.",
    )

    return parser


def print_section(title: str) -> None:
    print(f"\n{title}")
    print("-" * len(title))


def dump_json(payload: Any) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def parse_json_object(value: str, *, label: str) -> dict[str, Any]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise SystemExit(f"{label} must be valid JSON: {exc}") from exc

    if not isinstance(payload, dict):
        raise SystemExit(f"{label} must be a JSON object.")
    return payload


def extract_structured_content(result: Any) -> Any:
    payload = result.model_dump(mode="json")
    if "structuredContent" in payload:
        structured = payload["structuredContent"]
        return structured.get("result", structured) if isinstance(structured, dict) else structured
    return payload


def extract_resource_text(result: Any) -> str:
    payload = result.model_dump(mode="json")
    contents = payload.get("contents", [])
    if not contents:
        return json.dumps(payload, indent=2, sort_keys=True)

    first_content = contents[0]
    return first_content.get("text") or json.dumps(first_content, indent=2, sort_keys=True)


def extract_prompt_messages(result: Any) -> list[str]:
    payload = result.model_dump(mode="json")
    messages = []
    for message in payload.get("messages", []):
        content = message.get("content", {})
        text = content.get("text")
        if text:
            messages.append(text)
    return messages


def format_tool_result(result: Any, *, raw: bool) -> None:
    if raw:
        dump_json(result.model_dump(mode="json"))
        return
    dump_json(extract_structured_content(result))


def resolve_target(args: argparse.Namespace, registry: dict[str, MCPServerTarget]) -> MCPServerTarget:
    if args.url:
        return MCPServerTarget(
            id="custom",
            name="Custom MCP Server",
            url=args.url,
            purpose="User-provided MCP endpoint.",
        )
    return registry[args.server]


def explain_mcp_client() -> None:
    print_section("What This CLI Demonstrates")
    print("This command-line program is a separate MCP client.")
    print("It connects to the Trading Journal app over streamable HTTP and asks the app what it can do.")
    print()
    print("MCP concepts shown here:")
    print("1. Discovery: the client asks a server for available tools, resources, and prompts.")
    print("2. Tools: the client calls actions such as list_positions or get_equity_snapshots.")
    print("3. Resources: the client reads data snapshots such as portfolio://summary.")
    print("4. Prompts: the client asks the server for reusable prompt text built from app data.")
    print("5. Multi-server flow: one client can talk to portfolio, market-data, news, broker, and trading MCP servers.")


async def connect_and_run(target: MCPServerTarget, operation: Any) -> Any:
    async with httpx.AsyncClient(follow_redirects=True, timeout=30) as http_client:
        async with streamable_http_client(target.url, http_client=http_client) as (read, write, _):
            async with ClientSession(read, write) as session:
                await session.initialize()
                return await operation(session)


async def list_tools(target: MCPServerTarget) -> list[dict[str, Any]]:
    async def operation(session: ClientSession) -> list[dict[str, Any]]:
        result = await session.list_tools()
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": getattr(tool, "inputSchema", None),
            }
            for tool in result.tools
        ]

    return await connect_and_run(target, operation)


async def list_resources(target: MCPServerTarget) -> list[dict[str, Any]]:
    async def operation(session: ClientSession) -> list[dict[str, Any]]:
        result = await session.list_resources()
        return [
            {
                "uri": str(resource.uri),
                "name": resource.name,
                "description": resource.description,
                "mime_type": resource.mimeType,
            }
            for resource in result.resources
        ]

    return await connect_and_run(target, operation)


async def list_prompts(target: MCPServerTarget) -> list[dict[str, Any]]:
    async def operation(session: ClientSession) -> list[dict[str, Any]]:
        result = await session.list_prompts()
        return [
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
            for prompt in result.prompts
        ]

    return await connect_and_run(target, operation)


async def discover(target: MCPServerTarget) -> dict[str, Any]:
    async def operation(session: ClientSession) -> dict[str, Any]:
        tools_result = await session.list_tools()
        resources_result = await session.list_resources()
        prompts_result = await session.list_prompts()

        return {
            "server": {
                "id": target.id,
                "name": target.name,
                "url": target.url,
                "purpose": target.purpose,
            },
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

    return await connect_and_run(target, operation)


async def call_tool(target: MCPServerTarget, tool: str, arguments: dict[str, Any], *, raw: bool) -> None:
    async def operation(session: ClientSession) -> Any:
        return await session.call_tool(tool, arguments=arguments)

    result = await connect_and_run(target, operation)
    format_tool_result(result, raw=raw)


async def read_resource(target: MCPServerTarget, uri: str, *, raw: bool) -> None:
    async def operation(session: ClientSession) -> Any:
        return await session.read_resource(uri)

    result = await connect_and_run(target, operation)
    if raw:
        dump_json(result.model_dump(mode="json"))
    else:
        print(extract_resource_text(result))


async def get_prompt(target: MCPServerTarget, prompt: str, arguments: dict[str, Any], *, raw: bool) -> None:
    async def operation(session: ClientSession) -> Any:
        return await session.get_prompt(prompt, arguments=arguments or None)

    result = await connect_and_run(target, operation)
    if raw:
        dump_json(result.model_dump(mode="json"))
        return

    messages = extract_prompt_messages(result)
    print("\n\n".join(messages) if messages else json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True))


async def run_portfolio_review(journal: MCPServerTarget, focus: str, *, raw: bool) -> None:
    print_section("MCP Client Workflow: Portfolio Review")
    print(f"Connecting to {journal.name}: {journal.url}")

    async def operation(session: ClientSession) -> dict[str, Any]:
        tools = await session.list_tools()
        resources = await session.list_resources()
        prompts = await session.list_prompts()
        summary = await session.call_tool("get_portfolio_summary")
        positions_resource = await session.read_resource("portfolio://positions")
        review_prompt = await session.get_prompt("daily_portfolio_review", arguments={"focus": focus})
        return {
            "tools": [tool.name for tool in tools.tools],
            "resources": [str(resource.uri) for resource in resources.resources],
            "prompts": [prompt.name for prompt in prompts.prompts],
            "summary": summary,
            "positions_resource": positions_resource,
            "review_prompt": review_prompt,
        }

    payload = await connect_and_run(journal, operation)

    if raw:
        dump_json(
            {
                "tools": payload["tools"],
                "resources": payload["resources"],
                "prompts": payload["prompts"],
                "summary": payload["summary"].model_dump(mode="json"),
                "positions_resource": payload["positions_resource"].model_dump(mode="json"),
                "review_prompt": payload["review_prompt"].model_dump(mode="json"),
            }
        )
        return

    print_section("1. Discovery")
    print("Tools:", ", ".join(payload["tools"]))
    print("Resources:", ", ".join(payload["resources"]))
    print("Prompts:", ", ".join(payload["prompts"]))

    print_section("2. Tool Call: get_portfolio_summary")
    dump_json(extract_structured_content(payload["summary"]))

    print_section("3. Resource Read: portfolio://positions")
    print(extract_resource_text(payload["positions_resource"]))

    print_section("4. Prompt Render: daily_portfolio_review")
    print("\n\n".join(extract_prompt_messages(payload["review_prompt"])))


async def run_market_check(market: MCPServerTarget, symbols: str, *, raw: bool) -> None:
    normalized_symbols = [symbol.strip().upper() for symbol in symbols.split(",") if symbol.strip()]

    print_section("MCP Client Workflow: Market Data Check")
    print(f"Connecting to {market.name}: {market.url}")

    async def operation(session: ClientSession) -> dict[str, Any]:
        tools = await session.list_tools()
        resources = await session.list_resources()
        prompts = await session.list_prompts()
        capabilities = await session.call_tool("get_market_data_capabilities")
        capabilities_payload = extract_structured_content(capabilities)
        quotes = None
        if capabilities_payload.get("configured") is True:
            quotes = await session.call_tool("get_equity_snapshots", arguments={"symbols": normalized_symbols})
        health_prompt = await session.get_prompt(
            "market_data_health_check",
            arguments={"symbols": ",".join(normalized_symbols)},
        )
        return {
            "tools": [tool.name for tool in tools.tools],
            "resources": [str(resource.uri) for resource in resources.resources],
            "prompts": [prompt.name for prompt in prompts.prompts],
            "capabilities": capabilities,
            "quotes": quotes,
            "health_prompt": health_prompt,
        }

    payload = await connect_and_run(market, operation)

    if raw:
        dump_json(
            {
                "tools": payload["tools"],
                "resources": payload["resources"],
                "prompts": payload["prompts"],
                "capabilities": payload["capabilities"].model_dump(mode="json"),
                "quotes": None if payload["quotes"] is None else payload["quotes"].model_dump(mode="json"),
                "health_prompt": payload["health_prompt"].model_dump(mode="json"),
            }
        )
        return

    print_section("1. Discovery")
    print("Tools:", ", ".join(payload["tools"]))
    print("Resources:", ", ".join(payload["resources"]))
    print("Prompts:", ", ".join(payload["prompts"]))

    print_section("2. Tool Call: get_market_data_capabilities")
    dump_json(extract_structured_content(payload["capabilities"]))

    print_section("3. Tool Call: get_equity_snapshots")
    if payload["quotes"] is None:
        print("Skipped because live market data is not configured for this app instance.")
    else:
        dump_json(extract_structured_content(payload["quotes"]))

    print_section("4. Prompt Render: market_data_health_check")
    print("\n\n".join(extract_prompt_messages(payload["health_prompt"])))


async def run_client_demo(registry: dict[str, MCPServerTarget], *, raw: bool) -> None:
    explain_mcp_client()
    await run_portfolio_review(registry["journal"], "overall", raw=raw)
    await run_market_check(registry["market"], "AAPL,MSFT", raw=raw)
    for server_id in ("news", "broker", "trading"):
        print_section(f"MCP Client Workflow: Discover {registry[server_id].name}")
        dump_json(await discover(registry[server_id]))


async def run_client(args: argparse.Namespace) -> None:
    registry = build_server_registry(args.base_url)
    target = resolve_target(args, registry)

    if args.command == "explain":
        explain_mcp_client()
        return

    if args.command == "servers":
        dump_json(
            [
                {
                    "id": server.id,
                    "name": server.name,
                    "url": server.url,
                    "purpose": server.purpose,
                }
                for server in registry.values()
            ]
        )
        return

    if args.command == "discover":
        dump_json(await discover(target))
        return

    if args.command == "tools":
        dump_json(await list_tools(target))
        return

    if args.command == "resources":
        dump_json(await list_resources(target))
        return

    if args.command == "prompts":
        dump_json(await list_prompts(target))
        return

    if args.command == "summary":
        await call_tool(target if args.url else registry["journal"], "get_portfolio_summary", {}, raw=args.raw)
        return

    if args.command == "read-resource":
        await read_resource(target, args.uri, raw=args.raw)
        return

    if args.command == "get-prompt":
        prompt_args = parse_json_object(args.arguments, label="--arguments")
        await get_prompt(target, args.prompt, prompt_args, raw=args.raw)
        return

    if args.command == "call":
        tool_args = parse_json_object(args.arguments, label="--arguments")
        await call_tool(target, args.tool, tool_args, raw=args.raw)
        return

    if args.command == "portfolio-review":
        await run_portfolio_review(registry["journal"], args.focus, raw=args.raw)
        return

    if args.command == "market-check":
        await run_market_check(registry["market"], args.symbols, raw=args.raw)
        return

    if args.command == "client-demo":
        await run_client_demo(registry, raw=args.raw)
        return

    raise SystemExit(f"Unknown command: {args.command}")


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    try:
        asyncio.run(run_client(args))
    except httpx.ConnectError as exc:
        print(
            "Could not connect to the MCP server. Start the app first with: "
            "uvicorn app.main:app --reload",
            file=sys.stderr,
        )
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
