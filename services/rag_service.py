"""
RAG Service - Servicio dedicado para Retrieval Augmented Generation
Implementa búsqueda híbrida (BM25 + Vector) con RRF y filtros por metadata
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import json
import math
import anyio
import uuid
import base64
import hashlib
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from pydantic import BaseModel, Field
import numpy as np
from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
import fastapi

from core.rag.worker_rag_optimized import RAGWorkerOptimized
from utils.ollama_embeddings import OllamaEmbeddings
from utils.db_pool import db_pool
from utils.pgvector_adapter import register_pgvector_adapter
from utils.embedding_cache import embedding_cache
from services.metrics import rag_requests, rag_errors, rag_latency
from dotenv import load_dotenv

load_dotenv()

# Configuración de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Registrar adaptador pgvector
register_pgvector_adapter()

# Constantes de configuración
MAX_QUERY_LEN = int(os.getenv("MAX_QUERY_LEN", "1024"))
MAX_TOP_K = int(os.getenv("MAX_TOP_K", "50"))

# Configuración de paginación
SEARCH_PAGE_SIZE = int(os.getenv("SEARCH_PAGE_SIZE", "10"))
TOPN_BM25_PAGINATED = int(os.getenv("TOPN_BM25_PAGINATED", "120"))
TOPN_VECTOR_PAGINATED = int(os.getenv("TOPN_VECTOR_PAGINATED", "120"))

# Funciones de utilidad para keyset pagination
def _generate_query_hash(query: str, filters: Dict[str, Any], workspace_id: str, hybrid: bool = False) -> str:
    """Genera hash único para query + filters + workspace"""
    content = f"{query}|{json.dumps(filters, sort_keys=True)}|{workspace_id}|{hybrid}"
    return hashlib.sha1(content.encode()).hexdigest()

def _encode_cursor(mode: str, qhash: str, last_score: Optional[float] = None, 
                  last_id: Optional[str] = None, index: Optional[int] = None) -> str:
    """Codifica cursor para paginación"""
    cursor_data = {
        "mode": mode,
        "qhash": qhash,
        "last": {"score": last_score, "id": last_id} if last_score is not None else None,
        "index": index
    }
    return base64.b64encode(json.dumps(cursor_data).encode()).decode()

def _decode_cursor(cursor: str) -> Optional[Dict[str, Any]]:
    """Decodifica cursor de paginación"""
    try:
        cursor_data = json.loads(base64.b64decode(cursor.encode()).decode())
        return cursor_data
    except Exception:
        return None

def _validate_cursor(cursor_data: Dict[str, Any], expected_qhash: str) -> bool:
    """Valida que el cursor corresponde a la query actual"""
    return cursor_data.get("qhash") == expected_qhash

# Funciones de utilidad
def _require_admin(x_admin_token: Optional[str]):
    """Guard de seguridad para endpoints admin"""
    admin_token = os.getenv("ADMIN_TOKEN", "")
    if not admin_token or x_admin_token != admin_token:
        raise HTTPException(status_code=403, detail="forbidden")

def _ws_label(ws: Optional[str]) -> str:
    """Normaliza workspace_id para métricas (control de cardinalidad)"""
    allow = os.getenv("METRICS_WS_LABEL", "full")  # 'full' | 'redact'
    if allow == "redact":
        return "redacted"
    return ws or "unknown"

def _normalize_query(q: str) -> str:
    """Normaliza y valida query"""
    q = " ".join((q or "").split())
    if len(q) > MAX_QUERY_LEN:
        raise HTTPException(status_code=413, detail="query too long")
    return q

def _log_ctx(extra: dict):
    """Filtra contexto de logging (elimina valores None)"""
    return {k: v for k, v in extra.items() if v is not None}

# Middleware de trazabilidad
class TraceHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware para eco de headers de trazabilidad"""
    
    async def dispatch(self, request, call_next):
        rid = request.headers.get("X-Request-Id") or str(uuid.uuid4())
        ws = request.headers.get("X-Workspace-Id")
        
        resp = await call_next(request)
        
        resp.headers["X-Request-Id"] = rid
        if ws:
            resp.headers["X-Workspace-Id"] = ws
        
        return resp

# Modelos Pydantic
class RetrieveContextRequest(BaseModel):
    """Request para retrieve_context"""
    conversation_id: str = Field(..., description="ID de la conversación")
    query: str = Field(..., description="Query de búsqueda")
    slots: Dict[str, Any] = Field(default_factory=dict, description="Slots de la conversación")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filtros adicionales")
    top_k: int = Field(default=8, ge=1, le=20, description="Número de resultados")
    hybrid: bool = Field(default=True, description="Usar búsqueda híbrida")

class SearchRequest(BaseModel):
    """Request para búsqueda general"""
    query: str = Field(..., description="Query de búsqueda")
    workspace_id: str = Field(..., description="ID del workspace")
    filters: Dict[str, Any] = Field(default_factory=dict, description="Filtros por metadata")
    top_k: int = Field(default=10, ge=1, le=50, description="Número de resultados")
    hybrid: bool = Field(default=True, description="Usar búsqueda híbrida")
    similarity_threshold: float = Field(default=0.7, ge=0.0, le=1.0, description="Umbral de similitud")
    cursor: Optional[str] = Field(None, description="Cursor para paginación keyset")
    pagination_mode: Optional[str] = Field(default="native", description="Modo de paginación: native|hybrid")

class SearchResult(BaseModel):
    """Resultado de búsqueda"""
    chunk_id: str = Field(..., description="ID del chunk")
    text: str = Field(..., description="Texto del chunk")
    score: float = Field(..., description="Score de relevancia")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos del chunk")
    file: Dict[str, Any] = Field(default_factory=dict, description="Información del archivo")

class RetrieveContextResponse(BaseModel):
    """Response para retrieve_context"""
    results: List[SearchResult] = Field(..., description="Resultados de búsqueda")
    query: str = Field(..., description="Query original")
    total_results: int = Field(..., description="Total de resultados")
    processing_time: float = Field(..., description="Tiempo de procesamiento en segundos")

class SearchResponse(BaseModel):
    """Response para búsqueda general"""
    results: List[SearchResult] = Field(..., description="Resultados de búsqueda")
    query: str = Field(..., description="Query original")
    total_results: int = Field(..., description="Total de resultados")
    processing_time: float = Field(..., description="Tiempo de procesamiento en segundos")
    search_type: str = Field(..., description="Tipo de búsqueda usado")
    next_cursor: Optional[str] = Field(None, description="Cursor para siguiente página")
    pagination_mode: str = Field(default="native", description="Modo de paginación usado")

