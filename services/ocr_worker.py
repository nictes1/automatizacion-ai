#!/usr/bin/env python3
"""
OCR Worker asíncrono:
- Escanea documentos con needs_ocr=true AND ocr_processed=false
- Extrae texto (Tesseract por defecto, provider pluggable)
- Crea document_revisions (metadata={"source":"ocr", ...})
- Marca ocr_processed=true
- Registra en processing_jobs con reintentos
"""
import os
import asyncio
import logging
from datetime import datetime
from typing import Optional, Dict, Any

import anyio
from dotenv import load_dotenv

from utils.db_pool import db_pool
from utils.ocr_provider import OCRProvider, TesseractOCRProvider, create_ocr_provider

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ocr_worker")

MAX_CONCURRENCY = int(os.getenv("OCR_MAX_CONCURRENCY", "2"))
MAX_RETRIES = int(os.getenv("OCR_MAX_RETRIES", "3"))

class OCRWorker:
    """Worker asíncrono para procesamiento de OCR"""
    
    def __init__(self, provider: Optional[OCRProvider] = None):
        self.provider = provider or create_ocr_provider()
    
    async def _fetch_pending_docs(self, limit: int = 10) -> list:
        """
        Obtiene documentos pendientes de OCR
        """
        sql = """
        SELECT d.id, d.title, d.storage_url, d.workspace_id
        FROM pulpo.documents d
        LEFT JOIN pulpo.processing_jobs j
          ON j.document_id = d.id AND j.job_type = 'ocr' AND j.status IN ('pending', 'processing')
        WHERE d.needs_ocr = true
          AND d.ocr_processed = false
          AND d.deleted_at IS NULL
          AND (j.id IS NULL)
        ORDER BY d.created_at ASC
        LIMIT %s
        """
        return await anyio.to_thread.run_sync(db_pool.execute_query, sql, [limit])
    
    async def _enqueue_job(self, doc_id: str, max_retries: int = MAX_RETRIES, external_key: str = None) -> str:
        """
        Crea un job de procesamiento con idempotencia
        """
        sql = """
        INSERT INTO pulpo.processing_jobs (
            document_id, job_type, status, retries, max_retries,
            next_run_at, backoff_base_seconds, backoff_factor, jitter_seconds, external_key,
            created_at, updated_at
        )
        VALUES (%s, 'ocr', 'pending', 0, %s, now(), 5, 2.0, 5, %s, now(), now())
        ON CONFLICT (job_type, external_key) WHERE external_key IS NOT NULL DO NOTHING
        RETURNING id
        """
        row = await anyio.to_thread.run_sync(
            db_pool.execute_query_single, sql, [doc_id, max_retries, external_key]
        )
        return row["id"] if row and row.get("id") else "noop"
    
    async def _update_job(self, job_id: str, **fields):
        """
        Actualiza un job de procesamiento
        """
        sets = []
        params = []
        for k, v in fields.items():
            sets.append(f"{k}=%s")
            params.append(v)
        sets.append("updated_at=now()")
        sql = f"UPDATE pulpo.processing_jobs SET {', '.join(sets)} WHERE id=%s"
        params.append(job_id)
        await anyio.to_thread.run_sync(db_pool.execute_query, sql, params)
    
    async def _create_revision(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> int:
        """
        Crea una nueva revisión del documento con contenido OCR
        """
        sql = "SELECT pulpo.create_document_revision(%s, %s, %s, %s) AS revision"
        params = [doc_id, content, metadata, None]
        result = await anyio.to_thread.run_sync(db_pool.execute_query_single, sql, params)
        return result["revision"]
    
    async def _mark_ocr_processed(self, doc_id: str):
        """
        Marca el documento como procesado por OCR
        """
        sql = "UPDATE pulpo.documents SET ocr_processed=true WHERE id=%s AND ocr_processed=false"
        await anyio.to_thread.run_sync(db_pool.execute_query, sql, [doc_id])
    
    async def process_document(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Procesa un documento sin tocar processing_jobs (usado por scheduler)
        """
        logger.info(f"[ocr] processing doc={doc['id']} '{doc['title']}'")
        
        # Extraer texto con OCR
        text, meta = await self.provider.extract_text(doc["storage_url"])
        meta = {"source": "ocr", **(meta or {})}
        
        # Crear revisión con contenido OCR
        revision = await self._create_revision(doc["id"], text, meta)
        
        # Marcar documento como ocr_processed
        await self._mark_ocr_processed(doc["id"])
        
        logger.info(f"[ocr] completed doc={doc['id']} revision={revision} chars={len(text)}")
        return {"revision": revision, "chars": len(text)}

    async def enqueue_document(self, doc_id: str, max_retries: int = MAX_RETRIES) -> str:
        """
        Encola un documento para procesamiento (solo encola, no procesa)
        """
        return await self._enqueue_job(doc_id, max_retries, external_key=doc_id)

    async def _process_one(self, doc: Dict[str, Any]):
        """
        Procesa un documento individual (método legacy para compatibilidad)
        """
        job_id = await self._enqueue_job(doc["id"])
        await self._update_job(job_id, status='processing', started_at=datetime.now())
        
        try:
            result = await self.process_document(doc)
            await self._update_job(job_id, status='completed', completed_at=datetime.now())
            logger.info(f"[ocr] completed doc={doc['id']} chars={result['chars']}")
            
        except Exception as e:
            # Incrementar reintentos
            sql = """
            UPDATE pulpo.processing_jobs
               SET status = CASE WHEN retries + 1 >= max_retries THEN 'failed' ELSE 'pending' END,
                   retries = retries + 1,
                   last_error = %s,
                   updated_at = now()
             WHERE id = %s
            RETURNING status, retries, max_retries
            """
            res = await anyio.to_thread.run_sync(
                db_pool.execute_query_single, sql, [str(e), job_id]
            )
            logger.exception(
                f"[ocr] error doc={doc['id']} job={job_id} -> "
                f"status={res['status']} r={res['retries']}/{res['max_retries']}"
            )
    
    async def run_once(self, batch_size: int = 10) -> int:
        """
        Encola documentos para procesamiento (el scheduler los ejecutará)
        """
        docs = await self._fetch_pending_docs(batch_size)
        if not docs:
            logger.info("[ocr] no pending docs")
            return 0
        
        logger.info(f"[ocr] enqueueing {len(docs)} documents")
        
        async with anyio.create_task_group() as tg:
            sem = anyio.Semaphore(MAX_CONCURRENCY)
            
            async def _guarded(doc):
                async with sem:
                    # Encolar con external_key = doc_id para idempotencia
                    job_id = await self.enqueue_document(doc["id"], MAX_RETRIES)
                    if job_id != "noop":
                        logger.debug(f"[ocr] enqueued job={job_id} for doc={doc['id']}")
            
            for doc in docs:
                tg.start_soon(_guarded, doc)
        
        return len(docs)
    
    async def loop(self, interval_seconds: int = 30):
        """
        Loop continuo de procesamiento
        """
        logger.info(f"[ocr] starting loop with interval={interval_seconds}s")
        
        while True:
            try:
                processed = await self.run_once()
                if processed > 0:
                    logger.info(f"[ocr] processed {processed} documents")
            except Exception:
                logger.exception("[ocr] loop error")
            
            await anyio.sleep(interval_seconds)
    
    async def get_stats(self) -> Dict[str, Any]:
        """
        Obtiene estadísticas del worker
        """
        try:
            # Estadísticas de jobs
            sql = """
            SELECT 
                status,
                COUNT(*) as count,
                AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration
            FROM pulpo.processing_jobs
            WHERE job_type = 'ocr'
            GROUP BY status
            """
            job_stats = await anyio.to_thread.run_sync(db_pool.execute_query, sql, [])
            
            # Documentos pendientes
            sql = """
            SELECT COUNT(*) as pending_count
            FROM pulpo.documents
            WHERE needs_ocr = true AND ocr_processed = false AND deleted_at IS NULL
            """
            pending_result = await anyio.to_thread.run_sync(
                db_pool.execute_query_single, sql, []
            )
            
            return {
                "job_stats": job_stats,
                "pending_documents": pending_result["pending_count"],
                "max_concurrency": MAX_CONCURRENCY,
                "max_retries": MAX_RETRIES
            }
            
        except Exception as e:
            logger.error(f"Error getting stats: {e}")
            return {"error": str(e)}

async def main():
    """Función principal del worker"""
    worker = OCRWorker()
    mode = os.getenv("OCR_RUN_MODE", "loop")  # "once" | "loop"
    
    if mode == "once":
        logger.info("[ocr] running once")
        processed = await worker.run_once()
        logger.info(f"[ocr] processed {processed} documents")
    else:
        interval = int(os.getenv("OCR_LOOP_INTERVAL", "30"))
        await worker.loop(interval)

if __name__ == "__main__":
    anyio.run(main())
