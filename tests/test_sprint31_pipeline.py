"""
Tests para Sprint 3.1: Pipeline encadenado OCR → Chunking → Embedding
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
async def test_enqueue_job_helper():
    """Test: Helper genérico _enqueue_job"""
    from services.job_scheduler import _enqueue_job
    from utils.db_pool import db_pool
    
    # Mock de inserción exitosa
    mock_result = {"id": "job-123"}
    
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_result):
        job_id = await _enqueue_job("doc-1", "chunking", "doc-1:chunking:rev1", 3)
        assert job_id == "job-123"
    
    # Mock de conflicto (idempotencia)
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=None):
        job_id = await _enqueue_job("doc-1", "chunking", "doc-1:chunking:rev1", 3)
        assert job_id is None

@pytest.mark.asyncio
async def test_ocr_executor_chaining():
    """Test: OCR executor encola chunking tras éxito"""
    from services.job_scheduler import ocr_executor
    from services.ocr_worker import OCRWorker
    from utils.db_pool import db_pool
    
    # Mock del worker OCR
    with patch('services.ocr_worker.OCRWorker') as mock_worker_class:
        mock_worker = AsyncMock()
        mock_worker.process_document = AsyncMock(return_value={"revision": 1, "chars": 100})
        mock_worker_class.return_value = mock_worker
        
        # Mock de revisión
        mock_revision = {"revision": 1}
        
        # Mock de enqueue
        with patch('services.job_scheduler._enqueue_job', new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = "chunking-job-123"
            
            with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_revision):
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
                
                # Verificar que se llamó process_document
                mock_worker.process_document.assert_called_once()
                
                # Verificar que se encoló chunking
                mock_enqueue.assert_called_once_with("doc-1", "chunking", "doc-1:chunking:rev1", 3)

@pytest.mark.asyncio
async def test_chunking_executor():
    """Test: Ejecutor de chunking productivo"""
    from services.job_scheduler import chunking_executor
    from utils.db_pool import db_pool
    
    # Mock de revisión
    mock_revision = {
        "revision": 1,
        "content": "Este es un texto de prueba para chunking. " * 50,  # Texto largo
        "workspace_id": "ws-1",
        "title": "Test Document"
    }
    
    # Mock de inserción de chunks
    with patch('services.job_scheduler._insert_chunks', new_callable=AsyncMock) as mock_insert:
        mock_insert.return_value = 5  # 5 chunks insertados
        
        # Mock de enqueue embedding
        with patch('services.job_scheduler._enqueue_job', new_callable=AsyncMock) as mock_enqueue:
            mock_enqueue.return_value = "embedding-job-123"
            
            with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_revision):
                # Job de prueba
                test_job = {
                    "id": "job-1",
                    "document_id": "doc-1"
                }
                
                # Ejecutar
                await chunking_executor(test_job)
                
                # Verificar que se insertaron chunks
                mock_insert.assert_called_once()
                args = mock_insert.call_args[0]
                assert args[0] == "doc-1"  # document_id
                assert args[1] == "ws-1"   # workspace_id
                assert len(args[2]) > 0    # chunks
                assert args[3] == 1        # revision
                
                # Verificar que se encoló embedding
                mock_enqueue.assert_called_once_with("doc-1", "embedding", "doc-1:embedding:rev1", 3)

@pytest.mark.asyncio
async def test_chunk_text_function():
    """Test: Función de chunking de texto"""
    from services.job_scheduler import _chunk_text
    
    # Texto de prueba
    text = "Este es un texto de prueba para chunking. " * 20
    
    # Chunking con tamaño pequeño para testing
    chunks = _chunk_text(text, size=100, overlap=20)
    
    assert len(chunks) > 1
    assert all(len(chunk) <= 100 for chunk in chunks)
    assert all(chunk.strip() for chunk in chunks)  # No chunks vacíos

@pytest.mark.asyncio
async def test_embedding_executor():
    """Test: Ejecutor de embedding productivo"""
    from services.job_scheduler import embedding_executor
    from utils.db_pool import db_pool
    from utils.ollama_embeddings import OllamaEmbeddings
    
    # Mock de chunks sin embedding
    mock_chunks = [
        {"id": "chunk-1", "text": "Texto 1", "workspace_id": "ws-1"},
        {"id": "chunk-2", "text": "Texto 2", "workspace_id": "ws-1"}
    ]
    
    # Mock de inserción de embeddings
    with patch('services.job_scheduler._insert_embeddings', new_callable=AsyncMock) as mock_insert:
        mock_insert.return_value = 2  # 2 embeddings insertados
        
        # Mock de OllamaEmbeddings
        with patch('utils.ollama_embeddings.OllamaEmbeddings') as mock_embedder_class:
            mock_embedder = AsyncMock()
            mock_embedder.generate_embedding = AsyncMock(return_value=[0.1] * 10)
            mock_embedder_class.return_value = mock_embedder
            
            with patch('utils.db_pool.db_pool.execute_query', return_value=mock_chunks):
                # Job de prueba
                test_job = {
                    "id": "job-1",
                    "document_id": "doc-1"
                }
                
                # Ejecutar
                await embedding_executor(test_job)
                
                # Verificar que se generaron embeddings
                assert mock_embedder.generate_embedding.call_count == 2
                
                # Verificar que se insertaron embeddings
                mock_insert.assert_called_once()
                args = mock_insert.call_args[0]
                assert args[0] == "ws-1"  # workspace_id
                assert len(args[1]) == 2  # rows con embeddings

@pytest.mark.asyncio
async def test_embedding_executor_no_pending():
    """Test: Ejecutor de embedding sin chunks pendientes"""
    from services.job_scheduler import embedding_executor
    
    # Mock de chunks vacíos
    with patch('utils.db_pool.db_pool.execute_query', return_value=[]):
        # Job de prueba
        test_job = {
            "id": "job-1",
            "document_id": "doc-1"
        }
        
        # Ejecutar
        await embedding_executor(test_job)
        
        # No debería fallar, solo loggear que no hay nada pendiente

@pytest.mark.asyncio
async def test_get_latest_revision():
    """Test: Obtener última revisión"""
    from services.job_scheduler import _get_latest_revision
    from utils.db_pool import db_pool
    
    # Mock de revisión
    mock_revision = {
        "revision": 2,
        "content": "Contenido de la revisión",
        "workspace_id": "ws-1",
        "title": "Test Document"
    }
    
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=mock_revision):
        result = await _get_latest_revision("doc-1")
        assert result["revision"] == 2
        assert result["workspace_id"] == "ws-1"

@pytest.mark.asyncio
async def test_get_chunks_without_embedding():
    """Test: Obtener chunks sin embedding"""
    from services.job_scheduler import _get_chunks_without_embedding
    from utils.db_pool import db_pool
    
    # Mock de chunks
    mock_chunks = [
        {"id": "chunk-1", "text": "Texto 1", "workspace_id": "ws-1"},
        {"id": "chunk-2", "text": "Texto 2", "workspace_id": "ws-1"}
    ]
    
    with patch('utils.db_pool.db_pool.execute_query', return_value=mock_chunks):
        result = await _get_chunks_without_embedding("doc-1", 100)
        assert len(result) == 2
        assert result[0]["id"] == "chunk-1"

@pytest.mark.asyncio
async def test_pipeline_idempotency():
    """Test: Idempotencia del pipeline completo"""
    from services.job_scheduler import _enqueue_job
    from utils.db_pool import db_pool
    
    # Mock de conflicto (idempotencia)
    with patch('utils.db_pool.db_pool.execute_query_single', return_value=None):
        # Primera inserción
        job_id1 = await _enqueue_job("doc-1", "chunking", "doc-1:chunking:rev1", 3)
        
        # Segunda inserción con mismo external_key
        job_id2 = await _enqueue_job("doc-1", "chunking", "doc-1:chunking:rev1", 3)
        
        # Ambas deberían retornar None por conflicto
        assert job_id1 is None
        assert job_id2 is None

@pytest.mark.asyncio
async def test_pipeline_metrics():
    """Test: Métricas del pipeline"""
    from services.metrics import jobs_processed_total, job_duration_seconds, job_retries_total
    
    # Test métricas básicas
    jobs_processed_total.labels(job_type="chunking", status="completed").inc()
    job_duration_seconds.labels(job_type="embedding", status="completed").observe(1.5)
    job_retries_total.labels(job_type="chunking").inc()
    
    # Verificar que las métricas se pueden acceder
    assert jobs_processed_total._metrics is not None
    assert job_duration_seconds._metrics is not None
    assert job_retries_total._metrics is not None

@pytest.mark.asyncio
async def test_admin_endpoints_pipeline():
    """Test: Endpoints admin funcionan con pipeline"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Test stats con pipeline
        response = await client.get(
            "/admin/jobs/stats",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "job_stats" in response.json()
        assert "scheduler_stats" in response.json()
        
        # Test DLQ
        response = await client.get(
            "/admin/jobs/dlq",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert "items" in response.json()

if __name__ == "__main__":
    # Ejecutar tests básicos
    print("🧪 Ejecutando tests de Sprint 3.1...")
    
    try:
        # Test de helper
        asyncio.run(test_enqueue_job_helper())
        print("✅ Test de helper _enqueue_job: PASSED")
        
        # Test de chunking
        asyncio.run(test_chunk_text_function())
        print("✅ Test de chunking de texto: PASSED")
        
        # Test de idempotencia
        asyncio.run(test_pipeline_idempotency())
        print("✅ Test de idempotencia: PASSED")
        
        # Test de métricas
        asyncio.run(test_pipeline_metrics())
        print("✅ Test de métricas: PASSED")
        
        print("\n🎉 Todos los tests básicos del pipeline pasaron!")
        
    except Exception as e:
        print(f"❌ Error en tests: {e}")
        raise
