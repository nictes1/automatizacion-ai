-- =====================================================
-- PULPOAI DATABASE SCHEMA - NORMALIZED & CONSOLIDATED
-- =====================================================
-- Schema normalizado que corrige todas las inconsistencias
-- Versión: 2.0 - Enero 2025
--
-- Este es el schema canónico para fresh installations.
-- Para migraciones desde versiones anteriores, ver migration scripts.
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

  -- Información básica
  name text NOT NULL,
  domain text,

  -- Vertical del negocio
  vertical text NOT NULL CHECK (vertical IN ('gastronomia','inmobiliaria','servicios')),

  -- Plan de suscripción
  plan text NOT NULL CHECK (plan IN ('basic','premium','enterprise')),

  -- Metadata del negocio (para respuestas contextuales)
  business_name text, -- Nombre comercial (puede diferir de 'name')
  address text, -- Dirección física
  phone text, -- Teléfono de contacto
  email text, -- Email de contacto
  logo_url text, -- URL del logo
  website text, -- Sitio web
  description text, -- Descripción del negocio

  -- Configuración técnica
  settings jsonb DEFAULT '{}'::jsonb,

  -- Timestamps
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.workspaces IS 'Raíz del multitenant - cada workspace es un negocio independiente';
COMMENT ON COLUMN pulpo.workspaces.vertical IS 'Vertical del negocio: gastronomia, inmobiliaria, servicios';
COMMENT ON COLUMN pulpo.workspaces.settings IS 'Configuración técnica: Twilio, Ollama, webhooks, etc.';
COMMENT ON COLUMN pulpo.workspaces.business_name IS 'Nombre comercial del negocio (para usar en conversaciones)';

