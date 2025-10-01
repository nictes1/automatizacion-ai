Perfecto! Te voy a dar todos los archivos SQL con explicaciones detalladas y luego te ayudo a buscar alternativas a PostgresML y solucionar el tema de ingesta de archivos.


[7 tools called]

Ahora voy a buscar alternativas a PostgresML y crear una documentación completa:


[3 tools called]

Ahora voy a crear la documentación completa con todos los archivos SQL y las alternativas:

# 📋 Documentación Completa - PulpoAI SQL Schema

## 🎯 Objetivo General
Esta documentación contiene todos los archivos SQL del sistema PulpoAI, explicando su propósito y funcionalidad. Además, incluye alternativas a PostgresML y estrategias para la ingesta de archivos.

---

## �� Archivos SQL del Sistema

### 1. **`01_core_up.sql`** - Esquema Base del Sistema
**Objetivo**: Establece la estructura fundamental del SaaS multi-tenant con aislamiento por workspace.

```sql
-- sql/01_core_up.sql
CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS citext;
CREATE SCHEMA IF NOT EXISTS pulpo;

CREATE TABLE IF NOT EXISTS pulpo.workspaces(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  plan_tier text NOT NULL CHECK (plan_tier IN ('agent_basic','agent_pro','agent_premium', 'agent_custom')),  
  vertical text NOT NULL,
  settings_json jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pulpo.users(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  name text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS pulpo.workspace_members(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES pulpo.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','admin','editor','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, user_id)
);

CREATE TABLE IF NOT EXISTS pulpo.channels(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  type text NOT NULL CHECK (type IN ('whatsapp')),
  provider text NOT NULL CHECK (provider IN ('meta_whatsapp')),
  business_phone_id text NOT NULL,
  display_phone text NOT NULL,
  status text NOT NULL CHECK (status IN ('active','disabled')) DEFAULT 'active',
  settings_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, business_phone_id)
);

CREATE TABLE IF NOT EXISTS pulpo.contacts(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  user_phone text NOT NULL,
  attributes_json jsonb DEFAULT '{}'::jsonb,
  last_seen_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, user_phone)
);

CREATE TABLE IF NOT EXISTS pulpo.conversations(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  contact_id uuid NOT NULL REFERENCES pulpo.contacts(id) ON DELETE CASCADE,
  channel_id uuid NOT NULL REFERENCES pulpo.channels(id) ON DELETE CASCADE,
  status text NOT NULL CHECK (status IN ('open','closed')) DEFAULT 'open',
  last_message_at timestamptz,
  last_message_text   text,
  last_message_sender text,
  total_messages      int NOT NULL DEFAULT 0,
  unread_count        int NOT NULL DEFAULT 0,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_open_conv_per_contact
  ON pulpo.conversations(workspace_id, contact_id) WHERE status = 'open';

-- ENUMs idempotentes
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname='pulpo' AND t.typname='message_role'
  ) THEN
    CREATE TYPE pulpo.message_role AS ENUM ('user','assistant','system','tool');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname='pulpo' AND t.typname='message_dir'
  ) THEN
    CREATE TYPE pulpo.message_dir AS ENUM ('inbound','outbound');
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_type t JOIN pg_namespace n ON n.oid=t.typnamespace
    WHERE n.nspname='pulpo' AND t.typname='message_type'
  ) THEN
    CREATE TYPE pulpo.message_type AS ENUM
      ('text','image','document','audio','video','interactive','location','template');
  END IF;
END $$;

CREATE TABLE IF NOT EXISTS pulpo.messages(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL,
  conversation_id uuid NOT NULL,
  role pulpo.message_role NOT NULL,
  direction pulpo.message_dir NOT NULL,
  message_type pulpo.message_type NOT NULL,
  wa_message_id text,
  content_text text,
  model text,
  tool_name text,
  media_url text,
  meta_json jsonb DEFAULT '{}'::jsonb,
  tokens_in int,
  tokens_out int,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, wa_message_id)
);

-- FAQs
CREATE TABLE IF NOT EXISTS pulpo.faqs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  slug text NOT NULL,
  q text NOT NULL,
  a text NOT NULL,
  UNIQUE(workspace_id, slug)
);

-- Tickets de intervención
CREATE TABLE IF NOT EXISTS pulpo.handoff_tickets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  last_message_id uuid REFERENCES pulpo.messages(id),
  status text NOT NULL CHECK (status IN ('open','ack','closed')) DEFAULT 'open',
  reason text NOT NULL,
  detail text,
  created_at timestamptz NOT NULL DEFAULT now(),
  acknowledged_at timestamptz,
  closed_at timestamptz
);

-- workspace_configs
CREATE TABLE IF NOT EXISTS pulpo.workspace_configs (
  workspace_id uuid PRIMARY KEY REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  policy_json  jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- RLS (Row Level Security)
ALTER TABLE pulpo.workspaces        ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.channels          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.contacts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.messages          ENABLE ROW LEVEL SECURITY;

-- Función helper para contexto de workspace
CREATE OR REPLACE FUNCTION pulpo.set_ws_context(ws uuid) RETURNS void
LANGUAGE sql AS $$
  SELECT set_config('app.workspace_id', ws::text, true)::void
$$;

-- Policies de aislamiento por workspace
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_workspaces'
  ) THEN
    CREATE POLICY ws_isolation_workspaces ON pulpo.workspaces
      USING (id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_members'
  ) THEN
    CREATE POLICY ws_isolation_members ON pulpo.workspace_members
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_channels'
  ) THEN
    CREATE POLICY ws_isolation_channels ON pulpo.channels
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_contacts'
  ) THEN
    CREATE POLICY ws_isolation_contacts ON pulpo.contacts
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_conversations'
  ) THEN
    CREATE POLICY ws_isolation_conversations ON pulpo.conversations
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_messages'
  ) THEN
    CREATE POLICY ws_isolation_messages ON pulpo.messages
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
END $$;

-- Índices adicionales
CREATE INDEX IF NOT EXISTS idx_handoff_ws_status ON pulpo.handoff_tickets(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_conv_time ON pulpo.messages(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_ws_time   ON pulpo.messages(workspace_id, created_at DESC);

-- RLS en tablas secundarias
ALTER TABLE pulpo.faqs              ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.handoff_tickets   ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.workspace_configs ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_faqs') THEN
    CREATE POLICY ws_isolation_faqs ON pulpo.faqs
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_handoff') THEN
    CREATE POLICY ws_isolation_handoff ON pulpo.handoff_tickets
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_ws_configs') THEN
    CREATE POLICY ws_isolation_ws_configs ON pulpo.workspace_configs
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
END $$;
```

