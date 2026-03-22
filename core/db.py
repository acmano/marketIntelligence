"""
Gerenciamento de conexão com o banco market_intelligence.
Usa psycopg2 com pool de conexões e search_path configurado para o schema mi.
"""

import os
from contextlib import contextmanager
from typing import Generator

from typing import Optional

import psycopg2
import psycopg2.pool
from dotenv import load_dotenv
from loguru import logger

load_dotenv()

# Pool de conexões — criado uma vez na inicialização do módulo
_pool: Optional[psycopg2.pool.ThreadedConnectionPool] = None


def _get_pool() -> psycopg2.pool.ThreadedConnectionPool:
    global _pool
    if _pool is None or _pool.closed:
        _pool = psycopg2.pool.ThreadedConnectionPool(
            minconn=1,
            maxconn=10,
            host=os.environ["MI_DB_HOST"],
            port=int(os.getenv("MI_DB_PORT", 5432)),
            dbname=os.environ["MI_DB_NAME"],
            user=os.environ["MI_DB_USER"],
            password=os.environ["MI_DB_PASSWORD"],
            options="-c search_path=mi,public -c client_encoding=UTF8",
        )
        logger.info("Pool de conexões market_intelligence inicializado.")
    return _pool


@contextmanager
def get_conn() -> Generator[psycopg2.extensions.connection, None, None]:
    """
    Context manager que entrega uma conexão do pool e a devolve ao final,
    fazendo rollback automático em caso de exceção.
    """
    pool = _get_pool()
    conn = pool.getconn()
    try:
        conn.set_client_encoding("UTF8")
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        pool.putconn(conn)


def close_pool() -> None:
    """Fecha todas as conexões do pool. Chamar no shutdown da aplicação."""
    global _pool
    if _pool and not _pool.closed:
        _pool.closeall()
        logger.info("Pool de conexões encerrado.")

