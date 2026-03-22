"""
Scrapers que usam Google News RSS filtrado por domínio.
World Bank e TradeMap permanecem como stubs (implementar futuramente).
Compatível com Python 3.8+
"""

from loguru import logger
from .base_scraper import ArtigoColetado, BaseScraper
from .rss_scrapers import _parse_feed


class WorldBankScraper(BaseScraper):
    def __init__(self):
        super().__init__(slug="world-bank")

    def coletar(self):
        logger.warning(f"[{self.nome}] Não implementado ainda.")
        return []


class TradeMapScraper(BaseScraper):
    def __init__(self):
        super().__init__(slug="trademap")

    def coletar(self):
        logger.warning(f"[{self.nome}] Não implementado ainda.")
        return []


class AbiplastScraper(BaseScraper):
    def __init__(self):
        super().__init__(slug="abiplast")

    def coletar(self):
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)


class AbiquimScraper(BaseScraper):
    def __init__(self):
        super().__init__(slug="abiquim")

    def coletar(self):
        return _parse_feed(self._slug, self.nome, self.fonte.url_rss)
