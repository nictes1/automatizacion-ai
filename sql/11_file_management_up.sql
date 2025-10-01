-- =====================================================
-- Sistema de Gestión de Archivos para RAG (Arquitectura Mejorada)
-- Basado en la propuesta de ChatGPT con adaptaciones para nuestro stack
-- =====================================================

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- Tabla para archivos crudos (subidos)
CREATE TABLE IF NOT EXISTS pulpo.files (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    storage_uri text NOT NULL,                -- s3://bucket/key o file:///… (desarrollo)
    filename text NOT NULL,
    mime_type text,
    sha256 text NOT NULL,                      -- para deduplicación
    bytes bigint,
    status text NOT NULL DEFAULT 'uploaded',   -- uploaded|processing|processed|failed
    error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, sha256)              -- evita duplicados exactos por workspace
);

-- Documentos extraídos (1 archivo => 1 o varios "documentos" lógicos)
CREATE TABLE IF NOT EXISTS pulpo.documents (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    file_id uuid NOT NULL REFERENCES pulpo.files(id) ON DELETE CASCADE,
    title text,
    language text,                             -- ej. es, en
    raw_text text NOT NULL,                    -- texto consolidado
    token_count integer NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

-- Chunks de documentos
CREATE TABLE IF NOT EXISTS pulpo.doc_chunks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    document_id uuid NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
    chunk_index integer NOT NULL,
    content text NOT NULL,
    token_count integer NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb,        -- metadatos del chunk (página, sección, etc.)
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(document_id, chunk_index)
);

-- Embeddings de chunks (vector = 1536 o el tamaño que uses)
CREATE TABLE IF NOT EXISTS pulpo.doc_chunk_embeddings (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    chunk_id uuid NOT NULL REFERENCES pulpo.doc_chunks(id) ON DELETE CASCADE,
    model text NOT NULL,
    dims integer NOT NULL,
    embedding vector NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(chunk_id)
);

-- Tabla para configuraciones de procesamiento por tipo de archivo
CREATE TABLE IF NOT EXISTS pulpo.file_type_configs (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    file_extension text NOT NULL,
    mime_type text NOT NULL,
    processor_type text NOT NULL,
    processor_config jsonb DEFAULT '{}'::jsonb,
    is_enabled boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    UNIQUE(workspace_id, file_extension)
);

-- Índices para optimizar consultas
CREATE INDEX IF NOT EXISTS idx_files_workspace_id ON pulpo.files(workspace_id);
CREATE INDEX IF NOT EXISTS idx_files_status ON pulpo.files(status);
CREATE INDEX IF NOT EXISTS idx_files_created_at ON pulpo.files(created_at);
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON pulpo.files(sha256);

CREATE INDEX IF NOT EXISTS idx_documents_workspace_id ON pulpo.documents(workspace_id);
CREATE INDEX IF NOT EXISTS idx_documents_file_id ON pulpo.documents(file_id);

