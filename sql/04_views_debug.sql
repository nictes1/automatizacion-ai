-- 04_views_debug.sql

CREATE OR REPLACE VIEW pulpo.v_conversations_last AS
SELECT
  c.id,
  c.workspace_id,
  c.contact_id,
  c.channel_id,
  c.status,
  c.last_message_at,
  c.last_message_text,
  c.last_message_sender,
  c.total_messages,
  c.unread_count
FROM pulpo.conversations c;

CREATE OR REPLACE VIEW pulpo.v_messages_recent AS
SELECT
  m.id,
  m.workspace_id,
  m.conversation_id,
  m.role,
  m.direction,
  m.message_type,
  m.wa_message_id,
  m.content_text,
  m.created_at
FROM pulpo.messages m
ORDER BY m.created_at DESC
LIMIT 200;

-- E. Vistas de apoyo (debug/overview)
CREATE OR REPLACE VIEW pulpo.v_conversations_overview AS
SELECT
  c.workspace_id,
  c.id AS conversation_id,
  c.contact_id,
  c.channel_id,
  c.status,
  c.last_message_at,
  c.last_message_sender,
  c.last_message_text,
  c.total_messages,
  c.unread_count
FROM pulpo.conversations c
ORDER BY c.last_message_at DESC;
