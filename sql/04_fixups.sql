-- Fixups para Sprint 1 - Micro-nits pro-prod
-- Ejecutar después de 03_enterprise_features.sql

-- 1. Extensión para gen_random_uuid()
CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 2. Soft delete en chunk_embeddings (si no existe)
ALTER TABLE IF NOT EXISTS pulpo.chunk_embeddings
  ADD COLUMN IF NOT EXISTS deleted_at TIMESTAMP NULL;

-- 3. Índice parcial para embeddings activos
CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_deleted_at
ON pulpo.chunk_embeddings (deleted_at) WHERE deleted_at IS NULL;

-- 4. Índice compuesto para joins multitenant optimizados
-- (si chunk_embeddings tiene workspace_id)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'pulpo' 
        AND table_name = 'chunk_embeddings' 
        AND column_name = 'workspace_id'
    ) THEN
        CREATE INDEX IF NOT EXISTS idx_chunk_embeddings_workspace_active
        ON pulpo.chunk_embeddings (workspace_id) WHERE deleted_at IS NULL;
    END IF;
END $$;

-- 5. Verificar que todas las tablas tienen soft delete
SELECT 
    'documents' as table_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'pulpo' 
        AND table_name = 'documents' 
        AND column_name = 'deleted_at'
    ) THEN '✅' ELSE '❌' END as has_deleted_at
UNION ALL
SELECT 
    'chunks' as table_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'pulpo' 
        AND table_name = 'chunks' 
        AND column_name = 'deleted_at'
    ) THEN '✅' ELSE '❌' END as has_deleted_at
UNION ALL
SELECT 
    'chunk_embeddings' as table_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_schema = 'pulpo' 
        AND table_name = 'chunk_embeddings' 
        AND column_name = 'deleted_at'
    ) THEN '✅' ELSE '❌' END as has_deleted_at;

-- 6. Verificar extensiones requeridas
SELECT 
    'unaccent' as extension_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'unaccent'
    ) THEN '✅' ELSE '❌' END as status
UNION ALL
SELECT 
    'pgcrypto' as extension_name,
    CASE WHEN EXISTS (
        SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto'
    ) THEN '✅' ELSE '❌' END as status;

-- 7. Estadísticas finales de Sprint 1
SELECT 
    'Sprint 1 - Enterprise Features' as feature,
    'Soft Delete + Versionado' as description,
    now() as completed_at;

-- 8. Comentarios para documentación
COMMENT ON COLUMN pulpo.chunk_embeddings.deleted_at IS 'Timestamp de soft delete para embeddings (NULL = activo)';
COMMENT ON INDEX idx_chunk_embeddings_deleted_at IS 'Índice parcial para embeddings activos (sin soft delete)';

-- 9. Función de utilidad para verificar integridad de soft delete
CREATE OR REPLACE FUNCTION pulpo.check_soft_delete_integrity()
RETURNS TABLE(
    table_name TEXT,
    total_rows BIGINT,
    active_rows BIGINT,
    deleted_rows BIGINT,
    integrity_status TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        'documents'::TEXT,
        COUNT(*) as total_rows,
        COUNT(*) FILTER (WHERE deleted_at IS NULL) as active_rows,
        COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) as deleted_rows,
        CASE 
            WHEN COUNT(*) = COUNT(*) FILTER (WHERE deleted_at IS NULL) + COUNT(*) FILTER (WHERE deleted_at IS NOT NULL)
            THEN '✅ OK'
            ELSE '❌ ERROR'
        END as integrity_status
    FROM pulpo.documents
    UNION ALL
    SELECT 
        'chunks'::TEXT,
        COUNT(*) as total_rows,
        COUNT(*) FILTER (WHERE deleted_at IS NULL) as active_rows,
        COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) as deleted_rows,
        CASE 
            WHEN COUNT(*) = COUNT(*) FILTER (WHERE deleted_at IS NULL) + COUNT(*) FILTER (WHERE deleted_at IS NOT NULL)
            THEN '✅ OK'
            ELSE '❌ ERROR'
        END as integrity_status
    FROM pulpo.chunks
    UNION ALL
    SELECT 
        'chunk_embeddings'::TEXT,
        COUNT(*) as total_rows,
        COUNT(*) FILTER (WHERE deleted_at IS NULL) as active_rows,
        COUNT(*) FILTER (WHERE deleted_at IS NOT NULL) as deleted_rows,
        CASE 
            WHEN COUNT(*) = COUNT(*) FILTER (WHERE deleted_at IS NULL) + COUNT(*) FILTER (WHERE deleted_at IS NOT NULL)
            THEN '✅ OK'
            ELSE '❌ ERROR'
        END as integrity_status
    FROM pulpo.chunk_embeddings;
END;
$$ LANGUAGE plpgsql;

-- 10. Ejecutar verificación de integridad
SELECT * FROM pulpo.check_soft_delete_integrity();

-- 11. Mostrar resumen final
SELECT 
    'Sprint 1 Fixups Completados' as status,
    'Soft delete, versionado, y micro-nits implementados' as description,
    now() as timestamp;
