"""Script para testar geracao e envio do PowerPoint sem o Airflow."""

import os, sys, smtplib
from datetime import datetime, timedelta
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
load_dotenv()

from core.db import get_conn
from core.gerador_pptx import gerar_powerpoint
import anthropic

def buscar_artigos(categoria, semana_inicio, score_min=5, limite=5):
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
                ORDER BY p.relevancia_score DESC, a.data_publicacao DESC
                LIMIT %s
            """, (categoria, score_min, limite))
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]

def gerar_conteudo(artigos, tipo):
    if not artigos:
        return "Nenhum artigo relevante encontrado nesta categoria."
    cliente = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    contexto = "\n---\n".join([
        f"Titulo: {a['titulo']}\nFonte: {a['fonte_nome']}\nResumo: {a.get('resumo_pt','')}"
        for a in artigos
    ])
    prompts = {
        "resumo": f"Escreva um sumario executivo em portugues (max 150 palavras) dos artigos mais importantes para a Lorenzetti S.A.:\n{contexto}",
        "materias": f"Analise em portugues (max 200 palavras) os impactos nos precos e disponibilidade de PP, ABS e Nylon:\n{contexto}",
        "exportacao": f"Analise em portugues (max 200 palavras) as tendencias nos mercados de exportacao da Lorenzetti:\n{contexto}",
        "geopolitica": f"Analise em portugues (max 150 palavras) os impactos geopoliticos para a Lorenzetti:\n{contexto}",
        "alertas": f"Liste 3 a 5 alertas em portugues no formato 'ALERTA: [risco] | Acao: [acao]':\n{contexto}",
        "preditivo": f"Analise preditiva em portugues para as proximas 2-4 semanas para a Lorenzetti:\n{contexto}",
    }
    resp = cliente.messages.create(
        model=os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5"),
        max_tokens=1024,
        messages=[{"role": "user", "content": prompts[tipo]}],
    )
    return resp.content[0].text

def enviar_email(caminho):
    destinatarios = [d.strip() for d in os.getenv("PPTX_RECIPIENTS","").split(",") if d.strip()]
    if not destinatarios:
        print("PPTX_RECIPIENTS nao configurado — pulando envio.")
        return
    remetente = os.getenv("SMTP_FROM")
    msg = MIMEMultipart()
    msg["From"] = remetente
    msg["To"] = ", ".join(destinatarios)
    msg["Subject"] = f"Market Intelligence — Relatorio {datetime.now().strftime('%d/%m/%Y')}"
    msg.attach(MIMEText("Segue o relatorio semanal de Market Intelligence.", "plain", "utf-8"))
    with open(caminho, "rb") as f:
        part = MIMEApplication(f.read(), Name=os.path.basename(caminho))
    part["Content-Disposition"] = f'attachment; filename="{os.path.basename(caminho)}"'
    msg.attach(part)
    with smtplib.SMTP(os.getenv("SMTP_HOST"), int(os.getenv("SMTP_PORT", 587))) as s:
        s.ehlo(); s.starttls()
        s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASSWORD"))
        s.sendmail(remetente, destinatarios, msg.as_string())
    print(f"Email enviado para: {', '.join(destinatarios)}")

if __name__ == "__main__":
    semana_inicio = datetime.now() - timedelta(days=7)
    print("1. Buscando artigos...")
    artigos_mp  = buscar_artigos("materia-prima",       semana_inicio)
    artigos_exp = buscar_artigos("mercado-exportacao",  semana_inicio)
    artigos_geo = buscar_artigos("geopolitica",         semana_inicio)
    todos = artigos_mp + artigos_exp + artigos_geo
    print(f"   {len(todos)} artigos encontrados.")

    print("2. Gerando conteudo via Claude...")
    resumo      = gerar_conteudo(todos,       "resumo")
    analise_mp  = gerar_conteudo(artigos_mp,  "materias")
    analise_exp = gerar_conteudo(artigos_exp, "exportacao")
    analise_geo = gerar_conteudo(artigos_geo, "geopolitica")
    alertas     = gerar_conteudo(todos,       "alertas")
    preditivo   = gerar_conteudo(todos,       "preditivo")

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT nome FROM mi.fontes WHERE ativa = TRUE ORDER BY nome")
            fontes = [r[0] for r in cur.fetchall()]

    print("3. Gerando PowerPoint...")
    caminho = gerar_powerpoint(
        semana_inicio=semana_inicio,
        resumo_executivo=resumo,
        conteudo_materias=analise_mp,   artigos_materias=artigos_mp,
        conteudo_exportacao=analise_exp, artigos_exportacao=artigos_exp,
        conteudo_geopolitica=analise_geo, artigos_geopolitica=artigos_geo,
        alertas=alertas, analise_preditiva=preditivo, fontes_ativas=fontes,
    )
    print(f"   Arquivo: {caminho}")

    print("4. Enviando email...")
    enviar_email(caminho)
    print("Concluido!")
