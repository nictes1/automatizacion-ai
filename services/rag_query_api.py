#!/usr/bin/env python3
"""
API REST para Consultas RAG
Endpoint específico para que el LLM consulte información de documentos
"""

import os
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

from core.rag.rag_worker import RAGWorker
from utils.ollama_embeddings import OllamaEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Inicializar FastAPI
app = FastAPI(
    title="Pulpo RAG Query API",
    description="API para consultas RAG del LLM",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Inicializar componentes
rag_worker = RAGWorker()
ollama_embeddings = OllamaEmbeddings()

# Modelos Pydantic
class RAGQueryRequest(BaseModel):
    query: str
    workspace_id: str
    context_type: Optional[str] = "menu"  # menu, faq, policy, etc.
    limit: int = 5
    similarity_threshold: float = 0.7

class RAGQueryResult(BaseModel):
    content: str
    similarity_score: float
    source: str
    metadata: Dict[str, Any]

class RAGQueryResponse(BaseModel):
    query: str
    results: List[RAGQueryResult]
    total_results: int
    processing_time: float

# Dependencias
def get_workspace_id(workspace_id: str = Query(..., description="ID del workspace")) -> str:
    """Valida y retorna el workspace_id"""
    if not workspace_id:
        raise HTTPException(status_code=400, detail="workspace_id es requerido")
    return workspace_id

# Endpoints

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {"message": "Pulpo RAG Query API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/query", response_model=RAGQueryResponse)
async def query_rag(request: RAGQueryRequest):
    """Consulta RAG para el LLM"""
    
    start_time = datetime.now()
    
    try:
        logger.info(f"Consulta RAG: '{request.query}' en workspace {request.workspace_id}")
        
        # Usar RAG worker para buscar
        results = await rag_worker.search_documents(
            workspace_id=request.workspace_id,
            query=request.query,
            limit=request.limit,
            similarity_threshold=request.similarity_threshold
        )
        
        # Convertir resultados al formato esperado
        rag_results = []
        for result in results:
            rag_results.append(RAGQueryResult(
                content=result.get('content', ''),
                similarity_score=result.get('similarity', 0.0),
                source=result.get('filename', 'documento'),
                metadata=result.get('metadata', {})
            ))
        
        processing_time = (datetime.now() - start_time).total_seconds()
        
        return RAGQueryResponse(
            query=request.query,
            results=rag_results,
            total_results=len(rag_results),
            processing_time=processing_time
        )
        
    except Exception as e:
        logger.error(f"Error en consulta RAG: {e}")
        raise HTTPException(status_code=500, detail=f"Error en consulta RAG: {str(e)}")

@app.get("/query/simple")
async def simple_query(
    query: str = Query(..., description="Consulta de búsqueda"),
    workspace_id: str = Depends(get_workspace_id),
    limit: int = Query(5, ge=1, le=20)
):
    """Consulta RAG simple para el LLM"""
    
    try:
        logger.info(f"Consulta simple: '{query}' en workspace {workspace_id}")
        
        # Usar RAG worker para buscar
        results = await rag_worker.search_documents(
            workspace_id=workspace_id,
            query=query,
            limit=limit
        )
        
        # Formatear resultados para el LLM
        formatted_results = []
        for result in results:
            formatted_results.append({
                "content": result.get('content', ''),
                "similarity": result.get('similarity', 0.0),
                "source": result.get('filename', 'documento')
            })
        
        return {
            "query": query,
            "results": formatted_results,
            "total": len(formatted_results)
        }
        
    except Exception as e:
        logger.error(f"Error en consulta simple: {e}")
        raise HTTPException(status_code=500, detail=f"Error en consulta: {str(e)}")

@app.get("/query/menu")
async def query_menu(
    query: str = Query(..., description="Consulta del menú"),
    workspace_id: str = Depends(get_workspace_id),
    limit: int = Query(5, ge=1, le=20)
):
    """Consulta específica para menús"""
    
    try:
        logger.info(f"Consulta menú: '{query}' en workspace {workspace_id}")
        
        # Usar RAG worker para buscar
        results = await rag_worker.search_documents(
            workspace_id=workspace_id,
            query=query,
            limit=limit
        )
        
        # Filtrar solo resultados de menús
        menu_results = []
        for result in results:
            if 'menu' in result.get('filename', '').lower() or 'menu' in result.get('content', '').lower():
                menu_results.append({
                    "content": result.get('content', ''),
                    "similarity": result.get('similarity', 0.0),
                    "source": result.get('filename', 'menú')
                })
        
        return {
            "query": query,
            "menu_results": menu_results,
            "total": len(menu_results)
        }
        
    except Exception as e:
        logger.error(f"Error en consulta de menú: {e}")
        raise HTTPException(status_code=500, detail=f"Error en consulta de menú: {str(e)}")

@app.get("/query/context")
async def get_context(
    workspace_id: str = Depends(get_workspace_id),
    context_type: str = Query("all", description="Tipo de contexto: menu, faq, policy, all")
):
    """Obtiene contexto general del workspace"""
    
    try:
        logger.info(f"Obteniendo contexto {context_type} para workspace {workspace_id}")
        
        # Consulta general para obtener contexto
        results = await rag_worker.search_documents(
            workspace_id=workspace_id,
            query="información general del negocio",
            limit=10
        )
        
        # Filtrar por tipo de contexto si se especifica
        if context_type != "all":
            filtered_results = []
            for result in results:
                content = result.get('content', '').lower()
                if context_type in content or context_type in result.get('filename', '').lower():
                    filtered_results.append(result)
            results = filtered_results
        
        # Formatear contexto
        context = []
        for result in results:
            context.append({
                "content": result.get('content', ''),
                "source": result.get('filename', 'documento'),
                "type": context_type
            })
        
        return {
            "workspace_id": workspace_id,
            "context_type": context_type,
            "context": context,
            "total": len(context)
        }
        
    except Exception as e:
        logger.error(f"Error obteniendo contexto: {e}")
        raise HTTPException(status_code=500, detail=f"Error obteniendo contexto: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8003)

