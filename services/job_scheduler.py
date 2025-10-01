#!/usr/bin/env python3
"""
Job Scheduler - Sistema genérico de ejecución de jobs con retries
- Polling eficiente por next_run_at
- Backoff exponencial con jitter
- Ejecutores registrados por job_type
- Manejo de errores y transiciones de estado
"""
import os
import logging
import anyio
import asyncio
from datetime import datetime
from typing import Dict, Any, Callable, Optional, Awaitable
from collections import deque

from utils.db_pool import db_pool
from utils.pgvector_adapter import register_pgvector_adapter

# Asegurar adapter de pgvector para embeddings
register_pgvector_adapter()

logger = logging.getLogger("job_scheduler")

# Configuración
POLL_INTERVAL = int(os.getenv("SCHEDULER_POLL_INTERVAL", "5"))
MAX_CONCURRENCY = int(os.getenv("SCHEDULER_MAX_CONCURRENCY", "4"))

# Concurrencia por tipo de job
MAX_CONCURRENCY_BY_TYPE = {
    "ocr": int(os.getenv("SCHEDULER_MAX_CONCURRENCY_OCR", "1")),
    "chunking": int(os.getenv("SCHEDULER_MAX_CONCURRENCY_CHUNKING", "2")),
    "embedding": int(os.getenv("SCHEDULER_MAX_CONCURRENCY_EMBEDDING", "2"))
}

# Concurrencia para generación de embeddings (dentro de embedding_executor)
EMBEDDING_CONCURRENCY = int(os.getenv("EMBEDDING_CONCURRENCY", "4"))

# Prioridades por tipo de job
PRIORITY_BY_TYPE = {
    "ocr": int(os.getenv("PRIORITY_OCR", "100")),
    "chunking": int(os.getenv("PRIORITY_CHUNKING", "60")),
    "embedding": int(os.getenv("PRIORITY_EMBEDDING", "20"))
}

# Circuit breaker para embeddings
EMBEDDING_CB_FAILS = int(os.getenv("EMBEDDING_CB_FAILS", "5"))
EMBEDDING_CB_WINDOW_SEC = int(os.getenv("EMBEDDING_CB_WINDOW_SEC", "60"))
EMBEDDING_CB_COOLDOWN_SEC = int(os.getenv("EMBEDDING_CB_COOLDOWN_SEC", "45"))

# Circuit breaker state (en memoria) con ventana temporal
# { ws_id: {"fail_ts": deque([t1,t2,...]), "opened_until": epoch_seconds} }
circuit_breaker_state = {}

def _check_circuit_breaker(workspace_id: str) -> bool:
    """Verifica si el circuit breaker está abierto para el workspace"""
    now = datetime.now().timestamp()
    state = circuit_breaker_state.get(workspace_id, {"fail_ts": deque(), "opened_until": 0})
    
    # Si está abierto y no pasó cooldown, cortar
    if state["opened_until"] > now:
        return False
    
    # Si pasó cooldown, reset total
    if state["opened_until"] > 0 and state["opened_until"] <= now:
        state = {"fail_ts": deque(), "opened_until": 0}
        circuit_breaker_state[workspace_id] = state
    
    return True

def _record_circuit_breaker_failure(workspace_id: str):
    """Registra un fallo en el circuit breaker con ventana temporal"""
    now = datetime.now().timestamp()
    win = EMBEDDING_CB_WINDOW_SEC
    state = circuit_breaker_state.get(workspace_id, {"fail_ts": deque(), "opened_until": 0})
    
    # Purgar fallos fuera de ventana
    while state["fail_ts"] and (now - state["fail_ts"][0]) > win:
        state["fail_ts"].popleft()
    
    # Registrar fallo actual
    state["fail_ts"].append(now)
    
    # Abrir breaker si supera umbral en ventana
    if len(state["fail_ts"]) >= EMBEDDING_CB_FAILS:
        state["opened_until"] = now + EMBEDDING_CB_COOLDOWN_SEC
        logger.warning(f"[circuit_breaker] opened for workspace={workspace_id} until {state['opened_until']}")
    
    circuit_breaker_state[workspace_id] = state

def _record_circuit_breaker_success(workspace_id: str):
    """Registra un éxito en el circuit breaker (reset)"""
    circuit_breaker_state[workspace_id] = {"fail_ts": deque(), "opened_until": 0}

# Registry de ejecutores por job_type
EXECUTORS: Dict[str, Callable[[Dict[str, Any]], Awaitable[None]]] = {}

