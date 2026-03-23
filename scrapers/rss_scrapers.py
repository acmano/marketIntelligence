"""
Scrapers para fontes baseadas em RSS feed.

RssGenericScraper: scraper dinamico que funciona para qualquer fonte
com tipo='rss' e url_rss preenchida no banco. Novas fontes RSS podem
ser adicionadas via INSERT no banco sem alterar codigo Python.

Classes legadas (Reuters, ICIS, etc.) mantidas por compatibilidade
mas todas delegam para a mesma logica generica.
Compativel com Python 3.8+
"""

from __future__ import annotations

from datetime import timezone
from email.utils import parsedate_to_datetime
from typing import Optional

import feedparser
from loguru import logger

from .base_scraper import ArtigoColetado, BaseScraper


def _parse_feed(slug, nome, rss_url, usuario=None, senha=None):
    # type: (str, str, str, ..., ...) -> list
    """Helper generico: parseia um RSS feed e retorna lista de ArtigoColetado."""
    if not rss_url:
        logger.warning("[%s] url_rss nao configurada no banco. Pulando.", nome)
        return []

    logger.debug("[%s] Buscando RSS: %s", nome, rss_url)

    # Se ha credenciais, faz GET com Basic Auth e passa o conteudo ao feedparser
    if usuario and senha:
        import requests as _requests
        logger.debug("[%s] Usando HTTP Basic Auth (usuario: %s)", nome, usuario)
        resp = _requests.get(
            rss_url, auth=(usuario, senha),
            timeout=30, headers={"User-Agent": "Mozilla/5.0"},
        )
        resp.raise_for_status()
        feed = feedparser.parse(resp.content)
    else:
        feed = feedparser.parse(rss_url)

    if feed.bozo:
        logger.warning("[%s] Aviso no parsing do feed: %s", nome, feed.bozo_exception)

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
            logger.warning("[%s] Entrada ignorada: %s", nome, e)

    return artigos


class RssGenericScraper(BaseScraper):
    """
    Scraper generico para qualquer fonte com tipo='rss'.

    Nao requer subclasse: basta que a fonte tenha url_rss
    preenchida na tabela mi.fontes. Usado automaticamente
    pela DAG mi_coleta para fontes RSS sem scraper customizado.
    Suporta HTTP Basic Auth via campos rss_usuario/rss_senha.
    """

    def __init__(self, slug):
        # type: (str) -> None
        super().__init__(slug=slug)

    def coletar(self):
        # type: () -> list
        return _parse_feed(
            self._slug, self.nome, self.fonte.url_rss,
            usuario=self.fonte.rss_usuario, senha=self.fonte.rss_senha,
        )


# ---------------------------------------------------------------------------
# Scrapers legados — mantidos por compatibilidade, todos delegam para
# _parse_feed(). Novas fontes RSS NAO precisam de classe propria.
# ---------------------------------------------------------------------------

class ReutersScraper(BaseScraper):
    def __init__(self):
        # type: () -> None
        super().__init__(slug="reuters-commodities")

    def coletar(self):
        # type: () -> list
        return _parse_feed(
            self._slug, self.nome,
            self.fonte.url_rss or "https://feeds.reuters.com/reuters/businessNews",
        )


class IcisScraper(BaseScraper):
    def __init__(self):
        # type: () -> None
        super().__init__(slug="icis")

    def coletar(self):
        # type: () -> list
        return _parse_feed(
            self._slug, self.nome,
            self.fonte.url_rss or "https://www.icis.com/explore/resources/news/feed",
        )


class PlasticsNewsScraper(BaseScraper):
    def __init__(self):
        # type: () -> None
        super().__init__(slug="plastics-news")

    def coletar(self):
        # type: () -> list
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)


class BloombergScraper(BaseScraper):
    def __init__(self):
        # type: () -> None
        super().__init__(slug="bloomberg")

    def coletar(self):
        # type: () -> list
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)


class FinancialTimesScraper(BaseScraper):
    def __init__(self):
        # type: () -> None
        super().__init__(slug="financial-times")

    def coletar(self):
        # type: () -> list
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)
