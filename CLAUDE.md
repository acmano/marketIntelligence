# Market Intelligence — Contexto para Claude Code

## O que é este projeto

Plataforma de inteligência de mercado da Lorenzetti S.A. para a Assessoria à Alta Direção.
Coleta notícias de fontes internacionais, processa via IA (Claude API) e entrega via:
- Agente conversacional com RAG (Streamlit, porta 8501)
- Relatório semanal PowerPoint (gerado todo domingo, enviado segunda às 07h)

## Localização no servidor

```
/home/mano/projetos/datasul/marketIntelligence/
```

Mesmo nível de: `nexus/`, `nexusApi/`, `nexusDocs/`

## Stack

| Camada | Tecnologia |
|---|---|
| Orquestração | Apache Airflow prod (`/opt/airflow-prod`) |
| Coleta | Python 3.8 + feedparser + requests (Google News RSS) |
| Banco | PostgreSQL — banco `market_intelligence`, schema `mi`, role `mi_app` |
| Busca semântica | pgvector (extensão instalada) |
| IA — análise | API Claude (Anthropic) — modelo claude-sonnet-4-5 |
| IA — embeddings | OpenAI text-embedding-3-small (1536 dimensões) |
| Relatório | python-pptx |
| Agente MVP | Streamlit 1.40.1 |

## Python

Versão: **3.8.10** — atenção às incompatibilidades:
- Usar `Optional[X]` em vez de `X | None`
- Usar `Dict[X, Y]`, `List[X]`, `Type[X]` de `typing` em vez de `dict[x,y]`, `list[x]`
- Nunca usar emojis em arquivos `.py` — causam corrupção de encoding no servidor

## Estrutura do repositório

```
marketIntelligence/
├── agente.py               # Agente Streamlit (MVP) — porta 8501
├── testar_powerpoint.py    # Script standalone para testar geração de PPTX
├── CLAUDE.md               # Este arquivo
├── .env                    # Credenciais (nunca commitar)
├── .env.example            # Template de variáveis
├── requirements.txt
├── core/
│   ├── db.py               # Pool de conexões PostgreSQL
│   ├── fontes_repo.py      # Lookup de fontes por slug (sem hardcode)
│   ├── artigos_repo.py     # CRUD de artigos
│   ├── processados_repo.py # Persistência dos resultados da IA
│   ├── processador_ia.py   # Pipeline Claude API (classificação, resumo, entidades)
│   ├── embeddings_repo.py  # CRUD de embeddings
│   ├── pipeline_embeddings.py  # Geração de embeddings em lote
│   └── gerador_pptx.py     # Geração do PowerPoint com python-pptx
├── scrapers/
│   ├── base_scraper.py     # Classe base (retry automático, sem SQL direto)
│   ├── rss_scrapers.py     # Reuters, ICIS, Plastics News, Bloomberg, FT
│   └── api_scrapers.py     # ABIPLAST, ABIQUIM (RSS), World Bank e TradeMap (stubs)
├── embeddings/
│   └── generator.py        # OpenAI text-embedding-3-small
├── dags/
│   ├── mi_coleta.py        # DAG diária 06h — coleta → dispara mi_processamento
│   ├── mi_processamento.py # DAG sem schedule — processa IA → dispara mi_powerpoint (seg)
│   └── mi_powerpoint.py    # DAG sem schedule — gera e envia PPTX por email
├── migrations/
│   ├── 000_create_database.sql
│   ├── 001_create_schema.sql
│   └── 002_seed_fontes.sql
├── output/                 # PowerPoints gerados (gitignore)
└── docs/
    ├── architecture.md
    └── runbook.md
```

## Banco de dados

**Conexão:**
```
Host:   10.105.0.56 (ou variável MI_DB_HOST)
Banco:  market_intelligence
Schema: mi (search_path configurado na role)
User:   mi_app
```

**Tabelas principais:**
- `mi.fontes` — cadastro de fontes (lookup por `slug`, nunca por ID)
- `mi.artigos` — artigos brutos coletados (deduplicação por URL)
- `mi.artigos_processados` — enriquecimento por IA (1:1 com artigos)
- `mi.embeddings` — vetores pgvector 1536d
- `mi.execucoes_log` — histórico de execuções das DAGs

