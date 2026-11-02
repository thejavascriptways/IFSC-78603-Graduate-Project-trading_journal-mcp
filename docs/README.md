# Trading Journal Documentation

Last aligned with the implementation: November 1, 2026.

Alpaca supplies market-data snapshots by default using saved API keys. Yahoo Finance supplies Stock News and remains an optional demo quote adapter. The October Yahoo-default experiment is historical. MCP tools and endpoint names remain unchanged.

## Current Guides

| Material | Use |
|---|---|
| [Main README](../README.md) | Install, start, and use the local app and CLI |
| [Market Data Workflow](market_data_workflow.md) | Alpaca setup, request diagram, source timestamps, errors, code map, provider switching |
| [Application Requirements](application_requirements.md) | Current demo requirements and future product goals |
| [Architecture Plan](architecture_plan.md) | Web/CLI MCP paths, services, provider adapters, and storage |
| [Implementation Roadmap](implementation_plan.md) | Milestone status and remaining work |
| [Technical White Paper](mcp_use_case_white_paper.md) | MCP case study, provider contracts, evaluation evidence, limitations, references |
| [MCP Presentation](presentations/trading_journal_mcp_alpaca.pptx) | Existing Alpaca architecture deck restored as the current download |
| [Presentation Guide](presentations/README.md) | Slide outline, current data limits, and demo commands |
| [Public Demo README](../README_Public.md) | Password-protected temporary public demonstration |
| [Local Tunnel Runbook](local_tunnel_demo.md) | Start, verify, share, and stop the temporary tunnel |
| [Deployment Plan](deployment_plan.md) | Local and hosted deployment planning; hosting comparisons are historical research |

## In-App Documentation

- `Architecture` (`/architecture`): interactive component diagram contributed through the merged GitHub PR, available alongside the existing documentation and workflow pages.
- `Configuration > Documentation` (`/documentation`): current slides and downloadable technical white paper.
- `Configuration > Workflow Map` (`/workflow`): graphical request paths and implementation boundaries.
- `Configuration > Market Data Settings` (`/settings/market-data`): active provider, setup requirements, and Alpaca key management.
- `Configuration > MCP Console` (`/mcp-console`): discover and call the unchanged MCP capabilities.

## Historical Records

- [Accepted Proposal](proposal/README.md): submitted PDF and Word files, preserved as accepted.
- [Implementation Addendum](proposal/market_data_implementation_addendum.md): records the Yahoo experiment and restoration of Alpaca.
- [Prototype Baseline](prototype_baseline.md): frozen behavior, with a clearly labeled current-change notice.
- [Earlier Proposal Draft](../PROPOSAL.md): historical draft, not the accepted proposal.

The app serves the existing Alpaca deck from `docs/presentations/trading_journal_mcp_alpaca.pptx`. The Yahoo deck is retained as the historical October revision. Current provider details are in the Market Data Workflow.

## Interpretation

The app requests snapshots rather than streaming continuously. Alpaca IEX stocks cover one exchange; indicative options are labeled `INDICATIVE`. Bid/ask appears when supplied. Optional Yahoo charts use `SNAPSHOT` and omit bid/ask. Individual bonds and mutual-fund NAV lookup remain unsupported. Persistence, freshness thresholds, caching, and production validation remain roadmap work.

## Verification

The November integration with GitHub main preserves the new Architecture page and the existing Workflow Map, Documentation downloads, and their responsive styles. The architecture integration test checks that these pages, navigation links, and stylesheet sections coexist. After integration, `python3 -m pytest -q` reported **54 passed in 5.71 seconds**.

On November 1, 2026, `python3 -m pytest -q` reported **52 passed in 5.30 seconds** after restoring Alpaca as the default. The independent `market-check --symbols AAPL,MSFT` CLI demonstrated discovery and returned both Alpaca IEX snapshots with no missing symbols, using the existing saved credentials. The following October verification is historical.

On October 20, 2026, `python3 -m pytest -q` reported **50 passed in 5.35 seconds** after the documentation refresh. This includes download checks for the current Yahoo slide deck and market-data guide, in addition to the provider/MCP integration tests. All relative Markdown file links in the maintained documentation resolved locally. The revised eight-slide deck passed package/layout checks and was rendered for visual inspection.

These checks establish local document availability and functional examples, not market-feed uptime, a latency guarantee, or production readiness. The [white paper](mcp_use_case_white_paper.md#173-reporting-observations) separately records the earlier provider implementation tests and real Yahoo CLI/browser observations.
