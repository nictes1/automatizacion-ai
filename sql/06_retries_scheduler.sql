-- Sprint 3: Retries + Scheduler + DLQ
-- Ejecutar después de 05_ocr_metrics.sql

-- 1) Campos para scheduler/backoff/idempotencia
ALTER TABLE pulpo.processing_jobs
  ADD COLUMN IF NOT EXISTS next_run_at TIMESTAMP NULL,
  ADD COLUMN IF NOT EXISTS backoff_base_seconds INT DEFAULT 5,
  ADD COLUMN IF NOT EXISTS backoff_factor NUMERIC DEFAULT 2.0,   -- exponencial
  ADD COLUMN IF NOT EXISTS jitter_seconds INT DEFAULT 5,
  ADD COLUMN IF NOT EXISTS external_key TEXT NULL,                -- idempotencia
  ADD COLUMN IF NOT EXISTS paused BOOLEAN DEFAULT FALSE;

-- 2) Índices para polling eficiente
CREATE INDEX IF NOT EXISTS idx_jobs_poll
  ON pulpo.processing_jobs (status, next_run_at)
  WHERE status IN ('pending','retry') AND paused = FALSE;

-- Índice único para idempotencia
CREATE UNIQUE INDEX IF NOT EXISTS uq_jobs_external_key
  ON pulpo.processing_jobs (job_type, external_key)
  WHERE external_key IS NOT NULL;

-- Índice para DLQ
CREATE INDEX IF NOT EXISTS idx_jobs_dlq
  ON pulpo.processing_jobs (job_type, status, retries, max_retries)
  WHERE status = 'failed' AND retries >= max_retries;

-- 3) Estados normalizados
-- valores esperados: pending | processing | completed | failed | retry

-- 4) Función: calcular próxima ejecución (exponencial + jitter)
CREATE OR REPLACE FUNCTION pulpo.compute_next_run_at(
  retries INT,
  base INT,
  factor NUMERIC,
  jitter INT
) RETURNS TIMESTAMP AS $$
DECLARE
  delay_seconds NUMERIC;
BEGIN
  -- Usar retries-1 para que el primer retry use base * 1 (no base * factor)
  delay_seconds := base * (factor ^ GREATEST(retries-1, 0) :: NUMERIC) + (random() * jitter);
  RETURN now() + make_interval(secs => delay_seconds);
END;
$$ LANGUAGE plpgsql;

-- 5) Vista DLQ (Dead Letter Queue)
CREATE OR REPLACE VIEW pulpo.processing_jobs_dlq AS
SELECT *
FROM pulpo.processing_jobs
WHERE job_type IN ('ocr','chunking','embedding')  -- extensible
  AND status = 'failed'
  AND retries >= max_retries;

-- 6) Funciones de requeue
CREATE OR REPLACE FUNCTION pulpo.requeue_job(_id TEXT)
RETURNS BOOLEAN AS $$
DECLARE
  r pulpo.processing_jobs%ROWTYPE;
BEGIN
  SELECT * INTO r FROM pulpo.processing_jobs WHERE id=_id FOR UPDATE;
  IF NOT FOUND THEN RETURN FALSE; END IF;

  UPDATE pulpo.processing_jobs
     SET status='pending',
         paused=FALSE,
         next_run_at=now(),
         retries=0,              -- Reset retries
         updated_at=now()
   WHERE id=_id;

  RETURN TRUE;
END;
$$ LANGUAGE plpgsql;

CREATE OR REPLACE FUNCTION pulpo.requeue_failed_jobs(_job_type TEXT DEFAULT NULL)
RETURNS INT AS $$
DECLARE
  cnt INT;
BEGIN
  UPDATE pulpo.processing_jobs
     SET status='pending',
         paused=FALSE,
         next_run_at=now(),
         retries=0,              -- Reset retries
         updated_at=now()
   WHERE status='failed'
     AND retries >= max_retries
     AND (_job_type IS NULL OR job_type=_job_type);

  GET DIAGNOSTICS cnt = ROW_COUNT;
  RETURN cnt;
END;
$$ LANGUAGE plpgsql;

-- 7) Limpieza suave por antigüedad en DLQ
CREATE OR REPLACE FUNCTION pulpo.cleanup_dlq(retention_days INT DEFAULT 30)
RETURNS INT AS $$
DECLARE
  del INT;
BEGIN
  DELETE FROM pulpo.processing_jobs
   WHERE status='failed'
     AND retries >= max_retries
     AND updated_at < now() - (retention_days || ' days')::INTERVAL;

  GET DIAGNOSTICS del = ROW_COUNT;
  RETURN del;
END;
$$ LANGUAGE plpgsql;

