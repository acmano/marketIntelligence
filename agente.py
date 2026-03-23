"""
Market Intelligence - Agente Conversacional MVP
Lorenzetti S.A. | Assessoria a Alta Direcao

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
from core.fontes_repo import (
    listar_todas, cadastrar_fonte, alternar_ativa,
    obter_saude_fontes, remover_fonte,
)

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

    /* Ticker */
    .ticker-wrapper {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        width: 100% !important;
        background: #1B3A6B !important;
        color: #ffffff !important;
        padding: 6px 0 !important;
        z-index: 9999 !important;
        overflow: hidden !important;
        white-space: nowrap !important;
        font-size: 0.82rem !important;
        font-family: monospace !important;
    }
    .ticker-content {
        display: inline-block !important;
        animation: ticker-scroll 60s linear infinite !important;
        padding-left: 100% !important;
    }
    .ticker-content:hover { animation-play-state: paused !important; }
    @keyframes ticker-scroll {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-100%); }
    }
    .ticker-up   { color: #00ff88 !important; font-weight: bold !important; }
    .ticker-down { color: #ff4444 !important; font-weight: bold !important; }
    .ticker-neu  { color: #cccccc !important; }
    .ticker-sep  { color: #4488bb !important; margin: 0 16px !important; }

    /* Espaco no rodape para nao cobrir conteudo */
    .main .block-container { padding-bottom: 50px !important; }
</style>
""", unsafe_allow_html=True)

# ── Constantes ────────────────────────────────────────────────────────────────
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

# Ativos para o ticker
TICKER_ATIVOS = {
    "USD/BRL":       "BRL=X",
    "EUR/BRL":       "EURBRL=X",
    "Ouro":          "GC=F",
    "Prata":         "SI=F",
    "Brent":         "BZ=F",
    "LME Cobre":     "HG=F",
    "LME Aluminio":  "ALI=F",
    "LME Zinco":     "ZNC=F",
    "IBOV":          "^BVSP",
    "S&P 500":       "^GSPC",
    "Nasdaq":        "^IXIC",
}


# ── Ticker ────────────────────────────────────────────────────────────────────

def _fmt_brl(valor):
    # type: (float) -> str
    """Formata numero no padrao brasileiro: ponto milhar, virgula decimal."""
    # Formata com 2 casas decimais
    s = "{:,.2f}".format(valor)
    # Troca: virgula->@, ponto->ponto_milhar, @->virgula_decimal
    s = s.replace(",", "@").replace(".", ",").replace("@", ".")
    return s


def _fmt_brl_int(valor):
    # type: (float) -> str
    """Formata numero inteiro no padrao brasileiro (sem decimais)."""
    s = "{:,.0f}".format(valor)
    s = s.replace(",", ".")
    return s


# Ativos que ja sao cotados em BRL (nao converter)
_ATIVOS_BRL = {"BRL=X", "EURBRL=X", "^BVSP"}


@st.cache_data(ttl=120)  # cache de 2 minutos
def obter_cotacoes():
    # type: () -> List[Dict[str, Any]]
    """Busca cotacoes via Yahoo Finance API com conversao para BRL."""
    import requests as _requests

    headers = {"User-Agent": "Mozilla/5.0"}

    # Primeiro busca USD/BRL para converter os demais
    usd_brl = None
    try:
        url = "https://query1.finance.yahoo.com/v8/finance/chart/BRL=X?interval=1d&range=2d"
        r = _requests.get(url, headers=headers, timeout=8)
        meta = r.json()["chart"]["result"][0]["meta"]
        usd_brl = float(meta["regularMarketPrice"])
    except Exception:
        pass

    resultado = []
    for nome, simbolo in TICKER_ATIVOS.items():
        try:
            url = "https://query1.finance.yahoo.com/v8/finance/chart/%s?interval=1d&range=2d" % simbolo
            r = _requests.get(url, headers=headers, timeout=8)
            meta = r.json()["chart"]["result"][0]["meta"]
            preco_hoje = float(meta["regularMarketPrice"])
            preco_ant = float(meta["chartPreviousClose"])
            variacao = ((preco_hoje - preco_ant) / preco_ant) * 100

            # Converte para BRL se nao e ativo ja em BRL
            preco_brl = preco_hoje
            if simbolo not in _ATIVOS_BRL and usd_brl is not None:
                preco_brl = preco_hoje * usd_brl

            # Formatacao brasileira
            if simbolo in ("^BVSP", "^GSPC", "^IXIC"):
                valor_str = _fmt_brl_int(preco_brl)
            else:
                valor_str = _fmt_brl(preco_brl)

            # Mostra "R$" para valores convertidos, nao para pares cambiais
            if simbolo in ("BRL=X", "EURBRL=X"):
                valor_str = "R$ " + valor_str
            elif simbolo in ("^BVSP", "^GSPC", "^IXIC"):
                valor_str = valor_str + " pts"
            elif simbolo not in _ATIVOS_BRL:
                valor_str = "R$ " + valor_str

            resultado.append({
                "nome": nome,
                "valor": valor_str,
                "variacao": variacao,
            })
        except Exception:
            pass

    return resultado


