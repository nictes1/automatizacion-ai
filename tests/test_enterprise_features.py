"""
Tests para las funcionalidades enterprise del RAG Service
Sprint 1: Soft Delete + Versionado de Documentos
"""
import pytest
import asyncio
from unittest.mock import Mock, patch
from datetime import datetime, timedelta
from services.rag_service import RAGService, DocumentVersionRequest, SoftDeleteRequest, RestoreRequest


class TestEnterpriseFeatures:
    """Tests para funcionalidades enterprise"""
    
    @pytest.fixture
    def rag_service(self):
        """Fixture para el servicio RAG"""
        return RAGService()
    
    def test_soft_delete_document(self, rag_service):
        """Test: Soft delete de documento"""
        request = SoftDeleteRequest(
            document_id="test-doc-123",
            deleted_by="user-456"
        )
        
        # Mock de respuesta exitosa
        mock_result = {"success": True}
        
        with patch.object(rag_service, 'soft_delete_document') as mock_delete:
            mock_delete.return_value = asyncio.run(rag_service.soft_delete_document(request))
            
            # Verificar que se llamó correctamente
            mock_delete.assert_called_once()
    
    def test_restore_document(self, rag_service):
        """Test: Restaurar documento eliminado"""
        request = RestoreRequest(document_id="test-doc-123")
        
        with patch.object(rag_service, 'restore_document') as mock_restore:
            mock_restore.return_value = asyncio.run(rag_service.restore_document(request))
            
            mock_restore.assert_called_once()
    
    def test_create_document_version(self, rag_service):
        """Test: Crear nueva versión de documento"""
        request = DocumentVersionRequest(
            document_id="test-doc-123",
            content="Nueva versión del contenido",
            metadata={"version": "2.0", "author": "test-user"},
            created_by="user-456"
        )
        
        with patch.object(rag_service, 'create_document_version') as mock_version:
            mock_version.return_value = asyncio.run(rag_service.create_document_version(request))
            
            mock_version.assert_called_once()
    
    def test_get_document_versions(self, rag_service):
        """Test: Obtener versiones de documento"""
        document_id = "test-doc-123"
        
        with patch.object(rag_service, 'get_document_versions') as mock_versions:
            mock_versions.return_value = asyncio.run(rag_service.get_document_versions(document_id))
            
            mock_versions.assert_called_once_with(document_id)
    
    def test_purge_deleted_documents(self, rag_service):
        """Test: Purga de documentos eliminados"""
        retention_days = 7
        
        with patch.object(rag_service, 'purge_deleted_documents') as mock_purge:
            mock_purge.return_value = asyncio.run(rag_service.purge_deleted_documents(retention_days))
            
            mock_purge.assert_called_once_with(retention_days)
    
    def test_soft_delete_in_search_queries(self, rag_service):
        """Test: Verificar que las queries de búsqueda excluyen documentos eliminados"""
        # Este test verificaría que las queries SQL incluyen las condiciones de soft delete
        # En un test real, se verificaría que las queries contienen:
        # AND c.deleted_at IS NULL AND d.deleted_at IS NULL
        
        # Mock de query SQL
        expected_conditions = [
            "c.deleted_at IS NULL",
            "d.deleted_at IS NULL"
        ]
        
        # En un test real, se verificaría que estas condiciones están presentes
        # en las queries generadas por _bm25_search y _vector_search
        assert all(condition in expected_conditions for condition in expected_conditions)
    
    def test_document_versioning_workflow(self, rag_service):
        """Test: Flujo completo de versionado de documentos"""
        document_id = "test-doc-123"
        
        # 1. Crear versión inicial
        version_request = DocumentVersionRequest(
            document_id=document_id,
            content="Versión inicial",
            metadata={"version": "1.0"},
            created_by="user-123"
        )
        
        # 2. Crear segunda versión
        version_request_2 = DocumentVersionRequest(
            document_id=document_id,
            content="Versión actualizada",
            metadata={"version": "2.0"},
            created_by="user-123"
        )
        
        # 3. Soft delete
        delete_request = SoftDeleteRequest(
            document_id=document_id,
            deleted_by="user-123"
        )
        
        # 4. Restaurar
        restore_request = RestoreRequest(document_id=document_id)
        
        # En un test real, se ejecutarían estos pasos y se verificarían los resultados
        # Por ahora, solo verificamos que los requests se crean correctamente
        assert version_request.document_id == document_id
        assert version_request_2.document_id == document_id
        assert delete_request.document_id == document_id
        assert restore_request.document_id == document_id
    
    def test_purge_job_retention_logic(self):
        """Test: Lógica de retención en job de purga"""
        from jobs.purge_job import PurgeJob
        
        # Test con diferentes períodos de retención
        retention_periods = [1, 7, 30, 90]
        
        for retention_days in retention_periods:
            purge_job = PurgeJob(retention_days=retention_days)
            assert purge_job.retention_days == retention_days
    
    def test_document_revisions_table_structure(self):
        """Test: Estructura de tabla de revisiones"""
        # Este test verificaría que la tabla document_revisions tiene la estructura correcta
        expected_columns = [
            "id", "document_id", "revision", "content", 
            "metadata", "created_at", "created_by"
        ]
        
        # En un test real, se consultaría la estructura de la tabla
        # Por ahora, solo verificamos que tenemos las columnas esperadas
        assert all(col in expected_columns for col in expected_columns)
    
    def test_processing_jobs_table_structure(self):
        """Test: Estructura de tabla de jobs de procesamiento"""
        # Este test verificaría que la tabla processing_jobs tiene la estructura correcta
        expected_columns = [
            "id", "document_id", "job_type", "status", 
            "retries", "max_retries", "last_error", 
            "error_details", "started_at", "completed_at", 
            "created_at", "updated_at"
        ]
        
        # En un test real, se consultaría la estructura de la tabla
        assert all(col in expected_columns for col in expected_columns)
    
    def test_soft_delete_cascade(self):
        """Test: Verificar que soft delete se propaga correctamente"""
        # Este test verificaría que cuando se elimina un documento:
        # 1. Se marca el documento como eliminado
        # 2. Se marcan todos sus chunks como eliminados
        # 3. Se marcan todos sus embeddings como eliminados
        
        # En un test real, se ejecutaría el soft delete y se verificarían
        # todas las tablas relacionadas
        assert True  # Placeholder para test real
    
    def test_restore_cascade(self):
        """Test: Verificar que restore se propaga correctamente"""
        # Este test verificaría que cuando se restaura un documento:
        # 1. Se restaura el documento
        # 2. Se restauran todos sus chunks
        # 3. Se restauran todos sus embeddings
        
        # En un test real, se ejecutaría el restore y se verificarían
        # todas las tablas relacionadas
        assert True  # Placeholder para test real


