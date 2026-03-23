"""
DAG: mi_powerpoint
Descricao: Geracao automatica do relatorio PowerPoint semanal e envio por email.
Disparo: automatico pelo mi_processamento nas segundas-feiras
         Tambem pode ser disparado manualmente pela interface do Airflow.
Compativel com Python 3.8+
"""

import os
import sys
import smtplib
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import List, Dict, Any

from airflow import DAG
from airflow.operators.python import PythonOperator
from dotenv import load_dotenv

MI_ROOT = os.environ.get("MI_PROJECT_ROOT", "/home/mano/projetos/datasul/marketIntelligence")
sys.path.insert(0, MI_ROOT)
load_dotenv(os.path.join(MI_ROOT, ".env"))

DEFAULT_ARGS = {
    "owner": "antonio.mano",
    "depends_on_past": False,
    "retries": 1,
    "retry_delay": timedelta(minutes=30),
    "email_on_failure": True,
    "email": [os.getenv("SMTP_FROM", "ti@lorenzetti.com.br")],
}


def _buscar_artigos(categoria: str, semana_inicio: datetime, score_min: int = 5, limite: int = 5) -> List[Dict]:
    from core.db import get_conn
    semana_fim = semana_inicio + timedelta(days=7)
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT a.id, a.titulo, a.url, p.resumo_pt,
                       f.nome AS fonte_nome, a.data_publicacao
                FROM mi.artigos_processados p
                JOIN mi.artigos a ON a.id = p.artigo_id
                JOIN mi.fontes  f ON f.id = a.fonte_id
                WHERE p.categoria = %s::mi.categoria_artigo
                  AND p.relevancia_score >= %s
                  AND a.coletado_em >= %s
                  AND a.coletado_em <  %s
                ORDER BY p.relevancia_score DESC, a.data_publicacao DESC
                LIMIT %s
            """, (categoria, score_min, semana_inicio, semana_fim, limite))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]


def _gerar_conteudo(artigos: List[Dict], tipo: str) -> str:
    import anthropic
    if not artigos:
        return "Nenhum artigo relevante encontrado nesta categoria para a semana."
    cliente = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    contexto = "\n---\n".join([
        f"Titulo: {a['titulo']}\nFonte: {a['fonte_nome']}\nResumo: {a.get('resumo_pt','')}"
        for a in artigos
    ])
    prompts = {
        "resumo":     f"Escreva um sumario executivo em portugues (max 150 palavras) dos artigos mais importantes para a Lorenzetti S.A.:\n{contexto}",
        "materias":   f"Analise em portugues (max 200 palavras) os impactos nos precos e disponibilidade de PP, ABS e Nylon:\n{contexto}",
        "exportacao": f"Analise em portugues (max 200 palavras) as tendencias nos mercados de exportacao da Lorenzetti:\n{contexto}",
        "geopolitica":f"Analise em portugues (max 150 palavras) os impactos geopoliticos para a Lorenzetti:\n{contexto}",
        "alertas":    f"Liste 3 a 5 alertas em portugues no formato 'ALERTA: [risco] | Acao: [acao]':\n{contexto}",
        "preditivo":  f"Analise preditiva em portugues para as proximas 2-4 semanas para a Lorenzetti:\n{contexto}",
    }
    resp = cliente.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompts[tipo]}],
    )
    return resp.content[0].text


def task_selecionar_artigos(**context):
    from loguru import logger
    exec_date = context.get("execution_date", datetime.utcnow())
    semana_inicio = exec_date - timedelta(days=exec_date.weekday())
    semana_inicio = semana_inicio.replace(hour=0, minute=0, second=0, microsecond=0)
    artigos = {
        "semana_inicio": semana_inicio.isoformat(),
        "materias":   _buscar_artigos("materia-prima",      semana_inicio),
        "exportacao": _buscar_artigos("mercado-exportacao", semana_inicio),
        "geopolitica":_buscar_artigos("geopolitica",        semana_inicio),
    }
    total = sum(len(v) for k, v in artigos.items() if isinstance(v, list))
    logger.info(f"Artigos selecionados: {total}")
    return artigos


def task_gerar_powerpoint(**context):
    from core.gerador_pptx import gerar_powerpoint
    from core.db import get_conn
    from loguru import logger

    ti = context["ti"]
    dados = ti.xcom_pull(task_ids="selecionar_artigos")
    semana_inicio = datetime.fromisoformat(dados["semana_inicio"])
    artigos_mp  = dados["materias"]
    artigos_exp = dados["exportacao"]
    artigos_geo = dados["geopolitica"]
    todos = artigos_mp + artigos_exp + artigos_geo

    logger.info("Gerando conteudo via API Claude...")
    resumo       = _gerar_conteudo(todos,       "resumo")
    analise_mp   = _gerar_conteudo(artigos_mp,  "materias")
    analise_exp  = _gerar_conteudo(artigos_exp, "exportacao")
    analise_geo  = _gerar_conteudo(artigos_geo, "geopolitica")
    alertas      = _gerar_conteudo(todos,       "alertas")
    preditivo    = _gerar_conteudo(todos,       "preditivo")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM mi.fontes WHERE ativa = TRUE ORDER BY nome")
            fontes = [r[0] for r in cur.fetchall()]

    logger.info("Montando PowerPoint...")
    caminho = gerar_powerpoint(
        semana_inicio=semana_inicio,
        resumo_executivo=resumo,
        conteudo_materias=analise_mp,    artigos_materias=artigos_mp,
        conteudo_exportacao=analise_exp, artigos_exportacao=artigos_exp,
        conteudo_geopolitica=analise_geo,artigos_geopolitica=artigos_geo,
        alertas=alertas, analise_preditiva=preditivo, fontes_ativas=fontes,
    )
    logger.info(f"PowerPoint gerado: {caminho}")
    return caminho


def task_enviar_email(**context):
    from loguru import logger
    ti = context["ti"]
    caminho = ti.xcom_pull(task_ids="gerar_powerpoint")
    destinatarios_str = os.getenv("PPTX_RECIPIENTS", "")
    if not destinatarios_str:
        logger.warning("PPTX_RECIPIENTS nao configurado -- email nao enviado.")
        return
    destinatarios = [d.strip() for d in destinatarios_str.split(",") if d.strip()]
    remetente = os.getenv("SMTP_FROM")
    semana = datetime.now().strftime("%d/%m/%Y")
    msg = MIMEMultipart()
    msg["From"]    = remetente
    msg["To"]      = ", ".join(destinatarios)
    msg["Subject"] = f"Market Intelligence -- Relatorio Semanal {semana}"
    msg.attach(MIMEText(
        f"Prezados,\n\nSegue o relatorio semanal de Market Intelligence de {semana}.\n\n"
        f"Atenciosamente,\nSistema Market Intelligence -- TI/Sistemas",
        "plain", "utf-8"
    ))
    with open(caminho, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(caminho))
    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(caminho)}"'
    msg.attach(part)
    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as s:
        s.ehlo(); s.starttls()
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        s.sendmail(remetente, destinatarios, msg.as_string())
    logger.info(f"Email enviado para: {', '.join(destinatarios)}")


with DAG(
    dag_id="mi_powerpoint",
    description="Market Intelligence -- Relatorio PowerPoint semanal automatico",
    schedule=None,             # sem schedule proprio -- disparado pelo mi_processamento
    start_date=datetime(2026, 3, 23),
    catchup=False,
    max_active_runs=1,
    default_args=DEFAULT_ARGS,
    tags=["market-intelligence", "powerpoint", "relatorio"],
) as dag:

    t1 = PythonOperator(task_id="selecionar_artigos", python_callable=task_selecionar_artigos)
    t2 = PythonOperator(task_id="gerar_powerpoint",   python_callable=task_gerar_powerpoint)
    t3 = PythonOperator(task_id="enviar_email",       python_callable=task_enviar_email)

    t1 >> t2 >> t3
