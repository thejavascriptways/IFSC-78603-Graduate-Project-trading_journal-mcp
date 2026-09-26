# Local Tunnel Professor Demo Runbook

This runbook is for the short-term professor demo path: run Trading Journal MCP on your Mac and expose it temporarily through a public HTTPS tunnel.

Use this path when you want the professor to see the real working prototype without setting up a cloud deployment yet.

## 1. What This Demonstrates

The tunnel exposes the same local FastAPI application that you use at `http://127.0.0.1:8000`.

After the tunnel starts, the professor can access:

| Capability | Local URL | Public URL Pattern |
|---|---|---|
| Web UI | `http://127.0.0.1:8000/` | `https://your-tunnel-url/` |
| Trading Journal MCP | `http://127.0.0.1:8000/mcp/` | `https://your-tunnel-url/mcp/` |
| Market Data MCP | `http://127.0.0.1:8000/market-data-mcp/` | `https://your-tunnel-url/market-data-mcp/` |
| News MCP | `http://127.0.0.1:8000/news-mcp/` | `https://your-tunnel-url/news-mcp/` |
| Broker MCP | `http://127.0.0.1:8000/broker-mcp/` | `https://your-tunnel-url/broker-mcp/` |
| Trading MCP | `http://127.0.0.1:8000/trading-mcp/` | `https://your-tunnel-url/trading-mcp/` |
| Audit Logs | `http://127.0.0.1:8000/audit` | `https://your-tunnel-url/audit` |
| MCP Console | `http://127.0.0.1:8000/mcp-console` | `https://your-tunnel-url/mcp-console` |

## 2. Demo Safety Checklist

Before sharing a tunnel URL:

- Use sample/demo data when possible.
- Do not enter real broker credentials in a public demo.
- Keep live trading disabled.
- Prefer Alpaca paper/demo keys if market data is needed.
- Keep the tunnel open only during the demo.
- Stop the tunnel immediately after the demo with `Control-C`.
- Do not commit `instance/`, `.env`, API keys, or `trading_journal.db` to GitHub.

## 3. Start The Local App

For a public tunnel demo, start the app with a temporary demo password:

From the project folder:

```bash
cd /Users/deepaksingla/Documents/Trading/TradeAnalyser
source .venv/bin/activate
export TRADING_JOURNAL_DEMO_USERNAME="demo"
export TRADING_JOURNAL_DEMO_PASSWORD="choose-a-temporary-demo-password"
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open this local URL first and confirm the app works:

```text
http://127.0.0.1:8000/
```

Your browser should ask for a username and password. Use:

```text
Username: demo
Password: choose-a-temporary-demo-password
```

## 4. Option A: No-Install Tunnel With localhost.run

This is the fastest option because macOS already includes `ssh`.

Open a second terminal window and run:

```bash
ssh -R 80:localhost:8000 nokey@localhost.run
```

The command prints a public HTTPS URL. It usually looks similar to:

```text
https://some-name.lhr.life
```

Use that URL as the professor demo link.

Example MCP demo command using the public URL:

```bash
python3 scripts/mcp_demo_client.py --base-url https://some-name.lhr.life --demo-password "choose-a-temporary-demo-password" discover
```

Notes:

- The URL can change each time you start the tunnel.
- The tunnel stays active only while the SSH command is running.
- If the SSH connection drops, restart the command and share the new URL.

## 5. Option B: ngrok Tunnel

Use this if you want a cleaner tunnel dashboard and optional stable domain features.

Install ngrok from:

```text
https://ngrok.com/download
```

Then run:

```bash
ngrok http 8000
```

ngrok prints a forwarding URL similar to:

```text
https://abc123.ngrok-free.app
```

Example MCP demo command:

```bash
python3 scripts/mcp_demo_client.py --base-url https://abc123.ngrok-free.app --demo-password "choose-a-temporary-demo-password" client-demo
```

## 6. Option C: Cloudflare Quick Tunnel

Use this if `cloudflared` is installed.

```bash
cloudflared tunnel --url http://127.0.0.1:8000
```

Cloudflare prints a temporary public URL. Use that as the professor demo URL.

## 7. Professor Demo Script

Suggested demo flow:

1. Open the public tunnel URL and show the dashboard.
2. Show positions, closed positions, and profit/loss reporting.
3. Open `Configuration > MCP Console`.
4. Discover the Trading Journal MCP server.
5. Call portfolio summary and list positions from MCP Console.
6. Open `Configuration > Audit` and show that UI actions and MCP actions are logged.
7. Run the CLI against the public URL:

```bash
python3 scripts/mcp_demo_client.py --base-url https://your-tunnel-url.example --demo-password "choose-a-temporary-demo-password" explain
python3 scripts/mcp_demo_client.py --base-url https://your-tunnel-url.example --demo-password "choose-a-temporary-demo-password" servers
python3 scripts/mcp_demo_client.py --base-url https://your-tunnel-url.example --demo-password "choose-a-temporary-demo-password" discover
python3 scripts/mcp_demo_client.py --base-url https://your-tunnel-url.example --demo-password "choose-a-temporary-demo-password" client-demo
```

## 8. Stop The Demo

Stop the tunnel terminal:

```text
Control-C
```

Stop the FastAPI server terminal:

```text
Control-C
```

After both commands stop, the public URL no longer reaches the local app.