**Funcionalidades principales**:
- ✅ **Multi-tenancy**: Aislamiento completo por workspace con RLS
- ✅ **Gestión de usuarios**: Roles y permisos por workspace
- ✅ **Canales de comunicación**: WhatsApp Business API
- ✅ **Conversaciones**: Sistema completo de mensajería
- ✅ **FAQs**: Base de conocimiento por workspace
- ✅ **Handoff**: Escalamiento a agentes humanos
- ✅ **Configuración**: Settings flexibles por workspace

---

### 2. **`02_seed_dev.sql`** - Datos de Desarrollo
**Objetivo**: Poblar la base de datos con datos de prueba para desarrollo y testing.

```sql
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

-- I) Mensajes demo
INSERT INTO pulpo.messages (workspace_id,conversation_id,role,direction,message_type,wa_message_id,content_text,created_at) VALUES
('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-0000000000c0','user','inbound','text','wamid.DEMO1','Hola, ¿tienen horarios?',now()),
('00000000-0000-0000-0000-000000000001','00000000-0000-0000-0000-0000000000c0','assistant','outbound','text','wamid.DEMO2','¡Hola! Sí, de 9 a 18 hs.',now())
ON CONFLICT DO NOTHING;
```

**Funcionalidades principales**:
- ✅ **Workspace de desarrollo**: Configuración completa para testing
- ✅ **Configuración de negocio**: Settings para restaurante de prueba
- ✅ **Datos de ejemplo**: Usuario, canal, contacto, conversación
- ✅ **Mensajes de prueba**: Conversación inicial para testing

