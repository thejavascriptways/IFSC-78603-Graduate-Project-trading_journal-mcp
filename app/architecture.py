"""Static description of the Trading Journal architecture for the /architecture page.

Single source of truth for the block diagram: node geometry (in a 1000 x 580
canvas), connectors, and the text shown when a user hovers over a box.
"""
from __future__ import annotations

from typing import Any

CANVAS = {"w": 1000, "h": 580}

KIND_LABELS = {
    "client": "Client",
    "app": "Application",
    "mcp": "MCP server",
    "data": "Data / provider",
    "cross": "Cross-cutting",
    "group": "Layer",
}


def _node(id: str, label: str, sub: str, kind: str, x: int, y: int, w: int, h: int, summary: str,
          details: list[str] | None = None, lists: list[tuple[str, list[str]]] | None = None,
          files: list[str] | None = None) -> dict[str, Any]:
    return {
        "id": id, "label": label, "sub": sub, "kind": kind, "kind_label": KIND_LABELS[kind],
        "x": x, "y": y, "w": w, "h": h, "summary": summary, "details": details or [],
        "lists": [{"title": t, "items": i} for t, i in (lists or [])], "files": files or [],
    }


NODES: list[dict[str, Any]] = [
    # ---- layer containers (drawn behind the boxes) ----
    _node("g_app", "FastAPI application", "", "group", 250, 30, 300, 400,
          "One Python process that hosts the web UI, the JSON API and all five MCP servers.",
          ["Started with uvicorn app.main:app",
           "Creates the tables and seeds the IBKR Live and Manual Entry accounts on startup",
           "Mounts the MCP servers at /mcp, /market-data-mcp, /news-mcp, /broker-mcp and /trading-mcp"],
          files=["app/main.py"]),
    _node("g_mcp", "MCP servers", "", "group", 600, 30, 190, 450,
          "Five domain servers exposing 16 tools, 6 resources and 6 prompts over Streamable HTTP.",
          ["Stateless HTTP with JSON responses, built with FastMCP",
           "Split by domain so permissions and roadmap can evolve independently",
           "Journal, Market Data and News are live; Broker and Trading are safe scaffolds"],
          files=["app/mcp_servers/"]),
    _node("g_data", "Data layer", "", "group", 830, 30, 150, 450,
          "The systems of record and external services that sit behind the MCP servers.",
          ["Local SQLite database for the journal and the audit trail",
           "External providers are reached through adapter interfaces so they can be swapped"],
          files=["app/providers/", "app/models/"]),

    # ---- clients ----
    _node("browser", "Browser", "Server-rendered UI", "client", 20, 75, 180, 70,
          "The user's entry point. Pages are rendered on the server with Jinja2 templates; there is no separate front-end build.",
          ["Menus: Dashboard, Portfolio, Trading, Configuration, Architecture",
           "Dark and light theme toggle",
           "Talks to the FastAPI app over plain HTTP"],
          files=["app/templates/", "app/static/"]),
    _node("cli", "External MCP client", "CLI or any MCP client", "client", 20, 420, 180, 70,
          "A separate program that talks straight to the MCP servers over Streamable HTTP, bypassing the web UI.",
          ["The bundled script lists servers, tools, resources and prompts and can call tools such as list_positions",
           "Calls are recorded in the audit log as external MCP client requests",
           "Any MCP client that supports Streamable HTTP can connect to the same endpoints"],
          files=["scripts/mcp_demo_client.py"]),

    # ---- inside the FastAPI app ----
    _node("mw", "Middleware", "Audit + demo access", "app", 270, 80, 260, 60,
          "Wraps every HTTP request before it reaches a route.",
          ["Assigns a correlation ID to each request",
           "Optional HTTP Basic password gate for public demo tunnels (constant-time comparison)",
           "Writes user-action logs with secrets redacted"],
          files=["app/audit/middleware.py", "app/demo_access.py"]),
    _node("web", "Web UI + JSON API", "Routes and templates", "app", 270, 160, 260, 60,
          "Request handlers that turn HTTP calls into service calls.",
          ["Pages: dashboard, open and closed positions, trades, import holdings, market data, news, MCP Console, audit",
           "JSON API under /api for scripts and tests"],
          files=["app/routes/web.py", "app/routes/api.py"]),
    _node("svc", "Services layer", "All business logic", "app", 270, 240, 260, 60,
          "The single place where business rules live, shared by the UI, the API and every MCP server.",
          ["Average-cost accounting with realized and unrealized P&L",
           "Rules such as: a trade reason is required, and you cannot sell more than you hold",
           "Portfolio, market data, news, order preview and broker services"],
          files=["app/services/portfolio.py", "app/services/orders.py", "app/services/news.py"]),
    _node("host", "MCP host (client)", "App calls its own servers", "app", 270, 320, 260, 60,
          "The app is also an MCP client: it uses short-lived MCP sessions to fetch market data and news from its own servers.",
          ["One session per call: initialize, run one operation, close",
           "Uses httpx ASGITransport so there is no network hop",
           "Forwards the correlation ID and logs calls as internal MCP client requests"],
          files=["app/services/mcp_host.py"]),

    # ---- MCP servers ----
    _node("s_journal", "Trading Journal", "/mcp/ · 6 tools", "mcp", 615, 80, 160, 60,
          "Read and write access to accounts, positions and trades.",
          lists=[("Tools", ["get_portfolio_summary", "list_accounts", "list_positions", "list_trades", "add_opening_holding", "add_manual_trade"]),
                 ("Resources", ["portfolio://summary", "portfolio://positions"]),
                 ("Prompts", ["daily_portfolio_review", "journal_follow_up"])],
          details=["add_manual_trade requires a written reason"], files=["app/mcp_servers/portfolio.py"]),
    _node("s_market", "Market Data", "/market-data-mcp/ · 3 tools", "mcp", 615, 160, 160, 60,
          "Live quote snapshots from Alpaca for stocks, ETFs and options.",
          lists=[("Tools", ["get_market_data_capabilities", "get_equity_snapshots", "get_option_snapshots"]),
                 ("Resources", ["market-data://capabilities"]), ("Prompts", ["market_data_health_check"])],
          files=["app/mcp_servers/market_data.py"]),
    _node("s_news", "News", "/news-mcp/ · 3 tools", "mcp", 615, 240, 160, 60,
          "Recent headlines for a symbol or for the whole portfolio.",
          lists=[("Tools", ["get_news_capabilities", "get_symbol_news", "get_portfolio_news"]),
                 ("Resources", ["news://capabilities"]), ("Prompts", ["portfolio_news_review"])],
          details=["Headlines are third-party text: treat them as data, never as instructions"],
          files=["app/mcp_servers/news.py"]),
    _node("s_broker", "Broker", "/broker-mcp/ · scaffold", "mcp", 615, 320, 160, 60,
          "Placeholder for future brokerage sync. Reports status only.",
          lists=[("Tools", ["get_broker_status", "list_broker_accounts"]),
                 ("Resources", ["broker://status"]), ("Prompts", ["broker_sync_readiness"])],
          files=["app/mcp_servers/broker.py"]),
    _node("s_trading", "Trading", "/trading-mcp/ · preview only", "mcp", 615, 400, 160, 60,
          "Order preview with safety checks. Nothing is ever sent to a broker.",
          lists=[("Tools", ["get_trading_capabilities", "preview_order"]),
                 ("Resources", ["trading://capabilities"]), ("Prompts", ["order_safety_review"])],
          details=["Checks symbol, quantity, trade reason and limit price", "LIVE intent is rejected; paper trading is not implemented yet"],
          files=["app/mcp_servers/trading.py"]),

    # ---- data and providers ----
    _node("d_sqlite", "SQLite", "Journal + audit tables", "data", 840, 80, 130, 60,
          "Local-first database accessed through SQLAlchemy 2.",
          ["Core tables: accounts, instruments, trades, positions",
           "Audit tables: user actions, MCP requests, external API calls, application events",
           "Money values stored as Decimal"],
          files=["app/models/entities.py", "app/db.py"]),
    _node("d_alpaca", "Alpaca", "Market data API", "data", 840, 160, 130, 60,
          "Source of equity and option snapshots.",
          ["Free iex and indicative feeds work for demos; sip and opra need an entitlement",
           "API keys are saved to a git-ignored local settings file and never shown back",
           "Mutual funds and bonds are not covered, so they use manual mark prices"],
          files=["app/providers/market_data/alpaca.py"]),
    _node("d_yahoo", "Yahoo Finance", "News provider", "data", 840, 240, 130, 60,
          "Default news source.",
          ["GDELT or a deterministic demo provider can be selected with TRADING_JOURNAL_NEWS_PROVIDER",
           "Demo mode is handy for presentations with no internet dependency"],
          files=["app/providers/news/", "app/services/news.py"]),
    _node("d_ibkr", "IBKR", "Placeholder adapter", "data", 840, 320, 130, 60,
          "A BrokerProvider protocol and an IBKR stub; no live brokerage connection exists yet.",
          ["Designed so a real sync can be added without changing the rest of the app"],
          files=["app/providers/broker/base.py", "app/providers/broker/ibkr.py"]),
    _node("d_gate", "Order preview", "Safety gate", "data", 840, 400, 130, 60,
          "Preview-only order service behind the Trading server.",
          ["Always returns status preview_only", "Broker submission is not implemented"],
          files=["app/services/orders.py"]),

    # ---- cross-cutting ----
    _node("audit", "Audit and observability", "Correlation IDs · four log tables · secret redaction", "cross", 250, 505, 730, 55,
          "Every request, MCP call and external API call is recorded and can be traced end to end.",
          ["One correlation ID ties a click to its MCP calls and provider calls",
           "Keys, tokens, cookies and passwords are stored as [REDACTED]",
           "Browse the records on the Audit Logs page"],
          files=["app/audit/", "app/templates/audit.html"]),
]

