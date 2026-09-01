# Trading Journal

`Trading Journal` is a local-first Python application for tracking portfolios, recording manual trades, and preparing for broker sync and MCP exposure in later phases.

## What is included in this starter build

- FastAPI backend with a simple HTML interface
- SQLite-backed portfolio database
- Default account types for `IBKR Live` and `Manual Fidelity`
- Opening holding import flow for current Fidelity positions
- Manual trade entry flow with required trade reason
- Close-position workflow with prefilled sell entries
- Position updates and realized P&L using average-cost accounting
- Manual mark-price updates for unrealized P&L on open positions
- External live market-data page for open and closed positions
- Refresh open-position marks by calling a second MCP server backed by Alpaca market data
- Dashboard P&L tables for overall, by account, and by account plus asset class
- JSON API endpoints and a mounted MCP server over the same portfolio service layer

## Quick start

1. Create a virtual environment and activate it.
2. Install the project:

```bash
python3 -m pip install -e ".[dev]"
```

3. Set your external market-data credentials:

```bash
export ALPACA_API_KEY_ID="your-key-id"
export ALPACA_API_SECRET_KEY="your-secret-key"
export ALPACA_STOCK_FEED="iex"
export ALPACA_OPTION_FEED="indicative"
```

4. Run the app:

```bash
uvicorn app.main:app --reload
```

5. Open [http://127.0.0.1:8000](http://127.0.0.1:8000).

The database defaults to `sqlite:///./trading_journal.db`. Set `TRADING_JOURNAL_DATABASE_URL` to change it.
If you have Alpaca real-time entitlements, you can switch to `ALPACA_STOCK_FEED=sip` and `ALPACA_OPTION_FEED=opra`.

## MCP endpoint

The app now mounts two MCP servers:

- Trading Journal MCP: [http://127.0.0.1:8000/mcp/](http://127.0.0.1:8000/mcp/)
- Market Data MCP: [http://127.0.0.1:8000/market-data-mcp/](http://127.0.0.1:8000/market-data-mcp/)

Use the included command-line MCP client after the app is running. This script acts like a separate external client that discovers and uses the app's MCP capabilities over HTTP.

Explain what the CLI is demonstrating:

```bash
python3 scripts/mcp_demo_client.py explain
```

Show both MCP servers exposed by the app:

```bash
python3 scripts/mcp_demo_client.py servers
```

Discover the Trading Journal MCP server:

```bash
python3 scripts/mcp_demo_client.py discover
python3 scripts/mcp_demo_client.py tools
python3 scripts/mcp_demo_client.py resources
python3 scripts/mcp_demo_client.py prompts
python3 scripts/mcp_demo_client.py summary
python3 scripts/mcp_demo_client.py call list_positions --arguments '{"symbol":"VOO"}'
python3 scripts/mcp_demo_client.py read-resource portfolio://summary
python3 scripts/mcp_demo_client.py get-prompt daily_portfolio_review --arguments '{"focus":"risk"}'
```

Run a guided portfolio MCP workflow:

```bash
python3 scripts/mcp_demo_client.py portfolio-review --focus risk
```

Discover the Market Data MCP server:

```bash
python3 scripts/mcp_demo_client.py --server market discover
python3 scripts/mcp_demo_client.py --server market tools
python3 scripts/mcp_demo_client.py --server market resources
python3 scripts/mcp_demo_client.py --server market prompts
python3 scripts/mcp_demo_client.py --server market call get_market_data_capabilities
python3 scripts/mcp_demo_client.py --server market call get_equity_snapshots --arguments '{"symbols":["AAPL","MSFT"]}'
python3 scripts/mcp_demo_client.py --server market read-resource market-data://capabilities
python3 scripts/mcp_demo_client.py --server market get-prompt market_data_health_check --arguments '{"symbols":"AAPL,MSFT"}'
```

Run a guided market-data MCP workflow:

```bash
python3 scripts/mcp_demo_client.py market-check --symbols AAPL,MSFT
```

Run the complete multi-server demo:

```bash
python3 scripts/mcp_demo_client.py client-demo
```

## MCP topology in this build

This project is now a better MCP example because it has both roles:

- `Trading Journal` is an MCP server for portfolio data and trade actions.
- `Trading Journal` also acts as an MCP client when it refreshes prices from the separate `Market Data MCP` server.
- `Market Data MCP` is a second MCP server whose job is to reach the external Alpaca market-data service.

That means the app is no longer just "a website with one MCP endpoint". It is now a small multi-server MCP system.

## Current workflow

- Review the dashboard
- Import your opening Fidelity holdings
- Open `/market-data` to view live external market data for open and closed positions
- Refresh open positions from `/positions` with `Refresh Quotes via MCP`
- Use the close-position flow or the manual trade entry screen
- Save a trade with a required `trade_reason`
- Review open positions, closed positions, realized P&L, and recent activity
- Explore both MCP servers through the demo client

## Asset-class notes

- Stocks and ETFs can use Alpaca real-time feeds.
- Options require OPRA entitlement for true non-delayed quotes; the `indicative` feed is not equivalent to OPRA.
- Mutual funds generally publish NAV once per business day rather than live intraday quotes.
- Bonds are not covered by the Alpaca stock/options feeds.

## Next implementation phases

- IBKR sync worker and production-grade live market data ingestion
- richer MCP prompts, notifications, and journaling workflows
- Authentication and deployment hardening


## Command line interface commands

- python3 scripts/mcp_demo_client.py explain
- python3 scripts/mcp_demo_client.py servers
- python3 scripts/mcp_demo_client.py discover
- python3 scripts/mcp_demo_client.py portfolio-review --focus risk
- python3 scripts/mcp_demo_client.py --server market discover
- python3 scripts/mcp_demo_client.py market-check --symbols AAPL,MSFT
- python3 scripts/mcp_demo_client.py client-demo