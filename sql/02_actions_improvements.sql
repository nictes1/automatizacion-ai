-- Migraciones para mejoras del Actions Service
-- Ejecutar después de 01_core_up.sql

-- 1. Tabla de ejecuciones de acciones para idempotencia persistida
CREATE TABLE IF NOT EXISTS pulpo.action_executions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    conversation_id TEXT NOT NULL,
    action_name TEXT NOT NULL,
    idempotency_key TEXT NOT NULL,
    status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'success', 'failed', 'cancelled')),
    summary TEXT NOT NULL,
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at TIMESTAMPTZ,
    error_message TEXT,
    UNIQUE (workspace_id, idempotency_key)
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_action_executions_workspace_id ON pulpo.action_executions(workspace_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_conversation_id ON pulpo.action_executions(conversation_id);
CREATE INDEX IF NOT EXISTS idx_action_executions_status ON pulpo.action_executions(status);
CREATE INDEX IF NOT EXISTS idx_action_executions_created_at ON pulpo.action_executions(created_at);

-- 2. Tabla outbox para webhooks confiables a N8N
CREATE TABLE IF NOT EXISTS pulpo.event_outbox (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    event_type TEXT NOT NULL,
    payload JSONB NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'sent', 'failed', 'retrying')),
    attempts INT NOT NULL DEFAULT 0,
    max_attempts INT NOT NULL DEFAULT 3,
    last_attempt_at TIMESTAMPTZ,
    next_retry_at TIMESTAMPTZ,
    error_message TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    sent_at TIMESTAMPTZ
);

-- Índices para outbox
CREATE INDEX IF NOT EXISTS idx_event_outbox_status ON pulpo.event_outbox(status);
CREATE INDEX IF NOT EXISTS idx_event_outbox_next_retry ON pulpo.event_outbox(next_retry_at) WHERE status = 'retrying';
CREATE INDEX IF NOT EXISTS idx_event_outbox_workspace_id ON pulpo.event_outbox(workspace_id);

-- 3. Tabla de catálogo de menú para gastronomía (si no existe)
CREATE TABLE IF NOT EXISTS pulpo.menu_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    nombre TEXT NOT NULL,
    sku TEXT,
    precio DECIMAL(10,2) NOT NULL,
    descripcion TEXT,
    categoria TEXT,
    disponible BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, sku),
    UNIQUE (workspace_id, nombre)
);

-- Índices para menu_items
CREATE INDEX IF NOT EXISTS idx_menu_items_workspace_id ON pulpo.menu_items(workspace_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_nombre ON pulpo.menu_items(workspace_id, nombre);
CREATE INDEX IF NOT EXISTS idx_menu_items_sku ON pulpo.menu_items(workspace_id, sku);
CREATE INDEX IF NOT EXISTS idx_menu_items_disponible ON pulpo.menu_items(workspace_id, disponible);

-- 4. Tabla de servicios para vertical servicios
CREATE TABLE IF NOT EXISTS pulpo.services_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    service_type TEXT NOT NULL,
    nombre TEXT NOT NULL,
    descripcion TEXT,
    duracion_minutes INT NOT NULL DEFAULT 60,
    precio DECIMAL(10,2),
    disponible BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, service_type)
);

-- Índices para services_catalog
CREATE INDEX IF NOT EXISTS idx_services_catalog_workspace_id ON pulpo.services_catalog(workspace_id);
CREATE INDEX IF NOT EXISTS idx_services_catalog_service_type ON pulpo.services_catalog(workspace_id, service_type);

-- 5. Tabla de propiedades para inmobiliaria
CREATE TABLE IF NOT EXISTS pulpo.properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL,
    property_id TEXT NOT NULL,
    titulo TEXT NOT NULL,
    descripcion TEXT,
    direccion TEXT,
    precio DECIMAL(12,2),
    tipo_propiedad TEXT,
    disponible BOOLEAN NOT NULL DEFAULT true,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, property_id)
);

-- Índices para properties
CREATE INDEX IF NOT EXISTS idx_properties_workspace_id ON pulpo.properties(workspace_id);
CREATE INDEX IF NOT EXISTS idx_properties_property_id ON pulpo.properties(workspace_id, property_id);

-- 6. RLS (Row Level Security) para todas las tablas
ALTER TABLE pulpo.action_executions ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.menu_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.services_catalog ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.properties ENABLE ROW LEVEL SECURITY;

-- Políticas RLS (asumiendo que tienes una función get_current_workspace_id())
-- Nota: Necesitarás implementar esta función según tu sistema de autenticación

-- Para action_executions
CREATE POLICY action_executions_workspace_policy ON pulpo.action_executions
    FOR ALL TO authenticated
    USING (workspace_id = get_current_workspace_id());

-- Para event_outbox
CREATE POLICY event_outbox_workspace_policy ON pulpo.event_outbox
    FOR ALL TO authenticated
    USING (workspace_id = get_current_workspace_id());

