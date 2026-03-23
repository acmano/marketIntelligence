-- =============================================================================
-- Migration 003 -- Adiciona campos de autenticacao HTTP em mi.fontes
--
-- Algumas fontes RSS exigem HTTP Basic Auth. Estes campos sao opcionais
-- e usados pelo scraper ao fazer GET no feed.
--
-- EXECUTAR:
--   psql -U postgres -d market_intelligence -f migrations/003_add_auth_fontes.sql
--
-- Idempotente: seguro para re-execucao.
-- =============================================================================

ALTER TABLE mi.fontes ADD COLUMN IF NOT EXISTS rss_usuario VARCHAR(100);
ALTER TABLE mi.fontes ADD COLUMN IF NOT EXISTS rss_senha   VARCHAR(200);

COMMENT ON COLUMN mi.fontes.rss_usuario IS 'Usuario para HTTP Basic Auth no feed RSS (opcional)';
COMMENT ON COLUMN mi.fontes.rss_senha   IS 'Senha para HTTP Basic Auth no feed RSS (opcional)';
