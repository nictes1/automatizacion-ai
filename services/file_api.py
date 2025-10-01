#!/usr/bin/env python3
"""
API REST para Gestión de Archivos RAG
Endpoints para subir, listar, ver y eliminar archivos
"""

import os
import uuid
import shutil
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging

from fastapi import FastAPI, HTTPException, UploadFile, File, Depends, Query, Path as PathParam
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import psycopg2
from psycopg2.extras import RealDictCursor

from file_processor import FileProcessor, FileManager
from dotenv import load_dotenv

load_dotenv()

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configuración
UPLOAD_DIR = Path("uploads")
RAW_DIR = UPLOAD_DIR / "raw"
PROCESSED_DIR = UPLOAD_DIR / "processed"

# Crear directorios si no existen
UPLOAD_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)
PROCESSED_DIR.mkdir(exist_ok=True)

# Inicializar FastAPI
app = FastAPI(
    title="Pulpo File Management API",
    description="API para gestión de archivos y RAG",
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

# Inicializar procesador y gestor
processor = FileProcessor(
    db_connection_string=os.getenv('DATABASE_URL'),
    openai_api_key=os.getenv('OPENAI_API_KEY')
)

file_manager = FileManager(os.getenv('DATABASE_URL'))

# Modelos Pydantic
class FileUploadResponse(BaseModel):
    file_id: str
    filename: str
    file_size: int
    file_type: str
    status: str
    message: str

class FileInfo(BaseModel):
    id: str
    original_filename: str
    file_size: int
    file_type: str
    mime_type: str
    processing_status: str
    created_at: datetime
    updated_at: datetime
    processed_at: Optional[datetime] = None

class FileStats(BaseModel):
    total_files: int
    total_size: int
    files_by_status: Dict[str, int]
    files_by_type: Dict[str, int]
    total_chunks: int
    total_embeddings: int

class SearchResult(BaseModel):
    file_id: str
    filename: str
    file_type: str
    chunk_text: str
    similarity_score: float
    chunk_index: int

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
    return {"message": "Pulpo File Management API", "version": "1.0.0"}

@app.get("/health")
async def health_check():
    """Health check"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.post("/files/upload", response_model=FileUploadResponse)
async def upload_file(
    file: UploadFile = File(...),
    workspace_id: str = Depends(get_workspace_id)
):
    """Sube un archivo para procesamiento"""
    
    try:
        # Validar tipo de archivo
        if not processor.is_supported_file(file.filename):
            raise HTTPException(
                status_code=400, 
                detail=f"Tipo de archivo no soportado: {file.filename}"
            )
        
        # Generar nombre único para el archivo
        file_extension = Path(file.filename).suffix
        stored_filename = f"{uuid.uuid4()}{file_extension}"
        file_path = RAW_DIR / stored_filename
        
        # Guardar archivo
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Procesar archivo
        logger.info(f"Procesando archivo: {file.filename}")
        file_metadata = processor.process_file(str(file_path), workspace_id)
        
        # Guardar en base de datos
        file_id = file_manager.save_file_metadata(
            workspace_id, file_metadata, stored_filename, str(file_path)
        )
        
        # Mover archivo procesado
        processed_path = PROCESSED_DIR / stored_filename
        shutil.move(str(file_path), str(processed_path))
        
        return FileUploadResponse(
            file_id=file_id,
            filename=file_metadata.original_filename,
            file_size=file_metadata.file_size,
            file_type=file_metadata.file_type,
            status="completed",
            message="Archivo procesado exitosamente"
        )
        
    except Exception as e:
        logger.error(f"Error procesando archivo {file.filename}: {e}")
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")

@app.get("/files", response_model=List[FileInfo])
async def list_files(
    workspace_id: str = Depends(get_workspace_id),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0)
):
    """Lista archivos de un workspace"""
    try:
        files = file_manager.list_files(workspace_id, limit, offset)
        return [FileInfo(**file) for file in files]
    except Exception as e:
        logger.error(f"Error listando archivos: {e}")
        raise HTTPException(status_code=500, detail="Error listando archivos")

@app.get("/files/stats", response_model=FileStats)
async def get_file_stats(workspace_id: str = Depends(get_workspace_id)):
    """Obtiene estadísticas de archivos"""
    try:
        stats = file_manager.get_file_stats(workspace_id)
        return FileStats(**stats)
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@app.get("/files/{file_id}")
async def get_file_info(
    file_id: str = PathParam(..., description="ID del archivo"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Obtiene información detallada de un archivo"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT id, original_filename, file_size, file_type, mime_type,
                           processing_status, text_content, metadata_json, created_at, updated_at
                    FROM pulpo.files 
                    WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """, (file_id, workspace_id))
                
                file_data = cur.fetchone()
                if not file_data:
                    raise HTTPException(status_code=404, detail="Archivo no encontrado")
                
                return dict(file_data)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo archivo")

