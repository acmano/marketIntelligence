-- =============================================================================
-- Migration 001 — Schema e tabelas do Market Intelligence
-- Projeto: Market Intelligence — Assessoria à Alta Direção
--
-- EXECUTAR CONECTADO AO BANCO 'market_intelligence':
--   psql -U postgres -d market_intelligence -f migrations/001_create_schema.sql
--
-- Este script é idempotente: seguro para re-execução.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- Extensões
-- -----------------------------------------------------------------------------
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";   -- geração de UUIDs v4
CREATE EXTENSION IF NOT EXISTS vector;        -- pgvector (busca semântica)

-- -----------------------------------------------------------------------------
-- Schema dedicado
-- -----------------------------------------------------------------------------
CREATE SCHEMA IF NOT EXISTS mi
    AUTHORIZATION mi_app;

COMMENT ON SCHEMA mi IS
    'Schema do sistema Market Intelligence — coleta, processamento e entrega de inteligência de mercado';

-- Configura search_path da role de aplicação
ALTER ROLE mi_app SET search_path = mi, public;

-- -----------------------------------------------------------------------------
-- Função utilitária: atualiza updated_at automaticamente via trigger
-- -----------------------------------------------------------------------------
CREATE OR REPLACE FUNCTION mi.set_updated_at()
RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$;

COMMENT ON FUNCTION mi.set_updated_at IS
    'Trigger function: mantém updated_at sincronizado com o horário de qualquer UPDATE';

-- =============================================================================
-- TIPOS ENUMERADOS
-- Mais seguros que CHECK + VARCHAR: o banco rejeita valores inválidos na camada
-- de armazenamento, independentemente da aplicação.
-- =============================================================================
DO $$ BEGIN CREATE TYPE mi.tipo_fonte AS ENUM
    ('rss', 'api', 'scraping');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE mi.categoria_fonte AS ENUM (
    'petroquimica', 'industria_plastica', 'comercio_exterior',
    'economia_global', 'geopolitica', 'setor_nacional');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE mi.categoria_artigo AS ENUM (
    'materia-prima', 'mercado-exportacao', 'geopolitica',
    'economia', 'regulatorio', 'outro');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE mi.tom_artigo AS ENUM
    ('neutro', 'positivo', 'negativo', 'alerta');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

DO $$ BEGIN CREATE TYPE mi.status_execucao AS ENUM
    ('success', 'error', 'warning');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- =============================================================================
-- TABELAS
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Cadastro de fontes
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mi.fontes (
    id          UUID                NOT NULL DEFAULT uuid_generate_v4(),
    nome        VARCHAR(100)        NOT NULL,
    slug        VARCHAR(50)         NOT NULL,   -- chave de lookup pelo código (nunca muda)
    url_base    TEXT                NOT NULL,
    url_rss     TEXT,
    tipo        mi.tipo_fonte       NOT NULL,
    categoria   mi.categoria_fonte  NOT NULL,
    ativa       BOOLEAN             NOT NULL DEFAULT TRUE,
    created_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ         NOT NULL DEFAULT NOW(),

    CONSTRAINT fontes_pkey    PRIMARY KEY (id),
    CONSTRAINT fontes_slug_uk UNIQUE (slug),
    CONSTRAINT fontes_nome_uk UNIQUE (nome)
);

CREATE TRIGGER trg_fontes_updated_at
    BEFORE UPDATE ON mi.fontes
    FOR EACH ROW EXECUTE FUNCTION mi.set_updated_at();

COMMENT ON TABLE  mi.fontes      IS 'Cadastro de fontes de notícias monitoradas';
COMMENT ON COLUMN mi.fontes.slug IS
    'Identificador estável e imutável. O código resolve fonte_id via slug — nenhum ID é hardcoded';

-- -----------------------------------------------------------------------------
-- 2. Artigos coletados (dados brutos)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mi.artigos (
    id                  UUID        NOT NULL DEFAULT uuid_generate_v4(),
    fonte_id            UUID        NOT NULL,
    titulo              TEXT        NOT NULL,
    url                 TEXT        NOT NULL,
    texto_bruto         TEXT,
    data_publicacao     TIMESTAMPTZ,
    coletado_em         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processado          BOOLEAN     NOT NULL DEFAULT FALSE,

    CONSTRAINT artigos_pkey     PRIMARY KEY (id),
    CONSTRAINT artigos_url_uk   UNIQUE (url),
    CONSTRAINT artigos_fonte_fk FOREIGN KEY (fonte_id)
        REFERENCES mi.fontes(id) ON DELETE RESTRICT
);

CREATE INDEX idx_artigos_fonte_id ON mi.artigos(fonte_id);
CREATE INDEX idx_artigos_data_pub ON mi.artigos(data_publicacao DESC);
CREATE INDEX idx_artigos_nao_proc ON mi.artigos(coletado_em DESC) WHERE processado = FALSE;

COMMENT ON TABLE mi.artigos IS 'Artigos coletados em estado bruto pelas DAGs de coleta';