---

### 3. **`03_functions.sql`** - Funciones de Persistencia
**Objetivo**: Funciones para manejar la persistencia de mensajes entrantes y salientes.

```sql
--sql/03_functions.sql

SET search_path = public, pulpo;

-- Inbound con dedupe por (workspace_id, wa_message_id)
DROP FUNCTION IF EXISTS pulpo.persist_inbound(uuid, uuid, text, text, text);
CREATE OR REPLACE FUNCTION pulpo.persist_inbound(
  p_ws_id uuid,
  p_channel_id uuid,
  p_user_phone text,
  p_wamid text,
  p_text text
) RETURNS TABLE (conversation_id uuid, message_id uuid)
LANGUAGE plpgsql
AS $$
DECLARE
  v_contact_id   uuid;
  v_conv_id      uuid;
  v_msg_id       uuid;
  v_affected     int := 0;
  v_phone_digits text := regexp_replace(p_user_phone, '\D', '', 'g');
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);

  INSERT INTO pulpo.contacts (workspace_id, user_phone, last_seen_at)
  VALUES (p_ws_id, v_phone_digits, now())
  ON CONFLICT (workspace_id, user_phone)
  DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at
  RETURNING id INTO v_contact_id;

  SELECT c.id
    INTO v_conv_id
  FROM pulpo.conversations c
  WHERE c.workspace_id = p_ws_id
    AND c.contact_id   = v_contact_id
    AND c.status = 'open'
  ORDER BY c.created_at DESC
  LIMIT 1;

  IF v_conv_id IS NULL THEN
    INSERT INTO pulpo.conversations(
      workspace_id, contact_id, channel_id, status,
      last_message_at, last_message_text, last_message_sender,
      total_messages, unread_count
    )
    VALUES (
      p_ws_id, v_contact_id, p_channel_id, 'open',
      now(), p_text, 'user', 0, 0
    )
    RETURNING id INTO v_conv_id;
  END IF;

  INSERT INTO pulpo.messages(
    workspace_id, conversation_id, role, direction, message_type,
    wa_message_id, content_text, created_at
  )
  VALUES (
    p_ws_id, v_conv_id, 'user', 'inbound', 'text',
    p_wamid, p_text, now()
  )
  ON CONFLICT (workspace_id, wa_message_id) DO NOTHING;

  GET DIAGNOSTICS v_affected = ROW_COUNT;

  IF v_affected > 0 THEN
    SELECT m.id INTO v_msg_id
    FROM pulpo.messages m
    WHERE m.workspace_id = p_ws_id AND m.wa_message_id = p_wamid
    LIMIT 1;

    UPDATE pulpo.conversations
    SET last_message_at     = now(),
        last_message_text   = p_text,
        last_message_sender = 'user',
        total_messages      = total_messages + 1,
        unread_count        = unread_count + 1
    WHERE id = v_conv_id AND workspace_id = p_ws_id;
  ELSE
    SELECT m.id INTO v_msg_id
    FROM pulpo.messages m
    WHERE m.workspace_id = p_ws_id AND m.wa_message_id = p_wamid
    LIMIT 1;
  END IF;

  RETURN QUERY SELECT v_conv_id, v_msg_id;
END;
$$;

GRANT EXECUTE ON FUNCTION pulpo.persist_inbound(uuid, uuid, text, text, text) TO pulpo;

-- Outbound única (NO toca unread_count)
DROP FUNCTION IF EXISTS pulpo.persist_outbound(uuid, uuid, text, pulpo.message_type, text, jsonb);
CREATE OR REPLACE FUNCTION pulpo.persist_outbound(
  p_ws_id           uuid,
  p_conversation_id uuid,
  p_text            text,
  p_message_type    pulpo.message_type DEFAULT 'text',
  p_model           text DEFAULT NULL,
  p_meta            jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (message_id uuid)
LANGUAGE plpgsql
AS $$
DECLARE
  v_id uuid := gen_random_uuid();
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);

  INSERT INTO pulpo.messages (
    id, workspace_id, conversation_id,
    role, direction, message_type,
    content_text, model, meta_json, created_at
  )
  VALUES (
    v_id, p_ws_id, p_conversation_id,
    'assistant','outbound', p_message_type,
    p_text, p_model, COALESCE(p_meta,'{}'::jsonb), now()
  );

  UPDATE pulpo.conversations
  SET last_message_at     = now(),
      last_message_text   = p_text,
      last_message_sender = 'assistant',
      total_messages      = total_messages + 1
  WHERE id = p_conversation_id AND workspace_id = p_ws_id;

  RETURN QUERY SELECT v_id;
END;
$$;

GRANT EXECUTE ON FUNCTION pulpo.persist_outbound(uuid, uuid, text, pulpo.message_type, text, jsonb) TO pulpo;
```

