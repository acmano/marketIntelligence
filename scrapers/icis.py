"""
Scraper: ICIS (icis.com)
Método: RSS + scraping da página pública de notícias de polímeros
Fonte ID: 2
"""

import feedparser
from datetime import timezone
from email.utils import parsedate_to_datetime
from loguru import logger
from .base_scraper import Artigo, BaseScraper

RSS_URL = "https://www.icis.com/explore/resources/news/feed"

class IcisScraper(BaseScraper):
    def __init__(self):
        super().__init__(fonte_id=2, nome="ICIS")

    def coletar(self) -> list[Artigo]:
        logger.info(f"[ICIS] Buscando RSS: {RSS_URL}")
        feed = feedparser.parse(RSS_URL)
        artigos = []
        for entry in feed.entries:
            try:
                pub = None
                if hasattr(entry, "published"):
                    pub = parsedate_to_datetime(entry.published).astimezone(timezone.utc)
                artigos.append(Artigo(
                    titulo=entry.title,
                    url=entry.link,
                    fonte_id=self.fonte_id,
                    texto_bruto=getattr(entry, "summary", None),
                    data_publicacao=pub,
                ))
            except Exception as e:
                logger.warning(f"[ICIS] Erro: {e}")
        return artigos
