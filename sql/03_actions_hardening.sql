-- Mejoras de hardening para el Actions Service
-- Ejecutar después de 02_actions_improvements.sql

-- 1. Índices únicos funcionales para case-insensitive
-- Evita duplicados como "Empanada" + "empanada"

-- Para menu_items
DROP INDEX IF EXISTS pulpo.idx_menu_items_nombre;
CREATE UNIQUE INDEX idx_menu_items_nombre_lower 
ON pulpo.menu_items (workspace_id, LOWER(nombre));

-- Para properties (si no existe)
CREATE UNIQUE INDEX IF NOT EXISTS idx_properties_property_id_lower 
ON pulpo.properties (workspace_id, LOWER(property_id));

-- Para services_catalog (si no existe)
CREATE UNIQUE INDEX IF NOT EXISTS idx_services_catalog_service_type_lower 
ON pulpo.services_catalog (workspace_id, LOWER(service_type));

-- 2. Statement timeout por sesión
-- Evita cuelgues de DB en queries largas
CREATE OR REPLACE FUNCTION set_statement_timeout()
RETURNS void AS $$
BEGIN
    EXECUTE 'SET LOCAL statement_timeout = ''2s''';
END;
$$ LANGUAGE plpgsql;

-- 3. Función para establecer workspace_id en contexto
-- Mejora la función existente para ser más robusta
CREATE OR REPLACE FUNCTION get_current_workspace_id()
RETURNS UUID AS $$
DECLARE
    ws_id UUID;
BEGIN
    -- Intentar obtener del contexto de sesión
    BEGIN
        ws_id := current_setting('app.workspace_id', true)::UUID;
        IF ws_id IS NOT NULL THEN
            RETURN ws_id;
        END IF;
    EXCEPTION WHEN OTHERS THEN
        -- Si falla, continuar con otras opciones
    END;
    
    -- Fallback: workspace por defecto (para testing)
    RETURN '00000000-0000-0000-0000-000000000000'::UUID;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 4. Triggers para auditoría
-- Tabla de auditoría para cambios importantes
CREATE TABLE IF NOT EXISTS pulpo.action_audit_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    action_execution_id UUID NOT NULL,
    event_type TEXT NOT NULL, -- 'created', 'updated', 'completed', 'failed'
    old_status TEXT,
    new_status TEXT,
    details JSONB,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    created_by TEXT DEFAULT 'system'
);

-- Índices para auditoría
CREATE INDEX IF NOT EXISTS idx_action_audit_log_workspace_id ON pulpo.action_audit_log(workspace_id);
CREATE INDEX IF NOT EXISTS idx_action_audit_log_action_execution_id ON pulpo.action_audit_log(action_execution_id);
CREATE INDEX IF NOT EXISTS idx_action_audit_log_created_at ON pulpo.action_audit_log(created_at);

-- RLS para auditoría
ALTER TABLE pulpo.action_audit_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY action_audit_log_workspace_policy ON pulpo.action_audit_log
    FOR ALL TO authenticated
    USING (workspace_id = get_current_workspace_id());