# Semáforos por tipo de job para control de concurrencia
SEMAPHORES: Dict[str, anyio.Semaphore] = {
    job_type: anyio.Semaphore(limit) 
    for job_type, limit in MAX_CONCURRENCY_BY_TYPE.items()
}

def register_executor(job_type: str, fn: Callable[[Dict[str, Any]], any]):
    """Registra un ejecutor para un tipo de job"""
    EXECUTORS[job_type] = fn
    logger.info(f"Registered executor for job_type: {job_type}")

async def _enqueue_job(document_id: str, job_type: str, external_key: str, max_retries: int = 3, 
                      priority: int = 0, workspace_id: str = None) -> Optional[str]:
    """Helper genérico para encolar jobs con idempotencia y prioridad"""
    sql = """
    INSERT INTO pulpo.processing_jobs (
        document_id, job_type, status, retries, max_retries,
        next_run_at, backoff_base_seconds, backoff_factor, jitter_seconds, external_key,
        priority, workspace_id, created_at, updated_at
    )
    VALUES (%s, %s, 'pending', 0, %s, now(), 5, 2.0, 5, %s, %s, %s, now(), now())
    ON CONFLICT (job_type, external_key) WHERE external_key IS NOT NULL DO NOTHING
    RETURNING id
    """
    row = await anyio.to_thread.run_sync(
        db_pool.execute_query_single, sql, [document_id, job_type, max_retries, external_key, priority, workspace_id]
    )
    return row["id"] if row and row.get("id") else None

async def _fetch_due_jobs(limit: int = 20) -> list:
    """Obtiene y reclama jobs listos para ejecutar con prioridades y cuotas"""
    sql = """
    WITH due AS (
        SELECT id
        FROM pulpo.get_due_jobs_with_quotas(%s)
        FOR UPDATE SKIP LOCKED
    )
    UPDATE pulpo.processing_jobs p
       SET status='processing', started_at=now(), updated_at=now()
      FROM due
     WHERE p.id = due.id
    RETURNING p.*;
    """
    return await anyio.to_thread.run_sync(db_pool.execute_query, sql, [limit])

async def _mark_processing(job_id: str):
    """Marca un job como en procesamiento"""
    sql = "UPDATE pulpo.processing_jobs SET status='processing', started_at=now(), updated_at=now() WHERE id=%s"
    await anyio.to_thread.run_sync(db_pool.execute_query, sql, [job_id])

async def _mark_completed(job_id: str):
    """Marca un job como completado"""
    sql = "UPDATE pulpo.processing_jobs SET status='completed', completed_at=now(), updated_at=now() WHERE id=%s"
    await anyio.to_thread.run_sync(db_pool.execute_query, sql, [job_id])

async def _mark_retry(job: Dict[str, Any], last_error: str):
    """Marca un job para reintento con backoff exponencial"""
    sql = """
    UPDATE pulpo.processing_jobs
       SET status='retry',
           last_error=%s,
           retries=retries+1,
           next_run_at=pulpo.compute_next_run_at(retries+1, backoff_base_seconds, backoff_factor, jitter_seconds),
           updated_at=now()
     WHERE id=%s
     RETURNING retries, max_retries
    """
    row = await anyio.to_thread.run_sync(
        db_pool.execute_query_single, sql, [last_error, job["id"]]
    )
    
    # Si superó max_retries => failed
    if row and row["retries"] >= job["max_retries"]:
        sql_failed = "UPDATE pulpo.processing_jobs SET status='failed', updated_at=now() WHERE id=%s"
        await anyio.to_thread.run_sync(db_pool.execute_query, sql_failed, [job["id"]])
        logger.warning(f"Job {job['id']} failed after {row['retries']} retries")

async def _run_one_job(job: Dict[str, Any]):
    """Ejecuta un job individual con semáforo por tipo"""
    from services.metrics import jobs_running
    
    job_id = job["id"]
    job_type = job["job_type"]
    
    # Obtener semáforo por tipo de job
    semaphore = SEMAPHORES.get(job_type)
    if not semaphore:
        logger.error(f"No semaphore for job_type={job_type}")
        return
    
    # Usar semáforo por tipo
    async with semaphore:
        # Incrementar métrica de jobs en ejecución
        jobs_running.labels(job_type=job_type).inc()
        
        try:
            logger.info(f"[scheduler] processing job={job_id} type={job_type}")
            
            # Obtener ejecutor
            exec_fn = EXECUTORS.get(job_type)
            if not exec_fn:
                raise RuntimeError(f"No executor for job_type={job_type}")
            
            # Ejecutar job
            await exec_fn(job)
            
            # Marcar como completado
            await _mark_completed(job_id)
            logger.info(f"[scheduler] completed job={job_id} type={job_type}")
            
        except Exception as e:
            logger.exception(f"[scheduler] job={job_id} type={job_type} error: {e}")
            await _mark_retry(job, str(e))
            
        finally:
            # Decrementar métrica de jobs en ejecución
            jobs_running.labels(job_type=job_type).dec()

