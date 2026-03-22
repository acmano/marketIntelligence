-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 001 — Criação do schema Market Intelligence
-- Projeto: Market Intelligence — Assessoria à Alta Direção
-- Executar: psql -U <usuario> -d <banco> -f migrations/001_create_schema.sql
-- ─────────────────────────────────────────────────────────────────────────────

-- Extensão vetorial (requer pgvector instalado)
CREATE EXTENSION IF NOT EXISTS vector;

-- ─────────────────────────────────────────────────────────────────────────────
-- 1. Cadastro de fontes
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mi_fontes (
    id              SERIAL PRIMARY KEY,
    nome            VARCHAR(100) NOT NULL,
    url_base        TEXT NOT NULL,
    url_rss         TEXT,
    tipo            VARCHAR(20) NOT NULL CHECK (tipo IN ('rss', 'api', 'scraping')),
    categoria       VARCHAR(30) NOT NULL CHECK (categoria IN (
                        'petroquimica', 'industria_plastica',
                        'comercio_exterior', 'economia_global',
                        'geopolitica', 'setor_nacional'
                    )),
    ativa           BOOLEAN NOT NULL DEFAULT TRUE,
    criado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    atualizado_em   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE mi_fontes IS 'Cadastro de fontes de notícias monitoradas';

-- ─────────────────────────────────────────────────────────────────────────────
-- 2. Artigos coletados (dados brutos)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mi_artigos (
    id                  SERIAL PRIMARY KEY,
    fonte_id            INTEGER NOT NULL REFERENCES mi_fontes(id),
    titulo              TEXT NOT NULL,
    url                 TEXT NOT NULL UNIQUE,    -- deduplicação por URL
    texto_bruto         TEXT,
    data_publicacao     TIMESTAMPTZ,
    data_coleta         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processado          BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_mi_artigos_fonte_id     ON mi_artigos(fonte_id);
CREATE INDEX IF NOT EXISTS idx_mi_artigos_data_pub     ON mi_artigos(data_publicacao DESC);
CREATE INDEX IF NOT EXISTS idx_mi_artigos_processado   ON mi_artigos(processado) WHERE processado = FALSE;

COMMENT ON TABLE mi_artigos IS 'Artigos coletados em estado bruto pelas DAGs de coleta';

-- ─────────────────────────────────────────────────────────────────────────────
-- 3. Artigos processados (enriquecidos por IA)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mi_artigos_processados (
    id                  SERIAL PRIMARY KEY,
    artigo_id           INTEGER NOT NULL UNIQUE REFERENCES mi_artigos(id),
    resumo_pt           TEXT,                   -- resumo em português (máx 150 palavras)
    categoria           VARCHAR(30) CHECK (categoria IN (
                            'materia-prima', 'mercado-exportacao',
                            'geopolitica', 'economia', 'regulatorio', 'outro'
                        )),
    relevancia_score    SMALLINT CHECK (relevancia_score BETWEEN 0 AND 10),
    tom                 VARCHAR(10) CHECK (tom IN ('neutro', 'positivo', 'negativo', 'alerta')),
    entidades_json      JSONB,                  -- {paises: [], commodities: [], empresas: []}
    processado_em       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    modelo_ia           VARCHAR(50)             -- versão do modelo usado
);

CREATE INDEX IF NOT EXISTS idx_mi_proc_artigo_id    ON mi_artigos_processados(artigo_id);
CREATE INDEX IF NOT EXISTS idx_mi_proc_categoria    ON mi_artigos_processados(categoria);
CREATE INDEX IF NOT EXISTS idx_mi_proc_relevancia   ON mi_artigos_processados(relevancia_score DESC);
CREATE INDEX IF NOT EXISTS idx_mi_proc_data         ON mi_artigos_processados(processado_em DESC);
CREATE INDEX IF NOT EXISTS idx_mi_proc_entidades    ON mi_artigos_processados USING GIN (entidades_json);

COMMENT ON TABLE mi_artigos_processados IS 'Versão enriquecida dos artigos: resumo, categoria, score de relevância e entidades';

-- ─────────────────────────────────────────────────────────────────────────────
-- 4. Embeddings vetoriais (pgvector)
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mi_embeddings (
    id                  SERIAL PRIMARY KEY,
    artigo_id           INTEGER NOT NULL UNIQUE REFERENCES mi_artigos(id),
    embedding           VECTOR(1536),           -- text-embedding-3-small da OpenAI
    gerado_em           TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Índice HNSW para busca por similaridade coseno (melhor performance em larga escala)
CREATE INDEX IF NOT EXISTS idx_mi_embeddings_hnsw
    ON mi_embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE mi_embeddings IS 'Vetores semânticos dos artigos para busca por similaridade (RAG)';

-- ─────────────────────────────────────────────────────────────────────────────
-- 5. Log de execução das DAGs
-- ─────────────────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS mi_coletas_log (
    id                  SERIAL PRIMARY KEY,
    dag_id              VARCHAR(50) NOT NULL,
    fonte_id            INTEGER REFERENCES mi_fontes(id),
    status              VARCHAR(10) NOT NULL CHECK (status IN ('success', 'error', 'warning')),
    qtd_artigos         INTEGER DEFAULT 0,
    qtd_novos           INTEGER DEFAULT 0,
    custo_tokens_usd    NUMERIC(8,6),
    mensagem_erro       TEXT,
    iniciado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finalizado_em       TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_mi_log_dag_id    ON mi_coletas_log(dag_id);
CREATE INDEX IF NOT EXISTS idx_mi_log_status    ON mi_coletas_log(status);
CREATE INDEX IF NOT EXISTS idx_mi_log_data      ON mi_coletas_log(iniciado_em DESC);

COMMENT ON TABLE mi_coletas_log IS 'Histórico de execuções das DAGs Airflow com métricas e erros';

-- ─────────────────────────────────────────────────────────────────────────────
-- 6. Função auxiliar de busca por similaridade semântica
-- ─────────────────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION buscar_artigos_similares(
    query_vector    VECTOR(1536),
    top_k           INTEGER DEFAULT 8,
    filtro_cat      VARCHAR DEFAULT NULL,
    score_minimo    INTEGER DEFAULT 4,
    dias_max        INTEGER DEFAULT 90
)
RETURNS TABLE (
    artigo_id       INTEGER,
    titulo          TEXT,
    url             TEXT,
    resumo_pt       TEXT,
    categoria       VARCHAR,
    relevancia      SMALLINT,
    tom             VARCHAR,
    data_publicacao TIMESTAMPTZ,
    fonte_nome      VARCHAR,
    similaridade    FLOAT
)
LANGUAGE SQL STABLE AS $$
    SELECT
        a.id,
        a.titulo,
        a.url,
        p.resumo_pt,
        p.categoria,
        p.relevancia_score,
        p.tom,
        a.data_publicacao,
        f.nome,
        1 - (e.embedding <=> query_vector) AS similaridade
    FROM mi_embeddings e
    JOIN mi_artigos a             ON a.id = e.artigo_id
    JOIN mi_artigos_processados p ON p.artigo_id = a.id
    JOIN mi_fontes f              ON f.id = a.fonte_id
    WHERE
        p.relevancia_score >= score_minimo
        AND a.data_publicacao >= NOW() - (dias_max || ' days')::INTERVAL
        AND (filtro_cat IS NULL OR p.categoria = filtro_cat)
    ORDER BY e.embedding <=> query_vector
    LIMIT top_k;
$$;

COMMENT ON FUNCTION buscar_artigos_similares IS
    'Busca artigos semanticamente similares ao vetor de consulta usando pgvector (cosine similarity)';