def renderizar_ticker():
    """Renderiza a barra de ticker no rodape com auto-refresh a cada 2 minutos."""
    cotacoes = obter_cotacoes()

    if not cotacoes:
        st.markdown(
            '<div class="ticker-wrapper"><div class="ticker-content">'
            '<span class="ticker-neu">Cotacoes indisponiveis no momento</span>'
            '</div></div>',
            unsafe_allow_html=True,
        )
        return

    itens = []
    for c in cotacoes:
        var = c["variacao"]
        sinal = "+" if var >= 0 else ""
        if var > 0.05:
            cls = "ticker-up"
            seta = "&#9650;"
        elif var < -0.05:
            cls = "ticker-down"
            seta = "&#9660;"
        else:
            cls = "ticker-neu"
            seta = "&#9654;"

        itens.append(
            '<span class="ticker-neu">%s</span> '
            '<span class="%s">%s %s %s%s%%</span>'
            % (c["nome"], cls, c["valor"], seta, sinal, "{:.2f}".format(var).replace(".", ","))
        )

    separador = '<span class="ticker-sep">|</span>'
    conteudo = separador.join(itens)

    # Ticker + auto-refresh a cada 120s
    st.markdown(
        '<div class="ticker-wrapper">'
        '<div class="ticker-content">%s&nbsp;&nbsp;&nbsp;%s</div>'
        '</div>'
        '<script>setTimeout(function(){window.location.reload();}, 120000);</script>'
        % (conteudo, conteudo),
        unsafe_allow_html=True,
    )


# ── Backend ───────────────────────────────────────────────────────────────────

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


# ── Categorias de fonte (enum do banco) ──────────────────────────────────────
CATEGORIAS_FONTE = [
    "petroquimica",
    "industria_plastica",
    "comercio_exterior",
    "economia_global",
    "geopolitica",
    "setor_nacional",
]

TIPOS_FONTE = ["rss", "api", "scraping"]


# ── Pagina: Gerenciar Fontes ─────────────────────────────────────────────────

def _gerar_slug(nome):
    # type: (str) -> str
    """Gera slug a partir do nome: lowercase, espacos viram hifens, remove acentos."""
    import re
    import unicodedata
    slug = unicodedata.normalize("NFKD", nome).encode("ascii", "ignore").decode("ascii")
    slug = slug.lower().strip()
    slug = re.sub(r"[^a-z0-9\s-]", "", slug)
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug


