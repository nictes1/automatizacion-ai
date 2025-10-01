"""
Worker de purga para archivos marcados con soft-delete
Ejecuta purga automática de archivos vencidos
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

class PurgeWorker:
    """Worker para purga automática de archivos vencidos"""
    
    def __init__(self):
        self.ingestion_service = IngestionService()
    
    async def purge_due_files(self):
        """Purga archivos que han vencido su ventana de gracia"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Seleccionar archivos vencidos
                cur.execute("""
                    SELECT id, workspace_id
                      FROM pulpo.files
                     WHERE deleted_at IS NOT NULL
                       AND purge_at <= now()
                """)
                rows = cur.fetchall()
                return [(str(r[0]), str(r[1])) for r in rows]
        
        try:
            to_purge = await run_db(_fn)
            logger.info(f"Encontrados {len(to_purge)} archivos para purgar")
            
            for file_id, workspace_id in to_purge:
                try:
                    logger.info(f"Purgando archivo {file_id} del workspace {workspace_id}")
                    await self.ingestion_service.purge_file_everywhere(file_id, workspace_id)
                    logger.info(f"Archivo {file_id} purgado exitosamente")
                except Exception as e:
                    logger.exception(f"Error purgando archivo {file_id}: {e}")
            
            return len(to_purge)
            
        except Exception as e:
            logger.exception(f"Error en purge_due_files: {e}")
            return 0
    
    async def run_loop(self, interval_seconds: int = 3600):
        """Ejecuta el loop de purga cada intervalo especificado"""
        logger.info(f"Iniciando worker de purga (intervalo: {interval_seconds}s)")
        
        while True:
            try:
                start_time = datetime.now()
                purged_count = await self.purge_due_files()
                duration = (datetime.now() - start_time).total_seconds()
                
                logger.info(f"Ciclo de purga completado: {purged_count} archivos purgados en {duration:.2f}s")
                
            except Exception as e:
                logger.exception(f"Error en ciclo de purga: {e}")
            
            await asyncio.sleep(interval_seconds)

async def main():
    """Función principal para ejecutar el worker"""
    worker = PurgeWorker()
    
    # Intervalo configurable (default: 1 hora)
    interval = int(os.getenv("PURGE_WORKER_INTERVAL_SECONDS", "3600"))
    
    await worker.run_loop(interval)

if __name__ == "__main__":
    asyncio.run(main())
