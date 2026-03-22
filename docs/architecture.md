# Arquitetura — Market Intelligence

## Visão de Componentes

```
┌──────────────────────────────────────────────────────────────────────┐
│                        Apache Airflow                                │
│                                                                      │
│  ┌─────────────┐   ┌──────────────────┐   ┌──────────────────────┐  │
│  │ mi_coleta   │   │ mi_processamento  │   │   mi_powerpoint      │  │
│  │ (06h diário)│──▶│ (07h diário)      │   │ (segunda 07h)        │  │
│  └─────────────┘   └──────────────────┘   └──────────────────────┘  │
│         │                  │  │                       │              │
└─────────┼──────────────────┼──┼───────────────────────┼──────────────┘
          │                  │  │                       │
          ▼                  ▼  ▼                       │
  ┌───────────────────────────────────┐                 │
  │         PostgreSQL                │                 │
  │                                   │                 ▼
  │  mi_fontes                        │         ┌──────────────┐
  │  mi_artigos         ◀─ coleta     │         │  API Claude  │
  │  mi_artigos_proc    ◀─ IA         │         │  (Anthropic) │
  │  mi_embeddings      ◀─ OpenAI     │         └──────────────┘
  │  mi_coletas_log                   │
  └───────────────────────────────────┘
          │
          │ pgvector (busca semântica)
          ▼
  ┌───────────────────────────────────┐
  │   Agente Conversacional (RAG)     │
  │                                   │
  │   MVP: Streamlit                  │
  │   Produção: módulo React/Nexus    │
  └───────────────────────────────────┘
```

## Fluxo de Dados

### 1. Coleta (DAG: mi_coleta)
- Airflow dispara 9 tasks em paralelo (pool: 3 slots)
- Cada task instancia o scraper da fonte e chama `executar()`
- Artigos são salvos em `mi_artigos` com deduplicação por URL
- Resultado registrado em `mi_coletas_log`

### 2. Processamento (DAG: mi_processamento)
- Busca artigos com `processado = FALSE`
- Envia para API Claude em lotes (batch de 10)
- Claude retorna: categoria, score, tom, entidades, resumo_pt
- Salva em `mi_artigos_processados` e marca `mi_artigos.processado = TRUE`
- Para artigos com score >= 4: gera embedding via OpenAI e salva em `mi_embeddings`

### 3. Relatório Semanal (DAG: mi_powerpoint)
- Seleciona artigos da semana com score >= 7
- Claude gera textos curados para cada seção do slide
- python-pptx monta o arquivo .pptx com o template
- Airflow envia por SMTP para lista de destinatários

### 4. Agente Conversacional (RAG)
- Usuário digita pergunta
- Sistema gera embedding da pergunta via OpenAI
- pgvector retorna os 8 artigos mais similares (busca coseno)
- Pergunta + artigos enviados para Claude como contexto
- Claude retorna resposta fundamentada com citação das fontes

## Decisões de Arquitetura (ADR)

### ADR-001: PostgreSQL + pgvector vs banco vetorial dedicado
**Decisão:** pgvector no PostgreSQL existente  
**Justificativa:** Volume esperado (~5.000 artigos/ano) está bem dentro da capacidade do pgvector. 
Elimina infraestrutura adicional e mantém tudo num único banco já gerenciado.  
**Trade-off:** Menor performance que Pinecone/Qdrant em escala de milhões de vetores (não é o caso).

### ADR-002: API Claude vs modelo open-source self-hosted
**Decisão:** API Claude (Anthropic)  
**Justificativa:** Qualidade analítica superior para textos jornalísticos complexos. 
Custo estimado de US$ 100-200/mês é viável vs investimento de R$ 10.000-80.000 em GPU dedicada.  
**Trade-off:** Dados transitam por API externa (Anthropic tem política de não retenção de dados da API).

### ADR-003: Streamlit no MVP vs React direto
**Decisão:** Streamlit no MVP, React no Nexus na Fase 5  
**Justificativa:** Streamlit permite validar a experiência do usuário em 2 semanas. 
React entregaria o mesmo resultado em 4-6 semanas com risco maior antes da validação.  
**Trade-off:** Período de transição onde dois sistemas coexistem (Fases 3-4).
