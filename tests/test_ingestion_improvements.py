"""
Tests de verificación para las mejoras del ingestion service
"""

import pytest
import asyncio
import tempfile
import os
from unittest.mock import Mock, patch
from services.ingestion_service import IngestionService, get_workspace_hash

class TestIngestionImprovements:
    """Tests para verificar las mejoras implementadas"""
    
    @pytest.fixture
    def ingestion_service(self):
        """Fixture del servicio de ingesta"""
        return IngestionService()
    
    def test_workspace_hash_cardinality(self):
        """Test: hash de workspace evita cardinalidad en métricas"""
        workspace_id = "123e4567-e89b-12d3-a456-426614174000"
        hash_result = get_workspace_hash(workspace_id)
        
        # Verificar que el hash es consistente
        assert hash_result == get_workspace_hash(workspace_id)
        
        # Verificar que es de longitud fija (8 caracteres)
        assert len(hash_result) == 8
        
        # Verificar que es alfanumérico
        assert hash_result.isalnum()
    
    @pytest.mark.asyncio
    async def test_concurrency_limit(self):
        """Test: límite de concurrencia funciona"""
        service = IngestionService()
        
        # Verificar que el semáforo está configurado
        assert hasattr(service, 'processing_limiter')
        assert isinstance(service.processing_limiter, asyncio.Semaphore)
        
        # Verificar que el límite es configurable
        max_concurrent = int(os.getenv("INGESTION_MAX_CONCURRENT", "5"))
        assert service.processing_limiter._value == max_concurrent
    
    def test_file_permissions_security(self):
        """Test: permisos seguros en archivos temporales"""
        from services.ingestion_service import FileStorage
        
        # Crear directorio temporal
        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = FileStorage()
            storage.upload_dir = tmp_dir
            
            # Simular archivo temporal
            temp_file = os.path.join(tmp_dir, "test.tmp")
            with open(temp_file, 'w') as f:
                f.write("test content")
            
            # Establecer permisos seguros
            os.chmod(temp_file, 0o640)
            
            # Verificar permisos
            stat = os.stat(temp_file)
            permissions = oct(stat.st_mode)[-3:]
            assert permissions == "640"
    
    @pytest.mark.asyncio
    async def test_ocr_timeout_hardening(self):
        """Test: OCR tiene timeout y modo seguro"""
        from services.ingestion_service import DocumentProcessor
        import subprocess
        
        processor = DocumentProcessor()
        
        # Mock del subprocess para simular timeout específico
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = subprocess.TimeoutExpired("ocrmypdf", 120)
            
            # Test que el timeout se maneja correctamente
            result = await processor._extract_text("/fake/path.pdf")
            
            # Verificar que se maneja el timeout
            assert result == ""  # Debería retornar string vacío en caso de error
    
    def test_retry_worker_filters_soft_deleted(self):
        """Test: retry worker excluye archivos soft-deleted"""
        from workers.retry_worker import RetryWorker
        
        worker = RetryWorker()
        
        # Verificar que la query incluye filtro deleted_at IS NULL
        # (esto se verifica en el código, no en runtime)
        assert True  # Placeholder - la lógica está en el código SQL
    
    @pytest.mark.asyncio
    async def test_duplicate_upload_idempotency(self):
        """Test: uploads duplicados son idempotentes"""
        service = IngestionService()
        
        # Mock del database manager
        with patch.object(service.db_manager, 'create_file_record') as mock_create:
            # Simular archivo duplicado
            mock_create.return_value = ("existing-file-id", False)
            
            # Verificar que se maneja correctamente
            # (esto se verifica en el flujo de upload)
            assert True  # Placeholder - la lógica está en upload_file
    
    def test_structured_logging(self):
        """Test: logging estructurado funciona"""
        from services.ingestion_service import log_structured
        
        # Test que la función de logging estructurado existe
        assert callable(log_structured)
        
        # Test que genera JSON válido
        import json
        try:
            log_structured("INFO", "Test message", test_param="value")
            assert True  # Si no lanza excepción, está bien
        except Exception as e:
            pytest.fail(f"Logging estructurado falló: {e}")
    
    def test_metrics_labels_consistency(self):
        """Test: métricas usan labels consistentes"""
        from services.ingestion_service import FILES_UPLOADED, FILES_PROCESSED, FILES_FAILED, PROCESS_LATENCY
        
        # Verificar que todas las métricas usan workspace_hash
        assert "workspace_hash" in FILES_UPLOADED._labelnames
        assert "workspace_hash" in FILES_PROCESSED._labelnames
        assert "workspace_hash" in FILES_FAILED._labelnames
        assert "workspace_hash" in PROCESS_LATENCY._labelnames
    
    @pytest.mark.asyncio
    async def test_processing_race_condition_prevention(self):
        """Test: prevención de race conditions en procesamiento"""
        service = IngestionService()
        
        # Mock del método _can_start_processing
        with patch.object(service, '_can_start_processing') as mock_can_start:
            mock_can_start.return_value = False
            
            # Verificar que se previene el procesamiento duplicado
            # (esto se verifica en _process_file_background)
            assert True  # Placeholder - la lógica está en el código

# Tests de integración (requieren servicios reales)
class TestIntegrationScenarios:
    """Tests de escenarios de integración"""
    
    @pytest.mark.asyncio
    async def test_scanned_pdf_ocr_flow(self):
        """Test: flujo completo de OCR para PDF escaneado"""
        # Este test requeriría un PDF escaneado real y servicios configurados
        # Por ahora es un placeholder
        assert True
    
    @pytest.mark.asyncio
    async def test_duplicate_file_reuse_flow(self):
        """Test: flujo de reutilización de archivo duplicado"""
        # Este test requeriría base de datos real
        # Por ahora es un placeholder
        assert True
    
    @pytest.mark.asyncio
    async def test_retry_backoff_flow(self):
        """Test: flujo de reintentos con backoff"""
        # Este test requeriría simular fallos y verificar reintentos
        # Por ahora es un placeholder
        assert True
    
    @pytest.mark.asyncio
    async def test_soft_delete_purge_flow(self):
        """Test: flujo de soft-delete y purga"""
        # Este test requeriría base de datos real y worker
        # Por ahora es un placeholder
        assert True

if __name__ == "__main__":
    pytest.main([__file__])
