-- Mejoras para RAG Service v2.0.0
-- Ejecutar después de 01_core_up.sql

-- 1. Extensión unaccent para búsqueda sin acentos
CREATE EXTENSION IF NOT EXISTS unaccent;

-- 2. Función immutable para unaccent (requerida para índices)
CREATE OR REPLACE FUNCTION pulpo.immutable_unaccent(text)
RETURNS text LANGUAGE sql IMMUTABLE PARALLEL SAFE AS $$
  SELECT unaccent('public.unaccent', $1)
$$;

-- 3. Columna materializada para FTS con unaccent
ALTER TABLE pulpo.chunks 
ADD COLUMN IF NOT EXISTS tsv tsvector
GENERATED ALWAYS AS (
  to_tsvector('spanish', pulpo.immutable_unaccent(coalesce(text, '')))
) STORED;

-- 4. Índice GIN para FTS
CREATE INDEX IF NOT EXISTS idx_chunks_tsv 
ON pulpo.chunks USING GIN (tsv);

-- 5. Índice GIN para metadata JSONB (filtros frecuentes)
CREATE INDEX IF NOT EXISTS idx_chunks_meta_gin 
ON pulpo.chunks USING GIN (meta jsonb_path_ops);

-- 6. Índice IVFFLAT para embeddings vectoriales (ajustar lists según tamaño)
-- Nota: Ejecutar solo si tienes suficientes datos (recomendado: >1000 vectores)
-- CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_ivfflat 
-- ON pulpo.chunk_embeddings USING ivfflat (embedding vector_cosine_ops) 
-- WITH (lists = 100);

-- 7. Índice HNSW para embeddings (alternativa más moderna a IVFFLAT)
-- Requiere pgvector >= 0.5.0
-- CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_hnsw 
-- ON pulpo.chunk_embeddings USING hnsw (embedding vector_cosine_ops) 
-- WITH (m = 16, ef_construction = 64);

-- 8. Índices adicionales para performance
CREATE INDEX IF NOT EXISTS idx_chunks_workspace_document 
ON pulpo.chunks (workspace_id, document_id);

CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_workspace 
ON pulpo.chunk_embeddings (workspace_id);

-- 9. Función para actualizar estadísticas (ejecutar periódicamente)
CREATE OR REPLACE FUNCTION pulpo.update_rag_stats()
RETURNS void AS $$
BEGIN
  -- Actualizar estadísticas de las tablas principales
  ANALYZE pulpo.chunks;
  ANALYZE pulpo.chunk_embeddings;
  ANALYZE pulpo.documents;
  
  -- Log de estadísticas
  RAISE NOTICE 'Estadísticas de RAG actualizadas: % chunks, % embeddings, % documentos',
    (SELECT COUNT(*) FROM pulpo.chunks),
    (SELECT COUNT(*) FROM pulpo.chunk_embeddings),
    (SELECT COUNT(*) FROM pulpo.documents);
END;
$$ LANGUAGE plpgsql;

-- 10. Vista para monitoreo de performance
CREATE OR REPLACE VIEW pulpo.rag_performance_stats AS
SELECT 
  'chunks' as table_name,
  COUNT(*) as total_rows,
  COUNT(*) FILTER (WHERE tsv IS NOT NULL) as fts_ready,
  COUNT(*) FILTER (WHERE meta IS NOT NULL) as has_metadata
FROM pulpo.chunks
UNION ALL
SELECT 
  'chunk_embeddings' as table_name,
  COUNT(*) as total_rows,
  COUNT(*) FILTER (WHERE embedding IS NOT NULL) as fts_ready,
  COUNT(*) FILTER (WHERE workspace_id IS NOT NULL) as has_metadata
FROM pulpo.chunk_embeddings
UNION ALL
SELECT 
  'documents' as table_name,
  COUNT(*) as total_rows,
  COUNT(*) FILTER (WHERE title IS NOT NULL) as fts_ready,
  COUNT(*) FILTER (WHERE workspace_id IS NOT NULL) as has_metadata
FROM pulpo.documents;

-- 11. Comentarios para documentación
COMMENT ON COLUMN pulpo.chunks.tsv IS 'Columna materializada para full-text search con unaccent';
COMMENT ON INDEX idx_chunks_tsv IS 'Índice GIN para búsqueda full-text en chunks';
COMMENT ON INDEX idx_chunks_meta_gin IS 'Índice GIN para filtros por metadata JSONB';
COMMENT ON FUNCTION pulpo.immutable_unaccent(text) IS 'Función immutable para unaccent, requerida para índices';
COMMENT ON FUNCTION pulpo.update_rag_stats() IS 'Función para actualizar estadísticas de las tablas RAG';

-- 12. Ejecutar análisis inicial
SELECT pulpo.update_rag_stats();

-- 13. Mostrar estadísticas finales
SELECT * FROM pulpo.rag_performance_stats;
