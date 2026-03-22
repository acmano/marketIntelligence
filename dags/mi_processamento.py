"""
DAG: mi_processamento
Descrição: Enriquecimento dos artigos coletados via API Claude (classificação,
           resumo, extração de entidades, score de relevância) e geração de
           embeddings vetoriais via OpenAI.
Agendamento: diário às 07h00 BRT (após mi_coleta)
Implementação completa: MKI-6 e MKI-7
"""

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "retries": 2,
    "retry_delay": timedelta(minutes=10),
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}


def classificar_e_resumir(**context):
    """
    TODO (MKI-6): Para cada artigo não processado:
    1. Chamar API Claude com prompt de classificação + resumo + entidades
    2. Salvar resultado em mi_artigos_processados
    """
    raise NotImplementedError("Implementar na MKI-6")


def gerar_embeddings(**context):
    """
    TODO (MKI-7): Para cada artigo processado com score >= MIN_RELEVANCE_SCORE:
    1. Chamar OpenAI text-embedding-3-small com (titulo + resumo_pt)
    2. Salvar vetor em mi_embeddings
    """
    raise NotImplementedError("Implementar na MKI-7")


with DAG(
    dag_id="mi_processamento",
    description="Market Intelligence — Processamento e enriquecimento por IA",
    schedule_interval="0 10 * * *",   # 07h BRT = 10h UTC
    start_date=datetime(2026, 3, 23),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "ia", "embeddings"],
) as dag:

    t1 = PythonOperator(
        task_id="classificar_e_resumir",
        python_callable=classificar_e_resumir,
    )

    t2 = PythonOperator(
        task_id="gerar_embeddings",
        python_callable=gerar_embeddings,
    )

    t1 >> t2
