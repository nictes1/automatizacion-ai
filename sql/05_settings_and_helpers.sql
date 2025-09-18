-- sql/05_settings_and_helpers.sql

SET search_path = public, pulpo;

-- 1) Canal con overrides de settings
ALTER TABLE pulpo.channels
  ADD COLUMN IF NOT EXISTS settings_json jsonb NOT NULL DEFAULT '{}'::jsonb;

-- 2) Helper: devuelve plan/vertical y settings mergeados (workspace || channel)
CREATE OR REPLACE FUNCTION pulpo.get_plan_vertical_settings(
  p_ws_id uuid,
  p_channel_id uuid
) RETURNS TABLE (
  ws_id uuid,
  channel_id uuid,
  plan_tier text,
  vertical text,
  biz_settings jsonb
)
LANGUAGE sql STABLE AS $$
  SELECT
    w.id       AS ws_id,
    c.id       AS channel_id,
    w.plan_tier,
    w.vertical,
    COALESCE(w.settings_json,'{}'::jsonb) || COALESCE(c.settings_json,'{}'::jsonb) AS biz_settings
  FROM pulpo.workspaces w
  JOIN pulpo.channels   c ON c.id = p_channel_id AND c.workspace_id = w.id
  WHERE w.id = p_ws_id
$$;

GRANT EXECUTE ON FUNCTION pulpo.get_plan_vertical_settings(uuid, uuid) TO pulpo;

-- Normaliza y resuelve canal por display_phone (digits only)
CREATE OR REPLACE FUNCTION pulpo.resolve_channel_by_phone(p_to_phone text)
RETURNS TABLE(channel_id uuid, ws_id uuid, display_phone text)
LANGUAGE sql STABLE SECURITY DEFINER AS $$
  WITH input AS (
    SELECT regexp_replace(p_to_phone, '\D', '', 'g') AS digits
  )
  SELECT c.id, c.workspace_id, c.display_phone
  FROM pulpo.channels c, input i
  WHERE regexp_replace(c.display_phone, '\D', '', 'g') = i.digits
  LIMIT 1
$$;

GRANT EXECUTE ON FUNCTION pulpo.resolve_channel_by_phone(text) TO pulpo;