**Funcionalidades principales**:
- ✅ **Persistencia de mensajes entrantes**: Manejo automático de contactos y conversaciones
- ✅ **Deduplicación**: Evita mensajes duplicados por wa_message_id
- ✅ **Persistencia de mensajes salientes**: Registro de respuestas del asistente
- ✅ **Actualización de contadores**: Total de mensajes y unread_count

---

### 4. **`04_views_debug.sql`** - Vistas de Debug
**Objetivo**: Vistas para facilitar el debugging y monitoreo del sistema.

```sql
-- 04_views_debug.sql

CREATE OR REPLACE VIEW pulpo.v_conversations_last AS
SELECT
  c.id,
  c.workspace_id,
  c.contact_id,
  c.channel_id,
  c.status,
  c.last_message_at,
  c.last_message_text,
  c.last_message_sender,
  c.total_messages,
  c.unread_count
FROM pulpo.conversations c;

CREATE OR REPLACE VIEW pulpo.v_messages_recent AS
SELECT
  m.id,
  m.workspace_id,
  m.conversation_id,
  m.role,
  m.direction,
  m.message_type,
  m.wa_message_id,
  m.content_text,
  m.created_at
FROM pulpo.messages m
ORDER BY m.created_at DESC
LIMIT 200;

-- Vistas de apoyo (debug/overview)
CREATE OR REPLACE VIEW pulpo.v_conversations_overview AS
SELECT
  c.workspace_id,
  c.id AS conversation_id,
  c.contact_id,
  c.channel_id,
  c.status,
  c.last_message_at,
  c.last_message_sender,
  c.last_message_text,
  c.total_messages,
  c.unread_count
FROM pulpo.conversations c
ORDER BY c.last_message_at DESC;
```

**Funcionalidades principales**:
- ✅ **Vista de conversaciones**: Estado actual de todas las conversaciones
- ✅ **Vista de mensajes recientes**: Últimos 200 mensajes para debugging
- ✅ **Vista de overview**: Resumen de conversaciones ordenadas por actividad

---

### 5. **`05_settings_and_helpers.sql`** - Helpers y Configuración
**Objetivo**: Funciones auxiliares para configuración y resolución de canales.

