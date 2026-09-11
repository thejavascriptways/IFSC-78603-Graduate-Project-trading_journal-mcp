from __future__ import annotations

from datetime import date
from decimal import Decimal, InvalidOperation
from urllib.parse import urlencode

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.audit.events import AuditEventStatus, ClientType
from app.audit.service import list_recent_audit_logs, log_user_action
from app.config import settings
from app.db import get_session
from app.models.enums import AssetClass, OrderSide
from app.schemas import ManualTradeCreate, OpeningHoldingCreate, PositionMarkUpdate
from app.services.holding_import import (
    HoldingImportCsvError,
    OPENING_HOLDING_SAMPLE_CSV,
    import_opening_holdings_from_csv,
)
from app.services.market_data_settings import (
    MarketDataSettingsError,
    clear_alpaca_market_data_settings,
    get_alpaca_settings_view_model,
    save_alpaca_market_data_settings,
)
from app.services.market_data import (
    MarketDataError,
    apply_live_market_data_to_open_positions,
    build_live_market_data_rows,
    build_portfolio_market_data_targets,
    fetch_live_market_data_from_mcp,
)
from app.services.mcp_host import list_registered_mcp_servers
from app.services.portfolio import (
    PortfolioError,
    get_dashboard_data,
    get_position,
    get_portfolio_summary,
    import_opening_holding,
    list_accounts,
    list_closed_positions,
    list_manual_accounts,
    list_positions,
    list_trades,
    record_manual_trade,
    update_position_market_price,
)


