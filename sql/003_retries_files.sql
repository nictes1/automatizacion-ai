-- 003_retries_files.sql
-- Migración para sistema de reintentos

-- Agregar columnas de reintentos a files
ALTER TABLE pulpo.files
  ADD COLUMN attempts int NOT NULL DEFAULT 0,
  ADD COLUMN last_error text,
  ADD COLUMN next_retry_at timestamptz;

-- Índices para búsquedas de reintentos
CREATE INDEX idx_files_next_retry ON pulpo.files (next_retry_at) 
  WHERE status IN ('failed', 'processing') AND next_retry_at IS NOT NULL;

CREATE INDEX idx_files_attempts ON pulpo.files (attempts) 
  WHERE status = 'failed';

-- Comentarios para documentación
COMMENT ON COLUMN pulpo.files.attempts IS 'Número de intentos de procesamiento realizados';
COMMENT ON COLUMN pulpo.files.last_error IS 'Último mensaje de error (truncado a 4000 chars)';
COMMENT ON COLUMN pulpo.files.next_retry_at IS 'Timestamp del próximo intento de procesamiento';
