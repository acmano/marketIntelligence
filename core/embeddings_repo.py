"""
Repositório de embeddings.
Persiste e consulta vetores em mi.embeddings via pgvector.
Compatível com Python 3.8+
"""

from typing import Any, Dict, List, Optional
from uuid import UUID

from loguru import logger

from .db import get_conn


def salvar_embedding(artigo_id: str, embedding: List[float], modelo: str) -> bool:
    """
    Persiste o embedding de um artigo em mi.embeddings.
    Atualiza se já existir (ON CONFLICT).
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mi.embeddings (artigo_id, embedding, modelo)
                    VALUES (%s, %s::vector, %s)
                    ON CONFLICT (artigo_id) DO UPDATE SET
                        embedding = EXCLUDED.embedding,
                        modelo    = EXCLUDED.modelo,
                        gerado_em = NOW()
                    """,
                    (str(artigo_id), str(embedding), modelo),
                )
            conn.commit()
        return True
    except Exception as e:
        logger.error(f"Erro ao salvar embedding para artigo {artigo_id}: {e}")
        return False


def buscar_artigos_nao_vetorizados(score_min: int = 4, limite: int = 200) -> List[Dict[str, Any]]:
    """
    Retorna artigos processados com score >= score_min que ainda não têm embedding.
    """
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT a.id, a.titulo, p.resumo_pt, p.relevancia_score
                FROM mi.artigos_processados p
                JOIN mi.artigos a ON a.id = p.artigo_id
                LEFT JOIN mi.embeddings e ON e.artigo_id = a.id
                WHERE p.relevancia_score >= %s
                  AND e.id IS NULL
                ORDER BY p.relevancia_score DESC
                LIMIT %s
                """,
                (score_min, limite),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
