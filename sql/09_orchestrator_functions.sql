-- sql/09_orchestrator_functions.sql
-- Funciones para Slot Manager y Policy Orchestrator

SET search_path = public, pulpo;

-- 1. Función para obtener configuración de vertical pack
CREATE OR REPLACE FUNCTION pulpo.get_vertical_pack_config(
  p_ws_id uuid,
  p_vertical text
) RETURNS TABLE (
  pack_id uuid,
  role_prompt text,
  intents_json jsonb,
  slots_config jsonb,
  tools_config jsonb,
  policies_config jsonb,
  handoff_rules jsonb,
  rag_sources jsonb
)
LANGUAGE sql STABLE AS $$
  SELECT 
    vp.id,
    vp.role_prompt,
    vp.intents_json,
    vp.slots_config,
    vp.tools_config,
    vp.policies_config,
    vp.handoff_rules,
    vp.rag_sources
  FROM pulpo.vertical_packs vp
  WHERE vp.workspace_id = p_ws_id 
    AND vp.vertical = p_vertical 
    AND vp.is_active = true
  LIMIT 1
$$;

-- 2. Función para inicializar slots de conversación
CREATE OR REPLACE FUNCTION pulpo.init_conversation_slots(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_intent text,
  p_required_slots jsonb
) RETURNS TABLE (slot_id uuid)
LANGUAGE plpgsql AS $$
DECLARE
  v_slot_id uuid;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  INSERT INTO pulpo.conversation_slots (
    workspace_id, conversation_id, intent, 
    required_slots, max_attempts, status
  )
  VALUES (
    p_ws_id, p_conversation_id, p_intent,
    p_required_slots, 3, 'collecting'
  )
  ON CONFLICT (workspace_id, conversation_id, intent)
  DO UPDATE SET
    required_slots = EXCLUDED.required_slots,
    completed_slots = '[]'::jsonb,
    current_question = NULL,
    attempts_count = 0,
    status = 'collecting',
    updated_at = now()
  RETURNING id INTO v_slot_id;
  
  RETURN QUERY SELECT v_slot_id;
END;
$$;

-- 3. Función para actualizar slots
CREATE OR REPLACE FUNCTION pulpo.update_conversation_slots(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_intent text,
  p_slot_name text,
  p_slot_value text
) RETURNS TABLE (
  slot_id uuid,
  is_complete boolean,
  next_question text,
  status text
)
LANGUAGE plpgsql AS $$
DECLARE
  v_slot_id uuid;
  v_slots_json jsonb;
  v_required_slots jsonb;
  v_completed_slots jsonb;
  v_is_complete boolean := false;
  v_next_question text;
  v_status text;
  v_required_array text[];
  v_completed_array text[];
  v_missing_slot text;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  -- Obtener el slot actual
  SELECT id, slots_json, required_slots, completed_slots, status
  INTO v_slot_id, v_slots_json, v_required_slots, v_completed_slots, v_status
  FROM pulpo.conversation_slots
  WHERE workspace_id = p_ws_id 
    AND conversation_id = p_conversation_id 
    AND intent = p_intent;
  
  IF v_slot_id IS NULL THEN
    RAISE EXCEPTION 'Slot configuration not found for intent: %', p_intent;
  END IF;
  
  -- Actualizar el valor del slot
  v_slots_json := COALESCE(v_slots_json, '{}'::jsonb) || jsonb_build_object(p_slot_name, p_slot_value);
  
  -- Agregar a completed_slots si no está ya
  v_completed_array := ARRAY(SELECT jsonb_array_elements_text(v_completed_slots));
  IF NOT (p_slot_name = ANY(v_completed_array)) THEN
    v_completed_slots := v_completed_slots || jsonb_build_array(p_slot_name);
  END IF;
  
  -- Verificar si están todos los slots requeridos
  v_required_array := ARRAY(SELECT jsonb_array_elements_text(v_required_slots));
  v_completed_array := ARRAY(SELECT jsonb_array_elements_text(v_completed_slots));
  
  -- Encontrar el próximo slot faltante
  SELECT unnest(v_required_array) 
  INTO v_missing_slot
  WHERE unnest(v_required_array) NOT IN (SELECT unnest(v_completed_array))
  LIMIT 1;
  
  IF v_missing_slot IS NULL THEN
    v_is_complete := true;
    v_status := 'completed';
    v_next_question := NULL;
  ELSE
    v_next_question := 'Por favor, proporciona: ' || v_missing_slot;
    v_status := 'collecting';
  END IF;
  
  -- Actualizar en la base de datos
  UPDATE pulpo.conversation_slots
  SET 
    slots_json = v_slots_json,
    completed_slots = v_completed_slots,
    current_question = v_next_question,
    status = v_status,
    updated_at = now()
  WHERE id = v_slot_id;
  
  RETURN QUERY SELECT v_slot_id, v_is_complete, v_next_question, v_status;
