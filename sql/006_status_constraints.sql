-- 006_status_constraints.sql
-- Constraints CHECK para estados válidos

-- Limitar status a un conjunto válido
ALTER TABLE pulpo.files
  ADD CONSTRAINT files_status_chk
  CHECK (status IN ('uploaded','processing','processed','failed','deleted'));

-- Comentarios para documentación
COMMENT ON CONSTRAINT files_status_chk ON pulpo.files IS 'Garantiza que status solo contenga valores válidos del flujo de procesamiento';
