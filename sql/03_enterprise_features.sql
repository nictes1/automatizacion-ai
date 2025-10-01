-- Enterprise Features para RAG Service v2.0.0
-- Sprint 1: Soft Delete + Versionado de Documentos

-- 1. Soft Delete - Agregar columna deleted_at
ALTER TABLE pulpo.documents 
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL;

ALTER TABLE pulpo.chunks 
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL;

-- Índices para soft delete
CREATE INDEX IF NOT EXISTS idx_documents_deleted_at 
ON pulpo.documents (deleted_at) WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chunks_deleted_at 
ON pulpo.chunks (deleted_at) WHERE deleted_at IS NULL;

-- 2. Versionado de Documentos
CREATE TABLE IF NOT EXISTS pulpo.document_revisions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
    revision INT NOT NULL,
    content TEXT,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT now(),
    created_by UUID, -- Usuario que creó la revisión
    UNIQUE(document_id, revision)
);

-- Índices para versionado
CREATE INDEX IF NOT EXISTS idx_document_revisions_document_id 
ON pulpo.document_revisions (document_id);

CREATE INDEX IF NOT EXISTS idx_document_revisions_revision 
ON pulpo.document_revisions (document_id, revision DESC);

-- 3. OCR Support
ALTER TABLE pulpo.documents 
ADD COLUMN IF NOT EXISTS needs_ocr BOOLEAN DEFAULT false;

ALTER TABLE pulpo.documents 
ADD COLUMN IF NOT EXISTS ocr_processed BOOLEAN DEFAULT false;

-- 4. Processing Jobs para Reintentos
CREATE TABLE IF NOT EXISTS pulpo.processing_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    document_id UUID NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
    job_type VARCHAR(50) NOT NULL, -- 'ingestion', 'ocr', 'chunking'
    status VARCHAR(20) NOT NULL DEFAULT 'pending', -- 'pending', 'processing', 'completed', 'failed'
    retries INT DEFAULT 0,
    max_retries INT DEFAULT 3,
    last_error TEXT,
    error_details JSONB,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT now(),
    updated_at TIMESTAMP DEFAULT now()
);

-- Índices para processing jobs
CREATE INDEX IF NOT EXISTS idx_processing_jobs_status 
ON pulpo.processing_jobs (status);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_document_id 
ON pulpo.processing_jobs (document_id);

CREATE INDEX IF NOT EXISTS idx_processing_jobs_retries 
ON pulpo.processing_jobs (status, retries) WHERE status = 'failed' AND retries < max_retries;

-- 5. Función para obtener la última revisión de un documento
CREATE OR REPLACE FUNCTION pulpo.get_latest_revision(document_uuid UUID)
RETURNS INT AS $$
DECLARE
    latest_rev INT;
BEGIN
    SELECT COALESCE(MAX(revision), 0) INTO latest_rev
    FROM pulpo.document_revisions
    WHERE document_id = document_uuid;
    
    RETURN latest_rev;
END;
$$ LANGUAGE plpgsql;

-- 6. Función para crear nueva revisión
CREATE OR REPLACE FUNCTION pulpo.create_document_revision(
    doc_uuid UUID,
    content_text TEXT,
    metadata_json JSONB DEFAULT '{}',
    created_by_uuid UUID DEFAULT NULL
)
RETURNS INT AS $$
DECLARE
    new_revision INT;
BEGIN
    -- Obtener siguiente número de revisión
    SELECT COALESCE(MAX(revision), 0) + 1 INTO new_revision
    FROM pulpo.document_revisions
    WHERE document_id = doc_uuid;
    
    -- Insertar nueva revisión
    INSERT INTO pulpo.document_revisions (document_id, revision, content, metadata, created_by)
    VALUES (doc_uuid, new_revision, content_text, metadata_json, created_by_uuid);
    
    RETURN new_revision;
END;
$$ LANGUAGE plpgsql;

-- 7. Función para soft delete de documento
CREATE OR REPLACE FUNCTION pulpo.soft_delete_document(
    doc_uuid UUID,
    deleted_by_uuid UUID DEFAULT NULL
)
RETURNS BOOLEAN AS $$
BEGIN
    -- Marcar documento como eliminado
    UPDATE pulpo.documents 
    SET deleted_at = now()
    WHERE id = doc_uuid AND deleted_at IS NULL;
    
    -- Marcar chunks como eliminados
    UPDATE pulpo.chunks 
    SET deleted_at = now()
    WHERE document_id = doc_uuid AND deleted_at IS NULL;
    
    -- Marcar embeddings como eliminados (si existe la tabla)
    UPDATE pulpo.chunk_embeddings 
    SET deleted_at = now()
    WHERE chunk_id IN (
        SELECT id FROM pulpo.chunks WHERE document_id = doc_uuid
    ) AND deleted_at IS NULL;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- 8. Función para restaurar documento
CREATE OR REPLACE FUNCTION pulpo.restore_document(doc_uuid UUID)
RETURNS BOOLEAN AS $$
BEGIN
    -- Restaurar documento
    UPDATE pulpo.documents 
    SET deleted_at = NULL
    WHERE id = doc_uuid AND deleted_at IS NOT NULL;
    
    -- Restaurar chunks
    UPDATE pulpo.chunks 
    SET deleted_at = NULL
    WHERE document_id = doc_uuid AND deleted_at IS NOT NULL;
    
    -- Restaurar embeddings
    UPDATE pulpo.chunk_embeddings 
    SET deleted_at = NULL
    WHERE chunk_id IN (
        SELECT id FROM pulpo.chunks WHERE document_id = doc_uuid
    ) AND deleted_at IS NOT NULL;
    
    RETURN FOUND;