END;
$$;

-- 4. Función para obtener el próximo slot a completar
CREATE OR REPLACE FUNCTION pulpo.get_next_slot_question(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_intent text
) RETURNS TABLE (
  slot_name text,
  question text,
  is_complete boolean
)
LANGUAGE plpgsql AS $$
DECLARE
  v_required_slots jsonb;
  v_completed_slots jsonb;
  v_required_array text[];
  v_completed_array text[];
  v_missing_slot text;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  SELECT required_slots, completed_slots
  INTO v_required_slots, v_completed_slots
  FROM pulpo.conversation_slots
  WHERE workspace_id = p_ws_id 
    AND conversation_id = p_conversation_id 
    AND intent = p_intent;
  
  IF v_required_slots IS NULL THEN
    RETURN QUERY SELECT NULL::text, NULL::text, true;
    RETURN;
  END IF;
  
  v_required_array := ARRAY(SELECT jsonb_array_elements_text(v_required_slots));
  v_completed_array := ARRAY(SELECT jsonb_array_elements_text(v_completed_slots));
  
  -- Encontrar el próximo slot faltante
  SELECT unnest(v_required_array) 
  INTO v_missing_slot
  WHERE unnest(v_required_array) NOT IN (SELECT unnest(v_completed_array))
  LIMIT 1;
  
  IF v_missing_slot IS NULL THEN
    RETURN QUERY SELECT NULL::text, NULL::text, true;
  ELSE
    RETURN QUERY SELECT v_missing_slot, 'Por favor, proporciona: ' || v_missing_slot, false;
  END IF;
END;
$$;

-- 5. Función para Policy Orchestrator - inicializar estado de flujo
CREATE OR REPLACE FUNCTION pulpo.init_conversation_flow(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_initial_state text DEFAULT 'start'
) RETURNS TABLE (flow_id uuid)
LANGUAGE plpgsql AS $$
DECLARE
  v_flow_id uuid;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  INSERT INTO pulpo.conversation_flow_state (
    workspace_id, conversation_id, current_state, 
    automation_enabled, state_data
  )
  VALUES (
    p_ws_id, p_conversation_id, p_initial_state,
    true, '{}'::jsonb
  )
  ON CONFLICT (workspace_id, conversation_id)
  DO UPDATE SET
    current_state = EXCLUDED.current_state,
    previous_state = pulpo.conversation_flow_state.current_state,
    updated_at = now()
  RETURNING id INTO v_flow_id;
  
  RETURN QUERY SELECT v_flow_id;
END;
$$;