def _testar_feed_rss(url_rss, usuario=None, senha=None):
    # type: (str, ..., ...) -> dict
    """Testa um feed RSS e retorna resultado com status e exemplos de artigos."""
    import feedparser
    import requests as _requests
    try:
        auth = (usuario, senha) if usuario and senha else None
        resp = _requests.get(
            url_rss, timeout=10,
            headers={"User-Agent": "Mozilla/5.0"},
            auth=auth,
        )
        if resp.status_code == 401:
            return {"ok": False, "erro": "HTTP 401 - Autenticacao necessaria. Informe usuario e senha."}
        if resp.status_code == 403:
            return {"ok": False, "erro": "HTTP 403 - Acesso negado. Verifique as credenciais."}
        if resp.status_code != 200:
            return {"ok": False, "erro": "HTTP %d ao acessar a URL." % resp.status_code}

        feed = feedparser.parse(resp.content)

        if feed.bozo and not feed.entries:
            return {"ok": False, "erro": "Feed invalido: %s" % str(feed.bozo_exception)}

        total = len(feed.entries)
        if total == 0:
            return {"ok": False, "erro": "Feed acessivel mas sem artigos (0 entries)."}

        exemplos = []
        for entry in feed.entries[:5]:
            titulo = entry.get("title", "").strip()
            if titulo:
                exemplos.append(titulo)

        return {"ok": True, "total": total, "exemplos": exemplos}
    except _requests.exceptions.Timeout:
        return {"ok": False, "erro": "Timeout ao acessar a URL (10s)."}
    except _requests.exceptions.ConnectionError:
        return {"ok": False, "erro": "Nao foi possivel conectar a URL."}
    except Exception as e:
        return {"ok": False, "erro": str(e)}


