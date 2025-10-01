-- =====================================================
-- FUNCIONES PARA EL WORKFLOW DE n8n
-- =====================================================

-- 1. FUNCIÓN: persist_inbound - Persiste mensajes entrantes
CREATE OR REPLACE FUNCTION pulpo.persist_inbound(
    p_workspace_id UUID,
    p_channel_id UUID,
    p_user_phone TEXT,
    p_wamid TEXT,
    p_text TEXT
) RETURNS TABLE(conversation_id UUID, message_id UUID) AS $$
DECLARE
    v_contact_id UUID;
    v_conversation_id UUID;
    v_message_id UUID;
    v_unique_wamid TEXT;
BEGIN
    -- Buscar o crear contacto
    SELECT id INTO v_contact_id
    FROM pulpo.contacts
    WHERE workspace_id = p_workspace_id
    AND user_phone = p_user_phone;
    
    IF v_contact_id IS NULL THEN
        v_contact_id := gen_random_uuid();
        INSERT INTO pulpo.contacts (
            id, workspace_id, user_phone, created_at
        ) VALUES (
            v_contact_id, p_workspace_id, p_user_phone, NOW()
        );
    END IF;
    
    -- Buscar conversación activa
    SELECT id INTO v_conversation_id
    FROM pulpo.conversations
    WHERE workspace_id = p_workspace_id
    AND channel_id = p_channel_id
    AND contact_id = v_contact_id
    AND status = 'open'
    ORDER BY created_at DESC
    LIMIT 1;
    
    IF v_conversation_id IS NULL THEN
        v_conversation_id := gen_random_uuid();
        INSERT INTO pulpo.conversations (
            id, workspace_id, channel_id, contact_id, status, created_at
        ) VALUES (
            v_conversation_id, p_workspace_id, p_channel_id, v_contact_id, 'open', NOW()
        );
    END IF;
    
    -- Crear mensaje con ID único para wamid si es SM_FALLBACK
    v_message_id := gen_random_uuid();
    
    -- Si el wamid es SM_FALLBACK, generar uno único
    IF p_wamid = 'SM_FALLBACK' THEN
        v_unique_wamid := 'SM_FALLBACK_' || v_message_id::text;
    ELSE
        v_unique_wamid := p_wamid;
    END IF;
    
    INSERT INTO pulpo.messages (
        id, workspace_id, conversation_id, role, direction, message_type, wa_message_id, content_text, created_at
    ) VALUES (
        v_message_id, p_workspace_id, v_conversation_id, 'user', 'inbound', 'text', v_unique_wamid, p_text, NOW()
    );
    
    -- Actualizar estadísticas de la conversación
    UPDATE pulpo.conversations 
    SET 
        last_message_at = NOW(),
        last_message_text = p_text,
        last_message_sender = 'user',
        total_messages = total_messages + 1,
        unread_count = unread_count + 1
    WHERE id = v_conversation_id;
    
    RETURN QUERY SELECT v_conversation_id, v_message_id;
END;
$$ LANGUAGE plpgsql;

-- 2. FUNCIÓN: get_plan_vertical_settings - Obtiene configuración del workspace
CREATE OR REPLACE FUNCTION pulpo.get_plan_vertical_settings(
    p_workspace_id UUID,
    p_channel_id UUID
) RETURNS TABLE(ws_id UUID, vertical TEXT) AS $$
BEGIN
    RETURN QUERY
    SELECT w.id as ws_id, w.vertical
    FROM pulpo.workspaces w
    WHERE w.id = p_workspace_id;
END;
$$ LANGUAGE plpgsql;

