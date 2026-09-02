# Trading Journal Prototype Baseline

Baseline date: 2026-08-31

## 1. Purpose

This document freezes the accepted prototype behavior before the real application refactor begins. Future implementation work should preserve these baseline capabilities unless we intentionally replace them with a better version.

This is not a production release. It is the working prototype that was accepted as preliminary project work.

## 2. Repository Status

The current project directory is not initialized as a Git repository, so this freeze is documented through:

- A written baseline in this file.
- Existing automated tests.
- The current requirements and implementation planning documents.

If Git is added later, this baseline should become the first meaningful commit/tag before major refactoring.

## 3. Current Application Stack

The prototype currently uses:

- Python.
- FastAPI.
- Jinja2 templates.
- SQLite.
- SQLAlchemy.
- Pydantic.
- MCP Python SDK/FastMCP.
- HTTPX.
- Uvicorn.
- Pytest.

## 4. Current User-Facing Pages

The prototype exposes these main browser pages:

- `/`: dashboard with accounts, open positions, closed positions, recent trades, and P&L tables.
- `/holdings/import`: opening holding import form for manually entered existing holdings.
- `/trades/new`: manual trade entry form.
- `/trades`: trade history.
- `/positions`: open positions, mark price updates, and market-data refresh.
- `/positions/closed`: closed positions and realized P&L.
- `/market-data`: live market-data table for current portfolio symbols.
- `/mcp-console`: browser-based MCP console route exists in the app routes.

## 5. Current API Endpoints

The prototype exposes these JSON API endpoints:

- `GET /api/accounts`
- `GET /api/portfolio-summary`
- `GET /api/positions`
- `GET /api/closed-positions`
- `GET /api/trades`
- `GET /api/market-data/live`
- `POST /api/trades`
- `POST /api/opening-holdings`
- `POST /api/positions/{position_id}/mark`
- `POST /api/positions/refresh-market-data`
- `GET /api/mcp-console/servers`
- `GET /api/mcp-console/catalog`
- `POST /api/mcp-console/call-tool`
- `POST /api/mcp-console/read-resource`
- `POST /api/mcp-console/get-prompt`

## 6. Current Database Entities

The prototype currently has these main database models:

- `Account`
- `Instrument`
- `Trade`
- `Position`

Current enum coverage:

- Account source: `IBKR`, `MANUAL`
- Asset class: `STOCK`, `ETF`, `MUTUAL_FUND`, `BOND`, `OPTION`, `CASH`
- Order side: `BUY`, `SELL`
- Trade origin: `OPENING`, `MANUAL`, `IMPORTED`

## 7. Current Portfolio Behavior

The prototype supports:

- Default account seeding for `IBKR Live` and `Manual Fidelity`.
- Manual opening holding import.
- Manual buy trade entry.
- Manual sell trade entry.
- Required trade reason on manual trades.
- Position creation/update from trades.
- Average-cost accounting.
- Partial sells.
- Full position closes.
- Closed position summaries.
- Manual market price updates.
- Realized P&L on sells.
- Unrealized P&L on open positions.
- Overall, account-level, and account plus asset-class P&L summaries.

Accounting baseline:

- Buy trades increase quantity and cost basis.
- Average cost is recalculated after buys.
- Sell trades cannot exceed current quantity.
- Sell trades calculate realized P&L as sale proceeds minus removed average cost.
- Full sells set position quantity and cost basis to zero.
- Open positions are listed when quantity is non-zero.
- Closed positions are listed when quantity is zero.

## 8. Current Market Data Behavior

The prototype includes a Market Data MCP server backed by Alpaca configuration.

Supported behavior:

- Reads `ALPACA_API_KEY_ID`.
- Reads `ALPACA_API_SECRET_KEY`.
- Reads `ALPACA_STOCK_FEED`.
- Reads `ALPACA_OPTION_FEED`.
- Fetches stock/ETF snapshots through Alpaca stock snapshots.
- Fetches option snapshots through Alpaca option snapshots.
- Builds live market-data rows for open and closed portfolio symbols.
- Refreshes open-position marks by calling the Market Data MCP server through an internal MCP client.
- Displays asset-class limitations for mutual funds, bonds, and cash.

Known market-data limits:

- Stocks and ETFs depend on Alpaca feed access.
- Options require correct entitlement for true OPRA-quality data.
- Mutual funds are generally NAV-based, not live intraday.
- Bonds are not covered by the Alpaca stock/options quote feeds.
- Missing symbols return a user-facing no-data message.

