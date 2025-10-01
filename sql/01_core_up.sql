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

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='pulpo' AND indexname='uq_channel_phone_digits'
  ) THEN
    CREATE UNIQUE INDEX uq_channel_phone_digits
  ON pulpo.channels (
    workspace_id,
    (regexp_replace(display_phone, E'\\D', '', 'g'))
  );
  END IF;
END $$;

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

CREATE INDEX IF NOT EXISTS idx_handoff_ws_status ON pulpo.handoff_tickets(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_messages_conv_time ON pulpo.messages(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_messages_ws_time   ON pulpo.messages(workspace_id, created_at DESC);

-- NUEVO: workspace_configs
CREATE TABLE IF NOT EXISTS pulpo.workspace_configs (
  workspace_id uuid PRIMARY KEY REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  policy_json  jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at   timestamptz NOT NULL DEFAULT now()
);

-- RLS
ALTER TABLE pulpo.workspaces        ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.workspace_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.channels          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.contacts          ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversations     ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.messages          ENABLE ROW LEVEL SECURITY;

-- Función helper
CREATE OR REPLACE FUNCTION pulpo.set_ws_context(ws uuid) RETURNS void
LANGUAGE sql AS $$
  SELECT set_config('app.workspace_id', ws::text, true)::void
$$;

-- Policies idempotentes
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

CREATE UNIQUE INDEX IF NOT EXISTS uq_conversations_ws_id
  ON pulpo.conversations(workspace_id, id);

-- FK compuesta messages → conversations (quitar del 07_*)
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE constraint_schema='pulpo'
      AND table_name='messages'
      AND constraint_name='fk_messages_ws_conv'
  ) THEN
    ALTER TABLE pulpo.messages
      ADD CONSTRAINT fk_messages_ws_conv
      FOREIGN KEY (workspace_id, conversation_id)
      REFERENCES pulpo.conversations(workspace_id, id)
      ON DELETE CASCADE
      DEFERRABLE INITIALLY IMMEDIATE;
  END IF;
END $$;

CREATE INDEX IF NOT EXISTS idx_messages_ws_conv_time
  ON pulpo.messages (workspace_id, conversation_id, created_at DESC);

-- RLS en secundarias
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
