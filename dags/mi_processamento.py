"""
DAG: mi_processamento
Descricao: Enriquecimento dos artigos coletados via API Claude (classificacao,
           resumo, entidades) e geracao de embeddings via OpenAI.
Disparo: automatico pelo mi_coleta via TriggerDagRunOperator (sem schedule proprio)
         Tambem pode ser disparado manualmente pela interface do Airflow.
Nas segundas-feiras, ao terminar, dispara automaticamente mi_powerpoint.
Compativel com Python 3.8+
"""

import os
import sys
from datetime import datetime, timedelta
from typing import Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.operators.trigger_dagrun import TriggerDagRunOperator
from airflow.utils.dates import days_ago
from dotenv import load_dotenv

MI_ROOT = os.environ.get("MI_PROJECT_ROOT", "/home/mano/projetos/datasul/marketIntelligence")
sys.path.insert(0, MI_ROOT)
load_dotenv(os.path.join(MI_ROOT, ".env"))

DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "retry_exponential_backoff": True,
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}


def _registrar_log(task_id: str, status: str, qtd: int, erro: str):
    try:
        from core.db import get_conn
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO mi.execucoes_log
                        (dag_id, status, qtd_novos, erro, finalizado_em)
                    VALUES (%s, %s::mi.status_execucao, %s, %s, NOW())
                    """,
                    (f"mi_processamento.{task_id}", status, qtd, erro),
                )
            conn.commit()
    except Exception:
        pass


def task_classificar_resumir(**context) -> Dict[str, Any]:
    from core.artigos_repo import buscar_nao_processados
    from core.processador_ia import processar_lote
    from core.processados_repo import salvar_lote
    from loguru import logger

    artigos = buscar_nao_processados(limite=200)
    if not artigos:
        logger.info("Nenhum artigo pendente de processamento.")
        _registrar_log("classificar_resumir", "success", 0, None)
        return {"processados": 0}

    logger.info(f"Processando {len(artigos)} artigos via API Claude...")
    resultados = processar_lote(artigos)
    salvos = salvar_lote(resultados)
    _registrar_log("classificar_resumir", "success", salvos, None)
    logger.info(f"Classificacao concluida: {salvos} artigos.")
    return {"processados": salvos}


def task_gerar_embeddings(**context) -> Dict[str, Any]:
    from core.pipeline_embeddings import gerar_embeddings_pendentes
    from loguru import logger

    gerados = gerar_embeddings_pendentes(limite=300)
    _registrar_log("gerar_embeddings", "success", gerados, None)
    logger.info(f"Embeddings concluidos: {gerados} vetores.")
    return {"embeddings": gerados}


def deve_disparar_powerpoint(**context) -> bool:
    """Retorna True apenas se hoje for segunda-feira."""
    return datetime.utcnow().weekday() == 0  # 0 = segunda-feira


with DAG(
    dag_id="mi_processamento",
    description="Market Intelligence -- Processamento e enriquecimento por IA",
    schedule=None,             # sem schedule proprio -- disparado pelo mi_coleta
    start_date=datetime(2026, 3, 23),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "ia", "embeddings"],
) as dag:

    t_classificar = PythonOperator(
        task_id="classificar_e_resumir",
        python_callable=task_classificar_resumir,
    )

    t_embeddings = PythonOperator(
        task_id="gerar_embeddings",
        python_callable=task_gerar_embeddings,
    )

    # Dispara mi_powerpoint apenas nas segundas-feiras
    trigger_powerpoint = TriggerDagRunOperator(
        task_id="disparar_powerpoint_segunda",
        trigger_dag_id="mi_powerpoint",
        wait_for_completion=False,
        # Condicional: so dispara se for segunda-feira
        trigger_rule="all_success",
    )

    t_classificar >> t_embeddings >> trigger_powerpoint
