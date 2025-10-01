"""
Helper para operaciones de base de datos no bloqueantes
Maneja psycopg2 síncrono en contexto async con anyio
"""

import os
import anyio
import psycopg2
from psycopg2.extras import RealDictCursor
from psycopg2 import errors
import logging

logger = logging.getLogger(__name__)

DB_URL = os.getenv("DATABASE_URL")

def _with_conn(fn):
    """Decorator para funciones que necesitan conexión DB"""
    def wrapper(*args, **kwargs):
        with psycopg2.connect(DB_URL) as conn:
            return fn(conn, *args, **kwargs)
    return wrapper

async def run_db(fn, *args, **kwargs):
    """Ejecuta función síncrona en thread separado para no bloquear event loop"""
    return await anyio.to_thread.run_sync(fn, *args, **kwargs)

@_with_conn
def exec_with_ws(conn, workspace_id: str, sql: str, params=(), dict_cursor=False):
    """Ejecuta query con contexto RLS de workspace"""
    cur_factory = RealDictCursor if dict_cursor else None
    with conn.cursor(cursor_factory=cur_factory) as cur:
        # Setear contexto RLS por sesión
        cur.execute("SET LOCAL app.workspace_id = %s;", (workspace_id,))
        cur.execute(sql, params)
        
        if cur.description:
            rows = cur.fetchall()
            return rows
        conn.commit()
        return None

@_with_conn
def exec_with_ws_transaction(conn, workspace_id: str, operations):
    """Ejecuta múltiples operaciones en una transacción con contexto RLS"""
    with conn.cursor() as cur:
        # Setear contexto RLS
        cur.execute("SET LOCAL app.workspace_id = %s;", (workspace_id,))
        
        results = []
        for sql, params in operations:
            cur.execute(sql, params)
            if cur.description:
                results.append(cur.fetchall())
            else:
                results.append(cur.rowcount)
        
        conn.commit()
        return results

# Registrar adapter pgvector si está disponible
try:
    from pgvector.psycopg2 import register_vector
    import psycopg2
    register_vector(psycopg2.connect(DB_URL))
    logger.info("Adapter pgvector registrado correctamente")
except Exception as e:
    logger.warning(f"No se pudo registrar adapter pgvector: {e}. Usaré cast ::vector en SQL.")
