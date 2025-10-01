"""
Outbox Worker - Procesa eventos pendientes para envío a N8N
Implementa patrón outbox con reintentos y backoff exponencial
"""

import os
import logging
import json
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
import anyio

from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class OutboxWorker:
    """Worker para procesar eventos de la cola outbox"""
    
    def __init__(self):
        self.n8n_client = httpx.AsyncClient(timeout=30.0)
        self.n8n_base_url = os.getenv("N8N_BASE_URL", "http://localhost:5678")
        self.batch_size = int(os.getenv("OUTBOX_BATCH_SIZE", "10"))
        self.poll_interval = int(os.getenv("OUTBOX_POLL_INTERVAL", "30"))
        self.max_retries = int(os.getenv("OUTBOX_MAX_RETRIES", "3"))
        
    async def db_exec(self, fn, *args, **kwargs):
        """Ejecuta función síncrona en thread separado"""
        return await anyio.to_thread.run_sync(fn, *args, **kwargs)
    
    def _get_pending_events(self):
        """Obtiene eventos pendientes de procesar"""
        def _fn():
            with psycopg2.connect(os.getenv("DATABASE_URL")) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("""
                        SELECT id, workspace_id, event_type, payload, attempts, max_attempts
                        FROM pulpo.event_outbox
                        WHERE status = 'pending' 
                           OR (status = 'retrying' AND next_retry_at <= now())
                        ORDER BY created_at ASC
                        LIMIT %s
                    """, (self.batch_size,))
                    return cur.fetchall()
        return _fn
    
    def _update_event_status(self, event_id: str, status: str, attempts: int, 
                           error_message: Optional[str] = None, next_retry_at: Optional[datetime] = None):
        """Actualiza el estado de un evento"""
        def _fn():
            with psycopg2.connect(os.getenv("DATABASE_URL")) as conn:
                with conn.cursor() as cur:
                    if status == "sent":
                        cur.execute("""
                            UPDATE pulpo.event_outbox
                            SET status = %s, attempts = %s, sent_at = %s
                            WHERE id = %s
                        """, (status, attempts, datetime.now(), event_id))
                    elif status == "failed":
                        cur.execute("""
                            UPDATE pulpo.event_outbox
                            SET status = %s, attempts = %s, error_message = %s
                            WHERE id = %s
                        """, (status, attempts, error_message, event_id))
                    elif status == "retrying":
                        cur.execute("""
                            UPDATE pulpo.event_outbox
                            SET status = %s, attempts = %s, last_attempt_at = %s, 
                                next_retry_at = %s, error_message = %s
                            WHERE id = %s
                        """, (status, attempts, datetime.now(), next_retry_at, error_message, event_id))
                    conn.commit()
        return _fn
    
    def _calculate_backoff(self, attempts: int) -> int:
        """Calcula tiempo de backoff exponencial en segundos"""
        return min(300, 2 ** attempts * 60)  # Max 5 minutos
    
    async def _send_to_n8n(self, event_type: str, payload: Dict[str, Any]) -> bool:
        """Envía evento a N8N"""
        try:
            # Mapear tipos de evento a endpoints de N8N
            endpoint_map = {
                "pedido_creado": "/webhook/pedido",
                "visita_agendada": "/webhook/visita", 
                "turno_reservado": "/webhook/turno"
            }
            
            endpoint = endpoint_map.get(event_type, "/webhook/generic")
            
            response = await self.n8n_client.post(
                f"{self.n8n_base_url}{endpoint}",
                json=payload,
                headers={
                    "Content-Type": "application/json",
                    "X-Event-Type": event_type
                }
            )
            response.raise_for_status()
            return True
            
        except Exception as e:
            logger.error(f"Error enviando a N8N: {e}")
            return False
    
    async def process_event(self, event: Dict[str, Any]) -> bool:
        """Procesa un evento individual"""
        event_id = str(event["id"])
        event_type = event["event_type"]
        payload = event["payload"]
        attempts = event["attempts"]
        max_attempts = event["max_attempts"]
        
        logger.info(f"Procesando evento {event_id} tipo {event_type} intento {attempts + 1}")
        
        try:
            # Intentar envío a N8N
            success = await self._send_to_n8n(event_type, payload)
            
            if success:
                # Marcar como enviado
                await self.db_exec(self._update_event_status(
                    event_id, "sent", attempts + 1
                ))
                logger.info(f"Evento {event_id} enviado exitosamente")
                return True
            else:
                # Manejar fallo
                if attempts + 1 >= max_attempts:
                    # Máximo de intentos alcanzado
                    await self.db_exec(self._update_event_status(
                        event_id, "failed", attempts + 1, 
                        "Máximo de intentos alcanzado"
                    ))
                    logger.error(f"Evento {event_id} falló definitivamente")
                else:
                    # Programar reintento
                    backoff_seconds = self._calculate_backoff(attempts + 1)
                    next_retry = datetime.now() + timedelta(seconds=backoff_seconds)
                    
                    await self.db_exec(self._update_event_status(
                        event_id, "retrying", attempts + 1,
                        "Error en envío, reintentando", next_retry
                    ))
                    logger.warning(f"Evento {event_id} programado para reintento en {backoff_seconds}s")
                
                return False
                
        except Exception as e:
            logger.error(f"Error procesando evento {event_id}: {e}")
            
            if attempts + 1 >= max_attempts:
                await self.db_exec(self._update_event_status(
                    event_id, "failed", attempts + 1, str(e)
                ))
            else:
                backoff_seconds = self._calculate_backoff(attempts + 1)
                next_retry = datetime.now() + timedelta(seconds=backoff_seconds)
                
                await self.db_exec(self._update_event_status(
                    event_id, "retrying", attempts + 1, str(e), next_retry
                ))
            
            return False
    
    async def process_batch(self):
        """Procesa un lote de eventos"""
        try:
            events = await self.db_exec(self._get_pending_events())
            
            if not events:
                logger.debug("No hay eventos pendientes")
                return
            
            logger.info(f"Procesando {len(events)} eventos")
            
            # Procesar eventos en paralelo
            tasks = [self.process_event(event) for event in events]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            success_count = sum(1 for r in results if r is True)
            logger.info(f"Procesados {len(events)} eventos: {success_count} exitosos")
            
        except Exception as e:
            logger.error(f"Error procesando lote: {e}")
    
    async def run(self):
        """Loop principal del worker"""
        logger.info("🚀 Outbox Worker iniciado")
        logger.info(f"📊 Configuración: batch_size={self.batch_size}, poll_interval={self.poll_interval}s")
        logger.info(f"🔄 N8N URL: {self.n8n_base_url}")
        
        while True:
            try:
                await self.process_batch()
                await asyncio.sleep(self.poll_interval)
            except KeyboardInterrupt:
                logger.info("🛑 Worker detenido por usuario")
                break
            except Exception as e:
                logger.error(f"Error en loop principal: {e}")
                await asyncio.sleep(60)  # Esperar 1 minuto antes de reintentar
    
    async def cleanup(self):
        """Limpieza de recursos"""
        await self.n8n_client.aclose()

async def main():
    """Función principal"""
    worker = OutboxWorker()
    try:
        await worker.run()
    finally:
        await worker.cleanup()

if __name__ == "__main__":
    asyncio.run(main())
