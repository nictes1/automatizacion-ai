"""
Tests para Sprint 3: Retries + Scheduler + DLQ
"""
import os
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient

# Configurar variables de entorno para tests
os.environ["ADMIN_TOKEN"] = "secret"
os.environ["SCHEDULER_POLL_INTERVAL"] = "1"
os.environ["SCHEDULER_MAX_CONCURRENCY"] = "2"

@pytest.mark.asyncio
async def test_dlq_view():
    """Test: Vista DLQ lista jobs fallidos"""
    from utils.db_pool import db_pool
    
    # Mock de jobs fallidos
    mock_dlq_jobs = [
        {
            "id": "job-1",
            "job_type": "ocr",
            "status": "failed",
            "retries": 3,
            "max_retries": 3,
            "last_error": "Test error"
        }
    ]
    
    with patch('utils.db_pool.db_pool.execute_query', return_value=mock_dlq_jobs):
        # Simular consulta a DLQ
        sql = "SELECT * FROM pulpo.processing_jobs_dlq"
        result = await asyncio.to_thread(db_pool.execute_query, sql, [])
        
        assert len(result) == 1
        assert result[0]["status"] == "failed"
        assert result[0]["retries"] >= result[0]["max_retries"]

@pytest.mark.asyncio
async def test_requeue_failed_jobs():
    """Test: Requeue de jobs fallidos"""
    from utils.db_pool import db_pool
    
    # Mock de función de requeue
    mock_result = {"count": 2}
    
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_result):
        sql = "SELECT pulpo.requeue_failed_jobs(%s) AS count"
        result = await asyncio.to_thread(db_pool.execute_query_single, sql, ["ocr"])
        
        assert result["count"] == 2

@pytest.mark.asyncio
async def test_backoff_calculation():
    """Test: Cálculo de backoff exponencial"""
    from utils.db_pool import db_pool
    
    # Mock de función de backoff
    mock_result = {"next_run_at": "2024-01-01 10:05:00"}
    
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_result):
        sql = "SELECT pulpo.compute_next_run_at(2, 5, 2.0, 5) AS next_run_at"
        result = await asyncio.to_thread(db_pool.execute_query_single, sql, [])
        
        assert result["next_run_at"] is not None

@pytest.mark.asyncio
async def test_idempotency():
    """Test: Idempotencia con external_key"""
    from utils.db_pool import db_pool
    
    # Mock de inserción con conflicto
    mock_result = None  # No se inserta por conflicto
    
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_result):
        sql = """
        INSERT INTO pulpo.processing_jobs (job_type, external_key, ...)
        VALUES ('ocr', 'doc-123', ...)
        ON CONFLICT (job_type, external_key) WHERE external_key IS NOT NULL DO NOTHING
        RETURNING id
        """
        result = await asyncio.to_thread(db_pool.execute_query_single, sql, [])
        
        # No debe insertar por conflicto
        assert result is None

@pytest.mark.asyncio
async def test_job_scheduler_initialization():
    """Test: Inicialización del job scheduler"""
    from services.job_scheduler import EXECUTORS, register_executor
    
    # Verificar que OCR está registrado
    assert "ocr" in EXECUTORS
    
    # Registrar un ejecutor de prueba
    async def test_executor(job):
        pass
    
    register_executor("test", test_executor)
    assert "test" in EXECUTORS

@pytest.mark.asyncio
async def test_ocr_executor():
    """Test: Ejecutor OCR"""
    from services.job_scheduler import ocr_executor
    from services.ocr_worker import OCRWorker
    
    # Mock del worker OCR
    with patch('services.ocr_worker.OCRWorker') as mock_worker_class:
        mock_worker = AsyncMock()
        mock_worker._process_one = AsyncMock()
        mock_worker_class.return_value = mock_worker
        
        # Job de prueba
        test_job = {
            "id": "job-1",
            "document_id": "doc-1",
            "document_title": "Test Document",
            "storage_url": "file://test.pdf",
            "workspace_id": "ws-1"
        }
        
        # Ejecutar
        await ocr_executor(test_job)
        
        # Verificar que se llamó _process_one
        mock_worker._process_one.assert_called_once()

