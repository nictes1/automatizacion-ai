-- Sprint 3.1: Índices opcionales para performance y coherencia
-- Ejecutar después de 06_retries_scheduler.sql

-- Índices para chunks
CREATE INDEX IF NOT EXISTS idx_chunks_document_id 
ON pulpo.chunks(document_id) 
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chunks_workspace_id 
ON pulpo.chunks(workspace_id) 
WHERE deleted_at IS NULL;

-- Índices para chunk_embeddings
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_chunk_id 
ON pulpo.chunk_embeddings(chunk_id) 
WHERE deleted_at IS NULL;

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_workspace_id 
ON pulpo.chunk_embeddings(workspace_id) 
WHERE deleted_at IS NULL;

-- Índice único para ON CONFLICT DO NOTHING
CREATE UNIQUE INDEX IF NOT EXISTS uq_chunk_embeddings
ON pulpo.chunk_embeddings (chunk_id, workspace_id)
WHERE deleted_at IS NULL;

-- Índice compuesto para búsqueda eficiente de chunks sin embedding
CREATE INDEX IF NOT EXISTS idx_chunks_doc_workspace 
ON pulpo.chunks(document_id, workspace_id) 
WHERE deleted_at IS NULL;

-- Índice para document_revisions por documento
CREATE INDEX IF NOT EXISTS idx_document_revisions_doc_rev 
ON pulpo.document_revisions(document_id, revision DESC);

-- Análisis para optimizar
ANALYZE pulpo.chunks;
ANALYZE pulpo.chunk_embeddings;
ANALYZE pulpo.document_revisions;

-- Mostrar resumen
SELECT 
    'Sprint 3.1 - Índices de Performance' as feature,
    'Índices optimizados para pipeline OCR → Chunking → Embedding' as description,
    now() as completed_at;
