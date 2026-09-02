"""News provider adapters."""

from app.providers.news.base import NewsProvider, NewsProviderError
from app.providers.news.demo import DemoNewsProvider

__all__ = ["DemoNewsProvider", "NewsProvider", "NewsProviderError"]
