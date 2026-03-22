"""
Scraper: Reuters Commodities
Método: RSS feed
Fonte ID: 1 (conforme seed 002_seed_fontes.sql)
"""

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import feedparser
from loguru import logger

from .base_scraper import Artigo, BaseScraper

FONTE_ID = 1
RSS_URL = "https://feeds.reuters.com/reuters/businessNews"


class ReutersScraper(BaseScraper):
    def __init__(self):
        super().__init__(fonte_id=FONTE_ID, nome="Reuters Commodities")

    def coletar(self) -> list[Artigo]:
        logger.info(f"[Reuters] Buscando RSS: {RSS_URL}")
        feed = feedparser.parse(RSS_URL)

        if feed.bozo:
            logger.warning(f"[Reuters] Aviso no parsing do feed: {feed.bozo_exception}")

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
                logger.warning(f"[Reuters] Erro ao processar entrada: {e}")

        return artigos
