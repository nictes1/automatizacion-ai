-- Migración 005: Sistema de Memoria Conversacional
-- Implementa las 3 capas de memoria según CONVERSATIONAL_MEMORY_ARCHITECTURE.md

-- Capa 2: Short-Term Memory - Resúmenes de conversaciones del día/semana
CREATE TABLE IF NOT EXISTS pulpo.conversation_summaries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id VARCHAR(255) NOT NULL,
    client_phone VARCHAR(50) NOT NULL,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id),
    summary_text TEXT NOT NULL,
    key_facts JSONB NOT NULL DEFAULT '{}',
    last_interaction TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    interaction_count INTEGER NOT NULL DEFAULT 1,
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Índices para performance
    UNIQUE (client_phone, workspace_id),
    INDEX idx_conversation_summaries_client_workspace (client_phone, workspace_id),
    INDEX idx_conversation_summaries_last_interaction (last_interaction),
    INDEX idx_conversation_summaries_workspace (workspace_id)
);

-- Capa 3: Long-Term Memory - Perfiles completos de clientes
CREATE TABLE IF NOT EXISTS pulpo.client_profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    client_phone VARCHAR(50) NOT NULL,
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id),
    name VARCHAR(255),
    email VARCHAR(255),
    preferences JSONB NOT NULL DEFAULT '{}',
    interaction_history JSONB NOT NULL DEFAULT '{"total_interactions": 0}',
    lead_score INTEGER NOT NULL DEFAULT 0 CHECK (lead_score >= 0 AND lead_score <= 100),
    tags JSONB NOT NULL DEFAULT '[]',
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),
    
    -- Constraints
    UNIQUE (client_phone, workspace_id),
    CHECK (email IS NULL OR email ~* '^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$'),
    
    -- Índices para performance
    INDEX idx_client_profiles_client_workspace (client_phone, workspace_id),
    INDEX idx_client_profiles_workspace (workspace_id),
    INDEX idx_client_profiles_lead_score (lead_score),
    INDEX idx_client_profiles_updated_at (updated_at)
);

-- Comentarios para documentación
COMMENT ON TABLE pulpo.conversation_summaries IS 'Capa 2: Short-Term Memory - Resúmenes de conversaciones recientes del mismo cliente (TTL: 24h Redis + permanente PostgreSQL)';
COMMENT ON TABLE pulpo.client_profiles IS 'Capa 3: Long-Term Memory - Perfiles completos de clientes recurrentes (>3 interacciones)';

COMMENT ON COLUMN pulpo.conversation_summaries.client_phone IS 'Teléfono del cliente (identificador único por workspace)';
COMMENT ON COLUMN pulpo.conversation_summaries.summary_text IS 'Resumen conciso de las conversaciones recientes (máx 200 chars)';
COMMENT ON COLUMN pulpo.conversation_summaries.key_facts IS 'Hechos clave extraídos: service_type, preferred_date, etc.';
COMMENT ON COLUMN pulpo.conversation_summaries.interaction_count IS 'Número total de interacciones del cliente';

COMMENT ON COLUMN pulpo.client_profiles.preferences IS 'Preferencias del cliente: servicios favoritos, horarios, etc.';
COMMENT ON COLUMN pulpo.client_profiles.interaction_history IS 'Estadísticas de interacciones: total_interactions, last_service, etc.';
COMMENT ON COLUMN pulpo.client_profiles.lead_score IS 'Puntuación de lead (0-100) para priorización de ventas';
COMMENT ON COLUMN pulpo.client_profiles.tags IS 'Etiquetas de negocio: ["vip", "frequent", "high_value"]';

-- Función para auto-actualizar updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Triggers para auto-actualizar updated_at
CREATE TRIGGER update_conversation_summaries_updated_at 
    BEFORE UPDATE ON pulpo.conversation_summaries 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_client_profiles_updated_at 
    BEFORE UPDATE ON pulpo.client_profiles 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Datos de ejemplo para testing (opcional)
INSERT INTO pulpo.conversation_summaries 
(conversation_id, client_phone, workspace_id, summary_text, key_facts, interaction_count)
VALUES 
('test-conv-001', '+5491123456789', '550e8400-e29b-41d4-a716-446655440003', 
 'Cliente Juan solicitó corte de cabello para mañana 10am. Turno confirmado.', 
 '{"service_type": "Corte de Cabello", "client_name": "Juan", "preferred_time": "10:00"}', 1)
ON CONFLICT (client_phone, workspace_id) DO NOTHING;

INSERT INTO pulpo.client_profiles 
(client_phone, workspace_id, name, email, preferences, interaction_history, lead_score, tags)
VALUES 
('+5491123456789', '550e8400-e29b-41d4-a716-446655440003', 'Juan Pérez', 'juan@email.com',
 '{"preferred_service": "Corte de Cabello", "preferred_time": "10:00"}',
 '{"total_interactions": 5, "last_service": "Corte de Cabello"}', 75, '["frequent", "punctual"]')
ON CONFLICT (client_phone, workspace_id) DO NOTHING;

