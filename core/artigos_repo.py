"""
Repositório de artigos.
Toda persistência passa por aqui — os scrapers não conhecem SQL.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from uuid import UUID

from loguru import logger

from .db import get_conn


@dataclass
class ArtigoNovo:
    """DTO de entrada: dados brutos coletados pelo scraper."""
    fonte_id: UUID
    titulo: str
    url: str
    texto_bruto: Optional[str] = None
    data_publicacao: Optional[datetime] = None


def salvar_artigos(artigos: list[ArtigoNovo]) -> int:
    """
    Persiste lista de artigos ignorando duplicatas (conflito em url).
    Retorna quantidade de artigos efetivamente inseridos.
    """
    if not artigos:
        return 0

    novos = 0
    with get_conn() as conn:
        with conn.cursor() as cur:
            for a in artigos:
                cur.execute(
                    """
                    INSERT INTO mi.artigos (fonte_id, titulo, url, texto_bruto, data_publicacao)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (url) DO NOTHING
                    """,
                    (str(a.fonte_id), a.titulo, a.url, a.texto_bruto, a.data_publicacao),
                )
                if cur.rowcount > 0:
                    novos += 1
        conn.commit()

    return novos


def buscar_nao_processados(limite: int = 100) -> list[dict]:
    """Retorna artigos ainda não processados pela IA, ordenados por data de coleta."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.titulo, a.url, a.texto_bruto, a.data_publicacao,
                       f.nome AS fonte_nome, f.slug AS fonte_slug
                FROM mi.artigos a
                JOIN mi.fontes f ON f.id = a.fonte_id
                WHERE a.processado = FALSE
                ORDER BY a.coletado_em
                LIMIT %s
                """,
                (limite,),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def marcar_processado(artigo_id: UUID) -> None:
    """Marca um artigo como processado após enriquecimento pela IA."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE mi.artigos SET processado = TRUE WHERE id = %s",
                (str(artigo_id),),
            )
        conn.commit()
