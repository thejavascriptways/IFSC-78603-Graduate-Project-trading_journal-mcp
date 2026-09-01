from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field, field_validator

from app.models.enums import AssetClass, OrderSide


class ManualTradeCreate(BaseModel):
    account_id: int
    symbol: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=255)
    asset_class: AssetClass
    trade_date: date
    side: OrderSide
    quantity: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)
    fees: Decimal = Field(default=Decimal("0"), ge=0)
    reason: str = Field(min_length=3)
    notes: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=8)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("Trade reason is required.")
        return cleaned

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class OpeningHoldingCreate(BaseModel):
    account_id: int
    symbol: str = Field(min_length=1, max_length=32)
    description: str | None = Field(default=None, max_length=255)
    asset_class: AssetClass
    opening_date: date
    quantity: Decimal = Field(gt=0)
    average_cost: Decimal = Field(ge=0)
    notes: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=8)

    @field_validator("symbol")
    @classmethod
    def normalize_symbol(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class PositionMarkUpdate(BaseModel):
    market_price: Decimal = Field(ge=0)


class TradeRead(BaseModel):
    id: int
    account_name: str
    symbol: str
    asset_class: AssetClass
    trade_date: date
    side: OrderSide
    quantity: Decimal
    price: Decimal
    fees: Decimal
    reason: str
    notes: str | None
    realized_pnl: Decimal | None


class PositionRead(BaseModel):
    account_name: str
    symbol: str
    asset_class: AssetClass
    quantity: Decimal
    average_cost: Decimal
    cost_basis: Decimal


class MCPToolCallRequest(BaseModel):
    server_id: str = Field(min_length=1)
    tool_name: str = Field(min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)


class MCPResourceReadRequest(BaseModel):
    server_id: str = Field(min_length=1)
    uri: str = Field(min_length=1)


class MCPPromptReadRequest(BaseModel):
    server_id: str = Field(min_length=1)
    prompt_name: str = Field(min_length=1)
    arguments: dict[str, str] = Field(default_factory=dict)