```sql
-- sql/05_settings_and_helpers.sql

SET search_path = public, pulpo;

-- 1) Canal con overrides de settings
ALTER TABLE pulpo.channels
  ADD COLUMN IF NOT EXISTS settings_json jsonb NOT NULL DEFAULT '{}'::jsonb;

-- 2) Helper: devuelve plan/vertical y settings mergeados (workspace || channel)
CREATE OR REPLACE FUNCTION pulpo.get_plan_vertical_settings(
  p_ws_id uuid,
  p_channel_id uuid
) RETURNS TABLE (
  ws_id uuid,
  channel_id uuid,
  plan_tier text,
  vertical text,
  biz_settings jsonb
)
LANGUAGE sql STABLE AS $$
  SELECT
    w.id       AS ws_id,
    c.id       AS channel_id,
    w.plan_tier,
    w.vertical,
    COALESCE(w.settings_json,'{}'::jsonb) || COALESCE(c.settings_json,'{}'::jsonb) AS biz_settings
  FROM pulpo.workspaces w
  JOIN pulpo.channels   c ON c.id = p_channel_id AND c.workspace_id = w.id
  WHERE w.id = p_ws_id
$$;

GRANT EXECUTE ON FUNCTION pulpo.get_plan_vertical_settings(uuid, uuid) TO pulpo;

-- Normaliza y resuelve canal por display_phone (digits only)
CREATE OR REPLACE FUNCTION pulpo.resolve_channel_by_phone(p_to_phone text)
RETURNS TABLE(channel_id uuid, ws_id uuid, display_phone text)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  WITH input AS (
    SELECT regexp_replace(p_to_phone, '\D', '', 'g') AS digits
  )
  SELECT c.id, c.workspace_id, c.display_phone
  FROM pulpo.channels c, input i
  WHERE regexp_replace(c.display_phone, '\D', '', 'g') = i.digits
  LIMIT 1
$$;

GRANT EXECUTE ON FUNCTION pulpo.resolve_channel_by_phone(text) TO pulpo;
```

**Funcionalidades principales**:
- ✅ **Configuración por canal**: Overrides de settings a nivel de canal
- ✅ **Merge de configuración**: Combina settings de workspace y canal
- ✅ **Resolución de canales**: Encuentra canal por número de teléfono

---

### 6. **`06_plg_up.sql`** - Analytics y Métricas
**Objetivo**: Tablas para tracking de intenciones, métricas de plan y email outbox.

```sql
-- sql/06_plg_up.sql
SET search_path = public, pulpo;

CREATE TABLE IF NOT EXISTS pulpo.intent_events(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid REFERENCES pulpo.conversations(id) ON DELETE SET NULL,
  message_id uuid REFERENCES pulpo.messages(id) ON DELETE SET NULL,
  intent text NOT NULL,
  confidence numeric(3,2) NOT NULL,
  required_capability text,
  blocked_by_plan boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_ie_ws_time ON pulpo.intent_events(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ie_ws_block ON pulpo.intent_events(workspace_id, blocked_by_plan, created_at);

CREATE TABLE IF NOT EXISTS pulpo.plan_opportunities_daily(
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  day date NOT NULL,
  metric_key text NOT NULL,
  metric_value bigint NOT NULL DEFAULT 0,
  PRIMARY KEY(workspace_id, day, metric_key)
);

CREATE TABLE IF NOT EXISTS pulpo.email_outbox(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  to_email citext NOT NULL,
  subject text NOT NULL,
  body_json jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('pending','sent','failed')) DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);

CREATE OR REPLACE FUNCTION pulpo.inc_plan_metric(p_ws uuid, p_day date, p_key text, p_inc int)
RETURNS void LANGUAGE sql AS $$
  INSERT INTO pulpo.plan_opportunities_daily(workspace_id, day, metric_key, metric_value)
  VALUES (p_ws, p_day, p_key, p_inc)
  ON CONFLICT(workspace_id, day, metric_key)
  DO UPDATE SET metric_value = plan_opportunities_daily.metric_value + EXCLUDED.metric_value;
$$;

ALTER TABLE pulpo.intent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.plan_opportunities_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.email_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY ws_isolation_intent_events ON pulpo.intent_events
USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);

CREATE POLICY ws_isolation_plan_opportunities_daily ON pulpo.plan_opportunities_daily
USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);

CREATE POLICY ws_isolation_email_outbox ON pulpo.email_outbox
USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
```

