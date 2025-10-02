-- =====================================================
-- PULPOAI DATABASE SCHEMA - CONSOLIDATED
-- =====================================================
-- Esquema consolidado de base de datos para PulpoAI
-- Incluye: Core, RAG, Actions, Orchestrator, RLS, Functions
-- =====================================================

-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";
CREATE EXTENSION IF NOT EXISTS "vector";
CREATE EXTENSION IF NOT EXISTS "citext";

-- Crear esquema
CREATE SCHEMA IF NOT EXISTS pulpo;
SET search_path = public, pulpo;

-- =====================================================
-- CORE TABLES - MULTITENANT FOUNDATION
-- =====================================================

-- Workspaces (multitenant root)
CREATE TABLE pulpo.workspaces(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name text NOT NULL,
  domain text,
  plan text NOT NULL CHECK (plan IN ('basic','premium','enterprise')),
  settings jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Users
CREATE TABLE pulpo.users(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  name text NOT NULL,
  role text NOT NULL CHECK (role IN ('admin','user','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Workspace members (RLS)
CREATE TABLE pulpo.workspace_members(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES pulpo.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','admin','editor','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, user_id)
);

-- Channels (WhatsApp, etc.)
CREATE TABLE pulpo.channels(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  type text NOT NULL CHECK (type IN ('whatsapp')),
  name text NOT NULL,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Contacts
CREATE TABLE pulpo.contacts(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  channel_id uuid NOT NULL REFERENCES pulpo.channels(id) ON DELETE CASCADE,
  external_id text NOT NULL,
  name text,
  phone text,
  email text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, external_id)
);

-- Conversations
CREATE TABLE pulpo.conversations(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  channel_id uuid NOT NULL REFERENCES pulpo.channels(id) ON DELETE CASCADE,
  contact_id uuid NOT NULL REFERENCES pulpo.contacts(id) ON DELETE CASCADE,
  status text NOT NULL CHECK (status IN ('active','paused','closed','handoff')) DEFAULT 'active',
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Messages
CREATE TABLE pulpo.messages(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  sender text NOT NULL CHECK (sender IN ('user','assistant','system')),
  content text NOT NULL,
  message_type text NOT NULL DEFAULT 'text',
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =====================================================
-- DIALOGUE STATE TRACKING (E-01)
-- =====================================================

-- Dialogue states (current state per conversation)
CREATE TABLE pulpo.dialogue_states(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  fsm_state text NOT NULL,
  intent text,
  slots jsonb DEFAULT '{}'::jsonb,
  next_action text NOT NULL CHECK (next_action IN ('answer','tool_call','handoff','wait')),
  meta jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, conversation_id)
);

-- Dialogue state history (audit trail)
CREATE TABLE pulpo.dialogue_state_history(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  event text NOT NULL,
  payload jsonb DEFAULT '{}'::jsonb,
  previous_state jsonb,
  new_state jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Dialogue slots (typed slots)
CREATE TABLE pulpo.dialogue_slots(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  slot_name text NOT NULL,
  slot_value jsonb NOT NULL,
  slot_type text NOT NULL CHECK (slot_type IN ('string','number','boolean','object','array')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, conversation_id, slot_name)
);

-- =====================================================
-- RAG SYSTEM
-- =====================================================

-- Documents
CREATE TABLE pulpo.documents(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  title text NOT NULL,
  content text NOT NULL,
  document_type text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Document chunks (for RAG)
CREATE TABLE pulpo.document_chunks(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
  content text NOT NULL,
  chunk_index integer NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =====================================================
-- ACTIONS & BUSINESS LOGIC
-- =====================================================

-- Business actions (orders, appointments, etc.)
CREATE TABLE pulpo.business_actions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  action_type text NOT NULL,
  action_data jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('pending','processing','completed','failed')) DEFAULT 'pending',
  result jsonb,
  error_message text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Orders (gastronomy)
CREATE TABLE pulpo.orders(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  items jsonb NOT NULL,
  extras jsonb DEFAULT '[]'::jsonb,
  total numeric(12,2),
  metodo_entrega text CHECK (metodo_entrega IN ('retiro','delivery')),
  direccion text,
  metodo_pago text CHECK (metodo_pago IN ('efectivo','qr','tarjeta')),
  status text CHECK (status IN ('draft','confirmed','preparing','ready','delivered','cancelled')) DEFAULT 'draft',
  eta_minutes integer,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Properties (real estate)
CREATE TABLE pulpo.properties(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  operation text CHECK (operation IN ('venta','alquiler')),
  type text CHECK (type IN ('departamento','casa','ph','oficina','local','terreno')),
  zone text,
  address text,
  price numeric(14,2),
  bedrooms integer,
  bathrooms integer,
  surface_m2 numeric(8,2),
  description text,
  features jsonb DEFAULT '{}'::jsonb,
  images jsonb DEFAULT '[]'::jsonb,
  contact_phone text,
  contact_email text,
  is_available boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Appointments/Visits
CREATE TABLE pulpo.appointments(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  appointment_type text NOT NULL,
  scheduled_at timestamptz NOT NULL,
  duration_minutes integer DEFAULT 60,
  status text CHECK (status IN ('scheduled','confirmed','completed','cancelled')) DEFAULT 'scheduled',
  notes text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Action executions (for idempotency and tracking)
CREATE TABLE pulpo.action_executions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  action_name text NOT NULL,
  idempotency_key text NOT NULL,
  status text NOT NULL CHECK (status IN ('processing','success','failed')),
  summary text,
  details jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz,
  UNIQUE(workspace_id, idempotency_key)
);

-- Pedidos (gastronomía)
CREATE TABLE pulpo.pedidos(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
  items_json jsonb NOT NULL,
  metodo_entrega text CHECK (metodo_entrega IN ('retira','envio')),
  direccion text,
  total numeric(12,2),
  status text CHECK (status IN ('draft','confirmed','preparing','ready','delivered','cancelled')) DEFAULT 'draft',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Menu items (gastronomía catalog)
CREATE TABLE pulpo.menu_items(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  sku text,
  nombre text NOT NULL,
  descripcion text,
  precio numeric(10,2) NOT NULL,
  categoria text,
  disponible boolean DEFAULT true,
  imagen_url text,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Outbox events (for event-driven architecture)
CREATE TABLE pulpo.outbox_events(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('pending','sent','failed')) DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);

-- =====================================================
-- VERTICAL CONFIGURATION
-- =====================================================

-- Vertical configs
CREATE TABLE pulpo.vertical_configs(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  vertical text NOT NULL,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, vertical)
);

-- Document embeddings
CREATE TABLE pulpo.document_embeddings(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id uuid NOT NULL REFERENCES pulpo.document_chunks(id) ON DELETE CASCADE,
  embedding vector(768),  -- nomic-embed-text uses 768 dimensions
  model text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(chunk_id)
);

-- =====================================================
-- MONITORING & OBSERVABILITY
-- =====================================================

-- System metrics
CREATE TABLE pulpo.system_metrics(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  metric_name text NOT NULL,
  metric_value numeric NOT NULL,
  metric_unit text,
  tags jsonb DEFAULT '{}'::jsonb,
  recorded_at timestamptz NOT NULL DEFAULT now()
);

-- Error logs
CREATE TABLE pulpo.error_logs(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  service_name text NOT NULL,
  error_type text NOT NULL,
  error_message text NOT NULL,
  stack_trace text,
  context jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Core indexes
CREATE INDEX idx_workspaces_plan ON pulpo.workspaces(plan);
CREATE INDEX idx_conversations_workspace ON pulpo.conversations(workspace_id);
CREATE INDEX idx_conversations_contact ON pulpo.conversations(contact_id);
CREATE INDEX idx_messages_conversation ON pulpo.messages(conversation_id);
CREATE INDEX idx_messages_workspace ON pulpo.messages(workspace_id);
CREATE INDEX idx_messages_created_at ON pulpo.messages(created_at);

-- Dialogue state indexes
CREATE INDEX idx_dialogue_states_conversation ON pulpo.dialogue_states(conversation_id);
CREATE INDEX idx_dialogue_states_workspace ON pulpo.dialogue_states(workspace_id);
CREATE INDEX idx_dialogue_state_history_conversation ON pulpo.dialogue_state_history(conversation_id);

-- RAG indexes
CREATE INDEX idx_documents_workspace ON pulpo.documents(workspace_id);
CREATE INDEX idx_document_chunks_document ON pulpo.document_chunks(document_id);
CREATE INDEX idx_document_embeddings_embedding ON pulpo.document_embeddings USING ivfflat (embedding vector_cosine_ops);
CREATE INDEX idx_document_embeddings_chunk ON pulpo.document_embeddings(chunk_id);

-- Business logic indexes
CREATE INDEX idx_orders_conversation ON pulpo.orders(conversation_id);
CREATE INDEX idx_orders_workspace ON pulpo.orders(workspace_id);
CREATE INDEX idx_properties_workspace ON pulpo.properties(workspace_id);
CREATE INDEX idx_appointments_conversation ON pulpo.appointments(conversation_id);
CREATE INDEX idx_action_executions_workspace ON pulpo.action_executions(workspace_id);
CREATE INDEX idx_action_executions_conversation ON pulpo.action_executions(conversation_id);
CREATE INDEX idx_pedidos_workspace ON pulpo.pedidos(workspace_id);
CREATE INDEX idx_pedidos_conversation ON pulpo.pedidos(conversation_id);
CREATE INDEX idx_menu_items_workspace ON pulpo.menu_items(workspace_id);
CREATE INDEX idx_outbox_events_status ON pulpo.outbox_events(status, created_at);

-- Monitoring indexes
CREATE INDEX idx_system_metrics_recorded_at ON pulpo.system_metrics(recorded_at);
CREATE INDEX idx_error_logs_created_at ON pulpo.error_logs(created_at);
CREATE INDEX idx_error_logs_service ON pulpo.error_logs(service_name);
