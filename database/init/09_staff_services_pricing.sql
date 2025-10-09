-- =====================================================
-- STAFF SERVICES PRICING & DURATION
-- =====================================================
-- Migración: Mover precio y duración de service_types a staff_services
-- Cada profesional tiene su propio precio y tiempo por servicio
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- 1. Agregar columnas a staff_services
-- =====================================================

ALTER TABLE pulpo.staff_services
  ADD COLUMN IF NOT EXISTS price NUMERIC(10,2),
  ADD COLUMN IF NOT EXISTS currency TEXT DEFAULT 'ARS',
  ADD COLUMN IF NOT EXISTS duration_minutes INTEGER;

-- =====================================================
-- 2. Migrar datos existentes de service_types a staff_services
-- =====================================================

-- Para cada combinación staff+servicio existente, copiar precio y duración
UPDATE pulpo.staff_services ss
SET
  price = st.price,
  currency = st.currency,
  duration_minutes = st.duration_minutes
FROM pulpo.service_types st
WHERE ss.service_type_id = st.id
  AND ss.price IS NULL;  -- Solo si no tiene precio aún

-- =====================================================
-- 3. service_types: price → price_reference (opcional)
-- =====================================================

-- Renombrar price a price_reference (es solo referencia, no el precio real)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema = 'pulpo'
      AND table_name = 'service_types'
      AND column_name = 'price'
  ) THEN
    ALTER TABLE pulpo.service_types RENAME COLUMN price TO price_reference;
  END IF;
END $$;

-- Agregar comentario explicativo
COMMENT ON COLUMN pulpo.service_types.price_reference IS
  'Precio de referencia base. El precio real está en staff_services.price para cada profesional.';

COMMENT ON COLUMN pulpo.service_types.duration_minutes IS
  'Duración promedio de referencia. La duración real está en staff_services.duration_minutes para cada profesional.';

-- =====================================================
-- 4. Índices para performance
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_staff_services_lookup
  ON pulpo.staff_services(workspace_id, service_type_id, staff_id);

-- =====================================================
-- 5. Vista helper: Servicios con rangos de precio
-- =====================================================

CREATE OR REPLACE VIEW pulpo.service_pricing_summary AS
SELECT
  st.id AS service_type_id,
  st.workspace_id,
  st.name AS service_name,
  st.description,
  MIN(ss.price) AS min_price,
  MAX(ss.price) AS max_price,
  AVG(ss.price) AS avg_price,
  MIN(ss.duration_minutes) AS min_duration,
  MAX(ss.duration_minutes) AS max_duration,
  COUNT(DISTINCT ss.staff_id) AS staff_count,
  st.currency
FROM pulpo.service_types st
LEFT JOIN pulpo.staff_services ss ON ss.service_type_id = st.id
WHERE st.active = true
GROUP BY st.id, st.workspace_id, st.name, st.description, st.currency;

COMMENT ON VIEW pulpo.service_pricing_summary IS
  'Resumen de precios por servicio: min, max, avg y cantidad de staff que lo ofrece';

-- =====================================================
-- 6. Función: Obtener staff disponible para un servicio
-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.get_staff_for_service(
  p_workspace_id UUID,
  p_service_type_id UUID,
  p_date DATE DEFAULT CURRENT_DATE,
  p_time TIME DEFAULT NULL
)
RETURNS TABLE (
  staff_id UUID,
  staff_name TEXT,
  price NUMERIC(10,2),
  currency TEXT,
  duration_minutes INTEGER,
  is_available BOOLEAN
)
LANGUAGE plpgsql
AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id AS staff_id,
    s.name AS staff_name,
    ss.price,
    ss.currency,
    ss.duration_minutes,
    CASE
      WHEN p_time IS NULL THEN TRUE  -- Si no se especifica hora, asumimos disponible
      ELSE pulpo.is_staff_available(
        p_workspace_id,
        s.id,
        p_date,
        p_time,
        (p_time + (ss.duration_minutes || ' minutes')::INTERVAL)::TIME
      )
    END AS is_available
  FROM pulpo.staff s
  JOIN pulpo.staff_services ss ON ss.staff_id = s.id
  WHERE s.workspace_id = p_workspace_id
    AND ss.service_type_id = p_service_type_id
    AND s.is_active = true
  ORDER BY ss.price ASC;  -- Ordenar por precio (más barato primero)
END;
$$;

COMMENT ON FUNCTION pulpo.get_staff_for_service IS
  'Obtiene lista de staff que ofrece un servicio, con precio y disponibilidad opcional';

-- =====================================================
-- 7. Validaciones
-- =====================================================

-- Asegurar que staff_services siempre tenga precio y duración
ALTER TABLE pulpo.staff_services
  ALTER COLUMN price SET NOT NULL,
  ALTER COLUMN duration_minutes SET NOT NULL;

-- Constraint: precio positivo
ALTER TABLE pulpo.staff_services
  ADD CONSTRAINT staff_services_price_positive
  CHECK (price >= 0);

-- Constraint: duración positiva
ALTER TABLE pulpo.staff_services
  ADD CONSTRAINT staff_services_duration_positive
  CHECK (duration_minutes > 0);
