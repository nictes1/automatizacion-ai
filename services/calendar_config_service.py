"""
Calendar Configuration Service
Maneja la configuración de Google Calendar OAuth2 por workspace
"""

import json
import logging
from typing import Optional, Dict
from uuid import UUID
import asyncpg
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build
import os
from services.encryption_utils import encryption_service

logger = logging.getLogger(__name__)

class CalendarConfigService:
    """Servicio para configurar Google Calendar por workspace"""

    def __init__(self):
        self.db_pool: Optional[asyncpg.Pool] = None
        # Incluir scopes adicionales que Google agrega automáticamente
        self.oauth_scopes = [
            'openid',
            'https://www.googleapis.com/auth/userinfo.email',
            'https://www.googleapis.com/auth/userinfo.profile',
            'https://www.googleapis.com/auth/calendar',
            'https://www.googleapis.com/auth/calendar.events'
        ]

    async def initialize_db(self, pool: asyncpg.Pool):
        """Inicializa el pool de conexiones"""
        self.db_pool = pool
        logger.info("✅ Calendar config service initialized")

    def get_oauth_flow(self, redirect_uri: str) -> Flow:
        """
        Crea un flow de OAuth2 para Google Calendar

        Args:
            redirect_uri: URL donde Google redirigirá después de la autorización

        Returns:
            Flow configurado
        """
        client_config = {
            "web": {
                "client_id": os.getenv("GOOGLE_CLIENT_ID"),
                "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri]
            }
        }

        flow = Flow.from_client_config(
            client_config,
            scopes=self.oauth_scopes,
            redirect_uri=redirect_uri
        )

        return flow

    async def get_authorization_url(
        self,
        workspace_id: UUID,
        redirect_uri: str
    ) -> str:
        """
        Genera URL de autorización de Google OAuth

        Args:
            workspace_id: ID del workspace
            redirect_uri: URL de callback

        Returns:
            URL para que el usuario autorice
        """
        flow = self.get_oauth_flow(redirect_uri)

        # Generar URL con state (incluye workspace_id para tracking)
        # prompt='consent' fuerza a Google a devolver refresh_token siempre
        authorization_url, state = flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true',
            prompt='consent',  # IMPORTANTE: Fuerza refresh_token
            state=str(workspace_id)
        )

        return authorization_url

    async def save_calendar_credentials(
        self,
        workspace_id: UUID,
        authorization_code: str,
        redirect_uri: str
    ) -> Dict[str, str]:
        """
        Guarda las credenciales de Google Calendar después de la autorización

        Args:
            workspace_id: ID del workspace
            authorization_code: Código recibido de Google
            redirect_uri: URL de callback (debe coincidir con la del flow)

        Returns:
            Dict con email del calendario y status
        """
        # Intercambiar código por tokens
        flow = self.get_oauth_flow(redirect_uri)
        flow.fetch_token(code=authorization_code)

        credentials = flow.credentials

        # Obtener info del usuario (email del calendario)
        service = build('oauth2', 'v2', credentials=credentials)
        user_info = service.userinfo().get().execute()
        calendar_email = user_info['email']

        # Guardar tokens en DB (CIFRADOS)
        async with self.db_pool.acquire() as conn:
            # Construir el objeto de tokens
            tokens_data = {
                'token': credentials.token,
                'refresh_token': credentials.refresh_token,
                'token_uri': credentials.token_uri,
                'client_id': credentials.client_id,
                'client_secret': credentials.client_secret,
                'scopes': list(credentials.scopes)
            }

            # CIFRAR tokens sensibles antes de guardar
            encrypted_tokens = encryption_service.encrypt_dict(tokens_data)
            tokens_json = json.dumps(encrypted_tokens)

            logger.info(f"🔒 Encrypting OAuth tokens for workspace {workspace_id}")

            await conn.execute("""
                UPDATE pulpo.workspaces
                SET
                    business_calendar_email = $1,
                    settings = COALESCE(settings, '{}'::jsonb) ||
                               jsonb_build_object('google_calendar_tokens', $2::jsonb)
                WHERE id = $3
            """,
                calendar_email,
                tokens_json,
                workspace_id
            )

        logger.info(f"✅ Calendar configured for workspace {workspace_id}: {calendar_email}")

        return {
            "calendar_email": calendar_email,
            "status": "connected"
        }

    async def get_calendar_config(self, workspace_id: UUID) -> Optional[Dict]:
        """Obtiene la configuración de calendario de un workspace"""
        async with self.db_pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT
                    business_calendar_email,
                    settings->'google_calendar_tokens' as tokens,
                    calendar_settings
                FROM pulpo.workspaces
                WHERE id = $1
            """, workspace_id)

            if not row:
                return None

            has_tokens = row['tokens'] is not None

            return {
                "calendar_email": row['business_calendar_email'],
                "is_configured": has_tokens,
                "calendar_settings": row['calendar_settings'] or {}
            }

    async def disconnect_calendar(self, workspace_id: UUID) -> bool:
        """Desconecta el calendario de Google"""
        async with self.db_pool.acquire() as conn:
            await conn.execute("""
                UPDATE pulpo.workspaces
                SET
                    business_calendar_email = NULL,
                    settings = settings - 'google_calendar_tokens'
                WHERE id = $1
            """, workspace_id)

        logger.info(f"✅ Calendar disconnected for workspace {workspace_id}")
        return True

    def get_credentials_from_workspace(self, workspace_settings: dict) -> Optional[Credentials]:
        """
        Reconstruye Credentials de Google desde los settings del workspace
        DESCIFRA los tokens antes de usarlos

        Args:
            workspace_settings: Dict con settings del workspace

        Returns:
            Credentials si existen, None si no
        """
        encrypted_tokens = workspace_settings.get('google_calendar_tokens')
        if not encrypted_tokens:
            return None

        # DESCIFRAR tokens antes de usar
        logger.info("🔓 Decrypting OAuth tokens from workspace settings")
        tokens = encryption_service.decrypt_dict(encrypted_tokens)

        credentials = Credentials(
            token=tokens['token'],
            refresh_token=tokens.get('refresh_token'),
            token_uri=tokens['token_uri'],
            client_id=tokens['client_id'],
            client_secret=tokens['client_secret'],
            scopes=tokens['scopes']
        )

        return credentials

# Instancia global
calendar_config_service = CalendarConfigService()