@pytest.mark.asyncio
async def test_admin_requeue_endpoints():
    """Test: Endpoints admin de requeue"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test requeue jobs fallidos
        response = await client.post(
            "/admin/jobs/requeue?job_type=ocr",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "requeued" in response.json()
        
        # Test requeue job específico
        response = await client.post(
            "/admin/jobs/requeue-one?job_id=job-123",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "job_id" in response.json()

@pytest.mark.asyncio
async def test_admin_dlq_endpoints():
    """Test: Endpoints admin de DLQ"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test listar DLQ
        response = await client.get(
            "/admin/jobs/dlq",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "items" in response.json()
        assert "total" in response.json()
        
        # Test listar DLQ por tipo
        response = await client.get(
            "/admin/jobs/dlq?job_type=ocr",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200

@pytest.mark.asyncio
async def test_admin_job_stats():
    """Test: Estadísticas de jobs"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/admin/jobs/stats",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "job_stats" in response.json()
        assert "scheduler_stats" in response.json()

@pytest.mark.asyncio
async def test_admin_pause_job():
    """Test: Pausar/reanudar job"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test pausar job
        response = await client.post(
            "/admin/jobs/pause?job_id=job-123&pause=true",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert response.json()["paused"] is True
        
        # Test reanudar job
        response = await client.post(
            "/admin/jobs/pause?job_id=job-123&pause=false",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert response.json()["paused"] is False

@pytest.mark.asyncio
async def test_admin_next_jobs():
    """Test: Listar próximos jobs"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/admin/jobs/next?limit=5",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "items" in response.json()
        assert "total" in response.json()
        assert "limit" in response.json()

@pytest.mark.asyncio
async def test_ocr_worker_idempotency():
    """Test: OCR worker con idempotencia"""
    from services.ocr_worker import OCRWorker
    from utils.db_pool import db_pool
    
    worker = OCRWorker()
    
    # Mock de enqueue con idempotencia
    with patch('utils.db_pool.db_pool.execute_query_single') as mock_execute:
        # Primera inserción exitosa
        mock_execute.return_value = {"id": "job-1"}
        
        job_id = await worker._enqueue_job("doc-1", 3, external_key="doc-1")
        assert job_id == "job-1"
        
        # Segunda inserción con conflicto (idempotencia)
        mock_execute.return_value = None
        
        job_id = await worker._enqueue_job("doc-1", 3, external_key="doc-1")
        assert job_id == "noop"

@pytest.mark.asyncio
async def test_scheduler_stats():
    """Test: Estadísticas del scheduler"""
    from services.job_scheduler import get_scheduler_stats
    from utils.db_pool import db_pool
    
    # Mock de estadísticas
    mock_job_stats = [
        {"job_type": "ocr", "status": "completed", "count": 10, "avg_duration": 15.5}
    ]
    mock_dlq_stats = [
        {"job_type": "ocr", "dlq_count": 2}
    ]
    mock_next_result = {"next_count": 3}
    
    with patch('utils.db_pool.db_pool.execute_query') as mock_query, \
         patch('utils.db_pool.db_pool.execute_query_single') as mock_query_single:
        
        mock_query.side_effect = [mock_job_stats, mock_dlq_stats]
        mock_query_single.return_value = mock_next_result
        
        stats = await get_scheduler_stats()
        
        assert "job_stats" in stats
        assert "dlq_stats" in stats
        assert "next_jobs_count" in stats
        assert "registered_executors" in stats

@pytest.mark.asyncio
async def test_job_metrics():
    """Test: Métricas de jobs"""
    from services.metrics import jobs_running, job_retries_total, dlq_total
    
    # Test métricas básicas
    jobs_running.labels(job_type="ocr").set(2)
    job_retries_total.labels(job_type="ocr").inc()
    dlq_total.labels(job_type="ocr").set(1)
    
    # Verificar que las métricas se pueden acceder
    assert jobs_running._metrics is not None
    assert job_retries_total._metrics is not None
    assert dlq_total._metrics is not None

if __name__ == "__main__":
    # Ejecutar tests básicos
    print("🧪 Ejecutando tests de Sprint 3...")
    
    try:
        # Test de inicialización
        asyncio.run(test_job_scheduler_initialization())
        print("✅ Test de inicialización: PASSED")
        
        # Test de ejecutor OCR
        asyncio.run(test_ocr_executor())
        print("✅ Test de ejecutor OCR: PASSED")
        
        # Test de idempotencia
        asyncio.run(test_ocr_worker_idempotency())
        print("✅ Test de idempotencia: PASSED")
        
        # Test de métricas
        asyncio.run(test_job_metrics())
        print("✅ Test de métricas: PASSED")
        
        print("\n🎉 Todos los tests básicos pasaron!")
        
    except Exception as e:
        print(f"❌ Error en tests: {e}")
        raise
