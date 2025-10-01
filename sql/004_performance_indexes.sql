-- 004_performance_indexes.sql
-- Índices adicionales para performance

-- Índices para queries frecuentes
CREATE INDEX IF NOT EXISTS idx_files_workspace_status ON pulpo.files (workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_documents_workspace_file ON pulpo.documents (workspace_id, file_id);
CREATE INDEX IF NOT EXISTS idx_chunks_document_workspace ON pulpo.chunks (document_id, workspace_id);
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_document_workspace ON pulpo.chunk_embeddings (document_id, workspace_id);

-- Índices parciales para queries sin soft-deleted
CREATE INDEX IF NOT EXISTS idx_files_active ON pulpo.files (workspace_id, created_at) 
  WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_documents_active ON pulpo.documents (workspace_id, created_at) 
  WHERE deleted_at IS NULL;

-- Índices para workers
CREATE INDEX IF NOT EXISTS idx_files_retry_candidates ON pulpo.files (next_retry_at, attempts) 
  WHERE next_retry_at IS NOT NULL AND deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_files_purge_candidates ON pulpo.files (purge_at) 
  WHERE deleted_at IS NOT NULL AND purge_at IS NOT NULL;

-- Comentarios para documentación
COMMENT ON INDEX idx_files_workspace_status IS 'Optimiza queries por workspace y estado';
COMMENT ON INDEX idx_documents_workspace_file IS 'Optimiza búsqueda de documentos por archivo';
COMMENT ON INDEX idx_chunks_document_workspace IS 'Optimiza queries de chunks por documento';
COMMENT ON INDEX idx_chunk_embeddings_document_workspace IS 'Optimiza queries de embeddings por documento';
COMMENT ON INDEX idx_files_active IS 'Optimiza listado de archivos activos (sin soft-delete)';
COMMENT ON INDEX idx_documents_active IS 'Optimiza listado de documentos activos (sin soft-delete)';
COMMENT ON INDEX idx_files_retry_candidates IS 'Optimiza worker de reintentos';
COMMENT ON INDEX idx_files_purge_candidates IS 'Optimiza worker de purga';