-- 5. Función para log de auditoría
CREATE OR REPLACE FUNCTION log_action_audit(
    p_action_execution_id UUID,
    p_event_type TEXT,
    p_old_status TEXT DEFAULT NULL,
    p_new_status TEXT DEFAULT NULL,
    p_details JSONB DEFAULT NULL
)
RETURNS void AS $$
BEGIN
    INSERT INTO pulpo.action_audit_log (
        workspace_id, action_execution_id, event_type, 
        old_status, new_status, details
    ) VALUES (
        get_current_workspace_id(), p_action_execution_id, p_event_type,
        p_old_status, p_new_status, p_details
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 6. Triggers automáticos para auditoría
CREATE OR REPLACE FUNCTION trigger_action_audit()
RETURNS TRIGGER AS $$
BEGIN
    -- Log cuando se crea una acción
    IF TG_OP = 'INSERT' THEN
        PERFORM log_action_audit(
            NEW.id, 'created', NULL, NEW.status, 
            jsonb_build_object('action_name', NEW.action_name, 'conversation_id', NEW.conversation_id)
        );
        RETURN NEW;
    END IF;
    
    -- Log cuando se actualiza una acción
    IF TG_OP = 'UPDATE' THEN
        IF OLD.status != NEW.status THEN
            PERFORM log_action_audit(
                NEW.id, 'status_changed', OLD.status, NEW.status,
                jsonb_build_object('action_name', NEW.action_name)
            );
        END IF;
        
        IF NEW.completed_at IS NOT NULL AND OLD.completed_at IS NULL THEN
            PERFORM log_action_audit(
                NEW.id, 'completed', OLD.status, NEW.status,
                jsonb_build_object('action_name', NEW.action_name, 'completed_at', NEW.completed_at)
            );
        END IF;
        
        RETURN NEW;
    END IF;
    
    RETURN NULL;
END;
$$ LANGUAGE plpgsql;

-- Aplicar trigger a action_executions
DROP TRIGGER IF EXISTS action_executions_audit_trigger ON pulpo.action_executions;
CREATE TRIGGER action_executions_audit_trigger
    AFTER INSERT OR UPDATE ON pulpo.action_executions
    FOR EACH ROW
    EXECUTE FUNCTION trigger_action_audit();

-- 7. Vista para métricas de acciones
CREATE OR REPLACE VIEW pulpo.action_metrics AS
SELECT 
    workspace_id,
    action_name,
    status,
    COUNT(*) as count,
    AVG(EXTRACT(EPOCH FROM (completed_at - created_at))) as avg_duration_seconds,
    MIN(created_at) as first_created,
    MAX(created_at) as last_created
FROM pulpo.action_executions
WHERE created_at >= NOW() - INTERVAL '24 hours'
GROUP BY workspace_id, action_name, status;

-- 8. Función para limpiar datos antiguos
CREATE OR REPLACE FUNCTION cleanup_old_actions()
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    -- Limpiar acciones completadas hace más de 30 días
    DELETE FROM pulpo.action_executions 
    WHERE status IN ('success', 'failed', 'cancelled') 
    AND completed_at < NOW() - INTERVAL '30 days';
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    
    -- Limpiar eventos de outbox enviados hace más de 7 días
    DELETE FROM pulpo.event_outbox 
    WHERE status = 'sent' 
    AND sent_at < NOW() - INTERVAL '7 days';
    
    -- Limpiar logs de auditoría hace más de 90 días
    DELETE FROM pulpo.action_audit_log 
    WHERE created_at < NOW() - INTERVAL '90 days';
    
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql;

-- 9. Comentarios para documentación
COMMENT ON TABLE pulpo.action_audit_log IS 'Log de auditoría para cambios en acciones';
COMMENT ON FUNCTION get_current_workspace_id() IS 'Obtiene el workspace_id del contexto actual';
COMMENT ON FUNCTION log_action_audit(UUID, TEXT, TEXT, TEXT, JSONB) IS 'Registra evento de auditoría para una acción';
COMMENT ON FUNCTION cleanup_old_actions() IS 'Limpia datos antiguos de acciones, outbox y auditoría';
COMMENT ON VIEW pulpo.action_metrics IS 'Métricas de acciones por workspace, tipo y estado';

-- 10. Ejemplo de uso de cleanup (para cron job)
-- SELECT cleanup_old_actions();

-- 11. Ejemplo de consulta de métricas
-- SELECT * FROM pulpo.action_metrics WHERE workspace_id = '00000000-0000-0000-0000-000000000000';

-- 12. Ejemplo de consulta de auditoría
-- SELECT * FROM pulpo.action_audit_log 
-- WHERE action_execution_id = 'some-uuid' 
-- ORDER BY created_at DESC;
