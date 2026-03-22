"""
DAG: mi_coleta
Descrição: Coleta diária de notícias de todas as fontes ativas.
Agendamento: diário às 06h00 BRT (09h UTC)

As fontes são resolvidas dinamicamente do banco — nenhum slug ou ID
está hardcoded aqui. Para adicionar uma nova fonte: cadastre em mi.fontes
e crie o scraper correspondente no mapa SCRAPER_POR_SLUG abaixo.
"""

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scrapers import (
    ReutersScraper, IcisScraper, PlasticsNewsScraper,
    BloombergScraper, FinancialTimesScraper,
    WorldBankScraper, TradeMapScraper,
    AbiplastScraper, AbiquimScraper,
)
from core import get_conn

# -----------------------------------------------------------------------------
# Mapa slug → classe scraper
# Adicionar nova fonte: registrar aqui e criar o scraper em scrapers/
# -----------------------------------------------------------------------------
SCRAPER_POR_SLUG: dict[str, type] = {
    "reuters-commodities":  ReutersScraper,
    "icis":                 IcisScraper,
    "plastics-news":        PlasticsNewsScraper,
    "bloomberg":            BloombergScraper,
    "financial-times":      FinancialTimesScraper,
    "world-bank":           WorldBankScraper,
    "trademap":             TradeMapScraper,
    "abiplast":             AbiplastScraper,
    "abiquim":              AbiquimScraper,
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
    """
    Task callable: instancia o scraper pelo slug e executa a coleta.
    Registra resultado em mi.execucoes_log.
    """
    from datetime import timezone
    from loguru import logger

    if slug not in SCRAPER_POR_SLUG:
        raise ValueError(f"Slug '{slug}' não mapeado em SCRAPER_POR_SLUG.")

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
        # Registra no log independente de sucesso ou falha
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mi.execucoes_log
                        (dag_id, fonte_id, status, qtd_novos, erro, iniciado_em, finalizado_em)
                    SELECT
                        %s,
                        (SELECT id FROM mi.fontes WHERE slug = %s),
                        %s::mi.status_execucao,
                        %s,
                        %s,
                        %s,
                        NOW()
                    """,
                    ("mi_coleta", slug, status, novos, erro, inicio),
                )
            conn.commit()

    return {"slug": slug, "novos": novos, "status": status}


def carregar_fontes_ativas() -> list[str]:
    """
    Retorna slugs das fontes ativas no banco que possuem scraper mapeado.
    Nunca hardcoded — sempre lido do banco em runtime.
    """
    from core.fontes_repo import listar_ativas
    ativas = listar_ativas()
    return [f.slug for f in ativas if f.slug in SCRAPER_POR_SLUG]


# -----------------------------------------------------------------------------
# Definição da DAG
# As tasks são criadas dinamicamente com base nas fontes ativas no banco.
# -----------------------------------------------------------------------------
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

    slugs_ativos = carregar_fontes_ativas()

    for slug in slugs_ativos:
        PythonOperator(
            task_id=f"coletar_{slug.replace('-', '_')}",
            python_callable=executar_coleta,
            op_kwargs={"slug": slug},
            pool="mi_scrapers",   # pool com 3 slots — criar no Airflow Admin
        )
