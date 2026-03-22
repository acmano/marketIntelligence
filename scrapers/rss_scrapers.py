"""
Scrapers via RSS para fontes secundárias:
- Plastics News (fonte_id=3)
- Bloomberg Markets (fonte_id=6)
- Financial Times (fonte_id=7)

Padrão idêntico ao Reuters/ICIS — todos via feedparser.
"""

import feedparser
from datetime import timezone
from email.utils import parsedate_to_datetime
from loguru import logger
from .base_scraper import Artigo, BaseScraper


def _parse_rss(fonte_id: int, nome: str, rss_url: str) -> list[Artigo]:
    """Helper genérico para fontes RSS simples."""
    logger.info(f"[{nome}] Buscando RSS: {rss_url}")
    feed = feedparser.parse(rss_url)
    artigos = []
    for entry in feed.entries:
        try:
            pub = None
            if hasattr(entry, "published"):
                pub = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
            artigos.append(Artigo(
                titulo=entry.title,
                url=entry.link,
                fonte_id=fonte_id,
                texto_bruto=getattr(entry, "summary", None),
                data_publicacao=pub,
            ))
        except Exception as e:
            logger.warning(f"[{nome}] Erro ao processar entrada: {e}")
    return artigos


class PlasticsNewsScraper(BaseScraper):
    def __init__(self):
        super().__init__(fonte_id=3, nome="Plastics News")

    def coletar(self) -> list[Artigo]:
        return _parse_rss(self.fonte_id, self.nome, "https://www.plasticsnews.com/rss")


class BloombergScraper(BaseScraper):
    def __init__(self):
        super().__init__(fonte_id=6, nome="Bloomberg Markets")

    def coletar(self) -> list[Artigo]:
        return _parse_rss(self.fonte_id, self.nome, "https://feeds.bloomberg.com/markets/news.rss")


class FinancialTimesScraper(BaseScraper):
    def __init__(self):
        super().__init__(fonte_id=7, nome="Financial Times")

    def coletar(self) -> list[Artigo]:
        return _parse_rss(self.fonte_id, self.nome, "https://www.ft.com/rss/home")
