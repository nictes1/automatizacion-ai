-- Sprint 3.2: Prioridades y cuotas por job_type/workspace
-- Ejecutar después de 08_soft_delete_cascade.sql

-- 1) Prioridad por job
ALTER TABLE pulpo.processing_jobs
  ADD COLUMN IF NOT EXISTS priority INT DEFAULT 0;

-- Índice para ordenamiento por prioridad
CREATE INDEX IF NOT EXISTS idx_processing_jobs_priority
ON pulpo.processing_jobs (priority DESC, next_run_at NULLS FIRST, created_at ASC)
WHERE status IN ('pending','retry') AND paused = FALSE;

-- 2) Cuotas por workspace (soft)
CREATE TABLE IF NOT EXISTS pulpo.workspace_quotas(
  workspace_id TEXT PRIMARY KEY,
  max_processing INT NOT NULL DEFAULT 2,
  created_at TIMESTAMP DEFAULT now(),
  updated_at TIMESTAMP DEFAULT now()
);

-- 3) Vista de conteo de jobs en processing por workspace
CREATE OR REPLACE VIEW pulpo.v_ws_processing AS
SELECT 
  p.workspace_id, 
  COUNT(*) AS processing_count
FROM pulpo.processing_jobs p
WHERE p.status = 'processing'
  AND p.workspace_id IS NOT NULL
GROUP BY p.workspace_id;

-- 4) Función para obtener cuota de workspace
CREATE OR REPLACE FUNCTION pulpo.get_workspace_quota(_workspace_id TEXT)
RETURNS INT AS $$
DECLARE
  quota INT;
BEGIN
  SELECT max_processing INTO quota
  FROM pulpo.workspace_quotas
  WHERE workspace_id = _workspace_id;
  
  -- Si no hay cuota definida, usar default
  IF quota IS NULL THEN
    quota := 2; -- DEFAULT_WS_MAX_PROCESSING
  END IF;
  
  RETURN quota;
END;
$$ LANGUAGE plpgsql;

-- 5) Función para actualizar cuota de workspace
CREATE OR REPLACE FUNCTION pulpo.set_workspace_quota(_workspace_id TEXT, _max_processing INT)
RETURNS BOOLEAN AS $$
BEGIN
  INSERT INTO pulpo.workspace_quotas (workspace_id, max_processing, updated_at)
  VALUES (_workspace_id, _max_processing, now())
  ON CONFLICT (workspace_id) 
  DO UPDATE SET 
    max_processing = _max_processing,
    updated_at = now();
  
  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

-- 6) Función mejorada para obtener jobs con prioridades y cuotas
CREATE OR REPLACE FUNCTION pulpo.get_due_jobs_with_quotas(limit_count INT DEFAULT 20)
RETURNS TABLE(
    id UUID,
    document_id UUID,
    job_type TEXT,
    workspace_id TEXT,
    status TEXT,
    priority INT,
    retries INT,
    max_retries INT,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        p.id,
        p.document_id,
        p.job_type,
        p.workspace_id,
        p.status,
        p.priority,
        p.retries,
        p.max_retries,
        p.next_run_at,
        p.created_at
    FROM pulpo.processing_jobs p
    LEFT JOIN pulpo.v_ws_processing w
      ON w.workspace_id = p.workspace_id
    LEFT JOIN pulpo.workspace_quotas q
      ON q.workspace_id = p.workspace_id
    WHERE p.status IN ('pending','retry')
      AND p.paused = FALSE
      AND (p.next_run_at IS NULL OR p.next_run_at <= now())
      AND COALESCE(w.processing_count, 0) < COALESCE(q.max_processing, 2)  -- cuota soft
    ORDER BY p.priority DESC, p.next_run_at NULLS FIRST, p.created_at ASC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- 7) Función para estadísticas de cuotas
CREATE OR REPLACE FUNCTION pulpo.get_quota_stats()
RETURNS TABLE(
    workspace_id TEXT,
    max_processing INT,
    current_processing INT,
    utilization_pct NUMERIC
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        COALESCE(q.workspace_id, w.workspace_id) as workspace_id,
        COALESCE(q.max_processing, 2) as max_processing,
        COALESCE(w.processing_count, 0) as current_processing,
        CASE 
          WHEN COALESCE(q.max_processing, 2) > 0 THEN
            (COALESCE(w.processing_count, 0)::NUMERIC / COALESCE(q.max_processing, 2)::NUMERIC) * 100
          ELSE 0
        END as utilization_pct
    FROM pulpo.workspace_quotas q
    FULL OUTER JOIN pulpo.v_ws_processing w ON q.workspace_id = w.workspace_id
    ORDER BY utilization_pct DESC;
END;
$$ LANGUAGE plpgsql;

-- 8) Insertar cuotas por defecto para workspaces existentes (opcional)
INSERT INTO pulpo.workspace_quotas (workspace_id, max_processing)
SELECT DISTINCT workspace_id, 2
FROM pulpo.processing_jobs
WHERE workspace_id IS NOT NULL
  AND workspace_id NOT IN (SELECT workspace_id FROM pulpo.workspace_quotas)
ON CONFLICT (workspace_id) DO NOTHING;

-- 9) Comentarios para documentación
COMMENT ON COLUMN pulpo.processing_jobs.priority IS 'Prioridad del job (mayor = más prioritario)';
COMMENT ON TABLE pulpo.workspace_quotas IS 'Cuotas de procesamiento por workspace';
COMMENT ON VIEW pulpo.v_ws_processing IS 'Conteo de jobs en procesamiento por workspace';
COMMENT ON FUNCTION pulpo.get_workspace_quota(TEXT) IS 'Obtiene cuota máxima de procesamiento para workspace';
COMMENT ON FUNCTION pulpo.set_workspace_quota(TEXT, INT) IS 'Establece cuota máxima de procesamiento para workspace';
COMMENT ON FUNCTION pulpo.get_due_jobs_with_quotas(INT) IS 'Obtiene jobs listos respetando prioridades y cuotas';
COMMENT ON FUNCTION pulpo.get_quota_stats() IS 'Estadísticas de utilización de cuotas por workspace';

-- 10) Análisis para optimizar
ANALYZE pulpo.processing_jobs;
ANALYZE pulpo.workspace_quotas;

-- 11) Mostrar resumen
SELECT 
    'Sprint 3.2 - Prioridades y Cuotas' as feature,
    'Sistema de prioridades por job y cuotas por workspace' as description,
    now() as completed_at;
