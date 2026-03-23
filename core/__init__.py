"""Camada de acesso a dados — conexão, repositórios e tipos."""

from .db import get_conn, close_pool
from .fontes_repo import (
    Fonte, get_by_slug, listar_ativas, cadastrar_fonte,
    listar_todas, alternar_ativa, obter_saude_fontes, remover_fonte,
)
from .artigos_repo import ArtigoNovo, salvar_artigos, buscar_nao_processados, marcar_processado
from .processados_repo import salvar_processado, salvar_lote
from .processador_ia import processar_artigo, processar_lote
from .embeddings_repo import salvar_embedding, buscar_artigos_nao_vetorizados
from .pipeline_embeddings import gerar_embeddings_pendentes

__all__ = [
    "get_conn", "close_pool",
    "Fonte", "get_by_slug", "listar_ativas", "cadastrar_fonte",
    "listar_todas", "alternar_ativa", "obter_saude_fontes", "remover_fonte",
    "ArtigoNovo", "salvar_artigos", "buscar_nao_processados", "marcar_processado",
    "salvar_processado", "salvar_lote",
    "processar_artigo", "processar_lote",
    "salvar_embedding", "buscar_artigos_nao_vetorizados",
    "gerar_embeddings_pendentes",
]