END;
$$ LANGUAGE plpgsql;

-- 9. Vista para documentos activos (sin soft delete)
CREATE OR REPLACE VIEW pulpo.active_documents AS
SELECT d.*, 
       pulpo.get_latest_revision(d.id) as latest_revision
FROM pulpo.documents d
WHERE d.deleted_at IS NULL;

-- 10. Vista para chunks activos
CREATE OR REPLACE VIEW pulpo.active_chunks AS
SELECT c.*, d.title as document_title
FROM pulpo.chunks c
JOIN pulpo.documents d ON c.document_id = d.id
WHERE c.deleted_at IS NULL AND d.deleted_at IS NULL;

-- 11. Job de purga nocturna (función)
CREATE OR REPLACE FUNCTION pulpo.purge_deleted_documents(retention_days INT DEFAULT 7)
RETURNS TABLE(deleted_count INT, purged_documents INT) AS $$
DECLARE
    cutoff_date TIMESTAMP;
    doc_count INT;
    purged_count INT;
BEGIN
    cutoff_date := now() - (retention_days || ' days')::INTERVAL;
    
    -- Contar documentos a purgar
    SELECT COUNT(*) INTO doc_count
    FROM pulpo.documents
    WHERE deleted_at IS NOT NULL AND deleted_at < cutoff_date;
    
    -- Eliminar chunks de documentos a purgar
    DELETE FROM pulpo.chunks
    WHERE document_id IN (
        SELECT id FROM pulpo.documents
        WHERE deleted_at IS NOT NULL AND deleted_at < cutoff_date
    );
    
    -- Eliminar embeddings de chunks purgados
    DELETE FROM pulpo.chunk_embeddings
    WHERE chunk_id NOT IN (SELECT id FROM pulpo.chunks);
    
    -- Eliminar revisiones de documentos a purgar
    DELETE FROM pulpo.document_revisions
    WHERE document_id IN (
        SELECT id FROM pulpo.documents
        WHERE deleted_at IS NOT NULL AND deleted_at < cutoff_date
    );
    
    -- Eliminar jobs de documentos a purgar
    DELETE FROM pulpo.processing_jobs
    WHERE document_id IN (
        SELECT id FROM pulpo.documents
        WHERE deleted_at IS NOT NULL AND deleted_at < cutoff_date
    );
    
    -- Finalmente, eliminar documentos
    DELETE FROM pulpo.documents
    WHERE deleted_at IS NOT NULL AND deleted_at < cutoff_date;
    
    purged_count := doc_count;
    
    RETURN QUERY SELECT doc_count, purged_count;
END;
$$ LANGUAGE plpgsql;

-- 12. Triggers para updated_at
CREATE OR REPLACE FUNCTION pulpo.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_processing_jobs_updated_at
    BEFORE UPDATE ON pulpo.processing_jobs
    FOR EACH ROW
    EXECUTE FUNCTION pulpo.update_updated_at_column();

-- 13. Comentarios para documentación
COMMENT ON TABLE pulpo.document_revisions IS 'Historial de versiones de documentos';
COMMENT ON TABLE pulpo.processing_jobs IS 'Jobs de procesamiento con reintentos';
COMMENT ON COLUMN pulpo.documents.deleted_at IS 'Timestamp de soft delete (NULL = activo)';
COMMENT ON COLUMN pulpo.documents.needs_ocr IS 'Indica si el documento requiere OCR';
COMMENT ON COLUMN pulpo.documents.ocr_processed IS 'Indica si el OCR fue procesado';
COMMENT ON FUNCTION pulpo.get_latest_revision(UUID) IS 'Obtiene el número de la última revisión de un documento';
COMMENT ON FUNCTION pulpo.create_document_revision(UUID, TEXT, JSONB, UUID) IS 'Crea una nueva revisión de documento';
COMMENT ON FUNCTION pulpo.soft_delete_document(UUID, UUID) IS 'Elimina un documento de forma soft (reversible)';
COMMENT ON FUNCTION pulpo.restore_document(UUID) IS 'Restaura un documento eliminado con soft delete';
COMMENT ON FUNCTION pulpo.purge_deleted_documents(INT) IS 'Purga documentos eliminados después de N días';

-- 14. Ejecutar análisis para optimizar
ANALYZE pulpo.documents;
ANALYZE pulpo.chunks;
ANALYZE pulpo.document_revisions;
ANALYZE pulpo.processing_jobs;

-- 15. Mostrar estadísticas
SELECT 
    'documents' as table_name,
    COUNT(*) as total_rows,
    COUNT(*) FILTER (WHERE deleted_at IS NULL) as active_rows,
    COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) as deleted_rows
FROM pulpo.documents
UNION ALL
SELECT 
    'chunks' as table_name,
    COUNT(*) as total_rows,
    COUNT(*) FILTER (WHERE deleted_at IS NULL) as active_rows,
    COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) as deleted_rows
FROM pulpo.chunks
UNION ALL
SELECT 
    'document_revisions' as table_name,
    COUNT(*) as total_rows,
    COUNT(*) as active_rows,
    0 as deleted_rows
FROM pulpo.document_revisions
UNION ALL
SELECT 
    'processing_jobs' as table_name,
    COUNT(*) as total_rows,
    COUNT(*) FILTER (WHERE status IN ('pending', 'processing', 'completed')) as active_rows,
    COUNT(*) FILTER (WHERE status = 'failed') as deleted_rows
FROM pulpo.processing_jobs;