## 9. Current MCP Architecture

The prototype already demonstrates both MCP server and MCP client behavior.

Current MCP servers:

- Trading Journal MCP mounted at `/mcp/`.
- Market Data MCP mounted at `/market-data-mcp/`.

After Step 2 architecture scaffolding, the app also mounts safe placeholder MCP domains for future work:

- News MCP mounted at `/news-mcp/`.
- Broker MCP mounted at `/broker-mcp/`.
- Trading MCP mounted at `/trading-mcp/`.

These additional servers are discoverable architecture scaffolding. They do not add real broker sync or live trading yet.

Current internal MCP client behavior:

- The FastAPI app calls the Market Data MCP server over Streamable HTTP using the MCP Python client.
- This happens when refreshing market-data marks for open positions.

Current external MCP client behavior:

- `scripts/mcp_demo_client.py` acts as a separate command-line MCP client.
- It can discover MCP tools, resources, and prompts.
- It can call tools, read resources, and get prompts from the prototype MCP servers.

## 10. Current Trading Journal MCP Server

Current tools:

- `get_portfolio_summary`
- `list_accounts`
- `list_positions`
- `list_trades`
- `add_opening_holding`
- `add_manual_trade`

Current resources:

- `portfolio://summary`
- `portfolio://positions`

Current prompts:

- `daily_portfolio_review`
- `journal_follow_up`

## 11. Current Market Data MCP Server

Current tools:

- `get_market_data_capabilities`
- `get_equity_snapshots`
- `get_option_snapshots`

Current resources:

- `market-data://capabilities`

Current prompts:

- `market_data_health_check`

## 12. Current CLI MCP Demo Commands

The current MCP demo client supports:

- `python3 scripts/mcp_demo_client.py explain`
- `python3 scripts/mcp_demo_client.py servers`
- `python3 scripts/mcp_demo_client.py discover`
- `python3 scripts/mcp_demo_client.py tools`
- `python3 scripts/mcp_demo_client.py resources`
- `python3 scripts/mcp_demo_client.py prompts`
- `python3 scripts/mcp_demo_client.py summary`
- `python3 scripts/mcp_demo_client.py call <tool> --arguments '<json>'`
- `python3 scripts/mcp_demo_client.py read-resource <uri>`
- `python3 scripts/mcp_demo_client.py get-prompt <prompt> --arguments '<json>'`
- `python3 scripts/mcp_demo_client.py portfolio-review --focus risk`
- `python3 scripts/mcp_demo_client.py --server market discover`
- `python3 scripts/mcp_demo_client.py market-check --symbols AAPL,MSFT`
- `python3 scripts/mcp_demo_client.py client-demo`

The CLI already accepts `--base-url`, so it can target local or future deployed app URLs.

## 13. Current Test Baseline

The test suite was run during this freeze step.

Result:

- `8 passed`

Command:

```bash
python3 -m pytest
```

Covered behavior:

- Manual trade updates positions.
- Trade reason is required.
- Opening holding import seeds positions.
- Duplicate opening holding import is rejected.
- Partial sell updates quantity, cost basis, and realized P&L.
- Manual mark price updates unrealized P&L.
- Full close moves a position to closed history.
- Dashboard summary reports overall/account/account-plus-asset-class P&L.
- Trading Journal MCP server exposes tools/resources and portfolio state.
- Market Data MCP server exposes live tools and provider capabilities.

## 14. Known Prototype Limitations

The prototype does not yet include:

- Full audit logging.
- Correlation IDs.
- User action logs.
- MCP request logs.
- External API call logs.
- Production news provider integration.
- Real broker provider integration.
- IBKR account sync.
- Order staging.
- Paper trading.
- Live trading.
- Authentication.
- Public demo mode.
- Modern cold-theme UI refresh.
- Production deployment configuration.
- Database migrations.
- Robust multi-user security.

## 15. Freeze Rule For Future Work

Future implementation should preserve this baseline unless there is an intentional replacement.

Before and after each major change:

1. Run `python3 -m pytest`.
2. Confirm the dashboard still loads.
3. Confirm manual holding import still works.
4. Confirm manual buy/sell trade entry still works.
5. Confirm closed positions and P&L still calculate correctly.
6. Confirm MCP discovery still works for `/mcp/` and `/market-data-mcp/`.

This gives us a stable foundation for the real application build.