-- -----------------------------------------------------------------------------
-- 3. Artigos processados (enriquecidos por IA)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mi.artigos_processados (
    id                  UUID                    NOT NULL DEFAULT uuid_generate_v4(),
    artigo_id           UUID                    NOT NULL,
    resumo_pt           TEXT,
    categoria           mi.categoria_artigo,
    relevancia_score    SMALLINT                CHECK (relevancia_score BETWEEN 0 AND 10),
    tom                 mi.tom_artigo,
    -- {"paises": ["Brasil","China"], "commodities": ["PP","ABS"], "empresas": ["Braskem"]}
    entidades           JSONB                   NOT NULL DEFAULT '{}',
    modelo_ia           VARCHAR(60)             NOT NULL,
    processado_em       TIMESTAMPTZ             NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ             NOT NULL DEFAULT NOW(),

    CONSTRAINT artigos_proc_pkey      PRIMARY KEY (id),
    CONSTRAINT artigos_proc_artigo_uk UNIQUE (artigo_id),
    CONSTRAINT artigos_proc_artigo_fk FOREIGN KEY (artigo_id)
        REFERENCES mi.artigos(id) ON DELETE CASCADE
);

CREATE TRIGGER trg_artigos_proc_updated_at
    BEFORE UPDATE ON mi.artigos_processados
    FOR EACH ROW EXECUTE FUNCTION mi.set_updated_at();

CREATE INDEX idx_proc_categoria  ON mi.artigos_processados(categoria);
CREATE INDEX idx_proc_relevancia ON mi.artigos_processados(relevancia_score DESC);
CREATE INDEX idx_proc_data       ON mi.artigos_processados(processado_em DESC);
CREATE INDEX idx_proc_entidades  ON mi.artigos_processados USING GIN (entidades);
CREATE INDEX idx_proc_alta_rel   ON mi.artigos_processados(processado_em DESC)
    WHERE relevancia_score >= 7;

COMMENT ON TABLE  mi.artigos_processados          IS
    'Versão enriquecida dos artigos: resumo PT, categoria, score de relevância e entidades extraídas pela IA';
COMMENT ON COLUMN mi.artigos_processados.entidades IS
    'JSON com listas de países, commodities e empresas mencionados no artigo';

-- -----------------------------------------------------------------------------
-- 4. Embeddings vetoriais (pgvector)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mi.embeddings (
    id          UUID            NOT NULL DEFAULT uuid_generate_v4(),
    artigo_id   UUID            NOT NULL,
    embedding   VECTOR(1536)    NOT NULL,    -- text-embedding-3-small (OpenAI)
    modelo      VARCHAR(60)     NOT NULL,
    gerado_em   TIMESTAMPTZ     NOT NULL DEFAULT NOW(),

    CONSTRAINT embeddings_pkey      PRIMARY KEY (id),
    CONSTRAINT embeddings_artigo_uk UNIQUE (artigo_id),
    CONSTRAINT embeddings_artigo_fk FOREIGN KEY (artigo_id)
        REFERENCES mi.artigos(id) ON DELETE CASCADE
);

-- HNSW: melhor para produção (sem necessidade de VACUUM periódico como IVFFlat)
-- m=16, ef_construction=64: equilíbrio recall/velocidade para volume esperado
CREATE INDEX idx_embeddings_hnsw
    ON mi.embeddings
    USING hnsw (embedding vector_cosine_ops)
    WITH (m = 16, ef_construction = 64);

COMMENT ON TABLE  mi.embeddings           IS 'Vetores semânticos dos artigos para busca por similaridade coseno (RAG)';
COMMENT ON COLUMN mi.embeddings.embedding IS 'Vetor de 1536 dimensões — modelo text-embedding-3-small (OpenAI)';

-- -----------------------------------------------------------------------------
-- 5. Log de execução das DAGs
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS mi.execucoes_log (
    id              UUID                NOT NULL DEFAULT uuid_generate_v4(),
    dag_id          VARCHAR(50)         NOT NULL,
    fonte_id        UUID,                          -- NULL para DAGs globais
    status          mi.status_execucao  NOT NULL,
    qtd_coletados   INTEGER             NOT NULL DEFAULT 0,
    qtd_novos       INTEGER             NOT NULL DEFAULT 0,
    custo_usd       NUMERIC(10, 6),                -- custo estimado de tokens
    erro            TEXT,
    iniciado_em     TIMESTAMPTZ         NOT NULL DEFAULT NOW(),
    finalizado_em   TIMESTAMPTZ,

    CONSTRAINT exec_log_pkey     PRIMARY KEY (id),
    CONSTRAINT exec_log_fonte_fk FOREIGN KEY (fonte_id)
        REFERENCES mi.fontes(id) ON DELETE SET NULL
);

CREATE INDEX idx_exec_dag_id ON mi.execucoes_log(dag_id);
CREATE INDEX idx_exec_data   ON mi.execucoes_log(iniciado_em DESC);
CREATE INDEX idx_exec_erros  ON mi.execucoes_log(iniciado_em DESC) WHERE status = 'error';

