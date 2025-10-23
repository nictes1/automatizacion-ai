-- =====================================================
-- PULPOAI FUNCTIONS & RLS - NORMALIZED SCHEMA
-- =====================================================
-- Funciones y Row Level Security para el schema normalizado
-- =====================================================

SET search_path = public, pulpo;

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

-- =====================================================

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
  v_existing_reservas_count integer;
BEGIN
  -- Check staff availability records (vacaciones, días libres)
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

  IF v_unavailable_count > 0 THEN
    RETURN false;
  END IF;

  -- Check existing reservations
  SELECT COUNT(*) INTO v_existing_reservas_count
  FROM pulpo.reservas
  WHERE workspace_id = p_workspace_id
    AND staff_id = p_staff_id
    AND DATE(scheduled_at) = p_date
    AND status IN ('pending', 'confirmed')
    AND (
      -- Overlap check
      (scheduled_at::time >= p_start_time AND scheduled_at::time < p_end_time)
      OR (scheduled_at::time < p_start_time AND (scheduled_at::time + (duration_minutes || ' minutes')::interval) > p_start_time::time)
    );

  RETURN v_existing_reservas_count = 0;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.is_staff_available IS 'Verifica si un staff está disponible en fecha/hora específica';

-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.get_available_time_slots(
  p_workspace_id uuid,
  p_date date,
  p_service_type_id uuid,
  p_staff_id uuid DEFAULT NULL
)
RETURNS TABLE (
  time_slot time,
  available boolean,
  staff_id uuid,
  staff_name text
) AS $$
DECLARE
  v_duration integer;
  v_slot_start time;
  v_slot_end time;
  v_staff record;
BEGIN
  -- Get service duration from staff_services or service_types
  IF p_staff_id IS NOT NULL THEN
    SELECT duration_minutes INTO v_duration
    FROM pulpo.staff_services
    WHERE workspace_id = p_workspace_id
      AND staff_id = p_staff_id
      AND service_type_id = p_service_type_id
      AND is_active = true;
  END IF;

  -- Fallback to service_types duration
  IF v_duration IS NULL THEN
    SELECT duration_minutes INTO v_duration
    FROM pulpo.service_types
    WHERE id = p_service_type_id AND workspace_id = p_workspace_id;
  END IF;

  IF NOT FOUND OR v_duration IS NULL THEN
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

    -- If specific staff requested
    IF p_staff_id IS NOT NULL THEN
      SELECT s.id, s.name INTO v_staff
      FROM pulpo.staff s
      WHERE s.id = p_staff_id AND s.workspace_id = p_workspace_id;

      IF pulpo.is_staff_available(p_workspace_id, p_staff_id, p_date, v_slot_start, v_slot_end::time) THEN
        time_slot := v_slot_start;
        available := true;
        staff_id := v_staff.id;
        staff_name := v_staff.name;
        RETURN NEXT;
      ELSE
        time_slot := v_slot_start;
        available := false;
        staff_id := v_staff.id;
        staff_name := v_staff.name;
        RETURN NEXT;
      END IF;
    ELSE
      -- Find any available staff for this service
      FOR v_staff IN
        SELECT s.id, s.name
        FROM pulpo.staff s
        JOIN pulpo.staff_services ss ON ss.staff_id = s.id
        WHERE s.workspace_id = p_workspace_id
          AND ss.service_type_id = p_service_type_id
          AND s.is_active = true
          AND ss.is_active = true
        LIMIT 1
      LOOP
        IF pulpo.is_staff_available(p_workspace_id, v_staff.id, p_date, v_slot_start, v_slot_end::time) THEN
          time_slot := v_slot_start;
          available := true;
          staff_id := v_staff.id;
          staff_name := v_staff.name;
          RETURN NEXT;
          EXIT; -- Found available staff, next slot
        END IF;
      END LOOP;
    END IF;
  END LOOP;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.get_available_time_slots IS 'Obtiene slots disponibles para un servicio en una fecha';

-- =====================================================

CREATE OR REPLACE FUNCTION pulpo.get_staff_for_service(
  p_workspace_id uuid,
  p_service_type_id uuid,
  p_date date DEFAULT CURRENT_DATE,
  p_time time DEFAULT NULL
)
RETURNS TABLE (
  staff_id uuid,
  staff_name text,
  price numeric,
  currency text,
  duration_minutes integer,
  is_available boolean
) AS $$
BEGIN
  RETURN QUERY
  SELECT
    s.id AS staff_id,
    s.name AS staff_name,
    ss.price,
    ss.currency,
    ss.duration_minutes,
    CASE
      WHEN p_time IS NULL THEN TRUE
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
    AND ss.is_active = true
  ORDER BY ss.price ASC;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION pulpo.get_staff_for_service IS 'Obtiene staff que ofrece un servicio con precio y disponibilidad';

