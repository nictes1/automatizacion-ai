-- =====================================================
-- SEED DATA - INITIAL DATA FOR DEVELOPMENT
-- =====================================================
-- Datos iniciales para desarrollo y testing
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- SAMPLE WORKSPACES
-- =====================================================

-- Sample workspace for gastronomy
INSERT INTO pulpo.workspaces (id, name, plan, vertical, business_name, business_calendar_email, settings) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'Restaurante El Buen Sabor', 'premium', 'gastronomia', 'Restaurante El Buen Sabor', NULL,
   '{"twilio_from": "+14155238886", "ollama_model": "llama3.1:8b", "business_hours": "09:00-23:00"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440002', 'Inmobiliaria San Martín', 'premium', 'inmobiliaria', 'Inmobiliaria San Martín', NULL,
   '{"twilio_from": "+14155238887", "ollama_model": "llama3.1:8b", "business_hours": "08:00-18:00"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 'Peluquería Estilo', 'basic', 'servicios', 'Peluquería Estilo', 'nikolastesone@gmail.com',
   '{"twilio_from": "+14155238888", "ollama_model": "llama3.1:8b", "business_hours": "10:00-20:00"}'::jsonb);

-- =====================================================
-- SAMPLE USERS
-- =====================================================

INSERT INTO pulpo.users (id, email, name) VALUES
  ('660e8400-e29b-41d4-a716-446655440001', 'admin@elbuensabor.com', 'Admin El Buen Sabor'),
  ('660e8400-e29b-41d4-a716-446655440002', 'admin@sanmartin.com', 'Admin San Martín'),
  ('660e8400-e29b-41d4-a716-446655440003', 'admin@estilo.com', 'Admin Estilo');

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

INSERT INTO pulpo.channels (workspace_id, type, provider, business_phone_id, display_phone, settings_json) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'whatsapp', 'meta_whatsapp', '123456789', '+5491111111111',
   '{"webhook_url": "https://api.elbuensabor.com/webhook", "verify_token": "elbuensabor123"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440002', 'whatsapp', 'meta_whatsapp', '123456790', '+5492222222222',
   '{"webhook_url": "https://api.sanmartin.com/webhook", "verify_token": "sanmartin123"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 'whatsapp', 'meta_whatsapp', '123456791', '+5493333333333',
   '{"webhook_url": "https://api.estilo.com/webhook", "verify_token": "estilo123"}'::jsonb);

-- =====================================================
-- SAMPLE CONTACTS
-- =====================================================

INSERT INTO pulpo.contacts (workspace_id, user_phone, attributes_json) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', '+5491111111111', '{"name": "Juan Pérez", "preferences": {"vegetarian": false}}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440001', '+5491111111112', '{"name": "María García", "preferences": {"vegetarian": true}}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440002', '+5492222222222', '{"name": "Carlos López", "budget": 50000}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', '+5493333333333', '{"name": "Ana Rodríguez", "preferences": {"hair_type": "curly"}}'::jsonb);

-- =====================================================
-- SAMPLE CONVERSATIONS
-- =====================================================

