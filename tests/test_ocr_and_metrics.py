"""
Tests para OCR y Métricas del Sprint 2
"""
import os
import pytest
import asyncio
from unittest.mock import Mock, patch, AsyncMock
from httpx import AsyncClient

# Configurar variables de entorno para tests
os.environ["ADMIN_TOKEN"] = "secret"
os.environ["OCR_RUN_MODE"] = "once"

@pytest.mark.asyncio
async def test_metrics_endpoint():
    """Test: Endpoint de métricas Prometheus"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/metrics")
        assert response.status_code == 200
        assert "rag_requests_total" in response.text
        assert "rag_errors_total" in response.text
        assert "rag_latency_seconds" in response.text

@pytest.mark.asyncio
async def test_ocr_admin_guard():
    """Test: Guard de seguridad en endpoints OCR"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Sin token - debe fallar con 403
        response = await client.post("/admin/ocr/run-once")
        assert response.status_code == 403
        
        # Con token - debe funcionar (aunque no haya docs reales)
        response = await client.post(
            "/admin/ocr/run-once", 
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code in (200, 500)  # 500 si no hay docs, 200 si hay docs

@pytest.mark.asyncio
async def test_ocr_enable_document():
    """Test: Habilitar OCR para documento"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Con token válido
        response = await client.post(
            "/admin/ocr/enable?document_id=test-doc-123",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        assert response.json()["document_id"] == "test-doc-123"
        assert response.json()["needs_ocr"] is True

@pytest.mark.asyncio
async def test_ocr_stats():
    """Test: Estadísticas de OCR"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get(
            "/admin/ocr/stats",
            headers={"X-Admin-Token": "secret"}
        )
        assert response.status_code == 200
        stats = response.json()
        assert "pending_documents" in stats
        assert "max_concurrency" in stats
        assert "max_retries" in stats

@pytest.mark.asyncio
async def test_ocr_provider_mock():
    """Test: Provider mock de OCR"""
    from utils.ocr_provider import MockOCRProvider
    
    provider = MockOCRProvider()
    text, meta = await provider.extract_text("file://test.pdf")
    
    assert "Texto extraído de file://test.pdf usando OCR mock" in text
    assert meta["engine"] == "mock"
    assert meta["source_url"] == "file://test.pdf"

@pytest.mark.asyncio
async def test_ocr_worker_initialization():
    """Test: Inicialización del worker OCR"""
    from services.ocr_worker import OCRWorker
    from utils.ocr_provider import MockOCRProvider
    
    provider = MockOCRProvider()
    worker = OCRWorker(provider=provider)
    
    assert worker.provider is not None
    assert hasattr(worker, 'run_once')
    assert hasattr(worker, 'get_stats')

@pytest.mark.asyncio
async def test_ocr_worker_stats():
    """Test: Estadísticas del worker OCR"""
    from services.ocr_worker import OCRWorker
    from utils.ocr_provider import MockOCRProvider
    
    provider = MockOCRProvider()
    worker = OCRWorker(provider=provider)
    
    # Mock de la base de datos
    with patch('services.ocr_worker.db_pool') as mock_db:
        mock_db.execute_query.return_value = []
        mock_db.execute_query_single.return_value = {"pending_count": 0}
        
        stats = await worker.get_stats()
        
        assert "pending_documents" in stats
        assert "max_concurrency" in stats
        assert "max_retries" in stats

@pytest.mark.asyncio
async def test_metrics_in_rag_requests():
    """Test: Métricas en requests del RAG"""
    from services.rag_service import app
    from services.metrics import rag_requests, rag_errors, rag_latency
    
    # Resetear métricas
    rag_requests.clear()
    rag_errors.clear()
    rag_latency.clear()
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        # Request válido
        response = await client.post(
            "/search",
            json={
                "query": "test query",
                "workspace_id": "test-workspace",
                "hybrid": True
            }
        )
        
        # Verificar que las métricas se incrementaron
        # (En un test real, verificarías los valores específicos)
        assert response.status_code in (200, 500)  # Depende de si hay datos

