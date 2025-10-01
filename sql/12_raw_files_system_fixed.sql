-- =====================================================
-- Sistema de Archivos Crudos y Versiones - VERSIÓN CORREGIDA
-- =====================================================
-- Extiende el sistema de archivos para soportar:
-- 1. Archivos crudos con almacenamiento
-- 2. Sistema de versiones
-- 3. Metadatos por vertical y tipo de documento
-- 4. Borrado consistente
-- =====================================================

\set ON_ERROR_STOP on
SET search_path = public, pulpo;

-- =====================================================
-- 1. EXTENDER TABLA FILES EXISTENTE
-- =====================================================

-- Agregar columnas si no existen
DO $$ 
BEGIN
    -- Agregar columnas una por una para evitar errores
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'vertical') THEN
        ALTER TABLE pulpo.files ADD COLUMN vertical VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'document_type') THEN
        ALTER TABLE pulpo.files ADD COLUMN document_type VARCHAR(50);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'storage_uri') THEN
        ALTER TABLE pulpo.files ADD COLUMN storage_uri TEXT;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'mime_type') THEN
        ALTER TABLE pulpo.files ADD COLUMN mime_type VARCHAR(100);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'file_hash') THEN
        ALTER TABLE pulpo.files ADD COLUMN file_hash VARCHAR(64);
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'processing_status') THEN
        ALTER TABLE pulpo.files ADD COLUMN processing_status VARCHAR(20) DEFAULT 'uploaded';
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'files' AND column_name = 'deleted_at') THEN
        ALTER TABLE pulpo.files ADD COLUMN deleted_at TIMESTAMPTZ;
    END IF;
END $$;

-- Crear índices si no existen
CREATE INDEX IF NOT EXISTS idx_files_vertical ON pulpo.files(vertical);
CREATE INDEX IF NOT EXISTS idx_files_document_type ON pulpo.files(document_type);
CREATE INDEX IF NOT EXISTS idx_files_processing_status ON pulpo.files(processing_status);
CREATE INDEX IF NOT EXISTS idx_files_deleted_at ON pulpo.files(deleted_at);
CREATE INDEX IF NOT EXISTS idx_files_hash ON pulpo.files(file_hash);

-- =====================================================
-- 2. TABLA DE VERSIONES DE ARCHIVOS
-- =====================================================

CREATE TABLE IF NOT EXISTS pulpo.file_versions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES pulpo.files(id) ON DELETE CASCADE,
    version INTEGER NOT NULL DEFAULT 1,
    normalized_text_uri TEXT,
    parse_report JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES pulpo.users(id),
    
    UNIQUE(file_id, version)
);

-- Índices para versiones
CREATE INDEX IF NOT EXISTS idx_file_versions_file_id ON pulpo.file_versions(file_id);
CREATE INDEX IF NOT EXISTS idx_file_versions_version ON pulpo.file_versions(version);
CREATE INDEX IF NOT EXISTS idx_file_versions_created_at ON pulpo.file_versions(created_at);

-- =====================================================
-- 3. TABLA DE DOCUMENTOS LÓGICOS
-- =====================================================

CREATE TABLE IF NOT EXISTS pulpo.documents (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    file_id UUID NOT NULL REFERENCES pulpo.files(id) ON DELETE CASCADE,
    file_version_id UUID REFERENCES pulpo.file_versions(id) ON DELETE SET NULL,
    doc_path TEXT,
    title TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES pulpo.users(id)
);

-- Índices para documentos
CREATE INDEX IF NOT EXISTS idx_documents_workspace_id ON pulpo.documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_documents_file_id ON pulpo.documents(file_id);
CREATE INDEX IF NOT EXISTS idx_documents_file_version_id ON pulpo.documents(file_version_id);

-- =====================================================
-- 4. TABLA DE CHUNKS MEJORADA
-- =====================================================

