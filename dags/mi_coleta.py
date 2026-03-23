"""
DAG: mi_coleta
Descricao: Coleta diaria de noticias de todas as fontes ativas.
Agendamento: diario as 06h00 BRT (09h UTC)
Ao terminar com sucesso, dispara automaticamente mi_processamento.

Fontes com tipo='rss' sao coletadas automaticamente pelo RssGenericScraper.
Fontes com tipo='api' ou 'scraping' usam scrapers customizados registrados
em SCRAPER_CUSTOMIZADO. Novas fontes RSS podem ser adicionadas via INSERT
no banco sem alterar este codigo.

Compativel com Python 3.8+
"""

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Type

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from dotenv import load_dotenv

MI_ROOT = os.environ.get("MI_PROJECT_ROOT", "/home/mano/projetos/datasul/marketIntelligence")
sys.path.insert(0, MI_ROOT)
load_dotenv(os.path.join(MI_ROOT, ".env"))

from scrapers.base_scraper import BaseScraper
from scrapers.rss_scrapers import RssGenericScraper
from scrapers.api_scrapers import WorldBankScraper, TradeMapScraper

from core import get_conn

# ---------------------------------------------------------------------------
# Scrapers customizados: apenas fontes que NAO podem usar RssGenericScraper.
# Fontes com tipo='rss' sao coletadas automaticamente — nao precisam estar aqui.
# ---------------------------------------------------------------------------
SCRAPER_CUSTOMIZADO = {
    "world-bank": WorldBankScraper,
    "trademap":   TradeMapScraper,
}  # type: Dict[str, Type[BaseScraper]]

DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "depends_on_past": False,
    "retries": 3,
    "retry_delay": timedelta(minutes=5),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}


def _criar_scraper(slug, tipo):
    # type: (str, str) -> BaseScraper
    """
    Factory: retorna o scraper adequado para a fonte.
    1. Se ha scraper customizado registrado, usa ele.
    2. Se tipo='rss', usa RssGenericScraper.
    3. Senao, erro (fonte sem implementacao).
    """
    if slug in SCRAPER_CUSTOMIZADO:
        return SCRAPER_CUSTOMIZADO[slug]()

    if tipo == "rss":
        return RssGenericScraper(slug)

    raise ValueError(
        "Fonte '%s' (tipo='%s') nao tem scraper customizado registrado "
        "e nao e RSS. Adicione uma entrada em SCRAPER_CUSTOMIZADO." % (slug, tipo)
    )


def executar_coleta(slug, tipo, **context):
    # type: (str, str, ...) -> dict
    from loguru import logger

    scraper = _criar_scraper(slug, tipo)
    inicio = datetime.now(tz=timezone.utc)
    status, novos, erro = "success", 0, None  # type: str, int, Optional[str]
    try:
        novos = scraper.executar()
    except Exception as exc:
        status = "error"
        erro = str(exc)
        logger.error("[%s] Falha na coleta: %s", slug, exc)
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


def carregar_fontes_ativas():
    # type: () -> List[dict]
    """
    Retorna lista de fontes ativas que possuem scraper disponivel:
    - tipo='rss' com url_rss preenchida -> RssGenericScraper
    - slug registrado em SCRAPER_CUSTOMIZADO -> scraper customizado
    """
    from core.fontes_repo import listar_ativas
    from loguru import logger

    fontes = []
    for f in listar_ativas():
        if f.slug in SCRAPER_CUSTOMIZADO:
            fontes.append({"slug": f.slug, "tipo": f.tipo})
        elif f.tipo == "rss" and f.url_rss:
            fontes.append({"slug": f.slug, "tipo": f.tipo})
        elif f.tipo == "rss" and not f.url_rss:
            logger.warning(
                "[%s] Fonte RSS ativa mas sem url_rss. Pulando.", f.slug
            )
        else:
            logger.debug(
                "[%s] tipo='%s' sem scraper customizado. Pulando.", f.slug, f.tipo
            )
    return fontes


with DAG(
    dag_id="mi_coleta",
    description="Market Intelligence -- Coleta diaria de noticias",
    schedule="0 9 * * *",
    start_date=datetime(2026, 3, 22),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "coleta"],
) as dag:

    fontes_ativas = carregar_fontes_ativas()

    tasks_coleta = []
    for fonte in fontes_ativas:
        t = PythonOperator(
            task_id="coletar_%s" % fonte["slug"].replace("-", "_"),
            python_callable=executar_coleta,
            op_kwargs={"slug": fonte["slug"], "tipo": fonte["tipo"]},
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
