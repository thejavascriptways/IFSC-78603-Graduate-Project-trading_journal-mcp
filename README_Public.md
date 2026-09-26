# Trading Journal MCP Public Demo README

This README explains how to run the Trading Journal MCP application locally and expose it temporarily through a public URL for a professor or class demo.

This is not a production deployment. It is a short-term demo path where your Mac runs the application and a tunnel service creates a temporary public HTTPS URL.

## What The Public Demo Shows

The public URL exposes the same local application running at `http://127.0.0.1:8000`.

Demo visitors can see:

- Trading Journal dashboard.
- Open positions and closed positions.
- Realized and unrealized profit/loss reporting.
- Manual trade and holding workflows.
- Market data page.
- MCP Console.
- Audit Logs.
- MCP endpoints for external client demonstrations.

Public MCP endpoint pattern:

| MCP Server | Public Endpoint |
|---|---|
| Trading Journal MCP | `https://your-temporary-url/mcp/` |
| Market Data MCP | `https://your-temporary-url/market-data-mcp/` |
| News MCP | `https://your-temporary-url/news-mcp/` |
| Broker MCP | `https://your-temporary-url/broker-mcp/` |
| Trading MCP | `https://your-temporary-url/trading-mcp/` |

## Safety Rules

Use the public URL only for a controlled demo window.

- Use sample data when possible.
- Do not use real broker credentials in a public demo.
- Do not enable live trading.
- Use Alpaca paper/demo keys only if market data is needed.
- Share the temporary URL only with the intended reviewer.
- Share the temporary demo password separately.
- Stop the tunnel as soon as the demo is finished.
- Never commit `.env`, `instance/`, API keys, or `trading_journal.db`.

## Step 1: Start The Local App With Demo Password Protection

From the project folder:

```bash
cd /Users/deepaksingla/Documents/Trading/TradeAnalyser
source .venv/bin/activate
export TRADING_JOURNAL_DEMO_USERNAME="demo"
export TRADING_JOURNAL_DEMO_PASSWORD="choose-a-temporary-demo-password"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open the local app first:

```text
http://127.0.0.1:8000/
```

Login:

```text
Username: demo
Password: choose-a-temporary-demo-password
```

If the password prompt does not appear, stop the server and confirm that `TRADING_JOURNAL_DEMO_PASSWORD` is set before starting `uvicorn`.

## Step 2: Open A Temporary Public Tunnel

Open a second terminal window and run:

```bash
ssh -R 80:localhost:8000 nokey@localhost.run
```

If SSH asks to trust the host key, use:

```bash
ssh -o StrictHostKeyChecking=accept-new -R 80:localhost:8000 nokey@localhost.run
```

`localhost.run` prints a public URL similar to:

```text
https://some-name.lhr.life
```

That URL is the temporary public demo URL. It works only while the SSH tunnel command is running.

## Step 3: Share Demo Access

Share this information with the professor:

```text
URL: https://some-name.lhr.life
Username: demo
Password: choose-a-temporary-demo-password
```

The professor can open the web application directly in a browser.

## Step 4: Demonstrate MCP From The Public URL

Run the CLI client against the public URL:

```bash
python3 scripts/mcp_demo_client.py --base-url https://some-name.lhr.life --demo-password "choose-a-temporary-demo-password" explain
python3 scripts/mcp_demo_client.py --base-url https://some-name.lhr.life --demo-password "choose-a-temporary-demo-password" servers
python3 scripts/mcp_demo_client.py --base-url https://some-name.lhr.life --demo-password "choose-a-temporary-demo-password" discover
python3 scripts/mcp_demo_client.py --base-url https://some-name.lhr.life --demo-password "choose-a-temporary-demo-password" client-demo
```

These commands show that an external MCP client can discover and use the application capabilities through the public URL.

## Step 5: Suggested Professor Demo Flow

1. Open the public URL and log in.
2. Show the dashboard and explain the overall portfolio summary.
3. Open `Portfolio > Open Positions`.
4. Open `Portfolio > Closed Positions` and show realized P&L.
5. Open `Trading > Add Trade` and explain trade-reason journaling.
6. Open `Configuration > MCP Console`.
7. Discover the Trading Journal MCP server.
8. Call a portfolio MCP tool or read a portfolio MCP resource.
9. Open `Configuration > Audit Logs` and show that requests are logged.
10. Run the CLI `client-demo` command to prove that a separate client can call MCP endpoints.

## Step 6: Stop Public Access

Stop the tunnel terminal:

```text
Control-C
```

After the tunnel stops, the public URL no longer works.

You can also stop the local app:

```text
Control-C
```

## Important Notes

- A new tunnel usually creates a new URL.
- The public URL is temporary.
- The app stays protected by HTTP Basic authentication while `TRADING_JOURNAL_DEMO_PASSWORD` is set.
- The public URL should not be left running unattended.
- This demo path is separate from the future cloud deployment plan.

