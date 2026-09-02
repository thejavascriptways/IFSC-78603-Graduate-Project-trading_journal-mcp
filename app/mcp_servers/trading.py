from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from mcp.server.fastmcp import FastMCP

from app.mcp_servers.security import local_transport_security_settings
from app.services.orders import OrderDraft, OrderIntent, OrderService, OrderServiceError, OrderSide, OrderType, TimeInForce


def _normalize_error(exc: Exception) -> ValueError:
    return ValueError(str(exc))


def create_trading_mcp_server(order_service: OrderService | None = None) -> FastMCP:
    service = order_service or OrderService()
    trading_mcp = FastMCP(
        "Trading Journal Trading MCP",
        instructions=(
            "Trading MCP server for Trading Journal. "
            "Only safe preview scaffolding is available now; live trading is disabled."
        ),
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
        transport_security=local_transport_security_settings(),
    )

    @trading_mcp.tool(name="get_trading_capabilities", structured_output=True)
    def get_trading_capabilities_tool() -> dict[str, Any]:
        """Describe current order/trading capabilities and safety mode."""
        return {
            "paper_trading_enabled": False,
            "live_trading_enabled": False,
            "order_preview_enabled": True,
            "notes": [
                "Order preview scaffolding is available for architecture demos.",
                "Paper trading is not implemented yet.",
                "Live trading is disabled and must remain confirmation-gated in future phases.",
            ],
        }

    @trading_mcp.tool(name="preview_order", structured_output=True)
    def preview_order_tool(
        account_id: int,
        symbol: str,
        side: str,
        quantity: str,
        order_type: str = "MARKET",
        time_in_force: str = "DAY",
        intent: str = "PAPER",
        limit_price: str | None = None,
        reason: str = "Architecture preview only.",
        risk_notes: str | None = None,
    ) -> dict[str, str]:
        """Preview an order draft without sending anything to a broker."""
        try:
            draft = OrderDraft(
                account_id=account_id,
                symbol=symbol,
                side=OrderSide(side.upper()),
                quantity=Decimal(quantity),
                order_type=OrderType(order_type.upper()),
                time_in_force=TimeInForce(time_in_force.upper()),
                intent=OrderIntent(intent.upper()),
                limit_price=None if limit_price is None else Decimal(limit_price),
                reason=reason,
                risk_notes=risk_notes,
            )
            return service.preview(draft)
        except (InvalidOperation, ValueError, OrderServiceError) as exc:
            raise _normalize_error(exc) from exc

    @trading_mcp.resource("trading://capabilities", mime_type="application/json")
    def trading_capabilities_resource() -> str:
        """Read current trading safety capabilities as JSON."""
        return json.dumps(get_trading_capabilities_tool(), indent=2)

    @trading_mcp.prompt(
        name="order_safety_review",
        description="Create a prompt for reviewing a staged order before broker submission exists.",
    )
    def order_safety_review_prompt(symbol: str = "SPY") -> str:
        """Build a reusable prompt for reviewing order safety."""
        return (
            f"Review a potential Trading Journal order for {symbol}. "
            "Check that the user has a clear trade reason, understands risk, confirms paper/live mode, "
            "and has reviewed quote freshness before any order submission."
        )

    return trading_mcp