def pagina_fontes():
    st.markdown('<p class="titulo-principal">Gerenciar Fontes de Pesquisa</p>', unsafe_allow_html=True)

    # ── Saude das fontes ─────────────────────────────────────────────────
    st.markdown("### Saude da Coleta")
    try:
        saude = obter_saude_fontes()
        if saude:
            for s in saude:
                ultima = s["ultima_coleta"]
                ultima_str = ultima.strftime("%d/%m %H:%M") if ultima else "Nunca"
                erro = s["ultimo_erro"]
                erro_str = erro.strftime("%d/%m %H:%M") if erro else "Nenhum"
                status_icon = "🔴" if not s["ativa"] else ("🟢" if s["artigos_24h"] and s["artigos_24h"] > 0 else "🟡")

                col1, col2, col3, col4, col5 = st.columns([3, 1, 1, 2, 2])
                col1.write(f"{status_icon} **{s['nome']}**")
                col2.write(str(s["artigos_total"] or 0))
                col3.write(str(s["artigos_24h"] or 0))
                col4.caption("Ultima: %s" % ultima_str)
                col5.caption("Erro: %s" % erro_str)
        else:
            st.info("Nenhuma fonte cadastrada.")
    except Exception as e:
        st.error("Erro ao carregar saude: %s" % e)

    st.divider()

    # ── Listagem e toggle ativa/inativa ──────────────────────────────────
    st.markdown("### Fontes Cadastradas")
    try:
        fontes = listar_todas()
    except Exception as e:
        st.error("Erro ao listar fontes: %s" % e)
        return

    if not fontes:
        st.info("Nenhuma fonte cadastrada.")
    else:
        for fonte in fontes:
            with st.container():
                col1, col2, col3, col4 = st.columns([4, 2, 2, 2])
                col1.write("**%s** (`%s`)" % (fonte.nome, fonte.slug))
                col2.write("`%s` | `%s`" % (fonte.tipo, fonte.categoria))
                if fonte.url_rss:
                    col3.caption(fonte.url_rss[:40] + "..." if len(fonte.url_rss) > 40 else fonte.url_rss)
                else:
                    col3.caption("Sem RSS")

                # Toggle ativa/inativa
                btn_key = "toggle_%s" % fonte.slug
                if fonte.ativa:
                    if col4.button("Desativar", key=btn_key, type="secondary"):
                        alternar_ativa(fonte.slug, False)
                        st.rerun()
                else:
                    if col4.button("Ativar", key=btn_key, type="primary"):
                        alternar_ativa(fonte.slug, True)
                        st.rerun()

    st.divider()

    # ── Formulario de nova fonte ─────────────────────────────────────────
    st.markdown("### Adicionar Nova Fonte")

    # Estado: None=nao testado, dict com ok=True/False
    if "_teste_rss" not in st.session_state:
        st.session_state["_teste_rss"] = None
    # Dados da fonte que passou no teste (para o botao Adicionar)
    if "_fonte_testada" not in st.session_state:
        st.session_state["_fonte_testada"] = None

    col_a, col_b = st.columns(2)
    novo_nome = col_a.text_input("Nome da fonte *", placeholder="Ex: Chemical Week")
    novo_slug = col_b.text_input(
        "Slug (auto-gerado se vazio)",
        placeholder="Ex: chemical-week",
    )
    col_c, col_d = st.columns(2)
    novo_tipo = col_c.selectbox("Tipo *", TIPOS_FONTE)
    nova_categoria = col_d.selectbox("Categoria *", CATEGORIAS_FONTE)
    novo_url_base = st.text_input("URL do site *", placeholder="https://www.chemweek.com")
    novo_url_rss = st.text_input(
        "URL do feed RSS" + (" *" if novo_tipo == "rss" else " (opcional)"),
        placeholder="https://www.chemweek.com/rss",
    )

    # Campos de autenticacao (colapsados por padrao)
    with st.expander("Autenticacao HTTP (opcional)"):
        st.caption("Preencha apenas se o feed exigir login e senha (HTTP Basic Auth).")
        col_u, col_p = st.columns(2)
        novo_usuario = col_u.text_input("Usuario", placeholder="usuario")
        nova_senha = col_p.text_input("Senha", type="password", placeholder="senha")

    # Detecta se o usuario mudou os dados do formulario apos um teste
    _dados_atuais = (novo_nome, novo_url_rss, novo_usuario, nova_senha)
    if st.session_state.get("_dados_ultimo_teste") != _dados_atuais:
        # Dados mudaram — invalida teste anterior
        if st.session_state["_teste_rss"] is not None:
            st.session_state["_teste_rss"] = None
            st.session_state["_fonte_testada"] = None

    teste = st.session_state.get("_teste_rss")
    teste_ok = teste is not None and teste.get("ok", False)

    if not teste_ok:
        # ── Botao: Testar Feed ───────────────────────────────────────
        if st.button("Testar Feed", type="primary"):
            if not novo_nome or not novo_url_base:
                st.error("Nome e URL do site sao obrigatorios.")
            elif novo_tipo == "rss" and (not novo_url_rss or not novo_url_rss.strip()):
                st.error("URL do feed RSS e obrigatoria para fontes do tipo RSS.")
            elif not novo_url_rss or not novo_url_rss.strip():
                st.warning("URL do feed RSS nao informada. Nao e possivel testar.")
            else:
                with st.spinner("Testando feed RSS..."):
                    usuario = novo_usuario.strip() if novo_usuario.strip() else None
                    senha = nova_senha.strip() if nova_senha.strip() else None
                    resultado = _testar_feed_rss(novo_url_rss.strip(), usuario, senha)
                    st.session_state["_teste_rss"] = resultado
                    st.session_state["_dados_ultimo_teste"] = _dados_atuais
                    if resultado["ok"]:
                        slug_final = novo_slug.strip() if novo_slug.strip() else _gerar_slug(novo_nome)
                        st.session_state["_fonte_testada"] = {
                            "nome": novo_nome.strip(),
                            "slug": slug_final,
                            "url_base": novo_url_base.strip(),
                            "tipo": novo_tipo,
                            "categoria": nova_categoria,
                            "url_rss": novo_url_rss.strip(),
                            "rss_usuario": usuario,
                            "rss_senha": senha,
                        }
                    st.rerun()
    else:
        # ── Botao: Adicionar Fonte (teste passou) ────────────────────
        if st.button("Adicionar Fonte", type="primary"):
            dados = st.session_state["_fonte_testada"]
            try:
                fonte_criada = cadastrar_fonte(
                    nome=dados["nome"],
                    slug=dados["slug"],
                    url_base=dados["url_base"],
                    tipo=dados["tipo"],
                    categoria=dados["categoria"],
                    url_rss=dados["url_rss"],
                    rss_usuario=dados["rss_usuario"],
                    rss_senha=dados["rss_senha"],
                )
                st.session_state["_teste_rss"] = None
                st.session_state["_fonte_testada"] = None
                st.session_state["_dados_ultimo_teste"] = None
                st.success(
                    "Fonte '%s' cadastrada com sucesso (slug: %s). "
                    "Sera coletada na proxima execucao da DAG."
                    % (fonte_criada.nome, fonte_criada.slug)
                )
                st.rerun()
            except ValueError as ve:
                st.error(str(ve))
            except Exception as e:
                msg = str(e)
                if "fontes_slug_uk" in msg:
                    st.error("Ja existe uma fonte com o slug '%s'." % dados["slug"])
                elif "fontes_nome_uk" in msg:
                    st.error("Ja existe uma fonte com o nome '%s'." % dados["nome"])
                else:
                    st.error("Erro ao cadastrar: %s" % e)

    # ── Resultado do teste ───────────────────────────────────────────
    if teste is not None:
        if teste["ok"]:
            st.success(
                "Feed valido! %d artigos encontrados. Exemplos:" % teste["total"]
            )
            for titulo in teste["exemplos"]:
                st.markdown("- %s" % titulo)
        else:
            st.error("Falha no teste: %s" % teste["erro"])


