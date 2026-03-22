"""
DAG: mi_coleta
Descrição: Coleta diária de notícias de todas as fontes ativas.
Agendamento: diário às 06h00 (horário de Brasília / America/Sao_Paulo)
"""

import sys
import os
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.utils.email import send_email

# Adiciona o diretório do projeto ao path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from scrapers.reuters import ReutersScraper
from scrapers.icis import IcisScraper
from scrapers.rss_scrapers import PlasticsNewsScraper, BloombergScraper, FinancialTimesScraper
from scrapers.api_scrapers import WorldBankScraper, TradeMapScraper, AbiplastScraper, AbiquimScraper

# ─────────────────────────────────────────────────────────────────────────────
# Configurações padrão
# ─────────────────────────────────────────────────────────────────────────────
DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}

# ─────────────────────────────────────────────────────────────────────────────
# Mapa de scrapers ativos
# ─────────────────────────────────────────────────────────────────────────────
SCRAPERS = {
    "reuters":        ReutersScraper,
    "icis":           IcisScraper,
    "plastics_news":  PlasticsNewsScraper,
    "world_bank":     WorldBankScraper,
    "trademap":       TradeMapScraper,
    "bloomberg":      BloombergScraper,
    "financial_times": FinancialTimesScraper,
    "abiplast":       AbiplastScraper,
    "abiquim":        AbiquimScraper,
}


def executar_scraper(fonte_key: str, **context) -> dict:
    """Task callable: instancia e executa o scraper de uma fonte."""
    import psycopg2
    from loguru import logger

    scraper_cls = SCRAPERS[fonte_key]
    scraper = scraper_cls()

    inicio = datetime.utcnow()
    try:
        novos = scraper.executar()
        status = "success"
        erro = None
    except Exception as e:
        novos = 0
        status = "error"
        erro = str(e)
        logger.error(f"[{fonte_key}] Falha na coleta: {e}")
        raise

    # Registra no log
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST"), port=os.getenv("DB_PORT"),
        dbname=os.getenv("DB_NAME"), user=os.getenv("DB_USER"),
        password=os.getenv("DB_PASSWORD"),
    )
    with conn.cursor() as cur:
        cur.execute(
            """
            INSERT INTO mi_coletas_log
                (dag_id, fonte_id, status, qtd_novos, mensagem_erro, iniciado_em, finalizado_em)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            """,
            ("mi_coleta", scraper.fonte_id, status, novos, erro, inicio, datetime.utcnow()),
        )
        conn.commit()
    conn.close()

    return {"fonte": fonte_key, "novos": novos, "status": status}


# ─────────────────────────────────────────────────────────────────────────────
# Definição da DAG
# ─────────────────────────────────────────────────────────────────────────────
with DAG(
    dag_id="mi_coleta",
    description="Market Intelligence — Coleta diária de notícias",
    schedule_interval="0 9 * * *",   # 06h BRT = 09h UTC
    start_date=datetime(2026, 3, 23),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "coleta"],
) as dag:

    tarefas = {}
    for fonte_key in SCRAPERS:
        tarefas[fonte_key] = PythonOperator(
            task_id=f"coletar_{fonte_key}",
            python_callable=executar_scraper,
            op_kwargs={"fonte_key": fonte_key},
            pool="mi_scrapers",   # criar pool no Airflow com 3 slots para controle de paralelismo
        )