**Funcionalidades principales**:
- ✅ **Tracking de intenciones**: Registro de intenciones detectadas con confianza
- ✅ **Métricas de plan**: Contadores diarios por workspace
- ✅ **Email outbox**: Cola de emails pendientes de envío
- ✅ **Función de incremento**: Helper para actualizar métricas

---

### 7. **`07_rag_up.sql`** - Sistema RAG Completo
**Objetivo**: Implementación completa del sistema RAG con pgvector, chunking y búsqueda híbrida.

```sql
-- Pulpo RAG — esquema y soportes de búsqueda (vector + léxico)
-- Este script es idempotente.

SET search_path = public, pulpo;

-- Extensiones necesarias
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='vector') THEN
    CREATE EXTENSION vector;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='unaccent') THEN
    CREATE EXTENSION unaccent;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pg_trgm') THEN
    CREATE EXTENSION pg_trgm;
  END IF;
END
$$;

-- Tablas base de RAG
CREATE TABLE IF NOT EXISTS pulpo.documents(
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  title        text,
  mime         text,
  storage_url  text,
  size_bytes   bigint,
  hash         text NOT NULL,
  created_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, hash)
);

CREATE TABLE IF NOT EXISTS pulpo.chunks(
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  document_id  uuid NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
  pos          int  NOT NULL,
  text         text NOT NULL,
  meta         jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(workspace_id, document_id, pos)
);

-- IMPORTANTE: ajustar dimensión si cambiás de modelo de embeddings.
-- Por ahora se asume 1024 (e.g. BGE-M3).
CREATE TABLE IF NOT EXISTS pulpo.chunk_embeddings(
  chunk_id     uuid PRIMARY KEY REFERENCES pulpo.chunks(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL,
  document_id  uuid NOT NULL,
  embedding    vector(1024) NOT NULL
);

CREATE TABLE IF NOT EXISTS pulpo.ingest_jobs(
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id  uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  document_id   uuid REFERENCES pulpo.documents(id) ON DELETE CASCADE,
  status        text NOT NULL CHECK (status IN ('queued','processing','success','failed')),
  error_message text,
  stats_json    jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz
);

-- RLS
ALTER TABLE pulpo.documents        ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.chunks           ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.chunk_embeddings ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.ingest_jobs      ENABLE ROW LEVEL SECURITY;

-- Policies (idempotentes)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_documents') THEN
    CREATE POLICY ws_iso_documents ON pulpo.documents
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_chunks') THEN
    CREATE POLICY ws_iso_chunks ON pulpo.chunks
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_chunk_embeddings') THEN
    CREATE POLICY ws_iso_chunk_embeddings ON pulpo.chunk_embeddings
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname='ws_iso_ingest_jobs') THEN
    CREATE POLICY ws_iso_ingest_jobs ON pulpo.ingest_jobs
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
END
$$;

-- Índice vectorial (IVFFLAT) para cosine
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='pulpo' AND indexname='ivf_chunk_embeddings'
  ) THEN
    CREATE INDEX ivf_chunk_embeddings
      ON pulpo.chunk_embeddings
      USING ivfflat (embedding vector_cosine_ops)
      WITH (lists = 100);
  END IF;
END
$$;

-- Wrapper inmutable de unaccent (para usar en índices por expresión)
CREATE OR REPLACE FUNCTION pulpo.immutable_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE STRICT PARALLEL SAFE
AS $f$
  SELECT unaccent('unaccent', $1)
$f$;

-- Índice GIN por expresión: TS en español + unaccent inmutable sobre pulpo.chunks.text
CREATE INDEX IF NOT EXISTS idx_chunks_tsv_expr
  ON pulpo.chunks
  USING GIN (to_tsvector('spanish', pulpo.immutable_unaccent(coalesce(text,''))));

-- Trigram GIN para similarity()
CREATE INDEX IF NOT EXISTS idx_chunks_trgm
  ON pulpo.chunks
  USING GIN (text gin_trgm_ops);
```

