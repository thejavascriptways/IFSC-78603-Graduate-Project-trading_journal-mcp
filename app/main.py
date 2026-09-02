from __future__ import annotations

from contextlib import AsyncExitStack, asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from app.audit.middleware import AuditMiddleware
from app.audit.service import log_application_event
from app.config import settings
from app.db import init_db, session_scope
from app.market_data_mcp import create_market_data_mcp_server
from app.mcp_server import create_mcp_server
from app.mcp_servers import create_broker_mcp_server, create_news_mcp_server, create_trading_mcp_server
from app.routes import create_api_router, create_web_router
from app.services.portfolio import seed_default_accounts


def create_app() -> FastAPI:
    trading_journal_mcp = create_mcp_server()
    market_data_mcp = create_market_data_mcp_server()
    news_mcp = create_news_mcp_server()
    broker_mcp = create_broker_mcp_server()
    trading_mcp = create_trading_mcp_server()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        init_db()
        async with AsyncExitStack() as stack:
            with session_scope() as session:
                seed_default_accounts(session)
            log_application_event(
                event_type="application_startup",
                message="Trading Journal application startup completed.",
                metadata={"mcp_servers": ["trading_journal", "market_data", "news", "broker", "trading"]},
            )
            await stack.enter_async_context(trading_journal_mcp.session_manager.run())
            await stack.enter_async_context(market_data_mcp.session_manager.run())
            await stack.enter_async_context(news_mcp.session_manager.run())
            await stack.enter_async_context(broker_mcp.session_manager.run())
            await stack.enter_async_context(trading_mcp.session_manager.run())
            yield

    application = FastAPI(title=settings.app_name, lifespan=lifespan)
    templates = Jinja2Templates(directory=str(settings.templates_dir))

    application.add_middleware(AuditMiddleware)
    application.mount("/static", StaticFiles(directory=str(settings.static_dir)), name="static")
    application.include_router(create_web_router(templates))
    application.include_router(create_api_router())

    application.mount("/mcp", trading_journal_mcp.streamable_http_app(), name="trading-journal-mcp")
    application.mount("/market-data-mcp", market_data_mcp.streamable_http_app(), name="market-data-mcp")
    application.mount("/news-mcp", news_mcp.streamable_http_app(), name="news-mcp")
    application.mount("/broker-mcp", broker_mcp.streamable_http_app(), name="broker-mcp")
    application.mount("/trading-mcp", trading_mcp.streamable_http_app(), name="trading-mcp")

    return application


app = create_app()
