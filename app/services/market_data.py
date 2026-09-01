from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

import httpx
from fastapi import FastAPI
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from sqlalchemy.orm import Session

from app.config import settings
from app.models.enums import AssetClass
from app.services.portfolio import list_closed_positions, list_positions, update_position_market_price


ZERO = Decimal("0")
SUPPORTED_EQUITY_ASSET_CLASSES = {AssetClass.STOCK.value, AssetClass.ETF.value}
SUPPORTED_OPTION_ASSET_CLASSES = {AssetClass.OPTION.value}


class MarketDataError(Exception):
    """Raised when live market data cannot be retrieved or applied."""


def get_market_data_capabilities() -> dict[str, Any]:
    configured = bool(settings.alpaca_api_key_id and settings.alpaca_api_secret_key)
    stock_feed = settings.alpaca_stock_feed
    option_feed = settings.alpaca_option_feed

    notes = [
        "Stocks and ETFs are fetched from Alpaca Market Data.",
        "Mutual funds usually publish NAV once per business day rather than live intraday quotes.",
        "Bonds are not covered by Alpaca's stock/options feeds; FINRA TRACE is trade transparency, not live quotes.",
    ]

    if option_feed == "indicative":
        notes.append("Options are using Alpaca's indicative feed unless you switch to OPRA with a paid entitlement.")

    return {
        "provider": settings.market_data_provider,
        "configured": configured,
        "stock_feed": stock_feed,
        "option_feed": option_feed,
        "notes": notes,
    }


def fetch_live_equity_snapshots(symbols: list[str]) -> dict[str, Any]:
    capabilities = get_market_data_capabilities()
    if not capabilities["configured"]:
        raise MarketDataError("Live market data is not configured. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY.")

    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return {
            "provider": "alpaca",
            "asset_class": AssetClass.STOCK.value,
            "feed": settings.alpaca_stock_feed,
            "quotes": [],
            "missing_symbols": [],
        }

    quotes: list[dict[str, Any]] = []
    missing_symbols: list[str] = []

    with _alpaca_client() as client:
        for symbol_chunk in _chunked(normalized_symbols, 100):
            response = _request_alpaca(
                client,
                "/v2/stocks/snapshots",
                params={
                    "symbols": ",".join(symbol_chunk),
                    "feed": settings.alpaca_stock_feed,
                    "currency": "USD",
                },
            )
            payload = response.json()
            snapshots = _extract_snapshot_map(payload)

            for symbol in symbol_chunk:
                snapshot = snapshots.get(symbol)
                if snapshot is None:
                    missing_symbols.append(symbol)
                    quotes.append(_not_found_quote(symbol, AssetClass.STOCK.value, settings.alpaca_stock_feed))
                    continue
                quotes.append(_normalize_equity_snapshot(symbol, snapshot, settings.alpaca_stock_feed))

    return {
        "provider": "alpaca",
        "asset_class": AssetClass.STOCK.value,
        "feed": settings.alpaca_stock_feed,
        "quotes": quotes,
        "missing_symbols": missing_symbols,
    }


def fetch_live_option_snapshots(symbols: list[str]) -> dict[str, Any]:
    capabilities = get_market_data_capabilities()
    if not capabilities["configured"]:
        raise MarketDataError("Live market data is not configured. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY.")

    normalized_symbols = _normalize_symbols(symbols)
    if not normalized_symbols:
        return {
            "provider": "alpaca",
            "asset_class": AssetClass.OPTION.value,
            "feed": settings.alpaca_option_feed,
            "quotes": [],
            "missing_symbols": [],
        }

    quotes: list[dict[str, Any]] = []
    missing_symbols: list[str] = []

    with _alpaca_client() as client:
        for symbol_chunk in _chunked(normalized_symbols, 100):
            response = _request_alpaca(
                client,
                "/v1beta1/options/snapshots",
                params={
                    "symbols": ",".join(symbol_chunk),
                    "feed": settings.alpaca_option_feed,
                },
            )
            payload = response.json()
            snapshots = _extract_snapshot_map(payload)

            for symbol in symbol_chunk:
                snapshot = snapshots.get(symbol)
                if snapshot is None:
                    missing_symbols.append(symbol)
                    quotes.append(_not_found_quote(symbol, AssetClass.OPTION.value, settings.alpaca_option_feed))
                    continue
                quotes.append(_normalize_option_snapshot(symbol, snapshot, settings.alpaca_option_feed))

    return {
        "provider": "alpaca",
        "asset_class": AssetClass.OPTION.value,
        "feed": settings.alpaca_option_feed,
        "quotes": quotes,
        "missing_symbols": missing_symbols,
    }


