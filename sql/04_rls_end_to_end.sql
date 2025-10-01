-- RLS End-to-End para Actions Service
-- Aplica Row Level Security a todas las tablas multitenant

-- Función helper para obtener workspace_id actual
CREATE OR REPLACE FUNCTION get_current_workspace_id() 
RETURNS TEXT AS $$
BEGIN
    RETURN current_setting('app.workspace_id', true);
END;
$$ LANGUAGE plpgsql;

-- Habilitar RLS en action_executions
ALTER TABLE pulpo.action_executions ENABLE ROW LEVEL SECURITY;

CREATE POLICY action_executions_workspace_policy ON pulpo.action_executions
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en event_outbox
ALTER TABLE pulpo.event_outbox ENABLE ROW LEVEL SECURITY;

CREATE POLICY event_outbox_workspace_policy ON pulpo.event_outbox
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en menu_items
ALTER TABLE pulpo.menu_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY menu_items_workspace_policy ON pulpo.menu_items
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en pedidos
ALTER TABLE pulpo.pedidos ENABLE ROW LEVEL SECURITY;

CREATE POLICY pedidos_workspace_policy ON pulpo.pedidos
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en properties
ALTER TABLE pulpo.properties ENABLE ROW LEVEL SECURITY;

CREATE POLICY properties_workspace_policy ON pulpo.properties
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en services_catalog
ALTER TABLE pulpo.services_catalog ENABLE ROW LEVEL SECURITY;

CREATE POLICY services_catalog_workspace_policy ON pulpo.services_catalog
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en visitas
ALTER TABLE pulpo.visitas ENABLE ROW LEVEL SECURITY;

CREATE POLICY visitas_workspace_policy ON pulpo.visitas
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en reservas
ALTER TABLE pulpo.reservas ENABLE ROW LEVEL SECURITY;

CREATE POLICY reservas_workspace_policy ON pulpo.reservas
  FOR ALL TO authenticated
  USING (workspace_id = get_current_workspace_id());

-- Habilitar RLS en action_audit_log (si existe)
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'action_audit_log' AND table_schema = 'pulpo') THEN
        ALTER TABLE pulpo.action_audit_log ENABLE ROW LEVEL SECURITY;
        
        CREATE POLICY action_audit_log_workspace_policy ON pulpo.action_audit_log
          FOR ALL TO authenticated
          USING (workspace_id = get_current_workspace_id());
    END IF;
END $$;

-- Comentarios para documentación
COMMENT ON FUNCTION get_current_workspace_id() IS 'Obtiene el workspace_id actual de la sesión para RLS';
COMMENT ON POLICY action_executions_workspace_policy ON pulpo.action_executions IS 'RLS: Solo acceso a action_executions del workspace actual';
COMMENT ON POLICY event_outbox_workspace_policy ON pulpo.event_outbox IS 'RLS: Solo acceso a event_outbox del workspace actual';
COMMENT ON POLICY menu_items_workspace_policy ON pulpo.menu_items IS 'RLS: Solo acceso a menu_items del workspace actual';
COMMENT ON POLICY pedidos_workspace_policy ON pulpo.pedidos IS 'RLS: Solo acceso a pedidos del workspace actual';
COMMENT ON POLICY properties_workspace_policy ON pulpo.properties IS 'RLS: Solo acceso a properties del workspace actual';
COMMENT ON POLICY services_catalog_workspace_policy ON pulpo.services_catalog IS 'RLS: Solo acceso a services_catalog del workspace actual';
COMMENT ON POLICY visitas_workspace_policy ON pulpo.visitas IS 'RLS: Solo acceso a visitas del workspace actual';
COMMENT ON POLICY reservas_workspace_policy ON pulpo.reservas IS 'RLS: Solo acceso a reservas del workspace actual';
