# Market Intelligence — Assessoria à Alta Direção

> Plataforma de coleta, processamento e entrega de inteligência de mercado com IA.
> Lorenzetti S.A. — Departamento de TI/Sistemas

---

## Visão Geral

Sistema contínuo de monitoramento de notícias relevantes para dois eixos estratégicos da Lorenzetti:

- **Matérias-primas plásticas** (PP, Nylon, ABS) — preços, disponibilidade, geopolítica de produtores
- **Mercados de exportação** — demanda, regulação e concorrência nos países importadores

### Entregas

| Entrega | Descrição | Frequência |
|---|---|---|
| PowerPoint semanal | Relatório curado por IA com top notícias e análise preditiva | Toda segunda-feira às 07h |
| Agente conversacional | Interface de perguntas em linguagem natural com RAG | Sob demanda (Streamlit → Nexus) |

---

## Arquitetura

```
Fontes (RSS/APIs/Scrapers)
        │
        ▼
[DAG: mi_coleta] ── Airflow ──▶ PostgreSQL (mi_artigos)
        │
        ▼
[DAG: mi_processamento] ── API Claude ──▶ PostgreSQL (mi_artigos_processados)
        │                                         │
        ▼                                         ▼
[DAG: mi_powerpoint]                    pgvector (mi_embeddings)
        │                                         │
        ▼                                         ▼
  E-mail (.pptx)                     Agente RAG (Streamlit → Nexus)
```

---

## Stack Tecnológica

| Camada | Tecnologia |
|---|---|
| Orquestração | Apache Airflow |
| Coleta | Python + feedparser + requests + BeautifulSoup4 |
| Armazenamento | PostgreSQL + extensão pgvector |
| Inteligência Artificial | API Claude — Anthropic (claude-sonnet-4-5) |
| Embeddings | OpenAI text-embedding-3-small |
| Relatório Semanal | python-pptx |
| Agente MVP | Streamlit |
| Agente Final | React (módulo Nexus) + lordtsapi |

---

## Estrutura do Repositório

```
marketIntelligence/
├── dags/                   # DAGs do Apache Airflow
│   ├── mi_coleta.py        # Coleta diária de notícias (06h)
│   ├── mi_processamento.py # Enriquecimento por IA (classificação, resumo, embeddings)
│   └── mi_powerpoint.py    # Geração e envio do PowerPoint semanal (segunda 07h)
├── scrapers/               # Módulos de coleta por fonte
│   ├── base_scraper.py     # Classe base com interface comum
│   ├── reuters.py
│   ├── icis.py
│   ├── plastics_news.py
│   ├── world_bank.py
│   ├── trademap.py
│   ├── bloomberg.py
│   ├── financial_times.py
│   ├── abiplast.py
│   └── abiquim.py
├── embeddings/             # Pipeline de geração de vetores
│   └── generator.py
├── migrations/             # Scripts SQL versionados
│   ├── 001_create_schema.sql
│   └── 002_seed_fontes.sql
├── docs/                   # Documentação técnica
│   ├── architecture.md
│   └── runbook.md
├── tests/                  # Testes unitários e de integração
├── .env.example            # Variáveis de ambiente necessárias
├── .gitignore
├── requirements.txt
└── README.md               # Este arquivo
```

---

## Configuração

### 1. Variáveis de ambiente

Copie `.env.example` para `.env` e preencha:

```bash
cp .env.example .env
```

### 2. Instalar dependências Python

```bash
pip install -r requirements.txt
```

### 3. Aplicar migrations no PostgreSQL

```bash
psql -U <usuario> -d <banco> -f migrations/001_create_schema.sql
psql -U <usuario> -d <banco> -f migrations/002_seed_fontes.sql
```

### 4. Copiar DAGs para o Airflow

```bash
cp dags/*.py $AIRFLOW_HOME/dags/
```

---

## Roadmap

| Fase | Período | Marco |
|---|---|---|
| Fase 1 — Infraestrutura e Coleta | Semanas 1–2 | Primeiro lote de artigos coletados |
| Fase 2 — Pipeline de IA | Semanas 3–4 | Base de dados enriquecida |
| Fase 3 — MVP | Semana 5 | MVP validado com usuários |
| Fase 4 — Refinamento | Semanas 6–7 | Sistema estável em produção |
| Fase 5 — Nexus | Semanas 8–11 | Versão final no Nexus |

---

## Custo Operacional Estimado

| Item | Custo |
|---|---|
| API Claude (Anthropic) | US$ 50–200/mês |
| Embeddings (OpenAI) | US$ 1–5/mês |
| Infraestrutura | R$ 0 (servidores existentes) |
| **Total** | **~US$ 100–200/mês** |

---

## Contato

**Responsável:** Antonio Carlos Mano — TI/Sistemas  
**Projeto Linear:** [Market Intelligence — MKI](https://linear.app/nexusbymano/project/market-intelligence-assessoria-a-alta-direcao-cf46176dae88)
