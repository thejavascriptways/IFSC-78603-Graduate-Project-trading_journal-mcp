from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from app.models.entities import Account, Instrument, Position, Trade
from app.models.enums import AccountSource, OrderSide, TradeOrigin
from app.schemas import ManualTradeCreate, OpeningHoldingCreate


ZERO = Decimal("0")


class PortfolioError(Exception):
    """Domain-level validation error."""


@dataclass
class DashboardData:
    accounts: list[Account]
    open_positions: list[Position]
    closed_positions: list[dict[str, Any]]
    recent_trades: list[Trade]
    total_cost_basis: Decimal
    total_market_value: Decimal
    total_unrealized_pnl: Decimal
    total_realized_pnl: Decimal


InstrumentPayload = ManualTradeCreate | OpeningHoldingCreate


def seed_default_accounts(session: Session) -> None:
    defaults = [
        {
            "name": "IBKR Live",
            "source": AccountSource.IBKR,
            "account_number": None,
            "sync_enabled": True,
        },
        {
            "name": "Manual Fidelity",
            "source": AccountSource.MANUAL,
            "account_number": None,
            "sync_enabled": False,
        },
    ]

    for payload in defaults:
        existing = session.scalar(select(Account).where(Account.name == payload["name"]))
        if existing:
            continue
        session.add(Account(**payload))

    session.commit()


def list_accounts(session: Session) -> list[Account]:
    return list(session.scalars(select(Account).where(Account.is_active.is_(True)).order_by(Account.name)))


def list_manual_accounts(session: Session) -> list[Account]:
    return list(
        session.scalars(
            select(Account)
            .where(Account.is_active.is_(True), Account.source == AccountSource.MANUAL)
            .order_by(Account.name)
        )
    )


def get_dashboard_data(session: Session) -> DashboardData:
    accounts = list_accounts(session)
    open_positions = list_positions(session)
    closed_positions = list_closed_positions(session)
    all_trades = list_trades(session)
    recent_trades = list(
        session.scalars(
            select(Trade)
            .options(joinedload(Trade.account), joinedload(Trade.instrument))
            .order_by(Trade.trade_date.desc(), Trade.created_at.desc())
            .limit(10)
        )
    )
    total_cost_basis = sum((position.cost_basis for position in open_positions), ZERO)
    total_market_value = sum((position.market_value or ZERO for position in open_positions), ZERO)
    total_unrealized_pnl = sum((position.unrealized_pnl or ZERO for position in open_positions), ZERO)
    total_realized_pnl = sum((trade.realized_pnl or ZERO for trade in all_trades), ZERO)
    return DashboardData(
        accounts=accounts,
        open_positions=open_positions,
        closed_positions=closed_positions,
        recent_trades=recent_trades,
        total_cost_basis=total_cost_basis,
        total_market_value=total_market_value,
        total_unrealized_pnl=total_unrealized_pnl,
        total_realized_pnl=total_realized_pnl,
    )


def get_portfolio_summary(session: Session) -> dict[str, Any]:
    data = get_dashboard_data(session)
    manual_accounts = [account for account in data.accounts if account.source == AccountSource.MANUAL]
    performance = get_performance_breakdown(session)

    return {
        "account_count": len(data.accounts),
        "manual_account_count": len(manual_accounts),
        "synced_account_count": len(data.accounts) - len(manual_accounts),
        "open_position_count": len(data.open_positions),
        "closed_position_count": len(data.closed_positions),
        "recent_trade_count": len(data.recent_trades),
        "total_cost_basis": str(data.total_cost_basis),
        "total_market_value": str(data.total_market_value),
        "unrealized_pnl_total": str(data.total_unrealized_pnl),
        "realized_pnl_total": str(data.total_realized_pnl),
        "accounts": [serialize_account(account) for account in data.accounts],
        "performance_overall": performance["overall"],
        "performance_by_account": performance["by_account"],
        "performance_by_account_asset_class": performance["by_account_asset_class"],
    }


def list_positions(session: Session) -> list[Position]:
    return list(
        session.scalars(
            select(Position)
            .options(joinedload(Position.account), joinedload(Position.instrument))
            .where(Position.quantity != ZERO)
            .order_by(Position.account_id, Position.instrument_id)
        )
    )


