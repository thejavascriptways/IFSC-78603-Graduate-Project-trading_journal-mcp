from __future__ import annotations

import json
from decimal import InvalidOperation
from typing import Any

from mcp.server.fastmcp import FastMCP
from pydantic import ValidationError

from app.db import session_scope
from app.mcp_servers.security import local_transport_security_settings
from app.schemas import ManualTradeCreate, OpeningHoldingCreate
from app.services.portfolio import (
    PortfolioError,
    get_portfolio_summary,
    import_opening_holding,
    list_accounts,
    list_positions,
    list_trades,
    record_manual_trade,
    serialize_account,
    serialize_position,
    serialize_trade,
)


def _normalize_error(exc: Exception) -> ValueError:
    return ValueError(str(exc))


def create_mcp_server() -> FastMCP:
    trading_journal_mcp = FastMCP(
        "Trading Journal MCP",
        instructions=(
            "MCP server for the Trading Journal portfolio app. "
            "Use list_accounts before creating opening holdings or manual trades, "
            "then use positions and trades tools to review the resulting portfolio state."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=local_transport_security_settings(),
    )

    @trading_journal_mcp.tool(name="get_portfolio_summary", structured_output=True)
    def get_portfolio_summary_tool() -> dict[str, Any]:
        """Return a high-level portfolio summary for the current Trading Journal database."""
        with session_scope() as session:
            return get_portfolio_summary(session)

    @trading_journal_mcp.tool(name="list_accounts", structured_output=True)
    def list_accounts_tool() -> list[dict[str, Any]]:
        """List available accounts so MCP clients can choose the correct account_id for writes."""
        with session_scope() as session:
            return [serialize_account(account) for account in list_accounts(session)]

    @trading_journal_mcp.tool(name="list_positions", structured_output=True)
    def list_positions_tool(account_name: str | None = None, symbol: str | None = None) -> list[dict[str, Any]]:
        """List open positions, optionally filtered by account name or symbol."""
        with session_scope() as session:
            positions = [serialize_position(position) for position in list_positions(session)]

        if account_name:
            positions = [position for position in positions if position["account_name"] == account_name]
        if symbol:
            positions = [position for position in positions if position["symbol"] == symbol.strip().upper()]
        return positions

    @trading_journal_mcp.tool(name="list_trades", structured_output=True)
    def list_trades_tool(
        limit: int = 25,
        account_name: str | None = None,
        symbol: str | None = None,
    ) -> list[dict[str, Any]]:
        """List recent trades, optionally filtered by account name or symbol."""
        with session_scope() as session:
            trades = [serialize_trade(trade) for trade in list_trades(session)]

        if account_name:
            trades = [trade for trade in trades if trade["account_name"] == account_name]
        if symbol:
            trades = [trade for trade in trades if trade["symbol"] == symbol.strip().upper()]
        return trades[: max(limit, 0)]

    @trading_journal_mcp.tool(name="add_opening_holding", structured_output=True)
    def add_opening_holding_tool(
        account_id: int,
        symbol: str,
        asset_class: str,
        opening_date: str,
        quantity: str,
        average_cost: str,
        description: str | None = None,
        notes: str | None = None,
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create an opening holding for a manual account and seed the starting position."""
        try:
            payload = OpeningHoldingCreate(
                account_id=account_id,
                symbol=symbol,
                description=description,
                asset_class=asset_class,
                opening_date=opening_date,
                quantity=quantity,
                average_cost=average_cost,
                notes=notes,
                currency=currency,
            )
            with session_scope() as session:
                trade = import_opening_holding(session, payload)
                return serialize_trade(trade)
        except (PortfolioError, ValidationError, InvalidOperation) as exc:
            raise _normalize_error(exc) from exc

    @trading_journal_mcp.tool(name="add_manual_trade", structured_output=True)
    def add_manual_trade_tool(
        account_id: int,
        symbol: str,
        asset_class: str,
        trade_date: str,
        side: str,
        quantity: str,
        price: str,
        reason: str,
        description: str | None = None,
        notes: str | None = None,
        fees: str = "0",
        currency: str = "USD",
    ) -> dict[str, Any]:
        """Create a manual trade with a required trade reason and update positions."""
        try:
            payload = ManualTradeCreate(
                account_id=account_id,
                symbol=symbol,
                description=description,
                asset_class=asset_class,
                trade_date=trade_date,
                side=side,
                quantity=quantity,
                price=price,
                fees=fees,
                reason=reason,
                notes=notes,
                currency=currency,
            )
            with session_scope() as session:
                trade = record_manual_trade(session, payload)
                return serialize_trade(trade)
        except (PortfolioError, ValidationError, InvalidOperation) as exc:
            raise _normalize_error(exc) from exc

    @trading_journal_mcp.resource("portfolio://summary", mime_type="application/json")
    def portfolio_summary_resource() -> str:
        """Read the current portfolio summary as JSON."""
        with session_scope() as session:
            return json.dumps(get_portfolio_summary(session), indent=2)

    @trading_journal_mcp.resource("portfolio://positions", mime_type="application/json")
    def portfolio_positions_resource() -> str:
        """Read the current open positions as JSON."""
        with session_scope() as session:
            payload = [serialize_position(position) for position in list_positions(session)]
        return json.dumps(payload, indent=2)

    @trading_journal_mcp.prompt(
        name="daily_portfolio_review",
        description="Create a daily review prompt using the current Trading Journal portfolio summary.",
    )
    def daily_portfolio_review_prompt(focus: str = "overall") -> str:
        """Build a reusable prompt for reviewing the current portfolio and journal state."""
        with session_scope() as session:
            summary = get_portfolio_summary(session)

        return (
            "Review the current Trading Journal portfolio.\n"
            f"Focus area: {focus}.\n"
            f"Open positions: {summary['open_position_count']}.\n"
            f"Closed positions: {summary['closed_position_count']}.\n"
            f"Unrealized P&L total: {summary['unrealized_pnl_total']}.\n"
            f"Realized P&L total: {summary['realized_pnl_total']}.\n"
            "Explain the most important portfolio observations, identify any concentration or risk signals, "
            "and note which trades or positions deserve journal follow-up."
        )

    @trading_journal_mcp.prompt(
        name="journal_follow_up",
        description="Create a prompt for reviewing recent trades and missing journal context.",
    )
    def journal_follow_up_prompt(account_name: str = "Manual Fidelity") -> str:
        """Build a reusable prompt for trade-journal follow-up."""
        with session_scope() as session:
            trades = [serialize_trade(trade) for trade in list_trades(session)[:10]]

        filtered_trades = [trade for trade in trades if trade["account_name"] == account_name] or trades
        trade_lines = [
            f"{trade['trade_date']} {trade['symbol']} {trade['side']} qty={trade['quantity']} reason={trade['reason']}"
            for trade in filtered_trades[:5]
        ]

        return (
            f"Review the recent trade journal entries for account '{account_name}'.\n"
            "Recent trades:\n"
            + "\n".join(trade_lines or ["No trades available."])
            + "\nIdentify where the trade reason is too weak, too vague, or missing useful context, "
            "and suggest stronger journal notes."
        )

    return trading_journal_mcp
