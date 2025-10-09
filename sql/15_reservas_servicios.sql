-- =========================
-- Helper Functions
-- =========================

-- Función para actualizar updated_at automáticamente
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- =========================
-- Tabla de Reservas (book_slot action)
-- =========================

-- Tabla para reservas de turnos
CREATE TABLE IF NOT EXISTS pulpo.reservas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    service_type TEXT NOT NULL,
    preferred_date TIMESTAMPTZ NOT NULL,
    contact_info JSONB NOT NULL DEFAULT '{}',
    status TEXT CHECK (status IN ('confirmed', 'pending', 'cancelled', 'completed')) DEFAULT 'confirmed',
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para reservas
CREATE INDEX IF NOT EXISTS idx_reservas_workspace_id ON pulpo.reservas(workspace_id);
CREATE INDEX IF NOT EXISTS idx_reservas_conversation_id ON pulpo.reservas(conversation_id);
CREATE INDEX IF NOT EXISTS idx_reservas_status ON pulpo.reservas(status);
CREATE INDEX IF NOT EXISTS idx_reservas_preferred_date ON pulpo.reservas(preferred_date);

-- RLS para reservas
ALTER TABLE pulpo.reservas ENABLE ROW LEVEL SECURITY;

CREATE POLICY reservas_workspace_policy ON pulpo.reservas
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Trigger para updated_at
CREATE TRIGGER update_reservas_updated_at
    BEFORE UPDATE ON pulpo.reservas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =========================
-- Visitas (schedule_visit action)
-- =========================

-- Tabla para visitas a propiedades
CREATE TABLE IF NOT EXISTS pulpo.visitas (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID NOT NULL REFERENCES pulpo.conversations(id) ON DELETE CASCADE,
    property_id TEXT NOT NULL,
    preferred_date TIMESTAMPTZ NOT NULL,
    contact_info JSONB NOT NULL DEFAULT '{}',
    status TEXT CHECK (status IN ('scheduled', 'confirmed', 'cancelled', 'completed')) DEFAULT 'scheduled',
    notas TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Índices para visitas
CREATE INDEX IF NOT EXISTS idx_visitas_workspace_id ON pulpo.visitas(workspace_id);
CREATE INDEX IF NOT EXISTS idx_visitas_conversation_id ON pulpo.visitas(conversation_id);
CREATE INDEX IF NOT EXISTS idx_visitas_status ON pulpo.visitas(status);
CREATE INDEX IF NOT EXISTS idx_visitas_preferred_date ON pulpo.visitas(preferred_date);

-- RLS para visitas
ALTER TABLE pulpo.visitas ENABLE ROW LEVEL SECURITY;

CREATE POLICY visitas_workspace_policy ON pulpo.visitas
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Trigger para updated_at
CREATE TRIGGER update_visitas_updated_at
    BEFORE UPDATE ON pulpo.visitas
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =========================
-- Tabla de Catálogo de Servicios
-- =========================

-- Crear tabla services_catalog si no existe
CREATE TABLE IF NOT EXISTS pulpo.services_catalog (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
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

-- RLS para services_catalog
ALTER TABLE pulpo.services_catalog ENABLE ROW LEVEL SECURITY;

CREATE POLICY services_catalog_workspace_policy ON pulpo.services_catalog
    USING (workspace_id = current_setting('app.workspace_id', true)::UUID);

-- Trigger para updated_at
CREATE TRIGGER update_services_catalog_updated_at
    BEFORE UPDATE ON pulpo.services_catalog
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- =========================
-- Seed Data - Servicios de Peluquería
-- =========================

-- Insertar servicios de peluquería para testing
INSERT INTO pulpo.services_catalog (workspace_id, service_type, nombre, descripcion, duracion_minutes, precio, disponible) VALUES
    ('550e8400-e29b-41d4-a716-446655440000', 'corte_caballero', 'Corte Caballero', 'Corte de cabello clásico para hombre', 30, 15.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'corte_dama', 'Corte Dama', 'Corte de cabello para mujer', 45, 25.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'tintura', 'Tintura', 'Aplicación de color completo', 90, 50.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'barba', 'Arreglo de Barba', 'Perfilado y arreglo de barba', 20, 12.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'peinado', 'Peinado', 'Peinado para eventos', 60, 35.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'alisado', 'Alisado', 'Tratamiento de alisado', 120, 80.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'mechas', 'Mechas', 'Aplicación de mechas', 90, 60.00, true),
    ('550e8400-e29b-41d4-a716-446655440000', 'tratamiento_capilar', 'Tratamiento Capilar', 'Hidratación y reparación', 45, 30.00, true)
ON CONFLICT (workspace_id, service_type) DO UPDATE 
    SET nombre = EXCLUDED.nombre,
        descripcion = EXCLUDED.descripcion,
        duracion_minutes = EXCLUDED.duracion_minutes,
        precio = EXCLUDED.precio,
        disponible = EXCLUDED.disponible,
        updated_at = now();

-- =========================
-- Comentarios
-- =========================

COMMENT ON TABLE pulpo.reservas IS 'Reservas de turnos para servicios (peluquería, etc.)';
COMMENT ON TABLE pulpo.visitas IS 'Visitas agendadas a propiedades (inmobiliaria)';
COMMENT ON COLUMN pulpo.reservas.service_type IS 'Tipo de servicio referenciando pulpo.services_catalog';
COMMENT ON COLUMN pulpo.reservas.contact_info IS 'JSON con name, email, phone del cliente';
COMMENT ON COLUMN pulpo.visitas.property_id IS 'ID de propiedad referenciando pulpo.properties';
COMMENT ON COLUMN pulpo.visitas.contact_info IS 'JSON con información de contacto del interesado';