**Funcionalidades principales**:
- ✅ **Gestión de documentos**: Almacenamiento de archivos con metadatos
- ✅ **Chunking**: División de documentos en fragmentos
- ✅ **Embeddings**: Vectores de 1024 dimensiones (BGE-M3)
- ✅ **Búsqueda híbrida**: Vector + full-text search en español
- ✅ **Jobs de ingesta**: Tracking del procesamiento de documentos
- ✅ **Índices optimizados**: IVFFLAT para vectores, GIN para texto

---

## 🔄 Alternativas a PostgresML

### 1. **Supabase Vector (pgvector + Edge Functions)**
**Ventajas**:
- ✅ **pgvector nativo**: Ya lo tienes implementado
- ✅ **Edge Functions**: Para chunking y embeddings
- ✅ **Integración perfecta**: Con tu esquema actual
- ✅ **Costo**: Solo pagas por uso

**Implementación**:
```sql
-- Usar tu esquema actual + Edge Functions para:
-- 1. Chunking con JavaScript/TypeScript
-- 2. Embeddings con OpenAI/Cohere
-- 3. Búsqueda vectorial nativa
```

### 2. **Qdrant (Vector Database)**
**Ventajas**:
- ✅ **Performance**: Optimizado para vectores
- ✅ **Re-ranking**: Cross-encoders nativos
- ✅ **Filtros**: Metadatos complejos
- ✅ **Escalabilidad**: Horizontal

**Implementación**:
```python
# Pipeline: PostgreSQL (metadatos) + Qdrant (vectores)
# 1. Extraer texto → PostgreSQL
# 2. Chunking → PostgreSQL  
# 3. Embeddings → Qdrant
# 4. Búsqueda → Qdrant + PostgreSQL
```

### 3. **Weaviate (Vector Database)**
**Ventajas**:
- ✅ **GraphQL**: API moderna
- ✅ **Multi-modal**: Texto, imágenes, etc.
- ✅ **Auto-schema**: Inferencia automática
- ✅ **Cloud/self-hosted**: Flexibilidad

### 4. **Chroma (Vector Database)**
**Ventajas**:
- ✅ **Simplicidad**: Fácil de usar
- ✅ **Python-first**: Integración natural
- ✅ **Persistencia**: Local o remoto
- ✅ **Filtros**: Metadatos flexibles

### 5. **Pinecone (Managed Vector DB)**
**Ventajas**:
- ✅ **Managed**: Sin infraestructura
- ✅ **Performance**: Optimizado
- ✅ **Escalabilidad**: Automática
- ✅ **Filtros**: Metadatos complejos

---

## 📄 Estrategias para Ingesta de Archivos

### **Opción 1: Pipeline con Apache Tika + Python**
```python
# 1. Extracción de texto
import tika
from tika import parser

def extract_text(file_path):
    parsed = parser.from_file(file_path)
    return parsed['content']

# 2. Chunking inteligente
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_text(text, chunk_size=800, overlap=120):
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        separators=["\n\n", "\n", ". ", " "]
    )
    return splitter.split_text(text)

# 3. Embeddings con OpenAI/Cohere
import openai

def generate_embeddings(texts):
    response = openai.Embedding.create(
        input=texts,
        model="text-embedding-3-large"
    )
    return [item['embedding'] for item in response['data']]
```

### **Opción 2: Pipeline con Unstructured**
```python
# 1. Extracción inteligente
from unstructured.partition.auto import partition

def extract_documents(file_path):
    elements = partition(file_path)
    return [str(element) for element in elements]

# 2. Chunking por elementos
def chunk_by_elements(elements):
    chunks = []
    current_chunk = ""
    
    for element in elements:
        if len(current_chunk + element) > 800:
            if current_chunk:
                chunks.append(current_chunk)
            current_chunk = element
        else:
            current_chunk += "\n" + element
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks
```

### **Opción 3: Pipeline con LangChain**
```python
from langchain.document_loaders import PyPDFLoader, Docx2txtLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from lang