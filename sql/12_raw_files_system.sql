-- =====================================================
-- Sistema de Archivos Crudos y Versiones
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
-- 1. TABLA DE ARCHIVOS CRUDOS (RAW FILES)
-- =====================================================

-- Extender la tabla files existente para soportar archivos crudos
ALTER TABLE pulpo.files 
ADD COLUMN IF NOT EXISTS vertical VARCHAR(50),
ADD COLUMN IF NOT EXISTS document_type VARCHAR(50),
ADD COLUMN IF NOT EXISTS storage_uri TEXT,
ADD COLUMN IF NOT EXISTS mime_type VARCHAR(100),
ADD COLUMN IF NOT EXISTS file_hash VARCHAR(64), -- SHA256 para deduplicación
ADD COLUMN IF NOT EXISTS processing_status VARCHAR(20) DEFAULT 'uploaded',
ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMPTZ;

-- Índices para archivos crudos
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
    normalized_text_uri TEXT, -- Ruta al texto normalizado
    parse_report JSONB, -- Metadatos de parsing
    created_at TIMESTAMPTZ DEFAULT NOW(),
    created_by UUID REFERENCES pulpo.users(id),
    
    -- Restricciones
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
    doc_path TEXT, -- Ej: "sheet1!A1:D200" o "pages/3"
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

