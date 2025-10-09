-- =====================================================
-- STAFF SERVICES - Relación many-to-many
-- =====================================================
-- Cada staff member puede ofrecer múltiples servicios
-- Cada servicio tiene precio y duración específica por staff
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- Tabla de relación Staff <-> Services
-- =====================================================

CREATE TABLE IF NOT EXISTS pulpo.staff_services (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  staff_member_id UUID NOT NULL REFERENCES pulpo.staff_members(id) ON DELETE CASCADE,
  service_type_id UUID NOT NULL REFERENCES pulpo.service_types(id) ON DELETE CASCADE,

  -- Precio específico de ESTE staff para ESTE servicio
  price NUMERIC(10,2) NOT NULL CHECK (price >= 0),
  currency TEXT NOT NULL DEFAULT 'ARS',

  -- Duración específica de ESTE staff para ESTE servicio
  duration_minutes INTEGER NOT NULL CHECK (duration_minutes > 0),

  -- Metadata
  is_active BOOLEAN DEFAULT TRUE,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW(),

  -- Constraints
  UNIQUE(workspace_id, staff_member_id, service_type_id)
);

-- =====================================================
-- Índices
-- =====================================================

CREATE INDEX IF NOT EXISTS idx_staff_services_workspace
  ON pulpo.staff_services(workspace_id);

CREATE INDEX IF NOT EXISTS idx_staff_services_staff
  ON pulpo.staff_services(staff_member_id);

CREATE INDEX IF NOT EXISTS idx_staff_services_service
  ON pulpo.staff_services(service_type_id);

CREATE INDEX IF NOT EXISTS idx_staff_services_lookup
  ON pulpo.staff_services(workspace_id, service_type_id, is_active);

-- =====================================================
-- RLS Policy
-- =====================================================

ALTER TABLE pulpo.staff_services ENABLE ROW LEVEL SECURITY;

CREATE POLICY IF NOT EXISTS staff_services_workspace_isolation
  ON pulpo.staff_services
  USING (workspace_id::text = current_setting('app.current_workspace_id', true));

-- =====================================================
-- Trigger para updated_at
-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.update_staff_services_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER staff_services_updated_at
  BEFORE UPDATE ON pulpo.staff_services
  FOR EACH ROW
  EXECUTE FUNCTION pulpo.update_staff_services_updated_at();

-- =====================================================
-- Vista: Resumen de precios por servicio
-- =====================================================

CREATE OR REPLACE VIEW pulpo.v_service_pricing AS
SELECT
  st.id AS service_type_id,
  st.workspace_id,
  st.name AS service_name,
  st.description,
  MIN(ss.price) AS min_price,
  MAX(ss.price) AS max_price,
  ROUND(AVG(ss.price), 2) AS avg_price,
  MIN(ss.duration_minutes) AS min_duration,
  MAX(ss.duration_minutes) AS max_duration,
  COUNT(DISTINCT ss.staff_member_id) AS staff_count,
  COALESCE(ss.currency, st.currency) AS currency
FROM pulpo.service_types st
LEFT JOIN pulpo.staff_services ss
  ON ss.service_type_id = st.id AND ss.is_active = TRUE
WHERE st.active = TRUE
GROUP BY st.id, st.workspace_id, st.name, st.description, st.currency, ss.currency;

COMMENT ON VIEW pulpo.v_service_pricing IS 'Resumen de pricing: min, max, avg por servicio';

-- =====================================================
-- Función: Get staff que ofrece un servicio
-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.get_staff_for_service(
  p_workspace_id UUID,
  p_service_type_id UUID
)
RETURNS TABLE (
  staff_id UUID,
  staff_name TEXT,
  staff_email TEXT,
  price NUMERIC(10,2),
  currency TEXT,
  duration_minutes INTEGER
)
LANGUAGE SQL STABLE
AS $$
  SELECT
    sm.id AS staff_id,
    sm.name AS staff_name,
    sm.email AS staff_email,
    ss.price,
    ss.currency,
    ss.duration_minutes
  FROM pulpo.staff_members sm
  JOIN pulpo.staff_services ss ON ss.staff_member_id = sm.id
  WHERE sm.workspace_id = p_workspace_id
    AND ss.service_type_id = p_service_type_id
    AND sm.active = TRUE
    AND ss.is_active = TRUE
  ORDER BY ss.price ASC;  -- Más barato primero
$$;

COMMENT ON FUNCTION pulpo.get_staff_for_service IS
  'Devuelve staff que ofrece un servicio con precio/duración';

-- =====================================================
-- Seed Data Básico
-- =====================================================

DO $$
DECLARE
  v_workspace_id UUID := '550e8400-e29b-41d4-a716-446655440000';
  v_maria_id UUID;
  v_juan_id UUID;
  v_corte_id UUID;
BEGIN
  -- Obtener IDs
  SELECT id INTO v_corte_id
  FROM pulpo.service_types
  WHERE workspace_id = v_workspace_id AND name = 'Corte de Cabello'
  LIMIT 1;

  SELECT id INTO v_maria_id
  FROM pulpo.staff_members
  WHERE workspace_id = v_workspace_id AND name ILIKE '%María%'
  LIMIT 1;

  SELECT id INTO v_juan_id
  FROM pulpo.staff_members
  WHERE workspace_id = v_workspace_id AND name ILIKE '%Juan%'
  LIMIT 1;

  -- Insertar relaciones si existen los registros
  IF v_corte_id IS NOT NULL THEN
    IF v_maria_id IS NOT NULL THEN
      INSERT INTO pulpo.staff_services (workspace_id, staff_member_id, service_type_id, price, duration_minutes)
      VALUES (v_workspace_id, v_maria_id, v_corte_id, 6000, 45)
      ON CONFLICT (workspace_id, staff_member_id, service_type_id) DO UPDATE
      SET price = 6000, duration_minutes = 45;
    END IF;

    IF v_juan_id IS NOT NULL THEN
      INSERT INTO pulpo.staff_services (workspace_id, staff_member_id, service_type_id, price, duration_minutes)
      VALUES (v_workspace_id, v_juan_id, v_corte_id, 4500, 30)
      ON CONFLICT (workspace_id, staff_member_id, service_type_id) DO UPDATE
      SET price = 4500, duration_minutes = 30;
    END IF;
  END IF;

  RAISE NOTICE 'Staff services created successfully';
END $$;
