"""
Market Intelligence - Agente Conversacional MVP
Lorenzetti S.A. | Assessoria a Alta Direcao

RAG: Retrieval-Augmented Generation sobre base de artigos indexados.
Compativel com Python 3.8+

Executar:
    cd /home/mano/projetos/datasul/marketIntelligence
    streamlit run agente.py --server.port 8501 --server.address 0.0.0.0
"""

import os
import sys
from typing import List, Dict, Any, Optional

import streamlit as st
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

import anthropic
from embeddings.generator import gerar_embedding
from core.db import get_conn

st.set_page_config(
    page_title="Market Intelligence - Lorenzetti",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown("""
<style>
    .titulo-principal { color: #1B3A6B !important; font-size: 1.8rem; font-weight: 700; }
    .fonte-tag {
        display: inline-block !important;
        background: #E8F0FE !important;
        color: #1B3A6B !important;
        border-radius: 4px !important;
        padding: 2px 8px !important;
        font-size: 0.75rem !important;
        margin: 2px !important;
    }
    .score-badge {
        display: inline-block !important;
        background: #1B3A6B !important;
        color: #ffffff !important;
        border-radius: 10px !important;
        padding: 1px 8px !important;
        font-size: 0.75rem !important;
    }
    .artigo-card {
        background: #ffffff !important;
        color: #222222 !important;
        border-left: 3px solid #1B3A6B !important;
        padding: 8px 12px !important;
        margin: 4px 0 !important;
        border-radius: 0 4px 4px 0 !important;
    }
    .artigo-card a { color: #1B3A6B !important; }
    .artigo-card small { color: #666666 !important; }
</style>
""", unsafe_allow_html=True)

CATEGORIAS = {
    "Todas": None,
    "Materia-Prima": "materia-prima",
    "Mercado de Exportacao": "mercado-exportacao",
    "Geopolitica": "geopolitica",
    "Economia": "economia",
    "Regulatorio": "regulatorio",
}

PROMPT_SISTEMA = """Voce e um analista de inteligencia de mercado da Lorenzetti S.A.,
fabricante brasileira de aquecedores de agua, chuveiros eletricos, torneiras e filtros.
Responda em portugues brasileiro, de forma clara e objetiva.
Baseie suas respostas nos artigos fornecidos como contexto.
Cite as fontes usando [Fonte: nome] ao final de cada afirmacao importante.
Ao final da resposta, inclua uma secao "Implicacoes para a Lorenzetti" com 2-3 insights praticos."""

PROMPT_PREDITIVO = """Voce e um analista de inteligencia de mercado da Lorenzetti S.A.
Com base nos artigos fornecidos, faca uma analise preditiva.
Identifique tendencias, riscos e oportunidades para os proximos 3-6 meses.
Responda em portugues brasileiro com secoes: Tendencias, Riscos, Oportunidades e Recomendacoes."""


@st.cache_resource
def get_anthropic_client():
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _safe(texto):
    if texto is None:
        return None
    if isinstance(texto, bytes):
        return texto.decode("utf-8", errors="replace")
    return texto.encode("utf-8", errors="replace").decode("utf-8", errors="replace")


def buscar_artigos_relevantes(pergunta, top_k=8, categoria=None, dias=90):
    vetor = gerar_embedding(pergunta)
    with get_conn() as conn:
        with conn.cursor() as cur:
            if categoria:
                cur.execute(
                    """
                    SELECT artigo_id, titulo, url, resumo_pt, categoria,
                           relevancia, tom, fonte_nome, data_publicacao, similaridade
                    FROM mi.buscar_similares(%s::vector, %s::integer, %s::mi.categoria_artigo, 4::smallint, %s::integer)
                    """,
                    (str(vetor), top_k, categoria, dias),
                )
            else:
                cur.execute(
                    """
                    SELECT artigo_id, titulo, url, resumo_pt, categoria,
                           relevancia, tom, fonte_nome, data_publicacao, similaridade
                    FROM mi.buscar_similares(%s::vector, %s::integer, NULL, 4::smallint, %s::integer)
                    """,
                    (str(vetor), top_k, dias),
                )
            cols = [d[0] for d in cur.description]
            result = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                d["titulo"]     = _safe(d.get("titulo"))
                d["resumo_pt"]  = _safe(d.get("resumo_pt"))
                d["url"]        = _safe(d.get("url"))
                d["fonte_nome"] = _safe(d.get("fonte_nome"))
                result.append(d)
            return result


def montar_contexto(artigos):
    partes = []
    for i, a in enumerate(artigos, 1):
        data = a["data_publicacao"].strftime("%d/%m/%Y") if a["data_publicacao"] else "s/d"
        partes.append(
            f"[Artigo {i}]\n"
            f"Fonte: {a['fonte_nome']} | Data: {data} | Categoria: {a['categoria']}\n"
            f"Titulo: {a['titulo']}\n"
            f"Resumo: {a['resumo_pt'] or 'Sem resumo disponivel'}\n"
        )
    return "\n---\n".join(partes)


def gerar_resposta(pergunta, artigos, historico, modo_preditivo=False):
    cliente = get_anthropic_client()
    sistema = PROMPT_PREDITIVO if modo_preditivo else PROMPT_SISTEMA
    mensagens = []
    for msg in historico[-6:]:
        mensagens.append({"role": msg["role"], "content": msg["content"]})
    mensagens.append({
        "role": "user",
        "content": f"Contexto:\n{montar_contexto(artigos)}\n\n---\nPergunta: {pergunta}"
    })
    resp = cliente.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        max_tokens=int(os.getenv("ANTHROPIC_MAX_TOKENS", 2048)),
        system=sistema,
        messages=mensagens,
    )
    return resp.content[0].text


