#!/usr/bin/env python3
"""
Script para aplicar las nuevas migraciones del sistema genérico
"""

import os
import sys
import subprocess
import psycopg2
from pathlib import Path
import logging

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_database_connection():
    """Verifica la conexión a la base de datos"""
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        conn.close()
        logger.info("✅ Conexión a base de datos exitosa")
        return True
    except Exception as e:
        logger.error(f"❌ Error conectando a la base de datos: {e}")
        return False

def apply_migrations():
    """Aplica las migraciones de base de datos"""
    try:
        # Cambiar al directorio del proyecto
        project_root = Path(__file__).parent.parent
        os.chdir(project_root)
        
        # Ejecutar el script de migraciones
        logger.info("📦 Aplicando migraciones...")
        result = subprocess.run(
            ["psql", os.getenv('DATABASE_URL'), "-f", "sql/00_all_up.sql"],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            logger.info("✅ Migraciones aplicadas exitosamente")
            return True
        else:
            logger.error(f"❌ Error aplicando migraciones: {result.stderr}")
            return False
            
    except Exception as e:
        logger.error(f"❌ Error ejecutando migraciones: {e}")
        return False

def verify_tables():
    """Verifica que las nuevas tablas se crearon correctamente"""
    try:
        conn = psycopg2.connect(os.getenv('DATABASE_URL'))
        cur = conn.cursor()
        
        # Verificar tablas nuevas
        new_tables = [
            'file_versions',
            'documents', 
            'embeddings',
            'audit_events'
        ]
        
        for table in new_tables:
            cur.execute("""
                SELECT EXISTS (
                    SELECT FROM information_schema.tables 
                    WHERE table_schema = 'pulpo' 
                    AND table_name = %s
                )
            """, (table,))
            
            exists = cur.fetchone()[0]
            if exists:
                logger.info(f"✅ Tabla 'pulpo.{table}' existe")
            else:
                logger.error(f"❌ Tabla 'pulpo.{table}' no existe")
                return False
        
        # Verificar columnas nuevas en tabla files
        cur.execute("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_schema = 'pulpo' 
            AND table_name = 'files'
            AND column_name IN ('vertical', 'document_type', 'storage_uri', 'mime_type', 'file_hash', 'processing_status', 'deleted_at')
        """)
        
        new_columns = [row[0] for row in cur.fetchall()]
        expected_columns = ['vertical', 'document_type', 'storage_uri', 'mime_type', 'file_hash', 'processing_status', 'deleted_at']
        
        for col in expected_columns:
            if col in new_columns:
                logger.info(f"✅ Columna 'files.{col}' existe")
            else:
                logger.error(f"❌ Columna 'files.{col}' no existe")
                return False
        
        # Verificar funciones
        cur.execute("""
            SELECT routine_name 
            FROM information_schema.routines 
            WHERE routine_schema = 'pulpo' 
            AND routine_name IN ('delete_file_cascade', 'hybrid_search')
        """)
        
        functions = [row[0] for row in cur.fetchall()]
        expected_functions = ['delete_file_cascade', 'hybrid_search']
        
        for func in expected_functions:
            if func in functions:
                logger.info(f"✅ Función 'pulpo.{func}' existe")
            else:
                logger.error(f"❌ Función 'pulpo.{func}' no existe")
                return False
        
        # Verificar vistas
        cur.execute("""
            SELECT table_name 
            FROM information_schema.views 
            WHERE table_schema = 'pulpo' 
            AND table_name IN ('v_files_complete', 'v_vertical_stats')
        """)
        
        views = [row[0] for row in cur.fetchall()]
        expected_views = ['v_files_complete', 'v_vertical_stats']
        
        for view in expected_views:
            if view in views:
                logger.info(f"✅ Vista 'pulpo.{view}' existe")
            else:
                logger.error(f"❌ Vista 'pulpo.{view}' no existe")
                return False
        
        conn.close()
        return True
        
    except Exception as e:
        logger.error(f"❌ Error verificando tablas: {e}")
        return False

def main():
    """Función principal"""
    logger.info("🚀 Iniciando aplicación de migraciones del sistema genérico...")
    
    # Verificar conexión a base de datos
    if not check_database_connection():
        logger.error("❌ No se puede conectar a la base de datos. Verifica DATABASE_URL")
        return False
    
    # Aplicar migraciones
    if not apply_migrations():
        logger.error("❌ Error aplicando migraciones")
        return False
    
    # Verificar que todo se creó correctamente
    if not verify_tables():
        logger.error("❌ Error verificando tablas y funciones")
        return False
    
    logger.info("\n🎉 ¡Migraciones aplicadas exitosamente!")
    logger.info("📋 Sistema genérico listo para usar:")
    logger.info("  ✅ API genérica de documentos")
    logger.info("  ✅ Sistema de archivos crudos")
    logger.info("  ✅ Búsqueda híbrida BM25 + Vector")
    logger.info("  ✅ Soporte multi-vertical")
    logger.info("  ✅ Borrado consistente")
    logger.info("  ✅ Auditoría y estadísticas")
    
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
