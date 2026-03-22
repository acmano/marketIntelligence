"""
Scrapers para fontes baseadas em RSS feed.
Todos usam feedparser e herdam BaseScraper.
O slug passado ao super().__init__() deve corresponder
ao campo slug cadastrado em mi.fontes.
"""

from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from loguru import logger

from .base_scraper import ArtigoColetado, BaseScraper


def _parse_feed(slug: str, nome: str, rss_url: str) -> list[ArtigoColetado]:
    """Helper genérico: parseia um RSS feed e retorna lista de ArtigoColetado."""
    logger.debug(f"[{nome}] Buscando RSS: {rss_url}")
    feed = feedparser.parse(rss_url)

    if feed.bozo:
        logger.warning(f"[{nome}] Aviso no parsing do feed: {feed.bozo_exception}")

    artigos = []
    for entry in feed.entries:
        try:
            pub = None
            if hasattr(entry, "published"):
                pub = parsedate_to_datetime(entry.published).astimezone(timezone.utc)

            artigos.append(ArtigoColetado(
                titulo=entry.get("title", "").strip(),
                url=entry.get("link", "").strip(),
                texto_bruto=entry.get("summary") or entry.get("description"),
                data_publicacao=pub,
            ))
        except Exception as e:
            logger.warning(f"[{nome}] Entrada ignorada: {e}")

    return artigos


class ReutersScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__(slug="reuters-commodities")

    def coletar(self) -> list[ArtigoColetado]:
        return _parse_feed(
            self._slug, self.nome,
            self.fonte.url_rss or "https://feeds.reuters.com/reuters/businessNews",
        )


class IcisScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__(slug="icis")

    def coletar(self) -> list[ArtigoColetado]:
        return _parse_feed(
            self._slug, self.nome,
            self.fonte.url_rss or "https://www.icis.com/explore/resources/news/feed",
        )


class PlasticsNewsScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__(slug="plastics-news")

    def coletar(self) -> list[ArtigoColetado]:
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)


class BloombergScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__(slug="bloomberg")

    def coletar(self) -> list[ArtigoColetado]:
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)


class FinancialTimesScraper(BaseScraper):
    def __init__(self) -> None:
        super().__init__(slug="financial-times")

    def coletar(self) -> list[ArtigoColetado]:
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)
