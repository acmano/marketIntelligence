"""
DAG: mi_coleta
Descricao: Coleta diaria de noticias de todas as fontes ativas.
Agendamento: diario as 06h00 BRT (09h UTC)
Ao terminar com sucesso, dispara automaticamente mi_processamento.
Compativel com Python 3.8+
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Type

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from dotenv import load_dotenv

MI_ROOT = os.environ.get("MI_PROJECT_ROOT", "/home/mano/projetos/datasul/marketIntelligence")
sys.path.insert(0, MI_ROOT)
load_dotenv(os.path.join(MI_ROOT, ".env"))

from scrapers import (
    ReutersScraper, IcisScraper, PlasticsNewsScraper,
    BloombergScraper, FinancialTimesScraper,
    WorldBankScraper, TradeMapScraper,
    AbiplastScraper, AbiquimScraper,
)
from scrapers.base_scraper import BaseScraper
from core import get_conn

SCRAPER_POR_SLUG: Dict[str, Type[BaseScraper]] = {
    "reuters-commodities": ReutersScraper,
    "icis":                IcisScraper,
    "plastics-news":       PlasticsNewsScraper,
    "bloomberg":           BloombergScraper,
    "financial-times":     FinancialTimesScraper,
    "world-bank":          WorldBankScraper,
    "trademap":            TradeMapScraper,
    "abiplast":            AbiplastScraper,
    "abiquim":             AbiquimScraper,
}

DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}


def executar_coleta(slug: str, **context) -> dict:
    from loguru import logger
    if slug not in SCRAPER_POR_SLUG:
        raise ValueError(f"Slug '{slug}' nao mapeado em SCRAPER_POR_SLUG.")
    scraper = SCRAPER_POR_SLUG[slug]()
    inicio = datetime.now(tz=timezone.utc)
    status, novos, erro = "success", 0, None
    try:
        novos = scraper.executar()
    except Exception as exc:
        status = "error"
        erro = str(exc)
        logger.error(f"[{slug}] Falha na coleta: {exc}")
        raise
    finally:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mi.execucoes_log
                        (dag_id, fonte_id, status, qtd_novos, erro, iniciado_em, finalizado_em)
                    SELECT %s,
                           (SELECT id FROM mi.fontes WHERE slug = %s),
                           %s::mi.status_execucao,
                           %s, %s, %s, NOW()
                    """,
                    ("mi_coleta", slug, status, novos, erro, inicio),
                )
            conn.commit()
    return {"slug": slug, "novos": novos, "status": status}


def carregar_fontes_ativas() -> List[str]:
    from core.fontes_repo import listar_ativas
    ativas = listar_ativas()
    return [f.slug for f in ativas if f.slug in SCRAPER_POR_SLUG]


with DAG(
    dag_id="mi_coleta",
    description="Market Intelligence -- Coleta diaria de noticias",
    schedule="0 9 * * *",
    start_date=datetime(2026, 3, 23),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "coleta"],
) as dag:

    slugs_ativos = carregar_fontes_ativas()

    tasks_coleta = []
    for slug in slugs_ativos:
        t = PythonOperator(
            task_id=f"coletar_{slug.replace('-', '_')}",
            python_callable=executar_coleta,
            op_kwargs={"slug": slug},
        )
        tasks_coleta.append(t)

    # Dispara mi_processamento apos todas as coletas terminarem com sucesso
    trigger_processamento = TriggerDagRunOperator(
        task_id="disparar_processamento",
        trigger_dag_id="mi_processamento",
        wait_for_completion=False,
    )

    # Todas as tasks de coleta >> trigger
    if tasks_coleta:
        tasks_coleta >> trigger_processamento
