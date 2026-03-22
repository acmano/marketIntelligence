"""
Gerador de embeddings vetoriais.
Usa OpenAI text-embedding-3-small — modelo leve, barato e de alta qualidade.
"""

import os

from typing import Optional
from loguru import logger
from openai import OpenAI
from tenacity import retry, stop_after_attempt, wait_exponential

_client: Optional[OpenAI] = None


def _get_client() -> OpenAI:
    global _client
    if _client is None:
        _client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    return _client


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def gerar_embedding(texto: str):
    """Gera vetor de 1536 dimensões para o texto informado."""
    model = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")
    response = _get_client().embeddings.create(model=model, input=texto)
    return response.data[0].embedding


def gerar_embedding_artigo(titulo: str, resumo_pt: str):
    """
    Gera embedding combinando título + resumo para melhor representação semântica.
    O separador de parágrafo melhora a distinção entre título e corpo.
    """
    if not titulo and not resumo_pt:
        raise ValueError("Título e resumo não podem ser ambos vazios.")
    texto = f"{titulo}\n\n{resumo_pt}".strip()
    return gerar_embedding(texto)
