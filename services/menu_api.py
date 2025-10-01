#!/usr/bin/env python3
"""
API REST para Gestión de Menús Gastronómicos
Endpoints específicos para cargar, procesar y consultar menús
"""

import os
import uuid
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import asyncio

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Query, Path as PathParam
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

from core.ingestion.document_ingestion import DocumentIngestionPipeline
from core.rag.rag_worker import RAGWorker
from utils.ollama_embeddings import OllamaEmbeddings
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
UPLOAD_DIR = Path("uploads/menus")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

# Inicializar FastAPI
app = FastAPI(
    title="Pulpo Menu API",
    description="API para gestión de menús gastronómicos",
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
ingestion_pipeline = DocumentIngestionPipeline()
rag_worker = RAGWorker()
ollama_embeddings = OllamaEmbeddings()

# Modelos Pydantic
class MenuUploadResponse(BaseModel):
    menu_id: str
    filename: str
    file_size: int
    status: str
    message: str
    chunks_created: int
    embeddings_generated: int

class MenuSearchRequest(BaseModel):
    query: str
    workspace_id: str
    limit: int = 10

class MenuSearchResult(BaseModel):
    menu_id: str
    filename: str
    chunk_text: str
    similarity_score: float
    chunk_index: int
    metadata: Dict[str, Any]

class MenuInfo(BaseModel):
    menu_id: str
    filename: str
    file_size: int
    chunks_count: int
    created_at: datetime
    status: str

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
    return {"message": "Pulpo Menu API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/menus/upload", response_model=MenuUploadResponse)
async def upload_menu(
    file: UploadFile = File(...),
    workspace_id: str = Depends(get_workspace_id)
):
    """Sube un menú para procesamiento completo"""
    
    try:
        # Validar tipo de archivo
        if not file.filename.endswith(('.txt', '.pdf', '.docx', '.doc')):
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de archivo no soportado: {file.filename}"
            )
        
        # Generar nombre único para el archivo
        file_extension = Path(file.filename).suffix
        stored_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = UPLOAD_DIR / stored_filename
        
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            content = await file.read()
            buffer.write(content)
        
        # Procesar archivo con pipeline de ingesta
        logger.info(f"Procesando menú: {file.filename}")
        
        # 1. Extraer información estructurada
        extracted_data = await ingestion_pipeline.extract_structured_data(
            str(file_path), 
            workspace_id
        )
        
        # 2. Crear chunks
        chunks = await ingestion_pipeline.create_chunks(
            extracted_data, 
            workspace_id
        )
        
        # 3. Generar embeddings
        embeddings = await ingestion_pipeline.generate_embeddings(
            chunks, 
            workspace_id
        )
        
        # 4. Guardar en base de datos
        menu_id = await ingestion_pipeline.save_to_database(
            workspace_id, 
            file.filename, 
            str(file_path), 
            extracted_data, 
            chunks, 
            embeddings
        )
        
        return MenuUploadResponse(
            menu_id=menu_id,
            filename=file.filename,
            file_size=len(content),
            status="completed",
            message="Menú procesado exitosamente",
            chunks_created=len(chunks),
            embeddings_generated=len(embeddings)
        )
        
    except Exception as e:
        logger.error(f"Error procesando menú {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando menú: {str(e)}")

@app.post("/menus/search", response_model=List[MenuSearchResult])
async def search_menu(request: MenuSearchRequest):
    """Busca información específica en los menús"""
    
    try:
        # Usar RAG worker para buscar
        results = await rag_worker.search_documents(
            workspace_id=request.workspace_id,
            query=request.query,
            limit=request.limit
        )
        
        # Convertir resultados al formato esperado
        search_results = []
        for result in results:
            search_results.append(MenuSearchResult(
                menu_id=result.get('document_id', ''),
                filename=result.get('filename', ''),
                chunk_text=result.get('content', ''),
                similarity_score=result.get('similarity', 0.0),
                chunk_index=result.get('chunk_index', 0),
                metadata=result.get('metadata', {})
            ))
        
        return search_results
        
    except Exception as e:
        logger.error(f"Error buscando en menús: {e}")
        raise HTTPException(status_code=500, detail=f"Error en búsqueda: {str(e)}")