-- Users
CREATE TABLE pulpo.users(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  email citext UNIQUE NOT NULL,
  name text NOT NULL,
  role text NOT NULL CHECK (role IN ('admin','user','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.users IS 'Usuarios del sistema (administradores, operadores)';

-- Workspace members (RLS)
CREATE TABLE pulpo.workspace_members(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  user_id uuid NOT NULL REFERENCES pulpo.users(id) ON DELETE CASCADE,
  role text NOT NULL CHECK (role IN ('owner','admin','editor','viewer')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, user_id)
);

COMMENT ON TABLE pulpo.workspace_members IS 'Relación M2M entre workspaces y usuarios con roles';

-- Channels (WhatsApp, etc.)
CREATE TABLE pulpo.channels(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  type text NOT NULL CHECK (type IN ('whatsapp','telegram','instagram','webchat')),
  name text NOT NULL,
  config jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean DEFAULT true,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.channels IS 'Canales de comunicación (WhatsApp, Telegram, etc.)';

-- Contacts
CREATE TABLE pulpo.contacts(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  channel_id uuid NOT NULL REFERENCES pulpo.channels(id) ON DELETE CASCADE,
  external_id text NOT NULL, -- Phone number, user ID, etc.
  name text,
  phone text,
  email text,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, external_id)
);

COMMENT ON TABLE pulpo.contacts IS 'Contactos/clientes que interactúan por los canales';

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

COMMENT ON TABLE pulpo.conversations IS 'Conversaciones entre clientes y el sistema';

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

COMMENT ON TABLE pulpo.messages IS 'Mensajes dentro de las conversaciones';

-- =====================================================
-- DIALOGUE STATE TRACKING
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

COMMENT ON TABLE pulpo.dialogue_states IS 'Estado actual del diálogo por conversación (FSM)';

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

COMMENT ON TABLE pulpo.dialogue_state_history IS 'Historial de transiciones de estado (audit trail)';

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

COMMENT ON TABLE pulpo.dialogue_slots IS 'Slots tipados del diálogo (entidades extraídas)';

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

COMMENT ON TABLE pulpo.documents IS 'Documentos del negocio (PDFs, FAQs, políticas)';

-- Document chunks (for RAG)
CREATE TABLE pulpo.document_chunks(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  document_id uuid NOT NULL REFERENCES pulpo.documents(id) ON DELETE CASCADE,
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  content text NOT NULL,
  chunk_index integer NOT NULL,
  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.document_chunks IS 'Chunks de documentos para búsqueda semántica';

-- Document embeddings
CREATE TABLE pulpo.document_embeddings(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chunk_id uuid NOT NULL REFERENCES pulpo.document_chunks(id) ON DELETE CASCADE,
  embedding vector(768),  -- nomic-embed-text uses 768 dimensions
  model text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(chunk_id)
);

COMMENT ON TABLE pulpo.document_embeddings IS 'Embeddings vectoriales para RAG semántico';

-- =====================================================
-- BUSINESS CATALOG - STAFF
-- =====================================================

-- Staff (empleados/profesionales)
CREATE TABLE pulpo.staff(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Información básica
  name text NOT NULL,
  email text,
  phone text,
  role text, -- "peluquero", "chef", "asesor", etc.

  -- Disponibilidad
  is_active boolean DEFAULT true,
  working_hours jsonb DEFAULT '{}'::jsonb, -- {"monday": ["09:00-13:00", "14:00-18:00"], ...}

  -- Integración Google Calendar
  google_calendar_id text,

  -- Metadata
  skills jsonb DEFAULT '[]'::jsonb, -- ["corte", "coloración"]
  bio text, -- Biografía/descripción
  avatar_url text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.staff IS 'Staff/empleados del negocio (peluqueros, chefs, asesores)';
COMMENT ON COLUMN pulpo.staff.working_hours IS 'Horarios laborales: {"monday": ["09:00-13:00"], "tuesday": []}';
COMMENT ON COLUMN pulpo.staff.skills IS 'Habilidades: ["corte", "coloración", "asesoramiento"]';

-- =====================================================
-- BUSINESS CATALOG - SERVICE TYPES
-- =====================================================

-- Service types (catálogo de servicios)
CREATE TABLE pulpo.service_types(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  -- Información del servicio
  name text NOT NULL,
  description text,
  category text, -- "hair", "nails", "spa", "consultation", etc.

  -- Precio y duración de referencia (el real está en staff_services)
  price_reference numeric(10,2),
  currency text DEFAULT 'ARS',
  duration_minutes integer DEFAULT 60,

  -- Disponibilidad
  is_active boolean DEFAULT true,
  requires_staff boolean DEFAULT true,

  -- Metadata
  image_url text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.service_types IS 'Catálogo de servicios ofrecidos';
COMMENT ON COLUMN pulpo.service_types.price_reference IS 'Precio base de referencia - el real está en staff_services.price';
COMMENT ON COLUMN pulpo.service_types.duration_minutes IS 'Duración promedio - la real está en staff_services.duration_minutes';

-- =====================================================
-- BUSINESS CATALOG - STAFF SERVICES (M2M)
-- =====================================================

-- Staff services (qué staff ofrece qué servicio a qué precio)
CREATE TABLE pulpo.staff_services(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  staff_id uuid NOT NULL REFERENCES pulpo.staff(id) ON DELETE CASCADE,
  service_type_id uuid NOT NULL REFERENCES pulpo.service_types(id) ON DELETE CASCADE,

  -- Precio y duración REAL por staff
  price numeric(10,2) NOT NULL,
  currency text DEFAULT 'ARS',
  duration_minutes integer NOT NULL,

  -- Configuración
  is_active boolean DEFAULT true,

  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(staff_id, service_type_id),
  CHECK (price >= 0),
  CHECK (duration_minutes > 0)
);

COMMENT ON TABLE pulpo.staff_services IS 'Servicios que ofrece cada staff con precio/duración específica';
COMMENT ON COLUMN pulpo.staff_services.price IS 'Precio REAL del servicio para este staff';
COMMENT ON COLUMN pulpo.staff_services.duration_minutes IS 'Duración REAL para este staff';

-- =====================================================
-- BUSINESS CATALOG - MENU ITEMS (Gastronomía)
-- =====================================================

-- Menu items (catálogo de platos/productos)
CREATE TABLE pulpo.menu_items(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  sku text,
  name text NOT NULL,
  description text,
  price numeric(10,2) NOT NULL,
  category text,

  -- Disponibilidad (normalizado: is_active)
  is_active boolean DEFAULT true,

  image_url text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.menu_items IS 'Catálogo de menú (gastronomía)';
COMMENT ON COLUMN pulpo.menu_items.is_active IS 'Si el item está disponible actualmente';

-- =====================================================
-- BUSINESS CATALOG - PROPERTIES (Inmobiliaria)
-- =====================================================

-- Properties (catálogo de propiedades)
CREATE TABLE pulpo.properties(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  property_id text NOT NULL, -- ID externo/código
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

  -- Disponibilidad
  is_available boolean DEFAULT true,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(workspace_id, property_id)
);

COMMENT ON TABLE pulpo.properties IS 'Catálogo de propiedades (inmobiliaria)';

-- =====================================================
-- BUSINESS HOURS & AVAILABILITY
-- =====================================================

-- Business hours (horarios del negocio)
CREATE TABLE pulpo.business_hours(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  day_of_week integer NOT NULL CHECK (day_of_week BETWEEN 0 AND 6),
  is_open boolean DEFAULT true,
  time_blocks jsonb NOT NULL DEFAULT '[]'::jsonb, -- [{"open": "09:00", "close": "13:00"}]

  notes text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(workspace_id, day_of_week)
);

COMMENT ON TABLE pulpo.business_hours IS 'Horarios de atención del negocio';
COMMENT ON COLUMN pulpo.business_hours.day_of_week IS '0=Domingo, 1=Lunes, ..., 6=Sábado';

-- Special dates (feriados, horarios especiales)
CREATE TABLE pulpo.special_dates(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  date date NOT NULL,
  type text NOT NULL CHECK (type IN ('holiday','closed','special_hours')),
  time_blocks jsonb DEFAULT '[]'::jsonb,
  name text,
  description text,
  is_recurring boolean DEFAULT false,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(workspace_id, date)
);

COMMENT ON TABLE pulpo.special_dates IS 'Feriados y fechas con horarios especiales';

-- Staff availability (ausencias, vacaciones)
CREATE TABLE pulpo.staff_availability(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  staff_id uuid NOT NULL REFERENCES pulpo.staff(id) ON DELETE CASCADE,

  type text NOT NULL CHECK (type IN ('available','vacation','sick_leave','day_off','blocked')),
  start_date date NOT NULL,
  end_date date NOT NULL,
  start_time time,
  end_time time,
  is_all_day boolean DEFAULT true,

  reason text,
  notes text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CHECK (end_date >= start_date)
);

COMMENT ON TABLE pulpo.staff_availability IS 'Disponibilidad y ausencias de staff';

-- =====================================================
-- PROMOTIONS & PACKAGES
-- =====================================================

-- Promotions (promociones y descuentos)
CREATE TABLE pulpo.promotions(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  name text NOT NULL,
  description text,
  code text,

  discount_type text NOT NULL CHECK (discount_type IN ('percentage','fixed_amount','free_service')),
  discount_value numeric(10,2),

  applies_to text NOT NULL CHECK (applies_to IN ('all','specific_services','specific_staff')),
  service_type_ids jsonb DEFAULT '[]'::jsonb,
  staff_ids jsonb DEFAULT '[]'::jsonb,

  min_amount numeric(10,2),
  max_uses integer,
  max_uses_per_customer integer DEFAULT 1,
  current_uses integer DEFAULT 0,

  valid_from date NOT NULL,
  valid_until date NOT NULL,
  valid_days_of_week jsonb DEFAULT '[0,1,2,3,4,5,6]'::jsonb,

  is_active boolean DEFAULT true,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),

  CHECK (valid_until >= valid_from),
  CHECK (current_uses >= 0)
);

COMMENT ON TABLE pulpo.promotions IS 'Promociones y descuentos';

-- Service packages (paquetes/combos)
CREATE TABLE pulpo.service_packages(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  name text NOT NULL,
  description text,
  service_type_ids jsonb NOT NULL, -- ["uuid1", "uuid2"]

  package_price numeric(10,2) NOT NULL,
  regular_price numeric(10,2),
  currency text DEFAULT 'ARS',
  total_duration_minutes integer,

  is_active boolean DEFAULT true,
  requires_same_staff boolean DEFAULT true,

  image_url text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.service_packages IS 'Paquetes/combos de servicios';

-- =====================================================
-- BUSINESS ACTIONS & RESERVATIONS
-- =====================================================

-- Action executions (tracking con idempotencia)
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

COMMENT ON TABLE pulpo.action_executions IS 'Tracking de ejecución de acciones con idempotencia';

-- Pedidos (órdenes de gastronomía)
CREATE TABLE pulpo.pedidos(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,

  items jsonb NOT NULL, -- [{"nombre": "Pizza", "cantidad": 2, "precio": 15.99}]
  metodo_entrega text CHECK (metodo_entrega IN ('retira','envio')),
  direccion text,
  total numeric(12,2),

  status text CHECK (status IN ('draft','confirmed','preparing','ready','delivered','cancelled')) DEFAULT 'draft',
  notas text,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.pedidos IS 'Pedidos de gastronomía';
COMMENT ON COLUMN pulpo.pedidos.items IS 'Array de items del pedido con precio y cantidad';

-- Reservas (turnos/appointments para servicios)
CREATE TABLE pulpo.reservas(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,

  service_type_id uuid REFERENCES pulpo.service_types(id),
  staff_id uuid REFERENCES pulpo.staff(id),

  scheduled_at timestamptz NOT NULL,
  duration_minutes integer DEFAULT 60,

  client_name text NOT NULL,
  client_email text,
  client_phone text,

  status text CHECK (status IN ('pending','confirmed','completed','cancelled','no_show')) DEFAULT 'pending',

  google_event_id text, -- ID del evento en Google Calendar
  notes text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.reservas IS 'Reservas/turnos para servicios (peluquería, spa, etc.)';

-- Visitas (visitas a propiedades inmobiliaria)
CREATE TABLE pulpo.visitas(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,

  property_id text NOT NULL,
  staff_id uuid REFERENCES pulpo.staff(id), -- Asesor asignado

  scheduled_at timestamptz NOT NULL,

  client_name text NOT NULL,
  client_email text,
  client_phone text,

  status text CHECK (status IN ('pending','confirmed','completed','cancelled','no_show')) DEFAULT 'pending',

  notes text,
  metadata jsonb DEFAULT '{}'::jsonb,

  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE pulpo.visitas IS 'Visitas agendadas a propiedades (inmobiliaria)';

-- Appointment ratings (calificaciones)
CREATE TABLE pulpo.appointment_ratings(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  reserva_id uuid REFERENCES pulpo.reservas(id) ON DELETE CASCADE,

  rating integer NOT NULL CHECK (rating BETWEEN 1 AND 5),
  comment text,

  service_quality integer CHECK (service_quality BETWEEN 1 AND 5),
  staff_friendliness integer CHECK (staff_friendliness BETWEEN 1 AND 5),
  cleanliness integer CHECK (cleanliness BETWEEN 1 AND 5),
  punctuality integer CHECK (punctuality BETWEEN 1 AND 5),

  client_name text,
  client_email text,

  metadata jsonb DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),

  UNIQUE(reserva_id)
);

COMMENT ON TABLE pulpo.appointment_ratings IS 'Calificaciones de reservas completadas';

-- =====================================================
-- OUTBOX PATTERN (Event-driven)
-- =====================================================

-- Outbox events (para N8N)
CREATE TABLE pulpo.outbox_events(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,

  event_type text NOT NULL,
  payload jsonb NOT NULL,

  status text NOT NULL CHECK (status IN ('pending','sent','failed')) DEFAULT 'pending',

  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);

COMMENT ON TABLE pulpo.outbox_events IS 'Outbox pattern para eventos asíncronos (N8N)';

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

COMMENT ON TABLE pulpo.system_metrics IS 'Métricas del sistema (Prometheus)';

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

COMMENT ON TABLE pulpo.error_logs IS 'Logs de errores para debugging';

-- =====================================================
-- INDEXES FOR PERFORMANCE
-- =====================================================

-- Core indexes
CREATE INDEX idx_workspaces_vertical ON pulpo.workspaces(vertical);
CREATE INDEX idx_workspaces_plan ON pulpo.workspaces(plan);

CREATE INDEX idx_conversations_workspace ON pulpo.conversations(workspace_id);
CREATE INDEX idx_conversations_contact ON pulpo.conversations(contact_id);
CREATE INDEX idx_conversations_status ON pulpo.conversations(workspace_id, status);

CREATE INDEX idx_messages_conversation ON pulpo.messages(conversation_id);
CREATE INDEX idx_messages_workspace ON pulpo.messages(workspace_id);
CREATE INDEX idx_messages_created_at ON pulpo.messages(created_at DESC);

-- Dialogue state indexes
CREATE INDEX idx_dialogue_states_conversation ON pulpo.dialogue_states(conversation_id);
CREATE INDEX idx_dialogue_states_workspace ON pulpo.dialogue_states(workspace_id);
CREATE INDEX idx_dialogue_state_history_conversation ON pulpo.dialogue_state_history(conversation_id);

-- RAG indexes
CREATE INDEX idx_documents_workspace ON pulpo.documents(workspace_id);
CREATE INDEX idx_document_chunks_document ON pulpo.document_chunks(document_id);
CREATE INDEX idx_document_chunks_workspace ON pulpo.document_chunks(workspace_id);
CREATE INDEX idx_document_embeddings_embedding ON pulpo.document_embeddings USING ivfflat (embedding vector_cosine_ops);

-- Staff & Services indexes
CREATE INDEX idx_staff_workspace ON pulpo.staff(workspace_id);
CREATE INDEX idx_staff_active ON pulpo.staff(workspace_id, is_active) WHERE is_active = true;

CREATE INDEX idx_service_types_workspace ON pulpo.service_types(workspace_id);
CREATE INDEX idx_service_types_active ON pulpo.service_types(workspace_id, is_active) WHERE is_active = true;

CREATE INDEX idx_staff_services_workspace ON pulpo.staff_services(workspace_id);
CREATE INDEX idx_staff_services_staff ON pulpo.staff_services(staff_id);
CREATE INDEX idx_staff_services_service ON pulpo.staff_services(service_type_id);
CREATE INDEX idx_staff_services_lookup ON pulpo.staff_services(workspace_id, service_type_id, staff_id);

-- Catalog indexes
CREATE INDEX idx_menu_items_workspace ON pulpo.menu_items(workspace_id);
CREATE INDEX idx_menu_items_active ON pulpo.menu_items(workspace_id, is_active) WHERE is_active = true;

CREATE INDEX idx_properties_workspace ON pulpo.properties(workspace_id);
CREATE INDEX idx_properties_available ON pulpo.properties(workspace_id, is_available) WHERE is_available = true;

-- Business hours indexes
CREATE INDEX idx_business_hours_workspace ON pulpo.business_hours(workspace_id);
CREATE INDEX idx_special_dates_workspace ON pulpo.special_dates(workspace_id, date);
CREATE INDEX idx_staff_availability_workspace ON pulpo.staff_availability(workspace_id);
CREATE INDEX idx_staff_availability_dates ON pulpo.staff_availability(workspace_id, start_date, end_date);

-- Reservations indexes
CREATE INDEX idx_reservas_workspace ON pulpo.reservas(workspace_id);
CREATE INDEX idx_reservas_conversation ON pulpo.reservas(conversation_id);
CREATE INDEX idx_reservas_staff ON pulpo.reservas(staff_id);
CREATE INDEX idx_reservas_scheduled ON pulpo.reservas(workspace_id, scheduled_at);
CREATE INDEX idx_reservas_status ON pulpo.reservas(workspace_id, status);

CREATE INDEX idx_visitas_workspace ON pulpo.visitas(workspace_id);
CREATE INDEX idx_visitas_conversation ON pulpo.visitas(conversation_id);
CREATE INDEX idx_visitas_scheduled ON pulpo.visitas(workspace_id, scheduled_at);

CREATE INDEX idx_pedidos_workspace ON pulpo.pedidos(workspace_id);
CREATE INDEX idx_pedidos_conversation ON pulpo.pedidos(conversation_id);
CREATE INDEX idx_pedidos_status ON pulpo.pedidos(workspace_id, status);

-- Action tracking indexes
CREATE INDEX idx_action_executions_workspace ON pulpo.action_executions(workspace_id);
CREATE INDEX idx_action_executions_conversation ON pulpo.action_executions(conversation_id);
CREATE INDEX idx_action_executions_idempotency ON pulpo.action_executions(workspace_id, idempotency_key);

-- Outbox indexes
CREATE INDEX idx_outbox_events_status ON pulpo.outbox_events(status, created_at) WHERE status = 'pending';

-- Monitoring indexes
CREATE INDEX idx_system_metrics_recorded ON pulpo.system_metrics(recorded_at DESC);
CREATE INDEX idx_error_logs_created ON pulpo.error_logs(created_at DESC);
CREATE INDEX idx_error_logs_service ON pulpo.error_logs(service_name);

-- =====================================================
-- FUNCTIONS - TIMESTAMP AUTO-UPDATE
-- =====================================================

CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION update_updated_at_column IS 'Actualiza automáticamente updated_at en UPDATE';

-- =====================================================
-- TRIGGERS - AUTO UPDATE TIMESTAMPS
-- =====================================================

CREATE TRIGGER update_workspaces_updated_at BEFORE UPDATE ON pulpo.workspaces
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_users_updated_at BEFORE UPDATE ON pulpo.users
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_channels_updated_at BEFORE UPDATE ON pulpo.channels
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_contacts_updated_at BEFORE UPDATE ON pulpo.contacts
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON pulpo.conversations
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dialogue_states_updated_at BEFORE UPDATE ON pulpo.dialogue_states
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_dialogue_slots_updated_at BEFORE UPDATE ON pulpo.dialogue_slots
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON pulpo.documents
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_staff_updated_at BEFORE UPDATE ON pulpo.staff
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_service_types_updated_at BEFORE UPDATE ON pulpo.service_types
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_menu_items_updated_at BEFORE UPDATE ON pulpo.menu_items
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_properties_updated_at BEFORE UPDATE ON pulpo.properties
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_business_hours_updated_at BEFORE UPDATE ON pulpo.business_hours
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_special_dates_updated_at BEFORE UPDATE ON pulpo.special_dates
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_staff_availability_updated_at BEFORE UPDATE ON pulpo.staff_availability
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_promotions_updated_at BEFORE UPDATE ON pulpo.promotions
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_service_packages_updated_at BEFORE UPDATE ON pulpo.service_packages
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_pedidos_updated_at BEFORE UPDATE ON pulpo.pedidos
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_reservas_updated_at BEFORE UPDATE ON pulpo.reservas
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_visitas_updated_at BEFORE UPDATE ON pulpo.visitas
  FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
