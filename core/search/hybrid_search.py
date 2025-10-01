#!/usr/bin/env python3
"""
Sistema de Búsqueda Híbrida BM25 + Vector con RRF
Implementa búsqueda combinada usando PostgreSQL BM25 y Weaviate Vector
"""

import os
import json
import logging
import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
import weaviate
from weaviate.classes.query import MetadataQuery

from utils.ollama_embeddings import OllamaEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Resultado de búsqueda unificado"""
    chunk_id: str
    chunk_text: str
    similarity_score: float
    search_rank: int
    metadata: Dict[str, Any]
    filename: str
    vertical: str
    document_type: str
    search_method: str  # "bm25", "vector", "hybrid"

@dataclass
class HybridSearchConfig:
    """Configuración para búsqueda híbrida"""
    bm25_weight: float = 0.4
    vector_weight: float = 0.6
    rrf_k: int = 60  # Parámetro RRF
    max_results_per_method: int = 20
    final_limit: int = 10

class HybridSearchEngine:
    """Motor de búsqueda híbrida BM25 + Vector con RRF"""
    
    def __init__(self):
        self.db_url = os.getenv('DATABASE_URL')
        self.weaviate_url = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
        self.ollama_embeddings = OllamaEmbeddings()
        self.config = HybridSearchConfig()
        
        # Inicializar cliente Weaviate
        try:
            self.weaviate_client = weaviate.connect_to_local(
                host="localhost",
                port=8080,
                grpc_port=50051
            )
            logger.info("Conectado a Weaviate")
        except Exception as e:
            logger.error(f"Error conectando a Weaviate: {e}")
            self.weaviate_client = None
    
    async def search(
        self,
        query: str,
        workspace_id: str,
        limit: int = 10,
        filters: Optional[Dict[str, Any]] = None,
        search_type: str = "hybrid"
    ) -> List[SearchResult]:
        """
        Realiza búsqueda híbrida
        
        Args:
            query: Consulta de búsqueda
            workspace_id: ID del workspace
            limit: Número máximo de resultados
            filters: Filtros adicionales
            search_type: "bm25", "vector", "hybrid"
        
        Returns:
            Lista de resultados ordenados por relevancia
        """
        try:
            if search_type == "bm25":
                return await self._bm25_search(query, workspace_id, limit, filters)
            elif search_type == "vector":
                return await self._vector_search(query, workspace_id, limit, filters)
            elif search_type == "hybrid":
                return await self._hybrid_search(query, workspace_id, limit, filters)
            else:
                raise ValueError(f"Tipo de búsqueda no soportado: {search_type}")
                
        except Exception as e:
            logger.error(f"Error en búsqueda híbrida: {e}")
            return []
    
    async def _bm25_search(
        self,
        query: str,
        workspace_id: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Búsqueda BM25 usando PostgreSQL full-text search"""
        
        try:
            with psycopg2.connect(self.db_url) as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    # Construir filtros WHERE
                    where_conditions = [
                        "f.workspace_id = %s",
                        "f.deleted_at IS NULL",
                        "to_tsvector('spanish', fc.chunk_text) @@ plainto_tsquery('spanish', %s)"
                    ]
                    params = [workspace_id, query]
                    
                    # Agregar filtros adicionales
                    if filters:
                        if 'vertical' in filters:
                            where_conditions.append("f.vertical = %s")
                            params.append(filters['vertical'])
                        if 'document_type' in filters:
                            where_conditions.append("f.document_type = %s")
                            params.append(filters['document_type'])
                        if 'metadata' in filters:
                            for key, value in filters['metadata'].items():
                                where_conditions.append(f"fc.chunk_metadata->>%s = %s")
                                params.extend([key, str(value)])
                    
                    where_clause = " AND ".join(where_conditions)
                    params.append(limit)
                    
                    # Query BM25 con ranking
                    cur.execute(f"""
                        SELECT 
                            fc.id as chunk_id,
                            fc.chunk_text,
                            fc.chunk_metadata,
                            f.original_filename as filename,
                            f.vertical,
                            f.document_type,
                            ts_rank(to_tsvector('spanish', fc.chunk_text), plainto_tsquery('spanish', %s)) as bm25_score
                        FROM pulpo.file_chunks fc
                        JOIN pulpo.files f ON fc.file_id = f.id
                        WHERE {where_clause}
                        ORDER BY bm25_score DESC
                        LIMIT %s
                    """, [query] + params)
                    
                    results = cur.fetchall()
                    
                    # Convertir a SearchResult
                    search_results = []
                    for i, row in enumerate(results):
                        search_results.append(SearchResult(
                            chunk_id=str(row['chunk_id']),
                            chunk_text=row['chunk_text'],
                            similarity_score=float(row['bm25_score']),
                            search_rank=i + 1,
                            metadata=row['chunk_metadata'] or {},
                            filename=row['filename'],
                            vertical=row['vertical'] or '',
                            document_type=row['document_type'] or '',
                            search_method="bm25"
                        ))
                    
                    return search_results
                    
        except Exception as e:
            logger.error(f"Error en búsqueda BM25: {e}")
            return []
    
    async def _vector_search(
        self,
        query: str,
        workspace_id: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Búsqueda vectorial usando Weaviate"""
        
        if not self.weaviate_client:
            logger.warning("Weaviate no disponible, usando búsqueda BM25 como fallback")
            return await self._bm25_search(query, workspace_id, limit, filters)
        
        try:
            # Generar embedding de la consulta
            query_embedding = await self.ollama_embeddings.generate_embedding(query)
            
            # Construir filtros para Weaviate
            weaviate_filters = {
                "workspace_id": {"Equal": workspace_id}
            }
            
            if filters:
                if 'vertical' in filters:
                    weaviate_filters["vertical"] = {"Equal": filters['vertical']}
                if 'document_type' in filters:
                    weaviate_filters["document_type"] = {"Equal": filters['document_type']}
                if 'metadata' in filters:
                    for key, value in filters['metadata'].items():
                        weaviate_filters[f"metadata_{key}"] = {"Equal": str(value)}
            
            # Búsqueda en Weaviate
            collection = self.weaviate_client.collections.get("DocumentChunks")
            
            response = collection.query.near_vector(
                near_vector=query_embedding,
                limit=limit,
                where=weaviate_filters,
                return_metadata=MetadataQuery(distance=True)
            )
            
            # Convertir resultados
            search_results = []
            for i, obj in enumerate(response.objects):
                search_results.append(SearchResult(
                    chunk_id=obj.properties.get('chunk_id', ''),
                    chunk_text=obj.properties.get('chunk_text', ''),
                    similarity_score=1.0 - obj.metadata.distance,  # Convertir distancia a similitud
                    search_rank=i + 1,
                    metadata=obj.properties.get('metadata', {}),
                    filename=obj.properties.get('filename', ''),
                    vertical=obj.properties.get('vertical', ''),
                    document_type=obj.properties.get('document_type', ''),
                    search_method="vector"
                ))
            
            return search_results
            
        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {e}")
            return []
    
    async def _hybrid_search(
        self,
        query: str,
        workspace_id: str,
        limit: int,
        filters: Optional[Dict[str, Any]] = None
    ) -> List[SearchResult]:
        """Búsqueda híbrida combinando BM25 y Vector con RRF"""
        
        try:
            # Ejecutar ambas búsquedas en paralelo
            bm25_task = self._bm25_search(
                query, workspace_id, self.config.max_results_per_method, filters
            )
            vector_task = self._vector_search(
                query, workspace_id, self.config.max_results_per_method, filters
            )
            
            bm25_results, vector_results = await asyncio.gather(bm25_task, vector_task)
            
            # Aplicar RRF (Reciprocal Rank Fusion)
            hybrid_results = self._apply_rrf(bm25_results, vector_results, limit)
            
            return hybrid_results
            
        except Exception as e:
            logger.error(f"Error en búsqueda híbrida: {e}")
            # Fallback a búsqueda BM25
            return await self._bm25_search(query, workspace_id, limit, filters)
    
    def _apply_rrf(
        self,
        bm25_results: List[SearchResult],
        vector_results: List[SearchResult],
        limit: int
    ) -> List[SearchResult]:
        """Aplica Reciprocal Rank Fusion para combinar resultados"""
        
        # Crear diccionario de scores RRF
        rrf_scores = {}
        
        # Procesar resultados BM25
        for i, result in enumerate(bm25_results):
            chunk_id = result.chunk_id
            rrf_score = 1.0 / (self.config.rrf_k + i + 1)
            
            if chunk_id in rrf_scores:
                rrf_scores[chunk_id]['bm25_score'] = rrf_score
                rrf_scores[chunk_id]['bm25_rank'] = i + 1
            else:
                rrf_scores[chunk_id] = {
                    'result': result,
                    'bm25_score': rrf_score,
                    'bm25_rank': i + 1,
                    'vector_score': 0.0,
                    'vector_rank': 0
                }
        
        # Procesar resultados Vector
        for i, result in enumerate(vector_results):
            chunk_id = result.chunk_id
            rrf_score = 1.0 / (self.config.rrf_k + i + 1)
            
            if chunk_id in rrf_scores:
                rrf_scores[chunk_id]['vector_score'] = rrf_score
                rrf_scores[chunk_id]['vector_rank'] = i + 1
            else:
                rrf_scores[chunk_id] = {
                    'result': result,
                    'bm25_score': 0.0,
                    'bm25_rank': 0,
                    'vector_score': rrf_score,
                    'vector_rank': i + 1
                }
        
        # Calcular score híbrido y ordenar
        hybrid_results = []
        for chunk_id, scores in rrf_scores.items():
            # Score híbrido ponderado
            hybrid_score = (
                self.config.bm25_weight * scores['bm25_score'] +
                self.config.vector_weight * scores['vector_score']
            )
            
            # Crear resultado híbrido
            result = scores['result']
            hybrid_result = SearchResult(
                chunk_id=result.chunk_id,
                chunk_text=result.chunk_text,
                similarity_score=hybrid_score,
                search_rank=0,  # Se asignará después del ordenamiento
                metadata=result.metadata,
                filename=result.filename,
                vertical=result.vertical,
                document_type=result.document_type,
                search_method="hybrid"
            )
            
            hybrid_results.append(hybrid_result)
        
        # Ordenar por score híbrido y limitar
        hybrid_results.sort(key=lambda x: x.similarity_score, reverse=True)
        
        # Asignar ranks finales
        for i, result in enumerate(hybrid_results[:limit]):
            result.search_rank = i + 1
        
        return hybrid_results[:limit]
    
    def update_config(self, config: HybridSearchConfig):
        """Actualiza la configuración de búsqueda híbrida"""
        self.config = config
        logger.info(f"Configuración actualizada: {config}")
    
    def close(self):
        """Cierra conexiones"""
        if self.weaviate_client:
            self.weaviate_client.close()
            logger.info("Conexión a Weaviate cerrada")

# Instancia global del motor de búsqueda
hybrid_search_engine = HybridSearchEngine()

# Funciones de conveniencia
async def search_documents(
    query: str,
    workspace_id: str,
    limit: int = 10,
    filters: Optional[Dict[str, Any]] = None,
    search_type: str = "hybrid"
) -> List[Dict[str, Any]]:
    """
    Función de conveniencia para búsqueda de documentos
    
    Returns:
        Lista de diccionarios con los resultados
    """
    results = await hybrid_search_engine.search(
        query=query,
        workspace_id=workspace_id,
        limit=limit,
        filters=filters,
        search_type=search_type
    )
    
    # Convertir a formato de diccionario
    return [
        {
            'chunk_id': result.chunk_id,
            'content': result.chunk_text,
            'similarity': result.similarity_score,
            'rank': result.search_rank,
            'metadata': result.metadata,
            'filename': result.filename,
            'vertical': result.vertical,
            'document_type': result.document_type,
            'search_method': result.search_method
        }
        for result in results
    ]

async def get_search_stats(workspace_id: str) -> Dict[str, Any]:
    """Obtiene estadísticas de búsqueda para un workspace"""
    try:
        with psycopg2.connect(hybrid_search_engine.db_url) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        f.vertical,
                        f.document_type,
                        COUNT(f.id) as total_files,
                        COUNT(fc.id) as total_chunks,
                        COUNT(e.id) as total_embeddings
                    FROM pulpo.files f
                    LEFT JOIN pulpo.file_chunks fc ON f.id = fc.file_id
                    LEFT JOIN pulpo.embeddings e ON fc.id = e.chunk_id
                    WHERE f.workspace_id = %s AND f.deleted_at IS NULL
                    GROUP BY f.vertical, f.document_type
                    ORDER BY f.vertical, f.document_type
                """, (workspace_id,))
                
                stats = cur.fetchall()
                return {
                    'workspace_id': workspace_id,
                    'total_verticals': len(set(row['vertical'] for row in stats if row['vertical'])),
                    'total_document_types': len(set(row['document_type'] for row in stats if row['document_type'])),
                    'total_files': sum(row['total_files'] for row in stats),
                    'total_chunks': sum(row['total_chunks'] for row in stats),
                    'total_embeddings': sum(row['total_embeddings'] for row in stats),
                    'by_vertical': [dict(row) for row in stats]
                }
                
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        return {'error': str(e)}

if __name__ == "__main__":
    # Ejemplo de uso
    async def test_hybrid_search():
        engine = HybridSearchEngine()
        
        # Búsqueda híbrida
        results = await engine.search(
            query="empanadas de carne",
            workspace_id="00000000-0000-0000-0000-000000000001",
            limit=5,
            search_type="hybrid"
        )
        
        print(f"Resultados encontrados: {len(results)}")
        for result in results:
            print(f"- {result.filename}: {result.similarity_score:.3f} ({result.search_method})")
        
        engine.close()
    
    asyncio.run(test_hybrid_search())
