-- Sprint 3.1: Soft delete en cascada para chunks y embeddings
-- Ejecutar después de 07_sprint31_indexes.sql

-- 1) Función para soft delete en cascada de documentos
CREATE OR REPLACE FUNCTION pulpo.soft_delete_document_cascade(_document_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
  doc_exists BOOLEAN;
BEGIN
  -- Verificar que el documento existe y no está ya eliminado
  SELECT EXISTS(
    SELECT 1 FROM pulpo.documents 
    WHERE id = _document_id AND deleted_at IS NULL
  ) INTO doc_exists;
  
  IF NOT doc_exists THEN
    RETURN FALSE;
  END IF;
  
  -- Soft delete del documento
  UPDATE pulpo.documents 
  SET deleted_at = now(), updated_at = now()
  WHERE id = _document_id;
  
  -- Soft delete de chunks relacionados
  UPDATE pulpo.chunks 
  SET deleted_at = now(), updated_at = now()
  WHERE document_id = _document_id AND deleted_at IS NULL;
  
  -- Soft delete de embeddings relacionados
  UPDATE pulpo.chunk_embeddings 
  SET deleted_at = now(), updated_at = now()
  WHERE chunk_id IN (
    SELECT id FROM pulpo.chunks 
    WHERE document_id = _document_id
  ) AND deleted_at IS NULL;
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 2) Función para restaurar documento en cascada
CREATE OR REPLACE FUNCTION pulpo.restore_document_cascade(_document_id UUID)
RETURNS BOOLEAN AS $$
DECLARE
  doc_exists BOOLEAN;
BEGIN
  -- Verificar que el documento existe y está eliminado
  SELECT EXISTS(
    SELECT 1 FROM pulpo.documents 
    WHERE id = _document_id AND deleted_at IS NOT NULL
  ) INTO doc_exists;
  
  IF NOT doc_exists THEN
    RETURN FALSE;
  END IF;
  
  -- Restaurar documento
  UPDATE pulpo.documents 
  SET deleted_at = NULL, updated_at = now()
  WHERE id = _document_id;
  
  -- Restaurar chunks relacionados
  UPDATE pulpo.chunks 
  SET deleted_at = NULL, updated_at = now()
  WHERE document_id = _document_id AND deleted_at IS NOT NULL;
  
  -- Restaurar embeddings relacionados
  UPDATE pulpo.chunk_embeddings 
  SET deleted_at = NULL, updated_at = now()
  WHERE chunk_id IN (
    SELECT id FROM pulpo.chunks 
    WHERE document_id = _document_id
  ) AND deleted_at IS NOT NULL;
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 3) Función para limpiar chunks y embeddings huérfanos
CREATE OR REPLACE FUNCTION pulpo.cleanup_orphaned_chunks()
RETURNS INT AS $$
DECLARE
  chunks_deleted INT;
  embeddings_deleted INT;
BEGIN
  -- Soft delete chunks huérfanos (documento eliminado)
  UPDATE pulpo.chunks 
  SET deleted_at = now(), updated_at = now()
  WHERE deleted_at IS NULL 
    AND document_id IN (
      SELECT id FROM pulpo.documents WHERE deleted_at IS NOT NULL
    );
  
  GET DIAGNOSTICS chunks_deleted = ROW_COUNT;
  
  -- Soft delete embeddings huérfanos (chunk eliminado)
  UPDATE pulpo.chunk_embeddings 
  SET deleted_at = now(), updated_at = now()
  WHERE deleted_at IS NULL 
    AND chunk_id IN (
      SELECT id FROM pulpo.chunks WHERE deleted_at IS NOT NULL
    );
  
  GET DIAGNOSTICS embeddings_deleted = ROW_COUNT;
  
  -- Retornar total de elementos limpiados
  RETURN chunks_deleted + embeddings_deleted;
END;
$$ LANGUAGE plpgsql;

-- 4) Trigger para soft delete automático en cascada (opcional)
-- Solo si quieres que sea automático al eliminar documento
CREATE OR REPLACE FUNCTION pulpo.trigger_soft_delete_cascade()
RETURNS TRIGGER AS $$
BEGIN
  -- Si se está haciendo soft delete del documento
  IF OLD.deleted_at IS NULL AND NEW.deleted_at IS NOT NULL THEN
    -- Soft delete chunks
    UPDATE pulpo.chunks 
    SET deleted_at = NEW.deleted_at, updated_at = now()
    WHERE document_id = NEW.id AND deleted_at IS NULL;
    
    -- Soft delete embeddings
    UPDATE pulpo.chunk_embeddings 
    SET deleted_at = NEW.deleted_at, updated_at = now()
    WHERE chunk_id IN (
      SELECT id FROM pulpo.chunks 
      WHERE document_id = NEW.id
    ) AND deleted_at IS NULL;
  END IF;
  
  -- Si se está restaurando el documento
  IF OLD.deleted_at IS NOT NULL AND NEW.deleted_at IS NULL THEN
    -- Restaurar chunks
    UPDATE pulpo.chunks 
    SET deleted_at = NULL, updated_at = now()
    WHERE document_id = NEW.id AND deleted_at IS NOT NULL;
    
    -- Restaurar embeddings
    UPDATE pulpo.chunk_embeddings 
    SET deleted_at = NULL, updated_at = now()
    WHERE chunk_id IN (
      SELECT id FROM pulpo.chunks 
      WHERE document_id = NEW.id
    ) AND deleted_at IS NOT NULL;
  END IF;
  
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Crear trigger (comentado por defecto - descomenta si quieres automático)
-- DROP TRIGGER IF EXISTS trigger_document_soft_delete_cascade ON pulpo.documents;
-- CREATE TRIGGER trigger_document_soft_delete_cascade
--   AFTER UPDATE ON pulpo.documents
--   FOR EACH ROW
--   EXECUTE FUNCTION pulpo.trigger_soft_delete_cascade();

-- 5) Vista para documentos con conteo de chunks/embeddings
CREATE OR REPLACE VIEW pulpo.documents_with_counts AS
SELECT 
  d.*,
  COUNT(DISTINCT c.id) as chunks_count,
  COUNT(DISTINCT e.id) as embeddings_count
FROM pulpo.documents d
LEFT JOIN pulpo.chunks c ON c.document_id = d.id AND c.deleted_at IS NULL
LEFT JOIN pulpo.chunk_embeddings e ON e.chunk_id = c.id AND e.deleted_at IS NULL
GROUP BY d.id;

-- 6) Comentarios para documentación
COMMENT ON FUNCTION pulpo.soft_delete_document_cascade(UUID) IS 'Soft delete de documento con cascada a chunks y embeddings';
COMMENT ON FUNCTION pulpo.restore_document_cascade(UUID) IS 'Restaura documento con cascada a chunks y embeddings';
COMMENT ON FUNCTION pulpo.cleanup_orphaned_chunks() IS 'Limpia chunks y embeddings huérfanos';
COMMENT ON VIEW pulpo.documents_with_counts IS 'Vista de documentos con conteo de chunks y embeddings';

-- 7) Mostrar resumen
SELECT 
    'Sprint 3.1 - Soft Delete en Cascada' as feature,
    'Funciones para soft delete/restore en cascada de documentos, chunks y embeddings' as description,
    now() as completed_at;
