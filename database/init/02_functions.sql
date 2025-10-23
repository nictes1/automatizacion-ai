-- =====================================================
-- PULPOAI DATABASE FUNCTIONS - CONSOLIDATED
-- =====================================================
-- Funciones PL/pgSQL consolidadas para PulpoAI
-- Incluye: RLS, Dialogue State, RAG, Actions, Monitoring
-- =====================================================

SET search_path = public, pulpo;

-- =====================================================
-- ROW LEVEL SECURITY (RLS) FUNCTIONS
-- =====================================================

-- Set workspace context for RLS
CREATE OR REPLACE FUNCTION pulpo.set_ws_context(ws_id uuid)
RETURNS void AS $$
BEGIN
  PERFORM set_config('pulpo.workspace_id', ws_id::text, true);
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Get current workspace context
CREATE OR REPLACE FUNCTION pulpo.get_ws_context()
RETURNS uuid AS $$
BEGIN
  RETURN current_setting('pulpo.workspace_id', true)::uuid;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- DIALOGUE STATE TRACKING FUNCTIONS
-- =====================================================

-- Upsert dialogue state (idempotent)
CREATE OR REPLACE FUNCTION pulpo.upsert_dialogue_state(
  ws_id uuid,
  conv_id uuid,
  fsm_state text,
  intent text DEFAULT NULL,
  slots jsonb DEFAULT '{}'::jsonb,
  next_action text DEFAULT 'answer',
  meta jsonb DEFAULT '{}'::jsonb
)
RETURNS uuid AS $$
DECLARE
  state_id uuid;
BEGIN
  -- Set workspace context
  PERFORM pulpo.set_ws_context(ws_id);
  
  -- Upsert dialogue state
  INSERT INTO pulpo.dialogue_states (
    workspace_id, conversation_id, fsm_state, intent, slots, next_action, meta
  ) VALUES (
    ws_id, conv_id, fsm_state, intent, slots, next_action, meta
  )
  ON CONFLICT (workspace_id, conversation_id) 
  DO UPDATE SET
    fsm_state = EXCLUDED.fsm_state,
    intent = EXCLUDED.intent,
    slots = EXCLUDED.slots,
    next_action = EXCLUDED.next_action,
    meta = EXCLUDED.meta,
    updated_at = now()
  RETURNING id INTO state_id;
  
  RETURN state_id;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Apply event to dialogue state (FSM transition)
CREATE OR REPLACE FUNCTION pulpo.apply_event(
  ws_id uuid,
  conv_id uuid,
  event text,
  payload jsonb DEFAULT '{}'::jsonb
)
RETURNS jsonb AS $$
DECLARE
  current_state record;
  new_fsm_state text;
  new_intent text;
  new_slots jsonb;
  new_next_action text;
  result jsonb;
BEGIN
  -- Set workspace context
  PERFORM pulpo.set_ws_context(ws_id);
  
  -- Get current state
  SELECT * INTO current_state 
  FROM pulpo.dialogue_states 
  WHERE workspace_id = ws_id AND conversation_id = conv_id;
  
  -- FSM transition logic
  CASE current_state.fsm_state
    WHEN 'START' THEN
      CASE event
        WHEN 'user_msg' THEN
          new_fsm_state := 'COLLECTING';
          new_next_action := 'answer';
        WHEN 'handoff' THEN
          new_fsm_state := 'HANDOFF';
          new_next_action := 'handoff';
        ELSE
          new_fsm_state := current_state.fsm_state;
          new_next_action := current_state.next_action;
      END CASE;
      
    WHEN 'COLLECTING' THEN
      CASE event
        WHEN 'user_msg' THEN
          new_fsm_state := 'COLLECTING';
          new_next_action := 'tool_call';
        WHEN 'tool_result' THEN
          new_fsm_state := 'CONFIRMING';
          new_next_action := 'answer';
        WHEN 'handoff' THEN
          new_fsm_state := 'HANDOFF';
          new_next_action := 'handoff';
        ELSE
          new_fsm_state := current_state.fsm_state;
          new_next_action := current_state.next_action;
      END CASE;
      
    WHEN 'CONFIRMING' THEN
      CASE event
        WHEN 'confirm_ok' THEN
          new_fsm_state := 'CHECKOUT';
          new_next_action := 'tool_call';
        WHEN 'confirm_edit' THEN
          new_fsm_state := 'COLLECTING';
          new_next_action := 'answer';
        WHEN 'abort' THEN
          new_fsm_state := 'START';
          new_next_action := 'answer';
        WHEN 'handoff' THEN
          new_fsm_state := 'HANDOFF';
          new_next_action := 'handoff';
        ELSE
          new_fsm_state := current_state.fsm_state;
          new_next_action := current_state.next_action;
      END CASE;
      
    WHEN 'CHECKOUT' THEN
      CASE event
        WHEN 'tool_result' THEN
          new_fsm_state := 'DONE';
          new_next_action := 'answer';
        WHEN 'handoff' THEN
          new_fsm_state := 'HANDOFF';
          new_next_action := 'handoff';
        ELSE
          new_fsm_state := current_state.fsm_state;
          new_next_action := current_state.next_action;
      END CASE;
      
    ELSE
      new_fsm_state := current_state.fsm_state;
      new_next_action := current_state.next_action;
  END CASE;
  
  -- Update dialogue state
  PERFORM pulpo.upsert_dialogue_state(
    ws_id, conv_id, new_fsm_state, 
    current_state.intent, current_state.slots, 
    new_next_action, current_state.meta
  );
  
  -- Log state transition
  INSERT INTO pulpo.dialogue_state_history (
    workspace_id, conversation_id, event, payload,
    previous_state, new_state
  ) VALUES (
    ws_id, conv_id, event, payload,
    to_jsonb(current_state),
    jsonb_build_object(
      'fsm_state', new_fsm_state,
      'next_action', new_next_action
    )
  );
  
  -- Return result
  result := jsonb_build_object(
    'fsm_state', new_fsm_state,
    'next_action', new_next_action,
    'event_applied', event
  );
  
  RETURN result;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- RAG FUNCTIONS