@app.get("/files/{file_id}/download")
async def download_file(
    file_id: str = PathParam(..., description="ID del archivo"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Descarga un archivo original"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT stored_filename, original_filename, file_path
                    FROM pulpo.files 
                    WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """, (file_id, workspace_id))
                
                file_data = cur.fetchone()
                if not file_data:
                    raise HTTPException(status_code=404, detail="Archivo no encontrado")
                
                file_path = Path(file_data['file_path'])
                if not file_path.exists():
                    raise HTTPException(status_code=404, detail="Archivo no encontrado en disco")
                
                return FileResponse(
                    path=str(file_path),
                    filename=file_data['original_filename'],
                    media_type='application/octet-stream'
                )
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error descargando archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error descargando archivo")

@app.get("/files/{file_id}/content")
async def get_file_content(
    file_id: str = PathParam(..., description="ID del archivo"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Obtiene el contenido de texto de un archivo"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT text_content, original_filename
                    FROM pulpo.files 
                    WHERE id = %s AND workspace_id = %s AND deleted_at IS NULL
                """, (file_id, workspace_id))
                
                file_data = cur.fetchone()
                if not file_data:
                    raise HTTPException(status_code=404, detail="Archivo no encontrado")
                
                return {
                    "file_id": file_id,
                    "filename": file_data['original_filename'],
                    "content": file_data['text_content']
                }
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo contenido del archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo contenido")

@app.get("/files/{file_id}/chunks")
async def get_file_chunks(
    file_id: str = PathParam(..., description="ID del archivo"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Obtiene los chunks de un archivo"""
    try:
        with psycopg2.connect(os.getenv('DATABASE_URL')) as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute("""
                    SELECT fc.chunk_index, fc.chunk_text, fc.chunk_tokens, fc.chunk_metadata
                    FROM pulpo.file_chunks fc
                    JOIN pulpo.files f ON fc.file_id = f.id
                    WHERE f.id = %s AND f.workspace_id = %s AND f.deleted_at IS NULL
                    ORDER BY fc.chunk_index
                """, (file_id, workspace_id))
                
                chunks = cur.fetchall()
                if not chunks:
                    raise HTTPException(status_code=404, detail="Archivo o chunks no encontrados")
                
                return [dict(chunk) for chunk in chunks]
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error obteniendo chunks del archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo chunks")

@app.delete("/files/{file_id}")
async def delete_file(
    file_id: str = PathParam(..., description="ID del archivo"),
    workspace_id: str = Depends(get_workspace_id)
):
    """Elimina un archivo y sus embeddings"""
    try:
        success = file_manager.delete_file(workspace_id, file_id)
        if not success:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
        
        return {"message": "Archivo eliminado exitosamente", "file_id": file_id}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando archivo {file_id}: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando archivo")

@app.get("/search", response_model=List[SearchResult])
async def search_files(
    query: str = Query(..., description="Consulta de búsqueda"),
    workspace_id: str = Depends(get_workspace_id),
    limit: int = Query(10, ge=1, le=50)
):
    """Busca archivos por contenido"""
    try:
        results = file_manager.search_files(workspace_id, query, limit)
        return [SearchResult(**result) for result in results]
    except Exception as e:
        logger.error(f"Error buscando archivos: {e}")
        raise HTTPException(status_code=500, detail="Error en búsqueda")

@app.get("/supported-types")
async def get_supported_file_types():
    """Obtiene los tipos de archivos soportados"""
    return {
        "supported_extensions": list(processor.SUPPORTED_EXTENSIONS),
        "max_file_size": "50MB",
        "chunk_size": processor.CHUNK_SIZE,
        "chunk_overlap": processor.CHUNK_OVERLAP
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)

