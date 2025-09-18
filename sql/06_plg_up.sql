-- sql/06_plg_up.sql
SET search_path = public, pulpo;
CREATE TABLE IF NOT EXISTS pulpo.intent_events(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  conversation_id uuid REFERENCES pulpo.conversations(id) ON DELETE SET NULL,
  message_id uuid REFERENCES pulpo.messages(id) ON DELETE SET NULL,
  intent text NOT NULL,
  confidence numeric(3,2) NOT NULL,
  required_capability text,
  blocked_by_plan boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ie_ws_time ON pulpo.intent_events(workspace_id, created_at);
CREATE INDEX IF NOT EXISTS idx_ie_ws_block ON pulpo.intent_events(workspace_id, blocked_by_plan, created_at);

CREATE TABLE IF NOT EXISTS pulpo.plan_opportunities_daily(
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  day date NOT NULL,
  metric_key text NOT NULL,
  metric_value bigint NOT NULL DEFAULT 0,
  PRIMARY KEY(workspace_id, day, metric_key)
);

CREATE TABLE IF NOT EXISTS pulpo.email_outbox(
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  workspace_id uuid NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
  to_email citext NOT NULL,
  subject text NOT NULL,
  body_json jsonb NOT NULL,
  status text NOT NULL CHECK (status IN ('pending','sent','failed')) DEFAULT 'pending',
  created_at timestamptz NOT NULL DEFAULT now(),
  sent_at timestamptz
);

CREATE OR REPLACE FUNCTION pulpo.inc_plan_metric(p_ws uuid, p_day date, p_key text, p_inc int)
RETURNS void LANGUAGE sql AS $$
  INSERT INTO pulpo.plan_opportunities_daily(workspace_id, day, metric_key, metric_value)
  VALUES (p_ws, p_day, p_key, p_inc)
  ON CONFLICT(workspace_id, day, metric_key)
  DO UPDATE SET metric_value = plan_opportunities_daily.metric_value + EXCLUDED.metric_value;
$$;

ALTER TABLE pulpo.intent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.plan_opportunities_daily ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.email_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY ws_isolation_intent_events ON pulpo.intent_events
USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);

CREATE POLICY ws_isolation_plan_opportunities_daily ON pulpo.plan_opportunities_daily
USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);

CREATE POLICY ws_isolation_email_outbox ON pulpo.email_outbox
USING (workspace_id = current_setting('app.workspace_id', true)::uuid)
WITH CHECK (workspace_id = current_setting('app.workspace_id', true)::uuid);