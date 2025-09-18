--sql/03_functions.sql

SET search_path = public, pulpo;

-- Helper: contexto de workspace (ya existe en 01, lo dejamos referenciado)
-- CREATE OR REPLACE FUNCTION pulpo.set_ws_context(ws uuid) ...

-- Inbound con dedupe por (workspace_id, wa_message_id)
DROP FUNCTION IF EXISTS pulpo.persist_inbound(uuid, uuid, text, text, text);
CREATE OR REPLACE FUNCTION pulpo.persist_inbound(
  p_ws_id uuid,
  p_channel_id uuid,
  p_user_phone text,
  p_wamid text,
  p_text text
) RETURNS TABLE (conversation_id uuid, message_id uuid)
LANGUAGE plpgsql
AS $$
DECLARE
  v_contact_id   uuid;
  v_conv_id      uuid;
  v_msg_id       uuid;
  v_affected     int := 0;
  v_phone_digits text := regexp_replace(p_user_phone, '\D', '', 'g');
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);

  INSERT INTO pulpo.contacts (workspace_id, user_phone, last_seen_at)
  VALUES (p_ws_id, v_phone_digits, now())
  ON CONFLICT (workspace_id, user_phone)
  DO UPDATE SET last_seen_at = EXCLUDED.last_seen_at
  RETURNING id INTO v_contact_id;

  SELECT c.id
    INTO v_conv_id
  FROM pulpo.conversations c
  WHERE c.workspace_id = p_ws_id
    AND c.contact_id   = v_contact_id
    AND c.status = 'open'
  ORDER BY c.created_at DESC
  LIMIT 1;

  IF v_conv_id IS NULL THEN
    INSERT INTO pulpo.conversations(
      workspace_id, contact_id, channel_id, status,
      last_message_at, last_message_text, last_message_sender,
      total_messages, unread_count
    )
    VALUES (
      p_ws_id, v_contact_id, p_channel_id, 'open',
      now(), p_text, 'user', 0, 0
    )
    RETURNING id INTO v_conv_id;
  END IF;

  INSERT INTO pulpo.messages(
    workspace_id, conversation_id, role, direction, message_type,
    wa_message_id, content_text, created_at
  )
  VALUES (
    p_ws_id, v_conv_id, 'user', 'inbound', 'text',
    p_wamid, p_text, now()
  )
  ON CONFLICT (workspace_id, wa_message_id) DO NOTHING;

  GET DIAGNOSTICS v_affected = ROW_COUNT;

  IF v_affected > 0 THEN
    SELECT m.id INTO v_msg_id
    FROM pulpo.messages m
    WHERE m.workspace_id = p_ws_id AND m.wa_message_id = p_wamid
    LIMIT 1;

    UPDATE pulpo.conversations
    SET last_message_at     = now(),
        last_message_text   = p_text,
        last_message_sender = 'user',
        total_messages      = total_messages + 1,
        unread_count        = unread_count + 1
    WHERE id = v_conv_id AND workspace_id = p_ws_id;
  ELSE
    SELECT m.id INTO v_msg_id
    FROM pulpo.messages m
    WHERE m.workspace_id = p_ws_id AND m.wa_message_id = p_wamid
    LIMIT 1;
  END IF;

  RETURN QUERY SELECT v_conv_id, v_msg_id;
END;
$$;

GRANT EXECUTE ON FUNCTION pulpo.persist_inbound(uuid, uuid, text, text, text) TO pulpo;

-- Outbound única (NO toca unread_count)
DROP FUNCTION IF EXISTS pulpo.persist_outbound(uuid, uuid, text, pulpo.message_type, text, jsonb);
CREATE OR REPLACE FUNCTION pulpo.persist_outbound(
  p_ws_id           uuid,
  p_conversation_id uuid,
  p_text            text,
  p_message_type    pulpo.message_type DEFAULT 'text',
  p_model           text DEFAULT NULL,
  p_meta            jsonb DEFAULT '{}'::jsonb
) RETURNS TABLE (message_id uuid)
LANGUAGE plpgsql
AS $$
DECLARE
  v_id uuid := gen_random_uuid();
BEGIN
  PERFORM pulpo.set_ws_context(p_ws_id);

  INSERT INTO pulpo.messages (
    id, workspace_id, conversation_id,
    role, direction, message_type,
    content_text, model, meta_json, created_at
  )
  VALUES (
    v_id, p_ws_id, p_conversation_id,
    'assistant','outbound', p_message_type,
    p_text, p_model, COALESCE(p_meta,'{}'::jsonb), now()
  );

  UPDATE pulpo.conversations
  SET last_message_at     = now(),
      last_message_text   = p_text,
      last_message_sender = 'assistant',
      total_messages      = total_messages + 1
  WHERE id = p_conversation_id AND workspace_id = p_ws_id;

  RETURN QUERY SELECT v_id;
END;
$$;

GRANT EXECUTE ON FUNCTION pulpo.persist_outbound(uuid, uuid, text, pulpo.message_type, text, jsonb) TO pulpo;