"""
Pipeline de processamento de artigos por IA.
Enriquece cada artigo com: categoria, score de relevância, tom,
entidades (países, commodities, empresas) e resumo em português.

Implementação da MKI-6.
Compatível com Python 3.8+
"""

import json
import os
from typing import Any, Dict, List, Optional

import anthropic
from dotenv import load_dotenv
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

load_dotenv()

_client: Optional[anthropic.Anthropic] = None


def _get_client() -> anthropic.Anthropic:
    global _client
    if _client is None:
        _client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


PROMPT_SISTEMA = """Você é um analista de inteligência de mercado especializado na indústria de manufatura, 
com foco em matérias-primas plásticas (polipropileno, nylon, ABS e derivados) e mercados globais de 
aquecimento de água e distribuição (chuveiros elétricos, aquecedores a gás, filtros de água).

Sua tarefa é analisar artigos de notícias e retornar um JSON estruturado com as seguintes informações.
Responda APENAS com o JSON, sem texto adicional, sem blocos de código markdown."""

PROMPT_ANALISE = """Analise o artigo abaixo e retorne um JSON com exatamente esta estrutura:

{{
  "categoria": "<uma de: materia-prima | mercado-exportacao | geopolitica | economia | regulatorio | outro>",
  "relevancia_score": <inteiro de 0 a 10, onde 10 = máxima relevância para Lorenzetti S.A.>,
  "tom": "<uma de: neutro | positivo | negativo | alerta>",
  "resumo_pt": "<resumo em português com no máximo 150 palavras, focado nos impactos para a Lorenzetti>",
  "entidades": {{
    "paises": ["<lista de países mencionados>"],
    "commodities": ["<lista de matérias-primas, resinas, produtos mencionados>"],
    "empresas": ["<lista de empresas mencionadas>"]
  }}
}}

Critérios de relevância (0-10):
- 8-10: Impacto direto em PP, nylon, ABS ou mercados de exportação da Lorenzetti
- 5-7: Impacto indireto (macroeconomia, geopolítica de países produtores/consumidores)
- 2-4: Relacionado ao setor mas sem impacto claro
- 0-1: Irrelevante

Artigo:
Título: {titulo}
Fonte: {fonte}
Data: {data}

{texto}"""


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=30))
def _chamar_claude(titulo: str, fonte: str, data: str, texto: str) -> Dict[str, Any]:
    """Chama a API Claude e retorna o JSON analisado."""
    modelo = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")

    prompt = PROMPT_ANALISE.format(
        titulo=titulo,
        fonte=fonte,
        data=data,
        texto=texto[:3000],  # limita para economizar tokens
    )

    msg = _get_client().messages.create(
        model=modelo,
        max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", 1024)),
        system=PROMPT_SISTEMA,
        messages=[{"role": "user", "content": prompt}],
    )

    conteudo = msg.content[0].text.strip()

    # Remove markdown code blocks se o modelo os incluir
    if conteudo.startswith("```"):
        conteudo = conteudo.split("```")[1]
        if conteudo.startswith("json"):
            conteudo = conteudo[4:]

    return json.loads(conteudo)


def processar_artigo(artigo: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Processa um único artigo e retorna o resultado enriquecido.
    Retorna None se o processamento falhar.
    """
    artigo_id = artigo["id"]
    titulo = artigo["titulo"]
    fonte_nome = artigo.get("fonte_nome", "Desconhecida")
    data = str(artigo.get("data_publicacao", ""))
    texto = artigo.get("texto_bruto") or titulo  # usa título se não houver texto

    try:
        resultado = _chamar_claude(titulo, fonte_nome, data, texto)

        # Valida campos obrigatórios
        campos = ["categoria", "relevancia_score", "tom", "resumo_pt", "entidades"]
        for campo in campos:
            if campo not in resultado:
                raise ValueError(f"Campo '{campo}' ausente na resposta da IA")

        resultado["artigo_id"] = artigo_id
        resultado["modelo_ia"] = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        return resultado

    except Exception as e:
        logger.error(f"Erro ao processar artigo {artigo_id} '{titulo[:50]}': {e}")
        return None


def processar_lote(artigos: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Processa uma lista de artigos e retorna os resultados com sucesso.
    """
    resultados = []
    total = len(artigos)

    for i, artigo in enumerate(artigos, 1):
        logger.info(f"Processando {i}/{total}: {artigo['titulo'][:60]}...")
        resultado = processar_artigo(artigo)
        if resultado:
            resultados.append(resultado)

    logger.info(f"Lote concluído: {len(resultados)}/{total} processados com sucesso.")
    return resultados
