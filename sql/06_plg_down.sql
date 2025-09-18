-- sql/06_plg_down.sql
SET search_path = public, pulpo;
DROP FUNCTION IF EXISTS pulpo.inc_plan_metric(uuid, date, text, int);
DROP TABLE IF EXISTS pulpo.email_outbox;
DROP TABLE IF EXISTS pulpo.plan_opportunities_daily;
DROP TABLE IF EXISTS pulpo.intent_events;