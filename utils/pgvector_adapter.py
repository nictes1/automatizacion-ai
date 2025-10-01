"""
Adaptador pgvector para psycopg2
"""
import psycopg2
from psycopg2.extensions import register_adapter, AsIs
import logging

logger = logging.getLogger(__name__)

def adapt_vector(v):
    """Adapta una lista de floats a formato vector de PostgreSQL"""
    if not isinstance(v, list):
        raise ValueError("Vector debe ser una lista de floats")
    
    # Formatear como vector de PostgreSQL
    vector_str = "[" + ",".join(f"{x:.6f}" for x in v) + "]"
    return AsIs(f"'{vector_str}'::vector")

def register_pgvector_adapter():
    """Registra el adaptador de vector para psycopg2"""
    try:
        register_adapter(list, adapt_vector)
        logger.info("Adaptador pgvector registrado correctamente")
    except Exception as e:
        logger.error(f"Error registrando adaptador pgvector: {e}")
        raise

# Registrar automáticamente al importar
register_pgvector_adapter()
