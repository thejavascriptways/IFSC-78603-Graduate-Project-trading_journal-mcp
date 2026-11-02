# MCP Concepts And Trading Journal Presentation

Updated: November 1, 2026.

[Open the restored Alpaca presentation](trading_journal_mcp_alpaca.pptx), or use `Configuration > Documentation > Open / Download Slides` in the running app.

The app now reuses the existing eight-slide Alpaca architecture deck. It illustrates Alpaca quotes and Yahoo news. Current configuration, source timestamps, and feed limits are documented in the Market Data Workflow:

| Slide | Topic |
|---|---|
| 1 | MCP overview |
| 2 | Hosts, clients, servers, tools, resources, and prompts |
| 3 | Connection, discovery, invocation, and result lifecycle |
| 4 | Multiple clients sharing MCP capabilities |
| 5 | Trading Journal topology with Alpaca market data and Yahoo news |
| 6 | Internal web client and independent CLI accessing the same Market Data MCP tools |
| 7 | Implemented capabilities, audit layer, and broker/trading boundaries |
| 8 | MCP and project references |

## Talking Points For The Provider Change

Alpaca supplies requested snapshots using saved API keys. Yahoo Finance supplies news separately. MCP standardizes discovery and invocation; it is not the market-data source itself. Changing the provider therefore does not require changing the client tool calls or adding another MCP server.

Show provider, feed, and `As Of` in `Portfolio > Market Data`. Explain that IEX covers one exchange, indicative options are not OPRA exchange quotes, and continuous streaming and quote/news persistence remain future work. Yahoo quotes are retained as an explicit optional adapter.

```bash
python3 scripts/mcp_demo_client.py --server market discover
python3 scripts/mcp_demo_client.py market-check --symbols AAPL,MSFT
```

Speaker notes contain implementation references and source links. See [Market Data Workflow](../market_data_workflow.md) and the [technical white paper](../mcp_use_case_white_paper.md) for details. The October [Yahoo revision](trading_journal_mcp_yahoo.pptx) is historical. The restored Alpaca deck is the current in-app download.
