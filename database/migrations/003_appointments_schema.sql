-- =====================================================
-- Migration 003: Appointments & Services Schema
-- Sistema de agendamiento de turnos
-- =====================================================

-- Tabla de tipos de servicio por workspace
CREATE TABLE IF NOT EXISTS pulpo.service_types (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    description TEXT,
    duration_minutes INTEGER NOT NULL DEFAULT 30,
    price DECIMAL(10, 2),
    currency TEXT DEFAULT 'ARS',
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, name)
);

-- Índices para service_types
CREATE INDEX IF NOT EXISTS idx_service_types_workspace ON pulpo.service_types(workspace_id);
CREATE INDEX IF NOT EXISTS idx_service_types_active ON pulpo.service_types(workspace_id, active);

-- Tabla de empleados/staff por workspace
CREATE TABLE IF NOT EXISTS pulpo.staff_members (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    email TEXT NOT NULL,
    phone TEXT,
    google_calendar_id TEXT, -- Email del calendario de Google
    photo_url TEXT,
    role TEXT DEFAULT 'staff', -- staff, manager, admin
    specialties TEXT[], -- Array de service_type names que puede hacer
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(workspace_id, email)
);

-- Índices para staff_members
CREATE INDEX IF NOT EXISTS idx_staff_workspace ON pulpo.staff_members(workspace_id);
CREATE INDEX IF NOT EXISTS idx_staff_active ON pulpo.staff_members(workspace_id, active);
CREATE INDEX IF NOT EXISTS idx_staff_email ON pulpo.staff_members(email);

-- Tabla de turnos/appointments
CREATE TABLE IF NOT EXISTS pulpo.appointments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id UUID NOT NULL REFERENCES pulpo.workspaces(id) ON DELETE CASCADE,
    conversation_id UUID REFERENCES pulpo.conversations(id),

    -- Cliente
    client_name TEXT,
    client_email TEXT NOT NULL,
    client_phone TEXT,

    -- Servicio y staff
    service_type_id UUID REFERENCES pulpo.service_types(id),
    staff_member_id UUID REFERENCES pulpo.staff_members(id),

    -- Fecha y hora
    scheduled_date DATE NOT NULL,
    scheduled_time TIME NOT NULL,
    duration_minutes INTEGER NOT NULL,
    timezone TEXT DEFAULT 'America/Argentina/Buenos_Aires',

    -- Estado
    status TEXT DEFAULT 'pending', -- pending, confirmed, cancelled, completed, no_show

    -- Integración con Google Calendar
    google_event_id TEXT, -- ID del evento en Google Calendar

    -- Notas
    notes TEXT,
    metadata JSONB DEFAULT '{}',

    -- Auditoría
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    cancelled_at TIMESTAMPTZ,
    cancellation_reason TEXT
);

-- Índices para appointments
CREATE INDEX IF NOT EXISTS idx_appointments_workspace ON pulpo.appointments(workspace_id);
CREATE INDEX IF NOT EXISTS idx_appointments_conversation ON pulpo.appointments(conversation_id);
CREATE INDEX IF NOT EXISTS idx_appointments_client_email ON pulpo.appointments(client_email);
CREATE INDEX IF NOT EXISTS idx_appointments_staff ON pulpo.appointments(staff_member_id);
CREATE INDEX IF NOT EXISTS idx_appointments_date ON pulpo.appointments(scheduled_date, scheduled_time);
CREATE INDEX IF NOT EXISTS idx_appointments_status ON pulpo.appointments(workspace_id, status);
CREATE INDEX IF NOT EXISTS idx_appointments_google_event ON pulpo.appointments(google_event_id);

-- Row Level Security
ALTER TABLE pulpo.service_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.staff_members ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.appointments ENABLE ROW LEVEL SECURITY;

-- Políticas RLS (igual que otras tablas)
CREATE POLICY service_types_workspace_isolation ON pulpo.service_types
    USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid);

CREATE POLICY staff_members_workspace_isolation ON pulpo.staff_members
    USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid);

CREATE POLICY appointments_workspace_isolation ON pulpo.appointments
    USING (workspace_id = current_setting('app.current_workspace_id', true)::uuid);

