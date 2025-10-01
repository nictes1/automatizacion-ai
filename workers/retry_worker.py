"""
Worker de reintentos para archivos fallidos
Reintenta procesamiento de archivos con backoff exponencial
"""

import os
import asyncio
import logging
from datetime import datetime
from dotenv import load_dotenv

from utils.db_async import run_db
from services.ingestion_service import IngestionService

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class RetryWorker:
    """Worker para reintentos automáticos de archivos fallidos"""
    
    def __init__(self):
        self.ingestion_service = IngestionService()
        self.max_attempts = int(os.getenv("INGESTION_MAX_ATTEMPTS", "3"))
    
    async def retry_due_files(self):
        """Reintenta archivos que están listos para reintento"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Seleccionar archivos listos para reintento (excluir soft-deleted)
                cur.execute("""
                    SELECT id, workspace_id, storage_uri
                      FROM pulpo.files
                     WHERE next_retry_at IS NOT NULL
                       AND next_retry_at <= now()
                       AND attempts < %s
                       AND deleted_at IS NULL
                     LIMIT 20
                """, (self.max_attempts,))
                rows = cur.fetchall()
                return [(str(r[0]), str(r[1]), r[2]) for r in rows]
        
        try:
            candidates = await run_db(_fn)
            logger.info(f"Encontrados {len(candidates)} archivos para reintento")
            
            for file_id, workspace_id, storage_uri in candidates:
                try:
                    logger.info(f"Reintentando procesamiento de archivo {file_id}")
                    # Reintentar en background
                    asyncio.create_task(
                        self.ingestion_service._process_file_background(file_id, workspace_id, storage_uri)
                    )
                except Exception as e:
                    logger.exception(f"Error programando reintento para archivo {file_id}: {e}")
            
            return len(candidates)
            
        except Exception as e:
            logger.exception(f"Error en retry_due_files: {e}")
            return 0
    
    async def run_loop(self, interval_seconds: int = 60):
        """Ejecuta el loop de reintentos cada intervalo especificado"""
        logger.info(f"Iniciando worker de reintentos (intervalo: {interval_seconds}s)")
        
        while True:
            try:
                start_time = datetime.now()
                retried_count = await self.retry_due_files()
                duration = (datetime.now() - start_time).total_seconds()
                
                if retried_count > 0:
                    logger.info(f"Ciclo de reintentos completado: {retried_count} archivos programados en {duration:.2f}s")
                
            except Exception as e:
                logger.exception(f"Error en ciclo de reintentos: {e}")
            
            await asyncio.sleep(interval_seconds)

async def main():
    """Función principal para ejecutar el worker"""
    worker = RetryWorker()
    
    # Intervalo configurable (default: 60 segundos)
    interval = int(os.getenv("RETRY_WORKER_INTERVAL_SECONDS", "60"))
    
    await worker.run_loop(interval)

if __name__ == "__main__":
    asyncio.run(main())