CREATE INDEX IF NOT EXISTS idx_doc_chunks_workspace_id ON pulpo.doc_chunks(workspace_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_document_id ON pulpo.doc_chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunks_index ON pulpo.doc_chunks(chunk_index);

CREATE INDEX IF NOT EXISTS idx_doc_chunk_embeddings_workspace_id ON pulpo.doc_chunk_embeddings(workspace_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunk_embeddings_chunk_id ON pulpo.doc_chunk_embeddings(chunk_id);
CREATE INDEX IF NOT EXISTS idx_doc_chunk_embeddings_model ON pulpo.doc_chunk_embeddings(model);

-- Índice vectorial para búsqueda semántica (requiere extensión vector)
CREATE INDEX IF NOT EXISTS idx_doc_chunk_embeddings_vector ON pulpo.doc_chunk_embeddings 
USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);

-- RLS (Row Level Security) para multi-tenancy
ALTER TABLE pulpo.files ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.doc_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.doc_chunk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.file_type_configs ENABLE ROW LEVEL SECURITY;

-- Asume que seteás SET app.current_workspace = '<uuid>';
-- o usás una función para obtenerlos del JWT.
CREATE SCHEMA IF NOT EXISTS app;

CREATE OR REPLACE FUNCTION app.current_workspace() RETURNS uuid
LANGUAGE sql STABLE AS $$ 
    SELECT current_setting('app.current_workspace', true)::uuid 
$$;

-- Políticas RLS para files
CREATE POLICY by_workspace_files ON pulpo.files
    USING (workspace_id = app.current_workspace());

-- Políticas RLS para documents
CREATE POLICY by_workspace_documents ON pulpo.documents
    USING (workspace_id = app.current_workspace());

-- Políticas RLS para doc_chunks
CREATE POLICY by_workspace_doc_chunks ON pulpo.doc_chunks
    USING (workspace_id = app.current_workspace());

-- Políticas RLS para doc_chunk_embeddings
CREATE POLICY by_workspace_doc_chunk_embeddings ON pulpo.doc_chunk_embeddings
    USING (workspace_id = app.current_workspace());

-- Políticas RLS para file_type_configs
CREATE POLICY by_workspace_file_type_configs ON pulpo.file_type_configs
    USING (workspace_id = app.current_workspace());

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION pulpo.update_file_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
CREATE TRIGGER trigger_files_updated_at
    BEFORE UPDATE ON pulpo.files
    FOR EACH ROW
    EXECUTE FUNCTION pulpo.update_file_updated_at();

CREATE TRIGGER trigger_file_type_configs_updated_at
    BEFORE UPDATE ON pulpo.file_type_configs
    FOR EACH ROW
    EXECUTE FUNCTION pulpo.update_file_updated_at();

-- Función para limpiar archivos eliminados
CREATE OR REPLACE FUNCTION pulpo.cleanup_deleted_files()
RETURNS void AS $$
BEGIN
    -- Eliminar embeddings de archivos eliminados
    DELETE FROM pulpo.file_embeddings 
    WHERE chunk_id IN (
        SELECT fc.id FROM pulpo.file_chunks fc
        JOIN pulpo.files f ON fc.file_id = f.id
        WHERE f.deleted_at IS NOT NULL
    );
    
    -- Eliminar chunks de archivos eliminados
    DELETE FROM pulpo.file_chunks 
    WHERE file_id IN (
        SELECT id FROM pulpo.files 
        WHERE deleted_at IS NOT NULL
    );
    
    -- Eliminar archivos marcados como eliminados
    DELETE FROM pulpo.files 
    WHERE deleted_at IS NOT NULL;
END;
$$ LANGUAGE plpgsql;

-- Función para obtener estadísticas de archivos por workspace
CREATE OR REPLACE FUNCTION pulpo.get_file_stats(p_workspace_id uuid)
RETURNS TABLE (
    total_files bigint,
    total_size bigint,
    files_by_status jsonb,
    files_by_type jsonb,
    total_chunks bigint,
    total_embeddings bigint
) AS $$
BEGIN
    PERFORM pulpo.set_ws_context(p_workspace_id);
    
    RETURN QUERY
    SELECT 
        COUNT(*) as total_files,
        COALESCE(SUM(file_size), 0) as total_size,
        jsonb_object_agg(processing_status, status_count) as files_by_status,
        jsonb_object_agg(file_type, type_count) as files_by_type,
        (SELECT COUNT(*) FROM pulpo.file_chunks fc 
         JOIN pulpo.files f ON fc.file_id = f.id 
         WHERE f.workspace_id = p_workspace_id) as total_chunks,
        (SELECT COUNT(*) FROM pulpo.file_embeddings fe
         JOIN pulpo.file_chunks fc ON fe.chunk_id = fc.id
         JOIN pulpo.files f ON fc.file_id = f.id
         WHERE f.workspace_id = p_workspace_id) as total_embeddings
    FROM (
        SELECT 
            processing_status,
            COUNT(*) as status_count
        FROM pulpo.files 
        WHERE workspace_id = p_workspace_id AND deleted_at IS NULL
        GROUP BY processing_status
    ) status_stats
    CROSS JOIN (
        SELECT 
            file_type,
            COUNT(*) as type_count
        FROM pulpo.files 
        WHERE workspace_id = p_workspace_id AND deleted_at IS NULL
        GROUP BY file_type
    ) type_stats;
END;
$$ LANGUAGE plpgsql STABLE;

-- Función para buscar archivos por contenido
CREATE OR REPLACE FUNCTION pulpo.search_files_by_content(
    p_workspace_id uuid,
    p_search_query text,
    p_limit integer DEFAULT 10
)
RETURNS TABLE (
    file_id uuid,
    filename text,
    file_type text,
    chunk_text text,
    similarity_score float,
    chunk_index integer
) AS $$
BEGIN
    PERFORM pulpo.set_ws_context(p_workspace_id);
    
    -- Esta función requerirá la generación de embeddings para la consulta
    -- Por ahora retornamos búsqueda de texto simple
    RETURN QUERY
    SELECT 
        f.id as file_id,
        f.original_filename as filename,
        f.file_type,
        fc.chunk_text,
        1.0 as similarity_score, -- Placeholder para similitud
        fc.chunk_index
    FROM pulpo.files f
    JOIN pulpo.file_chunks fc ON f.id = fc.file_id
    WHERE f.workspace_id = p_workspace_id 
        AND f.deleted_at IS NULL
        AND f.processing_status = 'completed'
        AND fc.chunk_text ILIKE '%' || p_search_query || '%'
    ORDER BY f.created_at DESC
    LIMIT p_limit;
END;
$$ LANGUAGE plpgsql STABLE;

-- Comentarios para documentación
COMMENT ON TABLE pulpo.files IS 'Metadatos de archivos subidos para procesamiento RAG';
COMMENT ON TABLE pulpo.file_chunks IS 'Chunks de texto extraídos de archivos';
COMMENT ON TABLE pulpo.file_embeddings IS 'Embeddings vectoriales de chunks de archivos';
COMMENT ON TABLE pulpo.file_type_configs IS 'Configuraciones de procesamiento por tipo de archivo';

COMMENT ON COLUMN pulpo.files.content_hash IS 'SHA256 del contenido del archivo para detectar duplicados';
COMMENT ON COLUMN pulpo.files.processing_status IS 'Estado del procesamiento: pending, processing, completed, failed, deleted';
COMMENT ON COLUMN pulpo.file_chunks.chunk_tokens IS 'Número aproximado de tokens en el chunk';
COMMENT ON COLUMN pulpo.file_embeddings.embedding_vector IS 'Vector de embeddings (1536 dimensiones para OpenAI)';