def obter_estatisticas():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM mi.artigos")
            total_artigos = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM mi.embeddings")
            total_embeddings = cur.fetchone()[0]
            cur.execute("SELECT MAX(coletado_em) FROM mi.artigos")
            ultima_coleta = cur.fetchone()[0]
    return {"total_artigos": total_artigos, "total_embeddings": total_embeddings, "ultima_coleta": ultima_coleta}


def main():
    if "historico" not in st.session_state:
        st.session_state.historico = []

    with st.sidebar:
        st.markdown("### Market Intelligence")
        st.markdown("**Lorenzetti S.A.** | Assessoria a Alta Direcao")
        st.divider()
        st.markdown("#### Filtros")
        categoria_label = st.selectbox("Categoria", list(CATEGORIAS.keys()))
        categoria = CATEGORIAS[categoria_label]
        dias = st.slider("Periodo (dias)", 7, 365, 90)
        top_k = st.slider("Artigos por consulta", 3, 15, 8)
        modo_preditivo = st.toggle("Modo Analise Preditiva", value=False)
        st.divider()
        st.markdown("#### Base de Dados")
        try:
            stats = obter_estatisticas()
            st.metric("Artigos coletados", stats["total_artigos"])
            st.metric("Artigos vetorizados", stats["total_embeddings"])
            if stats["ultima_coleta"]:
                st.caption(f"Ultima coleta: {stats['ultima_coleta'].strftime('%d/%m %H:%M')}")
        except Exception:
            st.caption("Estatisticas indisponiveis")
        st.divider()
        if st.button("Limpar conversa"):
            st.session_state.historico = []
            st.rerun()

    st.markdown('<p class="titulo-principal">Market Intelligence - Agente Conversacional</p>', unsafe_allow_html=True)
    if modo_preditivo:
        st.info("**Modo Analise Preditiva** ativo - respostas focadas em tendencias e projecoes futuras.")

    for msg in st.session_state.historico:
        with st.chat_message(msg["role"]):
            st.markdown(msg["content"])

    placeholder = (
        "Ex: Qual a tendencia de precos do polipropileno nos proximos meses?"
        if modo_preditivo
        else "Ex: Quais os principais riscos de desabastecimento de PP atualmente?"
    )

    if pergunta := st.chat_input(placeholder):
        with st.chat_message("user"):
            st.markdown(pergunta)
        st.session_state.historico.append({"role": "user", "content": pergunta})

        with st.chat_message("assistant"):
            with st.spinner("Buscando artigos relevantes e analisando..."):
                try:
                    artigos = buscar_artigos_relevantes(pergunta, top_k, categoria, dias)
                    if not artigos:
                        resposta = "Nao encontrei artigos relevantes para esta consulta. Tente ampliar o periodo ou reformular a pergunta."
                    else:
                        resposta = gerar_resposta(pergunta, artigos, st.session_state.historico[:-1], modo_preditivo)

                    st.markdown(resposta)

                    if artigos:
                        st.markdown("---")
                        st.markdown(f"**Fontes consultadas ({len(artigos)} artigos):**")
                        for a in artigos:
                            data = a["data_publicacao"].strftime("%d/%m/%Y") if a["data_publicacao"] else "s/d"
                            st.markdown(
                                f'<div class="artigo-card">'
                                f'<span class="fonte-tag">{a["fonte_nome"]}</span> '
                                f'<span class="fonte-tag">{a["categoria"]}</span> '
                                f'<span class="score-badge">score {a["relevancia"]}</span> '
                                f'<span class="score-badge">sim {a["similaridade"]:.2f}</span><br>'
                                f'<a href="{a["url"]}" target="_blank">{a["titulo"]}</a> '
                                f'<small style="color:#666666;">({data})</small>'
                                f'</div>',
                                unsafe_allow_html=True,
                            )

                    st.session_state.historico.append({"role": "assistant", "content": resposta})

                except Exception as e:
                    st.error(f"Erro: {e}")


if __name__ == "__main__":
    main()