def build_portfolio_market_data_targets(session: Session) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []

    for position in list_positions(session):
        targets.append(
            {
                "status": "OPEN",
                "account_name": position.account.name,
                "symbol": position.instrument.symbol,
                "asset_class": position.instrument.asset_class.value,
                "quantity": str(position.quantity),
                "cost_basis": str(position.cost_basis),
                "average_cost": str(position.average_cost),
                "opened_on": None,
                "closed_on": None,
                "trade_count": None,
                "realized_pnl_total": None,
            }
        )

    for position in list_closed_positions(session):
        targets.append(
            {
                "status": "CLOSED",
                "account_name": position["account_name"],
                "symbol": position["symbol"],
                "asset_class": position["asset_class"],
                "quantity": None,
                "cost_basis": None,
                "average_cost": None,
                "opened_on": position["opened_on"],
                "closed_on": position["closed_on"],
                "trade_count": position["trade_count"],
                "realized_pnl_total": position["realized_pnl_total"],
            }
        )

    targets.sort(key=lambda item: (item["status"] != "OPEN", item["account_name"], item["symbol"]))
    return targets


async def fetch_live_market_data_from_mcp(app: FastAPI, targets: list[dict[str, Any]]) -> dict[str, Any]:
    lookup: dict[tuple[str, str], dict[str, Any]] = {}
    capabilities: dict[str, Any] = {}

    equity_symbols = sorted(
        {
            target["symbol"]
            for target in targets
            if target["asset_class"] in SUPPORTED_EQUITY_ASSET_CLASSES
        }
    )
    option_symbols = sorted(
        {
            target["symbol"]
            for target in targets
            if target["asset_class"] in SUPPORTED_OPTION_ASSET_CLASSES
        }
    )

    try:
        # Keep the app local-first while still exercising a real MCP client over HTTP transport.
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport,
            base_url="http://127.0.0.1:8000",
            follow_redirects=True,
            timeout=settings.market_data_timeout_seconds,
        ) as http_client:
            async with streamable_http_client(
                "http://127.0.0.1:8000/market-data-mcp/",
                http_client=http_client,
            ) as (read, write, _):
                async with ClientSession(read, write) as client_session:
                    await client_session.initialize()
                    capabilities_result = await client_session.call_tool("get_market_data_capabilities")
                    capabilities = capabilities_result.model_dump(mode="json").get("structuredContent", {})

                    if capabilities.get("configured") is not True:
                        return {
                            "capabilities": capabilities,
                            "lookup": lookup,
                        }

                    if equity_symbols:
                        equity_result = await client_session.call_tool(
                            "get_equity_snapshots",
                            {"symbols": equity_symbols},
                        )
                        equity_payload = equity_result.model_dump(mode="json").get("structuredContent", {})
                        for quote in equity_payload.get("quotes", []):
                            lookup[(quote["symbol"], AssetClass.STOCK.value)] = quote
                            lookup[(quote["symbol"], AssetClass.ETF.value)] = quote

                    if option_symbols:
                        option_result = await client_session.call_tool(
                            "get_option_snapshots",
                            {"symbols": option_symbols},
                        )
                        option_payload = option_result.model_dump(mode="json").get("structuredContent", {})
                        for quote in option_payload.get("quotes", []):
                            lookup[(quote["symbol"], AssetClass.OPTION.value)] = quote
    except Exception as exc:  # pragma: no cover - integration tests cover the user-facing error path
        raise MarketDataError("Could not retrieve live market data through the Market Data MCP server.") from exc

    return {
        "capabilities": capabilities,
        "lookup": lookup,
    }


