from __future__ import annotations

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.audit.service import list_recent_audit_logs
from app.db import get_session
from app.schemas import (
    MCPPromptReadRequest,
    MCPResourceReadRequest,
    MCPToolCallRequest,
    ManualTradeCreate,
    OpeningHoldingCreate,
    PositionMarkUpdate,
)
from app.services.market_data import (
    MarketDataError,
    apply_live_market_data_to_open_positions,
    build_live_market_data_rows,
    build_portfolio_market_data_targets,
    fetch_live_market_data_from_mcp,
)
from app.services.mcp_host import (
    MCPHostError,
    call_server_tool,
    get_server_prompt,
    list_registered_mcp_servers,
    list_server_catalog,
    read_server_resource,
)
from app.services.portfolio import (
    PortfolioError,
    get_portfolio_summary,
    import_opening_holding,
    list_accounts,
    list_closed_positions,
    list_positions,
    list_trades,
    record_manual_trade,
    serialize_account,
    serialize_closed_position,
    serialize_position,
    serialize_trade,
    update_position_market_price,
)


def create_api_router() -> APIRouter:
    router = APIRouter(prefix="/api")

    @router.get("/accounts")
    def api_accounts(session: Session = Depends(get_session)):
        return [serialize_account(account) for account in list_accounts(session)]

    @router.get("/portfolio-summary")
    def api_portfolio_summary(session: Session = Depends(get_session)):
        return get_portfolio_summary(session)

    @router.get("/positions")
    def api_positions(session: Session = Depends(get_session)):
        return [serialize_position(position) for position in list_positions(session)]

    @router.get("/closed-positions")
    def api_closed_positions(session: Session = Depends(get_session)):
        return [serialize_closed_position(position) for position in list_closed_positions(session)]

    @router.get("/trades")
    def api_trades(session: Session = Depends(get_session)):
        return [serialize_trade(trade) for trade in list_trades(session)]

    @router.get("/audit/logs")
    def api_audit_logs(session: Session = Depends(get_session), limit: int = 100):
        return list_recent_audit_logs(session, limit=min(max(limit, 1), 500))

    @router.get("/market-data/live")
    async def api_market_data_live(request: Request, session: Session = Depends(get_session)):
        targets = build_portfolio_market_data_targets(session)
        live_payload = await fetch_live_market_data_from_mcp(request.app, targets)
        return {
            "capabilities": live_payload["capabilities"],
            "rows": build_live_market_data_rows(targets, live_payload["lookup"], live_payload["capabilities"]),
        }

    @router.get("/mcp-console/servers")
    def api_mcp_console_servers():
        return {"servers": list_registered_mcp_servers()}

    @router.get("/mcp-console/catalog")
    async def api_mcp_console_catalog(request: Request, server_id: str):
        try:
            return await list_server_catalog(request.app, server_id)
        except MCPHostError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

    @router.post("/trades")
    def api_create_trade(payload: ManualTradeCreate, session: Session = Depends(get_session)):
        try:
            trade = record_manual_trade(session, payload)
        except PortfolioError as exc:
            session.rollback()
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(
            {
                **serialize_trade(trade),
                "account_id": trade.account_id,
                "instrument_id": trade.instrument_id,
            },
            status_code=status.HTTP_201_CREATED,
        )

    @router.post("/opening-holdings")
    def api_create_opening_holding(payload: OpeningHoldingCreate, session: Session = Depends(get_session)):
        try:
            trade = import_opening_holding(session, payload)
        except PortfolioError as exc:
            session.rollback()
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(
            {
                **serialize_trade(trade),
                "account_id": trade.account_id,
                "instrument_id": trade.instrument_id,
                "average_cost": str(trade.price),
                "cost_basis": str(trade.quantity * trade.price),
            },
            status_code=status.HTTP_201_CREATED,
        )

    @router.post("/positions/{position_id}/mark")
    def api_update_position_mark(
        position_id: int,
        payload: PositionMarkUpdate,
        session: Session = Depends(get_session),
    ):
        try:
            position = update_position_market_price(session, position_id, payload.market_price)
        except PortfolioError as exc:
            session.rollback()
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(serialize_position(position), status_code=status.HTTP_200_OK)

    @router.post("/mcp-console/call-tool")
    async def api_mcp_console_call_tool(request: Request, payload: MCPToolCallRequest):
        try:
            result = await call_server_tool(
                request.app,
                payload.server_id,
                payload.tool_name,
                payload.arguments,
            )
        except MCPHostError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(result, status_code=status.HTTP_200_OK)

    @router.post("/mcp-console/read-resource")
    async def api_mcp_console_read_resource(request: Request, payload: MCPResourceReadRequest):
        try:
            result = await read_server_resource(request.app, payload.server_id, payload.uri)
        except MCPHostError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(result, status_code=status.HTTP_200_OK)

    @router.post("/mcp-console/get-prompt")
    async def api_mcp_console_get_prompt(request: Request, payload: MCPPromptReadRequest):
        try:
            result = await get_server_prompt(
                request.app,
                payload.server_id,
                payload.prompt_name,
                payload.arguments,
            )
        except MCPHostError as exc:
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_400_BAD_REQUEST)

        return JSONResponse(result, status_code=status.HTTP_200_OK)

    @router.post("/positions/refresh-market-data")
    async def api_refresh_market_data_quotes(request: Request, session: Session = Depends(get_session)):
        try:
            targets = build_portfolio_market_data_targets(session)
            open_targets = [target for target in targets if target["status"] == "OPEN"]
            live_payload = await fetch_live_market_data_from_mcp(request.app, open_targets)
            if live_payload["capabilities"].get("configured") is not True:
                raise MarketDataError("Live market data is not configured. Set ALPACA_API_KEY_ID and ALPACA_API_SECRET_KEY.")
            refresh_result = apply_live_market_data_to_open_positions(
                session,
                open_targets,
                live_payload["lookup"],
            )
        except (MarketDataError, PortfolioError) as exc:
            session.rollback()
            return JSONResponse({"detail": str(exc)}, status_code=status.HTTP_502_BAD_GATEWAY)

        return JSONResponse(
            {
                **refresh_result,
                "capabilities": live_payload["capabilities"],
            },
            status_code=status.HTTP_200_OK,
        )

    return router
