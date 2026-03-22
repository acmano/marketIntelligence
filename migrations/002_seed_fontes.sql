-- =============================================================================
-- Migration 002 — Seed das 9 fontes iniciais
-- Projeto: Market Intelligence — Assessoria à Alta Direção
--
-- EXECUTAR APÓS 001_create_schema.sql:
--   psql -U postgres -d market_intelligence -f migrations/002_seed_fontes.sql
--
-- O campo 'slug' é o identificador estável usado pelo código Python para
-- resolver o UUID da fonte em runtime — nenhum ID é hardcoded na aplicação.
-- =============================================================================

INSERT INTO mi.fontes (nome, slug, url_base, url_rss, tipo, categoria, ativa) VALUES

-- ── Fase 1: fontes prioritárias ───────────────────────────────────────────────
('Reuters Commodities',
 'reuters-commodities',
 'https://www.reuters.com/business/commodities',
 'https://feeds.reuters.com/reuters/businessNews',
 'rss', 'petroquimica', TRUE),

('ICIS',
 'icis',
 'https://www.icis.com/explore/resources/news',
 'https://www.icis.com/explore/resources/news/feed',
 'rss', 'petroquimica', TRUE),

('Plastics News',
 'plastics-news',
 'https://www.plasticsnews.com',
 'https://www.plasticsnews.com/rss',
 'rss', 'industria_plastica', TRUE),

('World Bank Open Data',
 'world-bank',
 'https://data.worldbank.org',
 NULL,
 'api', 'economia_global', TRUE),

('ITC Trade Map',
 'trademap',
 'https://www.trademap.org',
 NULL,
 'scraping', 'comercio_exterior', TRUE),

-- ── Fase 2: fontes secundárias ────────────────────────────────────────────────
('Bloomberg Markets',
 'bloomberg',
 'https://www.bloomberg.com/markets',
 'https://feeds.bloomberg.com/markets/news.rss',
 'rss', 'economia_global', TRUE),

('Financial Times',
 'financial-times',
 'https://www.ft.com',
 'https://www.ft.com/rss/home',
 'rss', 'geopolitica', TRUE),

('ABIPLAST',
 'abiplast',
 'https://abiplast.org.br',
 NULL,
 'scraping', 'setor_nacional', TRUE),

('ABIQUIM',
 'abiquim',
 'https://www.abiquim.org.br',
 NULL,
 'scraping', 'setor_nacional', TRUE)

ON CONFLICT (slug) DO UPDATE SET
    nome      = EXCLUDED.nome,
    url_base  = EXCLUDED.url_base,
    url_rss   = EXCLUDED.url_rss,
    tipo      = EXCLUDED.tipo,
    categoria = EXCLUDED.categoria;
    -- ativa não é atualizado: permite desativar uma fonte sem o seed reverter

-- Verificação
SELECT slug, nome, tipo, categoria, ativa FROM mi.fontes ORDER BY slug;