-- 6. Función para actualizar estado del flujo
CREATE OR REPLACE FUNCTION pulpo.update_conversation_flow(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_new_state text,
  p_state_data jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (
  flow_id uuid,
  previous_state text,
  current_state text
)
LANGUAGE plpgsql AS $$
DECLARE
  v_flow_id uuid;
  v_previous_state text;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  UPDATE pulpo.conversation_flow_state
  SET 
    previous_state = current_state,
    current_state = p_new_state,
    state_data = COALESCE(state_data, '{}'::jsonb) || p_state_data,
    updated_at = now()
  WHERE workspace_id = p_ws_id 
    AND conversation_id = p_conversation_id
  RETURNING id, previous_state, current_state
  INTO v_flow_id, v_previous_state, p_new_state;
  
  RETURN QUERY SELECT v_flow_id, v_previous_state, p_new_state;
END;
$$;

-- 7. Función para deshabilitar automatización (handoff)
CREATE OR REPLACE FUNCTION pulpo.disable_automation(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_reason text
) RETURNS TABLE (flow_id uuid)
LANGUAGE plpgsql AS $$
DECLARE
  v_flow_id uuid;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  UPDATE pulpo.conversation_flow_state
  SET 
    automation_enabled = false,
    handoff_reason = p_reason,
    updated_at = now()
  WHERE workspace_id = p_ws_id 
    AND conversation_id = p_conversation_id
  RETURNING id INTO v_flow_id;
  
  -- Crear evento de handoff
  INSERT INTO pulpo.handoff_events (
    workspace_id, conversation_id, trigger_reason, status
  )
  VALUES (
    p_ws_id, p_conversation_id, p_reason, 'triggered'
  );
  
  RETURN QUERY SELECT v_flow_id;
END;
$$;

-- 8. Función para registrar clasificación de intención
CREATE OR REPLACE FUNCTION pulpo.record_intent_classification(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_message_id uuid,
  p_input_text text,
  p_detected_intent text,
  p_confidence numeric,
  p_vertical text
) RETURNS TABLE (classification_id uuid)
LANGUAGE plpgsql AS $$
DECLARE
  v_classification_id uuid;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  INSERT INTO pulpo.intent_classifications (
    workspace_id, conversation_id, message_id,
    input_text, detected_intent, confidence, vertical
  )
  VALUES (
    p_ws_id, p_conversation_id, p_message_id,
    p_input_text, p_detected_intent, p_confidence, p_vertical
  )
  RETURNING id INTO v_classification_id;
  
  RETURN QUERY SELECT v_classification_id;
END;
$$;

-- 9. Función para obtener herramientas disponibles por vertical
CREATE OR REPLACE FUNCTION pulpo.get_available_tools(
  p_ws_id uuid,
  p_vertical text
) RETURNS TABLE (
  tool_name text,
  tool_config jsonb
)
LANGUAGE sql STABLE AS $$
  SELECT 
    at.tool_name,
    at.tool_config
  FROM pulpo.available_tools at
  WHERE at.workspace_id = p_ws_id 
    AND at.is_active = true
    AND (at.tool_config->>'vertical' = p_vertical OR at.tool_config->>'vertical' = 'all')
  ORDER BY at.tool_name
$$;

-- 10. Función para verificar si debe hacer handoff
CREATE OR REPLACE FUNCTION pulpo.should_handoff(
  p_ws_id uuid,
  p_conversation_id uuid,
  p_intent text,
  p_confidence numeric,
  p_slot_data jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (
  should_handoff boolean,
  reason text,
  handoff_data jsonb
)
LANGUAGE plpgsql AS $$
DECLARE
  v_handoff_rules jsonb;
  v_should_handoff boolean := false;
  v_reason text;
  v_handoff_data jsonb := '{}'::jsonb;
  v_rule jsonb;
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);
  
  -- Obtener reglas de handoff del vertical pack
  SELECT vp.handoff_rules
  INTO v_handoff_rules
  FROM pulpo.vertical_packs vp
  JOIN pulpo.conversations c ON c.workspace_id = vp.workspace_id
  WHERE c.id = p_conversation_id AND vp.is_active = true;
  
  -- Verificar reglas de handoff
  IF v_handoff_rules IS NOT NULL THEN
    -- Regla: confianza baja
    IF p_confidence < 0.7 THEN
      v_should_handoff := true;
      v_reason := 'low_confidence';
      v_handoff_data := jsonb_build_object('confidence', p_confidence);
    END IF;
    
    -- Regla: intención específica de handoff
    IF p_intent IN ('speak_to_human', 'complaint', 'escalation') THEN
      v_should_handoff := true;
      v_reason := 'customer_request';
      v_handoff_data := jsonb_build_object('intent', p_intent);
    END IF;
    
    -- Regla: monto alto (si aplica)
    IF p_slot_data ? 'amount' AND (p_slot_data->>'amount')::numeric > 100000 THEN
      v_should_handoff := true;
      v_reason := 'high_amount';
      v_handoff_data := jsonb_build_object('amount', p_slot_data->>'amount');
    END IF;
  END IF;
  
  RETURN QUERY SELECT v_should_handoff, v_reason, v_handoff_data;
END;
$$;

-- Permisos
GRANT EXECUTE ON FUNCTION pulpo.get_vertical_pack_config(uuid, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.init_conversation_slots(uuid, uuid, text, jsonb) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.update_conversation_slots(uuid, uuid, text, text, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.get_next_slot_question(uuid, uuid, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.init_conversation_flow(uuid, uuid, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.update_conversation_flow(uuid, uuid, text, jsonb) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.disable_automation(uuid, uuid, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.record_intent_classification(uuid, uuid, uuid, text, text, numeric, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.get_available_tools(uuid, text) TO pulpo;
GRANT EXECUTE ON FUNCTION pulpo.should_handoff(uuid, uuid, text, numeric, jsonb) TO pulpo;
