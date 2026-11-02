from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from time import perf_counter
from typing import Any
from urllib.parse import quote

import httpx

from app.audit.events import AuditEventStatus
from app.audit.service import duration_ms_since, log_external_api_call
from app.config import settings
from app.providers.market_data.base import MarketDataProviderError


FEED = "yahoo_chart"
SNAPSHOT_NOTE = "Yahoo Finance snapshot; may be delayed. As Of is the source price timestamp, not the fetch time."


class _SymbolUnavailable(MarketDataProviderError):
    pass


class YahooFinanceMarketDataProvider:
    """Key-free demo adapter using Yahoo's public chart data, not a streaming feed."""

    name = "yahoo_finance"

    def __init__(self, *, transport: httpx.BaseTransport | None = None) -> None:
        self.transport = transport

    def get_capabilities(self) -> dict[str, Any]:
        return {
            "provider": self.name,
            "configured": True,
            "source": "Yahoo Finance public chart endpoint",
            "requires_api_key": False,
            "stock_feed": FEED,
            "option_feed": FEED,
            "base_url": settings.yahoo_finance_base_url,
            "notes": [
                "Yahoo Finance is an optional demo quote provider. No API keys are required for this provider.",
                SNAPSHOT_NOTE,
                "Stocks and ETFs use the latest regular-session price available from Yahoo.",
                "Options use the exact contract symbol where Yahoo chart data is available; expired or unsupported contracts may return no data.",
                "Bid/ask quotes are not supplied by this chart integration and remain blank.",
                "Mutual fund NAV lookup and individual bond quotes are not implemented.",
                "This unofficial endpoint may change or rate-limit requests; review source terms before production use.",
            ],
        }

    def get_equity_snapshots(self, symbols: list[str]) -> dict[str, Any]:
        return self._get_snapshots(symbols, asset_class="STOCK")

    def get_option_snapshots(self, symbols: list[str]) -> dict[str, Any]:
        return self._get_snapshots(symbols, asset_class="OPTION")

    def _get_snapshots(self, symbols: list[str], *, asset_class: str) -> dict[str, Any]:
        normalized = sorted({symbol.strip().upper() for symbol in symbols if symbol and symbol.strip()})
        quotes = []
        with httpx.Client(
            base_url=settings.yahoo_finance_base_url,
            timeout=settings.market_data_timeout_seconds,
            headers={"User-Agent": "Mozilla/5.0 TradingJournalMCP/0.1", "Accept": "application/json"},
            transport=self.transport,
            follow_redirects=True,
        ) as client:
            for symbol in normalized:
                # Yahoo uses hyphens for share classes; preserve the caller's symbol in the result.
                yahoo_symbol = symbol
                if asset_class == "STOCK" and symbol.endswith((".A", ".B")):
                    yahoo_symbol = symbol[:-2] + "-" + symbol[-1]
                elif asset_class == "OPTION":
                    yahoo_symbol = symbol.removeprefix("O:").replace(" ", "")
                try:
                    result = self._request(client, yahoo_symbol)
                    quotes.append(_normalize_snapshot(symbol, result, asset_class))
                except MarketDataProviderError as exc:
                    quotes.append({
                        "symbol": symbol,
                        "provider": self.name,
                        "asset_class": asset_class,
                        "feed": FEED,
                        "found": False,
                        "mark_price": None,
                        "as_of": None,
                        "data_status": "NO_DATA" if isinstance(exc, _SymbolUnavailable) else "ERROR",
                        "note": str(exc),
                    })
        return {
            "provider": self.name,
            "asset_class": asset_class,
            "feed": FEED,
            "quotes": quotes,
            "missing_symbols": [item["symbol"] for item in quotes if not item["found"]],
        }

    def _request(self, client: httpx.Client, symbol: str) -> dict[str, Any]:
        path = f"/v8/finance/chart/{quote(symbol, safe='')}"
        params = {"range": "1d", "interval": "1m", "includePrePost": "false"}
        started_at = perf_counter()
        status_code = None
        try:
            response = client.get(path, params=params)
            status_code = response.status_code
            if status_code == 404:
                raise _SymbolUnavailable(f"Yahoo Finance has no chart data for {symbol}.")
            response.raise_for_status()
            payload = response.json()
            chart = payload.get("chart") if isinstance(payload, dict) else None
            if not isinstance(chart, dict):
                raise MarketDataProviderError("Yahoo Finance returned an unexpected chart response.")
            error = chart.get("error")
            if error:
                if isinstance(error, dict) and error.get("code") == "Not Found":
                    raise _SymbolUnavailable(f"Yahoo Finance has no chart data for {symbol}.")
                raise MarketDataProviderError(f"Yahoo Finance could not return chart data for {symbol}.")
            results = chart.get("result")
            if not results:
                raise _SymbolUnavailable(f"Yahoo Finance has no chart data for {symbol}.")
            if not isinstance(results, list) or not isinstance(results[0], dict):
                raise MarketDataProviderError("Yahoo Finance returned an unexpected chart result.")
            result = results[0]
            # Validate before marking the external call successful in the audit log.
            _normalize_snapshot(symbol, result, "STOCK")
        except (httpx.HTTPError, ValueError, MarketDataProviderError) as exc:
            message = str(exc) if isinstance(exc, MarketDataProviderError) else "Could not retrieve or parse Yahoo Finance market data."
            if status_code == 429:
                message = "Yahoo Finance rate-limited this request. Please try again later."
            elif status_code in {401, 403}:
                message = "Yahoo Finance refused this market-data request. Please try again later."
            log_external_api_call(
                provider=self.name, operation="market_data_request", endpoint=path,
                status=AuditEventStatus.FAILURE, status_code=status_code,
                duration_ms=duration_ms_since(started_at), message=message,
                request_metadata={"symbol": symbol, "params": params},
            )
            if isinstance(exc, _SymbolUnavailable):
                raise
            raise MarketDataProviderError(message) from exc
        log_external_api_call(
            provider=self.name, operation="market_data_request", endpoint=path,
            status=AuditEventStatus.SUCCESS, status_code=status_code,
            duration_ms=duration_ms_since(started_at), message="Yahoo Finance market-data snapshot received.",
            request_metadata={"symbol": symbol, "params": params},
        )
        return result


