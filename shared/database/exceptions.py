#!/usr/bin/env python3
"""
PulpoAI Shared Database Exceptions
Excepciones compartidas para operaciones de base de datos
"""

class DatabaseError(Exception):
    """Error base de base de datos"""
    pass

class ConnectionError(DatabaseError):
    """Error de conexión a base de datos"""
    pass

class QueryError(DatabaseError):
    """Error en consulta SQL"""
    pass

class TransactionError(DatabaseError):
    """Error en transacción"""
    pass

class RLSError(DatabaseError):
    """Error de Row Level Security"""
    pass

class WorkspaceContextError(RLSError):
    """Error de contexto de workspace"""
    pass

class DialogueStateError(DatabaseError):
    """Error en estado de diálogo"""
    pass

class ActionExecutionError(DatabaseError):
    """Error en ejecución de acción"""
    pass

class DocumentError(DatabaseError):
    """Error en gestión de documentos"""
    pass

class EmbeddingError(DatabaseError):
    """Error en embeddings"""
    pass
