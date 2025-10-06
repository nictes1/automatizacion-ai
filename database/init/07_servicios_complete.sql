-- =====================================================
-- SERVICIOS VERTICAL - SCHEMA COMPLETO
-- =====================================================
-- Tablas adicionales para vertical servicios (peluquería)
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- BUSINESS HOURS - HORARIOS DEL NEGOCIO
-- =====================================================

CREATE TABLE pulpo.business_hours (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Día de la semana (0=domingo, 1=lunes, ..., 6=sábado)
  day_of_week integer NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),

  -- Horarios (puede haber múltiples bloques por día)
  time_blocks jsonb NOT NULL DEFAULT '[]'::jsonb,
  -- Ejemplo: [{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]

  -- Configuración
  is_open boolean DEFAULT true, -- Si abre ese día
  is_holiday boolean DEFAULT false, -- Si es feriado/día especial

  -- Metadata
  notes text, -- Notas especiales del día
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(workspace_id, day_of_week)
);

CREATE INDEX idx_business_hours_workspace ON pulpo.business_hours(workspace_id);
CREATE INDEX idx_business_hours_day ON pulpo.business_hours(workspace_id, day_of_week);

COMMENT ON TABLE pulpo.business_hours IS 'Horarios de atención del negocio por día de semana';
COMMENT ON COLUMN pulpo.business_hours.day_of_week IS '0=Domingo, 1=Lunes, 2=Martes, 3=Miércoles, 4=Jueves, 5=Viernes, 6=Sábado';
COMMENT ON COLUMN pulpo.business_hours.time_blocks IS 'Array de bloques horarios: [{"open": "09:00", "close": "13:00"}]';

-- =====================================================
-- SPECIAL DATES - FERIADOS Y DÍAS ESPECIALES
-- =====================================================

CREATE TABLE pulpo.special_dates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Fecha especial
  date date NOT NULL,

  -- Tipo
  type text NOT NULL CHECK (type IN ('holiday', 'closed', 'special_hours')),

  -- Horarios especiales (si type='special_hours')
  time_blocks jsonb DEFAULT '[]'::jsonb,

  -- Información
  name text, -- "Navidad", "Aniversario", etc.
  description text,
  is_recurring boolean DEFAULT false, -- Si se repite cada año

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(workspace_id, date)
);

CREATE INDEX idx_special_dates_workspace ON pulpo.special_dates(workspace_id);
CREATE INDEX idx_special_dates_date ON pulpo.special_dates(workspace_id, date);

COMMENT ON TABLE pulpo.special_dates IS 'Feriados y días con horarios especiales';

-- =====================================================
-- STAFF AVAILABILITY - DISPONIBILIDAD DE STAFF
-- =====================================================

CREATE TABLE pulpo.staff_availability (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  staff_id uuid NOT NULL REFERENCES pulpo.staff(id) ON DELETE CASCADE,

  -- Tipo de ausencia/disponibilidad
  type text NOT NULL CHECK (type IN ('available', 'vacation', 'sick_leave', 'day_off', 'blocked')),

  -- Rango de fechas
  start_date date NOT NULL,
  end_date date NOT NULL,

  -- Horarios específicos (opcional, si es parcial)
  start_time time,
  end_time time,

  -- All day o parcial
  is_all_day boolean DEFAULT true,

  -- Información
  reason text,
  notes text,

  -- Metadata
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CHECK (end_date >= start_date)
);

CREATE INDEX idx_staff_availability_workspace ON pulpo.staff_availability(workspace_id);
CREATE INDEX idx_staff_availability_staff ON pulpo.staff_availability(staff_id);
CREATE INDEX idx_staff_availability_dates ON pulpo.staff_availability(workspace_id, start_date, end_date);

