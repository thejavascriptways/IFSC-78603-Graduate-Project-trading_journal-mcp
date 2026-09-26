"""News provider adapters."""

from app.providers.news.base import NewsProvider, NewsProviderError
from app.providers.news.demo import DemoNewsProvider
from app.providers.news.gdelt import GdeltNewsProvider
from app.providers.news.yahoo import YahooFinanceNewsProvider

__all__ = [
    "DemoNewsProvider",
    "GdeltNewsProvider",
    "NewsProvider",
    "NewsProviderError",
    "YahooFinanceNewsProvider",
]
