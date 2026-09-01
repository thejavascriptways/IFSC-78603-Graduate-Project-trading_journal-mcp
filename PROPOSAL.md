# Trading Journal: An MCP-Based Portfolio and Trade Journal Platform

## Introduction

Model Context Protocol (MCP) is an open standard that allows an application to connect AI models to external tools, data sources, and reusable prompts through a consistent interface. Instead of building one-off integrations for every system, MCP gives developers a structured way to expose capabilities such as account data, portfolio summaries, market quotes, and trade-entry actions. For a project like a trading journal, this is especially useful because the application can be designed not only as a normal web app, but also as a system whose portfolio data and workflows can be accessed by MCP clients in a clean and inspectable way.

This project proposes the design and continued development of **Trading Journal**, a Python-based portfolio and trade-journaling application inspired by the usability of retail brokerage portfolio tools such as Fidelity. The project has two goals. The first goal is academic and technical: to understand how MCP works in practice by building both MCP servers and client behavior inside a real application. The second goal is practical: to create a day-to-day portfolio journal that helps a user track holdings, record trades, view profit and loss, and capture the reasoning behind each trade.

At the current stage, the application already supports manual trade entry, tracking of open and closed positions, realized and unrealized profit/loss calculations, account-level organization, and integration with external market data for supported instruments. The proposed project expands this foundation into a more complete MCP-oriented system, where the application itself becomes a live example of how structured AI connectivity can improve financial journaling and portfolio analysis.

## Summary of the Proposal

The proposal is to develop **Trading Journal** as a full-stack Python application that combines portfolio management, trade journaling, and MCP-based interoperability. The system will allow a user to manually import current holdings, enter buy and sell trades, close positions, and review both realized and unrealized performance. In addition to standard portfolio fields, every trade will include a required "reason for trade" field so that the platform functions as both an investment tracker and a decision journal. This makes the application more valuable than a basic ledger because it captures the thinking behind investment behavior, which can later be reviewed for learning and performance improvement.

From a systems perspective, the project is also a working study of MCP architecture. The current design already separates responsibilities into MCP-exposed services: one MCP server for portfolio and journaling operations, and another MCP server for market-data access. The application can act as an MCP client to call these services internally, and a lightweight MCP inspection interface can be added so that a user can observe tools, resources, and prompts without relying only on command-line tests. This structure makes the project suitable for demonstrating how MCP can be used in a realistic software system rather than in a toy example.

The proposal also includes the use of live external market data for supported instruments, beginning with an API-based provider appropriate for a Python application. In the current design direction, live market data is used for stocks, ETFs, and supported options contracts, while mutual funds and bonds may initially rely on delayed, daily, or manual valuation methods depending on provider limitations. This keeps the proposal realistic, technically achievable, and honest about data availability constraints in the financial domain.

## Scope of the Project

The proposed project scope includes the following implementation goals:

1. Build a Python-based web application for portfolio tracking and trade journaling using a clean service-oriented architecture.

2. Support manual import of existing holdings and manual entry of new trades, including buy and sell transactions across multiple account types.

3. Track open positions and closed positions separately, and calculate overall realized profit/loss, overall unrealized profit/loss, profit/loss percentages, profit/loss by account, and profit/loss by account and asset class.

4. Add a required journal field for the user’s reason for each trade, so the system records not only what was traded, but why it was traded.

5. Integrate live external market data for supported securities, initially focusing on stocks, ETFs, and options where real-time or near-real-time feeds are available through the chosen provider.

6. Expose portfolio features through an MCP server so MCP clients can discover and use tools such as account listing, trade entry, position review, and portfolio summary retrieval.

7. Expose market-data features through a separate MCP server so that quote and snapshot functionality can be treated as a modular external capability.

8. Implement MCP client behavior inside the application so the web app can consume MCP tools and demonstrate how client-server communication works in practice.

9. Provide a lightweight client-side MCP inspection interface for learning purposes, allowing a user to view available tools, resources, and prompts and observe MCP behavior without depending entirely on terminal commands.

10. Design the system so it can later be extended for internet deployment, stronger authentication, automated brokerage synchronization, richer analytics, and additional asset-class coverage.

The project will intentionally begin with a manageable first version. The first version emphasizes usability, correctness of trade and P&L logic, and a clear demonstration of MCP concepts. More advanced brokerage syncing, multi-user deployment, and production security controls are considered future extensions rather than part of the initial academic scope.

## References

1. Model Context Protocol, Introduction: [https://modelcontextprotocol.io/docs/getting-started/intro](https://modelcontextprotocol.io/docs/getting-started/intro)
2. Model Context Protocol, Specification: [https://modelcontextprotocol.io/specification/2025-06-18](https://modelcontextprotocol.io/specification/2025-06-18)
3. FastMCP Documentation: [https://gofastmcp.com/getting-started/welcome](https://gofastmcp.com/getting-started/welcome)
4. FastAPI Documentation: [https://fastapi.tiangolo.com/](https://fastapi.tiangolo.com/)
5. SQLAlchemy Documentation: [https://docs.sqlalchemy.org/](https://docs.sqlalchemy.org/)
6. Alpaca Documentation, Getting Started: [https://docs.alpaca.markets/us/docs/getting-started](https://docs.alpaca.markets/us/docs/getting-started)
7. Alpaca Documentation, Market Data API: [https://docs.alpaca.markets/us/docs/about-market-data-api](https://docs.alpaca.markets/us/docs/about-market-data-api)
8. Alpaca Market Data Overview: [https://alpaca.markets/data](https://alpaca.markets/data)