COMMENT ON TABLE pulpo.staff_availability IS 'Disponibilidad y ausencias de staff (vacaciones, días libres, etc.)';
COMMENT ON COLUMN pulpo.staff_availability.type IS 'available: disponible especial, vacation: vacaciones, sick_leave: enfermedad, day_off: día libre, blocked: bloqueado';

-- =====================================================
-- PROMOTIONS - PROMOCIONES Y DESCUENTOS
-- =====================================================

CREATE TABLE pulpo.promotions (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Información básica
  name text NOT NULL,
  description text,
  code text, -- Código promocional (opcional)

  -- Tipo de descuento
  discount_type text NOT NULL CHECK (discount_type IN ('percentage', 'fixed_amount', 'free_service')),
  discount_value numeric(10,2), -- 20 (para 20%) o 500 (para $500)

  -- Aplicación
  applies_to text NOT NULL CHECK (applies_to IN ('all', 'specific_services', 'specific_staff')),
  service_type_ids jsonb DEFAULT '[]'::jsonb, -- Array de UUIDs si applies_to='specific_services'
  staff_ids jsonb DEFAULT '[]'::jsonb, -- Array de UUIDs si applies_to='specific_staff'

  -- Condiciones
  min_amount numeric(10,2), -- Monto mínimo de compra
  max_uses integer, -- Usos máximos totales
  max_uses_per_customer integer DEFAULT 1, -- Usos máximos por cliente
  current_uses integer DEFAULT 0,

  -- Vigencia
  valid_from date NOT NULL,
  valid_until date NOT NULL,

  -- Horarios específicos (opcional)
  valid_days_of_week jsonb DEFAULT '[0,1,2,3,4,5,6]'::jsonb, -- [0,1,2,3,4,5,6] = todos los días
  valid_hours jsonb DEFAULT '{"start": "00:00", "end": "23:59"}'::jsonb,

  -- Estado
  is_active boolean DEFAULT true,

  -- Metadata
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CHECK (valid_until >= valid_from),
  CHECK (max_uses IS NULL OR max_uses > 0),
  CHECK (current_uses >= 0)
);

CREATE INDEX idx_promotions_workspace ON pulpo.promotions(workspace_id);
CREATE INDEX idx_promotions_active ON pulpo.promotions(workspace_id, is_active) WHERE is_active = true;
CREATE INDEX idx_promotions_dates ON pulpo.promotions(workspace_id, valid_from, valid_until);
CREATE INDEX idx_promotions_code ON pulpo.promotions(workspace_id, code) WHERE code IS NOT NULL;

COMMENT ON TABLE pulpo.promotions IS 'Promociones y descuentos para servicios';
COMMENT ON COLUMN pulpo.promotions.discount_type IS 'percentage: porcentaje (ej: 20%), fixed_amount: monto fijo (ej: $500), free_service: servicio gratis';

-- =====================================================
-- SERVICE PACKAGES - PAQUETES DE SERVICIOS
-- =====================================================