-- 8) Función para estadísticas de jobs
CREATE OR REPLACE FUNCTION pulpo.get_job_stats()
RETURNS TABLE(
    job_type TEXT,
    status TEXT,
    total BIGINT,
    avg_retries NUMERIC,
    oldest_job TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pj.job_type,
        pj.status,
        COUNT(*) as total,
        AVG(pj.retries) as avg_retries,
        MIN(pj.created_at) as oldest_job
    FROM pulpo.processing_jobs pj
    GROUP BY pj.job_type, pj.status
    ORDER BY pj.job_type, pj.status;
END;
$$ LANGUAGE plpgsql;

-- 9) Vista de métricas para Prometheus
CREATE OR REPLACE VIEW pulpo.processing_jobs_metrics AS
SELECT 
    job_type, 
    status, 
    COUNT(*) AS total,
    AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
FROM pulpo.processing_jobs
WHERE started_at IS NOT NULL
GROUP BY job_type, status
UNION ALL
SELECT 
    job_type,
    'dlq' as status,
    COUNT(*) AS total,
    NULL as avg_duration_seconds
FROM pulpo.processing_jobs_dlq
GROUP BY job_type;

-- 10) Función para pausar/reanudar jobs por tipo
CREATE OR REPLACE FUNCTION pulpo.pause_jobs_by_type(_job_type TEXT, _pause BOOLEAN)
RETURNS INT AS $$
DECLARE
  cnt INT;
BEGIN
  UPDATE pulpo.processing_jobs
     SET paused=_pause,
         updated_at=now()
   WHERE job_type=_job_type
     AND status IN ('pending', 'retry');

  GET DIAGNOSTICS cnt = ROW_COUNT;
  RETURN cnt;
END;
$$ LANGUAGE plpgsql;

-- 11) Función para obtener jobs próximos a ejecutar
CREATE OR REPLACE FUNCTION pulpo.get_next_jobs(limit_count INT DEFAULT 10)
RETURNS TABLE(
    id UUID,
    job_type TEXT,
    document_id UUID,
    status TEXT,
    retries INT,
    max_retries INT,
    next_run_at TIMESTAMP,
    created_at TIMESTAMP
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        pj.id,
        pj.job_type,
        pj.document_id,
        pj.status,
        pj.retries,
        pj.max_retries,
        pj.next_run_at,
        pj.created_at
    FROM pulpo.processing_jobs pj
    WHERE pj.status IN ('pending','retry')
      AND pj.paused = FALSE
      AND (pj.next_run_at IS NULL OR pj.next_run_at <= now())
    ORDER BY pj.next_run_at NULLS FIRST, pj.created_at ASC
    LIMIT limit_count;
END;
$$ LANGUAGE plpgsql;

-- 12) Comentarios para documentación
COMMENT ON COLUMN pulpo.processing_jobs.next_run_at IS 'Timestamp de próxima ejecución programada';
COMMENT ON COLUMN pulpo.processing_jobs.backoff_base_seconds IS 'Segundos base para backoff exponencial';
COMMENT ON COLUMN pulpo.processing_jobs.backoff_factor IS 'Factor exponencial para backoff (ej: 2.0)';
COMMENT ON COLUMN pulpo.processing_jobs.jitter_seconds IS 'Segundos de jitter aleatorio para evitar thundering herd';
COMMENT ON COLUMN pulpo.processing_jobs.external_key IS 'Clave externa para idempotencia (única por job_type)';
COMMENT ON COLUMN pulpo.processing_jobs.paused IS 'Si el job está pausado (no se ejecuta)';

COMMENT ON FUNCTION pulpo.compute_next_run_at(INT, INT, NUMERIC, INT) IS 'Calcula próxima ejecución con backoff exponencial + jitter';
COMMENT ON VIEW pulpo.processing_jobs_dlq IS 'Jobs fallidos que superaron max_retries (Dead Letter Queue)';
COMMENT ON FUNCTION pulpo.requeue_job(TEXT) IS 'Reencola un job específico para reintento';
COMMENT ON FUNCTION pulpo.requeue_failed_jobs(TEXT) IS 'Reencola todos los jobs fallidos de un tipo (o todos)';

-- 13) Ejecutar análisis para optimizar
ANALYZE pulpo.processing_jobs;

-- 14) Mostrar estadísticas iniciales
SELECT * FROM pulpo.get_job_stats();

-- 15) Mostrar resumen de Sprint 3
SELECT 
    'Sprint 3 - Retries + Scheduler + DLQ' as feature,
    'Sistema de reintentos con backoff exponencial, scheduler genérico y DLQ' as description,
    now() as completed_at;
