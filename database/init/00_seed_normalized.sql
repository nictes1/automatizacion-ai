-- =====================================================
-- SEED DATA - NORMALIZED SCHEMA
-- =====================================================
-- Datos de ejemplo para desarrollo y testing
-- Compatible con schema normalizado v2.0
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- SAMPLE WORKSPACES (con metadata del negocio)
-- =====================================================

INSERT INTO pulpo.workspaces (
  id, name, vertical, plan,
  business_name, address, phone, email,
  settings
) VALUES
(
  '550e8400-e29b-41d4-a716-446655440001',
  'Restaurante El Buen Sabor',
  'gastronomia',
  'premium',
  'El Buen Sabor - Cocina Casera',
  'Av. Rivadavia 1234, CABA',
  '+5491112345678',
  'contacto@elbuensabor.com.ar',
  '{"twilio_from": "+14155238886", "ollama_model": "qwen2.5:14b"}'::jsonb
),
(
  '550e8400-e29b-41d4-a716-446655440002',
  'Inmobiliaria San Martín',
  'inmobiliaria',
  'enterprise',
  'San Martín Propiedades',
  'Av. Santa Fe 5678, CABA',
  '+5491187654321',
  'info@sanmartin.com.ar',
  '{"twilio_from": "+14155238887", "ollama_model": "qwen2.5:14b"}'::jsonb
),
(
  '550e8400-e29b-41d4-a716-446655440003',
  'Peluquería Estilo',
  'servicios',
  'basic',
  'Estilo Peluquería & Spa',
  'Av. Cabildo 9012, CABA',
  '+5491198765432',
  'turnos@estilo.com.ar',
  '{"twilio_from": "+14155238888", "ollama_model": "qwen2.5:14b"}'::jsonb
);

-- =====================================================
-- SAMPLE USERS
-- =====================================================

INSERT INTO pulpo.users (id, email, name, role) VALUES
  ('660e8400-e29b-41d4-a716-446655440001', 'admin@elbuensabor.com', 'Admin El Buen Sabor', 'admin'),
  ('660e8400-e29b-41d4-a716-446655440002', 'admin@sanmartin.com', 'Admin San Martín', 'admin'),
  ('660e8400-e29b-41d4-a716-446655440003', 'admin@estilo.com', 'Admin Estilo', 'admin');

-- =====================================================
-- SAMPLE WORKSPACE MEMBERS
-- =====================================================

INSERT INTO pulpo.workspace_members (workspace_id, user_id, role) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', '660e8400-e29b-41d4-a716-446655440001', 'owner'),
  ('550e8400-e29b-41d4-a716-446655440002', '660e8400-e29b-41d4-a716-446655440002', 'owner'),
  ('550e8400-e29b-41d4-a716-446655440003', '660e8400-e29b-41d4-a716-446655440003', 'owner');

-- =====================================================
-- SAMPLE CHANNELS
-- =====================================================

INSERT INTO pulpo.channels (workspace_id, type, name, config, is_active) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'whatsapp', 'WhatsApp Principal',
   '{"business_phone_id": "123456789", "display_phone": "+5491111111111"}'::jsonb, true),
  ('550e8400-e29b-41d4-a716-446655440002', 'whatsapp', 'WhatsApp Consultas',
   '{"business_phone_id": "123456790", "display_phone": "+5492222222222"}'::jsonb, true),
  ('550e8400-e29b-41d4-a716-446655440003', 'whatsapp', 'WhatsApp Turnos',
   '{"business_phone_id": "123456791", "display_phone": "+5493333333333"}'::jsonb, true);

-- =====================================================
-- SAMPLE CONTACTS
-- =====================================================