-- Crear tabla file_chunks si no existe
CREATE TABLE IF NOT EXISTS pulpo.file_chunks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    file_id UUID NOT NULL REFERENCES pulpo.files(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    chunk_text TEXT NOT NULL,
    chunk_tokens INTEGER,
    chunk_metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Agregar columnas adicionales si no existen
DO $$ 
BEGIN
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'file_chunks' AND column_name = 'document_id') THEN
        ALTER TABLE pulpo.file_chunks ADD COLUMN document_id UUID REFERENCES pulpo.documents(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'file_chunks' AND column_name = 'file_version_id') THEN
        ALTER TABLE pulpo.file_chunks ADD COLUMN file_version_id UUID REFERENCES pulpo.file_versions(id) ON DELETE CASCADE;
    END IF;
    
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema = 'pulpo' AND table_name = 'file_chunks' AND column_name = 'position') THEN
        ALTER TABLE pulpo.file_chunks ADD COLUMN position INTEGER NOT NULL DEFAULT 0;
    END IF;
END $$;

-- Índices para chunks
CREATE INDEX IF NOT EXISTS idx_file_chunks_file_id ON pulpo.file_chunks(file_id);
CREATE INDEX IF NOT EXISTS idx_file_chunks_chunk_index ON pulpo.file_chunks(chunk_index);
CREATE INDEX IF NOT EXISTS idx_file_chunks_document_id ON pulpo.file_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_file_chunks_file_version_id ON pulpo.file_chunks(file_version_id);
CREATE INDEX IF NOT EXISTS idx_file_chunks_position ON pulpo.file_chunks(position);

-- =====================================================
-- 5. TABLA DE EMBEDDINGS
-- =====================================================

CREATE TABLE IF NOT EXISTS pulpo.embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES pulpo.file_chunks(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    model VARCHAR(100) NOT NULL,
    dim INTEGER NOT NULL,
    vector VECTOR(1536) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    UNIQUE(chunk_id, model)
);

-- Índices para embeddings
CREATE INDEX IF NOT EXISTS idx_embeddings_chunk_id ON pulpo.embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_workspace_id ON pulpo.embeddings(workspace_id);
CREATE INDEX IF NOT EXISTS idx_embeddings_model ON pulpo.embeddings(model);

-- =====================================================
-- 6. TABLA DE AUDITORÍA
-- =====================================================

CREATE TABLE IF NOT EXISTS pulpo.audit_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    event_type VARCHAR(50) NOT NULL,
    ref_id UUID,
    ref_type VARCHAR(50),
    payload JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES pulpo.users(id)
);