async def run_scheduler_loop():
    """Loop principal del scheduler"""
    logger.info(f"[scheduler] starting: poll={POLL_INTERVAL}s")
    logger.info(f"[scheduler] concurrency by type: {MAX_CONCURRENCY_BY_TYPE}")
    logger.info(f"[scheduler] priority by type: {PRIORITY_BY_TYPE}")

    while True:
        try:
            # Obtener jobs listos para ejecutar
            jobs = await _fetch_due_jobs()
            
            if jobs:
                logger.info(f"[scheduler] dispatching {len(jobs)} jobs")
                
                # Ejecutar jobs en paralelo (cada uno usa su semáforo por tipo)
                async with anyio.create_task_group() as tg:
                    for job in jobs:
                        tg.start_soon(_run_one_job, job)
            else:
                logger.debug("[scheduler] no jobs to process")
                
        except Exception:
            logger.exception("[scheduler] loop error")

        # Esperar antes del siguiente poll
        await anyio.sleep(POLL_INTERVAL)

async def get_scheduler_stats() -> Dict[str, Any]:
    """Obtiene estadísticas del scheduler"""
    try:
        # Estadísticas de jobs por estado
        sql = """
        SELECT 
            job_type,
            status,
            COUNT(*) as count,
            AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration
        FROM pulpo.processing_jobs
        WHERE started_at IS NOT NULL
        GROUP BY job_type, status
        ORDER BY job_type, status
        """
        job_stats = await anyio.to_thread.run_sync(db_pool.execute_query, sql, [])
        
        # Jobs en DLQ
        sql_dlq = """
        SELECT job_type, COUNT(*) as dlq_count
        FROM pulpo.processing_jobs_dlq
        GROUP BY job_type
        """
        dlq_stats = await anyio.to_thread.run_sync(db_pool.execute_query, sql_dlq, [])
        
        # Jobs próximos a ejecutar
        sql_next = """
        SELECT COUNT(*) as next_count
        FROM pulpo.processing_jobs
        WHERE status IN ('pending','retry')
          AND paused = FALSE
          AND (next_run_at IS NULL OR next_run_at <= now())
        """
        next_result = await anyio.to_thread.run_sync(
            db_pool.execute_query_single, sql_next, []
        )
        
        # Obtener workspaces con circuit breaker abierto
        now = datetime.now().timestamp()
        cb_open_workspaces = [
            ws for (ws, st) in circuit_breaker_state.items() 
            if st.get("opened_until", 0) > now
        ]
        
        return {
            "job_stats": job_stats,
            "dlq_stats": dlq_stats,
            "next_jobs_count": next_result["next_count"],
            "registered_executors": list(EXECUTORS.keys()),
            "poll_interval": POLL_INTERVAL,
            "max_concurrency": MAX_CONCURRENCY,
            "concurrency_by_type": MAX_CONCURRENCY_BY_TYPE,
            "priority_by_type": PRIORITY_BY_TYPE,
            "cb_open_workspaces": cb_open_workspaces
        }
        
    except Exception as e:
        logger.error(f"Error getting scheduler stats: {e}")
        return {"error": str(e)}

