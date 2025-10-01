-- 001_soft_delete_files.sql
-- Migración para soft-delete con ventana de gracia

-- Agregar columnas de soft-delete a files
ALTER TABLE pulpo.files
  ADD COLUMN deleted_at timestamptz,
  ADD COLUMN purge_at   timestamptz;

-- Opcional: soft-delete en documents también
ALTER TABLE pulpo.documents
  ADD COLUMN deleted_at timestamptz;

-- Índices para búsquedas rápidas
CREATE INDEX idx_files_purge_at ON pulpo.files (purge_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_files_deleted_at ON pulpo.files (deleted_at) WHERE deleted_at IS NOT NULL;
CREATE INDEX idx_documents_deleted_at ON pulpo.documents (deleted_at) WHERE deleted_at IS NOT NULL;

-- Comentarios para documentación
COMMENT ON COLUMN pulpo.files.deleted_at IS 'Timestamp cuando el archivo fue marcado para eliminación (soft-delete)';
COMMENT ON COLUMN pulpo.files.purge_at IS 'Timestamp cuando el archivo debe ser purgado físicamente';
COMMENT ON COLUMN pulpo.documents.deleted_at IS 'Timestamp cuando el documento fue marcado para eliminación (soft-delete)';
