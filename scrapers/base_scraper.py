"""
Classe base para todos os scrapers do Market Intelligence.

Design principles:
- Scrapers não conhecem IDs, SQL ou detalhes de banco
- Toda persistência é delegada ao repositório (core.artigos_repo)
- A fonte é resolvida pelo slug estável em runtime
- Retry automático com backoff exponencial via tenacity
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from loguru import logger
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    before_sleep_log,
    RetryError,
)
import logging

from core.fontes_repo import Fonte, get_by_slug
from core.artigos_repo import ArtigoNovo, salvar_artigos


@dataclass
class ArtigoColetado:
    """
    DTO de saída dos scrapers.
    Contém apenas dados de domínio — sem IDs de banco.
    O repositório resolve o fonte_id a partir do slug da Fonte.
    """
    titulo: str
    url: str
    texto_bruto: Optional[str] = None
    data_publicacao: Optional[datetime] = None


class BaseScraper(ABC):
    """
    Interface base para todos os coletores de fontes.

    Subclasses devem:
      1. Chamar super().__init__(slug='meu-slug')
      2. Implementar coletar() retornando list[ArtigoColetado]

    O slug deve corresponder exatamente ao campo slug cadastrado em mi.fontes.
    Nunca hardcode o UUID da fonte — ele é resolvido automaticamente.
    """

    def __init__(self, slug: str) -> None:
        self._slug = slug
        self._fonte: Optional[Fonte] = None   # resolvido lazy no primeiro uso

    @property
    def fonte(self) -> Fonte:
        """Resolve a Fonte pelo slug na primeira chamada (lazy + cached)."""
        if self._fonte is None:
            self._fonte = get_by_slug(self._slug)
        return self._fonte

    @property
    def nome(self) -> str:
        return self.fonte.nome

    @abstractmethod
    def coletar(self) -> list[ArtigoColetado]:
        """
        Coleta artigos da fonte externa.
        Deve retornar apenas ArtigoColetado — sem lógica de banco.
        """
        raise NotImplementedError

    def _persistir(self, artigos: list[ArtigoColetado]) -> int:
        """Converte ArtigoColetado → ArtigoNovo e delega ao repositório."""
        if not artigos:
            logger.info(f"[{self.nome}] Nenhum artigo para persistir.")
            return 0

        dtos = [
            ArtigoNovo(
                fonte_id=self.fonte.id,
                titulo=a.titulo,
                url=a.url,
                texto_bruto=a.texto_bruto,
                data_publicacao=a.data_publicacao,
            )
            for a in artigos
        ]

        novos = salvar_artigos(dtos)
        logger.info(f"[{self.nome}] {novos} novos de {len(artigos)} coletados.")
        return novos

    @retry(
        retry=retry_if_exception_type(Exception),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        before_sleep=before_sleep_log(logger, logging.WARNING),
        reraise=True,
    )
    def executar(self) -> int:
        """
        Ponto de entrada principal.
        Executa coleta + persistência com retry automático.
        Retorna número de artigos novos inseridos.
        """
        logger.info(f"[{self.nome}] Iniciando coleta (slug={self._slug})...")
        artigos = self.coletar()
        novos = self._persistir(artigos)
        logger.info(f"[{self.nome}] Concluído. {novos} artigos novos.")
        return novos