# Bootstrap: registrar OCR como ejecutor
async def ocr_executor(job: Dict[str, Any]):
    """Ejecutor para jobs de OCR"""
    from services.ocr_worker import OCRWorker
    from services.metrics import jobs_processed_total, job_duration_seconds, job_retries_total
    from time import perf_counter
    
    t0 = perf_counter()
    worker = OCRWorker()
    
    # Construir documento desde job
    doc = {
        "id": job["document_id"],
        "title": job.get("document_title", ""),
        "storage_url": job.get("document_storage_url", ""),
        "workspace_id": job.get("workspace_id", "")
    }
    
    try:
        # Procesar documento (sin tocar processing_jobs)
        result = await worker.process_document(doc)
        
        # Encadenar chunking tras éxito de OCR
        try:
            # Obtener última revisión para idempotencia
            rev_row = await anyio.to_thread.run_sync(
                db_pool.execute_query_single,
                "SELECT revision FROM pulpo.document_revisions WHERE document_id=%s ORDER BY revision DESC LIMIT 1",
                [job["document_id"]]
            )
            if rev_row:
                revision = rev_row["revision"]
                ek = f"{job['document_id']}:chunking:rev{revision}"
                chunking_job_id = await _enqueue_job(
                    job["document_id"], "chunking", ek, 
                    max_retries=3, 
                    priority=PRIORITY_BY_TYPE["chunking"],
                    workspace_id=job.get("workspace_id")
                )
                if chunking_job_id:
                    logger.info(f"[ocr] enqueued chunking job={chunking_job_id} for doc={job['document_id']} rev={revision}")
        except Exception as chain_error:
            logger.warning(f"[ocr] failed to enqueue chunking for doc={job['document_id']}: {chain_error}")
            # No fallar el job OCR por error en encadenamiento
        
        # Métricas de éxito
        job_duration_seconds.labels("ocr", "completed").observe(perf_counter() - t0)
        jobs_processed_total.labels("ocr", "completed").inc()
        
    except Exception as e:
        # Métricas de error
        job_retries_total.labels("ocr").inc()
        job_duration_seconds.labels("ocr", "retry").observe(perf_counter() - t0)
        raise  # Re-lanzar para que el scheduler maneje el retry

# Registrar ejecutores
register_executor("ocr", ocr_executor)

# Funciones helper para chunking
def _chunk_text(text: str, size: int = 800, overlap: int = 150):
    """Divide texto en chunks con overlap"""
    chunks = []
    i = 0
    n = len(text)
    while i < n:
        end = min(i + size, n)
        chunk = text[i:end]
        chunks.append(chunk.strip())
        i = end - overlap if end - overlap > i else end
    return [c for c in chunks if c]

async def _get_latest_revision(document_id: str):
    """Obtiene la última revisión de un documento"""
    sql = """
    SELECT r.revision, r.content, d.workspace_id, d.title
    FROM pulpo.document_revisions r
    JOIN pulpo.documents d ON d.id = r.document_id
    WHERE r.document_id = %s
    ORDER BY r.revision DESC
    LIMIT 1
    """
    return await anyio.to_thread.run_sync(db_pool.execute_query_single, sql, [document_id])

async def _insert_chunks(document_id: str, workspace_id: str, chunks: list, revision: int) -> int:
    """Inserta chunks en lotes"""
    rows = [(document_id, workspace_id, t, {"source":"ocr","revision":revision}) for t in chunks]
    inserted = 0
    for i in range(0, len(rows), 200):
        batch = rows[i:i+200]
        values_sql = ", ".join(["(%s,%s,%s,%s,now())"]*len(batch))
        flat = []
        for r in batch: 
            flat.extend(list(r))
        sql = f"""
        INSERT INTO pulpo.chunks (document_id, workspace_id, text, meta, created_at)
        VALUES {values_sql}
        """
        await anyio.to_thread.run_sync(db_pool.execute_query, sql, flat)
        inserted += len(batch)
    return inserted

# Ejecutor productivo de chunking
async def chunking_executor(job: Dict[str, Any]):
    """Ejecutor para jobs de chunking (productivo)"""
    from services.metrics import jobs_processed_total, job_duration_seconds, job_retries_total
    from time import perf_counter
    
    t0 = perf_counter()
    try:
        info = await _get_latest_revision(job["document_id"])
        if not info: 
            raise RuntimeError("No hay revisión disponible para chunking")
        
        revision = info["revision"]
        content = info["content"]
        ws_id = info["workspace_id"]
        title = info["title"]
        
        pieces = _chunk_text(content, 800, 150)
        if not pieces:
            raise RuntimeError("Texto vacío tras chunking")
        
        count = await _insert_chunks(job["document_id"], ws_id, pieces, revision)

        # Encadenar embedding con idempotencia por revisión
        ek = f"{job['document_id']}:embedding:rev{revision}"
        embedding_job_id = await _enqueue_job(
            job["document_id"], "embedding", ek, 
            max_retries=3, 
            priority=PRIORITY_BY_TYPE["embedding"],
            workspace_id=ws_id
        )
        if embedding_job_id:
            logger.info(f"[chunking] enqueued embedding job={embedding_job_id} for doc={job['document_id']} rev={revision}")

        job_duration_seconds.labels("chunking", "completed").observe(perf_counter() - t0)
        jobs_processed_total.labels("chunking", "completed").inc()
        logger.info(f"[chunking] doc={job['document_id']} rev={revision} chunks={count}")
        
    except Exception as e:
        job_retries_total.labels("chunking").inc()
        job_duration_seconds.labels("chunking", "retry").observe(perf_counter() - t0)
        raise

