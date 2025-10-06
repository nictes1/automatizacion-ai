"""
Appointments Service - Gestión de turnos y agendamiento
"""

import logging
from datetime import datetime, date, time, timedelta
from typing import Optional, Dict, List, Any
from uuid import UUID
import asyncpg
from services.google_calendar_client import GoogleCalendarClient
from services.calendar_config_service import calendar_config_service

logger = logging.getLogger(__name__)

class AppointmentsService:
    """Servicio para gestión de turnos"""

    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None

    async def initialize_db(self, pool: asyncpg.Pool):
        """Inicializa el pool de conexiones"""
        self.db_pool = pool
        logger.info("✅ Appointments service initialized")

    async def _get_calendar_client(self, workspace_id: UUID) -> Optional[GoogleCalendarClient]:
        """
        Obtiene un cliente de Google Calendar con las credenciales del workspace

        Args:
            workspace_id: ID del workspace

        Returns:
            GoogleCalendarClient configurado o None si no hay calendario conectado
        """
        import json

        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT settings FROM pulpo.workspaces WHERE id = $1
            """, workspace_id)

            if not row or not row['settings']:
                logger.warning(f"No settings found for workspace {workspace_id}")
                return None

            settings = row['settings']
            # asyncpg puede devolver JSONB como string
            if isinstance(settings, str):
                settings = json.loads(settings)

        # Obtener credenciales descifradas
        credentials = calendar_config_service.get_credentials_from_workspace(settings)

        if not credentials:
            logger.warning(f"No calendar credentials for workspace {workspace_id}")
            return None

        # Crear cliente con las credenciales
        return GoogleCalendarClient(credentials)

    async def get_service_types(self, workspace_id: UUID) -> List[Dict[str, Any]]:
        """Obtiene los tipos de servicio disponibles"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(f"SELECT set_config('app.current_workspace_id', '{workspace_id}', true)")

            rows = await conn.fetch("""
                SELECT id, name, description, duration_minutes, price, currency
                FROM pulpo.service_types
                WHERE workspace_id = $1 AND active = true
                ORDER BY name
            """, workspace_id)

            return [dict(row) for row in rows]

    async def get_staff_members(
        self,
        workspace_id: UUID,
        service_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Obtiene staff disponible, opcionalmente filtrado por servicio"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(f"SELECT set_config('app.current_workspace_id', '{workspace_id}', true)")

            if service_type:
                rows = await conn.fetch("""
                    SELECT id, name, email, phone, photo_url, specialties
                    FROM pulpo.staff_members
                    WHERE workspace_id = $1
                        AND active = true
                        AND $2 = ANY(specialties)
                    ORDER BY name
                """, workspace_id, service_type)
            else:
                rows = await conn.fetch("""
                    SELECT id, name, email, phone, photo_url, specialties
                    FROM pulpo.staff_members
                    WHERE workspace_id = $1 AND active = true
                    ORDER BY name
                """, workspace_id)

            return [dict(row) for row in rows]

    async def check_availability(
        self,
        workspace_id: UUID,
        staff_id: UUID,
        appointment_date: date,
        appointment_time: time,
        duration_minutes: int
    ) -> bool:
        """
        Verifica si un staff member está disponible en un horario
        Consulta:
        1. DB (turnos ya agendados en el sistema)
        2. Calendario del negocio (por si hay eventos manuales)
        3. Calendario personal del empleado (si compartió acceso - para bloqueos personales)
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(f"SELECT set_config('app.current_workspace_id', '{workspace_id}', true)")

            # 1. Verificar en DB
            count = await conn.fetchval("""
                SELECT COUNT(*)
                FROM pulpo.appointments
                WHERE staff_member_id = $1
                    AND scheduled_date = $2
                    AND status NOT IN ('cancelled', 'no_show')
                    AND (
                        scheduled_time, scheduled_time + (duration_minutes || ' minutes')::INTERVAL
                    ) OVERLAPS (
                        $3::TIME, $3::TIME + make_interval(mins => $4)
                    )
            """, staff_id, appointment_date, appointment_time, duration_minutes)

            if count > 0:
                logger.info(f"Staff {staff_id} no disponible: turno en DB")
                return False

            # 2. Verificar en calendario del negocio
            business_calendar = await conn.fetchval("""
                SELECT business_calendar_email
                FROM pulpo.workspaces
                WHERE id = $1
            """, workspace_id)

            if business_calendar:
                start_dt = datetime.combine(appointment_date, appointment_time)
                end_dt = start_dt + timedelta(minutes=duration_minutes)

                # TODO: Verificar calendario de Google
                # Por ahora solo verificamos en DB
                logger.info("Verificación de disponibilidad en Google Calendar pendiente")

            # 3. Verificar calendario personal del empleado (opcional - para bloqueos)
            staff = await conn.fetchrow("""
                SELECT name, google_calendar_id
                FROM pulpo.staff_members
                WHERE id = $1
            """, staff_id)

            if staff and staff['google_calendar_id']:
                start_dt = datetime.combine(appointment_date, appointment_time)
                end_dt = start_dt + timedelta(minutes=duration_minutes)

                is_available = await google_calendar_client.check_availability(
                    calendar_id=staff['google_calendar_id'],
                    start_datetime=start_dt,
                    end_datetime=end_dt
                )

                if not is_available:
                    logger.info(f"Staff {staff['name']} no disponible: bloqueo en calendario personal")
                    return False

            return True

    async def create_appointment(
        self,
        workspace_id: UUID,
        conversation_id: Optional[UUID],
        service_type_name: str,
        client_name: str,
        client_email: str,
        client_phone: Optional[str],
        appointment_date: date,
        appointment_time: time,
        staff_id: Optional[UUID] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Crea un nuevo turno

        Returns:
            Dict con appointment_id, staff asignado, y google_event_id
        """
        async with self.db_pool.acquire() as conn:
            await conn.execute(f"SELECT set_config('app.current_workspace_id', '{workspace_id}', true)")

            # 1. Obtener service_type
            service = await conn.fetchrow("""
                SELECT id, duration_minutes, price, name
                FROM pulpo.service_types
                WHERE workspace_id = $1 AND name = $2
            """, workspace_id, service_type_name)

            if not service:
                raise ValueError(f"Service type '{service_type_name}' not found")

            service_id = service['id']
            duration = service['duration_minutes']

            # 2. Asignar staff si no se especificó
            if not staff_id:
                staff_row = await conn.fetchrow("""
                    SELECT staff_id, staff_name, staff_email
                    FROM pulpo.find_available_staff($1, $2, $3, $4, $5)
                    LIMIT 1
                """, workspace_id, service_type_name, appointment_date, appointment_time, duration)

                if not staff_row:
                    raise ValueError("No hay staff disponible para ese horario")

                staff_id = staff_row['staff_id']

            # Obtener info completa del staff (incluye google_calendar_id)
            staff_row = await conn.fetchrow("""
                SELECT name, email, google_calendar_id
                FROM pulpo.staff_members
                WHERE id = $1
            """, staff_id)

            if not staff_row:
                raise ValueError("El staff seleccionado no existe")

            # 3. Obtener calendario del negocio
            business_calendar = await conn.fetchval("""
                SELECT business_calendar_email
                FROM pulpo.workspaces
                WHERE id = $1
            """, workspace_id)

        # 4. Crear evento en Google Calendar del negocio (FUERA del contexto de conn)
        google_event_id = None
        if business_calendar:
            # Obtener cliente de calendario con credenciales OAuth del workspace
            calendar_client = await self._get_calendar_client(workspace_id)

            if calendar_client and calendar_client.is_available():
                start_dt = datetime.combine(appointment_date, appointment_time)
                end_dt = start_dt + timedelta(minutes=duration)

                summary = f"{staff_row['name']} - {service['name']} - {client_name}"
                description = f"""
Turno agendado via PulpoAI

Empleado: {staff_row['name']}
Servicio: {service['name']}
Cliente: {client_name}
Email: {client_email}
Teléfono: {client_phone or 'No especificado'}

Notas: {notes or 'Sin notas'}
""".strip()

                # Invitados: empleado + cliente
                attendees = [staff_row['email'], client_email]

                logger.info(f"📅 Creating Google Calendar event for appointment")

                google_event_id = await calendar_client.create_event(
                    calendar_id=business_calendar,
                    summary=summary,
                    description=description,
                    start_datetime=start_dt,
                    end_datetime=end_dt,
                    attendees=attendees
                )

                logger.info(f"✅ Event created in business calendar {business_calendar}: {google_event_id}")
            else:
                logger.warning(f"Google Calendar not available for workspace {workspace_id}")

        # 5. Guardar en DB
        async with self.db_pool.acquire() as conn:
            appointment_id = await conn.fetchval("""
                INSERT INTO pulpo.appointments (
                    workspace_id,
                    conversation_id,
                    client_name,
                    client_email,
                    client_phone,
                    service_type_id,
                    staff_member_id,
                    scheduled_date,
                    scheduled_time,
                    duration_minutes,
                    status,
                    google_event_id,
                    notes
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'confirmed', $11, $12
                )
                RETURNING id
            """, workspace_id, conversation_id, client_name, client_email, client_phone,
                service_id, staff_id, appointment_date, appointment_time, duration,
                google_event_id, notes)

        logger.info(f"✅ Appointment created: {appointment_id} with staff {staff_row['name']}")

        return {
            "appointment_id": str(appointment_id),
            "staff_name": staff_row['name'],
            "staff_email": staff_row['email'],
            "service_name": service['name'],
            "date": str(appointment_date),
            "time": str(appointment_time),
            "duration_minutes": duration,
            "google_event_id": google_event_id,
            "status": "confirmed"
        }

    async def cancel_appointment(
        self,
        workspace_id: UUID,
        appointment_id: UUID,
        cancellation_reason: Optional[str] = None
    ) -> bool:
        """Cancela un turno"""
        async with self.db_pool.acquire() as conn:
            await conn.execute(f"SELECT set_config('app.current_workspace_id', '{workspace_id}', true)")

            # Obtener appointment
            appt = await conn.fetchrow("""
                SELECT google_event_id
                FROM pulpo.appointments
                WHERE id = $1 AND workspace_id = $2
            """, appointment_id, workspace_id)

            if not appt:
                return False

            # Cancelar en Google Calendar del negocio
            if appt['google_event_id']:
                business_calendar = await conn.fetchval("""
                    SELECT business_calendar_email
                    FROM pulpo.workspaces
                    WHERE id = $1
                """, workspace_id)

                if business_calendar:
                    await google_calendar_client.cancel_event(
                        calendar_id=business_calendar,
                        event_id=appt['google_event_id'],
                        notify_attendees=True
                    )

            # Actualizar en DB
            await conn.execute("""
                UPDATE pulpo.appointments
                SET status = 'cancelled',
                    cancelled_at = NOW(),
                    cancellation_reason = $1
                WHERE id = $2
            """, cancellation_reason, appointment_id)

            logger.info(f"✅ Appointment cancelled: {appointment_id}")
            return True

# Instancia global
appointments_service = AppointmentsService()