def _number(value: Any) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = Decimal(str(value))
        return number if number.is_finite() else None
    except (InvalidOperation, ValueError):
        return None


def _timestamp(value: Any) -> str | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        number = float(value)
        return datetime.fromtimestamp(number, UTC).isoformat() if number > 0 else None
    except (TypeError, ValueError, OSError, OverflowError):
        return None


def _normalize_snapshot(symbol: str, result: dict[str, Any], asset_class: str) -> dict[str, Any]:
    meta = result.get("meta")
    if not isinstance(meta, dict):
        raise MarketDataProviderError("Yahoo Finance returned chart data without price metadata.")
    price = _number(meta.get("regularMarketPrice"))
    as_of = _timestamp(meta.get("regularMarketTime"))
    # A price is usable only with its matching source timestamp; never invent freshness.
    if price is None or price <= 0 or as_of is None:
        raise _SymbolUnavailable(f"Yahoo Finance returned no usable timestamped price for {symbol}.")
    previous_close = _number(meta.get("previousClose"))
    if previous_close is None:
        previous_close = _number(meta.get("chartPreviousClose"))
    change = ((price - previous_close) / previous_close) * 100 if previous_close and previous_close > 0 else None
    return {
        "symbol": symbol, "provider": "yahoo_finance", "asset_class": asset_class,
        "feed": FEED, "found": True, "data_status": "SNAPSHOT", "note": SNAPSHOT_NOTE,
        "mark_price": format(price, ".6f"), "last_trade_price": format(price, ".6f"),
        "bid_price": None, "ask_price": None,
        "change_percent": format(change, ".4f") if change is not None else None,
        "as_of": as_of, "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
    }