# ── Pagina: Chat (original) ──────────────────────────────────────────────────

def pagina_chat():
    if "historico" not in st.session_state:
        st.session_state.historico = []

    # Filtros na sidebar (adicionados pela main)
    categoria_label = st.session_state.get("_filtro_categoria", "Todas")
    categoria = CATEGORIAS[categoria_label]
    dias = st.session_state.get("_filtro_dias", 90)
    top_k = st.session_state.get("_filtro_top_k", 8)
    modo_preditivo = st.session_state.get("_filtro_preditivo", False)

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
                        st.markdown("**Fontes consultadas (%d artigos):**" % len(artigos))
                        for a in artigos:
                            data = a["data_publicacao"].strftime("%d/%m/%Y") if a["data_publicacao"] else "s/d"
                            st.markdown(
                                '<div class="artigo-card">'
                                '<span class="fonte-tag">%s</span> '
                                '<span class="fonte-tag">%s</span> '
                                '<span class="score-badge">score %s</span> '
                                '<span class="score-badge">sim %.2f</span><br>'
                                '<a href="%s" target="_blank">%s</a> '
                                '<small style="color:#666666;">(%s)</small>'
                                '</div>'
                                % (a["fonte_nome"], a["categoria"], a["relevancia"],
                                   a["similaridade"], a["url"], a["titulo"], data),
                                unsafe_allow_html=True,
                            )

                    st.session_state.historico.append({"role": "assistant", "content": resposta})

                except Exception as e:
                    st.error("Erro: %s" % e)

    # Ticker no rodape
    renderizar_ticker()


# ── Interface principal ───────────────────────────────────────────────────────

def main():
    with st.sidebar:
        st.markdown("### Market Intelligence")
        st.markdown("**Lorenzetti S.A.** | Assessoria a Alta Direcao")
        st.divider()

        pagina = st.radio(
            "Navegar",
            ["Chat", "Gerenciar Fontes"],
            label_visibility="collapsed",
        )
        st.divider()

        if pagina == "Chat":
            st.markdown("#### Filtros")
            st.session_state["_filtro_categoria"] = st.selectbox("Categoria", list(CATEGORIAS.keys()))
            st.session_state["_filtro_dias"] = st.slider("Periodo (dias)", 7, 365, 90)
            st.session_state["_filtro_top_k"] = st.slider("Artigos por consulta", 3, 15, 8)
            st.session_state["_filtro_preditivo"] = st.toggle("Modo Analise Preditiva", value=False)
            st.divider()
            st.markdown("#### Base de Dados")
            try:
                stats = obter_estatisticas()
                st.metric("Artigos coletados", stats["total_artigos"])
                st.metric("Artigos vetorizados", stats["total_embeddings"])
                if stats["ultima_coleta"]:
                    st.caption("Ultima coleta: %s" % stats["ultima_coleta"].strftime("%d/%m %H:%M"))
            except Exception:
                st.caption("Estatisticas indisponiveis")
            st.divider()
            if st.button("Limpar conversa"):
                st.session_state.historico = []
                st.rerun()

    if pagina == "Chat":
        pagina_chat()
    else:
        pagina_fontes()


if __name__ == "__main__":
    main()

