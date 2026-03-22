"""
Scrapers que requerem implementação específica (API ou scraping HTML).
Stubs prontos — implementar na MKI-3 (Fase 1).
"""

from loguru import logger
from .base_scraper import Artigo, BaseScraper


class WorldBankScraper(BaseScraper):
    """
    World Bank Open Data API
    Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392
    TODO (MKI-3): Implementar coleta de indicadores dos mercados-alvo de exportação.
    Indicadores relevantes: NY.GDP.PCAP.CD (PIB per capita), EG.ELC.ACCS.ZS (acesso energia)
    """
    def __init__(self):
        super().__init__(fonte_id=4, nome="World Bank Open Data")

    def coletar(self) -> list[Artigo]:
        logger.warning(f"[{self.nome}] TODO: implementar coleta via API World Bank (MKI-3)")
        return []


class TradeMapScraper(BaseScraper):
    """
    ITC Trade Map — dados de importação/exportação por país e produto NCM.
    TODO (MKI-3): Implementar coleta via API ou scraping autenticado.
    NCMs relevantes: 8516 (aquecedores), 8421 (filtros), 3926 (plásticos)
    """
    def __init__(self):
        super().__init__(fonte_id=5, nome="ITC Trade Map")

    def coletar(self) -> list[Artigo]:
        logger.warning(f"[{self.nome}] TODO: implementar coleta via TradeMap (MKI-3)")
        return []


class AbiplastScraper(BaseScraper):
    """
    ABIPLAST — Associação Brasileira da Indústria do Plástico
    TODO (MKI-8): Implementar scraping de notícias do site abiplast.org.br
    """
    def __init__(self):
        super().__init__(fonte_id=8, nome="ABIPLAST")

    def coletar(self) -> list[Artigo]:
        logger.warning(f"[{self.nome}] TODO: implementar scraping ABIPLAST (MKI-8)")
        return []


class AbiquimScraper(BaseScraper):
    """
    ABIQUIM — Associação Brasileira da Indústria Química
    TODO (MKI-8): Implementar scraping de notícias do site abiquim.org.br
    """
    def __init__(self):
        super().__init__(fonte_id=9, nome="ABIQUIM")

    def coletar(self) -> list[Artigo]:
        logger.warning(f"[{self.nome}] TODO: implementar scraping ABIQUIM (MKI-8)")
        return []
