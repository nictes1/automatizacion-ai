-- sql/08_vertical_packs_up.sql
-- Extensión del esquema para soportar Vertical Packs, Slot Manager y Policy Orchestrator

SET search_path = public, pulpo;

-- 1. Tabla para Vertical Packs (configuración por vertical)
CREATE TABLE IF NOT EXISTS pulpo.vertical_packs (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  vertical text NOT NULL CHECK (vertical IN ('gastronomia', 'ecommerce', 'inmobiliaria', 'generico')),
  role_prompt text NOT NULL,
  intents_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  slots_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  tools_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  policies_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  handoff_rules jsonb NOT NULL DEFAULT '{}'::jsonb,
  rag_sources jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, vertical)
);

-- 2. Tabla para Slot Manager (estado de slots por conversación)
CREATE TABLE IF NOT EXISTS pulpo.conversation_slots (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  intent text NOT NULL,
  slots_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  required_slots jsonb NOT NULL DEFAULT '[]'::jsonb,
  completed_slots jsonb NOT NULL DEFAULT '[]'::jsonb,
  current_question text,
  attempts_count int NOT NULL DEFAULT 0,
  max_attempts int NOT NULL DEFAULT 3,
  status text NOT NULL CHECK (status IN ('collecting', 'completed', 'failed', 'handoff')) DEFAULT 'collecting',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, conversation_id, intent)
);

-- 3. Tabla para Policy Orchestrator (estado del flujo)
CREATE TABLE IF NOT EXISTS pulpo.conversation_flow_state (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  current_state text NOT NULL,
  previous_state text,
  state_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  automation_enabled boolean NOT NULL DEFAULT true,
  handoff_reason text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, conversation_id)
);

-- 4. Tabla para Tools/Agentes (registro de herramientas disponibles)
CREATE TABLE IF NOT EXISTS pulpo.available_tools (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  tool_name text NOT NULL,
  tool_config jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, tool_name)
);

-- 5. Tabla para Router (clasificación de intenciones)
CREATE TABLE IF NOT EXISTS pulpo.intent_classifications (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  message_id uuid REFERENCES pulpo.messages(id) ON DELETE SET NULL,
  input_text text NOT NULL,
  detected_intent text NOT NULL,
  confidence numeric(3,2) NOT NULL,
  vertical text NOT NULL,
  router_version text NOT NULL DEFAULT 'v1',
  created_at timestamptz NOT NULL DEFAULT now()
);

-- 6. Tabla para Handoff Controller (tickets de escalamiento)
CREATE TABLE IF NOT EXISTS pulpo.handoff_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  trigger_reason text NOT NULL,
  trigger_data jsonb NOT NULL DEFAULT '{}'::jsonb,
  status text NOT NULL CHECK (status IN ('triggered', 'acknowledged', 'resolved', 'escalated')) DEFAULT 'triggered',
  assigned_to uuid REFERENCES pulpo.users(id),
  created_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);

-- RLS para todas las nuevas tablas
ALTER TABLE pulpo.vertical_packs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversation_slots ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversation_flow_state ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.available_tools ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.intent_classifications ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.handoff_events ENABLE ROW LEVEL SECURITY;

-- Policies de aislamiento
DO $$
BEGIN
  -- Vertical Packs
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_vertical_packs') THEN
    CREATE POLICY ws_isolation_vertical_packs ON pulpo.vertical_packs
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  -- Conversation Slots
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_conversation_slots') THEN
    CREATE POLICY ws_isolation_conversation_slots ON pulpo.conversation_slots
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  -- Conversation Flow State
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_conversation_flow_state') THEN
    CREATE POLICY ws_isolation_conversation_flow_state ON pulpo.conversation_flow_state
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  -- Available Tools
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_available_tools') THEN
    CREATE POLICY ws_isolation_available_tools ON pulpo.available_tools
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  -- Intent Classifications
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_intent_classifications') THEN
    CREATE POLICY ws_isolation_intent_classifications ON pulpo.intent_classifications
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;

  -- Handoff Events
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND policyname='ws_isolation_handoff_events') THEN
    CREATE POLICY ws_isolation_handoff_events ON pulpo.handoff_events
      USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
      WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);
  END IF;
END $$;

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_vertical_packs_ws_vertical ON pulpo.vertical_packs(workspace_id, vertical);
CREATE INDEX IF NOT EXISTS idx_conversation_slots_conv_intent ON pulpo.conversation_slots(conversation_id, intent);
CREATE INDEX IF NOT EXISTS idx_conversation_flow_state_conv ON pulpo.conversation_flow_state(conversation_id);
CREATE INDEX IF NOT EXISTS idx_available_tools_ws_name ON pulpo.available_tools(workspace_id, tool_name);
CREATE INDEX IF NOT EXISTS idx_intent_classifications_conv_time ON pulpo.intent_classifications(conversation_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_handoff_events_ws_status ON pulpo.handoff_events(workspace_id, status);

-- Triggers para updated_at
CREATE OR REPLACE FUNCTION pulpo.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_vertical_packs_updated_at BEFORE UPDATE ON pulpo.vertical_packs FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();
CREATE TRIGGER update_conversation_slots_updated_at BEFORE UPDATE ON pulpo.conversation_slots FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();
CREATE TRIGGER update_conversation_flow_state_updated_at BEFORE UPDATE ON pulpo.conversation_flow_state FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();
