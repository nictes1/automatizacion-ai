"""
Google Calendar API Client
Maneja la integración con Google Calendar para agendamiento de turnos
Usa OAuth2 credentials del workspace (no service account)
"""

import json
import logging
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

class GoogleCalendarClient:
    """Cliente para interactuar con Google Calendar API usando OAuth credentials"""

    def __init__(self, credentials: Credentials):
        """
        Inicializa el cliente con credenciales OAuth del workspace

        Args:
            credentials: Google OAuth2 Credentials del usuario
        """
        self.credentials = credentials
        self.service = None
        self._initialize_service()

    def _initialize_service(self):
        """Crea el servicio de Google Calendar"""
        try:
            self.service = build('calendar', 'v3', credentials=self.credentials)
            logger.info("✅ Google Calendar service initialized")
        except Exception as e:
            logger.error(f"❌ Error initializing Google Calendar service: {e}")
            self.service = None

    def is_available(self) -> bool:
        """Verifica si el servicio está disponible"""
        return self.service is not None

    async def check_availability(
        self,
        calendar_id: str,
        start_datetime: datetime,
        end_datetime: datetime
    ) -> bool:
        """
        Verifica si un horario está disponible en el calendario

        Args:
            calendar_id: Email del calendario a verificar
            start_datetime: Inicio del slot
            end_datetime: Fin del slot

        Returns:
            True si está disponible, False si hay conflicto
        """
        if not self.is_available():
            logger.warning("Google Calendar not available, assuming slot is free")
            return True

        try:
            # Buscar eventos en ese rango
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=start_datetime.isoformat(),
                timeMax=end_datetime.isoformat(),
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])

            # Si hay eventos, el slot no está disponible
            if events:
                logger.info(f"Slot ocupado en {calendar_id}: {len(events)} evento(s) encontrado(s)")
                return False

            return True

        except HttpError as e:
            logger.error(f"Error checking availability: {e}")
            # En caso de error, asumimos que está disponible para no bloquear
            return True

    async def create_event(
        self,
        calendar_id: str,
        summary: str,
        description: str,
        start_datetime: datetime,
        end_datetime: datetime,
        attendees: List[str],
        location: Optional[str] = None,
        timezone: str = 'America/Argentina/Buenos_Aires'
    ) -> Optional[str]:
        """
        Crea un evento en Google Calendar

        Args:
            calendar_id: Email del calendario principal
            summary: Título del evento
            description: Descripción
            start_datetime: Inicio
            end_datetime: Fin
            attendees: Lista de emails de asistentes
            location: Ubicación (opcional)
            timezone: Timezone

        Returns:
            Event ID si se creó exitosamente, None en caso de error
        """
        if not self.is_available():
            logger.warning("Google Calendar not available, event not created")
            return None

        try:
            event = {
                'summary': summary,
                'description': description,
                'start': {
                    'dateTime': start_datetime.isoformat(),
                    'timeZone': timezone,
                },
                'end': {
                    'dateTime': end_datetime.isoformat(),
                    'timeZone': timezone,
                },
                'attendees': [{'email': email} for email in attendees],
                'reminders': {
                    'useDefault': False,
                    'overrides': [
                        {'method': 'email', 'minutes': 24 * 60},  # 1 día antes
                        {'method': 'popup', 'minutes': 60},       # 1 hora antes
                    ],
                },
            }

            if location:
                event['location'] = location

            # Crear evento
            created_event = self.service.events().insert(
                calendarId=calendar_id,
                body=event,
                sendUpdates='all'  # Enviar invitaciones por email
            ).execute()

            event_id = created_event.get('id')
            logger.info(f"✅ Event created: {event_id} in calendar {calendar_id}")

            return event_id

        except HttpError as e:
            logger.error(f"Error creating event: {e}")
            return None

    async def cancel_event(
        self,
        calendar_id: str,
        event_id: str,
        notify_attendees: bool = True
    ) -> bool:
        """
        Cancela un evento de Google Calendar

        Args:
            calendar_id: Email del calendario
            event_id: ID del evento
            notify_attendees: Si notificar a los asistentes

        Returns:
            True si se canceló exitosamente
        """
        if not self.is_available():
            logger.warning("Google Calendar not available, event not cancelled")
            return False

        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id,
                sendUpdates='all' if notify_attendees else 'none'
            ).execute()

            logger.info(f"✅ Event cancelled: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Error cancelling event: {e}")
            return False

    async def update_event(
        self,
        calendar_id: str,
        event_id: str,
        updates: Dict[str, Any]
    ) -> bool:
        """
        Actualiza un evento existente

        Args:
            calendar_id: Email del calendario
            event_id: ID del evento
            updates: Diccionario con campos a actualizar

        Returns:
            True si se actualizó exitosamente
        """
        if not self.is_available():
            logger.warning("Google Calendar not available, event not updated")
            return False

        try:
            # Obtener evento actual
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()

            # Aplicar updates
            event.update(updates)

            # Actualizar
            self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event,
                sendUpdates='all'
            ).execute()

            logger.info(f"✅ Event updated: {event_id}")
            return True

        except HttpError as e:
            logger.error(f"Error updating event: {e}")
            return False
