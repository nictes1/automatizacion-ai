#!/usr/bin/env python3
"""
PulpoAI Shared Database Client
Cliente compartido para operaciones de base de datos
"""

import os
import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import asyncpg
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import asynccontextmanager, contextmanager
from dataclasses import dataclass

logger = logging.getLogger(__name__)

@dataclass
class DatabaseConfig:
    """Configuración de base de datos"""
    host: str
    port: int
    database: str
    user: str
    password: str
    min_connections: int = 5
    max_connections: int = 20
    max_queries: int = 50000
    max_inactive_connection_lifetime: float = 300.0

class DatabaseError(Exception):
    """Error de base de datos"""
    pass

class ConnectionError(DatabaseError):
    """Error de conexión"""
    pass

class QueryError(DatabaseError):
    """Error de consulta"""
    pass

class DatabaseClient:
    """Cliente de base de datos compartido"""
    
    def __init__(self, config: Optional[DatabaseConfig] = None):
        self.config = config or self._load_config()
        self.pool: Optional[asyncpg.Pool] = None
        self._sync_conn = None
    
    def _load_config(self) -> DatabaseConfig:
        """Cargar configuración desde variables de entorno"""
        return DatabaseConfig(
            host=os.getenv('DB_HOST', 'postgres'),
            port=int(os.getenv('DB_PORT', '5432')),
            database=os.getenv('DB_NAME', 'pulpo'),
            user=os.getenv('DB_USER', 'pulpo'),
            password=os.getenv('DB_PASSWORD', 'pulpo'),
            min_connections=int(os.getenv('DB_MIN_CONNECTIONS', '5')),
            max_connections=int(os.getenv('DB_MAX_CONNECTIONS', '20'))
        )
    
    async def initialize(self):
        """Inicializar pool de conexiones"""
        if self.pool is None:
            try:
                self.pool = await asyncpg.create_pool(
                    host=self.config.host,
                    port=self.config.port,
                    database=self.config.database,
                    user=self.config.user,
                    password=self.config.password,
                    min_size=self.config.min_connections,
                    max_size=self.config.max_connections,
                    max_queries=self.config.max_queries,
                    max_inactive_connection_lifetime=self.config.max_inactive_connection_lifetime
                )
                logger.info("Database pool initialized")
            except Exception as e:
                logger.error(f"Failed to initialize database pool: {e}")
                raise ConnectionError(f"Failed to initialize database pool: {e}")
    
    async def close(self):
        """Cerrar pool de conexiones"""
        if self.pool:
            await self.pool.close()
            self.pool = None
            logger.info("Database pool closed")
    
    @asynccontextmanager
    async def get_connection(self):
        """Obtener conexión del pool"""
        if not self.pool:
            await self.initialize()
        
        connection = None
        try:
            connection = await self.pool.acquire()
            yield connection
        finally:
            if connection:
                await self.pool.release(connection)
    
    @contextmanager
    def get_sync_connection(self):
        """Obtener conexión síncrona"""
        connection = None
        try:
            connection = psycopg2.connect(
                host=self.config.host,
                port=self.config.port,
                database=self.config.database,
                user=self.config.user,
                password=self.config.password,
                cursor_factory=RealDictCursor
            )
            yield connection
        except Exception as e:
            if connection:
                connection.rollback()
            raise ConnectionError(f"Failed to get sync connection: {e}")
        finally:
            if connection:
                connection.close()
    
    async def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """Ejecutar consulta y retornar resultados"""
        try:
            async with self.get_connection() as conn:
                if params:
                    rows = await conn.fetch(query, *params)
                else:
                    rows = await conn.fetch(query)
                return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise QueryError(f"Query execution failed: {e}")
    
    async def execute_one(self, query: str, params: tuple = None) -> Optional[Dict[str, Any]]:
        """Ejecutar consulta y retornar un resultado"""
        try:
            async with self.get_connection() as conn:
                if params:
                    row = await conn.fetchrow(query, *params)
                else:
                    row = await conn.fetchrow(query)
                return dict(row) if row else None
        except Exception as e:
            logger.error(f"Query execution failed: {e}")
            raise QueryError(f"Query execution failed: {e}")
    
    async def execute_command(self, query: str, params: tuple = None) -> str:
        """Ejecutar comando (INSERT, UPDATE, DELETE)"""
        try:
            async with self.get_connection() as conn:
                if params:
                    result = await conn.execute(query, *params)
                else:
                    result = await conn.execute(query)
                return result
        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            raise QueryError(f"Command execution failed: {e}")
    
    async def execute_function(self, function_name: str, params: tuple = None) -> Any:
        """Ejecutar función PL/pgSQL"""
        try:
            async with self.get_connection() as conn:
                if params:
                    result = await conn.fetchval(f"SELECT {function_name}(*$1)", params)
                else:
                    result = await conn.fetchval(f"SELECT {function_name}()")
                return result
        except Exception as e:
            logger.error(f"Function execution failed: {e}")
            raise QueryError(f"Function execution failed: {e}")
    
    async def set_workspace_context(self, workspace_id: str):
        """Configurar contexto de workspace para RLS"""
        try:
            await self.execute_command(
                "SELECT pulpo.set_ws_context($1)",
                (workspace_id,)
            )
        except Exception as e:
            logger.error(f"Failed to set workspace context: {e}")
            raise QueryError(f"Failed to set workspace context: {e}")
    
    async def get_workspace_context(self) -> Optional[str]:
        """Obtener contexto de workspace actual"""
        try:
            result = await self.execute_one("SELECT pulpo.get_ws_context() as workspace_id")
            return result['workspace_id'] if result else None
        except Exception as e:
            logger.error(f"Failed to get workspace context: {e}")
            raise QueryError(f"Failed to get workspace context: {e}")
    
    # Métodos específicos para PulpoAI
    
    async def upsert_dialogue_state(
        self,
        workspace_id: str,
        conversation_id: str,
        fsm_state: str,
        intent: Optional[str] = None,
        slots: Dict[str, Any] = None,
        next_action: str = "answer",
        meta: Dict[str, Any] = None
    ) -> str:
        """Upsertar estado de diálogo"""
        try:
            result = await self.execute_function(
                "pulpo.upsert_dialogue_state",
                (workspace_id, conversation_id, fsm_state, intent, slots or {}, next_action, meta or {})
            )
            return result
        except Exception as e:
            logger.error(f"Failed to upsert dialogue state: {e}")
            raise QueryError(f"Failed to upsert dialogue state: {e}")
    
    async def apply_dialogue_event(
        self,
        workspace_id: str,
        conversation_id: str,
        event: str,
        payload: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """Aplicar evento a la FSM"""
        try:
            result = await self.execute_function(
                "pulpo.apply_event",
                (workspace_id, conversation_id, event, payload or {})
            )
            return result
        except Exception as e:
            logger.error(f"Failed to apply dialogue event: {e}")
            raise QueryError(f"Failed to apply dialogue event: {e}")
    
    async def search_documents(
        self,
        workspace_id: str,
        query_embedding: List[float],
        similarity_threshold: float = 0.7,
        max_results: int = 5
    ) -> List[Dict[str, Any]]:
        """Buscar documentos por similitud"""
        try:
            result = await self.execute_query(
                "SELECT * FROM pulpo.search_documents($1, $2, $3, $4)",
                (workspace_id, query_embedding, similarity_threshold, max_results)
            )
            return result
        except Exception as e:
            logger.error(f"Failed to search documents: {e}")
            raise QueryError(f"Failed to search documents: {e}")
    
    async def execute_action(
        self,
        workspace_id: str,
        conversation_id: str,
        action_type: str,
        action_data: Dict[str, Any],
        request_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Ejecutar acción de negocio"""
        try:
            result = await self.execute_function(
                "pulpo.execute_action",
                (workspace_id, conversation_id, action_type, action_data, request_id)
            )
            return result
        except Exception as e:
            logger.error(f"Failed to execute action: {e}")
            raise QueryError(f"Failed to execute action: {e}")

# Instancia global del cliente
db_client = DatabaseClient()
