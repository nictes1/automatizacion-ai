-- OCR y Métricas para Sprint 2
-- Ejecutar después de 04_fixups.sql

-- 1. Índices para OCR
CREATE INDEX IF NOT EXISTS idx_documents_ocr_pending
ON pulpo.documents (needs_ocr, ocr_processed) 
WHERE needs_ocr = true AND ocr_processed = false AND deleted_at IS NULL;

-- 2. Índices para jobs de OCR
CREATE INDEX IF NOT EXISTS idx_processing_jobs_ocr
ON pulpo.processing_jobs (job_type, status, retries);

-- 3. Asegurar columna storage_url en documents
DO $$
BEGIN
  IF NOT EXISTS (
     SELECT 1 FROM information_schema.columns
     WHERE table_schema='pulpo' AND table_name='documents' AND column_name='storage_url'
  ) THEN
    ALTER TABLE pulpo.documents ADD COLUMN storage_url TEXT;
    COMMENT ON COLUMN pulpo.documents.storage_url IS 'Ubicación del archivo para OCR (file://, s3://, gs://)';
  END IF;
END $$;

-- 4. Índice para storage_url
CREATE INDEX IF NOT EXISTS idx_documents_storage_url
ON pulpo.documents (storage_url) WHERE storage_url IS NOT NULL;

-- 5. Vista para documentos pendientes de OCR
CREATE OR REPLACE VIEW pulpo.ocr_pending_documents AS
SELECT 
    d.id,
    d.title,
    d.storage_url,
    d.workspace_id,
    d.created_at,
    d.needs_ocr,
    d.ocr_processed
FROM pulpo.documents d
LEFT JOIN pulpo.processing_jobs j
  ON j.document_id = d.id 
  AND j.job_type = 'ocr' 
  AND j.status IN ('pending', 'processing')
WHERE d.needs_ocr = true
  AND d.ocr_processed = false
  AND d.deleted_at IS NULL
  AND j.id IS NULL;

-- 6. Función para estadísticas de OCR
CREATE OR REPLACE FUNCTION pulpo.get_ocr_stats()
RETURNS TABLE(
    total_documents BIGINT,
    needs_ocr BIGINT,
    ocr_processed BIGINT,
    ocr_pending BIGINT,
    ocr_failed BIGINT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        (SELECT COUNT(*) FROM pulpo.documents WHERE deleted_at IS NULL) as total_documents,
        (SELECT COUNT(*) FROM pulpo.documents WHERE needs_ocr = true AND deleted_at IS NULL) as needs_ocr,
        (SELECT COUNT(*) FROM pulpo.documents WHERE ocr_processed = true AND deleted_at IS NULL) as ocr_processed,
        (SELECT COUNT(*) FROM pulpo.ocr_pending_documents) as ocr_pending,
        (SELECT COUNT(*) FROM pulpo.processing_jobs WHERE job_type = 'ocr' AND status = 'failed') as ocr_failed;
END;
$$ LANGUAGE plpgsql;

-- 7. Función para limpiar jobs de OCR antiguos
CREATE OR REPLACE FUNCTION pulpo.cleanup_old_ocr_jobs(retention_days INT DEFAULT 30)
RETURNS INT AS $$
DECLARE
    deleted_count INT;
BEGIN
    DELETE FROM pulpo.processing_jobs
    WHERE job_type = 'ocr'
      AND status IN ('completed', 'failed')
      AND updated_at < now() - (retention_days || ' days')::INTERVAL;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 8. Trigger para actualizar métricas cuando se procesa OCR
CREATE OR REPLACE FUNCTION pulpo.update_ocr_metrics()
RETURNS TRIGGER AS $$
BEGIN
    -- Log de procesamiento OCR
    IF NEW.ocr_processed = true AND OLD.ocr_processed = false THEN
        RAISE NOTICE 'Documento % procesado por OCR', NEW.id;
    END IF;
    
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_ocr_metrics
    AFTER UPDATE ON pulpo.documents
    FOR EACH ROW
    WHEN (NEW.ocr_processed != OLD.ocr_processed)
    EXECUTE FUNCTION pulpo.update_ocr_metrics();

-- 9. Vista para métricas de Prometheus (opcional)
CREATE OR REPLACE VIEW pulpo.prometheus_metrics AS
SELECT 
    'rag_documents_total' as metric_name,
    workspace_id as label_workspace,
    'active' as label_status,
    COUNT(*) as metric_value
FROM pulpo.documents
WHERE deleted_at IS NULL
GROUP BY workspace_id
UNION ALL
SELECT 
    'rag_documents_total' as metric_name,
    workspace_id as label_workspace,
    'deleted' as label_status,
    COUNT(*) as metric_value
FROM pulpo.documents
WHERE deleted_at IS NOT NULL
GROUP BY workspace_id
UNION ALL
SELECT 
    'rag_documents_total' as metric_name,
    workspace_id as label_workspace,
    'needs_ocr' as label_status,
    COUNT(*) as metric_value
FROM pulpo.documents
WHERE needs_ocr = true AND deleted_at IS NULL
GROUP BY workspace_id;

-- 10. Comentarios para documentación
COMMENT ON VIEW pulpo.ocr_pending_documents IS 'Documentos pendientes de procesamiento OCR';
COMMENT ON FUNCTION pulpo.get_ocr_stats() IS 'Estadísticas de procesamiento OCR';
COMMENT ON FUNCTION pulpo.cleanup_old_ocr_jobs(INT) IS 'Limpia jobs de OCR antiguos';
COMMENT ON COLUMN pulpo.documents.storage_url IS 'URL del archivo para procesamiento OCR';

-- 11. Ejecutar análisis para optimizar
ANALYZE pulpo.documents;
ANALYZE pulpo.processing_jobs;

-- 12. Mostrar estadísticas iniciales
SELECT * FROM pulpo.get_ocr_stats();

-- 13. Mostrar resumen de Sprint 2
SELECT 
    'Sprint 2 - OCR + Métricas' as feature,
    'OCR asíncrono + Prometheus metrics' as description,
    now() as completed_at;
