"""Scrapers de coleta de notícias por fonte."""

from .base_scraper import BaseScraper, ArtigoColetado
from .rss_scrapers import (
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
    "BaseScraper", "ArtigoColetado",
    "ReutersScraper", "IcisScraper", "PlasticsNewsScraper",
    "BloombergScraper", "FinancialTimesScraper",
    "WorldBankScraper", "TradeMapScraper",
    "AbiplastScraper", "AbiquimScraper",
]
