# Runbook Operacional — Market Intelligence

> Guia para operação, diagnóstico e manutenção do sistema.

---

## Verificação de Saúde

### DAGs Airflow
```bash
# Ver status das últimas execuções
airflow dags list-runs -d mi_coleta --limit 5
airflow dags list-runs -d mi_processamento --limit 5
airflow dags list-runs -d mi_powerpoint --limit 5
```

### Artigos coletados hoje
```sql
SELECT f.nome, COUNT(*) as artigos_hoje
FROM mi_artigos a
JOIN mi_fontes f ON f.id = a.fonte_id
WHERE a.data_coleta >= CURRENT_DATE
GROUP BY f.nome
ORDER BY artigos_hoje DESC;
```

### Fontes com falha nas últimas 24h
```sql
SELECT fonte_id, COUNT(*) as falhas, MAX(iniciado_em) as ultima_falha
FROM mi_coletas_log
WHERE status = 'error' AND iniciado_em >= NOW() - INTERVAL '24 hours'
GROUP BY fonte_id;
```

### Custo acumulado de tokens no mês
```sql
SELECT
    ROUND(SUM(custo_tokens_usd)::numeric, 4) AS custo_total_usd,
    COUNT(*) AS execucoes
FROM mi_coletas_log
WHERE iniciado_em >= DATE_TRUNC('month', NOW());
```

---

## Procedimentos Comuns

### Reprocessar artigos de uma fonte específica
```sql
-- Marca artigos da fonte como não processados para reprocessamento
UPDATE mi_artigos
SET processado = FALSE
WHERE fonte_id = <fonte_id>
  AND data_coleta >= CURRENT_DATE - INTERVAL '7 days';
```

### Adicionar nova fonte
1. Inserir em `mi_fontes`:
```sql
INSERT INTO mi_fontes (nome, url_base, url_rss, tipo, categoria)
VALUES ('Nome da Fonte', 'https://...', 'https://.../rss', 'rss', 'petroquimica');
```
2. Criar scraper em `scrapers/nova_fonte.py` herdando `BaseScraper`
3. Adicionar ao mapa `SCRAPERS` em `dags/mi_coleta.py`
4. Reiniciar o Airflow scheduler

### Desativar fonte temporariamente
```sql
UPDATE mi_fontes SET ativa = FALSE WHERE id = <fonte_id>;
```

### Forçar re-execução da DAG de coleta
```bash
airflow dags trigger mi_coleta
```

---

## Recuperação de Falhas

### PowerPoint não foi enviado na segunda-feira
```bash
# Executar manualmente
airflow dags trigger mi_powerpoint --run-id manual_$(date +%Y%m%d)
```

### Banco de dados com muitos artigos não processados
```bash
# Verificar fila
psql -c "SELECT COUNT(*) FROM mi_artigos WHERE processado = FALSE;"

# Forçar processamento imediato
airflow dags trigger mi_processamento
```

### Extensão pgvector não está respondendo
```sql
-- Verificar se extensão está ativa
SELECT * FROM pg_extension WHERE extname = 'vector';

-- Recriar índice HNSW se necessário
REINDEX INDEX idx_mi_embeddings_hnsw;
```

---

## Rotação de Chaves de API

### Anthropic (Claude)
1. Acesse https://console.anthropic.com → API Keys
2. Crie nova chave
3. Atualize `ANTHROPIC_API_KEY` no `.env` do servidor
4. Reinicie os workers do Airflow: `systemctl restart airflow-worker`
5. Revogue a chave antiga no console

### OpenAI (Embeddings)
1. Acesse https://platform.openai.com → API Keys
2. Mesmo processo acima para `OPENAI_API_KEY`
