"""
Pool de conexiones para PostgreSQL con soporte async
"""
import os
import psycopg2
from psycopg2.pool import SimpleConnectionPool
from psycopg2.extras import RealDictCursor
import logging

logger = logging.getLogger(__name__)

class DatabasePool:
    """Pool de conexiones PostgreSQL"""
    
    def __init__(self, minconn=2, maxconn=10):
        self.pool = SimpleConnectionPool(
            minconn=minconn,
            maxconn=maxconn,
            dsn=os.getenv("DATABASE_URL")
        )
        logger.info(f"Pool de conexiones inicializado: {minconn}-{maxconn} conexiones")
    
    def get_connection(self):
        """Obtiene una conexión del pool"""
        return self.pool.getconn()
    
    def put_connection(self, conn):
        """Devuelve una conexión al pool"""
        self.pool.putconn(conn)
    
    def execute_query(self, sql, params=None):
        """Ejecuta una query y devuelve resultados como lista de dicts"""
        conn = self.get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    results = cur.fetchall()
                    return [dict(row) for row in results]
        finally:
            self.put_connection(conn)
    
    def execute_query_single(self, sql, params=None):
        """Ejecuta una query y devuelve un solo resultado"""
        conn = self.get_connection()
        try:
            with conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(sql, params)
                    result = cur.fetchone()
                    return dict(result) if result else None
        finally:
            self.put_connection(conn)

# Pool global
db_pool = DatabasePool()
