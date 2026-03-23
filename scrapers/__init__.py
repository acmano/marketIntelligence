"""Scrapers de coleta de noticias por fonte."""

from .base_scraper import BaseScraper, ArtigoColetado
from .rss_scrapers import (
    RssGenericScraper,
    ReutersScraper,
    IcisScraper,
    PlasticsNewsScraper,
    BloombergScraper,
    FinancialTimesScraper,
)
from .api_scrapers import (
    WorldBankScraper,
    TradeMapScraper,
    AbiplastScraper,
    AbiquimScraper,
)

__all__ = [
    "BaseScraper", "ArtigoColetado", "RssGenericScraper",
    "ReutersScraper", "IcisScraper", "PlasticsNewsScraper",
    "BloombergScraper", "FinancialTimesScraper",
    "WorldBankScraper", "TradeMapScraper",
    "AbiplastScraper", "AbiquimScraper",
]
