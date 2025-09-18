-- sql/02_seed_dev.sql

SET search_path = public, pulpo;

-- A) Contexto de workspace DEV (necesario por RLS)
SELECT pulpo.set_ws_context('00000000-0000-0000-0000-000000000001');

-- B) Workspace base con settings_json
INSERT INTO pulpo.workspaces (id,name,plan_tier,vertical,settings_json) VALUES
(
  '00000000-0000-0000-0000-000000000001',
  'Pulpo DEV',
  'agent_basic',
  'gastronomia',
  jsonb_build_object(
    'name',           'El Local de Prueba',
    'address',        'Av. Test 123, CABA',
    'hours',          'Lun-Dom 09:00–22:00',
    'booking_phone',  '+54 11 1234-5678',
    'menu_url',       'https://ejemplo.local/menu',
    'closed_msg',     'Estamos cerrados ahora. ¿Querés que te agendemos para mañana?',
    'lang',           'es'
  )
)
ON CONFLICT (id) DO UPDATE
SET name = EXCLUDED.name,
    plan_tier = EXCLUDED.plan_tier,
    vertical = EXCLUDED.vertical,
    settings_json = EXCLUDED.settings_json;

-- C) Policy JSON inicial
INSERT INTO pulpo.workspace_configs (workspace_id, policy_json, updated_at)
VALUES (
  '00000000-0000-0000-0000-000000000001',
  '{
    "basic": {
      "tone":"neutral",
      "locales":["es","en"],
      "fallback":"Te confirmo enseguida.",
      "max_tokens_out":300,
      "name": "El Local de Prueba",
      "vertical": "gastronomia",
      "address": "Av. Test 123, CABA",
      "alt_phone": "+54 11 1234-5678",
      "hours": "Lun-Dom 09:00–22:00",
      "payments": ["debito","credito","efectivo","qr"],
      "shipping": "CABA + GBA, 24–48 h",
      "promos": "2x1 lunes, 10% efectivo",
      "faqs": ["reservas","delivery","envios","devoluciones","menu","ubicacion"],
      "signature": "— Equipo El Local de Prueba"
    },
    "gastro": {
      "reservation_policy":"manual",
      "reservation_hours":"Lun-Dom 12:00-00:00",
      "delivery_hours":"Lun-Dom 12:00-23:00",
      "delivery_zones":"CABA+GBA",
      "pickup_address": "Av. Test 123, CABA",
      "max_party_size":12,
      "lead_time_minutes":15,
      "menu_link": "https://ejemplo.local/menu",
      "whatsapp_handoff_tag":"RESERVA|DELIVERY"
    }
  }'::jsonb,
  now()
)
ON CONFLICT (workspace_id) DO UPDATE
SET policy_json = EXCLUDED.policy_json,
    updated_at = now();

-- D) Usuario demo
INSERT INTO pulpo.users (id,email,name) VALUES
('00000000-0000-0000-0000-0000000000aa','dev@pulpo.local','Dev Pulpo')
ON CONFLICT (id) DO NOTHING;

-- E) Miembro demo
INSERT INTO pulpo.workspace_members (workspace_id,user_id,role) VALUES
('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-0000000000aa','owner')
ON CONFLICT DO NOTHING;

-- F) Canal demo
INSERT INTO pulpo.channels (id,workspace_id,type,provider,business_phone_id,display_phone,status,settings_json) VALUES
('00000000-0000-0000-0000-0000000000c1','00000000-0000-0000-0000-000000000001','whatsapp','meta_whatsapp','BSP_TEST_1','5491112345678','active','{}'::jsonb)
ON CONFLICT (id) DO UPDATE
SET display_phone = EXCLUDED.display_phone;

-- G) Contacto demo
INSERT INTO pulpo.contacts (id,workspace_id,user_phone,attributes_json) VALUES
('00000000-0000-0000-0000-0000000000cc','00000000-0000-0000-0000-000000000001','5491122223333','{"name":"Cliente Demo"}')
ON CONFLICT (id) DO NOTHING;

-- H) Conversación demo
INSERT INTO pulpo.conversations (id,workspace_id,contact_id,channel_id,status,last_message_at) VALUES
('00000000-0000-0000-0000-0000000000c0','00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-0000000000cc','00000000-0000-0000-0000-0000000000c1','open',now())
ON CONFLICT (id) DO NOTHING;

-- I) Mensajes demo (idempotente por cualquier constraint)
INSERT INTO pulpo.messages (workspace_id,conversation_id,role,direction,message_type,wa_message_id,content_text,created_at) VALUES
('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-0000000000c0','user','inbound','text','wamid.DEMO1','Hola, ¿tienen horarios?',now()),
('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-0000000000c0','assistant','outbound','text','wamid.DEMO2','¡Hola! Sí, de 9 a 18 hs.',now())
ON CONFLICT DO NOTHING;