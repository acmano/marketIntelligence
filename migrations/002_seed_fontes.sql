-- ─────────────────────────────────────────────────────────────────────────────
-- Migration 002 — Seed das 9 fontes iniciais
-- Projeto: Market Intelligence — Assessoria à Alta Direção
-- Executar APÓS 001_create_schema.sql
-- ─────────────────────────────────────────────────────────────────────────────

INSERT INTO mi_fontes (nome, url_base, url_rss, tipo, categoria, ativa) VALUES

-- Fase 1: fontes prioritárias
('Reuters Commodities',
 'https://www.reuters.com/business/commodities',
 'https://feeds.reuters.com/reuters/businessNews',
 'rss', 'petroquimica', TRUE),

('ICIS',
 'https://www.icis.com/explore/resources/news',
 'https://www.icis.com/explore/resources/news/feed',
 'rss', 'petroquimica', TRUE),

('Plastics News',
 'https://www.plasticsnews.com',
 'https://www.plasticsnews.com/rss',
 'rss', 'industria_plastica', TRUE),

('World Bank Open Data',
 'https://data.worldbank.org',
 NULL,
 'api', 'economia_global', TRUE),

('ITC Trade Map',
 'https://www.trademap.org',
 NULL,
 'scraping', 'comercio_exterior', TRUE),

-- Fase 2: fontes secundárias
('Bloomberg Markets',
 'https://www.bloomberg.com/markets',
 'https://feeds.bloomberg.com/markets/news.rss',
 'rss', 'economia_global', TRUE),

('Financial Times',
 'https://www.ft.com',
 'https://www.ft.com/rss/home',
 'rss', 'geopolitica', TRUE),

('ABIPLAST',
 'https://abiplast.org.br',
 NULL,
 'scraping', 'setor_nacional', TRUE),

('ABIQUIM',
 'https://www.abiquim.org.br',
 NULL,
 'scraping', 'setor_nacional', TRUE)

ON CONFLICT DO NOTHING;
