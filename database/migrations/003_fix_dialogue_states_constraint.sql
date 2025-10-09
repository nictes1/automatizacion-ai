-- =====================================================
-- Fix dialogue_states next_action constraint
-- =====================================================
-- El constraint original solo permitía: answer, tool_call, handoff, wait
-- Pero el Orchestrator usa: GREET, SLOT_FILL, RETRIEVE_CONTEXT, EXECUTE_ACTION, ANSWER, ASK_HUMAN
-- =====================================================

-- Eliminar constraint antiguo
ALTER TABLE pulpo.dialogue_states 
DROP CONSTRAINT IF EXISTS dialogue_states_next_action_check;

-- Agregar constraint nuevo con todos los valores del Orchestrator
ALTER TABLE pulpo.dialogue_states
ADD CONSTRAINT dialogue_states_next_action_check 
CHECK (next_action = ANY (ARRAY[
  -- Valores del Orchestrator (NextAction enum)
  'GREET'::text,
  'SLOT_FILL'::text, 
  'RETRIEVE_CONTEXT'::text,
  'EXECUTE_ACTION'::text,
  'ANSWER'::text,
  'ASK_HUMAN'::text,
  -- Valores legacy por compatibilidad
  'answer'::text,
  'tool_call'::text,
  'handoff'::text,
  'wait'::text
]));

COMMENT ON CONSTRAINT dialogue_states_next_action_check ON pulpo.dialogue_states IS
  'Permite todos los valores de NextAction del Orchestrator más valores legacy';
