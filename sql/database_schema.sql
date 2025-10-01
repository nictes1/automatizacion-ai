-- Esquema de base de datos multitenant para sistema de slot filling
-- PulpoAI - Sistema de diálogo orientado a tareas

-- Crear esquema
CREATE SCHEMA IF NOT EXISTS pulpo;

-- Habilitar extensiones necesarias
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- Workspaces (multitenant)
CREATE TABLE pulpo.workspaces (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    name TEXT NOT NULL,
    vertical TEXT NOT NULL CHECK (vertical IN ('gastronomia','inmobiliaria','otro')),
    plan TEXT NOT NULL DEFAULT 'basic',
    rag_index TEXT,           -- nombre del índice vectorial (qdrant/pgvector)
    twilio_from TEXT NOT NULL,
    twilio_account_sid TEXT,
    twilio_auth_token TEXT,
    ollama_url TEXT DEFAULT 'http://localhost:11434',
    ollama_model TEXT DEFAULT 'llama3.1:8b',
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    is_active BOOLEAN DEFAULT true
);

-- Conversaciones
CREATE TABLE pulpo.conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    user_phone TEXT NOT NULL,
    last_message_at TIMESTAMPTZ DEFAULT now(),
    state JSONB DEFAULT '{}'::jsonb,   -- slots y progreso del FSM
    total_messages INT DEFAULT 0,
    unread_count INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, user_phone)
);

-- Mensajes
CREATE TABLE pulpo.messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    direction TEXT NOT NULL CHECK (direction IN ('inbound','outbound')),
    text TEXT NOT NULL,
    wa_message_sid TEXT,                 -- para dedupe
    intent TEXT,                         -- intención detectada
    slots_extracted JSONB,               -- slots extraídos del mensaje
    tool_calls JSONB,                    -- llamadas a herramientas
    tool_results JSONB,                  -- resultados de herramientas
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, wa_message_sid) -- dedupe inbound por Twilio SID
);

