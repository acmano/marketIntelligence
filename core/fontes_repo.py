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
    rss_usuario: Optional[str] = None
    rss_senha: Optional[str] = None


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
                SELECT id, nome, slug, url_base, url_rss, tipo::text, categoria::text, ativa,
                       rss_usuario, rss_senha
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
        rss_usuario=row[8], rss_senha=row[9],
    )
    logger.debug(f"Fonte resolvida: slug='{slug}' → id={fonte.id}")
    return fonte


def listar_ativas():
    # type: () -> list
    """Retorna todas as fontes ativas cadastradas."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, slug, url_base, url_rss, tipo::text, categoria::text, ativa,
                       rss_usuario, rss_senha
                FROM mi.fontes
                WHERE ativa = TRUE
                ORDER BY slug
                """
            )
            rows = cur.fetchall()

    return [
        Fonte(id=r[0], nome=r[1], slug=r[2], url_base=r[3],
              url_rss=r[4], tipo=r[5], categoria=r[6], ativa=r[7],
              rss_usuario=r[8], rss_senha=r[9])
        for r in rows
    ]


def cadastrar_fonte(
    nome,            # type: str
    slug,            # type: str
    url_base,        # type: str
    tipo,            # type: str
    categoria,       # type: str
    url_rss=None,    # type: Optional[str]
    ativa=True,      # type: bool
    rss_usuario=None,  # type: Optional[str]
    rss_senha=None,    # type: Optional[str]
):
    # type: (...) -> Fonte
    """
    Insere uma nova fonte no banco e retorna o objeto Fonte.

    Parametros:
        nome:         Nome legivel (ex: 'Chemical Week')
        slug:         Identificador estavel kebab-case (ex: 'chemical-week')
        url_base:     URL principal do site
        tipo:         'rss', 'api' ou 'scraping'
        categoria:    Uma das categorias do enum mi.categoria_fonte
        url_rss:      URL do feed RSS (obrigatorio para tipo='rss')
        ativa:        Se a fonte inicia ativa (default True)
        rss_usuario:  Usuario para HTTP Basic Auth (opcional)
        rss_senha:    Senha para HTTP Basic Auth (opcional)

    Raises:
        ValueError: se tipo='rss' e url_rss nao for informada
        psycopg2.IntegrityError: se slug ou nome ja existir
    """
    if tipo == "rss" and not url_rss:
        raise ValueError(
            "Fontes do tipo 'rss' precisam de url_rss preenchida."
        )

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO mi.fontes
                    (nome, slug, url_base, url_rss, tipo, categoria, ativa, rss_usuario, rss_senha)
                VALUES (%s, %s, %s, %s, %s::mi.tipo_fonte, %s::mi.categoria_fonte, %s, %s, %s)
                RETURNING id
                """,
                (nome, slug, url_base, url_rss, tipo, categoria, ativa, rss_usuario, rss_senha),
            )
            fonte_id = cur.fetchone()[0]
        conn.commit()

    # Limpa cache do lru_cache para que a nova fonte seja visivel
    get_by_slug.cache_clear()

    logger.info("Fonte cadastrada: slug='%s', tipo='%s', categoria='%s'", slug, tipo, categoria)
    return get_by_slug(slug)


def listar_todas():
    # type: () -> list
    """Retorna todas as fontes cadastradas (ativas e inativas)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, nome, slug, url_base, url_rss, tipo::text, categoria::text, ativa,
                       rss_usuario, rss_senha
                FROM mi.fontes
                ORDER BY slug
                """
            )
            rows = cur.fetchall()

    return [
        Fonte(id=r[0], nome=r[1], slug=r[2], url_base=r[3],
              url_rss=r[4], tipo=r[5], categoria=r[6], ativa=r[7],
              rss_usuario=r[8], rss_senha=r[9])
        for r in rows
    ]


def alternar_ativa(slug, ativa):
    # type: (str, bool) -> None
    """Ativa ou desativa uma fonte pelo slug."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE mi.fontes SET ativa = %s WHERE slug = %s",
                (ativa, slug),
            )
        conn.commit()
    get_by_slug.cache_clear()
    logger.info("Fonte '%s' %s", slug, "ativada" if ativa else "desativada")


def obter_saude_fontes():
    # type: () -> list
    """Retorna dados de saude de coleta por fonte (view v_saude_coleta)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT slug, nome, ativa, artigos_total, artigos_24h,
                       ultima_coleta, ultimo_erro
                FROM mi.v_saude_coleta
                """
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def remover_fonte(slug):
    # type: (str,) -> None
    """Remove uma fonte pelo slug. Falha se houver artigos vinculados (FK RESTRICT)."""
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM mi.fontes WHERE slug = %s", (slug,))
        conn.commit()
    get_by_slug.cache_clear()
    logger.info("Fonte '%s' removida", slug)