def build_live_market_data_rows(
    targets: list[dict[str, Any]],
    live_lookup: dict[tuple[str, str], dict[str, Any]],
    capabilities: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for target in targets:
        asset_class = target["asset_class"]
        quote = live_lookup.get((target["symbol"], asset_class))
        support_status = "LIVE"
        note = None

        if asset_class == AssetClass.MUTUAL_FUND.value:
            support_status = "NAV_ONLY"
            note = "Mutual funds typically publish NAV after market close, not live intraday prices."
        elif asset_class == AssetClass.BOND.value:
            support_status = "UNSUPPORTED"
            note = "Bond live quotes are not available from the Alpaca stock/options feeds."
        elif asset_class == AssetClass.CASH.value:
            support_status = "UNSUPPORTED"
            note = "Cash balances do not have market quote data."
        elif quote is None:
            support_status = "NO_DATA"
            note = "No live market data was returned for this symbol."
        elif quote.get("found") is not True:
            support_status = "NO_DATA"
            note = quote.get("note") or "No live market data was returned for this symbol."

        live_price = quote.get("mark_price") if quote else None
        live_unrealized = None
        live_unrealized_pct = None

        if target["status"] == "OPEN" and live_price is not None and target["quantity"] is not None and target["cost_basis"] is not None:
            try:
                quantity = Decimal(target["quantity"])
                cost_basis = Decimal(target["cost_basis"])
                live_value = Decimal(live_price) * quantity
                live_unrealized_value = live_value - cost_basis
                live_unrealized = _format_decimal(live_unrealized_value)
                if cost_basis != ZERO:
                    live_unrealized_pct = _format_decimal((live_unrealized_value / cost_basis) * Decimal("100"), places=4)
            except (InvalidOperation, ValueError):
                live_unrealized = None
                live_unrealized_pct = None

        rows.append(
            {
                **target,
                "market_data_status": support_status,
                "note": note,
                "provider": capabilities.get("provider"),
                "feed": quote.get("feed") if quote else _feed_for_asset_class(asset_class, capabilities),
                "mark_price": live_price,
                "last_trade_price": quote.get("last_trade_price") if quote else None,
                "bid_price": quote.get("bid_price") if quote else None,
                "ask_price": quote.get("ask_price") if quote else None,
                "change_percent": quote.get("change_percent") if quote else None,
                "as_of": quote.get("as_of") if quote else None,
                "live_unrealized_pnl": live_unrealized,
                "live_unrealized_pct": live_unrealized_pct,
            }
        )

    return rows


def apply_live_market_data_to_open_positions(
    session: Session,
    targets: list[dict[str, Any]],
    live_lookup: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    open_positions = list_positions(session)
    positions_by_symbol: dict[tuple[str, str], list[Any]] = {}
    for position in open_positions:
        key = (position.instrument.symbol, position.instrument.asset_class.value)
        positions_by_symbol.setdefault(key, []).append(position)

    updated_symbols: set[str] = set()
    updated_position_count = 0
    missing_symbols: list[str] = []

    for target in targets:
        if target["status"] != "OPEN":
            continue
        key = (target["symbol"], target["asset_class"])
        quote = live_lookup.get(key)
        if not quote or quote.get("mark_price") is None:
            missing_symbols.append(target["symbol"])
            continue

        try:
            market_price = Decimal(str(quote["mark_price"]))
        except (InvalidOperation, ValueError):
            missing_symbols.append(target["symbol"])
            continue

        for position in positions_by_symbol.get(key, []):
            update_position_market_price(session, position.id, market_price)
            updated_position_count += 1
            updated_symbols.add(position.instrument.symbol)

    return {
        "updated_position_count": updated_position_count,
        "updated_symbols": sorted(updated_symbols),
        "missing_symbols": sorted(set(missing_symbols) - updated_symbols),
    }


def _alpaca_client() -> httpx.Client:
    return httpx.Client(
        base_url=settings.alpaca_market_data_base_url,
        headers={
            "APCA-API-KEY-ID": settings.alpaca_api_key_id or "",
            "APCA-API-SECRET-KEY": settings.alpaca_api_secret_key or "",
            "accept": "application/json",
        },
        timeout=settings.market_data_timeout_seconds,
    )


def _request_alpaca(client: httpx.Client, path: str, params: dict[str, Any]) -> httpx.Response:
    try:
        response = client.get(path, params=params)
        response.raise_for_status()
        return response
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code in {401, 403}:
            raise MarketDataError("Alpaca rejected the market data request. Check your API keys and feed entitlements.") from exc
        if exc.response.status_code == 429:
            raise MarketDataError("Alpaca rate-limited the market data request. Please try again in a moment.") from exc
        raise MarketDataError("Alpaca market data request failed.") from exc
    except httpx.HTTPError as exc:
        raise MarketDataError("Could not reach Alpaca market data.") from exc


def _normalize_symbols(symbols: list[str]) -> list[str]:
    return sorted({symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()})


def _extract_snapshot_map(payload: dict[str, Any]) -> dict[str, Any]:
    snapshots = payload.get("snapshots")
    if isinstance(snapshots, dict):
        return snapshots
    return payload


def _chunked(items: list[str], size: int) -> list[list[str]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def _normalize_equity_snapshot(symbol: str, snapshot: dict[str, Any], feed: str) -> dict[str, Any]:
    latest_trade = snapshot.get("latestTrade") or {}
    latest_quote = snapshot.get("latestQuote") or {}
    daily_bar = snapshot.get("dailyBar") or {}
    previous_daily_bar = snapshot.get("prevDailyBar") or {}

    trade_price = _optional_decimal_string(latest_trade.get("p"))
    bid_price = _optional_decimal_string(latest_quote.get("bp"))
    ask_price = _optional_decimal_string(latest_quote.get("ap"))
    mark_price = trade_price or _midpoint_string(bid_price, ask_price) or _optional_decimal_string(daily_bar.get("c"))

    return {
        "symbol": symbol,
        "asset_class": AssetClass.STOCK.value,
        "found": True,
        "provider": "alpaca",
        "feed": feed,
        "mark_price": mark_price,
        "last_trade_price": trade_price,
        "bid_price": bid_price,
        "ask_price": ask_price,
        "change_percent": _percent_change_string(daily_bar.get("c"), previous_daily_bar.get("c")),
        "as_of": latest_trade.get("t") or latest_quote.get("t") or daily_bar.get("t"),
        "note": None,
    }


def _normalize_option_snapshot(symbol: str, snapshot: dict[str, Any], feed: str) -> dict[str, Any]:
    latest_trade = snapshot.get("latestTrade") or {}
    latest_quote = snapshot.get("latestQuote") or {}

    trade_price = _optional_decimal_string(latest_trade.get("p"))
    bid_price = _optional_decimal_string(latest_quote.get("bp"))
    ask_price = _optional_decimal_string(latest_quote.get("ap"))
    mark_price = _midpoint_string(bid_price, ask_price) or trade_price

    note = None
    if feed == "indicative":
        note = "Indicative option feed in use. OPRA requires a paid entitlement."

    return {
        "symbol": symbol,
        "asset_class": AssetClass.OPTION.value,
        "found": True,
        "provider": "alpaca",
        "feed": feed,
        "mark_price": mark_price,
        "last_trade_price": trade_price,
        "bid_price": bid_price,
        "ask_price": ask_price,
        "change_percent": None,
        "as_of": latest_trade.get("t") or latest_quote.get("t"),
        "note": note,
    }


def _not_found_quote(symbol: str, asset_class: str, feed: str) -> dict[str, Any]:
    return {
        "symbol": symbol,
        "asset_class": asset_class,
        "found": False,
        "provider": "alpaca",
        "feed": feed,
        "mark_price": None,
        "last_trade_price": None,
        "bid_price": None,
        "ask_price": None,
        "change_percent": None,
        "as_of": None,
        "note": "No market data was returned for this symbol.",
    }


def _optional_decimal_string(value: Any) -> str | None:
    if value is None:
        return None
    try:
        return _format_decimal(Decimal(str(value)))
    except (InvalidOperation, ValueError):
        return None


def _midpoint_string(bid_price: str | None, ask_price: str | None) -> str | None:
    if bid_price is None or ask_price is None:
        return None

    try:
        midpoint = (Decimal(bid_price) + Decimal(ask_price)) / Decimal("2")
    except (InvalidOperation, ValueError):
        return None
    return _format_decimal(midpoint)


def _percent_change_string(current_value: Any, previous_value: Any) -> str | None:
    try:
        current = Decimal(str(current_value))
        previous = Decimal(str(previous_value))
    except (InvalidOperation, ValueError):
        return None

    if previous == ZERO:
        return None
    return _format_decimal(((current - previous) / previous) * Decimal("100"), places=4)


def _feed_for_asset_class(asset_class: str, capabilities: dict[str, Any]) -> str | None:
    if asset_class in SUPPORTED_EQUITY_ASSET_CLASSES:
        return capabilities.get("stock_feed")
    if asset_class in SUPPORTED_OPTION_ASSET_CLASSES:
        return capabilities.get("option_feed")
    return None


def _format_decimal(value: Decimal, *, places: int = 6) -> str:
    return format(value, f".{places}f")
