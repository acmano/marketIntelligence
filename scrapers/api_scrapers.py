"""
Scrapers que requerem implementação específica (API REST ou scraping HTML).
Stubs documentados — implementar nas issues MKI-3 (World Bank, TradeMap)
e MKI-8 (ABIPLAST, ABIQUIM).

Padrão: o slug passado ao super().__init__() é a única referência à fonte —
nenhum ID, nenhuma URL hardcoded. Tudo é resolvido via self.fonte em runtime.
"""

from __future__ import annotations

from loguru import logger
from .base_scraper import ArtigoColetado, BaseScraper


class WorldBankScraper(BaseScraper):
    """
    World Bank Open Data API
    Docs: https://datahelpdesk.worldbank.org/knowledgebase/articles/889392-about-the-indicators-api-documentation

    TODO (MKI-3): Coletar indicadores dos mercados-alvo de exportação.
    Indicadores sugeridos:
      - NY.GDP.PCAP.CD  — PIB per capita (USD)
      - EG.ELC.ACCS.ZS  — Acesso à eletricidade (% população)
      - SP.POP.TOTL     — População total
    Países relevantes: AR, MX, CO, CL, PE, NG, AO, EG, IN, PH
    """

    def __init__(self) -> None:
        super().__init__(slug="world-bank")

    def coletar(self) -> list[ArtigoColetado]:
        logger.warning(f"[{self.nome}] Não implementado — pendente MKI-3")
        return []


class TradeMapScraper(BaseScraper):
    """
    ITC Trade Map — dados de importação/exportação por país e código NCM.
    URL: https://www.trademap.org

    TODO (MKI-3): Implementar coleta de dados de comércio exterior.
    NCMs relevantes para Lorenzetti:
      - 8516.40   — Ferros elétricos
      - 8516.50   — Fornos micro-ondas
      - 8421.21   — Aparelhos para filtrar/depurar água
      - 8516.10   — Aquecedores elétricos de água
      - 3926.90   — Outras obras de plástico
    """

    def __init__(self) -> None:
        super().__init__(slug="trademap")

    def coletar(self) -> list[ArtigoColetado]:
        logger.warning(f"[{self.nome}] Não implementado — pendente MKI-3")
        return []


class AbiplastScraper(BaseScraper):
    """
    ABIPLAST — Associação Brasileira da Indústria do Plástico
    URL: https://abiplast.org.br/noticias

    TODO (MKI-8): Implementar scraping de notícias.
    Seções de interesse: Notícias, Publicações, Indicadores do Setor
    """

    def __init__(self) -> None:
        super().__init__(slug="abiplast")

    def coletar(self) -> list[ArtigoColetado]:
        logger.warning(f"[{self.nome}] Não implementado — pendente MKI-8")
        return []


class AbiquimScraper(BaseScraper):
    """
    ABIQUIM — Associação Brasileira da Indústria Química
    URL: https://www.abiquim.org.br/noticias

    TODO (MKI-8): Implementar scraping de notícias.
    Seções de interesse: Notícias, Relatórios, Conjuntura Química
    """

    def __init__(self) -> None:
        super().__init__(slug="abiquim")

    def coletar(self) -> list[ArtigoColetado]:
        logger.warning(f"[{self.nome}] Não implementado — pendente MKI-8")
        return []