-- =====================================================

-- Search documents by similarity
CREATE OR REPLACE FUNCTION pulpo.search_documents(
  ws_id uuid,
  query_embedding vector(1536),
  similarity_threshold float DEFAULT 0.7,
  max_results integer DEFAULT 5
)
RETURNS TABLE (
  document_id uuid,
  content text,
  similarity float,
  metadata jsonb
) AS $$
BEGIN
  -- Set workspace context
  PERFORM pulpo.set_ws_context(ws_id);
  
  RETURN QUERY
  SELECT 
    dc.document_id,
    dc.content,
    1 - (dc.embedding <=> query_embedding) as similarity,
    dc.metadata
  FROM pulpo.document_chunks dc
  JOIN pulpo.documents d ON dc.document_id = d.id
  WHERE d.workspace_id = ws_id
    AND 1 - (dc.embedding <=> query_embedding) > similarity_threshold
  ORDER BY dc.embedding <=> query_embedding
  LIMIT max_results;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- ACTIONS FUNCTIONS
-- =====================================================

-- Execute business action (idempotent)
CREATE OR REPLACE FUNCTION pulpo.execute_action(
  ws_id uuid,
  conv_id uuid,
  action_type text,
  action_data jsonb,
  request_id text DEFAULT NULL
)
RETURNS jsonb AS $$
DECLARE
  action_id uuid;
  result jsonb;