INSERT INTO pulpo.conversations (workspace_id, channel_id, contact_id, status, total_messages) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 
   (SELECT id FROM pulpo.channels WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   (SELECT id FROM pulpo.contacts WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   'active', 5),
  ('550e8400-e29b-41d4-a716-446655440002',
   (SELECT id FROM pulpo.channels WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440002' LIMIT 1),
   (SELECT id FROM pulpo.contacts WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440002' LIMIT 1),
   'active', 3),
  ('550e8400-e29b-41d4-a716-446655440003',
   (SELECT id FROM pulpo.channels WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003' LIMIT 1),
   (SELECT id FROM pulpo.contacts WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003' LIMIT 1),
   'active', 2);

-- =====================================================
-- SAMPLE MESSAGES
-- =====================================================

INSERT INTO pulpo.messages (conversation_id, workspace_id, direction, text, intent) VALUES
  ((SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   '550e8400-e29b-41d4-a716-446655440001', 'inbound', 'Hola, quiero hacer un pedido', 'order_intent'),
  ((SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   '550e8400-e29b-41d4-a716-446655440001', 'outbound', '¡Hola! Te ayudo con tu pedido. ¿Qué te gustaría ordenar?', 'greeting'),
  ((SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440002' LIMIT 1),
   '550e8400-e29b-41d4-a716-446655440002', 'inbound', 'Busco un departamento de 2 ambientes', 'property_search'),
  ((SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003' LIMIT 1),
   '550e8400-e29b-41d4-a716-446655440003', 'inbound', 'Quiero agendar un turno para el viernes', 'appointment_request');

-- =====================================================
-- SAMPLE DIALOGUE STATES
-- =====================================================

INSERT INTO pulpo.dialogue_states (workspace_id, conversation_id, fsm_state, intent, slots, next_action) VALUES
  ('550e8400-e29b-41d4-a716-446655440001',
   (SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   'COLLECTING', 'order_intent', '{"items": [], "delivery_method": null}'::jsonb, 'tool_call'),
  ('550e8400-e29b-41d4-a716-446655440002',
   (SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440002' LIMIT 1),
   'START', 'property_search', '{"property_type": "departamento", "rooms": 2}'::jsonb, 'answer'),
  ('550e8400-e29b-41d4-a716-446655440003',
   (SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003' LIMIT 1),
   'COLLECTING', 'appointment_request', '{"date": "viernes", "time": null}'::jsonb, 'tool_call');

-- =====================================================
-- SAMPLE DOCUMENTS (RAG)
-- =====================================================

INSERT INTO pulpo.documents (workspace_id, title, content, file_type, metadata) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'Menú Principal', 
   'Pizza Margherita - $15.99\nHamburguesa Clásica - $12.50\nEnsalada César - $8.99\nPasta Carbonara - $14.99',
   'menu', '{"category": "food", "language": "es"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440002', 'Propiedades Disponibles',
   'Departamento 2 ambientes en Palermo - $45,000\nCasa 3 dormitorios en Belgrano - $65,000\nOficina en Microcentro - $35,000',
   'catalog', '{"category": "real_estate", "language": "es"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 'Servicios de Peluquería',
   'Corte de cabello - $25\nPeinado - $30\nTintura - $45\nManicura - $20',
   'services', '{"category": "beauty", "language": "es"}'::jsonb);

-- =====================================================
-- SAMPLE ORDERS
-- =====================================================

INSERT INTO pulpo.orders (workspace_id, conversation_id, items, total, status) VALUES
  ('550e8400-e29b-41d4-a716-446655440001',
   (SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001' LIMIT 1),
   '[{"name": "Pizza Margherita", "quantity": 1, "price": 15.99}]'::jsonb,
   15.99, 'draft');

-- =====================================================
-- SAMPLE PROPERTIES
-- =====================================================

INSERT INTO pulpo.properties (workspace_id, operation, type, zone, address, price, bedrooms, bathrooms, surface_m2, description) VALUES
  ('550e8400-e29b-41d4-a716-446655440002', 'venta', 'departamento', 'Palermo', 'Av. Santa Fe 1234', 45000, 2, 1, 65.5, 'Departamento luminoso en Palermo'),
  ('550e8400-e29b-41d4-a716-446655440002', 'alquiler', 'casa', 'Belgrano', 'Av. Cabildo 5678', 65000, 3, 2, 120.0, 'Casa con jardín en Belgrano');

-- =====================================================
-- SAMPLE APPOINTMENTS
-- =====================================================

INSERT INTO pulpo.appointments (workspace_id, conversation_id, appointment_type, scheduled_at, status) VALUES
  ('550e8400-e29b-41d4-a716-446655440003',
   (SELECT id FROM pulpo.conversations WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003' LIMIT 1),
   'corte_cabello', '2024-01-26 14:00:00', 'scheduled');

-- =====================================================
-- SAMPLE SYSTEM METRICS
-- =====================================================

INSERT INTO pulpo.system_metrics (workspace_id, metric_name, metric_value, metric_unit, tags) VALUES
  ('550e8400-e29b-41d4-a716-446655440001', 'messages_processed', 150, 'count', '{"service": "orchestrator"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440001', 'response_time', 1.2, 'seconds', '{"service": "orchestrator"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440002', 'properties_searched', 25, 'count', '{"service": "rag"}'::jsonb),
  ('550e8400-e29b-41d4-a716-446655440003', 'appointments_created', 8, 'count', '{"service": "actions"}'::jsonb);