COMMENT ON TABLE mi.execucoes_log IS
    'Histórico de execuções das DAGs Airflow com métricas operacionais e rastreio de erros';

-- =============================================================================
-- VIEWS UTILITÁRIAS
-- =============================================================================

CREATE OR REPLACE VIEW mi.v_artigos_completos AS
    SELECT
        a.id,
        a.url,
        a.titulo,
        a.data_publicacao,
        a.coletado_em,
        f.slug              AS fonte_slug,
        f.nome              AS fonte_nome,
        f.categoria         AS fonte_categoria,
        p.resumo_pt,
        p.categoria,
        p.relevancia_score,
        p.tom,
        p.entidades,
        p.modelo_ia,
        (e.id IS NOT NULL)  AS tem_embedding
    FROM      mi.artigos              a
    JOIN      mi.fontes               f ON f.id = a.fonte_id
    LEFT JOIN mi.artigos_processados  p ON p.artigo_id = a.id
    LEFT JOIN mi.embeddings           e ON e.artigo_id = a.id;

COMMENT ON VIEW mi.v_artigos_completos IS
    'Visão desnormalizada dos artigos com fonte, processamento e flag de embedding — evita JOINs repetidos';

CREATE OR REPLACE VIEW mi.v_saude_coleta AS
    SELECT
        f.slug,
        f.nome,
        f.ativa,
        COUNT(a.id)                                                      AS artigos_total,
        COUNT(a.id) FILTER (WHERE a.coletado_em >= NOW() - INTERVAL '24h') AS artigos_24h,
        MAX(a.coletado_em)                                               AS ultima_coleta,
        MAX(l.iniciado_em) FILTER (WHERE l.status = 'error')            AS ultimo_erro
    FROM      mi.fontes       f
    LEFT JOIN mi.artigos      a ON a.fonte_id = f.id
    LEFT JOIN mi.execucoes_log l ON l.fonte_id = f.id
    GROUP BY  f.id, f.slug, f.nome, f.ativa
    ORDER BY  f.slug;

COMMENT ON VIEW mi.v_saude_coleta IS
    'Dashboard de saúde do pipeline: artigos por fonte nas últimas 24h e último erro registrado';

-- =============================================================================
-- FUNÇÃO: busca semântica (RAG)
-- =============================================================================
CREATE OR REPLACE FUNCTION mi.buscar_similares(
    p_query_vector  VECTOR(1536),
    p_top_k         INTEGER                 DEFAULT 8,
    p_categoria     mi.categoria_artigo     DEFAULT NULL,
    p_score_min     SMALLINT                DEFAULT 4,
    p_dias_max      INTEGER                 DEFAULT 90
)
RETURNS TABLE (
    artigo_id       UUID,
    titulo          TEXT,
    url             TEXT,
    resumo_pt       TEXT,
    categoria       mi.categoria_artigo,
    relevancia      SMALLINT,
    tom             mi.tom_artigo,
    fonte_nome      VARCHAR,
    data_publicacao TIMESTAMPTZ,
    similaridade    DOUBLE PRECISION
)
LANGUAGE SQL STABLE PARALLEL SAFE AS $$
    SELECT
        a.id,
        a.titulo,
        a.url,
        p.resumo_pt,
        p.categoria,
        p.relevancia_score,
        p.tom,
        f.nome,
        a.data_publicacao,
        1.0 - (e.embedding <=> p_query_vector)  AS similaridade
    FROM      mi.embeddings           e
    JOIN      mi.artigos              a ON a.id = e.artigo_id
    JOIN      mi.artigos_processados  p ON p.artigo_id = a.id
    JOIN      mi.fontes               f ON f.id = a.fonte_id
    WHERE
        p.relevancia_score >= p_score_min
        AND a.data_publicacao >= NOW() - (p_dias_max || ' days')::INTERVAL
        AND (p_categoria IS NULL OR p.categoria = p_categoria)
    ORDER BY e.embedding <=> p_query_vector
    LIMIT p_top_k;
$$;

COMMENT ON FUNCTION mi.buscar_similares IS
    'Busca semântica por similaridade coseno via pgvector. Retorna top-k artigos mais próximos do vetor de consulta.';

-- =============================================================================
-- PERMISSÕES
-- =============================================================================
GRANT USAGE  ON SCHEMA mi TO mi_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES    IN SCHEMA mi TO mi_app;
GRANT USAGE  ON ALL SEQUENCES                         IN SCHEMA mi TO mi_app;
GRANT EXECUTE ON ALL FUNCTIONS                        IN SCHEMA mi TO mi_app;

ALTER DEFAULT PRIVILEGES IN SCHEMA mi
    GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES    TO mi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA mi
    GRANT USAGE ON SEQUENCES                          TO mi_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA mi
    GRANT EXECUTE ON FUNCTIONS                        TO mi_app;
