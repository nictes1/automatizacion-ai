#!/usr/bin/env python3
"""
Validador de Tokens de Usuario de la App Pulpo
Integra con el sistema de autenticación de la app principal
"""

import jwt
import logging
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Dict, Any, Optional, Tuple
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class PulpoTokenValidator:
    """Validador de tokens de usuario de la app Pulpo"""
    
    def __init__(self, db_connection_string: str, jwt_secret: str = None):
        self.db_connection_string = db_connection_string
        self.jwt_secret = jwt_secret or os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
        self.jwt_algorithm = os.getenv('JWT_ALGORITHM', 'HS256')
    
    def validate_user_token(self, token: str) -> Tuple[bool, Dict[str, Any], str]:
        """
        Valida token de usuario de la app Pulpo
        
        Args:
            token: Token JWT del usuario
            
        Returns:
            Tuple[es_valido, datos_usuario, mensaje_error]
        """
        try:
            # Decodificar token JWT
            payload = jwt.decode(token, self.jwt_secret, algorithms=[self.jwt_algorithm])
            
            # Verificar campos requeridos
            required_fields = ['user_id', 'workspace_id', 'exp']
            for field in required_fields:
                if field not in payload:
                    return False, {}, f"Campo requerido faltante: {field}"
            
            # Verificar expiración
            exp = datetime.fromtimestamp(payload['exp'])
            if exp < datetime.utcnow():
                return False, {}, "Token expirado"
            
            # Obtener información del usuario desde la base de datos
            user_info = self._get_user_info(payload['user_id'], payload['workspace_id'])
            if not user_info:
                return False, {}, "Usuario no encontrado o sin acceso al workspace"
            
            # Combinar datos del token con datos de la base de datos
            user_data = {
                'user_id': payload['user_id'],
                'workspace_id': payload['workspace_id'],
                'email': user_info.get('email'),
                'name': user_info.get('name'),
                'role': user_info.get('role'),
                'permissions': self._get_user_permissions(payload['user_id'], payload['workspace_id']),
                'workspace_name': user_info.get('workspace_name'),
                'workspace_plan': user_info.get('workspace_plan')
            }
            
            return True, user_data, ""
            
        except jwt.ExpiredSignatureError:
            return False, {}, "Token expirado"
        except jwt.JWTError as e:
            return False, {}, f"Token inválido: {str(e)}"
        except Exception as e:
            logger.error(f"Error validando token: {e}")
            return False, {}, f"Error interno: {str(e)}"
    
    def _get_user_info(self, user_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información del usuario desde la base de datos"""
        conn = None
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Consulta para obtener información del usuario y workspace
            query = """
            SELECT 
                u.id as user_id,
                u.email,
                u.name,
                u.role,
                w.id as workspace_id,
                w.name as workspace_name,
                w.plan as workspace_plan,
                w.status as workspace_status
            FROM pulpo.users u
            JOIN pulpo.workspaces w ON w.id = %s
            WHERE u.id = %s 
            AND u.workspace_id = %s
            AND u.status = 'active'
            AND w.status = 'active'
            """
            
            cur.execute(query, (workspace_id, user_id, workspace_id))
            result = cur.fetchone()
            
            if result:
                return dict(result)
            else:
                return None
                
        except Exception as e:
            logger.error(f"Error obteniendo información del usuario: {e}")
            return None
        finally:
            if conn:
                conn.close()
    
    def _get_user_permissions(self, user_id: str, workspace_id: str) -> list:
        """Obtiene permisos del usuario para el workspace"""
        # Por ahora, permisos basados en rol
        # En el futuro, esto podría ser más granular
        
        conn = None
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener rol del usuario
            cur.execute(
                "SELECT role FROM pulpo.users WHERE id = %s AND workspace_id = %s",
                (user_id, workspace_id)
            )
            result = cur.fetchone()
            
            if not result:
                return []
            
            role = result['role']
            
            # Mapear roles a permisos
            role_permissions = {
                'admin': [
                    'file:ingest', 'file:delete', 'file:read',
                    'workspace:read', 'workspace:admin', 'workspace:settings'
                ],
                'manager': [
                    'file:ingest', 'file:delete', 'file:read',
                    'workspace:read', 'workspace:settings'
                ],
                'user': [
                    'file:ingest', 'file:read', 'workspace:read'
                ],
                'viewer': [
                    'file:read', 'workspace:read'
                ]
            }
            
            return role_permissions.get(role, [])
            
        except Exception as e:
            logger.error(f"Error obteniendo permisos del usuario: {e}")
            return []
        finally:
            if conn:
                conn.close()
    
    def get_workspace_limits(self, workspace_id: str) -> Dict[str, Any]:
        """Obtiene límites del workspace desde la base de datos"""
        conn = None
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener configuración del workspace
            cur.execute(
                """
                SELECT 
                    w.plan,
                    wc.config
                FROM pulpo.workspaces w
                LEFT JOIN pulpo.workspace_configs wc ON wc.workspace_id = w.id
                WHERE w.id = %s
                """,
                (workspace_id,)
            )
            result = cur.fetchone()
            
            if not result:
                return self._get_default_limits()
            
            # Límites por plan
            plan_limits = {
                'free': {
                    'max_file_size_mb': 10,
                    'max_pages_pdf': 50,
                    'max_audio_duration_minutes': 10,
                    'max_video_duration_minutes': 15,
                    'max_files_per_month': 100,
                    'quality_threshold': 0.6
                },
                'basic': {
                    'max_file_size_mb': 50,
                    'max_pages_pdf': 100,
                    'max_audio_duration_minutes': 30,
                    'max_video_duration_minutes': 60,
                    'max_files_per_month': 1000,
                    'quality_threshold': 0.7
                },
                'premium': {
                    'max_file_size_mb': 200,
                    'max_pages_pdf': 500,
                    'max_audio_duration_minutes': 120,
                    'max_video_duration_minutes': 240,
                    'max_files_per_month': 10000,
                    'quality_threshold': 0.8
                },
                'enterprise': {
                    'max_file_size_mb': 1000,
                    'max_pages_pdf': 2000,
                    'max_audio_duration_minutes': 480,
                    'max_video_duration_minutes': 960,
                    'max_files_per_month': 100000,
                    'quality_threshold': 0.9
                }
            }
            
            plan = result['plan'] or 'free'
            limits = plan_limits.get(plan, plan_limits['free'])
            
            # Aplicar configuraciones personalizadas si existen
            if result['config']:
                custom_config = result['config']
                if 'file_limits' in custom_config:
                    limits.update(custom_config['file_limits'])
            
            return limits
            
        except Exception as e:
            logger.error(f"Error obteniendo límites del workspace: {e}")
            return self._get_default_limits()
        finally:
            if conn:
                conn.close()
    
    def _get_default_limits(self) -> Dict[str, Any]:
        """Retorna límites por defecto"""
        return {
            'max_file_size_mb': 10,
            'max_pages_pdf': 50,
            'max_audio_duration_minutes': 10,
            'max_video_duration_minutes': 15,
            'max_files_per_month': 100,
            'quality_threshold': 0.6
        }
    
    def check_user_file_quota(self, user_id: str, workspace_id: str) -> Tuple[bool, str]:
        """Verifica si el usuario puede subir más archivos este mes"""
        conn = None
        try:
            conn = psycopg2.connect(self.db_connection_string)
            cur = conn.cursor(cursor_factory=RealDictCursor)
            
            # Obtener límites del workspace
            limits = self.get_workspace_limits(workspace_id)
            max_files = limits.get('max_files_per_month', 100)
            
            # Contar archivos subidos este mes
            cur.execute(
                """
                SELECT COUNT(*) as file_count
                FROM pulpo.files
                WHERE workspace_id = %s
                AND created_at >= date_trunc('month', CURRENT_DATE)
                """,
                (workspace_id,)
            )
            result = cur.fetchone()
            
            current_files = result['file_count'] if result else 0
            
            if current_files >= max_files:
                return False, f"Límite mensual alcanzado: {current_files}/{max_files} archivos"
            
            return True, f"Quota disponible: {max_files - current_files} archivos restantes"
            
        except Exception as e:
            logger.error(f"Error verificando quota del usuario: {e}")
            return False, f"Error verificando quota: {str(e)}"
        finally:
            if conn:
                conn.close()

# Función de utilidad para crear tokens de prueba
def create_test_user_token(
    user_id: str,
    workspace_id: str,
    jwt_secret: str = None,
    expires_hours: int = 24
) -> str:
    """Crea un token de prueba para un usuario"""
    import jwt
    from datetime import datetime, timedelta
    
    secret = jwt_secret or os.getenv('JWT_SECRET', 'your-secret-key-change-in-production')
    
    now = datetime.utcnow()
    exp = now + timedelta(hours=expires_hours)
    
    payload = {
        'user_id': user_id,
        'workspace_id': workspace_id,
        'iat': now,
        'exp': exp
    }
    
    return jwt.encode(payload, secret, algorithm='HS256')

if __name__ == "__main__":
    # Prueba del validador
    validator = PulpoTokenValidator(
        db_connection_string="postgresql://pulpo_user:pulpo_password@localhost:5432/pulpo_db"
    )
    
    # Crear token de prueba
    test_token = create_test_user_token(
        user_id="00000000-0000-0000-0000-000000000001",
        workspace_id="00000000-0000-0000-0000-000000000001"
    )
    
    print(f"Token de prueba: {test_token}")
    
    # Validar token
    is_valid, user_data, error = validator.validate_user_token(test_token)
    
    if is_valid:
        print("✅ Token válido")
        print(f"Usuario: {user_data['name']} ({user_data['email']})")
        print(f"Workspace: {user_data['workspace_name']}")
        print(f"Permisos: {', '.join(user_data['permissions'])}")
        
        # Verificar límites
        limits = validator.get_workspace_limits(user_data['workspace_id'])
        print(f"Límites: {limits}")
        
        # Verificar quota
        can_upload, quota_msg = validator.check_user_file_quota(
            user_data['user_id'], user_data['workspace_id']
        )
        print(f"Quota: {quota_msg}")
    else:
        print(f"❌ Token inválido: {error}")

