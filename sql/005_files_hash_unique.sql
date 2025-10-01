-- 005_files_hash_unique.sql
-- Evita duplicados exactos por workspace

-- Constraint único para deduplicación por hash
ALTER TABLE pulpo.files
  ADD CONSTRAINT files_ws_sha256_uniq UNIQUE (workspace_id, sha256);

-- Índice útil si hacés búsquedas frecuentes por sha256
CREATE INDEX IF NOT EXISTS idx_files_sha256 ON pulpo.files (sha256);

-- Índice de soporte para queries de deduplicación
CREATE INDEX IF NOT EXISTS idx_files_workspace_sha256 ON pulpo.files (workspace_id, sha256);

-- Comentarios para documentación
COMMENT ON CONSTRAINT files_ws_sha256_uniq ON pulpo.files IS 'Garantiza que no haya archivos duplicados por hash en el mismo workspace';
COMMENT ON INDEX idx_files_sha256 IS 'Optimiza búsquedas por hash SHA256';
COMMENT ON INDEX idx_files_workspace_sha256 IS 'Optimiza queries de deduplicación por workspace y hash';
