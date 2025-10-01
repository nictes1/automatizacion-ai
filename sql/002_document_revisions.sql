-- 002_document_revisions.sql
-- Migración para versionado de documentos

-- Tabla de revisiones de documentos
CREATE TABLE pulpo.document_revisions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
  version int NOT NULL,
  raw_text text,
  structured_json jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (document_id, version)
);

-- Agregar referencia a revisión en chunks
ALTER TABLE pulpo.chunks
  ADD COLUMN revision_id uuid REFERENCES pulpo.document_revisions(id);

-- Índices para performance
CREATE INDEX idx_document_revisions_document_version ON pulpo.document_revisions (document_id, version);
CREATE INDEX idx_chunks_revision_id ON pulpo.chunks (revision_id);

-- Comentarios para documentación
COMMENT ON TABLE pulpo.document_revisions IS 'Revisiones inmutables de documentos para versionado y auditoría';
COMMENT ON COLUMN pulpo.document_revisions.version IS 'Número de versión incremental por documento';
COMMENT ON COLUMN pulpo.document_revisions.structured_json IS 'Datos estructurados del documento (menú, etc.)';
COMMENT ON COLUMN pulpo.chunks.revision_id IS 'Referencia a la revisión específica del documento';
