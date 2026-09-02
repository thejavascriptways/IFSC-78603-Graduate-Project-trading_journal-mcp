"""HTTP route modules for the Trading Journal web and JSON APIs."""

from app.routes.api import create_api_router
from app.routes.web import create_web_router

__all__ = ["create_api_router", "create_web_router"]