INSERT INTO pulpo.contacts (workspace_id, channel_id, external_id, name, phone) VALUES
  ('550e8400-e29b-41d4-a716-446655440001',
   (SELECT id FROM pulpo.channels WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   '+5491111111111', 'Juan Pérez', '+5491111111111'),
  ('550e8400-e29b-41d4-a716-446655440002',
   (SELECT id FROM pulpo.channels WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440002' LIMIT 1),
   '+5492222222222', 'María García', '+5492222222222'),
  ('550e8400-e29b-41d4-a716-446655440003',
   (SELECT id FROM pulpo.channels WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003' LIMIT 1),
   '+5493333333333', 'Carlos López', '+5493333333333');

-- =====================================================
-- SAMPLE MENU ITEMS (Gastronomía) - is_active normalizado
-- =====================================================

INSERT INTO pulpo.menu_items (workspace_id, sku, name, description, price, category, is_active) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'EMP-001', 'Empanada de Carne', 'Empanada criolla de carne cortada a cuchillo', 350, 'empanadas', true),
  ('550e8400-e29b-41d4-a716-446655440001', 'EMP-002', 'Empanada de Pollo', 'Empanada de pollo con cebolla y huevo', 300, 'empanadas', true),
  ('550e8400-e29b-41d4-a716-446655440001', 'PIZZA-001', 'Pizza Napolitana', 'Pizza con tomate, mozzarella y albahaca', 2500, 'pizzas', true),
  ('550e8400-e29b-41d4-a716-446655440001', 'MILANESA-001', 'Milanesa Napolitana', 'Milanesa de ternera con jamón y queso', 4500, 'principales', true);

-- =====================================================
-- SAMPLE PROPERTIES (Inmobiliaria)
-- =====================================================

INSERT INTO pulpo.properties (workspace_id, property_id, operation, type, zone, address, price, bedrooms, bathrooms, surface_m2, description, is_available) VALUES
  ('550e8400-e29b-41d4-a716-446655440002', 'PROP-001', 'venta', 'departamento', 'Palermo', 'Av. Santa Fe 1234', 180000, 2, 1, 55.0, 'Depto 2 ambientes luminoso en Palermo', true),
  ('550e8400-e29b-41d4-a716-446655440002', 'PROP-002', 'alquiler', 'casa', 'Belgrano', 'Av. Cabildo 5678', 85000, 3, 2, 120.0, 'Casa con jardín en Belgrano', true);

-- =====================================================
-- SAMPLE STAFF (Peluquería)
-- =====================================================

INSERT INTO pulpo.staff (id, workspace_id, name, email, phone, role, is_active, skills) VALUES
  ('770e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440003', 'Carlos Rodríguez', 'carlos@estilo.com', '+5491111111111', 'Peluquero Senior', true, '["corte", "barba", "peinado"]'::jsonb),
  ('770e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440003', 'Juan Martínez', 'juan@estilo.com', '+5491122222222', 'Peluquero', true, '["corte", "peinado"]'::jsonb),
  ('770e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440003', 'María Fernández', 'maria@estilo.com', '+5491133333333', 'Estilista', true, '["corte", "coloración", "tratamientos"]'::jsonb);

-- =====================================================
-- SAMPLE SERVICE TYPES (Peluquería)
-- =====================================================

INSERT INTO pulpo.service_types (id, workspace_id, name, description, category, price_reference, duration_minutes, is_active) VALUES
  ('880e8400-e29b-41d4-a716-446655440001', '550e8400-e29b-41d4-a716-446655440003', 'Corte de Cabello', 'Corte de cabello para hombre o mujer', 'hair', 4500, 35, true),
  ('880e8400-e29b-41d4-a716-446655440002', '550e8400-e29b-41d4-a716-446655440003', 'Coloración', 'Tintura completa', 'hair', 8000, 90, true),
  ('880e8400-e29b-41d4-a716-446655440003', '550e8400-e29b-41d4-a716-446655440003', 'Barba', 'Corte y arreglo de barba', 'grooming', 2500, 20, true);

-- =====================================================
-- SAMPLE STAFF SERVICES (Precios por staff)
-- =====================================================

INSERT INTO pulpo.staff_services (workspace_id, staff_id, service_type_id, price, currency, duration_minutes, is_active) VALUES
  -- Carlos (senior): precios más altos
  ('550e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440001', '880e8400-e29b-41d4-a716-446655440001', 6000, 'ARS', 45, true),  -- Corte
  ('550e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440001', '880e8400-e29b-41d4-a716-446655440003', 3000, 'ARS', 25, true),  -- Barba

  -- Juan (mid): precios medios
  ('550e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440002', '880e8400-e29b-41d4-a716-446655440001', 4500, 'ARS', 30, true),  -- Corte

  -- María (especialista): servicios específicos
  ('550e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440003', '880e8400-e29b-41d4-a716-446655440001', 3500, 'ARS', 35, true),  -- Corte
  ('550e8400-e29b-41d4-a716-446655440003', '770e8400-e29b-41d4-a716-446655440003', '880e8400-e29b-41d4-a716-446655440002', 9500, 'ARS', 120, true); -- Coloración

-- =====================================================
-- SAMPLE BUSINESS HOURS (Peluquería)
-- =====================================================

INSERT INTO pulpo.business_hours (workspace_id, day_of_week, is_open, time_blocks) VALUES
  -- Lunes a Viernes (1-5)
  ('550e8400-e29b-41d4-a716-446655440003', 1, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 2, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 3, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 4, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 5, true, '[{"open": "09:00", "close": "13:00"}, {"open": "14:00", "close": "19:00"}]'::jsonb),
  -- Sábado (6): horario reducido
  ('550e8400-e29b-41d4-a716-446655440003', 6, true, '[{"open": "09:00", "close": "14:00"}]'::jsonb),
  -- Domingo (0): cerrado
  ('550e8400-e29b-41d4-a716-446655440003', 0, false, '[]'::jsonb);

-- =====================================================
-- SAMPLE DOCUMENTS (RAG)
-- =====================================================

INSERT INTO pulpo.documents (workspace_id, title, content, document_type) VALUES
  ('550e8400-e29b-41d4-a716-446655440003',
   'Políticas de Cancelación',
   'Las cancelaciones deben realizarse con al menos 24 horas de anticipación. Cancelaciones tardías pueden generar un cargo del 50% del servicio.',
   'policy'),
  ('550e8400-e29b-41d4-a716-446655440003',
   'Preguntas Frecuentes',
   '¿Aceptan tarjeta? Sí, aceptamos todas las tarjetas de débito y crédito. ¿Hacen domicilio? No, todos nuestros servicios son en el local.',
   'faq');

-- =====================================================
-- SAMPLE PROMOTIONS
-- =====================================================

INSERT INTO pulpo.promotions (workspace_id, name, description, discount_type, discount_value, applies_to, valid_from, valid_until, valid_days_of_week, is_active) VALUES
  ('550e8400-e29b-41d4-a716-446655440003',
   '20% OFF Martes',
   'Descuento del 20% en todos los servicios los martes',
   'percentage',
   20,
   'all',
   '2025-01-01',
   '2025-12-31',
   '[2]'::jsonb,  -- Solo martes
   true);

-- =====================================================
-- SAMPLE SERVICE PACKAGES
-- =====================================================

INSERT INTO pulpo.service_packages (workspace_id, name, description, service_type_ids, package_price, regular_price, total_duration_minutes, is_active) VALUES
  ('550e8400-e29b-41d4-a716-446655440003',
   'Look Completo',
   'Corte + Barba combo',
   '["880e8400-e29b-41d4-a716-446655440001", "880e8400-e29b-41d4-a716-446655440003"]'::jsonb,
   7500,
   9000,
   65,
   true);

-- =====================================================
-- Configurar app.workspace_id para pruebas locales
-- =====================================================

-- Para testing local, puedes setear el workspace default:
-- SELECT set_config('app.workspace_id', '550e8400-e29b-41d4-a716-446655440003', false);