@app.get("/menus", response_model=List[MenuInfo])
async def list_menus(
    workspace_id: str = Depends(get_workspace_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Lista menús de un workspace"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        f.id as menu_id,
                        f.original_filename as filename,
                        f.file_size,
                        COUNT(fc.id) as chunks_count,
                        f.created_at,
                        f.processing_status as status
                    FROM pulpo.files f
                    LEFT JOIN pulpo.file_chunks fc ON f.id = fc.file_id
                    WHERE f.workspace_id = %s 
                    AND f.deleted_at IS NULL
                    AND f.file_type IN ('text', 'pdf', 'docx', 'doc')
                    GROUP BY f.id, f.original_filename, f.file_size, f.created_at, f.processing_status
                    ORDER BY f.created_at DESC
                    LIMIT %s OFFSET %s
                """, (workspace_id, limit, offset))
                
                menus = cur.fetchall()
                return [MenuInfo(**menu) for menu in menus]
                
    except Exception as e:
        logger.error(f"Error listando menús: {e}")
        raise HTTPException(status_code=500, detail="Error listando menús")

@app.get("/menus/{menu_id}")
async def get_menu_info(
    menu_id: str = PathParam(..., description="ID del menú"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Obtiene información detallada de un menú"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        f.id as menu_id,
                        f.original_filename as filename,
                        f.file_size,
                        f.text_content,
                        f.metadata_json,
                        f.processing_status as status,
                        f.created_at,
                        COUNT(fc.id) as chunks_count
                    FROM pulpo.files f
                    LEFT JOIN pulpo.file_chunks fc ON f.id = fc.file_id
                    WHERE f.id = %s AND f.workspace_id = %s AND f.deleted_at IS NULL
                    GROUP BY f.id, f.original_filename, f.file_size, f.text_content, 
                             f.metadata_json, f.processing_status, f.created_at
                """, (menu_id, workspace_id))
                
                menu_data = cur.fetchone()
                if not menu_data:
                    raise HTTPException(status_code=404, detail="Menú no encontrado")
                
                return dict(menu_data)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo menú {menu_id}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo menú")

@app.delete("/menus/{menu_id}")
async def delete_menu(
    menu_id: str = PathParam(..., description="ID del menú"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Elimina un menú y sus embeddings"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor() as cur:
                # Eliminar chunks y embeddings
                cur.execute("""
                    DELETE FROM pulpo.file_chunks 
                    WHERE file_id = %s
                """, (menu_id,))
                
                # Marcar archivo como eliminado
                cur.execute("""
                    UPDATE pulpo.files 
                    SET deleted_at = NOW() 
                    WHERE id = %s AND workspace_id = %s
                """, (menu_id, workspace_id))
                
                if cur.rowcount == 0:
                    raise HTTPException(status_code=404, detail="Menú no encontrado")
                
                conn.commit()
        
        return {"message": "Menú eliminado exitosamente", "menu_id": menu_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando menú {menu_id}: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando menú")

@app.get("/menus/{menu_id}/chunks")
async def get_menu_chunks(
    menu_id: str = PathParam(..., description="ID del menú"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Obtiene los chunks de un menú"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT 
                        fc.chunk_index,
                        fc.chunk_text,
                        fc.chunk_tokens,
                        fc.chunk_metadata
                    FROM pulpo.file_chunks fc
                    JOIN pulpo.files f ON fc.file_id = f.id
                    WHERE f.id = %s AND f.workspace_id = %s AND f.deleted_at IS NULL
                    ORDER BY fc.chunk_index
                """, (menu_id, workspace_id))
                
                chunks = cur.fetchall()
                if not chunks:
                    raise HTTPException(status_code=404, detail="Menú o chunks no encontrados")
                
                return [dict(chunk) for chunk in chunks]
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo chunks del menú {menu_id}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo chunks")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

