"""
Repositório de fontes.
Resolve UUID de fontes pelo slug em runtime — nenhum ID hardcoded na aplicação.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from typing import Optional
from uuid import UUID

from loguru import logger

from .db import get_conn


@dataclass(frozen=True)
class Fonte:
    id: UUID
    nome: str
    slug: str
    url_base: str
    url_rss: Optional[str]
    tipo: str
    categoria: str
    ativa: bool


@functools.lru_cache(maxsize=128)
def get_by_slug(slug: str) -> Fonte:
    """
    Retorna a fonte pelo slug. Resultado cacheado em memória — fontes raramente
    mudam e o processo Airflow é de curta duração.

    Lança ValueError se o slug não existir no banco.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, slug, url_base, url_rss, tipo::text, categoria::text, ativa
                FROM mi.fontes
                WHERE slug = %s
                """,
                (slug,),
            )
            row = cur.fetchone()

    if row is None:
        raise ValueError(
            f"Fonte com slug '{slug}' não encontrada no banco. "
            "Verifique se a migration 002_seed_fontes.sql foi executada."
        )

    fonte = Fonte(
        id=row[0], nome=row[1], slug=row[2], url_base=row[3],
        url_rss=row[4], tipo=row[5], categoria=row[6], ativa=row[7],
    )
    logger.debug(f"Fonte resolvida: slug='{slug}' → id={fonte.id}")
    return fonte


def listar_ativas() -> list[Fonte]:
    """Retorna todas as fontes ativas cadastradas."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, slug, url_base, url_rss, tipo::text, categoria::text, ativa
                FROM mi.fontes
                WHERE ativa = TRUE
                ORDER BY slug
                """
            )
            rows = cur.fetchall()

    return [
        Fonte(id=r[0], nome=r[1], slug=r[2], url_base=r[3],
              url_rss=r[4], tipo=r[5], categoria=r[6], ativa=r[7])
        for r in rows
    ]
