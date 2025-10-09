-- =====================================================
-- Funciones SQL para n8n Workflow
-- =====================================================
-- Estas funciones son llamadas por el workflow de n8n
-- para persistir mensajes y cargar/guardar estado conversacional.
-- =====================================================

-- 1. persist_inbound: Guarda mensaje entrante de Twilio
-- Parámetros: workspace_id, channel_id, user_phone, wamid (message ID), text
-- Retorna: JSON con {conversation_id, message_id}
CREATE OR REPLACE FUNCTION pulpo.persist_inbound(
  p_workspace_id uuid,
  p_channel_id uuid,
  p_user_phone text,
  p_wamid text,
  p_text text
) RETURNS jsonb AS $$
DECLARE
  v_contact_id uuid;
  v_conversation_id uuid;
  v_message_id uuid;
BEGIN
  -- 1. Encontrar o crear contacto por teléfono
  SELECT id INTO v_contact_id
  FROM pulpo.contacts
  WHERE workspace_id = p_workspace_id
    AND channel_id = p_channel_id
    AND phone = p_user_phone
  LIMIT 1;

  IF v_contact_id IS NULL THEN
    -- Crear nuevo contacto
    INSERT INTO pulpo.contacts (workspace_id, channel_id, external_id, phone, name)
    VALUES (p_workspace_id, p_channel_id, p_user_phone, p_user_phone, 'Cliente')
    RETURNING id INTO v_contact_id;
  END IF;

  -- 2. Encontrar o crear conversación activa
  SELECT id INTO v_conversation_id
  FROM pulpo.conversations
  WHERE workspace_id = p_workspace_id
    AND contact_id = v_contact_id
    AND status = 'active'
  ORDER BY updated_at DESC
  LIMIT 1;

  IF v_conversation_id IS NULL THEN
    -- Crear nueva conversación
    INSERT INTO pulpo.conversations (workspace_id, channel_id, contact_id, status)
    VALUES (p_workspace_id, p_channel_id, v_contact_id, 'active')
    RETURNING id INTO v_conversation_id;
  END IF;

  -- 3. Insertar mensaje entrante
  INSERT INTO pulpo.messages (
    workspace_id,
    conversation_id,
    sender,
    content,
    message_type,
    metadata
  ) VALUES (
    p_workspace_id,
    v_conversation_id,
    'user',
    p_text,
    'text',
    jsonb_build_object('wamid', p_wamid, 'phone', p_user_phone)
  ) RETURNING id INTO v_message_id;

  -- 4. Retornar IDs como JSON
  RETURN jsonb_build_object(
    'conversation_id', v_conversation_id,
    'message_id', v_message_id,
    'contact_id', v_contact_id
  );
END;
$$ LANGUAGE plpgsql;


-- 2. load_state: Carga el estado conversacional de una conversación
-- Parámetros: workspace_id, conversation_id
-- Retorna: JSON con {greeted, slots, objective, last_action, attempts_count}
CREATE OR REPLACE FUNCTION pulpo.load_state(
  p_workspace_id uuid,
  p_conversation_id uuid
) RETURNS jsonb AS $$
DECLARE
  v_state jsonb;
BEGIN
  -- Cargar estado desde dialogue_states
  SELECT jsonb_build_object(
    'greeted', COALESCE((slots->>'greeted')::boolean, false),
    'slots', COALESCE(slots, '{}'::jsonb),
    'objective', COALESCE(meta->>'objective', ''),
    'last_action', next_action,
    'attempts_count', COALESCE((meta->>'attempts_count')::int, 0)
  )
  INTO v_state
  FROM pulpo.dialogue_states
  WHERE workspace_id = p_workspace_id
    AND conversation_id = p_conversation_id;

  -- Si no hay estado, retornar estado inicial
  IF v_state IS NULL THEN
    v_state := jsonb_build_object(
      'greeted', false,
      'slots', '{}'::jsonb,
      'objective', '',
      'last_action', null,
      'attempts_count', 0
    );
  END IF;

  RETURN v_state;
END;
$$ LANGUAGE plpgsql;


-- 3. persist_outbound: Guarda mensaje saliente (respuesta del bot)
-- Parámetros: workspace_id, conversation_id, message_text, message_type, message_source, metadata
-- Retorna: message_id (uuid)
CREATE OR REPLACE FUNCTION pulpo.persist_outbound(
  p_workspace_id uuid,
  p_conversation_id uuid,
  p_message_text text,
  p_message_type text DEFAULT 'text',
  p_message_source text DEFAULT 'assistant',
  p_metadata jsonb DEFAULT '{}'::jsonb
) RETURNS uuid AS $$
DECLARE
  v_message_id uuid;
  v_slots jsonb;
  v_objective text;
  v_last_action text;
BEGIN
  -- 1. Insertar mensaje saliente
  INSERT INTO pulpo.messages (
    workspace_id,
    conversation_id,
    sender,
    content,
    message_type,
    metadata
  ) VALUES (
    p_workspace_id,
    p_conversation_id,
    'assistant',
    p_message_text,
    p_message_type,
    p_metadata
  ) RETURNING id INTO v_message_id;

  -- 2. Actualizar dialogue_states si hay metadata de estado
  IF p_metadata ? 'slots' OR p_metadata ? 'objective' OR p_metadata ? 'last_action' THEN
    v_slots := COALESCE(p_metadata->'slots', '{}'::jsonb);
    v_objective := COALESCE(p_metadata->>'objective', '');
    v_last_action := COALESCE(p_metadata->>'last_action', 'answer');

    INSERT INTO pulpo.dialogue_states (
      workspace_id,
      conversation_id,
      fsm_state,
      intent,
      slots,
      next_action,
      meta
    ) VALUES (
      p_workspace_id,
      p_conversation_id,
      'active',
      COALESCE(p_metadata->>'intent', 'chat'),
      v_slots,
      v_last_action,
      jsonb_build_object(
        'objective', v_objective,
        'attempts_count', COALESCE((p_metadata->>'attempts_count')::int, 0)
      )
    )
    ON CONFLICT (workspace_id, conversation_id)
    DO UPDATE SET
      slots = v_slots,
      next_action = v_last_action,
      meta = jsonb_build_object(
        'objective', v_objective,
        'attempts_count', COALESCE((p_metadata->>'attempts_count')::int, 0)
      ),
      updated_at = now();
  END IF;

  -- 3. Retornar message_id
  RETURN v_message_id;
END;
$$ LANGUAGE plpgsql;


-- Comentarios de documentación
COMMENT ON FUNCTION pulpo.persist_inbound IS
  'Guarda mensaje entrante de Twilio WhatsApp. Crea contacto y conversación si no existen.';

COMMENT ON FUNCTION pulpo.load_state IS
  'Carga el estado conversacional completo (greeted, slots, objetivo, etc.) para una conversación.';

COMMENT ON FUNCTION pulpo.persist_outbound IS
  'Guarda mensaje saliente del bot y actualiza dialogue_states con metadata de estado.';