-- Pedidos gastronomía
CREATE TABLE pulpo.orders (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    items JSONB NOT NULL,   -- [{sku, name, qty, price, notes}]
    extras JSONB DEFAULT '[]'::jsonb,  -- [{sku, name, price}]
    total NUMERIC(12,2),
    metodo_entrega TEXT CHECK (metodo_entrega IN ('retiro','delivery')),
    direccion TEXT,
    metodo_pago TEXT CHECK (metodo_pago IN ('efectivo','qr','tarjeta')),
    status TEXT CHECK (status IN ('draft','confirmed','preparing','ready','delivered','cancelled')) DEFAULT 'draft',
    eta_minutes INT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Propiedades inmobiliaria (vista/materializada desde tu catálogo real)
CREATE TABLE pulpo.properties (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    operation TEXT CHECK (operation IN ('venta','alquiler')),
    type TEXT CHECK (type IN ('departamento','casa','ph','oficina','local','terreno')),
    zone TEXT,
    address TEXT,
    price NUMERIC(14,2),
    bedrooms INT,
    bathrooms INT,
    surface_m2 NUMERIC(8,2),
    description TEXT,
    features JSONB DEFAULT '{}'::jsonb,  -- características adicionales
    images JSONB DEFAULT '[]'::jsonb,    -- URLs de imágenes
    contact_phone TEXT,
    contact_email TEXT,
    is_available BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Visitas agendadas (inmobiliaria)
CREATE TABLE pulpo.visits (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    property_id UUID NOT NULL REFERENCES pulpo.properties(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    visit_datetime TIMESTAMPTZ NOT NULL,
    status TEXT CHECK (status IN ('scheduled','confirmed','completed','cancelled')) DEFAULT 'scheduled',
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);

-- Configuraciones de FSM por workspace
CREATE TABLE pulpo.fsm_configs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    vertical TEXT NOT NULL,
    config JSONB NOT NULL,  -- configuración del FSM
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(workspace_id, vertical)
);

-- Logs de herramientas (para analytics)
CREATE TABLE pulpo.tool_logs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    tool_name TEXT NOT NULL,
    input_params JSONB,
    output_result JSONB,
    execution_time_ms INT,
    success BOOLEAN,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT now()
);

-- Índices para optimización
CREATE INDEX idx_workspaces_vertical ON pulpo.workspaces(vertical);
CREATE INDEX idx_workspaces_active ON pulpo.workspaces(is_active);
CREATE INDEX idx_conversations_workspace_phone ON pulpo.conversations(workspace_id, user_phone);
CREATE INDEX idx_conversations_last_message ON pulpo.conversations(last_message_at);
CREATE INDEX idx_messages_conversation ON pulpo.messages(conversation_id);
CREATE INDEX idx_messages_workspace_created ON pulpo.messages(workspace_id, created_at);
CREATE INDEX idx_messages_wa_sid ON pulpo.messages(wa_message_sid);
CREATE INDEX idx_orders_workspace_status ON pulpo.orders(workspace_id, status);
CREATE INDEX idx_orders_conversation ON pulpo.orders(conversation_id);
CREATE INDEX idx_properties_workspace_operation ON pulpo.properties(workspace_id, operation);
CREATE INDEX idx_properties_workspace_type ON pulpo.properties(workspace_id, type);
CREATE INDEX idx_properties_workspace_zone ON pulpo.properties(workspace_id, zone);
CREATE INDEX idx_properties_price_range ON pulpo.properties(price);
CREATE INDEX idx_visits_property ON pulpo.visits(property_id);
CREATE INDEX idx_visits_datetime ON pulpo.visits(visit_datetime);
CREATE INDEX idx_tool_logs_workspace_tool ON pulpo.tool_logs(workspace_id, tool_name);
CREATE INDEX idx_tool_logs_created ON pulpo.tool_logs(created_at);

-- Row Level Security (RLS)
ALTER TABLE pulpo.workspaces ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.messages ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.visits ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.fsm_configs ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.tool_logs ENABLE ROW LEVEL SECURITY;

-- Políticas RLS
CREATE POLICY workspace_policy ON pulpo.workspaces
    USING (id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY conversation_policy ON pulpo.conversations
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY message_policy ON pulpo.messages
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY order_policy ON pulpo.orders
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY property_policy ON pulpo.properties
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY visit_policy ON pulpo.visits
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY fsm_config_policy ON pulpo.fsm_configs
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

CREATE POLICY tool_log_policy ON pulpo.tool_logs
    USING (workspace_id = current_setting('pulpo.workspace_id')::uuid);

-- Funciones de utilidad
CREATE OR REPLACE FUNCTION pulpo.set_workspace_id(workspace_uuid UUID)
RETURNS void AS $$
BEGIN
    PERFORM set_config('pulpo.workspace_id', workspace_uuid::text, true);
END;
$$ LANGUAGE plpgsql;

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION pulpo.update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
CREATE TRIGGER update_workspaces_updated_at BEFORE UPDATE ON pulpo.workspaces
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();

CREATE TRIGGER update_conversations_updated_at BEFORE UPDATE ON pulpo.conversations
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();

CREATE TRIGGER update_orders_updated_at BEFORE UPDATE ON pulpo.orders
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();

CREATE TRIGGER update_properties_updated_at BEFORE UPDATE ON pulpo.properties
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();

CREATE TRIGGER update_visits_updated_at BEFORE UPDATE ON pulpo.visits
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();

CREATE TRIGGER update_fsm_configs_updated_at BEFORE UPDATE ON pulpo.fsm_configs
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_updated_at_column();

-- Vistas útiles
CREATE VIEW pulpo.conversation_summary AS
SELECT 
    c.id,
    c.workspace_id,
    c.user_phone,
    c.last_message_at,
    c.total_messages,
    c.unread_count,
    w.name as workspace_name,
    w.vertical,
    c.state->>'current_state' as current_fsm_state,
    CASE 
        WHEN c.state->>'slots' IS NOT NULL THEN 
            jsonb_object_agg(
                key, 
                CASE WHEN value->>'filled' = 'true' THEN value->>'value' ELSE NULL END
            )
        ELSE '{}'::jsonb
    END as filled_slots
FROM pulpo.conversations c
JOIN pulpo.workspaces w ON c.workspace_id = w.id
LEFT JOIN jsonb_each(c.state->'slots') ON true
GROUP BY c.id, c.workspace_id, c.user_phone, c.last_message_at, 
         c.total_messages, c.unread_count, w.name, w.vertical, c.state;

-- Vista para analytics de herramientas
CREATE VIEW pulpo.tool_analytics AS
SELECT 
    workspace_id,
    tool_name,
    DATE(created_at) as date,
    COUNT(*) as total_calls,
    COUNT(*) FILTER (WHERE success = true) as successful_calls,
    COUNT(*) FILTER (WHERE success = false) as failed_calls,
    AVG(execution_time_ms) as avg_execution_time_ms,
    MAX(execution_time_ms) as max_execution_time_ms
FROM pulpo.tool_logs
GROUP BY workspace_id, tool_name, DATE(created_at);

-- Datos de ejemplo para testing
INSERT INTO pulpo.workspaces (id, name, vertical, plan, rag_index, twilio_from) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'La Nonna', 'gastronomia', 'premium', 'la-nonna-menu', '+5491123456789'),
    ('550e8400-e29b-41d4-a716-446655440001', 'Inmobiliaria Central', 'inmobiliaria', 'basic', 'central-properties', '+5491123456790');

-- Configuración FSM para gastronomía
INSERT INTO pulpo.fsm_configs (workspace_id, vertical, config) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'gastronomia', '{
        "states": {
            "START": {"description": "Estado inicial", "next_states": ["PEDIR_CATEGORIA", "ARMAR_ITEMS", "MOSTRAR_MENU"]},
            "PEDIR_CATEGORIA": {"description": "Solicitar categoría", "question": "¿De qué categoría querés pedir?", "slot": "categoria", "next_state": "ARMAR_ITEMS"},
            "ARMAR_ITEMS": {"description": "Armar items", "question": "Decime cantidad y sabor", "slot": "items", "tool": "search_menu", "next_state": "UPSELL"},
            "UPSELL": {"description": "Sugerir extras", "question": "¿Querés agregar bebida o postre?", "slot": "extras", "tool": "suggest_upsell", "next_state": "ENTREGA"},
            "ENTREGA": {"description": "Método de entrega", "question": "¿Retirás o delivery?", "slot": "metodo_entrega", "next_state": "DIRECCION_OR_PAGO"},
            "PAGO": {"description": "Método de pago", "question": "¿Cómo pagás?", "slot": "metodo_pago", "tool": "create_order", "next_state": "CONFIRMAR"},
            "CONFIRMAR": {"description": "Confirmar pedido", "end": true}
        },
        "slots": {
            "categoria": {"required": true, "type": "string"},
            "items": {"required": true, "type": "array"},
            "extras": {"required": false, "type": "array"},
            "metodo_entrega": {"required": true, "type": "string", "options": ["retiro", "delivery"]},
            "direccion": {"required": false, "type": "string"},
            "metodo_pago": {"required": true, "type": "string", "options": ["efectivo", "qr", "tarjeta"]}
        }
    }'::jsonb);

-- Comentarios de documentación
COMMENT ON SCHEMA pulpo IS 'Esquema principal del sistema PulpoAI - Diálogo orientado a tareas con slot filling';
COMMENT ON TABLE pulpo.workspaces IS 'Configuración de workspaces multitenant';
COMMENT ON TABLE pulpo.conversations IS 'Conversaciones con estado de slots y FSM';
COMMENT ON TABLE pulpo.messages IS 'Mensajes individuales con metadatos de procesamiento';
COMMENT ON TABLE pulpo.orders IS 'Pedidos de gastronomía';
COMMENT ON TABLE pulpo.properties IS 'Propiedades inmobiliarias';
COMMENT ON TABLE pulpo.visits IS 'Visitas agendadas para inmobiliaria';
COMMENT ON TABLE pulpo.fsm_configs IS 'Configuraciones de máquinas de estado por workspace';
COMMENT ON TABLE pulpo.tool_logs IS 'Logs de herramientas para analytics';