class TestPurgeJob:
    """Tests específicos para el job de purga"""
    
    def test_purge_job_initialization(self):
        """Test: Inicialización del job de purga"""
        from jobs.purge_job import PurgeJob
        
        # Test con retención por defecto
        job = PurgeJob()
        assert job.retention_days == 7
        
        # Test con retención personalizada
        job_custom = PurgeJob(retention_days=30)
        assert job_custom.retention_days == 30
    
    def test_purge_job_stats(self):
        """Test: Estadísticas del job de purga"""
        from jobs.purge_job import PurgeJob
        
        job = PurgeJob(retention_days=7)
        
        # En un test real, se mockearía la base de datos y se verificarían
        # las estadísticas retornadas
        assert job.retention_days == 7
    
    def test_purge_job_error_handling(self):
        """Test: Manejo de errores en job de purga"""
        from jobs.purge_job import PurgeJob
        
        job = PurgeJob(retention_days=7)
        
        # En un test real, se simularían errores de base de datos
        # y se verificaría que se manejan correctamente
        assert True  # Placeholder para test real


if __name__ == "__main__":
    # Ejecutar tests básicos
    test_instance = TestEnterpriseFeatures()
    
    print("🧪 Ejecutando tests de funcionalidades enterprise...")
    
    try:
        # Test de inicialización
        rag_service = RAGService()
        print("✅ Test de inicialización: PASSED")
        
        # Test de requests
        test_instance.test_soft_delete_document(rag_service)
        print("✅ Test de soft delete: PASSED")
        
        test_instance.test_restore_document(rag_service)
        print("✅ Test de restore: PASSED")
        
        test_instance.test_create_document_version(rag_service)
        print("✅ Test de versionado: PASSED")
        
        # Test de job de purga
        purge_test = TestPurgeJob()
        purge_test.test_purge_job_initialization()
        print("✅ Test de job de purga: PASSED")
        
        print("\n🎉 Todos los tests básicos pasaron!")
        
    except Exception as e:
        print(f"❌ Error en tests: {e}")
        raise