def create_web_router(templates: Jinja2Templates) -> APIRouter:
    router = APIRouter()

    def build_trade_form_context(
        session: Session,
        *,
        error: str | None = None,
        form_values: dict[str, str] | None = None,
        position_id: int | None = None,
    ) -> dict[str, object]:
        defaults = {
            "account_id": "",
            "symbol": "",
            "description": "",
            "asset_class": AssetClass.STOCK.value,
            "trade_date": date.today().isoformat(),
            "side": OrderSide.BUY.value,
            "quantity": "",
            "price": "",
            "fees": "0",
            "reason": "",
            "notes": "",
            "currency": "USD",
            "form_mode": "manual",
            "position_id": str(position_id or ""),
        }
        close_position = get_position(session, position_id) if position_id is not None else None

        if close_position is not None and close_position.quantity > 0 and form_values is None:
            defaults.update(
                {
                    "account_id": str(close_position.account_id),
                    "symbol": close_position.instrument.symbol,
                    "description": close_position.instrument.description or "",
                    "asset_class": close_position.instrument.asset_class.value,
                    "side": OrderSide.SELL.value,
                    "quantity": str(close_position.quantity),
                    "price": str(
                        close_position.market_price
                        if close_position.market_price is not None
                        else close_position.average_cost
                    ),
                    "currency": close_position.instrument.currency,
                    "form_mode": "close",
                    "position_id": str(close_position.id),
                }
            )

        if form_values is not None:
            defaults.update({key: value for key, value in form_values.items() if value is not None})

        return {
            "accounts": list_accounts(session),
            "asset_classes": list(AssetClass),
            "sides": list(OrderSide),
            "error": error,
            "today": defaults["trade_date"],
            "defaults": defaults,
            "close_position": close_position,
            "form_mode": defaults["form_mode"],
        }

    def build_mcp_console_context(
        *,
        error: str | None = None,
        notice: str | None = None,
        selected_server_id: str = "trading_journal",
    ) -> dict[str, object]:
        return {
            "error": error,
            "notice": notice,
            "servers": list_registered_mcp_servers(),
            "selected_server_id": selected_server_id,
        }

    def build_holding_import_context(
        session: Session,
        *,
        error: str | None = None,
        notice: str | None = None,
        bulk_errors: list[str] | None = None,
    ) -> dict[str, object]:
        return {
            "accounts": list_manual_accounts(session),
            "asset_classes": list(AssetClass),
            "error": error,
            "notice": notice,
            "today": date.today().isoformat(),
            "sample_csv": OPENING_HOLDING_SAMPLE_CSV,
            "bulk_errors": bulk_errors or [],
        }

    @router.get("/", response_class=HTMLResponse)
    def dashboard(request: Request, session: Session = Depends(get_session)):
        data = get_dashboard_data(session)
        portfolio_summary = get_portfolio_summary(session)
        return templates.TemplateResponse(
            request=request,
            name="dashboard.html",
            context={
                "accounts": data.accounts,
                "closed_positions": data.closed_positions,
                "open_positions": data.open_positions,
                "portfolio_summary": portfolio_summary,
                "recent_trades": data.recent_trades,
                "total_cost_basis": data.total_cost_basis,
            },
        )

    @router.get("/trades", response_class=HTMLResponse)
    def trades_page(request: Request, session: Session = Depends(get_session)):
        return templates.TemplateResponse(request=request, name="trades.html", context={"trades": list_trades(session)})

    @router.get("/positions", response_class=HTMLResponse)
    def positions_page(
        request: Request,
        session: Session = Depends(get_session),
        error: str | None = None,
        notice: str | None = None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="positions.html",
            context={
                "positions": list_positions(session),
                "error": error,
                "notice": notice,
            },
        )

    @router.get("/positions/closed", response_class=HTMLResponse)
    def closed_positions_page(request: Request, session: Session = Depends(get_session)):
        return templates.TemplateResponse(
            request=request,
            name="closed_positions.html",
            context={"closed_positions": list_closed_positions(session)},
        )

    @router.get("/market-data", response_class=HTMLResponse)
    async def market_data_page(
        request: Request,
        session: Session = Depends(get_session),
        error: str | None = None,
        notice: str | None = None,
    ):
        targets = build_portfolio_market_data_targets(session)
        capabilities = {}
        live_rows = []
        error_message = error

        try:
            live_payload = await fetch_live_market_data_from_mcp(request.app, targets)
            capabilities = live_payload["capabilities"]
            live_rows = build_live_market_data_rows(
                targets,
                live_payload["lookup"],
                capabilities,
            )
        except MarketDataError as exc:
            capabilities = {"provider": settings.market_data_provider}
            live_rows = build_live_market_data_rows(targets, {}, capabilities)
            error_message = str(exc)

        if capabilities.get("configured") is not True and error_message is None:
            error_message = "Live market data is not configured. Add Alpaca credentials under Configuration > Alpaca Settings."

        return templates.TemplateResponse(
            request=request,
            name="market_data.html",
            context={
                "error": error_message,
                "notice": notice,
                "market_data_rows": live_rows,
                "capabilities": capabilities,
                "market_data_mcp_url": "/market-data-mcp/",
                "trading_journal_mcp_url": "/mcp/",
            },
        )

    @router.get("/mcp-console", response_class=HTMLResponse)
    def mcp_console_page(
        request: Request,
        error: str | None = None,
        notice: str | None = None,
        selected_server_id: str = "trading_journal",
    ):
        return templates.TemplateResponse(
            request=request,
            name="mcp_console.html",
            context=build_mcp_console_context(
                error=error,
                notice=notice,
                selected_server_id=selected_server_id,
            ),
        )

    @router.get("/audit", response_class=HTMLResponse)
    def audit_page(request: Request, session: Session = Depends(get_session)):
        return templates.TemplateResponse(
            request=request,
            name="audit.html",
            context={"audit_logs": list_recent_audit_logs(session, limit=50)},
        )

    @router.get("/settings/market-data/alpaca", response_class=HTMLResponse)
    def alpaca_settings_page(
        request: Request,
        error: str | None = None,
        notice: str | None = None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="alpaca_settings.html",
            context={
                "error": error,
                "notice": notice,
                "alpaca_settings": get_alpaca_settings_view_model(),
            },
        )

    @router.post("/settings/market-data/alpaca", response_class=HTMLResponse)
    def save_alpaca_settings(
        request: Request,
        api_key_id: str | None = Form(default=None),
        api_secret_key: str | None = Form(default=None),
        stock_feed: str = Form(...),
        option_feed: str = Form(...),
        base_url: str = Form(...),
        session: Session = Depends(get_session),
    ):
        try:
            saved_settings = save_alpaca_market_data_settings(
                api_key_id=api_key_id,
                api_secret_key=api_secret_key,
                stock_feed=stock_feed,
                option_feed=option_feed,
                base_url=base_url,
            )
            log_user_action(
                session,
                action="save_alpaca_market_data_settings",
                client_type=ClientType.WEB_UI,
                method=request.method,
                path=request.url.path,
                status=AuditEventStatus.SUCCESS,
                message="Alpaca market-data settings were saved.",
                metadata={
                    "configured": saved_settings.configured,
                    "source": saved_settings.source,
                    "stock_feed": saved_settings.stock_feed,
                    "option_feed": saved_settings.option_feed,
                    "base_url": saved_settings.base_url,
                    "api_key_id": saved_settings.masked_api_key_id,
                    "api_secret_key": saved_settings.secret_status,
                },
            )
        except MarketDataSettingsError as exc:
            session.rollback()
            return templates.TemplateResponse(
                request=request,
                name="alpaca_settings.html",
                context={
                    "error": str(exc),
                    "notice": None,
                    "alpaca_settings": get_alpaca_settings_view_model(),
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return RedirectResponse(
            url="/settings/market-data/alpaca?notice=Alpaca+settings+saved",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @router.post("/settings/market-data/alpaca/clear", response_class=HTMLResponse)
    def clear_alpaca_settings(request: Request, session: Session = Depends(get_session)):
        clear_alpaca_market_data_settings()
        log_user_action(
            session,
            action="clear_alpaca_market_data_settings",
            client_type=ClientType.WEB_UI,
            method=request.method,
            path=request.url.path,
            status=AuditEventStatus.SUCCESS,
            message="Saved Alpaca market-data settings were cleared.",
            metadata={
                "environment_fallback_available": bool(
                    settings.alpaca_api_key_id or settings.alpaca_api_secret_key
                )
            },
        )
        return RedirectResponse(
            url="/settings/market-data/alpaca?notice=Saved+Alpaca+settings+cleared",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @router.get("/trades/new", response_class=HTMLResponse)
    def new_trade_form(
        request: Request,
        session: Session = Depends(get_session),
        error: str | None = None,
        position_id: int | None = None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="trade_form.html",
            context=build_trade_form_context(session, error=error, position_id=position_id),
        )

    @router.get("/holdings/import", response_class=HTMLResponse)
    def import_holding_form(
        request: Request,
        session: Session = Depends(get_session),
        error: str | None = None,
        notice: str | None = None,
    ):
        return templates.TemplateResponse(
            request=request,
            name="holding_import_form.html",
            context=build_holding_import_context(session, error=error, notice=notice),
        )

    @router.post("/trades", response_class=HTMLResponse)
    def create_trade(
        request: Request,
        account_id: int = Form(...),
        symbol: str = Form(...),
        description: str | None = Form(default=None),
        asset_class: AssetClass = Form(...),
        trade_date: date = Form(...),
        side: OrderSide = Form(...),
        quantity: str = Form(...),
        price: str = Form(...),
        fees: str = Form(default="0"),
        reason: str = Form(...),
        notes: str | None = Form(default=None),
        currency: str = Form(default="USD"),
        position_id: int | None = Form(default=None),
        form_mode: str = Form(default="manual"),
        session: Session = Depends(get_session),
    ):
        try:
            payload = ManualTradeCreate(
                account_id=account_id,
                symbol=symbol,
                description=description,
                asset_class=asset_class,
                trade_date=trade_date,
                side=side,
                quantity=Decimal(quantity),
                price=Decimal(price),
                fees=Decimal(fees),
                reason=reason,
                notes=notes,
                currency=currency,
            )
            record_manual_trade(session, payload)
        except (PortfolioError, ValidationError, ValueError, InvalidOperation) as exc:
            session.rollback()
            form_values = {
                "account_id": str(account_id),
                "symbol": symbol,
                "description": description or "",
                "asset_class": asset_class.value,
                "trade_date": trade_date.isoformat(),
                "side": side.value,
                "quantity": quantity,
                "price": price,
                "fees": fees,
                "reason": reason,
                "notes": notes or "",
                "currency": currency,
                "position_id": str(position_id or ""),
                "form_mode": form_mode,
            }
            return templates.TemplateResponse(
                request=request,
                name="trade_form.html",
                context=build_trade_form_context(
                    session,
                    error=str(exc),
                    form_values=form_values,
                    position_id=position_id,
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if form_mode == "close" and position_id is not None:
            updated_position = get_position(session, position_id)
            if updated_position is not None and updated_position.quantity == 0:
                return RedirectResponse(
                    url="/positions/closed",
                    status_code=status.HTTP_303_SEE_OTHER,
                )
            return RedirectResponse(url="/positions", status_code=status.HTTP_303_SEE_OTHER)

        return RedirectResponse(url="/trades", status_code=status.HTTP_303_SEE_OTHER)

    @router.post("/positions/refresh-market-data", response_class=HTMLResponse)
    async def refresh_market_data_marks(request: Request, session: Session = Depends(get_session)):
        targets = build_portfolio_market_data_targets(session)
        open_targets = [target for target in targets if target["status"] == "OPEN"]
        if not open_targets:
            return RedirectResponse(
                url=f"/positions?{urlencode({'notice': 'No open positions to refresh.'})}",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        try:
            live_payload = await fetch_live_market_data_from_mcp(request.app, open_targets)
            if live_payload["capabilities"].get("configured") is not True:
                raise MarketDataError("Live market data is not configured. Add Alpaca credentials under Configuration > Alpaca Settings.")
            refresh_result = apply_live_market_data_to_open_positions(
                session,
                open_targets,
                live_payload["lookup"],
            )
        except (MarketDataError, PortfolioError) as exc:
            session.rollback()
            return templates.TemplateResponse(
                request=request,
                name="positions.html",
                context={
                    "positions": list_positions(session),
                    "error": str(exc),
                    "notice": None,
                },
                status_code=status.HTTP_502_BAD_GATEWAY,
            )

        notice_parts = [
            f"Refreshed {refresh_result['updated_position_count']} position(s) from Market Data MCP."
        ]
        if refresh_result["missing_symbols"]:
            notice_parts.append(
                "Missing quotes for: " + ", ".join(refresh_result["missing_symbols"]) + "."
            )

        return RedirectResponse(
            url=f"/positions?{urlencode({'notice': ' '.join(notice_parts)})}",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @router.post("/positions/{position_id}/mark", response_class=HTMLResponse)
    def update_mark_price(
        request: Request,
        position_id: int,
        market_price: str = Form(...),
        session: Session = Depends(get_session),
    ):
        try:
            payload = PositionMarkUpdate(market_price=Decimal(market_price))
            update_position_market_price(session, position_id, payload.market_price)
        except (PortfolioError, ValidationError, ValueError, InvalidOperation) as exc:
            session.rollback()
            return templates.TemplateResponse(
                request=request,
                name="positions.html",
                context={
                    "positions": list_positions(session),
                    "error": str(exc),
                    "notice": None,
                },
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return RedirectResponse(
            url="/positions?notice=Market+price+updated",
            status_code=status.HTTP_303_SEE_OTHER,
        )

    @router.post("/holdings/import", response_class=HTMLResponse)
    def create_opening_holding(
        request: Request,
        account_id: int = Form(...),
        symbol: str = Form(...),
        description: str | None = Form(default=None),
        asset_class: AssetClass = Form(...),
        opening_date: date = Form(...),
        quantity: str = Form(...),
        average_cost: str = Form(...),
        notes: str | None = Form(default=None),
        currency: str = Form(default="USD"),
        session: Session = Depends(get_session),
    ):
        try:
            payload = OpeningHoldingCreate(
                account_id=account_id,
                symbol=symbol,
                description=description,
                asset_class=asset_class,
                opening_date=opening_date,
                quantity=Decimal(quantity),
                average_cost=Decimal(average_cost),
                notes=notes,
                currency=currency,
            )
            import_opening_holding(session, payload)
        except (PortfolioError, ValidationError, ValueError, InvalidOperation) as exc:
            session.rollback()
            return templates.TemplateResponse(
                request=request,
                name="holding_import_form.html",
                context=build_holding_import_context(session, error=str(exc)),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        return RedirectResponse(url="/positions", status_code=status.HTTP_303_SEE_OTHER)

    @router.post("/holdings/import/csv", response_class=HTMLResponse)
    async def create_opening_holdings_from_csv(
        request: Request,
        csv_file: UploadFile = File(...),
        session: Session = Depends(get_session),
    ):
        if not csv_file.filename or not csv_file.filename.lower().endswith(".csv"):
            return templates.TemplateResponse(
                request=request,
                name="holding_import_form.html",
                context=build_holding_import_context(session, error="Please upload a .csv file."),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        try:
            csv_bytes = await csv_file.read()
            result = import_opening_holdings_from_csv(session, csv_bytes)
        except HoldingImportCsvError as exc:
            session.rollback()
            return templates.TemplateResponse(
                request=request,
                name="holding_import_form.html",
                context=build_holding_import_context(session, error=str(exc)),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        if result.imported_count == 0 and result.failed_count > 0:
            return templates.TemplateResponse(
                request=request,
                name="holding_import_form.html",
                context=build_holding_import_context(
                    session,
                    error="No holdings were imported. Please review the row errors below.",
                    bulk_errors=result.row_errors,
                ),
                status_code=status.HTTP_400_BAD_REQUEST,
            )

        notice_parts = [f"Imported {result.imported_count} holding(s) from CSV."]
        if result.failed_count:
            notice_parts.append(f"{result.failed_count} row(s) failed.")

        return templates.TemplateResponse(
            request=request,
            name="holding_import_form.html",
            context=build_holding_import_context(
                session,
                notice=" ".join(notice_parts),
                bulk_errors=result.row_errors,
            ),
            status_code=status.HTTP_207_MULTI_STATUS if result.failed_count else status.HTTP_200_OK,
        )

    return router