def list_closed_positions(session: Session) -> list[dict[str, Any]]:
    closed_positions = list(
        session.scalars(
            select(Position)
            .options(joinedload(Position.account), joinedload(Position.instrument))
            .where(Position.quantity == ZERO)
            .order_by(Position.updated_at.desc())
        )
    )
    summaries: list[dict[str, Any]] = []

    for position in closed_positions:
        trades = list(
            session.scalars(
                select(Trade)
                .where(
                    Trade.account_id == position.account_id,
                    Trade.instrument_id == position.instrument_id,
                )
                .order_by(Trade.trade_date.asc(), Trade.created_at.asc())
            )
        )
        if not trades:
            continue

        realized_total = sum((trade.realized_pnl or ZERO for trade in trades), ZERO)
        summaries.append(
            {
                "position_id": position.id,
                "account_name": position.account.name,
                "symbol": position.instrument.symbol,
                "description": position.instrument.description,
                "asset_class": position.instrument.asset_class.value,
                "opened_on": trades[0].trade_date.isoformat(),
                "closed_on": trades[-1].trade_date.isoformat(),
                "realized_pnl_total": str(realized_total),
                "trade_count": len(trades),
                "last_exit_price": str(trades[-1].price),
            }
        )

    return summaries


def list_trades(session: Session) -> list[Trade]:
    return list(
        session.scalars(
            select(Trade)
            .options(joinedload(Trade.account), joinedload(Trade.instrument))
            .order_by(Trade.trade_date.desc(), Trade.created_at.desc())
        )
    )


def get_position(session: Session, position_id: int) -> Position | None:
    return session.scalar(
        select(Position)
        .options(joinedload(Position.account), joinedload(Position.instrument))
        .where(Position.id == position_id)
    )


def record_manual_trade(session: Session, payload: ManualTradeCreate) -> Trade:
    account = session.get(Account, payload.account_id)
    if not account:
        raise PortfolioError("Selected account does not exist.")

    instrument = _get_or_create_instrument(session, payload)
    position = _get_or_create_position(session, account.id, instrument.id)

    trade = Trade(
        account=account,
        instrument=instrument,
        origin=TradeOrigin.MANUAL,
        trade_date=payload.trade_date,
        side=payload.side,
        quantity=payload.quantity,
        price=payload.price,
        fees=payload.fees,
        reason=payload.reason,
        notes=payload.notes,
    )

    if payload.side == OrderSide.BUY:
        _apply_buy(position, payload.quantity, payload.price, payload.fees)
    else:
        trade.realized_pnl = _apply_sell(position, payload.quantity, payload.price, payload.fees)

    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


def serialize_account(account: Account) -> dict[str, Any]:
    return {
        "id": account.id,
        "name": account.name,
        "source": account.source.value,
        "account_number": account.account_number,
        "base_currency": account.base_currency,
        "sync_enabled": account.sync_enabled,
        "is_active": account.is_active,
    }


def serialize_position(position: Position) -> dict[str, Any]:
    return {
        "id": position.id,
        "account_id": position.account_id,
        "instrument_id": position.instrument_id,
        "account_name": position.account.name,
        "symbol": position.instrument.symbol,
        "description": position.instrument.description,
        "asset_class": position.instrument.asset_class.value,
        "currency": position.instrument.currency,
        "quantity": str(position.quantity),
        "average_cost": str(position.average_cost),
        "cost_basis": str(position.cost_basis),
        "market_price": None if position.market_price is None else str(position.market_price),
        "market_value": None if position.market_value is None else str(position.market_value),
        "unrealized_pnl": None if position.unrealized_pnl is None else str(position.unrealized_pnl),
    }


def serialize_trade(trade: Trade) -> dict[str, Any]:
    return {
        "id": trade.id,
        "account_name": trade.account.name,
        "symbol": trade.instrument.symbol,
        "description": trade.instrument.description,
        "asset_class": trade.instrument.asset_class.value,
        "origin": trade.origin.value,
        "trade_date": trade.trade_date.isoformat(),
        "side": trade.side.value,
        "quantity": str(trade.quantity),
        "price": str(trade.price),
        "fees": str(trade.fees),
        "reason": trade.reason,
        "notes": trade.notes,
        "realized_pnl": None if trade.realized_pnl is None else str(trade.realized_pnl),
    }


def serialize_closed_position(position: dict[str, Any]) -> dict[str, Any]:
    return position