-- Para menu_items
CREATE POLICY menu_items_workspace_policy ON pulpo.menu_items
    FOR ALL TO authenticated
    USING (workspace_id = get_current_workspace_id());

-- Para services_catalog
CREATE POLICY services_catalog_workspace_policy ON pulpo.services_catalog
    FOR ALL TO authenticated
    USING (workspace_id = get_current_workspace_id());

-- Para properties
CREATE POLICY properties_workspace_policy ON pulpo.properties
    FOR ALL TO authenticated
    USING (workspace_id = get_current_workspace_id());

-- 7. Función helper para obtener workspace_id del contexto
-- Esta función debe ser implementada según tu sistema de autenticación
-- Por ahora, una versión simple que retorna el workspace_id del contexto de sesión
CREATE OR REPLACE FUNCTION get_current_workspace_id()
RETURNS UUID AS $$
BEGIN
    -- En una implementación real, esto vendría del JWT o contexto de sesión
    -- Por ahora retornamos un UUID por defecto
    RETURN COALESCE(
        current_setting('app.workspace_id', true)::UUID,
        '00000000-0000-0000-0000-000000000000'::UUID
    );
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- 8. Triggers para updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_menu_items_updated_at
    BEFORE UPDATE ON pulpo.menu_items
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_services_catalog_updated_at
    BEFORE UPDATE ON pulpo.services_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_properties_updated_at
    BEFORE UPDATE ON pulpo.properties
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- 9. Datos de ejemplo para testing
INSERT INTO pulpo.menu_items (workspace_id, nombre, sku, precio, descripcion, categoria) VALUES
    ('00000000-0000-0000-0000-000000000000', 'Empanada de Carne', 'EMP-CARNE-001', 500.00, 'Empanada tradicional de carne molida', 'Empanadas'),
    ('00000000-0000-0000-0000-000000000000', 'Empanada de Pollo', 'EMP-POLLO-001', 500.00, 'Empanada de pollo con verduras', 'Empanadas'),
    ('00000000-0000-0000-0000-000000000000', 'Pizza Margherita', 'PIZ-MARG-001', 1200.00, 'Pizza con tomate, mozzarella y albahaca', 'Pizzas'),
    ('00000000-0000-0000-0000-000000000000', 'Coca Cola 500ml', 'BEB-COCA-500', 300.00, 'Bebida gaseosa', 'Bebidas')
ON CONFLICT (workspace_id, nombre) DO NOTHING;

INSERT INTO pulpo.services_catalog (workspace_id, service_type, nombre, descripcion, duracion_minutes, precio) VALUES
    ('00000000-0000-0000-0000-000000000000', 'limpieza', 'Limpieza Residencial', 'Servicio de limpieza para hogares', 120, 5000.00),
    ('00000000-0000-0000-0000-000000000000', 'jardineria', 'Mantenimiento de Jardín', 'Corte de pasto y poda de plantas', 90, 3500.00),
    ('00000000-0000-0000-0000-000000000000', 'plomeria', 'Reparación de Plomería', 'Servicio de plomería general', 60, 8000.00)
ON CONFLICT (workspace_id, service_type) DO NOTHING;

INSERT INTO pulpo.properties (workspace_id, property_id, titulo, descripcion, direccion, precio, tipo_propiedad) VALUES
    ('00000000-0000-0000-0000-000000000000', 'PROP-001', 'Casa en Palermo', 'Hermosa casa de 3 dormitorios en Palermo', 'Av. Santa Fe 1234, Palermo', 150000.00, 'casa'),
    ('00000000-0000-0000-0000-000000000000', 'PROP-002', 'Departamento en Recoleta', 'Departamento de 2 ambientes en Recoleta', 'Av. Las Heras 5678, Recoleta', 120000.00, 'departamento'),
    ('00000000-0000-0000-0000-000000000000', 'PROP-003', 'Oficina en Microcentro', 'Oficina moderna en el centro', 'Av. Corrientes 9999, Microcentro', 80000.00, 'oficina')
ON CONFLICT (workspace_id, property_id) DO NOTHING;

-- 10. Comentarios para documentación
COMMENT ON TABLE pulpo.action_executions IS 'Registro de ejecuciones de acciones para idempotencia';
COMMENT ON TABLE pulpo.event_outbox IS 'Cola de eventos para envío confiable a sistemas externos';
COMMENT ON TABLE pulpo.menu_items IS 'Catálogo de items del menú para gastronomía';
COMMENT ON TABLE pulpo.services_catalog IS 'Catálogo de servicios disponibles';
COMMENT ON TABLE pulpo.properties IS 'Catálogo de propiedades inmobiliarias';

COMMENT ON COLUMN pulpo.action_executions.idempotency_key IS 'Clave única para prevenir ejecuciones duplicadas';
COMMENT ON COLUMN pulpo.event_outbox.next_retry_at IS 'Timestamp para próximo intento de envío';
COMMENT ON COLUMN pulpo.menu_items.sku IS 'Código único del producto (opcional)';
COMMENT ON COLUMN pulpo.properties.property_id IS 'Identificador externo de la propiedad';
