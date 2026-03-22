"""
DAG: mi_powerpoint
Descrição: Geração automática do relatório PowerPoint semanal e envio por e-mail.
Agendamento: toda segunda-feira às 07h00 BRT
Implementação completa: MKI-10 e MKI-11
"""

import os
import sys
from datetime import datetime, timedelta

from airflow import DAG
from airflow.operators.python import PythonOperator

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "retries": 1,
    "retry_delay": timedelta(minutes=30),
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}


def selecionar_artigos_semana(**context):
    """
    TODO (MKI-11): Busca os top artigos da semana por categoria
    com relevancia_score >= MIN_PPTX_SCORE (padrão: 7).
    """
    raise NotImplementedError("Implementar na MKI-11")


def gerar_conteudo_ia(**context):
    """
    TODO (MKI-11): Chama API Claude para:
    - Resumo executivo da semana
    - Curadoria por categoria (matéria-prima, exportação, geopolítica)
    - Alertas e riscos identificados
    - Análise preditiva (o que monitorar na próxima semana)
    """
    raise NotImplementedError("Implementar na MKI-11")


def montar_powerpoint(**context):
    """
    TODO (MKI-10 + MKI-11): Preenche o template python-pptx com o conteúdo
    gerado e salva em /tmp/mi_relatorio_YYYY-MM-DD.pptx
    """
    raise NotImplementedError("Implementar na MKI-10 e MKI-11")


def enviar_email(**context):
    """
    TODO (MKI-11): Envia o arquivo .pptx para a lista PPTX_RECIPIENTS via SMTP.
    """
    raise NotImplementedError("Implementar na MKI-11")


with DAG(
    dag_id="mi_powerpoint",
    description="Market Intelligence — Geração e envio do PowerPoint semanal",
    schedule_interval="0 10 * * 1",   # toda segunda-feira às 07h BRT = 10h UTC
    start_date=datetime(2026, 3, 23),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "powerpoint", "relatorio"],
) as dag:

    t1 = PythonOperator(task_id="selecionar_artigos_semana", python_callable=selecionar_artigos_semana)
    t2 = PythonOperator(task_id="gerar_conteudo_ia",         python_callable=gerar_conteudo_ia)
    t3 = PythonOperator(task_id="montar_powerpoint",         python_callable=montar_powerpoint)
    t4 = PythonOperator(task_id="enviar_email",              python_callable=enviar_email)

    t1 >> t2 >> t3 >> t4