BEGIN
  -- Set workspace context
  PERFORM pulpo.set_ws_context(ws_id);
  
  -- Check for existing action with same request_id
  IF request_id IS NOT NULL THEN
    SELECT id INTO action_id
    FROM pulpo.business_actions
    WHERE workspace_id = ws_id 
      AND conversation_id = conv_id
      AND action_data->>'request_id' = request_id;
    
    IF action_id IS NOT NULL THEN
      -- Return existing result
      SELECT jsonb_build_object(
        'action_id', id,
        'status', status,
        'result', result
      ) INTO result
      FROM pulpo.business_actions
      WHERE id = action_id;
      
      RETURN result;
    END IF;
  END IF;
  
  -- Create new action
  INSERT INTO pulpo.business_actions (
    workspace_id, conversation_id, action_type, action_data
  ) VALUES (
    ws_id, conv_id, action_type, action_data
  ) RETURNING id INTO action_id;
  
  -- Execute action based on type
  CASE action_type
    WHEN 'create_order' THEN
      result := pulpo._execute_create_order(ws_id, conv_id, action_data);
    WHEN 'search_menu' THEN
      result := pulpo._execute_search_menu(ws_id, action_data);
    WHEN 'book_appointment' THEN
      result := pulpo._execute_book_appointment(ws_id, conv_id, action_data);
    ELSE
      result := jsonb_build_object('error', 'Unknown action type');
  END CASE;
  
  -- Update action with result
  UPDATE pulpo.business_actions
  SET status = 'completed',
      result = result,
      updated_at = now()
  WHERE id = action_id;
  
  RETURN jsonb_build_object(
    'action_id', action_id,
    'status', 'completed',
    'result', result
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Helper function: Create order
CREATE OR REPLACE FUNCTION pulpo._execute_create_order(
  ws_id uuid,
  conv_id uuid,
  action_data jsonb
)
RETURNS jsonb AS $$
DECLARE
  order_id uuid;
  total_amount numeric;
BEGIN
  -- Calculate total
  SELECT COALESCE(SUM((item->>'price')::numeric * (item->>'quantity')::integer), 0)
  INTO total_amount
  FROM jsonb_array_elements(action_data->'items') as item;
  
  -- Create order
  INSERT INTO pulpo.orders (
    workspace_id, conversation_id, items, total, status
  ) VALUES (
    ws_id, conv_id, action_data->'items', total_amount, 'draft'
  ) RETURNING id INTO order_id;
  
  RETURN jsonb_build_object(
    'order_id', order_id,
    'total', total_amount,
    'status', 'draft'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Helper function: Search menu
CREATE OR REPLACE FUNCTION pulpo._execute_search_menu(
  ws_id uuid,
  action_data jsonb
)
RETURNS jsonb AS $$
DECLARE
  search_query text;
  menu_results jsonb;
BEGIN
  search_query := action_data->>'query';
  
  -- Mock menu search (replace with real implementation)
  menu_results := jsonb_build_array(
    jsonb_build_object(
      'name', 'Pizza Margherita',
      'price', 15.99,
      'description', 'Pizza con tomate, mozzarella y albahaca'
    ),
    jsonb_build_object(
      'name', 'Hamburguesa Clásica',
      'price', 12.50,
      'description', 'Hamburguesa con lechuga, tomate y cebolla'
    )
  );
  
  RETURN jsonb_build_object(
    'query', search_query,
    'results', menu_results,
    'count', jsonb_array_length(menu_results)
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Helper function: Book appointment
CREATE OR REPLACE FUNCTION pulpo._execute_book_appointment(
  ws_id uuid,
  conv_id uuid,
  action_data jsonb
)
RETURNS jsonb AS $$
DECLARE
  appointment_id uuid;
BEGIN
  -- Create appointment
  INSERT INTO pulpo.appointments (
    workspace_id, conversation_id, appointment_type, scheduled_at
  ) VALUES (
    ws_id, conv_id, 
    action_data->>'type',
    (action_data->>'scheduled_at')::timestamptz
  ) RETURNING id INTO appointment_id;
  
  RETURN jsonb_build_object(
    'appointment_id', appointment_id,
    'scheduled_at', action_data->>'scheduled_at',
    'status', 'scheduled'
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =====================================================
-- MONITORING FUNCTIONS
-- =====================================================

-- Record system metric
CREATE OR REPLACE FUNCTION pulpo.record_metric(
  ws_id uuid,
  metric_name text,
  metric_value numeric,
  metric_unit text DEFAULT NULL,
  tags jsonb DEFAULT '{}'::jsonb
)
RETURNS void AS $$
BEGIN
  -- Set workspace context
  PERFORM pulpo.set_ws_context(ws_id);
  
  INSERT INTO pulpo.system_metrics (
    workspace_id, metric_name, metric_value, metric_unit, tags
  ) VALUES (
    ws_id, metric_name, metric_value, metric_unit, tags
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Record error log
CREATE OR REPLACE FUNCTION pulpo.record_error(
  ws_id uuid,
  service_name text,
  error_type text,
  error_message text,
  stack_trace text DEFAULT NULL,
  context jsonb DEFAULT '{}'::jsonb
)
RETURNS void AS $$
BEGIN
  -- Set workspace context
  PERFORM pulpo.set_ws_context(ws_id);
  
  INSERT INTO pulpo.error_logs (
    workspace_id, service_name, error_type, error_message, stack_trace, context
  ) VALUES (
    ws_id, service_name, error_type, error_message, stack_trace, context
  );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;


-- =====================================================
-- GOOGLE CALENDAR HELPER FUNCTIONS
-- =====================================================

-- Función helper: Obtener calendario del negocio
CREATE OR REPLACE FUNCTION pulpo.get_business_calendar(p_workspace_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_calendar_email TEXT;
BEGIN
    SELECT business_calendar_email INTO v_calendar_email
    FROM pulpo.workspaces
    WHERE id = p_workspace_id;

    RETURN v_calendar_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