# Funciones helper para embedding
async def _get_chunks_without_embedding(document_id: str, limit: int = 500):
    """Obtiene chunks sin embedding de un documento"""
    sql = """
    SELECT c.id, c.text, c.workspace_id
    FROM pulpo.chunks c
    LEFT JOIN pulpo.chunk_embeddings e
      ON e.chunk_id = c.id AND e.workspace_id = c.workspace_id AND e.deleted_at IS NULL
    WHERE c.document_id = %s
      AND c.deleted_at IS NULL
      AND e.chunk_id IS NULL
    LIMIT %s
    """
    return await anyio.to_thread.run_sync(db_pool.execute_query, sql, [document_id, limit])

async def _insert_embeddings(workspace_id: str, rows: list):
    """Inserta embeddings en lotes"""
    # rows: [(chunk_id, workspace_id, embedding_vector)]
    inserted = 0
    for i in range(0, len(rows), 200):
        batch = rows[i:i+200]
        values_sql = ", ".join(["(%s,%s,%s,now())"]*len(batch))
        flat = []
        for (cid, ws, emb) in batch:
            flat.extend([cid, ws, emb])
        sql = f"""
        INSERT INTO pulpo.chunk_embeddings (chunk_id, workspace_id, embedding, created_at)
        VALUES {values_sql}
        ON CONFLICT DO NOTHING
        """
        await anyio.to_thread.run_sync(db_pool.execute_query, sql, flat)
        inserted += len(batch)
    return inserted

# Ejecutor productivo de embedding
async def embedding_executor(job: Dict[str, Any]):
    """Ejecutor para jobs de embedding (productivo)"""
    from services.metrics import jobs_processed_total, job_duration_seconds, job_retries_total
    from utils.ollama_embeddings import OllamaEmbeddings
    from time import perf_counter
    
    t0 = perf_counter()
    workspace_id = job.get("workspace_id", "default")
    
    try:
        # Verificar circuit breaker
        if not _check_circuit_breaker(workspace_id):
            raise RuntimeError("circuit_breaker_open")
        
        pending = await _get_chunks_without_embedding(job["document_id"])
        if not pending:
            logger.info(f"[embedding] doc={job['document_id']} nada pendiente")
            job_duration_seconds.labels("embedding", "completed").observe(perf_counter() - t0)
            jobs_processed_total.labels("embedding", "completed").inc()
            return

        embedder = OllamaEmbeddings()
        
        # Generar embeddings con concurrencia limitada
        semaphore = anyio.Semaphore(EMBEDDING_CONCURRENCY)
        
        async def _generate_embedding(row):
            async with semaphore:
                vec = await embedder.generate_embedding(row["text"])
                return (row["id"], row["workspace_id"], vec)
        
        # Ejecutar en paralelo con concurrencia limitada usando asyncio.gather
        rows = await asyncio.gather(*[_generate_embedding(row) for row in pending])

        inserted = await _insert_embeddings(pending[0]["workspace_id"], rows)
        
        # Registrar éxito en circuit breaker
        _record_circuit_breaker_success(workspace_id)
        
        job_duration_seconds.labels("embedding", "completed").observe(perf_counter() - t0)
        jobs_processed_total.labels("embedding", "completed").inc()
        logger.info(f"[embedding] doc={job['document_id']} embeddeds={inserted}")
        
    except Exception as e:
        # Registrar fallo en circuit breaker
        _record_circuit_breaker_failure(workspace_id)
        
        job_retries_total.labels("embedding").inc()
        job_duration_seconds.labels("embedding", "retry").observe(perf_counter() - t0)
        raise

# Registrar ejecutores placeholder
register_executor("chunking", chunking_executor)
register_executor("embedding", embedding_executor)

async def main():
    """Función principal del scheduler"""
    logger.info("Starting Pulpo Job Scheduler...")
    
    # Mostrar ejecutores registrados
    logger.info(f"Registered executors: {list(EXECUTORS.keys())}")
    
    # Iniciar loop principal
    await run_scheduler_loop()

if __name__ == "__main__":
    anyio.run(main())