def get_performance_breakdown(session: Session) -> dict[str, Any]:
    open_positions = list_positions(session)
    trades = list_trades(session)

    overall = _new_performance_bucket()
    by_account: dict[str, dict[str, Decimal | str]] = defaultdict(_new_performance_bucket)
    by_account_asset_class: dict[tuple[str, str], dict[str, Decimal | str]] = defaultdict(_new_performance_bucket)

    for position in open_positions:
        _apply_open_position_metrics(overall, position)

        account_key = position.account.name
        account_bucket = by_account[account_key]
        account_bucket["account_name"] = account_key
        _apply_open_position_metrics(account_bucket, position)

        asset_key = (position.account.name, position.instrument.asset_class.value)
        account_asset_bucket = by_account_asset_class[asset_key]
        account_asset_bucket["account_name"] = position.account.name
        account_asset_bucket["asset_class"] = position.instrument.asset_class.value
        _apply_open_position_metrics(account_asset_bucket, position)

    for trade in trades:
        if trade.realized_pnl is None:
            continue

        _apply_realized_trade_metrics(overall, trade)

        account_key = trade.account.name
        account_bucket = by_account[account_key]
        account_bucket["account_name"] = account_key
        _apply_realized_trade_metrics(account_bucket, trade)

        asset_key = (trade.account.name, trade.instrument.asset_class.value)
        account_asset_bucket = by_account_asset_class[asset_key]
        account_asset_bucket["account_name"] = trade.account.name
        account_asset_bucket["asset_class"] = trade.instrument.asset_class.value
        _apply_realized_trade_metrics(account_asset_bucket, trade)

    overall["label"] = "Overall"

    return {
        "overall": _serialize_performance_bucket(overall),
        "by_account": [
            _serialize_performance_bucket(by_account[key])
            for key in sorted(by_account)
        ],
        "by_account_asset_class": [
            _serialize_performance_bucket(by_account_asset_class[key])
            for key in sorted(by_account_asset_class)
        ],
    }


def update_position_market_price(session: Session, position_id: int, market_price: Decimal) -> Position:
    position = get_position(session, position_id)
    if position is None:
        raise PortfolioError("Selected position does not exist.")
    if position.quantity == ZERO:
        raise PortfolioError("Cannot update market price for a closed position.")

    position.market_price = market_price
    _refresh_position_market_metrics(position)
    session.commit()
    session.refresh(position)
    return position


def import_opening_holding(session: Session, payload: OpeningHoldingCreate) -> Trade:
    account = session.get(Account, payload.account_id)
    if not account:
        raise PortfolioError("Selected account does not exist.")
    if account.source != AccountSource.MANUAL:
        raise PortfolioError("Opening holdings can only be imported into manual accounts.")

    instrument = _get_or_create_instrument(session, payload)
    position = _get_or_create_position(session, account.id, instrument.id)

    if position.quantity != ZERO:
        raise PortfolioError("An open position already exists for this account and symbol.")

    existing_trade = session.scalar(
        select(Trade.id).where(Trade.account_id == account.id, Trade.instrument_id == instrument.id).limit(1)
    )
    if existing_trade is not None:
        raise PortfolioError("Trade history already exists for this account and symbol.")

    cost_basis = payload.quantity * payload.average_cost
    position.quantity = payload.quantity
    position.average_cost = payload.average_cost
    position.cost_basis = cost_basis
    position.market_price = payload.average_cost
    _refresh_position_market_metrics(position)

    trade = Trade(
        account=account,
        instrument=instrument,
        origin=TradeOrigin.OPENING,
        trade_date=payload.opening_date,
        side=OrderSide.BUY,
        quantity=payload.quantity,
        price=payload.average_cost,
        fees=ZERO,
        reason="Opening holding import",
        notes=payload.notes,
    )
    session.add(trade)
    session.commit()
    session.refresh(trade)
    return trade


def _get_or_create_instrument(session: Session, payload: InstrumentPayload) -> Instrument:
    statement = select(Instrument).where(
        Instrument.symbol == payload.symbol,
        Instrument.asset_class == payload.asset_class,
        Instrument.currency == payload.currency,
    )
    instrument = session.scalar(statement)
    if instrument:
        if payload.description and not instrument.description:
            instrument.description = payload.description
        return instrument

    instrument = Instrument(
        symbol=payload.symbol,
        description=payload.description,
        asset_class=payload.asset_class,
        currency=payload.currency,
    )
    session.add(instrument)
    session.flush()
    return instrument