-- 3. FUNCIÓN: get_vertical_pack_config - Obtiene configuración del vertical
CREATE OR REPLACE FUNCTION pulpo.get_vertical_pack_config(
    p_workspace_id UUID,
    p_vertical TEXT
) RETURNS TABLE(pack_config JSONB) AS $$
BEGIN
    -- Configuración básica para gastronomía
    IF p_vertical = 'gastronomia' THEN
        RETURN QUERY SELECT jsonb_build_array(
            jsonb_build_object(
                'role_prompt', 'Eres un asistente de restaurante. Ayudas a los clientes con pedidos, consultas sobre el menú y reservas.',
                'intents_json', '["pedido", "consulta_menu", "reserva", "informacion", "saludo"]',
                'slots_config', jsonb_build_object(
                    'pedido', jsonb_build_object(
                        'required', '["productos", "cantidad", "direccion"]'
                    )
                )
            )
        );
    ELSE
        -- Configuración por defecto
        RETURN QUERY SELECT jsonb_build_array(
            jsonb_build_object(
                'role_prompt', 'Eres un asistente virtual. Ayudas a los usuarios con sus consultas.',
                'intents_json', '["consulta", "informacion", "saludo"]',
                'slots_config', jsonb_build_object()
            )
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 4. FUNCIÓN: record_intent_classification - Registra clasificación de intenciones
CREATE OR REPLACE FUNCTION pulpo.record_intent_classification(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_message_id UUID,
    p_user_text TEXT,
    p_intent TEXT,
    p_confidence FLOAT,
    p_vertical TEXT
) RETURNS TABLE(classification_id UUID) AS $$
DECLARE
    v_classification_id UUID;
BEGIN
    v_classification_id := gen_random_uuid();
    
    -- Crear tabla si no existe
    CREATE TABLE IF NOT EXISTS pulpo.intent_classifications (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL,
        conversation_id UUID NOT NULL,
        message_id UUID NOT NULL,
        user_text TEXT NOT NULL,
        intent TEXT NOT NULL,
        confidence FLOAT NOT NULL,
        vertical TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    INSERT INTO pulpo.intent_classifications (
        id, workspace_id, conversation_id, message_id, user_text, intent, confidence, vertical
    ) VALUES (
        v_classification_id, p_workspace_id, p_conversation_id, p_message_id, p_user_text, p_intent, p_confidence, p_vertical
    );
    
    RETURN QUERY SELECT v_classification_id;
END;
$$ LANGUAGE plpgsql;

-- 5. FUNCIÓN: init_conversation_flow - Inicializa flujo de conversación
CREATE OR REPLACE FUNCTION pulpo.init_conversation_flow(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_status TEXT
) RETURNS TABLE(flow_id UUID) AS $$
DECLARE
    v_flow_id UUID;
BEGIN
    v_flow_id := gen_random_uuid();
    
    -- Crear tabla si no existe
    CREATE TABLE IF NOT EXISTS pulpo.conversation_flows (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL,
        conversation_id UUID NOT NULL,
        status TEXT NOT NULL,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    INSERT INTO pulpo.conversation_flows (
        id, workspace_id, conversation_id, status
    ) VALUES (
        v_flow_id, p_workspace_id, p_conversation_id, p_status
    );
    
    RETURN QUERY SELECT v_flow_id;
END;
$$ LANGUAGE plpgsql;

-- 6. FUNCIÓN: get_next_slot_question - Obtiene siguiente pregunta de slot
CREATE OR REPLACE FUNCTION pulpo.get_next_slot_question(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_intent TEXT
) RETURNS TABLE(slot_info JSONB) AS $$
BEGIN
    -- Crear tabla si no existe
    CREATE TABLE IF NOT EXISTS pulpo.conversation_slots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL,
        conversation_id UUID NOT NULL,
        intent TEXT NOT NULL,
        slot_name TEXT NOT NULL,
        slot_value TEXT,
        is_complete BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Por ahora, retornar que no hay slots pendientes
    RETURN QUERY SELECT jsonb_build_array(
        jsonb_build_object(
            'is_complete', true,
            'question', '¿En qué más puedo ayudarte?'
        )
    );
END;
$$ LANGUAGE plpgsql;

-- 7. FUNCIÓN: init_conversation_slots - Inicializa slots de conversación
CREATE OR REPLACE FUNCTION pulpo.init_conversation_slots(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_intent TEXT,
    p_required_slots JSONB
) RETURNS TABLE(slot_id UUID) AS $$
DECLARE
    v_slot_id UUID;
BEGIN
    v_slot_id := gen_random_uuid();
    
    -- Crear tabla si no existe (ya creada en función anterior)
    CREATE TABLE IF NOT EXISTS pulpo.conversation_slots (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL,
        conversation_id UUID NOT NULL,
        intent TEXT NOT NULL,
        slot_name TEXT NOT NULL,
        slot_value TEXT,
        is_complete BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    -- Por ahora, solo crear un slot básico
    INSERT INTO pulpo.conversation_slots (
        id, workspace_id, conversation_id, intent, slot_name, is_complete
    ) VALUES (
        v_slot_id, p_workspace_id, p_conversation_id, p_intent, 'basic_info', true
    );
    
    RETURN QUERY SELECT v_slot_id;
END;
$$ LANGUAGE plpgsql;

-- 8. FUNCIÓN: get_available_tools - Obtiene herramientas disponibles
CREATE OR REPLACE FUNCTION pulpo.get_available_tools(
    p_workspace_id UUID,
    p_vertical TEXT
) RETURNS TABLE(tools JSONB) AS $$
BEGIN
    -- Herramientas básicas para gastronomía
    IF p_vertical = 'gastronomia' THEN
        RETURN QUERY SELECT jsonb_build_object(
            'search_menu', 'Buscar en el menú del restaurante',
            'create_order', 'Crear un pedido',
            'check_availability', 'Verificar disponibilidad'
        );
    ELSE
        RETURN QUERY SELECT jsonb_build_object(
            'search_info', 'Buscar información',
            'contact_support', 'Contactar soporte'
        );
    END IF;
END;
$$ LANGUAGE plpgsql;

-- 9. FUNCIÓN: persist_outbound - Persiste mensajes salientes
CREATE OR REPLACE FUNCTION pulpo.persist_outbound(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_content TEXT,
    p_message_type TEXT,
    p_model TEXT,
    p_metadata JSONB
) RETURNS TABLE(message_id UUID) AS $$
DECLARE
    v_message_id UUID;
BEGIN
    v_message_id := gen_random_uuid();
    
    INSERT INTO pulpo.messages (
        id, conversation_id, content, message_type, direction, metadata, created_at
    ) VALUES (
        v_message_id, p_conversation_id, p_content, p_message_type, 'outbound', p_metadata, NOW()
    );
    
    RETURN QUERY SELECT v_message_id;
END;
$$ LANGUAGE plpgsql;

-- 10. FUNCIÓN: update_conversation_flow - Actualiza flujo de conversación
CREATE OR REPLACE FUNCTION pulpo.update_conversation_flow(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_status TEXT,
    p_metadata JSONB
) RETURNS TABLE(flow_update BOOLEAN) AS $$
BEGIN
    -- Crear tabla si no existe (ya creada en función anterior)
    CREATE TABLE IF NOT EXISTS pulpo.conversation_flows (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL,
        conversation_id UUID NOT NULL,
        status TEXT NOT NULL,
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    UPDATE pulpo.conversation_flows
    SET status = p_status, metadata = p_metadata, updated_at = NOW()
    WHERE workspace_id = p_workspace_id AND conversation_id = p_conversation_id;
    
    RETURN QUERY SELECT TRUE;
END;
$$ LANGUAGE plpgsql;

-- 11. FUNCIÓN: disable_automation - Desactiva automatización para handoff
CREATE OR REPLACE FUNCTION pulpo.disable_automation(
    p_workspace_id UUID,
    p_conversation_id UUID,
    p_reason TEXT
) RETURNS TABLE(flow_id UUID) AS $$
DECLARE
    v_flow_id UUID;
BEGIN
    v_flow_id := gen_random_uuid();
    
    -- Crear tabla si no existe (ya creada en función anterior)
    CREATE TABLE IF NOT EXISTS pulpo.conversation_flows (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        workspace_id UUID NOT NULL,
        conversation_id UUID NOT NULL,
        status TEXT NOT NULL,
        metadata JSONB,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    );
    
    INSERT INTO pulpo.conversation_flows (
        id, workspace_id, conversation_id, status, metadata
    ) VALUES (
        v_flow_id, p_workspace_id, p_conversation_id, 'handoff', 
        jsonb_build_object('reason', p_reason, 'automation_disabled', true)
    );
    
    RETURN QUERY SELECT v_flow_id;
END;
$$ LANGUAGE plpgsql;

-- =====================================================
-- CREAR TABLAS ADICIONALES NECESARIAS
-- =====================================================

-- Tabla de conversaciones si no existe
CREATE TABLE IF NOT EXISTS pulpo.conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    channel_id UUID NOT NULL,
    contact_phone TEXT NOT NULL,
    status TEXT DEFAULT 'active',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tabla de mensajes si no existe
CREATE TABLE IF NOT EXISTS pulpo.messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    message_type TEXT DEFAULT 'text',
    direction TEXT NOT NULL, -- 'inbound' o 'outbound'
    external_id TEXT,
    metadata JSONB,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Índices para mejor rendimiento
CREATE INDEX IF NOT EXISTS idx_conversations_workspace_id ON pulpo.conversations(workspace_id);
CREATE INDEX IF NOT EXISTS idx_conversations_channel_id ON pulpo.conversations(channel_id);
CREATE INDEX IF NOT EXISTS idx_conversations_contact_phone ON pulpo.conversations(contact_phone);
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON pulpo.messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON pulpo.messages(created_at);

-- RLS para las nuevas tablas
ALTER TABLE pulpo.conversations ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.messages ENABLE ROW LEVEL SECURITY;

-- Políticas RLS
DROP POLICY IF EXISTS by_workspace_conversations ON pulpo.conversations;
CREATE POLICY by_workspace_conversations ON pulpo.conversations
    USING (workspace_id = app.current_workspace());

DROP POLICY IF EXISTS by_workspace_messages ON pulpo.messages;
CREATE POLICY by_workspace_messages ON pulpo.messages
    USING (conversation_id IN (
        SELECT id FROM pulpo.conversations WHERE workspace_id = app.current_workspace()
    ));
