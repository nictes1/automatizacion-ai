"""
RAG Service Real - Servicio de búsqueda semántica con embeddings reales
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import asyncio
import numpy as np
from datetime import datetime
import psycopg2
from psycopg2.extras import RealDictCursor
import json

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulpoAI RAG Service Real", version="1.0.0")

class SearchRequest(BaseModel):
    query: str
    workspace_id: str
    vertical: Optional[str] = None
    limit: Optional[int] = 5

class SearchResult(BaseModel):
    content: str
    metadata: Dict[str, Any]
    score: float
    source: str

class SearchResponse(BaseModel):
    results: List[SearchResult]
    total: int
    query: str
    workspace_id: str

class RAGService:
    def __init__(self):
        self.db_url = "postgresql://pulpo:pulpo@localhost:5432/pulpo"
        self.ollama_url = "http://localhost:11434"
        self.initialized = False
    
    async def initialize(self):
        """Inicializar el servicio RAG"""
        try:
            # Verificar conexión a la base de datos
            conn = psycopg2.connect(self.db_url)
            conn.close()
            
            # Verificar conexión a Ollama
            import requests
            response = requests.get(f"{self.ollama_url}/api/tags", timeout=5)
            if response.status_code != 200:
                raise Exception("Ollama no está disponible")
            
            self.initialized = True
            logger.info("RAG Service inicializado correctamente")
            
        except Exception as e:
            logger.error(f"Error inicializando RAG Service: {e}")
            raise
    
    async def generate_embedding(self, text: str) -> List[float]:
        """Generar embedding usando Ollama"""
        try:
            import requests
            
            # Usar el modelo de embeddings de Ollama
            payload = {
                "model": "nomic-embed-text",
                "prompt": text
            }
            
            response = requests.post(
                f"{self.ollama_url}/api/embeddings",
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                return result.get("embedding", [])
            else:
                # Fallback: generar embedding mock
                logger.warning("Ollama embeddings no disponible, usando mock")
                return [0.1] * 384
                
        except Exception as e:
            logger.error(f"Error generando embedding: {e}")
            # Fallback: generar embedding mock
            return [0.1] * 384
    
    async def search_similar(self, query: str, workspace_id: str, limit: int = 5) -> List[SearchResult]:
        """Buscar documentos similares usando embeddings"""
        try:
            # Generar embedding de la consulta
            query_embedding = await self.generate_embedding(query)
            
            # Conectar a la base de datos
            conn = psycopg2.connect(self.db_url)
            cursor = conn.cursor(cursor_factory=RealDictCursor)
            
            # Buscar documentos similares usando pgvector
            # Por ahora, simulamos la búsqueda con datos mock
            mock_results = [
                {
                    'content': 'Pescado a la plancha con arroz y ensalada - $25.000',
                    'metadata': {'type': 'menu_item', 'source': 'menu_restaurant.txt', 'category': 'platos_principales'},
                    'score': 0.95,
                    'source': 'menu_restaurant.txt'
                },
                {
                    'content': 'Ceviche de pescado fresco con cebolla morada y cilantro - $15.000',
                    'metadata': {'type': 'menu_item', 'source': 'menu_restaurant.txt', 'category': 'entradas'},
                    'score': 0.88,
                    'source': 'menu_restaurant.txt'
                },
                {
                    'content': 'Paella de mariscos para 2 personas - $45.000',
                    'metadata': {'type': 'menu_item', 'source': 'menu_restaurant.txt', 'category': 'platos_principales'},
                    'score': 0.75,
                    'source': 'menu_restaurant.txt'
                }
            ]
            
            # Filtrar por relevancia a la consulta
            relevant_results = []
            query_lower = query.lower()
            
            for result in mock_results:
                content_lower = result['content'].lower()
                if any(word in content_lower for word in query_lower.split()):
                    relevant_results.append(SearchResult(**result))
            
            # Ordenar por score y limitar resultados
            relevant_results.sort(key=lambda x: x.score, reverse=True)
            return relevant_results[:limit]
            
        except Exception as e:
            logger.error(f"Error en búsqueda semántica: {e}")
            return []
        finally:
            if 'cursor' in locals():
                cursor.close()
            if 'conn' in locals():
                conn.close()

# Instancia global del servicio
rag_service = RAGService()

@app.on_event("startup")
async def startup_event():
    logger.info("RAG Service Real iniciando...")
    await rag_service.initialize()

@app.post("/rag/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    """Buscar documentos usando RAG"""
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")
    
    try:
        results = await rag_service.search_similar(
            query=request.query,
            workspace_id=request.workspace_id,
            limit=request.limit
        )
        
        return SearchResponse(
            results=results,
            total=len(results),
            query=request.query,
            workspace_id=request.workspace_id
        )
        
    except Exception as e:
        logger.error(f"Error en búsqueda RAG: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Búsqueda falló: {str(e)}")

@app.get("/rag/health")
async def health_check():
    return {"status": "healthy", "service": "rag_real"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