CREATE TABLE pulpo.service_packages (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Información básica
  name text NOT NULL,
  description text,

  -- Servicios incluidos
  service_type_ids jsonb NOT NULL, -- Array de UUIDs: ["uuid1", "uuid2"]

  -- Precio
  package_price numeric(10,2) NOT NULL,
  regular_price numeric(10,2), -- Suma de precios individuales (para mostrar ahorro)
  currency text DEFAULT 'ARS',

  -- Duración total (calculada o custom)
  total_duration_minutes integer,

  -- Configuración
  is_active boolean DEFAULT true,
  requires_same_staff boolean DEFAULT true, -- Si todos los servicios deben ser con el mismo staff

  -- Imagen
  image_url text,

  -- Metadata
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX idx_service_packages_workspace ON pulpo.service_packages(workspace_id);
CREATE INDEX idx_service_packages_active ON pulpo.service_packages(workspace_id, is_active) WHERE is_active = true;

COMMENT ON TABLE pulpo.service_packages IS 'Paquetes/combos de servicios con precio especial';
COMMENT ON COLUMN pulpo.service_packages.service_type_ids IS 'Array de IDs de servicios incluidos en el paquete';

-- =====================================================
-- APPOINTMENT RATINGS - CALIFICACIONES DE TURNOS
-- =====================================================

CREATE TABLE pulpo.appointment_ratings (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  appointment_id uuid NOT NULL REFERENCES pulpo.appointments(id) ON DELETE CASCADE,

  -- Calificación
  rating integer NOT NULL CHECK (rating BETWEEN 1 AND 5),

  -- Feedback
  comment text,

  -- Aspectos específicos (opcional)
  service_quality integer CHECK (service_quality BETWEEN 1 AND 5),
  staff_friendliness integer CHECK (staff_friendliness BETWEEN 1 AND 5),
  cleanliness integer CHECK (cleanliness BETWEEN 1 AND 5),
  punctuality integer CHECK (punctuality BETWEEN 1 AND 5),

  -- Info del cliente
  client_name text,
  client_email text,

  -- Metadata
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(appointment_id)
);

CREATE INDEX idx_appointment_ratings_workspace ON pulpo.appointment_ratings(workspace_id);
CREATE INDEX idx_appointment_ratings_appointment ON pulpo.appointment_ratings(appointment_id);
CREATE INDEX idx_appointment_ratings_rating ON pulpo.appointment_ratings(workspace_id, rating);

COMMENT ON TABLE pulpo.appointment_ratings IS 'Calificaciones y reviews de turnos completados';

-- =====================================================
-- ROW LEVEL SECURITY
-- =====================================================

ALTER TABLE pulpo.business_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.special_dates ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.staff_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.promotions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.service_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.appointment_ratings ENABLE ROW LEVEL SECURITY;

CREATE POLICY workspace_isolation_business_hours ON pulpo.business_hours
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_special_dates ON pulpo.special_dates
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_staff_availability ON pulpo.staff_availability
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_promotions ON pulpo.promotions
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_service_packages ON pulpo.service_packages
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation_appointment_ratings ON pulpo.appointment_ratings
  USING (workspace_id::text = current_setting('app.workspace_id', true));

-- =====================================================
-- FUNCTIONS - AVAILABILITY CHECKING
-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.is_business_open(
  p_workspace_id uuid,
  p_date date,
  p_time time
)
RETURNS boolean AS $$
DECLARE
  v_day_of_week integer;
  v_is_open boolean;
  v_time_blocks jsonb;
  v_block jsonb;
  v_special_date record;
BEGIN
  -- Check special dates first
  SELECT * INTO v_special_date
  FROM pulpo.special_dates
  WHERE workspace_id = p_workspace_id AND date = p_date;

  IF FOUND THEN
    IF v_special_date.type = 'holiday' OR v_special_date.type = 'closed' THEN
      RETURN false;
    ELSIF v_special_date.type = 'special_hours' THEN
      -- Check special hours
      FOR v_block IN SELECT * FROM jsonb_array_elements(v_special_date.time_blocks)
      LOOP
        IF p_time >= (v_block->>'open')::time AND p_time < (v_block->>'close')::time THEN
          RETURN true;
        END IF;
      END LOOP;
      RETURN false;
    END IF;
  END IF;

  -- Regular business hours
  v_day_of_week := EXTRACT(DOW FROM p_date);

  SELECT is_open, time_blocks INTO v_is_open, v_time_blocks
  FROM pulpo.business_hours
  WHERE workspace_id = p_workspace_id AND day_of_week = v_day_of_week;

  IF NOT FOUND OR NOT v_is_open THEN
    RETURN false;
  END IF;

  -- Check time blocks
  FOR v_block IN SELECT * FROM jsonb_array_elements(v_time_blocks)
  LOOP
    IF p_time >= (v_block->>'open')::time AND p_time < (v_block->>'close')::time THEN
      RETURN true;
    END IF;
  END LOOP;

  RETURN false;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.is_business_open IS 'Verifica si el negocio está abierto en fecha/hora específica';

CREATE OR REPLACE FUNCTION pulpo.is_staff_available(
  p_workspace_id uuid,
  p_staff_id uuid,
  p_date date,
  p_start_time time,
  p_end_time time
)
RETURNS boolean AS $$
DECLARE
  v_unavailable_count integer;
BEGIN
  -- Check staff availability records
  SELECT COUNT(*) INTO v_unavailable_count
  FROM pulpo.staff_availability
  WHERE workspace_id = p_workspace_id
    AND staff_id = p_staff_id
    AND type IN ('vacation', 'sick_leave', 'day_off', 'blocked')
    AND start_date <= p_date
    AND end_date >= p_date
    AND (
      is_all_day = true
      OR (start_time <= p_start_time AND end_time >= p_end_time)
    );

  RETURN v_unavailable_count = 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.is_staff_available IS 'Verifica si un staff está disponible en fecha/hora específica';

CREATE OR REPLACE FUNCTION pulpo.get_available_time_slots(
  p_workspace_id uuid,
  p_date date,
  p_service_type_id uuid,
  p_staff_id uuid DEFAULT NULL
)
RETURNS TABLE (
  time_slot time,
  available boolean
) AS $$
DECLARE
  v_duration integer;
  v_slot_start time;
  v_slot_end time;
BEGIN
  -- Get service duration
  SELECT duration_minutes INTO v_duration
  FROM pulpo.service_types
  WHERE id = p_service_type_id AND workspace_id = p_workspace_id;

  IF NOT FOUND THEN
    RETURN;
  END IF;

  -- Generate time slots (cada 30 minutos de 08:00 a 20:00)
  FOR v_slot_start IN
    SELECT generate_series('08:00'::time, '20:00'::time, interval '30 minutes')
  LOOP
    v_slot_end := v_slot_start + (v_duration || ' minutes')::interval;

    -- Check if business is open
    IF NOT pulpo.is_business_open(p_workspace_id, p_date, v_slot_start) THEN
      CONTINUE;
    END IF;

    -- Check if staff is available (if specified)
    IF p_staff_id IS NOT NULL THEN
      IF NOT pulpo.is_staff_available(p_workspace_id, p_staff_id, p_date, v_slot_start, v_slot_end::time) THEN
        CONTINUE;
      END IF;

      -- Check existing appointments
      IF EXISTS (
        SELECT 1 FROM pulpo.appointments
        WHERE workspace_id = p_workspace_id
          AND staff_id = p_staff_id
          AND DATE(scheduled_at) = p_date
          AND status IN ('scheduled', 'confirmed')
          AND (
            (scheduled_at::time >= v_slot_start AND scheduled_at::time < v_slot_end)
            OR (scheduled_at::time < v_slot_start AND (scheduled_at::time + (duration_minutes || ' minutes')::interval) > v_slot_start::time)
          )
      ) THEN
        time_slot := v_slot_start;
        available := false;
        RETURN NEXT;
        CONTINUE;
      END IF;
    END IF;

    time_slot := v_slot_start;
    available := true;
    RETURN NEXT;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.get_available_time_slots IS 'Obtiene slots de tiempo disponibles para un servicio en una fecha';

-- =====================================================
-- TRIGGERS
-- =====================================================

CREATE TRIGGER update_business_hours_updated_at
  BEFORE UPDATE ON pulpo.business_hours
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_special_dates_updated_at
  BEFORE UPDATE ON pulpo.special_dates
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_staff_availability_updated_at
  BEFORE UPDATE ON pulpo.staff_availability
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_promotions_updated_at
  BEFORE UPDATE ON pulpo.promotions
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_service_packages_updated_at
  BEFORE UPDATE ON pulpo.service_packages
  FOR EACH ROW
  EXECUTE FUNCTION update_updated_at_column();