class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    timestamp: datetime
    service: str
    version: str

class DocumentVersionRequest(BaseModel):
    """Request para versionado de documentos"""
    document_id: str = Field(..., description="ID del documento")
    content: str = Field(..., description="Contenido de la nueva versión")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Metadatos de la versión")
    created_by: Optional[str] = Field(None, description="ID del usuario que crea la versión")

class DocumentVersionResponse(BaseModel):
    """Response para versionado de documentos"""
    document_id: str
    revision: int
    created_at: datetime
    success: bool

class SoftDeleteRequest(BaseModel):
    """Request para soft delete"""
    document_id: str = Field(..., description="ID del documento a eliminar")
    deleted_by: Optional[str] = Field(None, description="ID del usuario que elimina")

class SoftDeleteResponse(BaseModel):
    """Response para soft delete"""
    document_id: str
    deleted_at: datetime
    success: bool

class RestoreRequest(BaseModel):
    """Request para restaurar documento"""
    document_id: str = Field(..., description="ID del documento a restaurar")

class RestoreResponse(BaseModel):
    """Response para restaurar documento"""
    document_id: str
    restored_at: datetime
    success: bool

class HybridSearchEngine:
    """Motor de búsqueda híbrida con RRF (Reciprocal Rank Fusion)"""
    
    def __init__(self):
        self.rag_worker = RAGWorkerOptimized()
        self.embeddings = OllamaEmbeddings()
        self.k = int(os.getenv("RRF_K", "60"))  # Número de resultados para combinar en RRF
        self.top_n_bm25 = int(os.getenv("TOPN_BM25", "50"))
        self.top_n_vector = int(os.getenv("TOPN_VECTOR", "50"))
        self.embedding_cache = embedding_cache
    
    async def hybrid_search(
        self, 
        workspace_id: str, 
        query: str, 
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """
        Búsqueda híbrida combinando BM25 y búsqueda vectorial con RRF
        """
        try:
            # Sanitizar query
            query = " ".join((query or "").split())
            if not query:
                return []
            
            # 1. Búsqueda BM25 (Full-text search)
            bm25_results = await self._bm25_search(workspace_id, query, filters, self.top_n_bm25)
            
            # 2. Búsqueda vectorial
            vector_results = await self._vector_search(workspace_id, query, filters, self.top_n_vector)
            
            # 3. Combinar con RRF
            combined_results = self._reciprocal_rank_fusion(bm25_results, vector_results)
            
            # 4. Aplicar filtros finales y limitar resultados
            final_results = self._apply_final_filters(combined_results, filters, top_k)
            
            return final_results
            
        except Exception as e:
            logger.error(f"Error en búsqueda híbrida: {e}")
            # Fallback a búsqueda vectorial simple
            return await self._vector_search(workspace_id, query, filters, top_k)
    
    async def _bm25_search(
        self, 
        workspace_id: str, 
        query: str, 
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        cursor_data: Optional[Dict[str, Any]] = None,
        cursor_qhash: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Búsqueda FTS mejorada usando websearch_to_tsquery y columna materializada"""
        try:
            # Construir query SQL con filtros
            where_conditions = ["c.workspace_id = %s"]
            params = [workspace_id]
            
            # Agregar filtros de metadata y rangos
            if filters:
                metadata_filters = filters.get("metadata", {})
                for key, value in metadata_filters.items():
                    if key in ("price", "price_range"):
                        # Soporte para rangos de precio
                        clause, range_params = self._build_range_clause("price", str(value))
                        where_conditions.append(clause)
                        params.extend(range_params)
                    else:
                        if isinstance(value, list) and value:
                            # Soporte para listas (IN)
                            where_conditions.append(f"(lower(c.meta->>%s)) = ANY(%s)")
                            params.extend([key, [str(v).lower() for v in value]])
                        else:
                            # Case-insensitive para strings
                            where_conditions.append(f"lower(c.meta->>%s) = lower(%s)")
                            params.extend([key, str(value)])
            
            where_clause = " AND ".join(where_conditions)
            
            # Keyset pagination para FTS search
            cursor_condition = ""
            if cursor_data and cursor_data.get("mode") == "fts" and cursor_data.get("last"):
                last_score = cursor_data["last"]["score"]
                last_id = cursor_data["last"]["id"]
                cursor_condition = """
                AND (
                    ts_rank(c.tsv, websearch_to_tsquery('spanish', unaccent(%s))) < %s OR
                    (ts_rank(c.tsv, websearch_to_tsquery('spanish', unaccent(%s))) = %s AND c.id > %s)
                )
                """
                where_clause += cursor_condition
                params.extend([query, last_score, query, last_score, last_id])
            
            # Query FTS mejorada con websearch_to_tsquery y soft delete
            sql = f"""
            SELECT 
                c.id as chunk_id,
                c.text,
                c.meta,
                d.title as filename,
                d.id as document_id,
                ts_rank(
                    c.tsv, 
                    websearch_to_tsquery('spanish', unaccent(%s))
                ) as fts_score
            FROM pulpo.chunks c
            JOIN pulpo.documents d ON c.document_id = d.id
            AND d.workspace_id = c.workspace_id
            WHERE {where_clause}
            AND c.tsv @@ websearch_to_tsquery('spanish', unaccent(%s))
            AND c.deleted_at IS NULL
            AND d.deleted_at IS NULL
            ORDER BY fts_score DESC, c.id
            LIMIT %s
            """
            
            params.extend([query, query, limit])
            
            # Ejecutar query usando pool async
            results = await anyio.to_thread.run_sync(
                db_pool.execute_query, sql, params
            )
            
            # Formatear resultados
            formatted_results = []
            for row in results:
                formatted_results.append({
                    "chunk_id": str(row["chunk_id"]),
                    "text": row["text"],
                    "score": float(row["fts_score"]),
                    "metadata": row["meta"] or {},
                    "file": {
                        "id": str(row["document_id"]),
                        "filename": row["filename"]
                    },
                    "search_type": "fts"
                })
            
            # Generar next_cursor si hay más resultados
            next_cursor = None
            if len(formatted_results) == limit and formatted_results:
                last_result = formatted_results[-1]
                # Usar qhash del cursor o del parámetro
                qhash_for_cursor = cursor_data.get("qhash", "") if cursor_data else (cursor_qhash or "")
                next_cursor = _encode_cursor(
                    mode="fts",
                    qhash=qhash_for_cursor,
                    last_score=last_result["score"],
                    last_id=last_result["chunk_id"]
                )
            
            return formatted_results, next_cursor
            
        except Exception as e:
            logger.error(f"Error en búsqueda FTS: {e}")
            return [], None
    
    async def _vector_search(
        self, 
        workspace_id: str, 
        query: str, 
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 50,
        cursor_data: Optional[Dict[str, Any]] = None,
        cursor_qhash: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Búsqueda vectorial usando embeddings con cache"""
        try:
            # Validación de query vacía
            if not (query and query.strip()):
                return [], None
            
            # Obtener embedding del cache o generar nuevo
            query_embedding = self.embedding_cache.get(workspace_id, query)
            if query_embedding is None:
                query_embedding = await self.embeddings.generate_embedding(query)
                self.embedding_cache.set(workspace_id, query, query_embedding)
            
            # Construir query SQL con filtros
            where_conditions = ["ce.workspace_id = %s"]
            params = [workspace_id]
            
            # Agregar filtros de metadata y rangos
            if filters:
                metadata_filters = filters.get("metadata", {})
                for key, value in metadata_filters.items():
                    if key in ("price", "price_range"):
                        # Soporte para rangos de precio
                        clause, range_params = self._build_range_clause("price", str(value))
                        where_conditions.append(clause)
                        params.extend(range_params)
                    else:
                        if isinstance(value, list) and value:
                            # Soporte para listas (IN)
                            where_conditions.append(f"(lower(c.meta->>%s)) = ANY(%s)")
                            params.extend([key, [str(v).lower() for v in value]])
                        else:
                            # Case-insensitive para strings
                            where_conditions.append(f"lower(c.meta->>%s) = lower(%s)")
                            params.extend([key, str(value)])
            
            where_clause = " AND ".join(where_conditions)
            
            # Keyset pagination para vector search
            cursor_condition = ""
            if cursor_data and cursor_data.get("mode") == "vector" and cursor_data.get("last"):
                last_score = cursor_data["last"]["score"]
                last_id = cursor_data["last"]["id"]
                cursor_condition = """
                AND (
                    (ce.embedding <=> %s) > %s OR
                    ((ce.embedding <=> %s) = %s AND c.id > %s)
                )
                """
                where_clause += cursor_condition
                params.extend([query_embedding, last_score, query_embedding, last_score, last_id])
            
            # Query vectorial con similitud coseno y soft delete
            sql = f"""
            SELECT 
                c.id as chunk_id,
                c.text,
                c.meta,
                d.title as filename,
                d.id as document_id,
                1 - (ce.embedding <=> %s) as vector_score
            FROM pulpo.chunk_embeddings ce
            JOIN pulpo.chunks c ON ce.chunk_id = c.id
            JOIN pulpo.documents d ON c.document_id = d.id
            WHERE {where_clause}
              AND c.workspace_id = ce.workspace_id
              AND d.workspace_id = ce.workspace_id
              AND c.deleted_at IS NULL
              AND d.deleted_at IS NULL
              AND ce.deleted_at IS NULL
            ORDER BY ce.embedding <=> %s, c.id
            LIMIT %s
            """
            
            params.extend([query_embedding, query_embedding, limit])
            
            # Ejecutar query usando pool async
            results = await anyio.to_thread.run_sync(
                db_pool.execute_query, sql, params
            )
            
            # Formatear resultados
            formatted_results = []
            for row in results:
                formatted_results.append({
                    "chunk_id": str(row["chunk_id"]),
                    "text": row["text"],
                    "score": float(row["vector_score"]),
                    "metadata": row["meta"] or {},
                    "file": {
                        "id": str(row["document_id"]),
                        "filename": row["filename"]
                    },
                    "search_type": "vector"
                })
            
            # Generar next_cursor si hay más resultados
            next_cursor = None
            if len(formatted_results) == limit and formatted_results:
                last_result = formatted_results[-1]
                # Convertir similitud a distancia para el cursor
                last_distance = 1.0 - float(last_result["score"])
                # Usar qhash del cursor o del parámetro
                qhash_for_cursor = cursor_data.get("qhash", "") if cursor_data else (cursor_qhash or "")
                next_cursor = _encode_cursor(
                    mode="vector",
                    qhash=qhash_for_cursor,
                    last_score=last_distance,  # distancia, no similitud
                    last_id=last_result["chunk_id"]
                )
            
            return formatted_results, next_cursor
            
        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {e}")
            return [], None
    
    async def _hybrid_search_paginated(
        self,
        workspace_id: str,
        query: str,
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 10,
        cursor_data: Optional[Dict[str, Any]] = None,
        cursor_qhash: Optional[str] = None
    ) -> Tuple[List[Dict[str, Any]], Optional[str]]:
        """Búsqueda híbrida con paginación por índice"""
        try:
            # Obtener más resultados para fusionar
            bm25_results, _ = await self._bm25_search(
                workspace_id, query, filters, TOPN_BM25_PAGINATED, cursor_data
            )
            vector_results, _ = await self._vector_search(
                workspace_id, query, filters, TOPN_VECTOR_PAGINATED, cursor_data
            )
            
            # Fusionar con RRF
            fused_results = self._reciprocal_rank_fusion(bm25_results, vector_results)
            
            # Paginación por índice
            start_index = 0
            if cursor_data and cursor_data.get("mode") == "hybrid" and cursor_data.get("index"):
                start_index = cursor_data["index"]
            
            # Obtener página actual
            page_results = fused_results[start_index:start_index + top_k]
            
            # Generar next_cursor si hay más resultados
            next_cursor = None
            if len(fused_results) > start_index + top_k:
                # Usar qhash del cursor o del parámetro
                qhash_for_cursor = cursor_data.get("qhash", "") if cursor_data else (cursor_qhash or "")
                next_cursor = _encode_cursor(
                    mode="hybrid",
                    qhash=qhash_for_cursor,
                    index=start_index + top_k
                )
            
            return page_results, next_cursor
            
        except Exception as e:
            logger.error(f"Error en búsqueda híbrida paginada: {e}")
            return [], None
    
    def _reciprocal_rank_fusion(
        self, 
        bm25_results: List[Dict[str, Any]], 
        vector_results: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Combina resultados de BM25 y vectorial usando Reciprocal Rank Fusion
        """
        # Crear diccionarios para scores
        bm25_scores = {result["chunk_id"]: result["score"] for result in bm25_results}
        vector_scores = {result["chunk_id"]: result["score"] for result in vector_results}
        
        # Obtener todos los chunk_ids únicos
        all_chunk_ids = set(bm25_scores.keys()) | set(vector_scores.keys())
        
        # Calcular RRF scores
        rrf_scores = {}
        for chunk_id in all_chunk_ids:
            bm25_rank = self._get_rank(bm25_results, chunk_id)
            vector_rank = self._get_rank(vector_results, chunk_id)
            
            # RRF formula: 1 / (k + rank)
            rrf_score = 0
            if bm25_rank is not None:
                rrf_score += 1 / (self.k + bm25_rank)
            if vector_rank is not None:
                rrf_score += 1 / (self.k + vector_rank)
            
            rrf_scores[chunk_id] = rrf_score
        
        # Combinar resultados y ordenar por RRF score
        combined_results = []
        for chunk_id, rrf_score in rrf_scores.items():
            # Obtener datos del resultado (preferir BM25 si existe)
            result_data = None
            for result in bm25_results:
                if result["chunk_id"] == chunk_id:
                    result_data = result
                    break
            
            if not result_data:
                for result in vector_results:
                    if result["chunk_id"] == chunk_id:
                        result_data = result
                        break
            
            if result_data:
                result_data["score"] = rrf_score
                result_data["search_type"] = "hybrid"
                combined_results.append(result_data)
        
        # Ordenar por RRF score descendente
        combined_results.sort(key=lambda x: x["score"], reverse=True)
        
        return combined_results
    
    def _get_rank(self, results: List[Dict[str, Any]], chunk_id: str) -> Optional[int]:
        """Obtiene el rank de un chunk en una lista de resultados"""
        for i, result in enumerate(results):
            if result["chunk_id"] == chunk_id:
                return i + 1  # Rank basado en 1
        return None
    
    def _apply_final_filters(
        self, 
        results: List[Dict[str, Any]], 
        filters: Optional[Dict[str, Any]] = None,
        top_k: int = 8
    ) -> List[Dict[str, Any]]:
        """Aplica filtros finales, MMR para diversidad y limita resultados"""
        if not results:
            return results
        
        # Aplicar filtros adicionales si existen
        filtered_results = results
        if filters:
            filtered_results = []
            for result in results:
                if self._matches_filters(result, filters):
                    filtered_results.append(result)
        
        # Aplicar MMR para diversidad
        diverse_results = self._apply_mmr_diversity(filtered_results, lambda_mult=0.7, top_k=top_k)
        
        return diverse_results
    
    def _matches_filters(self, result: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Verifica si un resultado coincide con los filtros"""
        metadata = result.get("metadata", {})
        
        # Filtros de metadata
        if "metadata" in filters:
            for key, value in filters["metadata"].items():
                if metadata.get(key) != value:
                    return False
        
        # Filtros de archivo
        if "file" in filters:
            file_info = result.get("file", {})
            for key, value in filters["file"].items():
                if file_info.get(key) != value:
                    return False
        
        return True
    
    def _build_range_clause(self, field: str, rng: str, table_alias: str = "c") -> Tuple[str, list]:
        """Construye cláusula SQL para filtros de rango"""
        try:
            # normalización: quito espacios y convierto coma decimal a punto
            rng = (rng or "").strip().replace(",", ".")
        except Exception:
            # fallback safe: condición imposible
            return ("1=0", [])

        if "-" in rng:
            # Rango: "50000-80000"
            lo, hi = [p.strip() for p in rng.split("-", 1)]
            return (f"({table_alias}.meta->>'{field}')::numeric BETWEEN %s AND %s", [lo or "0", hi or "0"])
        elif rng.startswith(">="):
            # Mayor o igual: ">=60000"
            return (f"({table_alias}.meta->>'{field}')::numeric >= %s", [rng[2:].strip()])
        elif rng.startswith("<="):
            # Menor o igual: "<=90000"
            return (f"({table_alias}.meta->>'{field}')::numeric <= %s", [rng[2:].strip()])
        elif rng.startswith(">"):
            # Mayor: ">60000"
            return (f"({table_alias}.meta->>'{field}')::numeric > %s", [rng[1:].strip()])
        elif rng.startswith("<"):
            # Menor: "<90000"
            return (f"({table_alias}.meta->>'{field}')::numeric < %s", [rng[1:].strip()])
        else:
            # Igualdad exacta
            return (f"({table_alias}.meta->>'{field}')::numeric = %s", [rng.strip()])
    
    def _apply_mmr_diversity(self, results: List[Dict[str, Any]], lambda_mult: float = 0.7, top_k: int = 8) -> List[Dict[str, Any]]:
        """Aplica Maximum Marginal Relevance para diversidad de resultados"""
        if not results or len(results) <= top_k:
            return results[:top_k]
        
        selected = []
        doc_counts = {}  # Contador de apariciones por documento
        remaining = results.copy()
        
        # Cache de texto corto para similitud rápida (Jaccard sobre shingles simple)
        def _sim(a: str, b: str) -> float:
            sa, sb = set(a.lower().split()[:40]), set(b.lower().split()[:40])
            if not sa or not sb: 
                return 0.0
            inter = len(sa & sb)
            union = len(sa | sb)
            return inter / union if union > 0 else 0.0
        
        while remaining and len(selected) < top_k:
            best_score = -1
            best_idx = 0
            
            for i, result in enumerate(remaining):
                # Score base (normalizado por posición)
                base_score = result["score"]
                
                # Penalizar documentos ya seleccionados (penalización progresiva)
                doc_id = result["file"].get("id")
                doc_count = doc_counts.get(doc_id, 0)
                diversity_penalty = 0.3 * (doc_count + 1)  # Penalización progresiva
                
                # Penaliza similitud con ya seleccionados (MMR light)
                redundancy = 0.0
                for s in selected:
                    redundancy = max(redundancy, _sim(result["text"], s["text"]))
                
                # Score final con diversidad y redundancia
                final_score = lambda_mult * base_score - (1 - lambda_mult) * redundancy - diversity_penalty
                
                if final_score > best_score:
                    best_score = final_score
                    best_idx = i
            
            # Agregar el mejor resultado
            best_result = remaining.pop(best_idx)
            selected.append(best_result)
            doc_id = best_result["file"].get("id")
            doc_counts[doc_id] = doc_counts.get(doc_id, 0) + 1
        
        return selected

class RAGService:
    """Servicio principal de RAG"""
    
    def __init__(self):
        self.search_engine = HybridSearchEngine()
    
    async def retrieve_context(self, request: RetrieveContextRequest, workspace_id: str) -> RetrieveContextResponse:
        """
        Endpoint principal para retrieve_context - usado por el orquestador
        """
        from time import perf_counter
        
        ws = workspace_id
        ws_label = _ws_label(ws)
        start_dt = datetime.now()
        start_t = perf_counter()
        
        try:
            # Normalizar query
            q_norm = _normalize_query(request.query)
            
            # Logging estructurado
            logger.info("Retrieve context start", extra=_log_ctx({
                "rid": request.conversation_id,
                "ws": ws,
                "q": q_norm[:120],
                "hybrid": request.hybrid,
                "top_k": request.top_k
            }))
            
            # Construir filtros desde slots
            filters = self._build_filters_from_slots(request.slots, request.filters)
            
            # Realizar búsqueda híbrida
            t0 = datetime.now()
            if request.hybrid:
                results = await self.search_engine.hybrid_search(
                    workspace_id=workspace_id,
                    query=q_norm,
                    filters=filters,
                    top_k=min(request.top_k, MAX_TOP_K)
                )
            else:
                # Solo búsqueda vectorial
                results = await self.search_engine._vector_search(
                    workspace_id=workspace_id,
                    query=q_norm,
                    filters=filters,
                    limit=min(request.top_k, MAX_TOP_K)
                )
            t1 = datetime.now()
            
            # Telemetría útil
            logger.info(f"[rag] cid={request.conversation_id} q='{q_norm[:60]}' "
                       f"hybrid={request.hybrid} k={request.top_k} "
                       f"ms={int((t1-t0).total_seconds()*1000)}")
            
            # Convertir a formato de respuesta
            search_results = []
            for result in results:
                # Truncado seguro del texto para payloads optimizados
                txt = result["text"]
                if len(txt) > 1200:
                    txt = txt[:1197] + "..."
                
                search_results.append(SearchResult(
                    chunk_id=result["chunk_id"],
                    text=txt,
                    score=result["score"],
                    metadata=result["metadata"],
                    file=result["file"]
                ))
            
            processing_time = (datetime.now() - start_dt).total_seconds()
            
            # Métricas de éxito
            rag_requests.labels("retrieve_context", ws_label, "200").inc()
            rag_latency.labels("retrieve_context", ws_label).observe(perf_counter() - start_t)
            
            return RetrieveContextResponse(
                results=search_results,
                query=request.query,
                total_results=len(search_results),
                processing_time=processing_time
            )
            
        except Exception as e:
            # Métricas de error
            rag_errors.labels("retrieve_context", ws_label).inc()
            rag_requests.labels("retrieve_context", ws_label, "500").inc()
            rag_latency.labels("retrieve_context", ws_label).observe(perf_counter() - start_t)
            
            logger.error(f"Error en retrieve_context: {e}")
            raise HTTPException(status_code=500, detail=f"Error en retrieve_context: {str(e)}")
    
    async def search(self, request: SearchRequest) -> SearchResponse:
        """
        Endpoint de búsqueda general
        """
        from time import perf_counter
        
        ws = request.workspace_id
        ws_label = _ws_label(ws)
        start_dt = datetime.now()
        start_t = perf_counter()
        
        try:
            # Normalizar y validar query
            q_norm = _normalize_query(request.query)
            if not q_norm:
                raise HTTPException(status_code=400, detail="query cannot be empty")
            
            # Limitar top_k
            request.top_k = min(request.top_k, MAX_TOP_K)
            
            # Logging estructurado
            logger.info("Search start", extra=_log_ctx({
                "ws": ws,
                "q": q_norm[:120],
                "hybrid": request.hybrid,
                "top_k": request.top_k
            }))
            
            # Decodificar cursor si existe
            cursor_data = None
            if request.cursor:
                cursor_data = _decode_cursor(request.cursor)
                if not cursor_data:
                    raise HTTPException(status_code=400, detail="Invalid cursor format")
                
                # Validar que el cursor corresponde a la query actual
                expected_qhash = _generate_query_hash(q_norm, request.filters, request.workspace_id, request.hybrid)
                if not _validate_cursor(cursor_data, expected_qhash):
                    raise HTTPException(status_code=400, detail="Cursor does not match current query")
            
            # Realizar búsqueda con keyset pagination
            if request.hybrid and request.pagination_mode == "hybrid":
                # Búsqueda híbrida con paginación por índice
                results, next_cursor = await self._hybrid_search_paginated(
                    workspace_id=request.workspace_id,
                    query=q_norm,
                    filters=request.filters,
                    top_k=request.top_k,
                    cursor_data=cursor_data,
                    cursor_qhash=expected_qhash
                )
                search_type = "hybrid"
            elif request.hybrid:
                # Búsqueda híbrida nativa (sin paginación)
                results = await self.search_engine.hybrid_search(
                    workspace_id=request.workspace_id,
                    query=q_norm,
                    filters=request.filters,
                    top_k=request.top_k
                )
                next_cursor = None
                search_type = "hybrid"
            else:
                # Solo búsqueda vectorial con keyset pagination
                results, next_cursor = await self.search_engine._vector_search(
                    workspace_id=request.workspace_id,
                    query=q_norm,
                    filters=request.filters,
                    limit=request.top_k,
                    cursor_data=cursor_data,
                    cursor_qhash=expected_qhash
                )
                search_type = "vector"
            
            # Filtrar por umbral de similitud (solo para búsqueda vectorial pura)
            if search_type == "vector":
                filtered_results = [
                    result for result in results 
                    if result["score"] >= request.similarity_threshold
                ]
            else:
                # Para búsqueda híbrida, no aplicar umbral de similitud
                # porque los scores RRF no están en [0,1]
                filtered_results = results
            
            # Convertir a formato de respuesta
            search_results = []
            for result in filtered_results:
                # Truncado seguro del texto para payloads optimizados
                txt = result["text"]
                if len(txt) > 1200:
                    txt = txt[:1197] + "..."
                
                search_results.append(SearchResult(
                    chunk_id=result["chunk_id"],
                    text=txt,
                    score=result["score"],
                    metadata=result["metadata"],
                    file=result["file"]
                ))
            
            processing_time = (datetime.now() - start_dt).total_seconds()
            
            # Métricas de éxito
            rag_requests.labels("search", ws_label, "200").inc()
            rag_latency.labels("search", ws_label).observe(perf_counter() - start_t)
            
            return SearchResponse(
                results=search_results,
                query=request.query,
                total_results=len(search_results),
                processing_time=processing_time,
                search_type=search_type,
                next_cursor=next_cursor,
                pagination_mode=request.pagination_mode
            )
            
        except fastapi.HTTPException as he:
            # Métricas para errores HTTP
            rag_requests.labels("search", ws_label, str(he.status_code)).inc()
            if he.status_code >= 500:
                rag_errors.labels("search", ws_label).inc()
            rag_latency.labels("search", ws_label).observe(perf_counter() - start_t)
            raise
        except Exception as e:
            # Métricas para errores generales
            rag_errors.labels("search", ws_label).inc()
            rag_requests.labels("search", ws_label, "500").inc()
            rag_latency.labels("search", ws_label).observe(perf_counter() - start_t)
            
            logger.error(f"Error en search: {e}")
            raise HTTPException(status_code=500, detail=f"Error en search: {str(e)}")
    
    def _build_filters_from_slots(
        self, 
        slots: Dict[str, Any], 
        additional_filters: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Construye filtros de búsqueda desde los slots de la conversación"""
        filters = additional_filters.copy()
        
        # Agregar filtros desde slots
        if "categoria" in slots:
            filters.setdefault("metadata", {})["category"] = slots["categoria"]

        # Normalizamos: el orchestrator usa "city" (no "zone")
        if "zone" in slots and slots["zone"]:
            filters.setdefault("metadata", {})["city"] = slots["zone"]
        if "city" in slots and slots["city"]:
            filters.setdefault("metadata", {})["city"] = slots["city"]
        
        if "operation" in slots:
            filters.setdefault("metadata", {})["operation"] = slots["operation"]
        
        return filters
    
    async def create_document_version(self, request: DocumentVersionRequest) -> DocumentVersionResponse:
        """
        Crea una nueva versión de un documento
        """
        try:
            # Llamar a la función SQL para crear revisión
            sql = "SELECT pulpo.create_document_revision(%s, %s, %s, %s) as revision"
            params = [request.document_id, request.content, request.metadata, request.created_by]
            
            result = await anyio.to_thread.run_sync(
                db_pool.execute_query_single, sql, params
            )
            
            if result and result["revision"]:
                return DocumentVersionResponse(
                    document_id=request.document_id,
                    revision=result["revision"],
                    created_at=datetime.now(),
                    success=True
                )
            else:
                raise HTTPException(status_code=400, detail="No se pudo crear la versión")
                
        except Exception as e:
            logger.error(f"Error creando versión de documento: {e}")
            raise HTTPException(status_code=500, detail=f"Error creando versión: {str(e)}")
    
    async def soft_delete_document(self, request: SoftDeleteRequest) -> SoftDeleteResponse:
        """
        Elimina un documento de forma soft (reversible)
        """
        try:
            # Llamar a la función SQL para soft delete
            sql = "SELECT pulpo.soft_delete_document(%s, %s) as success"
            params = [request.document_id, request.deleted_by]
            
            result = await anyio.to_thread.run_sync(
                db_pool.execute_query_single, sql, params
            )
            
            if result and result["success"]:
                return SoftDeleteResponse(
                    document_id=request.document_id,
                    deleted_at=datetime.now(),
                    success=True
                )
            else:
                raise HTTPException(status_code=404, detail="Documento no encontrado")
                
        except Exception as e:
            logger.error(f"Error en soft delete: {e}")
            raise HTTPException(status_code=500, detail=f"Error eliminando documento: {str(e)}")
    
    async def restore_document(self, request: RestoreRequest) -> RestoreResponse:
        """
        Restaura un documento eliminado con soft delete
        """
        try:
            # Llamar a la función SQL para restaurar
            sql = "SELECT pulpo.restore_document(%s) as success"
            params = [request.document_id]
            
            result = await anyio.to_thread.run_sync(
                db_pool.execute_query_single, sql, params
            )
            
            if result and result["success"]:
                return RestoreResponse(
                    document_id=request.document_id,
                    restored_at=datetime.now(),
                    success=True
                )
            else:
                raise HTTPException(status_code=404, detail="Documento no encontrado o ya activo")
                
        except Exception as e:
            logger.error(f"Error restaurando documento: {e}")
            raise HTTPException(status_code=500, detail=f"Error restaurando documento: {str(e)}")
    
    async def get_document_versions(self, document_id: str) -> List[Dict[str, Any]]:
        """
        Obtiene todas las versiones de un documento
        """
        try:
            sql = """
            SELECT id, revision, content, metadata, created_at, created_by
            FROM pulpo.document_revisions
            WHERE document_id = %s
            ORDER BY revision DESC
            """
            params = [document_id]
            
            results = await anyio.to_thread.run_sync(
                db_pool.execute_query, sql, params
            )
            
            return results
            
        except Exception as e:
            logger.error(f"Error obteniendo versiones: {e}")
            raise HTTPException(status_code=500, detail=f"Error obteniendo versiones: {str(e)}")
    
    async def purge_deleted_documents(self, retention_days: int = 7) -> Dict[str, int]:
        """
        Purga documentos eliminados después de N días
        """
        try:
            sql = "SELECT * FROM pulpo.purge_deleted_documents(%s)"
            params = [retention_days]
            
            result = await anyio.to_thread.run_sync(
                db_pool.execute_query_single, sql, params
            )
            
            if result:
                return {
                    "deleted_count": result["deleted_count"],
                    "purged_documents": result["purged_documents"]
                }
            else:
                return {"deleted_count": 0, "purged_documents": 0}
                
        except Exception as e:
            logger.error(f"Error en purga: {e}")
            raise HTTPException(status_code=500, detail=f"Error en purga: {str(e)}")

# 1) Lifespan manager PRIMERO
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan manager para startup y shutdown"""
    logger.info("🚀 RAG Service v2.0.0 iniciado")
    
    # Verificar extensiones requeridas
    try:
        await anyio.to_thread.run_sync(
            db_pool.execute_query,
            "SELECT extname FROM pg_extension WHERE extname='unaccent';",
            []
        )
        logger.info("✅ Extensión 'unaccent' disponible")
    except Exception:
        logger.warning("⚠️ 'unaccent' no disponible. FTS funcionará sin normalizar tildes.")

    # Verificar pgcrypto para gen_random_uuid()
    try:
        await anyio.to_thread.run_sync(
            db_pool.execute_query,
            "CREATE EXTENSION IF NOT EXISTS pgcrypto;",
            []
        )
        logger.info("✅ Extensión 'pgcrypto' verificada")
    except Exception:
        logger.warning("⚠️ No pude asegurar pgcrypto; gen_random_uuid() podría fallar si no existe.")
    
    logger.info("✨ Mejoras implementadas:")
    logger.info("  - Pool de conexiones async con anyio.to_thread")
    logger.info("  - Cache de embeddings con TTL")
    logger.info("  - FTS mejorado con websearch_to_tsquery + unaccent")
    logger.info("  - MMR real con similaridad semántica")
    logger.info("  - Filtros expresivos (listas, case-insensitive)")
    logger.info("  - Joins multitenant blindados")
    logger.info("  - Parametrización por ENV")
    logger.info("  - Telemetría mejorada")
    logger.info("  - Soft delete + versionado de documentos")
    logger.info("  - Job nocturno de purga automática")
    logger.info("  - OCR asíncrono con reintentos")
    logger.info("  - Métricas Prometheus por workspace")
    logger.info("  - Sistema de retries con backoff exponencial")
    logger.info("  - Scheduler genérico con DLQ")
    logger.info("📋 Endpoints disponibles:")
    logger.info("  - POST /tools/retrieve_context - Retrieve context para orquestador")
    logger.info("  - POST /search - Búsqueda general")
    logger.info("  - GET /search/simple - Búsqueda simple")
    logger.info("  - GET /search/menu - Búsqueda de menús")
    logger.info("  - POST /search/test - Testing")
    logger.info("  - GET /health - Health check")
    logger.info("  - GET /stats - Estadísticas del servicio")
    logger.info("  - GET /metrics - Métricas Prometheus")
    logger.info("  - POST /documents/version - Crear versión de documento")
    logger.info("  - POST /documents/soft-delete - Eliminar documento")
    logger.info("  - POST /documents/restore - Restaurar documento")
    logger.info("  - GET /documents/{id}/versions - Listar versiones")
    logger.info("  - POST /admin/purge-deleted - Purga manual (admin)")
    logger.info("  - POST /admin/ocr/run-once - Ejecutar OCR (admin)")
    logger.info("  - POST /admin/ocr/enable - Habilitar OCR (admin)")
    logger.info("  - GET /admin/ocr/stats - Stats OCR (admin)")
    logger.info("  - POST /admin/jobs/requeue - Requeue jobs (admin)")
    logger.info("  - GET /admin/jobs/dlq - Listar DLQ (admin)")
    logger.info("  - GET /admin/jobs/stats - Stats jobs (admin)")

    yield

    logger.info("🛑 RAG Service cerrando...")

# 2) Luego crea la app
app = FastAPI(
    title="PulpoAI RAG Service",
    description="Servicio de Retrieval Augmented Generation con búsqueda híbrida",
    version="2.0.0",
    lifespan=lifespan
)

# 3) Middleware de trazabilidad
app.add_middleware(TraceHeadersMiddleware)

# 4) CORS middleware endurecido
allowed_origins = os.getenv("CORS_ALLOW_ORIGINS", "*").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 5) Instancia del servicio
rag_service = RAGService()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del servicio"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(),
        service="rag",
        version="2.0.0"
    )

@app.get("/stats")
async def get_stats():
    """Estadísticas del servicio"""
    return {
        "embedding_cache": embedding_cache.get_stats(),
        "service": "rag",
        "version": "2.0.0",
        "timestamp": datetime.now()
    }

@app.get("/metrics")
async def metrics(x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")):
    """Endpoint de métricas Prometheus"""
    if os.getenv("METRICS_PROTECTED", "false").lower() == "true":
        _require_admin(x_admin_token)
    data = generate_latest()
    return fastapi.Response(content=data, media_type=CONTENT_TYPE_LATEST)

# Endpoints para gestión de documentos (Sprint 1)
@app.post("/documents/version", response_model=DocumentVersionResponse)
async def create_document_version(request: DocumentVersionRequest):
    """
    Crea una nueva versión de un documento
    """
    return await rag_service.create_document_version(request)

@app.post("/documents/soft-delete", response_model=SoftDeleteResponse)
async def soft_delete_document(request: SoftDeleteRequest):
    """
    Elimina un documento de forma soft (reversible)
    """
    return await rag_service.soft_delete_document(request)

@app.post("/documents/restore", response_model=RestoreResponse)
async def restore_document(request: RestoreRequest):
    """
    Restaura un documento eliminado con soft delete
    """
    return await rag_service.restore_document(request)

@app.get("/documents/{document_id}/versions")
async def get_document_versions(document_id: str):
    """
    Obtiene todas las versiones de un documento
    """
    versions = await rag_service.get_document_versions(document_id)
    return {
        "document_id": document_id,
        "versions": versions,
        "total_versions": len(versions)
    }

@app.post("/admin/purge-deleted")
async def purge_deleted_documents(
    retention_days: int = 7,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Purga documentos eliminados después de N días (solo admin)
    """
    _require_admin(x_admin_token)
    
    result = await rag_service.purge_deleted_documents(retention_days)
    return {
        "message": f"Purga completada",
        "retention_days": retention_days,
        **result
    }

# Endpoints de control OCR (Sprint 2)
@app.post("/admin/ocr/run-once")
async def ocr_run_once(
    batch_size: int = 10,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Ejecuta una pasada de OCR (solo admin)
    """
    _require_admin(x_admin_token)

    from services.ocr_worker import OCRWorker
    worker = OCRWorker()
    processed = await worker.run_once(batch_size)
    return {"processed": processed}

@app.post("/admin/ocr/enable")
async def enable_ocr_for_document(
    document_id: str,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Habilita OCR para un documento específico (solo admin)
    """
    _require_admin(x_admin_token)

    sql = "UPDATE pulpo.documents SET needs_ocr=true, ocr_processed=false WHERE id=%s AND deleted_at IS NULL"
    await anyio.to_thread.run_sync(db_pool.execute_query, sql, [document_id])
    return {"document_id": document_id, "needs_ocr": True}

@app.get("/admin/ocr/stats")
async def ocr_stats(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Estadísticas del worker OCR (solo admin)
    """
    _require_admin(x_admin_token)

    from services.ocr_worker import OCRWorker
    worker = OCRWorker()
    stats = await worker.get_stats()
    return stats

# Endpoints de gestión de jobs (Sprint 3)
@app.post("/admin/jobs/requeue")
async def admin_requeue_jobs(
    job_type: Optional[str] = None,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Reencola jobs fallidos (solo admin)
    """
    _require_admin(x_admin_token)
    
    sql = "SELECT pulpo.requeue_failed_jobs(%s) AS count"
    row = await anyio.to_thread.run_sync(db_pool.execute_query_single, sql, [job_type])
    return {"requeued": row["count"], "job_type": job_type}

@app.post("/admin/jobs/requeue-one")
async def admin_requeue_one(
    job_id: str,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Reencola un job específico (solo admin)
    """
    _require_admin(x_admin_token)
    
    sql = "SELECT pulpo.requeue_job(%s) AS ok"
    row = await anyio.to_thread.run_sync(db_pool.execute_query_single, sql, [job_id])
    return {"job_id": job_id, "ok": bool(row["ok"])}

@app.post("/admin/jobs/pause")
async def admin_pause_job(
    job_id: str,
    pause: bool = True,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Pausa/reanuda un job específico (solo admin)
    """
    _require_admin(x_admin_token)
    
    sql = "UPDATE pulpo.processing_jobs SET paused=%s, updated_at=now() WHERE id=%s"
    await anyio.to_thread.run_sync(db_pool.execute_query, sql, [pause, job_id])
    return {"job_id": job_id, "paused": pause}

@app.get("/admin/jobs/dlq")
async def admin_list_dlq(
    job_type: Optional[str] = None,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Lista jobs en DLQ (Dead Letter Queue) (solo admin)
    """
    _require_admin(x_admin_token)
    
    if job_type:
        sql = "SELECT * FROM pulpo.processing_jobs_dlq WHERE job_type=%s ORDER BY updated_at DESC"
        rows = await anyio.to_thread.run_sync(db_pool.execute_query, sql, [job_type])
    else:
        sql = "SELECT * FROM pulpo.processing_jobs_dlq ORDER BY updated_at DESC"
        rows = await anyio.to_thread.run_sync(db_pool.execute_query, sql, [])
    
    return {"items": rows, "total": len(rows), "job_type": job_type}

@app.get("/admin/jobs/stats")
async def admin_job_stats(
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Estadísticas de jobs (solo admin)
    """
    _require_admin(x_admin_token)
    
    sql = "SELECT * FROM pulpo.get_job_stats()"
    stats = await anyio.to_thread.run_sync(db_pool.execute_query, sql, [])
    
    # Estadísticas del scheduler
    try:
        from services.job_scheduler import get_scheduler_stats
        scheduler_stats = await get_scheduler_stats()
    except Exception as e:
        scheduler_stats = {"error": str(e)}
    
    return {
        "job_stats": stats,
        "scheduler_stats": scheduler_stats
    }

@app.get("/admin/jobs/next")
async def admin_next_jobs(
    limit: int = 10,
    x_admin_token: Optional[str] = Header(None, alias="X-Admin-Token")
):
    """
    Lista próximos jobs a ejecutar (solo admin)
    """
    _require_admin(x_admin_token)
    
    sql = "SELECT * FROM pulpo.get_next_jobs(%s)"
    rows = await anyio.to_thread.run_sync(db_pool.execute_query, sql, [limit])
    return {"items": rows, "total": len(rows), "limit": limit}

@app.post("/tools/retrieve_context", response_model=RetrieveContextResponse)
async def retrieve_context(
    request: RetrieveContextRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """
    Endpoint principal para retrieve_context - usado por el orquestador
    """
    return await rag_service.retrieve_context(request, workspace_id=x_workspace_id)

@app.post("/search", response_model=SearchResponse)
async def search(
    request: SearchRequest,
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    """
    Endpoint de búsqueda general
    """
    # Si vino header, enforce match para evitar cross-tenant accidental
    if x_workspace_id and x_workspace_id != request.workspace_id:
        raise HTTPException(status_code=403, detail="workspace_id mismatch")
    if x_request_id:
        logger.info(f"[search] request_id={x_request_id}")
    return await rag_service.search(request)

@app.get("/search/simple")
async def simple_search(
    query: str,
    workspace_id: str,
    top_k: int = 10,
    hybrid: bool = True
):
    """
    Endpoint de búsqueda simple
    """
    request = SearchRequest(
        query=query,
        workspace_id=workspace_id,
        top_k=top_k,
        hybrid=hybrid
    )
    
    response = await rag_service.search(request)
    
    # Formatear para compatibilidad con API anterior
    return {
        "query": response.query,
        "results": [
            {
                "content": result.text,
                "similarity": result.score,
                "source": result.file.get("filename", "documento"),
                "metadata": result.metadata
            }
            for result in response.results
        ],
        "total": response.total_results,
        "processing_time": response.processing_time
    }

@app.get("/search/menu")
async def search_menu(
    query: str,
    workspace_id: str,
    top_k: int = 5
):
    """
    Endpoint específico para búsqueda de menús
    """
    filters = {
        "metadata": {"document_type": "menu"}
    }
    
    request = SearchRequest(
        query=query,
        workspace_id=workspace_id,
        filters=filters,
        top_k=top_k,
        hybrid=True
    )
    
    response = await rag_service.search(request)
    
    return {
        "query": response.query,
        "menu_results": [
            {
                "content": result.text,
                "similarity": result.score,
                "source": result.file.get("filename", "menú"),
                "metadata": result.metadata
            }
            for result in response.results
        ],
        "total": response.total_results
    }

@app.post("/search/test")
async def test_search():
    """
    Endpoint de testing para validar el funcionamiento del RAG
    """
    try:
        # Test con query de ejemplo
        test_request = SearchRequest(
            query="empanadas de carne",
            workspace_id="test-workspace",
            top_k=5,
            hybrid=True
        )
        
        response = await rag_service.search(test_request)
        
        return {
            "test": "success",
            "query": test_request.query,
            "results_count": len(response.results),
            "search_type": response.search_type,
            "processing_time": response.processing_time
        }
        
    except Exception as e:
        logger.error(f"Error en test: {e}")
        raise HTTPException(status_code=500, detail=f"Error en test: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "rag_service:app",
        host="0.0.0.0",
        port=8003,
        reload=True,
        log_level="info"
    )