-- Función para actualizar updated_at
CREATE OR REPLACE FUNCTION pulpo.update_appointments_updated_at()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Triggers para updated_at
CREATE TRIGGER service_types_updated_at
    BEFORE UPDATE ON pulpo.service_types
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_appointments_updated_at();

CREATE TRIGGER staff_members_updated_at
    BEFORE UPDATE ON pulpo.staff_members
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_appointments_updated_at();

CREATE TRIGGER appointments_updated_at
    BEFORE UPDATE ON pulpo.appointments
    FOR EACH ROW EXECUTE FUNCTION pulpo.update_appointments_updated_at();

-- Función helper: Buscar staff disponible para un servicio
CREATE OR REPLACE FUNCTION pulpo.find_available_staff(
    p_workspace_id UUID,
    p_service_type TEXT,
    p_date DATE,
    p_time TIME,
    p_duration_minutes INTEGER
) RETURNS TABLE (
    staff_id UUID,
    staff_name TEXT,
    staff_email TEXT,
    staff_photo_url TEXT
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        sm.id,
        sm.name,
        sm.email,
        sm.photo_url
    FROM pulpo.staff_members sm
    WHERE sm.workspace_id = p_workspace_id
        AND sm.active = true
        AND p_service_type = ANY(sm.specialties)
        AND NOT EXISTS (
            -- Verificar que no tenga otro turno a esa hora
            SELECT 1 FROM pulpo.appointments a
            WHERE a.staff_member_id = sm.id
                AND a.scheduled_date = p_date
                AND a.status NOT IN ('cancelled', 'no_show')
                AND (
                    -- Overlap detection
                    (a.scheduled_time, a.scheduled_time + (a.duration_minutes || ' minutes')::INTERVAL)
                    OVERLAPS
                    (p_time, p_time + (p_duration_minutes || ' minutes')::INTERVAL)
                )
        )
    ORDER BY sm.name
    LIMIT 5;
END;
$$ LANGUAGE plpgsql;

-- Datos de ejemplo para testing
-- (Solo insertar si no existen)
DO $$
DECLARE
    v_workspace_id UUID;
    v_service_corte UUID;
    v_service_barba UUID;
    v_staff_maria UUID;
    v_staff_carlos UUID;
BEGIN
    -- Buscar workspace de prueba
    SELECT id INTO v_workspace_id
    FROM pulpo.workspaces
    WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid
    LIMIT 1;

    IF v_workspace_id IS NOT NULL THEN
        -- Insertar tipos de servicio
        INSERT INTO pulpo.service_types (workspace_id, name, description, duration_minutes, price, currency)
        VALUES
            (v_workspace_id, 'Corte de pelo', 'Corte de pelo clásico o moderno', 30, 5000, 'ARS'),
            (v_workspace_id, 'Barba', 'Arreglo de barba completo', 20, 3000, 'ARS'),
            (v_workspace_id, 'Corte + Barba', 'Combo completo', 45, 7000, 'ARS'),
            (v_workspace_id, 'Coloración', 'Tinte de cabello', 60, 8000, 'ARS')
        ON CONFLICT (workspace_id, name) DO NOTHING
        RETURNING id INTO v_service_corte;

        -- Insertar staff
        INSERT INTO pulpo.staff_members (workspace_id, name, email, phone, google_calendar_id, specialties, active)
        VALUES
            (
                v_workspace_id,
                'María González',
                'maria@corteyook.com',
                '+5492235555001',
                'maria@corteyook.com',
                ARRAY['Corte de pelo', 'Coloración', 'Corte + Barba'],
                true
            ),
            (
                v_workspace_id,
                'Carlos Rodríguez',
                'carlos@corteyook.com',
                '+5492235555002',
                'carlos@corteyook.com',
                ARRAY['Corte de pelo', 'Barba', 'Corte + Barba'],
                true
            )
        ON CONFLICT (workspace_id, email) DO NOTHING;

        RAISE NOTICE 'Datos de ejemplo insertados para workspace %', v_workspace_id;
    END IF;
END $$;