**Views úteis:**
- `mi.v_artigos_completos` — join desnormalizado para consultas
- `mi.v_saude_coleta` — dashboard de saúde por fonte

**Função de busca semântica:**
```sql
SELECT * FROM mi.buscar_similares(
    vetor::vector,
    top_k::integer,
    categoria::mi.categoria_artigo,  -- NULL para todas
    score_min::smallint,
    dias_max::integer
);
```

## Fontes de coleta (9 ativas)

Todas usam Google News RSS (Reuters encerrou feeds oficiais em 2020):

| Slug | Nome | Categoria |
|---|---|---|
| reuters-commodities | Reuters Commodities | petroquimica |
| icis | ICIS | petroquimica |
| plastics-news | Plastics News | industria_plastica |
| bloomberg | Bloomberg Markets | economia_global |
| financial-times | Financial Times | geopolitica |
| world-bank | World Bank Open Data | economia_global |
| trademap | ITC Trade Map | comercio_exterior |
| abiplast | ABIPLAST | setor_nacional |
| abiquim | ABIQUIM | setor_nacional |

World Bank e TradeMap são stubs — não coletam ainda (pendente MKI futura).

## Airflow

**Instância prod:** `/opt/airflow-prod`
**DAGs:**  `/opt/airflow-prod/dags/`
**Executar comandos:**
```bash
AIRFLOW_HOME=/opt/airflow-prod /opt/airflow-prod/venv/bin/airflow <comando>
```
**Copiar DAG:**
```bash
sudo cp dags/mi_coleta.py /opt/airflow-prod/dags/
```
**Executor:** SequentialExecutor (sem paralelismo)

**Fluxo encadeado:**
```
mi_coleta (06h diário)
    └── TriggerDagRunOperator → mi_processamento
            └── TriggerDagRunOperator → mi_powerpoint (apenas segundas-feiras)
```

## Agente Streamlit

**Executar:**
```bash
cd /home/mano/projetos/datasul/marketIntelligence
streamlit run agente.py --server.port 8501 --server.address 0.0.0.0
```

**Acesso:** `http://10.105.0.56:8501`

**Ticker financeiro:** Yahoo Finance via requests (sem yfinance — incompatível com Python 3.8)
Ativos: USD/BRL, EUR/BRL, Ouro, Prata, Brent, LME Cobre, LME Alumínio, LME Zinco, IBOV, S&P 500, Nasdaq

## Variáveis de ambiente (.env)

```
MI_DB_HOST=10.105.0.56
MI_DB_PORT=5432
MI_DB_NAME=market_intelligence
MI_DB_USER=mi_app
MI_DB_PASSWORD=...
ANTHROPIC_API_KEY=...
ANTHROPIC_MODEL=claude-sonnet-4-5
OPENAI_API_KEY=...
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
MI_SCORE_MIN_EMBEDDING=4
MI_SCORE_MIN_PPTX=7
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=...
SMTP_PASSWORD=...
SMTP_FROM=...
PPTX_RECIPIENTS=...
```

## Backlog Linear

Projeto: **Market Intelligence — Assessoria à Alta Direção** (prefixo MKI)
URL: https://linear.app/nexusbymano/project/market-intelligence-assessoria-a-alta-direcao-cf46176dae88

Issues pendentes relevantes:
- **MKI-12** — Sessão de validação com usuários (In Progress)
- **MKI-13** — Ajustes pós-validação e refinamento de prompts
- **MKI-14** — Monitoramento de saúde e alertas operacionais
- **MKI-15** — Documentação técnica
- **MKI-22** — Tela de gerenciamento de fontes na UI
- **MKI-23** — Ticker financeiro (concluído nesta sessão)

## Regras importantes

1. **Nunca hardcode IDs** — fontes sempre resolvidas por `slug` via `core.fontes_repo.get_by_slug()`
2. **Scrapers não tocam SQL** — toda persistência passa pelos repositórios em `core/`
3. **Python 3.8** — sem syntax moderna de tipos
4. **Sem emojis em .py** — causam corrupção de encoding
5. **Arquivos .env nunca vão para o git**
