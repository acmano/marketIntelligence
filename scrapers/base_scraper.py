"""
Base scraper — interface comum para todos os coletores de fontes.
Todos os scrapers devem herdar desta classe e implementar o método `coletar()`.
"""

import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

import psycopg2
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()


@dataclass
class Artigo:
    """Representa um artigo coletado de uma fonte."""
    titulo: str
    url: str
    fonte_id: int
    texto_bruto: Optional[str] = None
    data_publicacao: Optional[datetime] = None


class BaseScraper(ABC):
    """
    Interface base para todos os scrapers do Market Intelligence.

    Cada scraper de fonte deve:
    1. Herdar desta classe
    2. Implementar o método `coletar()` retornando lista de Artigo
    3. Chamar `self.salvar(artigos)` ao final
    """

    def __init__(self, fonte_id: int, nome: str):
        self.fonte_id = fonte_id
        self.nome = nome
        self.conn = None

    def _get_conn(self):
        if self.conn is None or self.conn.closed:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "localhost"),
                port=int(os.getenv("DB_PORT", 5432)),
                dbname=os.getenv("DB_NAME"),
                user=os.getenv("DB_USER"),
                password=os.getenv("DB_PASSWORD"),
            )
        return self.conn

    @abstractmethod
    def coletar(self) -> list[Artigo]:
        """Coleta artigos da fonte. Deve ser implementado por cada subclasse."""
        raise NotImplementedError

    def salvar(self, artigos: list[Artigo]) -> int:
        """
        Persiste os artigos no banco, ignorando duplicatas (por URL).
        Retorna o número de artigos novos inseridos.
        """
        if not artigos:
            logger.info(f"[{self.nome}] Nenhum artigo para salvar.")
            return 0

        conn = self._get_conn()
        novos = 0
        with conn.cursor() as cur:
            for a in artigos:
                try:
                    cur.execute(
                        """
                        INSERT INTO mi_artigos (fonte_id, titulo, url, texto_bruto, data_publicacao)
                        VALUES (%s, %s, %s, %s, %s)
                        ON CONFLICT (url) DO NOTHING
                        """,
                        (a.fonte_id, a.titulo, a.url, a.texto_bruto, a.data_publicacao),
                    )
                    if cur.rowcount > 0:
                        novos += 1
                except Exception as e:
                    logger.warning(f"[{self.nome}] Erro ao salvar artigo '{a.url}': {e}")
            conn.commit()

        logger.info(f"[{self.nome}] {novos} novos artigos de {len(artigos)} coletados.")
        return novos

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=30))
    def executar(self) -> int:
        """Executa coleta completa com retry automático. Retorna qtd de novos artigos."""
        logger.info(f"[{self.nome}] Iniciando coleta...")
        artigos = self.coletar()
        novos = self.salvar(artigos)
        logger.info(f"[{self.nome}] Coleta concluída. {novos} novos artigos.")
        return novos

    def __del__(self):
        if self.conn and not self.conn.closed:
            self.conn.close()
