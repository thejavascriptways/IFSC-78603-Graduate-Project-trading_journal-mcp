from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class OrderServiceError(Exception):
    """Domain-level error for order workflows."""


class OrderIntent(StrEnum):
    PAPER = "PAPER"
    LIVE = "LIVE"


class OrderType(StrEnum):
    MARKET = "MARKET"
    LIMIT = "LIMIT"


class OrderSide(StrEnum):
    BUY = "BUY"
    SELL = "SELL"


class TimeInForce(StrEnum):
    DAY = "DAY"
    GTC = "GTC"


@dataclass(frozen=True)
class OrderDraft:
    """A not-yet-submitted order used for preview, journaling, and safety checks."""

    account_id: int
    symbol: str
    side: OrderSide
    quantity: Decimal
    order_type: OrderType
    time_in_force: TimeInForce
    intent: OrderIntent
    reason: str
    limit_price: Decimal | None = None
    risk_notes: str | None = None


class OrderService:
    """Coordinates safe order staging before any broker submission exists."""

    def preview(self, draft: OrderDraft) -> dict[str, str]:
        symbol = draft.symbol.strip().upper()
        reason = draft.reason.strip()
        if not symbol:
            raise OrderServiceError("Symbol is required for order preview.")
        if draft.quantity <= 0:
            raise OrderServiceError("Quantity must be greater than zero for order preview.")
        if not reason:
            raise OrderServiceError("Trade reason is required for order preview.")
        if draft.order_type == OrderType.LIMIT and (draft.limit_price is None or draft.limit_price <= 0):
            raise OrderServiceError("Limit price must be greater than zero for limit order preview.")
        if draft.intent == OrderIntent.LIVE:
            raise OrderServiceError("Live order preview is not enabled yet.")
        return {
            "status": "preview_only",
            "symbol": symbol,
            "side": draft.side.value,
            "quantity": str(draft.quantity),
            "order_type": draft.order_type.value,
            "time_in_force": draft.time_in_force.value,
            "intent": draft.intent.value,
            "reason": reason,
            "message": "Order staging architecture is ready; broker submission is not implemented yet.",
        }