EDGES: list[dict[str, Any]] = [
    {"from": "browser", "to": "mw", "x1": 200, "y1": 110, "x2": 270, "y2": 110},
    {"from": "mw", "to": "web", "x1": 400, "y1": 140, "x2": 400, "y2": 160},
    {"from": "web", "to": "svc", "x1": 400, "y1": 220, "x2": 400, "y2": 240},
    {"from": "svc", "to": "host", "x1": 400, "y1": 300, "x2": 400, "y2": 320},
    {"from": "host", "to": "g_mcp", "x1": 530, "y1": 350, "x2": 600, "y2": 350, "label": "MCP"},
    {"from": "cli", "to": "g_mcp", "x1": 200, "y1": 455, "x2": 600, "y2": 455, "label": "Streamable HTTP"},
    {"from": "s_journal", "to": "d_sqlite", "x1": 775, "y1": 110, "x2": 840, "y2": 110},
    {"from": "s_market", "to": "d_alpaca", "x1": 775, "y1": 190, "x2": 840, "y2": 190},
    {"from": "s_news", "to": "d_yahoo", "x1": 775, "y1": 270, "x2": 840, "y2": 270},
    {"from": "s_broker", "to": "d_ibkr", "x1": 775, "y1": 350, "x2": 840, "y2": 350},
    {"from": "s_trading", "to": "d_gate", "x1": 775, "y1": 430, "x2": 840, "y2": 430},
]


def get_architecture() -> dict[str, Any]:
    return {"canvas": CANVAS, "nodes": NODES, "edges": EDGES}
