-- =====================================================
-- Migration 004: Workspace Calendar Configuration
-- Agrega configuración de Google Calendar por workspace
-- =====================================================

-- Agregar campos de configuración de calendario al workspace
ALTER TABLE pulpo.workspaces
ADD COLUMN IF NOT EXISTS business_calendar_email TEXT,
ADD COLUMN IF NOT EXISTS calendar_settings JSONB DEFAULT '{}'::jsonb;

-- Índice para buscar por calendar email
CREATE INDEX IF NOT EXISTS idx_workspaces_calendar_email
ON pulpo.workspaces(business_calendar_email);

-- Comentarios
COMMENT ON COLUMN pulpo.workspaces.business_calendar_email IS 'Email del Google Calendar del negocio (ej: peluqueriaReina@gmail.com)';
COMMENT ON COLUMN pulpo.workspaces.calendar_settings IS 'Configuración adicional de calendario: timezone, horarios de atención, días no laborables, etc.';

-- Actualizar workspace de ejemplo
UPDATE pulpo.workspaces
SET
    business_calendar_email = 'peluqueriaReina@gmail.com',
    calendar_settings = jsonb_build_object(
        'timezone', 'America/Argentina/Buenos_Aires',
        'business_hours', jsonb_build_object(
            'monday', jsonb_build_array('09:00', '18:00'),
            'tuesday', jsonb_build_array('09:00', '18:00'),
            'wednesday', jsonb_build_array('09:00', '18:00'),
            'thursday', jsonb_build_array('09:00', '18:00'),
            'friday', jsonb_build_array('09:00', '18:00'),
            'saturday', jsonb_build_array('09:00', '14:00')
        ),
        'buffer_minutes', 5,
        'advance_booking_days', 30
    )
WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa'::uuid;

-- Modificar staff_members para que google_calendar_id sea opcional
-- (se usa solo si el empleado quiere compartir su calendario personal para bloqueos)
COMMENT ON COLUMN pulpo.staff_members.google_calendar_id IS 'Email del calendario personal del empleado (OPCIONAL - solo para verificar bloqueos personales)';

-- Función helper: Obtener calendario del negocio
CREATE OR REPLACE FUNCTION pulpo.get_business_calendar(p_workspace_id UUID)
RETURNS TEXT AS $$
DECLARE
    v_calendar_email TEXT;
BEGIN
    SELECT business_calendar_email INTO v_calendar_email
    FROM pulpo.workspaces
    WHERE id = p_workspace_id;

    RETURN v_calendar_email;
END;
$$ LANGUAGE plpgsql;

-- Ejemplo de consulta de disponibilidad que considera calendario del negocio
COMMENT ON FUNCTION pulpo.find_available_staff IS 'Encuentra staff disponible verificando turnos en appointments (DB). La verificación de Google Calendar se hace en el código de Python.';