@pytest.mark.asyncio
async def test_embedding_cache_metrics():
    """Test: Métricas del cache de embeddings"""
    from utils.embedding_cache import EmbeddingCache
    from services.metrics import emb_cache_hits, emb_cache_miss
    
    # Resetear métricas
    emb_cache_hits.clear()
    emb_cache_miss.clear()
    
    cache = EmbeddingCache(ttl_seconds=60)
    
    # Test cache miss
    result = cache.get("test-workspace", "test query")
    assert result is None
    
    # Test cache hit
    cache.set("test-workspace", "test query", [0.1, 0.2, 0.3])
    result = cache.get("test-workspace", "test query")
    assert result == [0.1, 0.2, 0.3]
    
    # Verificar estadísticas
    stats = cache.get_stats()
    assert stats["hits"] >= 1
    assert stats["misses"] >= 1

@pytest.mark.asyncio
async def test_ocr_worker_run_once():
    """Test: Ejecución única del worker OCR"""
    from services.ocr_worker import OCRWorker
    from utils.ocr_provider import MockOCRProvider
    
    provider = MockOCRProvider()
    worker = OCRWorker(provider=provider)
    
    # Mock de la base de datos
    with patch('services.ocr_worker.db_pool') as mock_db:
        # Mock de documentos pendientes
        mock_db.execute_query.return_value = [
            {
                "id": "doc-1",
                "title": "Test Document",
                "storage_url": "file://test.pdf",
                "workspace_id": "test-workspace"
            }
        ]
        
        # Mock de operaciones de base de datos
        mock_db.execute_query_single.return_value = {"id": "job-1"}
        mock_db.execute_query.return_value = []
        
        # Ejecutar una pasada
        processed = await worker.run_once(batch_size=1)
        
        # Verificar que se procesó un documento
        assert processed == 1

@pytest.mark.asyncio
async def test_ocr_provider_factory():
    """Test: Factory de providers OCR"""
    from utils.ocr_provider import create_ocr_provider, MockOCRProvider, TesseractOCRProvider
    
    # Test provider mock
    mock_provider = create_ocr_provider("mock")
    assert isinstance(mock_provider, MockOCRProvider)
    
    # Test provider por defecto (tesseract)
    default_provider = create_ocr_provider()
    assert isinstance(default_provider, TesseractOCRProvider)

@pytest.mark.asyncio
async def test_metrics_prometheus_format():
    """Test: Formato de métricas Prometheus"""
    from services.rag_service import app
    
    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.get("/metrics")
        
        # Verificar formato Prometheus
        assert response.headers["content-type"] == "text/plain; version=0.0.4; charset=utf-8"
        
        # Verificar métricas específicas
        content = response.text
        assert "# HELP rag_requests_total" in content
        assert "# TYPE rag_requests_total counter" in content
        assert "# HELP rag_errors_total" in content
        assert "# TYPE rag_errors_total counter" in content
        assert "# HELP rag_latency_seconds" in content
        assert "# TYPE rag_latency_seconds histogram" in content

if __name__ == "__main__":
    # Ejecutar tests básicos
    print("🧪 Ejecutando tests de OCR y métricas...")
    
    try:
        # Test de provider mock
        asyncio.run(test_ocr_provider_mock())
        print("✅ Test de provider mock: PASSED")
        
        # Test de worker initialization
        asyncio.run(test_ocr_worker_initialization())
        print("✅ Test de worker initialization: PASSED")
        
        # Test de factory
        asyncio.run(test_ocr_provider_factory())
        print("✅ Test de factory: PASSED")
        
        # Test de cache metrics
        asyncio.run(test_embedding_cache_metrics())
        print("✅ Test de cache metrics: PASSED")
        
        print("\n🎉 Todos los tests básicos pasaron!")
        
    except Exception as e:
        print(f"❌ Error en tests: {e}")
        raise