-- Índices para auditoría
CREATE INDEX IF NOT EXISTS idx_audit_events_workspace_id ON pulpo.audit_events(workspace_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_event_type ON pulpo.audit_events(event_type);
CREATE INDEX IF NOT EXISTS idx_audit_events_ref_id ON pulpo.audit_events(ref_id);
CREATE INDEX IF NOT EXISTS idx_audit_events_created_at ON pulpo.audit_events(created_at);

-- =====================================================
-- 7. FUNCIONES DE BORRADO CONSISTENTE
-- =====================================================

-- Función para eliminar archivo y todos sus datos relacionados
CREATE OR REPLACE FUNCTION pulpo.delete_file_cascade(file_uuid UUID, workspace_uuid UUID)
RETURNS JSONB AS $$
DECLARE
    file_record RECORD;
    deleted_chunks INTEGER := 0;
    deleted_embeddings INTEGER := 0;
    deleted_versions INTEGER := 0;
    deleted_documents INTEGER := 0;
    result JSONB;
BEGIN
    -- Obtener información del archivo
    SELECT * INTO file_record 
    FROM pulpo.files 
    WHERE id = file_uuid AND workspace_id = workspace_uuid AND deleted_at IS NULL;
    
    IF NOT FOUND THEN
        RETURN jsonb_build_object('error', 'Archivo no encontrado');
    END IF;
    
    -- Eliminar embeddings
    DELETE FROM pulpo.embeddings 
    WHERE chunk_id IN (
        SELECT fc.id FROM pulpo.file_chunks fc WHERE fc.file_id = file_uuid
    );
    GET DIAGNOSTICS deleted_embeddings = ROW_COUNT;
    
    -- Eliminar chunks
    DELETE FROM pulpo.file_chunks WHERE file_id = file_uuid;
    GET DIAGNOSTICS deleted_chunks = ROW_COUNT;
    
    -- Eliminar documentos
    DELETE FROM pulpo.documents WHERE file_id = file_uuid;
    GET DIAGNOSTICS deleted_documents = ROW_COUNT;
    
    -- Eliminar versiones
    DELETE FROM pulpo.file_versions WHERE file_id = file_uuid;
    GET DIAGNOSTICS deleted_versions = ROW_COUNT;
    
    -- Marcar archivo como eliminado (soft delete)
    UPDATE pulpo.files 
    SET deleted_at = NOW() 
    WHERE id = file_uuid;
    
    -- Registrar evento de auditoría
    INSERT INTO pulpo.audit_events (
        workspace_id, event_type, ref_id, ref_type, payload
    ) VALUES (
        workspace_uuid, 'delete_request', file_uuid, 'file',
        jsonb_build_object(
            'filename', file_record.original_filename,
            'deleted_chunks', deleted_chunks,
            'deleted_embeddings', deleted_embeddings,
            'deleted_versions', deleted_versions,
            'deleted_documents', deleted_documents
        )
    );
    
    -- Construir resultado
    result := jsonb_build_object(
        'success', true,
        'file_id', file_uuid,
        'filename', file_record.original_filename,
        'deleted_chunks', deleted_chunks,
        'deleted_embeddings', deleted_embeddings,
        'deleted_versions', deleted_versions,
        'deleted_documents', deleted_documents
    );
    
    RETURN result;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 8. VISTAS ÚTILES
-- =====================================================

-- Vista para archivos con información completa
CREATE OR REPLACE VIEW pulpo.v_files_complete AS
SELECT 
    f.id,
    f.workspace_id,
    f.original_filename,
    f.file_size,
    f.vertical,
    f.document_type,
    f.mime_type,
    f.processing_status,
    f.created_at,
    f.deleted_at,
    COUNT(fc.id) as chunks_count,
    COUNT(e.id) as embeddings_count,
    COUNT(fv.id) as versions_count
FROM pulpo.files f
LEFT JOIN pulpo.file_chunks fc ON f.id = fc.file_id
LEFT JOIN pulpo.embeddings e ON fc.id = e.chunk_id
LEFT JOIN pulpo.file_versions fv ON f.id = fv.file_id
WHERE f.deleted_at IS NULL
GROUP BY f.id, f.workspace_id, f.original_filename, f.file_size, 
         f.vertical, f.document_type, f.mime_type, f.processing_status, 
         f.created_at, f.deleted_at;

-- Vista para estadísticas por vertical
CREATE OR REPLACE VIEW pulpo.v_vertical_stats AS
SELECT 
    f.vertical,
    f.document_type,
    COUNT(*) as total_files,
    SUM(f.file_size) as total_size,
    COUNT(fc.id) as total_chunks,
    COUNT(e.id) as total_embeddings,
    MAX(f.created_at) as last_upload
FROM pulpo.files f
LEFT JOIN pulpo.file_chunks fc ON f.id = fc.file_id
LEFT JOIN pulpo.embeddings e ON fc.id = e.chunk_id
WHERE f.deleted_at IS NULL
GROUP BY f.vertical, f.document_type
ORDER BY f.vertical, f.document_type;

-- =====================================================
-- 9. COMENTARIOS Y DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE pulpo.file_versions IS 'Versiones de archivos procesados con texto normalizado';
COMMENT ON TABLE pulpo.documents IS 'Documentos lógicos extraídos de archivos (puede haber múltiples por archivo)';
COMMENT ON TABLE pulpo.embeddings IS 'Embeddings vectoriales de chunks con metadatos del modelo';
COMMENT ON TABLE pulpo.audit_events IS 'Auditoría de eventos del sistema';

COMMENT ON FUNCTION pulpo.delete_file_cascade(UUID, UUID) IS 'Elimina archivo y todos sus datos relacionados de forma consistente';

-- =====================================================
-- FIN DEL SCRIPT
-- =====================================================

\echo '✅ Sistema de archivos crudos y versiones instalado correctamente'
\echo '📁 Tablas creadas: file_versions, documents, embeddings, audit_events'
\echo '🔧 Funciones creadas: delete_file_cascade'
\echo '👁️  Vistas creadas: v_files_complete, v_vertical_stats'
\echo '📊 Sistema genérico multi-vertical listo'