-- =====================================================
-- ROW LEVEL SECURITY (RLS)
-- =====================================================

-- Enable RLS on all workspace-scoped tables
ALTER TABLE pulpo.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.channels ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.contacts ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_state_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.document_chunks ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.staff ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.service_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.staff_services ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.menu_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.business_hours ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.special_dates ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.staff_availability ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.promotions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.service_packages ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.action_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.pedidos ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.reservas ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.visitas ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.appointment_ratings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.outbox_events ENABLE ROW LEVEL SECURITY;

-- Create RLS policies (workspace isolation)
CREATE POLICY workspace_isolation ON pulpo.workspaces
  USING (id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.workspace_members
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.channels
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.contacts
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.conversations
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.messages
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.dialogue_states
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.dialogue_state_history
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.dialogue_slots
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.documents
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.document_chunks
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.staff
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.service_types
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.staff_services
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.menu_items
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.properties
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.business_hours
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.special_dates
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.staff_availability
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.promotions
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.service_packages
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.action_executions
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.pedidos
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.reservas
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.visitas
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.appointment_ratings
  USING (workspace_id::text = current_setting('app.workspace_id', true));

CREATE POLICY workspace_isolation ON pulpo.outbox_events
  USING (workspace_id::text = current_setting('app.workspace_id', true));

-- =====================================================
-- HELPER VIEWS
-- =====================================================

-- Vista: Resumen de precios por servicio
CREATE OR REPLACE VIEW pulpo.service_pricing_summary AS
SELECT
  st.id AS service_type_id,
  st.workspace_id,
  st.name AS service_name,
  st.description,
  st.category,
  MIN(ss.price) AS min_price,
  MAX(ss.price) AS max_price,
  AVG(ss.price) AS avg_price,
  MIN(ss.duration_minutes) AS min_duration,
  MAX(ss.duration_minutes) AS max_duration,
  COUNT(DISTINCT ss.staff_id) AS staff_count,
  st.currency,
  st.is_active
FROM pulpo.service_types st
LEFT JOIN pulpo.staff_services ss ON ss.service_type_id = st.id AND ss.is_active = true
WHERE st.is_active = true
GROUP BY st.id, st.workspace_id, st.name, st.description, st.category, st.currency, st.is_active;

COMMENT ON VIEW pulpo.service_pricing_summary IS 'Resumen de precios por servicio con rangos y cantidad de staff';

-- =====================================================
-- GRANT PERMISSIONS (for application user)
-- =====================================================

-- Si tienes un usuario específico para la aplicación, puedes agregar GRANTs aquí
-- GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA pulpo TO pulpo_app;
-- GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA pulpo TO pulpo_app;
-- =====================================================
-- Funciones SQL para n8n Workflow
-- =====================================================
-- Estas funciones son llamadas por el workflow de n8n
-- para persistir mensajes y cargar/guardar estado conversacional.
-- =====================================================

-- 1. persist_inbound: Guarda mensaje entrante de Twilio
-- Parámetros: workspace_id, channel_id, user_phone, wamid (message ID), text
-- Retorna: JSON con {conversation_id, message_id}
CREATE OR REPLACE FUNCTION pulpo.persist_inbound(
  p_workspace_id uuid,
  p_channel_id uuid,
  p_user_phone text,
  p_wamid text,
  p_text text
) RETURNS jsonb AS $$
DECLARE
  v_contact_id uuid;
  v_conversation_id uuid;
  v_message_id uuid;
BEGIN
  -- 1. Encontrar o crear contacto por teléfono
  SELECT id INTO v_contact_id
  FROM pulpo.contacts
  WHERE workspace_id = p_workspace_id
    AND channel_id = p_channel_id
    AND phone = p_user_phone
  LIMIT 1;

  IF v_contact_id IS NULL THEN
    -- Crear nuevo contacto
    INSERT INTO pulpo.contacts (workspace_id, channel_id, external_id, phone, name)
    VALUES (p_workspace_id, p_channel_id, p_user_phone, p_user_phone, 'Cliente')
    RETURNING id INTO v_contact_id;
  END IF;

  -- 2. Encontrar o crear conversación activa
  SELECT id INTO v_conversation_id
  FROM pulpo.conversations
  WHERE workspace_id = p_workspace_id
    AND contact_id = v_contact_id
    AND status = 'active'
  ORDER BY updated_at DESC
  LIMIT 1;

  IF v_conversation_id IS NULL THEN
    -- Crear nueva conversación
    INSERT INTO pulpo.conversations (workspace_id, channel_id, contact_id, status)
    VALUES (p_workspace_id, p_channel_id, v_contact_id, 'active')
    RETURNING id INTO v_conversation_id;
  END IF;

  -- 3. Insertar mensaje entrante
  INSERT INTO pulpo.messages (
    workspace_id,
    conversation_id,
    sender,
    content,
    message_type,
    metadata
  ) VALUES (
    p_workspace_id,
    v_conversation_id,
    'user',
    p_text,
    'text',
    jsonb_build_object('wamid', p_wamid, 'phone', p_user_phone)
  ) RETURNING id INTO v_message_id;

  -- 4. Retornar IDs como JSON
  RETURN jsonb_build_object(
    'conversation_id', v_conversation_id,
    'message_id', v_message_id,
    'contact_id', v_contact_id
  );
END;
$$ LANGUAGE plpgsql;


-- 2. load_state: Carga el estado conversacional de una conversación
-- Parámetros: workspace_id, conversation_id
-- Retorna: JSON con {greeted, slots, objective, last_action, attempts_count}
CREATE OR REPLACE FUNCTION pulpo.load_state(
  p_workspace_id uuid,
  p_conversation_id uuid
) RETURNS jsonb AS $$
DECLARE
  v_state jsonb;
BEGIN
  -- Cargar estado desde dialogue_states
  SELECT jsonb_build_object(
    'greeted', COALESCE((slots->>'greeted')::boolean, false),
    'slots', COALESCE(slots, '{}'::jsonb),
    'objective', COALESCE(meta->>'objective', ''),
    'last_action', next_action,
    'attempts_count', COALESCE((meta->>'attempts_count')::int, 0)
  )
  INTO v_state
  FROM pulpo.dialogue_states
  WHERE workspace_id = p_workspace_id
    AND conversation_id = p_conversation_id;

  -- Si no hay estado, retornar estado inicial
  IF v_state IS NULL THEN
    v_state := jsonb_build_object(
      'greeted', false,
      'slots', '{}'::jsonb,
      'objective', '',
      'last_action', null,
      'attempts_count', 0
    );
  END IF;

  RETURN v_state;
END;
$$ LANGUAGE plpgsql;


-- 3. persist_outbound: Guarda mensaje saliente (respuesta del bot)
-- Parámetros: workspace_id, conversation_id, message_text, message_type, message_source, metadata
-- Retorna: message_id (uuid)
CREATE OR REPLACE FUNCTION pulpo.persist_outbound(
  p_workspace_id uuid,
  p_conversation_id uuid,
  p_message_text text,
  p_message_type text DEFAULT 'text',
  p_message_source text DEFAULT 'assistant',
  p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS uuid AS $$
DECLARE
  v_message_id uuid;
  v_slots jsonb;
  v_objective text;
  v_last_action text;
BEGIN
  -- 1. Insertar mensaje saliente
  INSERT INTO pulpo.messages (
    workspace_id,
    conversation_id,
    sender,
    content,
    message_type,
    metadata
  ) VALUES (
    p_workspace_id,
    p_conversation_id,
    'assistant',
    p_message_text,
    p_message_type,
    p_metadata
  ) RETURNING id INTO v_message_id;

  -- 2. Actualizar dialogue_states si hay metadata de estado
  IF p_metadata ? 'slots' OR p_metadata ? 'objective' OR p_metadata ? 'last_action' THEN
    v_slots := COALESCE(p_metadata->'slots', '{}'::jsonb);
    v_objective := COALESCE(p_metadata->>'objective', '');
    v_last_action := COALESCE(p_metadata->>'last_action', 'answer');

    INSERT INTO pulpo.dialogue_states (
      workspace_id,
      conversation_id,
      fsm_state,
      intent,
      slots,
      next_action,
      meta
    ) VALUES (
      p_workspace_id,
      p_conversation_id,
      'active',
      COALESCE(p_metadata->>'intent', 'chat'),
      v_slots,
      v_last_action,
      jsonb_build_object(
        'objective', v_objective,
        'attempts_count', COALESCE((p_metadata->>'attempts_count')::int, 0)
      )
    )
    ON CONFLICT (workspace_id, conversation_id)
    DO UPDATE SET
      slots = v_slots,
      next_action = v_last_action,
      meta = jsonb_build_object(
        'objective', v_objective,
        'attempts_count', COALESCE((p_metadata->>'attempts_count')::int, 0)
      ),
      updated_at = now();
  END IF;

  -- 3. Retornar message_id
  RETURN v_message_id;
END;
$$ LANGUAGE plpgsql;


-- Comentarios de documentación
COMMENT ON FUNCTION pulpo.persist_inbound IS
  'Guarda mensaje entrante de Twilio WhatsApp. Crea contacto y conversación si no existen.';

COMMENT ON FUNCTION pulpo.load_state IS
  'Carga el estado conversacional completo (greeted, slots, objetivo, etc.) para una conversación.';

COMMENT ON FUNCTION pulpo.persist_outbound IS
  'Guarda mensaje saliente del bot y actualiza dialogue_states con metadata de estado.';
