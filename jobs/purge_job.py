"""
Job nocturno para purga de documentos eliminados
"""
import asyncio
import logging
import os
from datetime import datetime, timedelta
from typing import Dict, Any

from utils.db_pool import db_pool
from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class PurgeJob:
    """Job para purga automática de documentos eliminados"""
    
    def __init__(self, retention_days: int = 7):
        self.retention_days = retention_days
        self.db_pool = db_pool
    
    async def run_purge(self) -> Dict[str, Any]:
        """
        Ejecuta la purga de documentos eliminados
        """
        try:
            logger.info(f"Iniciando purga de documentos eliminados (retención: {self.retention_days} días)")
            
            # Llamar a la función SQL de purga
            sql = "SELECT * FROM pulpo.purge_deleted_documents(%s)"
            params = [self.retention_days]
            
            result = await asyncio.to_thread(
                self.db_pool.execute_query_single, sql, params
            )
            
            if result:
                deleted_count = result["deleted_count"]
                purged_documents = result["purged_documents"]
                
                logger.info(f"Purga completada: {deleted_count} documentos eliminados, {purged_documents} purgados")
                
                return {
                    "success": True,
                    "deleted_count": deleted_count,
                    "purged_documents": purged_documents,
                    "retention_days": self.retention_days,
                    "executed_at": datetime.now().isoformat()
                }
            else:
                logger.warning("No se encontraron documentos para purgar")
                return {
                    "success": True,
                    "deleted_count": 0,
                    "purged_documents": 0,
                    "retention_days": self.retention_days,
                    "executed_at": datetime.now().isoformat()
                }
                
        except Exception as e:
            logger.error(f"Error en purga: {e}")
            return {
                "success": False,
                "error": str(e),
                "executed_at": datetime.now().isoformat()
            }
    
    async def get_purge_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas de documentos eliminados
        """
        try:
            # Contar documentos eliminados por antigüedad
            sql = """
            SELECT 
                COUNT(*) as total_deleted,
                COUNT(*) FILTER (WHERE deleted_at < now() - interval '7 days') as old_enough_to_purge,
                COUNT(*) FILTER (WHERE deleted_at < now() - interval '30 days') as very_old
            FROM pulpo.documents
            WHERE deleted_at IS NOT NULL
            """
            
            result = await asyncio.to_thread(
                self.db_pool.execute_query_single, sql, []
            )
            
            return {
                "total_deleted": result["total_deleted"],
                "old_enough_to_purge": result["old_enough_to_purge"],
                "very_old": result["very_old"],
                "retention_days": self.retention_days
            }
            
        except Exception as e:
            logger.error(f"Error obteniendo estadísticas: {e}")
            return {"error": str(e)}

async def main():
    """
    Función principal para ejecutar el job de purga
    """
    # Configuración desde ENV
    retention_days = int(os.getenv("PURGE_RETENTION_DAYS", "7"))
    
    # Crear instancia del job
    purge_job = PurgeJob(retention_days=retention_days)
    
    # Obtener estadísticas antes de la purga
    stats_before = await purge_job.get_purge_stats()
    logger.info(f"Estadísticas antes de la purga: {stats_before}")
    
    # Ejecutar purga
    result = await purge_job.run_purge()
    
    # Obtener estadísticas después de la purga
    stats_after = await purge_job.get_purge_stats()
    logger.info(f"Estadísticas después de la purga: {stats_after}")
    
    # Log final
    if result["success"]:
        logger.info(f"✅ Job de purga completado exitosamente: {result}")
    else:
        logger.error(f"❌ Job de purga falló: {result}")
    
    return result

if __name__ == "__main__":
    # Ejecutar el job
    asyncio.run(main())