-- Extender la tabla file_chunks existente
ALTER TABLE pulpo.file_chunks 
ADD COLUMN IF NOT EXISTS document_id UUID REFERENCES pulpo.documents(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS file_version_id UUID REFERENCES pulpo.file_versions(id) ON DELETE CASCADE,
ADD COLUMN IF NOT EXISTS position INTEGER NOT NULL DEFAULT 0;

-- Índices para chunks mejorados
CREATE INDEX IF NOT EXISTS idx_file_chunks_document_id ON pulpo.file_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_file_chunks_file_version_id ON pulpo.file_chunks(file_version_id);
CREATE INDEX IF NOT EXISTS idx_file_chunks_position ON pulpo.file_chunks(position);

-- =====================================================
-- 5. TABLA DE EMBEDDINGS MEJORADA
-- =====================================================

CREATE TABLE IF NOT EXISTS pulpo.embeddings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    chunk_id UUID NOT NULL REFERENCES pulpo.file_chunks(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    model VARCHAR(100) NOT NULL, -- Ej: "text-embedding-3-large"
    dim INTEGER NOT NULL,
    vector VECTOR(1536) NOT NULL, -- Ajustar dimensión según modelo
    created_at TIMESTAMPTZ DEFAULT NOW(),
    
    -- Restricciones
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
    event_type VARCHAR(50) NOT NULL, -- upload, ingest_started, embed_upsert, delete_request, action_executed
    ref_id UUID, -- file_id, conversation_id, action_id
    ref_type VARCHAR(50), -- file, conversation, action
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
-- 8. FUNCIÓN DE BÚSQUEDA HÍBRIDA
-- =====================================================

-- Función para búsqueda híbrida (BM25 + Vector)
CREATE OR REPLACE FUNCTION pulpo.hybrid_search(
    search_query TEXT,
    workspace_uuid UUID,
    search_limit INTEGER DEFAULT 10,
    search_filters JSONB DEFAULT '{}'::jsonb
)
RETURNS TABLE (
    chunk_id UUID,
    chunk_text TEXT,
    similarity_score FLOAT,
    search_rank INTEGER,
    metadata JSONB,
    filename TEXT,
    vertical VARCHAR(50),
    document_type VARCHAR(50)
) AS $$
BEGIN
    RETURN QUERY
    WITH vector_search AS (
        -- Búsqueda vectorial (simplificada - necesitará implementación completa)
        SELECT 
            fc.id as chunk_id,
            fc.chunk_text,
            0.8::FLOAT as similarity_score, -- Placeholder
            1 as search_rank,
            fc.chunk_metadata as metadata,
            f.original_filename as filename,
            f.vertical,
            f.document_type
        FROM pulpo.file_chunks fc
        JOIN pulpo.files f ON fc.file_id = f.id
        WHERE f.workspace_id = workspace_uuid 
        AND f.deleted_at IS NULL
        AND fc.chunk_text ILIKE '%' || search_query || '%'
        LIMIT search_limit
    ),
    bm25_search AS (
        -- Búsqueda BM25 (simplificada - necesitará implementación completa)
        SELECT 
            fc.id as chunk_id,
            fc.chunk_text,
            0.7::FLOAT as similarity_score, -- Placeholder
            2 as search_rank,
            fc.chunk_metadata as metadata,
            f.original_filename as filename,
            f.vertical,
            f.document_type
        FROM pulpo.file_chunks fc
        JOIN pulpo.files f ON fc.file_id = f.id
        WHERE f.workspace_id = workspace_uuid 
        AND f.deleted_at IS NULL
        AND to_tsvector('spanish', fc.chunk_text) @@ plainto_tsquery('spanish', search_query)
        LIMIT search_limit
    ),
    combined_results AS (
        SELECT * FROM vector_search
        UNION ALL
        SELECT * FROM bm25_search
    )
    SELECT DISTINCT ON (chunk_id)
        cr.chunk_id,
        cr.chunk_text,
        cr.similarity_score,
        cr.search_rank,
        cr.metadata,
        cr.filename,
        cr.vertical,
        cr.document_type
    FROM combined_results cr
    ORDER BY chunk_id, similarity_score DESC
    LIMIT search_limit;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- 9. VISTAS ÚTILES
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
-- 10. POLÍTICAS RLS (Row Level Security)
-- =====================================================

-- Habilitar RLS en las nuevas tablas
ALTER TABLE pulpo.file_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.audit_events ENABLE ROW LEVEL SECURITY;

-- Políticas para file_versions
CREATE POLICY file_versions_workspace_policy ON pulpo.file_versions
    FOR ALL TO authenticated
    USING (
        file_id IN (
            SELECT id FROM pulpo.files 
            WHERE workspace_id = current_setting('app.workspace_id')::uuid
        )
    );

-- Políticas para documents
CREATE POLICY documents_workspace_policy ON pulpo.documents
    FOR ALL TO authenticated
    USING (workspace_id = current_setting('app.workspace_id')::uuid);

-- Políticas para embeddings
CREATE POLICY embeddings_workspace_policy ON pulpo.embeddings
    FOR ALL TO authenticated
    USING (workspace_id = current_setting('app.workspace_id')::uuid);

-- Políticas para audit_events
CREATE POLICY audit_events_workspace_policy ON pulpo.audit_events
    FOR ALL TO authenticated
    USING (workspace_id = current_setting('app.workspace_id')::uuid);

-- =====================================================
-- 11. COMENTARIOS Y DOCUMENTACIÓN
-- =====================================================

COMMENT ON TABLE pulpo.file_versions IS 'Versiones de archivos procesados con texto normalizado';
COMMENT ON TABLE pulpo.documents IS 'Documentos lógicos extraídos de archivos (puede haber múltiples por archivo)';
COMMENT ON TABLE pulpo.embeddings IS 'Embeddings vectoriales de chunks con metadatos del modelo';
COMMENT ON TABLE pulpo.audit_events IS 'Auditoría de eventos del sistema';

COMMENT ON FUNCTION pulpo.delete_file_cascade(UUID, UUID) IS 'Elimina archivo y todos sus datos relacionados de forma consistente';
COMMENT ON FUNCTION pulpo.hybrid_search(TEXT, UUID, INTEGER, JSONB) IS 'Búsqueda híbrida combinando BM25 y vectorial';

-- =====================================================
-- 12. DATOS DE PRUEBA (OPCIONAL)
-- =====================================================

-- Insertar configuración de verticales
INSERT INTO pulpo.vertical_configs (vertical, config_json) VALUES
('gastronomia', '{
    "document_types": {
        "menu": {
            "extraction_prompt": "Extrae información del menú gastronómico",
            "chunking_strategy": "semantic",
            "search_fields": ["name", "price", "category", "description"]
        },
        "policy": {
            "extraction_prompt": "Extrae políticas del restaurante",
            "chunking_strategy": "paragraph",
            "search_fields": ["policy_type", "content", "conditions"]
        }
    }
}'::jsonb),
('inmobiliaria', '{
    "document_types": {
        "properties": {
            "extraction_prompt": "Extrae información de propiedades inmobiliarias",
            "chunking_strategy": "property",
            "search_fields": ["address", "price", "type", "features"]
        },
        "policy": {
            "extraction_prompt": "Extrae políticas inmobiliarias",
            "chunking_strategy": "paragraph",
            "search_fields": ["policy_type", "content", "conditions"]
        }
    }
}'::jsonb)
ON CONFLICT (vertical) DO UPDATE SET
    config_json = EXCLUDED.config_json,
    updated_at = NOW();

-- =====================================================
-- FIN DEL SCRIPT
-- =====================================================

\echo '✅ Sistema de archivos crudos y versiones instalado correctamente'
\echo '📁 Tablas creadas: file_versions, documents, embeddings, audit_events'
\echo '🔧 Funciones creadas: delete_file_cascade, hybrid_search'
\echo '👁️  Vistas creadas: v_files_complete, v_vertical_stats'
\echo '🔒 Políticas RLS configuradas'
\echo '📊 Configuración de verticales insertada'
