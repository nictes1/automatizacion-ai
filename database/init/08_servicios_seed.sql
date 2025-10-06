-- =====================================================
-- SERVICIOS SEED DATA
-- =====================================================
-- Datos de ejemplo para tablas de servicios
-- =====================================================

SET search_path = public, pulpo;

DO $$
DECLARE
  v_workspace_id uuid := '550e8400-e29b-41d4-a716-446655440000';
  v_staff_maria uuid;
  v_staff_juan uuid;
  v_service_corte uuid;
  v_service_coloracion uuid;
  v_service_barba uuid;
BEGIN

  -- =====================================================
  -- BUSINESS HOURS - Horarios del negocio
  -- =====================================================

  -- Lunes a Viernes: 9:00-13:00 y 14:00-19:00
  INSERT INTO pulpo.business_hours (workspace_id, day_of_week, is_open, time_blocks)
  VALUES
    (v_workspace_id, 1, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb), -- Lunes
    (v_workspace_id, 2, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb), -- Martes
    (v_workspace_id, 3, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb), -- Miércoles
    (v_workspace_id, 4, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb), -- Jueves
    (v_workspace_id, 5, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb), -- Viernes

    -- Sábado: 9:00-15:00 (corrido)
    (v_workspace_id, 6, true, '[{"open": "09:00", "close": "15:00"}]'::jsonb), -- Sábado

    -- Domingo: cerrado
    (v_workspace_id, 0, false, '[]'::jsonb) -- Domingo
  ON CONFLICT (workspace_id, day_of_week) DO UPDATE
  SET time_blocks = EXCLUDED.time_blocks,
      is_open = EXCLUDED.is_open;

  -- =====================================================
  -- SPECIAL DATES - Feriados
  -- =====================================================

  INSERT INTO pulpo.special_dates (workspace_id, date, type, name, is_recurring)
  VALUES
    (v_workspace_id, '2025-12-25', 'holiday', 'Navidad', true),
    (v_workspace_id, '2025-01-01', 'holiday', 'Año Nuevo', true),
    (v_workspace_id, '2025-05-01', 'holiday', 'Día del Trabajador', true),
    (v_workspace_id, '2025-05-25', 'holiday', 'Revolución de Mayo', true),
    (v_workspace_id, '2025-07-09', 'holiday', 'Día de la Independencia', true)
  ON CONFLICT (workspace_id, date) DO NOTHING;

  -- =====================================================
  -- STAFF AVAILABILITY - Ausencias/Disponibilidad
  -- =====================================================

  -- Get staff IDs
  SELECT id INTO v_staff_maria FROM pulpo.staff
  WHERE workspace_id = v_workspace_id AND name = 'María García' LIMIT 1;

  SELECT id INTO v_staff_juan FROM pulpo.staff
  WHERE workspace_id = v_workspace_id AND name = 'Juan Pérez' LIMIT 1;

  -- Ejemplos de ausencias
  IF v_staff_maria IS NOT NULL THEN
    INSERT INTO pulpo.staff_availability (workspace_id, staff_id, type, start_date, end_date, is_all_day, reason)
    VALUES
      -- María tiene vacaciones en diciembre
      (v_workspace_id, v_staff_maria, 'vacation', '2025-12-20', '2025-12-31', true, 'Vacaciones de fin de año')
    ON CONFLICT DO NOTHING;
  END IF;

  IF v_staff_juan IS NOT NULL THEN
    INSERT INTO pulpo.staff_availability (workspace_id, staff_id, type, start_date, end_date, is_all_day, reason)
    VALUES
      -- Juan no trabaja los miércoles por tarde
      (v_workspace_id, v_staff_juan, 'day_off', '2025-10-08', '2025-10-08', false, 'No disponible miércoles tarde'),
      (v_workspace_id, v_staff_juan, 'day_off', '2025-10-15', '2025-10-15', false, 'No disponible miércoles tarde'),
      (v_workspace_id, v_staff_juan, 'day_off', '2025-10-22', '2025-10-22', false, 'No disponible miércoles tarde')
    ON CONFLICT DO NOTHING;
  END IF;

  -- =====================================================
  -- PROMOTIONS - Promociones
  -- =====================================================

  INSERT INTO pulpo.promotions (
    workspace_id, name, description, discount_type, discount_value,
    applies_to, valid_from, valid_until, is_active,
    valid_days_of_week, valid_hours
  )
  VALUES
    -- 20% descuento martes y miércoles
    (v_workspace_id,
     '20% OFF Martes y Miércoles',
     'Descuento del 20% en todos los servicios los martes y miércoles',
     'percentage', 20,
     'all',
     '2025-10-01', '2025-12-31',
     true,
     '[2,3]'::jsonb, -- Solo martes y miércoles
     '{"start": "00:00", "end": "23:59"}'::jsonb),

    -- Promo mañanas: $500 off
    (v_workspace_id,
     'Promo Mañanas',
     '$500 de descuento en servicios antes de las 12pm',
     'fixed_amount', 500,
     'all',
     '2025-10-01', '2025-12-31',
     true,
     '[1,2,3,4,5]'::jsonb, -- Lunes a viernes
     '{"start": "09:00", "end": "12:00"}'::jsonb),

    -- Primera vez: 30% off
    (v_workspace_id,
     'Primera Visita 30% OFF',
     'Descuento del 30% para clientes nuevos',
     'percentage', 30,
     'all',
     '2025-10-01', '2025-12-31',
     true,
     '[0,1,2,3,4,5,6]'::jsonb,
     '{"start": "00:00", "end": "23:59"}'::jsonb)
  ON CONFLICT DO NOTHING;

  -- =====================================================
  -- SERVICE PACKAGES - Paquetes
  -- =====================================================

  -- Get service IDs
  SELECT id INTO v_service_corte FROM pulpo.service_types
  WHERE workspace_id = v_workspace_id AND name = 'Corte de Cabello' LIMIT 1;

  SELECT id INTO v_service_coloracion FROM pulpo.service_types
  WHERE workspace_id = v_workspace_id AND name = 'Coloración Completa' LIMIT 1;

  SELECT id INTO v_service_barba FROM pulpo.service_types
  WHERE workspace_id = v_workspace_id AND name = 'Corte y Barba' LIMIT 1;

  IF v_service_corte IS NOT NULL AND v_service_coloracion IS NOT NULL THEN
    INSERT INTO pulpo.service_packages (
      workspace_id, name, description, service_type_ids,
      package_price, regular_price, total_duration_minutes, is_active
    )
    VALUES
      -- Paquete corte + coloración
      (v_workspace_id,
       'Paquete Look Completo',
       'Corte de cabello + Coloración completa con 15% de descuento',
       jsonb_build_array(v_service_corte::text, v_service_coloracion::text),
       7650, -- $9000 - 15%
       9000, -- $2500 + $6500
       165, -- 45min + 120min
       true)
    ON CONFLICT DO NOTHING;
  END IF;

  IF v_service_corte IS NOT NULL AND v_service_barba IS NOT NULL THEN
    INSERT INTO pulpo.service_packages (
      workspace_id, name, description, service_type_ids,
      package_price, regular_price, total_duration_minutes, is_active
    )
    VALUES
      -- Paquete masculino
      (v_workspace_id,
       'Paquete Caballero',
       'Corte + Barba completa con precio especial',
       jsonb_build_array(v_service_corte::text, v_service_barba::text),
       4000, -- Normalmente $5500
       5500, -- $2500 + $3000
       105, -- 45min + 60min
       true)
    ON CONFLICT DO NOTHING;
  END IF;

  RAISE NOTICE 'Servicios seed data loaded successfully';

END $$;
