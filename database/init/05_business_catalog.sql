-- =====================================================
-- BUSINESS CATALOG TABLES
-- =====================================================
-- Tablas para catálogos de negocio (servicios, staff, menú)
-- Datos variables por workspace, sin RAG
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- STAFF / EMPLEADOS
-- =====================================================

CREATE TABLE pulpo.staff (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Información básica
  name text NOT NULL,
  email text,
  phone text,
  role text, -- "peluquero", "chef", "asesor", etc.

  -- Disponibilidad
  is_active boolean DEFAULT true,
  working_hours jsonb DEFAULT '{}'::jsonb, -- {"monday": ["09:00-13:00", "14:00-18:00"], ...}

  -- Integración Google Calendar
  google_calendar_id text, -- Email de Google Calendar

  -- Metadata
  skills jsonb DEFAULT '[]'::jsonb, -- ["corte", "coloración"] o ["cocina_italiana"]
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_staff_workspace ON pulpo.staff(workspace_id);
CREATE INDEX idx_staff_active ON pulpo.staff(workspace_id, is_active) WHERE is_active = true;
CREATE UNIQUE INDEX idx_staff_email_unique ON pulpo.staff(workspace_id, email);

COMMENT ON TABLE pulpo.staff IS 'Empleados/Staff del negocio (peluqueros, chefs, asesores)';
COMMENT ON COLUMN pulpo.staff.working_hours IS 'Horarios de trabajo en formato JSON: {"monday": ["09:00-13:00"], "tuesday": []}';
COMMENT ON COLUMN pulpo.staff.skills IS 'Habilidades/especialidades del empleado: ["corte", "coloración"]';

-- =====================================================
-- SERVICE TYPES / TIPOS DE SERVICIO
-- =====================================================

CREATE TABLE pulpo.service_types (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Información del servicio
  name text NOT NULL, -- "Corte de Cabello", "Coloración", "Menú Ejecutivo"
  description text,
  category text, -- "hair", "nails", "spa", "food", etc.

  -- Precio y duración
  price numeric(10,2),
  currency text DEFAULT 'ARS',
  duration_minutes integer DEFAULT 60,

  -- Disponibilidad
  is_active boolean DEFAULT true,
  requires_staff boolean DEFAULT true, -- Si necesita asignación de staff

  -- Metadata
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_service_types_workspace ON pulpo.service_types(workspace_id);
CREATE INDEX idx_service_types_active ON pulpo.service_types(workspace_id, is_active) WHERE is_active = true;
CREATE INDEX idx_service_types_category ON pulpo.service_types(workspace_id, category);
CREATE UNIQUE INDEX idx_service_types_name_unique ON pulpo.service_types(workspace_id, name);

COMMENT ON TABLE pulpo.service_types IS 'Catálogo de servicios ofrecidos por el negocio';
COMMENT ON COLUMN pulpo.service_types.requires_staff IS 'Si true, el servicio requiere asignación de empleado';

-- =====================================================
-- STAFF SERVICES (M2M)
-- =====================================================

CREATE TABLE pulpo.staff_services (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  staff_id uuid NOT NULL REFERENCES pulpo.staff(id) ON DELETE CASCADE,
  service_type_id uuid NOT NULL REFERENCES pulpo.service_types(id) ON DELETE CASCADE,

  -- Configuración específica
  custom_duration_minutes integer, -- Duración custom para este staff
  custom_price numeric(10,2), -- Precio custom para este staff

  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(staff_id, service_type_id)
);

CREATE INDEX idx_staff_services_workspace ON pulpo.staff_services(workspace_id);
CREATE INDEX idx_staff_services_staff ON pulpo.staff_services(staff_id);
CREATE INDEX idx_staff_services_service ON pulpo.staff_services(service_type_id);

COMMENT ON TABLE pulpo.staff_services IS 'Relación M2M: qué servicios puede realizar cada empleado';

-- =====================================================
-- MENU ITEMS (YA EXISTÍA - AGREGAR ÍNDICES)
-- =====================================================

-- Agregar índices a tabla existente
CREATE INDEX IF NOT EXISTS idx_menu_items_workspace ON pulpo.menu_items(workspace_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_categoria ON pulpo.menu_items(workspace_id, categoria);
CREATE INDEX IF NOT EXISTS idx_menu_items_disponible ON pulpo.menu_items(workspace_id, disponible) WHERE disponible = true;
CREATE UNIQUE INDEX IF NOT EXISTS idx_menu_items_sku_unique ON pulpo.menu_items(workspace_id, sku);

COMMENT ON TABLE pulpo.menu_items IS 'Catálogo de items del menú (gastronomía)';

-- =====================================================
-- ACTUALIZAR APPOINTMENTS CON RELACIONES
-- =====================================================

-- Agregar columnas a appointments
ALTER TABLE pulpo.appointments
  ADD COLUMN IF NOT EXISTS service_type_id uuid REFERENCES pulpo.service_types(id),
  ADD COLUMN IF NOT EXISTS staff_id uuid REFERENCES pulpo.staff(id),
  ADD COLUMN IF NOT EXISTS client_name text,
  ADD COLUMN IF NOT EXISTS client_email text,
  ADD COLUMN IF NOT EXISTS client_phone text,
  ADD COLUMN IF NOT EXISTS google_event_id text; -- ID del evento en Google Calendar

CREATE INDEX IF NOT EXISTS idx_appointments_service_type ON pulpo.appointments(service_type_id);
CREATE INDEX IF NOT EXISTS idx_appointments_staff ON pulpo.appointments(staff_id);
CREATE INDEX IF NOT EXISTS idx_appointments_scheduled ON pulpo.appointments(workspace_id, scheduled_at);

COMMENT ON COLUMN pulpo.appointments.service_type_id IS 'Tipo de servicio agendado';
COMMENT ON COLUMN pulpo.appointments.staff_id IS 'Empleado asignado al turno';
COMMENT ON COLUMN pulpo.appointments.google_event_id IS 'ID del evento en Google Calendar';

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================

ALTER TABLE pulpo.staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.service_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.staff_services ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation_staff ON pulpo.staff
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_service_types ON pulpo.service_types
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_staff_services ON pulpo.staff_services
  USING (workspace_id::text = current_setting('app.workspace_id', true));

-- =====================================================
-- FUNCTIONS - GET AVAILABLE STAFF FOR SERVICE
-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.get_available_staff_for_service(
  p_workspace_id uuid,
  p_service_type_id uuid,
  p_date date,
  p_time time
)
RETURNS TABLE (
  staff_id uuid,
  staff_name text,
  staff_email text,
  can_perform boolean
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id,
    s.name,
    s.email,
    EXISTS(
      SELECT 1 FROM pulpo.staff_services ss
      WHERE ss.staff_id = s.id AND ss.service_type_id = p_service_type_id
    ) as can_perform
  FROM pulpo.staff s
  WHERE s.workspace_id = p_workspace_id
    AND s.is_active = true
  ORDER BY can_perform DESC, s.name;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.get_available_staff_for_service IS 'Obtiene staff disponible para un servicio en fecha/hora específica';

-- =====================================================
-- TRIGGERS - UPDATE TIMESTAMPS
-- =====================================================

CREATE TRIGGER update_staff_updated_at
  BEFORE UPDATE ON pulpo.staff
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_service_types_updated_at
  BEFORE UPDATE ON pulpo.service_types
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
