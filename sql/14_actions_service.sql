-- =========================
-- Actions Service Tables
-- =========================

-- Tabla para resultados de acciones
CREATE TABLE IF NOT EXISTS pulpo.action_results (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    action_name VARCHAR(100) NOT NULL,
    args_json JSONB NOT NULL DEFAULT '{}',
    result_json JSONB NOT NULL DEFAULT '{}',
    request_hash VARCHAR(64) NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para performance
CREATE INDEX IF NOT EXISTS idx_action_results_conversation_id ON pulpo.action_results(conversation_id);
CREATE INDEX IF NOT EXISTS idx_action_results_action_name ON pulpo.action_results(action_name);
CREATE INDEX IF NOT EXISTS idx_action_results_request_hash ON pulpo.action_results(request_hash);
CREATE INDEX IF NOT EXISTS idx_action_results_created_at ON pulpo.action_results(created_at);

-- RLS para action_results
ALTER TABLE pulpo.action_results ENABLE ROW LEVEL SECURITY;

CREATE POLICY action_results_workspace_policy ON pulpo.action_results
    USING (conversation_id IN (
        SELECT c.id FROM pulpo.conversations c
        WHERE c.workspace_id = current_setting('app.workspace_id', true)::UUID
    ));

-- =========================
-- Tablas de negocio (ejemplos)
-- =========================

-- Menú para gastronomía
CREATE TABLE IF NOT EXISTS pulpo.menu_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    category VARCHAR(100) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para menu_items
CREATE INDEX IF NOT EXISTS idx_menu_items_workspace_id ON pulpo.menu_items(workspace_id);
CREATE INDEX IF NOT EXISTS idx_menu_items_category ON pulpo.menu_items(category);
CREATE INDEX IF NOT EXISTS idx_menu_items_is_active ON pulpo.menu_items(is_active);

-- RLS para menu_items
ALTER TABLE pulpo.menu_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY menu_items_workspace_policy ON pulpo.menu_items
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Pedidos
CREATE TABLE IF NOT EXISTS pulpo.orders (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES pulpo.conversations(id) ON DELETE SET NULL,
    items_json JSONB NOT NULL DEFAULT '[]',
    total DECIMAL(10,2) NOT NULL,
    metodo_entrega VARCHAR(50) NOT NULL,
    direccion TEXT,
    metodo_pago VARCHAR(50) NOT NULL,
    status VARCHAR(50) DEFAULT 'pending',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para orders
CREATE INDEX IF NOT EXISTS idx_orders_workspace_id ON pulpo.orders(workspace_id);
CREATE INDEX IF NOT EXISTS idx_orders_conversation_id ON pulpo.orders(conversation_id);
CREATE INDEX IF NOT EXISTS idx_orders_status ON pulpo.orders(status);
CREATE INDEX IF NOT EXISTS idx_orders_created_at ON pulpo.orders(created_at);

-- RLS para orders
ALTER TABLE pulpo.orders ENABLE ROW LEVEL SECURITY;

CREATE POLICY orders_workspace_policy ON pulpo.orders
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Propiedades para inmobiliaria
CREATE TABLE IF NOT EXISTS pulpo.properties (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    title VARCHAR(200) NOT NULL,
    description TEXT,
    zone VARCHAR(100) NOT NULL,
    price DECIMAL(12,2) NOT NULL,
    bedrooms INTEGER NOT NULL,
    bathrooms INTEGER NOT NULL,
    area DECIMAL(8,2) NOT NULL,
    operation VARCHAR(20) NOT NULL CHECK (operation IN ('venta', 'alquiler')),
    type VARCHAR(50) NOT NULL,
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para properties
CREATE INDEX IF NOT EXISTS idx_properties_workspace_id ON pulpo.properties(workspace_id);
CREATE INDEX IF NOT EXISTS idx_properties_operation ON pulpo.properties(operation);
CREATE INDEX IF NOT EXISTS idx_properties_type ON pulpo.properties(type);
CREATE INDEX IF NOT EXISTS idx_properties_zone ON pulpo.properties(zone);
CREATE INDEX IF NOT EXISTS idx_properties_price ON pulpo.properties(price);
CREATE INDEX IF NOT EXISTS idx_properties_is_active ON pulpo.properties(is_active);

-- RLS para properties
ALTER TABLE pulpo.properties ENABLE ROW LEVEL SECURITY;

CREATE POLICY properties_workspace_policy ON pulpo.properties
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Visitas
CREATE TABLE IF NOT EXISTS pulpo.visits (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    property_id UUID NOT NULL REFERENCES pulpo.properties(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES pulpo.conversations(id) ON DELETE SET NULL,
    visit_datetime TIMESTAMP WITH TIME ZONE NOT NULL,
    status VARCHAR(50) DEFAULT 'scheduled',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para visits
CREATE INDEX IF NOT EXISTS idx_visits_workspace_id ON pulpo.visits(workspace_id);
CREATE INDEX IF NOT EXISTS idx_visits_property_id ON pulpo.visits(property_id);
CREATE INDEX IF NOT EXISTS idx_visits_conversation_id ON pulpo.visits(conversation_id);
CREATE INDEX IF NOT EXISTS idx_visits_visit_datetime ON pulpo.visits(visit_datetime);

-- RLS para visits
ALTER TABLE pulpo.visits ENABLE ROW LEVEL SECURITY;

CREATE POLICY visits_workspace_policy ON pulpo.visits
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Servicios para servicios generales
CREATE TABLE IF NOT EXISTS pulpo.services (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    name VARCHAR(200) NOT NULL,
    description TEXT,
    price DECIMAL(10,2) NOT NULL,
    duration INTEGER NOT NULL, -- en minutos
    is_active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Índices para services
CREATE INDEX IF NOT EXISTS idx_services_workspace_id ON pulpo.services(workspace_id);
CREATE INDEX IF NOT EXISTS idx_services_is_active ON pulpo.services(is_active);

-- RLS para services
ALTER TABLE pulpo.services ENABLE ROW LEVEL SECURITY;

CREATE POLICY services_workspace_policy ON pulpo.services
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- =========================
-- Funciones de utilidad
-- =========================

-- Función para obtener estadísticas de acciones
CREATE OR REPLACE FUNCTION pulpo.get_action_stats(workspace_id_param UUID)
RETURNS TABLE (
    action_name VARCHAR,
    total_executions BIGINT,
    success_rate DECIMAL,
    avg_response_time DECIMAL
) AS $$
BEGIN
    RETURN QUERY
    SELECT 
        ar.action_name,
        COUNT(*) as total_executions,
        ROUND(
            (COUNT(*) FILTER (WHERE (ar.result_json->>'ok')::boolean = true) * 100.0 / COUNT(*)), 
            2
        ) as success_rate,
        ROUND(
            AVG(EXTRACT(EPOCH FROM (ar.updated_at - ar.created_at))), 
            3
        ) as avg_response_time
    FROM pulpo.action_results ar
    JOIN pulpo.conversations c ON ar.conversation_id = c.id
    WHERE c.workspace_id = workspace_id_param
    GROUP BY ar.action_name
    ORDER BY total_executions DESC;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- Función para limpiar resultados antiguos
CREATE OR REPLACE FUNCTION pulpo.cleanup_old_action_results(days_to_keep INTEGER DEFAULT 30)
RETURNS INTEGER AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM pulpo.action_results 
    WHERE created_at < NOW() - INTERVAL '1 day' * days_to_keep;
    
    GET DIAGNOSTICS deleted_count = ROW_COUNT;
    RETURN deleted_count;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;

-- =========================
-- Datos de ejemplo
-- =========================

-- Insertar datos de ejemplo para testing
INSERT INTO pulpo.menu_items (workspace_id, name, description, price, category) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Pizza Margarita', 'Pizza clásica con tomate, mozzarella y albahaca', 12.50, 'pizzas'),
    ('00000000-0000-0000-0000-000000000001', 'Pizza Pepperoni', 'Pizza con pepperoni y queso mozzarella', 14.00, 'pizzas'),
    ('00000000-0000-0000-0000-000000000001', 'Hamburguesa Clásica', 'Hamburguesa con carne, lechuga, tomate y cebolla', 8.50, 'hamburguesas'),
    ('00000000-0000-0000-0000-000000000001', 'Coca Cola', 'Bebida gaseosa 500ml', 2.50, 'bebidas'),
    ('00000000-0000-0000-0000-000000000001', 'Papas Fritas', 'Papas fritas crujientes', 3.00, 'acompañamientos')
ON CONFLICT DO NOTHING;

INSERT INTO pulpo.properties (workspace_id, title, zone, price, bedrooms, bathrooms, area, operation, type) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Departamento 2 ambientes', 'Palermo', 150000.00, 2, 1, 65.5, 'venta', 'departamento'),
    ('00000000-0000-0000-0000-000000000001', 'Casa 3 dormitorios', 'Belgrano', 250000.00, 3, 2, 120.0, 'venta', 'casa'),
    ('00000000-0000-0000-0000-000000000001', 'Departamento 1 ambiente', 'Recoleta', 80000.00, 1, 1, 45.0, 'alquiler', 'departamento')
ON CONFLICT DO NOTHING;

INSERT INTO pulpo.services (workspace_id, name, description, price, duration) VALUES
    ('00000000-0000-0000-0000-000000000001', 'Consulta General', 'Consulta médica general', 50.00, 30),
    ('00000000-0000-0000-0000-000000000001', 'Limpieza Dental', 'Limpieza y profilaxis dental', 80.00, 45),
    ('00000000-0000-0000-0000-000000000001', 'Control de Presión', 'Control de presión arterial', 25.00, 15)
ON CONFLICT DO NOTHING;

-- =========================
-- Comentarios
-- =========================

COMMENT ON TABLE pulpo.action_results IS 'Resultados de acciones ejecutadas por el Actions Service';
COMMENT ON TABLE pulpo.menu_items IS 'Items del menú para restaurantes';
COMMENT ON TABLE pulpo.orders IS 'Pedidos realizados por los clientes';
COMMENT ON TABLE pulpo.properties IS 'Propiedades inmobiliarias';
COMMENT ON TABLE pulpo.visits IS 'Visitas agendadas a propiedades';
COMMENT ON TABLE pulpo.services IS 'Servicios disponibles para agendar';

COMMENT ON FUNCTION pulpo.get_action_stats IS 'Obtiene estadísticas de acciones ejecutadas';
COMMENT ON FUNCTION pulpo.cleanup_old_action_results IS 'Limpia resultados de acciones antiguos';