def _get_or_create_position(session: Session, account_id: int, instrument_id: int) -> Position:
    statement = select(Position).where(Position.account_id == account_id, Position.instrument_id == instrument_id)
    position = session.scalar(statement)
    if position:
        return position

    position = Position(
        account_id=account_id,
        instrument_id=instrument_id,
        quantity=ZERO,
        average_cost=ZERO,
        cost_basis=ZERO,
    )
    session.add(position)
    session.flush()
    return position


def _apply_buy(position: Position, quantity: Decimal, price: Decimal, fees: Decimal) -> None:
    total_cost = (quantity * price) + fees
    position.quantity += quantity
    position.cost_basis += total_cost
    if position.quantity == ZERO:
        position.average_cost = ZERO
    else:
        position.average_cost = position.cost_basis / position.quantity
    if position.market_price is None:
        position.market_price = price
    _refresh_position_market_metrics(position)


def _apply_sell(position: Position, quantity: Decimal, price: Decimal, fees: Decimal) -> Decimal:
    if position.quantity < quantity:
        raise PortfolioError("Cannot sell more than the current position quantity.")
    if position.quantity == ZERO:
        raise PortfolioError("Cannot sell from an empty position.")

    average_cost = position.average_cost
    removed_cost = average_cost * quantity
    proceeds = (quantity * price) - fees
    realized_pnl = proceeds - removed_cost

    position.quantity -= quantity
    position.cost_basis -= removed_cost
    position.market_price = price
    if position.quantity == ZERO:
        position.average_cost = ZERO
        position.cost_basis = ZERO
    else:
        position.average_cost = position.cost_basis / position.quantity
    _refresh_position_market_metrics(position)

    return realized_pnl


def _refresh_position_market_metrics(position: Position) -> None:
    if position.quantity == ZERO:
        position.market_value = ZERO
        position.unrealized_pnl = ZERO
        return

    if position.market_price is None:
        position.market_value = None
        position.unrealized_pnl = None
        return

    position.market_value = position.market_price * position.quantity
    position.unrealized_pnl = position.market_value - position.cost_basis


def _new_performance_bucket() -> dict[str, Decimal | str]:
    return {
        "open_cost_basis": ZERO,
        "market_value": ZERO,
        "unrealized_pnl": ZERO,
        "realized_cost_basis": ZERO,
        "realized_pnl": ZERO,
    }


def _apply_open_position_metrics(bucket: dict[str, Decimal | str], position: Position) -> None:
    bucket["open_cost_basis"] += position.cost_basis
    bucket["market_value"] += position.market_value or ZERO
    bucket["unrealized_pnl"] += position.unrealized_pnl or ZERO


def _apply_realized_trade_metrics(bucket: dict[str, Decimal | str], trade: Trade) -> None:
    realized_pnl = trade.realized_pnl or ZERO
    proceeds = (trade.quantity * trade.price) - trade.fees
    realized_cost_basis = proceeds - realized_pnl

    bucket["realized_cost_basis"] += realized_cost_basis
    bucket["realized_pnl"] += realized_pnl


def _serialize_performance_bucket(bucket: dict[str, Decimal | str]) -> dict[str, Any]:
    open_cost_basis = bucket["open_cost_basis"]
    market_value = bucket["market_value"]
    unrealized_pnl = bucket["unrealized_pnl"]
    realized_cost_basis = bucket["realized_cost_basis"]
    realized_pnl = bucket["realized_pnl"]
    total_basis = open_cost_basis + realized_cost_basis
    total_pnl = unrealized_pnl + realized_pnl

    return {
        "label": bucket.get("label"),
        "account_name": bucket.get("account_name"),
        "asset_class": bucket.get("asset_class"),
        "open_cost_basis": _decimal_to_string(open_cost_basis),
        "market_value": _decimal_to_string(market_value),
        "unrealized_pnl": _decimal_to_string(unrealized_pnl),
        "unrealized_pct": _percentage_to_string(unrealized_pnl, open_cost_basis),
        "realized_cost_basis": _decimal_to_string(realized_cost_basis),
        "realized_pnl": _decimal_to_string(realized_pnl),
        "realized_pct": _percentage_to_string(realized_pnl, realized_cost_basis),
        "total_basis": _decimal_to_string(total_basis),
        "total_pnl": _decimal_to_string(total_pnl),
        "total_pct": _percentage_to_string(total_pnl, total_basis),
    }


def _decimal_to_string(value: Decimal) -> str:
    return format(value, ".6f")


def _percentage_to_string(numerator: Decimal, denominator: Decimal) -> str | None:
    if denominator == ZERO:
        return None
    return format((numerator / denominator) * Decimal("100"), ".4f")
