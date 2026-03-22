"""
Gerador de embeddings vetoriais via OpenAI text-embedding-3-small.
Implementação completa: MKI-7
"""

import os
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def gerar_embedding(texto: str) -> list[float]:
    """
    Gera embedding vetorial (1536 dimensões) para um texto.
    Usa retry automático com backoff exponencial em caso de erro de rate limit.
    """
    response = client.embeddings.create(
        model=MODEL,
        input=texto,
    )
    return response.data[0].embedding


def gerar_embedding_artigo(titulo: str, resumo_pt: str) -> list[float]:
    """Gera embedding combinando título + resumo para melhor semântica."""
    texto = f"{titulo}\n\n{resumo_pt}"
    return gerar_embedding(texto)
