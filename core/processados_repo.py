"""
Repositório de artigos processados.
Persiste os resultados do pipeline de IA em mi.artigos_processados.
Compatível com Python 3.8+
"""

import json
from typing import Any, Dict, List
from uuid import UUID

from loguru import logger

from .db import get_conn


def salvar_processado(resultado: Dict[str, Any]) -> bool:
    """
    Persiste o resultado do processamento IA para um artigo.
    Atualiza mi.artigos.processado = TRUE atomicamente.
    Retorna True se inserido com sucesso.
    """
    artigo_id = str(resultado["artigo_id"])

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Insere o resultado processado
                cur.execute(
                    """
                    INSERT INTO mi.artigos_processados
                        (artigo_id, resumo_pt, categoria, relevancia_score,
                         tom, entidades, modelo_ia)
                    VALUES (%s, %s, %s::mi.categoria_artigo, %s,
                            %s::mi.tom_artigo, %s::jsonb, %s)
                    ON CONFLICT (artigo_id) DO UPDATE SET
                        resumo_pt        = EXCLUDED.resumo_pt,
                        categoria        = EXCLUDED.categoria,
                        relevancia_score = EXCLUDED.relevancia_score,
                        tom              = EXCLUDED.tom,
                        entidades        = EXCLUDED.entidades,
                        modelo_ia        = EXCLUDED.modelo_ia,
                        updated_at       = NOW()
                    """,
                    (
                        artigo_id,
                        resultado["resumo_pt"],
                        resultado["categoria"],
                        resultado["relevancia_score"],
                        resultado["tom"],
                        json.dumps(resultado["entidades"], ensure_ascii=False),
                        resultado["modelo_ia"],
                    ),
                )
                # Marca artigo como processado
                cur.execute(
                    "UPDATE mi.artigos SET processado = TRUE WHERE id = %s",
                    (artigo_id,),
                )
            conn.commit()
        return True

    except Exception as e:
        logger.error(f"Erro ao salvar processado para artigo {artigo_id}: {e}")
        return False


def salvar_lote(resultados: List[Dict[str, Any]]) -> int:
    """Salva lista de resultados. Retorna quantidade salva com sucesso."""
    salvos = sum(1 for r in resultados if salvar_processado(r))
    logger.info(f"Salvos {salvos}/{len(resultados)} artigos processados.")
    return salvos
