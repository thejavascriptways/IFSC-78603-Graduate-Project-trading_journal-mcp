from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Numeric, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base
from app.models.enums import AccountSource, AssetClass, OrderSide, TradeOrigin


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class Account(TimestampMixin, Base):
    __tablename__ = "accounts"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    source: Mapped[AccountSource] = mapped_column(Enum(AccountSource), nullable=False)
    account_number: Mapped[str | None] = mapped_column(String(64))
    base_currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    sync_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    trades: Mapped[list["Trade"]] = relationship(back_populates="account")
    positions: Mapped[list["Position"]] = relationship(back_populates="account")


class Instrument(TimestampMixin, Base):
    __tablename__ = "instruments"

    id: Mapped[int] = mapped_column(primary_key=True)
    symbol: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    asset_class: Mapped[AssetClass] = mapped_column(Enum(AssetClass), nullable=False)
    currency: Mapped[str] = mapped_column(String(8), default="USD", nullable=False)
    exchange: Mapped[str | None] = mapped_column(String(64))
    underlying_symbol: Mapped[str | None] = mapped_column(String(32))
    option_right: Mapped[str | None] = mapped_column(String(8))
    option_strike: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    option_expiration: Mapped[date | None] = mapped_column(Date)

    trades: Mapped[list["Trade"]] = relationship(back_populates="instrument")
    positions: Mapped[list["Position"]] = relationship(back_populates="instrument")

    __table_args__ = (
        UniqueConstraint(
            "symbol",
            "asset_class",
            "currency",
            "option_expiration",
            "option_strike",
            "option_right",
            name="uq_instruments_contract",
        ),
    )


class Trade(TimestampMixin, Base):
    __tablename__ = "trades"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False, index=True)
    origin: Mapped[TradeOrigin] = mapped_column(Enum(TradeOrigin), default=TradeOrigin.MANUAL, nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(120), index=True)
    trade_date: Mapped[date] = mapped_column(Date, nullable=False)
    side: Mapped[OrderSide] = mapped_column(Enum(OrderSide), nullable=False)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(18, 6), nullable=False)
    fees: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    account: Mapped["Account"] = relationship(back_populates="trades")
    instrument: Mapped["Instrument"] = relationship(back_populates="trades")


class Position(TimestampMixin, Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id"), nullable=False, index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"), nullable=False, index=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    average_cost: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    cost_basis: Mapped[Decimal] = mapped_column(Numeric(18, 6), default=Decimal("0"), nullable=False)
    market_price: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    market_value: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 6))

    account: Mapped["Account"] = relationship(back_populates="positions")
    instrument: Mapped["Instrument"] = relationship(back_populates="positions")

    __table_args__ = (UniqueConstraint("account_id", "instrument_id", name="uq_positions_account_instrument"),)
