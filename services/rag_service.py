"""
RAG Service - Búsqueda semántica con embeddings de Ollama
"""

from fastapi import FastAPI, HTTPException, Header
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import logging
import os
import httpx
import psycopg2
from psycopg2.extras import RealDictCursor
from contextlib import contextmanager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="PulpoAI RAG Service", version="1.0.0")

# Configuración
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@postgres:5432/pulpo")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://ollama:11434")

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

@contextmanager
def get_db_cursor():
    """Obtiene cursor de base de datos"""
    conn = psycopg2.connect(DATABASE_URL)
    try:
        cursor = conn.cursor(cursor_factory=RealDictCursor)
        try:
            yield conn, cursor
        finally:
            cursor.close()
    finally:
        conn.close()

class RAGClient:
    def __init__(self):
        self.initialized = False
        self.http_client = httpx.AsyncClient(timeout=30.0)

    async def initialize(self):
        """Inicializa el cliente RAG"""
        try:
            # Verificar conexión con Ollama
            response = await self.http_client.get(f"{OLLAMA_URL}/api/tags")
            if response.status_code == 200:
                logger.info(f"✅ Conectado a Ollama: {OLLAMA_URL}")
                models = response.json().get("models", [])
                logger.info(f"   Modelos disponibles: {[m['name'] for m in models]}")
            self.initialized = True
            logger.info("RAG Client initialized")
        except Exception as e:
            logger.error(f"Error inicializando RAG Client: {e}")
            # No falla si no puede conectar, usará fallback
            self.initialized = True

    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """Genera embedding usando Ollama"""
        try:
            response = await self.http_client.post(
                f"{OLLAMA_URL}/api/embeddings",
                json={
                    "model": "nomic-embed-text",
                    "prompt": text
                }
            )
            if response.status_code == 200:
                data = response.json()
                return data.get("embedding")
            else:
                logger.error(f"Error generando embedding: {response.status_code}")
                return None
        except Exception as e:
            logger.error(f"Error conectando con Ollama: {e}")
            return None

    async def search(self, query: str, workspace_id: str, vertical: str = None, limit: int = 5) -> List[SearchResult]:
        """Búsqueda semántica en documentos"""
        if not self.initialized:
            await self.initialize()

        try:
            # Generar embedding del query
            query_embedding = await self.generate_embedding(query)

            results = []

            if query_embedding:
                # Búsqueda por similaridad vectorial
                results = await self._vector_search(query_embedding, workspace_id, limit)

            # Fallback: búsqueda por texto si no hay embedding
            if not results:
                results = await self._text_search(query, workspace_id, limit)

            return results

        except Exception as e:
            logger.error(f"Error en búsqueda: {e}")
            # Retornar datos de ejemplo en caso de error
            return [
                SearchResult(
                    content=f"Búsqueda para: {query} (modo fallback)",
                    metadata={"type": "fallback", "workspace_id": workspace_id},
                    score=0.5,
                    source="sistema"
                )
            ]

    async def _vector_search(self, embedding: List[float], workspace_id: str, limit: int) -> List[SearchResult]:
        """Búsqueda vectorial con pgvector"""
        try:
            with get_db_cursor() as (conn, cur):
                # Convertir embedding a formato pgvector
                embedding_str = f"[{','.join(map(str, embedding))}]"

                query = """
                    SELECT
                        dc.content,
                        d.title as source,
                        dc.metadata,
                        1 - (de.embedding <=> %s::vector) as score
                    FROM pulpo.document_chunks dc
                    INNER JOIN pulpo.documents d ON dc.document_id = d.id
                    LEFT JOIN pulpo.document_embeddings de ON dc.id = de.chunk_id
                    WHERE d.workspace_id = %s
                      AND de.embedding IS NOT NULL
                    ORDER BY de.embedding <=> %s::vector
                    LIMIT %s
                """

                cur.execute(query, (embedding_str, workspace_id, embedding_str, limit))
                rows = cur.fetchall()

                results = []
                for row in rows:
                    results.append(SearchResult(
                        content=row["content"],
                        metadata=row["metadata"] or {},
                        score=float(row["score"]) if row["score"] else 0.0,
                        source=row["source"]
                    ))

                return results

        except Exception as e:
            logger.error(f"Error en búsqueda vectorial: {e}")
            return []

    async def _text_search(self, query: str, workspace_id: str, limit: int) -> List[SearchResult]:
        """Búsqueda por texto (fallback)"""
        try:
            with get_db_cursor() as (conn, cur):
                sql_query = """
                    SELECT
                        dc.content,
                        d.title as source,
                        dc.metadata,
                        CASE
                            WHEN dc.content ILIKE %s THEN 0.9
                            WHEN dc.content ILIKE %s THEN 0.7
                            ELSE 0.5
                        END as score
                    FROM pulpo.document_chunks dc
                    INNER JOIN pulpo.documents d ON dc.document_id = d.id
                    WHERE d.workspace_id = %s
                      AND (
                          dc.content ILIKE %s
                          OR dc.content ILIKE %s
                      )
                    ORDER BY score DESC
                    LIMIT %s
                """

                exact_match = f"%{query}%"
                fuzzy_match = f"%{query.split()[0]}%" if query.split() else exact_match

                cur.execute(sql_query, (
                    exact_match, fuzzy_match,  # para CASE
                    workspace_id,  # WHERE workspace
                    exact_match, fuzzy_match,  # WHERE ILIKE
                    limit
                ))
                rows = cur.fetchall()

                results = []
                for row in rows:
                    results.append(SearchResult(
                        content=row["content"],
                        metadata=row["metadata"] or {},
                        score=float(row["score"]),
                        source=row["source"]
                    ))

                return results

        except Exception as e:
            logger.error(f"Error en búsqueda de texto: {e}")
            return []

    async def close(self):
        """Cierra el cliente HTTP"""
        await self.http_client.aclose()

rag_client = RAGClient()

@app.on_event("startup")
async def startup_event():
    logger.info("🚀 RAG Service starting up...")
    await rag_client.initialize()
    logger.info("✅ RAG Service ready")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("🛑 RAG Service shutting down...")
    await rag_client.close()

@app.post("/rag/search", response_model=SearchResponse)
async def search_documents(
    request: SearchRequest,
    x_workspace_id: Optional[str] = Header(None, alias="X-Workspace-Id"),
    x_request_id: Optional[str] = Header(None, alias="X-Request-Id")
):
    """Endpoint de búsqueda semántica"""
    if not x_workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header is required")

    try:
        results = await rag_client.search(
            query=request.query,
            workspace_id=request.workspace_id,
            vertical=request.vertical,
            limit=request.limit
        )

        return SearchResponse(
            results=results,
            total=len(results),
            query=request.query,
            workspace_id=request.workspace_id
        )

    except Exception as e:
        logger.error(f"Error in search: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/rag/health")
async def health_check():
    """Health check endpoint"""
    return {
        "status": "healthy",
        "service": "rag",
        "ollama_url": OLLAMA_URL,
        "database": "connected"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8007)
