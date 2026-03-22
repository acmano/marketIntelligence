"""Camada de acesso a dados — conexão, repositórios e tipos."""

from .db import get_conn, close_pool
from .fontes_repo import Fonte, get_by_slug, listar_ativas
from .artigos_repo import ArtigoNovo, salvar_artigos, buscar_nao_processados, marcar_processado

__all__ = [
    "get_conn", "close_pool",
    "Fonte", "get_by_slug", "listar_ativas",
    "ArtigoNovo", "salvar_artigos", "buscar_nao_processados", "marcar_processado",
]
