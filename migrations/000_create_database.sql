-- =============================================================================
-- Migration 000 — Criação do banco de dados e schema dedicados
-- Projeto: Market Intelligence — Assessoria à Alta Direção
--
-- EXECUTAR CONECTADO AO BANCO 'postgres' (superuser):
--   psql -U postgres -f migrations/000_create_database.sql
--
-- Este script é idempotente: seguro para re-execução.
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. Banco de dados dedicado
-- -----------------------------------------------------------------------------
SELECT 'CREATE DATABASE market_intelligence
    ENCODING    = ''UTF8''
    LC_COLLATE  = ''pt_BR.UTF-8''
    LC_CTYPE    = ''pt_BR.UTF-8''
    TEMPLATE    = template0
    CONNECTION LIMIT = 100'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'market_intelligence'
)\gexec

-- Comentário no banco
COMMENT ON DATABASE market_intelligence IS
    'Banco dedicado ao sistema Market Intelligence — Lorenzetti S.A.';

-- -----------------------------------------------------------------------------
-- 2. Role de aplicação (sem permissão de superuser)
-- -----------------------------------------------------------------------------
DO $$
BEGIN
    IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'mi_app') THEN
        CREATE ROLE mi_app
            LOGIN
            NOSUPERUSER
            NOCREATEDB
            NOCREATEROLE
            NOINHERIT
            CONNECTION LIMIT 20;
        RAISE NOTICE 'Role mi_app criada. Defina a senha com: ALTER ROLE mi_app PASSWORD ''<senha>'';';
    ELSE
        RAISE NOTICE 'Role mi_app já existe, pulando criação.';
    END IF;
END;
$$;

-- -----------------------------------------------------------------------------
-- PRÓXIMO PASSO:
-- Conecte ao banco market_intelligence e execute 001_create_schema.sql
--   psql -U postgres -d market_intelligence -f migrations/001_create_schema.sql
-- -----------------------------------------------------------------------------
