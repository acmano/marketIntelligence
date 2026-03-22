"""
Pipeline de geração de embeddings em lote.
Processa artigos com score >= MI_SCORE_MIN_EMBEDDING e gera vetores via OpenAI.
Compatível com Python 3.8+
"""

import os
from typing import List

from dotenv import load_dotenv
from loguru import logger

load_dotenv()


def gerar_embeddings_pendentes(score_min: int = None, limite: int = 200) -> int:
    """
    Gera embeddings para todos os artigos processados que ainda não têm vetor.
    Retorna quantidade de embeddings gerados com sucesso.
    """
    from embeddings.generator import gerar_embedding_artigo
    from core.embeddings_repo import buscar_artigos_nao_vetorizados, salvar_embedding

    score_min = score_min or int(os.getenv("MI_SCORE_MIN_EMBEDDING", 4))
    modelo = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

    artigos = buscar_artigos_nao_vetorizados(score_min=score_min, limite=limite)
    total = len(artigos)

    if total == 0:
        logger.info("Nenhum artigo pendente de embedding.")
        return 0

    logger.info(f"Gerando embeddings para {total} artigos (score >= {score_min})...")
    gerados = 0

    for i, artigo in enumerate(artigos, 1):
        artigo_id = str(artigo["id"])
        titulo = artigo["titulo"]
        resumo = artigo.get("resumo_pt") or titulo

        try:
            vetor = gerar_embedding_artigo(titulo, resumo)
            if salvar_embedding(artigo_id, vetor, modelo):
                gerados += 1
                if i % 20 == 0:
                    logger.info(f"  {i}/{total} embeddings gerados...")
        except Exception as e:
            logger.error(f"Erro no artigo {artigo_id}: {e}")

    logger.info(f"Concluído: {gerados}/{total} embeddings gerados.")
    return gerados
