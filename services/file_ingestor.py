#!/usr/bin/env python3
"""
Servicio de Ingesta de Archivos para RAG
Servicio principal que orquesta el procesamiento de archivos
"""

import os
import logging
import asyncio
from typing import Dict, Any, Optional
from pathlib import Path
import json
import time

from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel
import uvicorn

from file_processor_improved import FileProcessorImproved, FileManagerImproved
from tika_client import TikaClient
from ollama_embeddings import OllamaEmbeddings

# Configuración
from dotenv import load_dotenv
load_dotenv()

# Configurar logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/file_ingestor.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuración del servicio
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://pulpo_user:pulpo_password@localhost:5432/pulpo_db')
TIKA_URL = os.getenv('TIKA_URL', 'http://localhost:9998')
OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
EMBEDDING_DIMS = int(os.getenv('EMBEDDING_DIMS', '768'))
SERVER_ADDR = os.getenv('SERVER_ADDR', ':8080')
READ_LOCAL_FILES = os.getenv('READ_LOCAL_FILES', 'true').lower() == 'true'

# Inicializar FastAPI
app = FastAPI(
    title="Pulpo File Ingestor",
    description="Servicio de ingesta de archivos para RAG",
    version="1.0.0"
)

# Inicializar componentes
processor = FileProcessorImproved(DATABASE_URL, TIKA_URL, OLLAMA_URL, EMBEDDING_MODEL)
file_manager = FileManagerImproved(DATABASE_URL)

# Modelos Pydantic
class IngestRequest(BaseModel):
    workspace_id: str
    file_path: str
    title: Optional[str] = None
    language: Optional[str] = None
    chunk_size: Optional[int] = None
    chunk_overlap: Optional[int] = None

class IngestResponse(BaseModel):
    file_id: str
    document_id: str
    chunks_created: int
    embeddings_generated: int
    processing_time: float
    status: str

class HealthResponse(BaseModel):
    status: str
    tika_ready: bool
    ollama_ready: bool
    database_ready: bool
    timestamp: str

# Variables globales para estado
service_ready = False
startup_time = None

@app.on_event("startup")
async def startup_event():
    """Inicialización del servicio"""
    global service_ready, startup_time
    startup_time = time.time()
    
    logger.info("🚀 Iniciando servicio de ingesta de archivos...")
    
    # Verificar dependencias
    tika_ready = processor.tika_client.wait_for_ready()
    ollama_ready = processor.ollama_embeddings.wait_for_ready()
    
    if tika_ready and ollama_ready:
        service_ready = True
        logger.info("✅ Servicio listo para procesar archivos")
    else:
        logger.error("❌ Servicio no pudo inicializarse correctamente")
        service_ready = False

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del servicio"""
    tika_ready = processor.tika_client.health_check()
    ollama_ready = processor.ollama_embeddings.health_check()
    
    # Verificar base de datos
    try:
        file_manager.set_workspace_context("00000000-0000-0000-0000-000000000001")
        db_ready = True
    except Exception as e:
        logger.error(f"Error verificando base de datos: {e}")
        db_ready = False
    
    overall_status = "healthy" if (tika_ready and ollama_ready and db_ready) else "unhealthy"
    
    return HealthResponse(
        status=overall_status,
        tika_ready=tika_ready,
        ollama_ready=ollama_ready,
        database_ready=db_ready,
        timestamp=time.strftime("%Y-%m-%d %H:%M:%S")
    )

@app.post("/ingest", response_model=IngestResponse)
async def ingest_file(request: IngestRequest, background_tasks: BackgroundTasks):
    """Ingesta un archivo para procesamiento RAG"""
    if not service_ready:
        raise HTTPException(status_code=503, detail="Servicio no está listo")
    
    start_time = time.time()
    
    try:
        # Verificar que el archivo existe
        if not os.path.exists(request.file_path):
            raise HTTPException(status_code=404, detail=f"Archivo no encontrado: {request.file_path}")
        
        # Verificar que es un archivo soportado
        if not processor.is_supported_file(request.file_path):
            raise HTTPException(status_code=400, detail=f"Tipo de archivo no soportado: {request.file_path}")
        
        # Establecer contexto del workspace
        file_manager.set_workspace_context(request.workspace_id)
        
        # Obtener metadatos del archivo
        sha256, file_size = processor.get_file_hash(request.file_path)
        mime_type = processor.detect_mime_type(request.file_path)
        filename = Path(request.file_path).name
        
        # Crear URI de almacenamiento (para desarrollo usamos file://)
        storage_uri = f"file://{os.path.abspath(request.file_path)}"
        
        # Guardar metadatos del archivo
        file_id = file_manager.save_file_metadata(
            request.workspace_id, filename, storage_uri, mime_type, sha256, file_size
        )
        
        # Actualizar estado a procesando
        file_manager.update_file_status(file_id, "processing")
        
        # Procesar archivo
        document = processor.process_file(
            request.file_path, 
            request.workspace_id, 
            request.title or filename,
            request.language
        )
        
        # Generar embeddings para todos los chunks
        chunk_texts = [chunk["content"] for chunk in document.chunks]
        embeddings = processor.ollama_embeddings.generate_embeddings_batch(chunk_texts)
        
        # Guardar documento, chunks y embeddings
        document_id = file_manager.save_document_and_chunks(
            request.workspace_id, file_id, document, embeddings
        )
        
        # Actualizar estado a procesado
        file_manager.update_file_status(file_id, "processed")
        
        processing_time = time.time() - start_time
        
        logger.info(f"✅ Archivo procesado exitosamente: {filename} ({processing_time:.2f}s)")
        
        return IngestResponse(
            file_id=file_id,
            document_id=document_id,
            chunks_created=len(document.chunks),
            embeddings_generated=len(embeddings),
            processing_time=processing_time,
            status="completed"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error procesando archivo {request.file_path}: {e}")
        
        # Actualizar estado a fallido si tenemos file_id
        try:
            if 'file_id' in locals():
                file_manager.update_file_status(file_id, "failed", str(e))
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"Error procesando archivo: {str(e)}")

@app.post("/ingest/async", response_model=Dict[str, str])
async def ingest_file_async(request: IngestRequest, background_tasks: BackgroundTasks):
    """Ingesta un archivo de forma asíncrona"""
    if not service_ready:
        raise HTTPException(status_code=503, detail="Servicio no está listo")
    
    # Agregar tarea en background
    background_tasks.add_task(process_file_async, request)
    
    return {
        "message": "Archivo agregado a la cola de procesamiento",
        "file_path": request.file_path,
        "workspace_id": request.workspace_id
    }

async def process_file_async(request: IngestRequest):
    """Procesa un archivo de forma asíncrona"""
    try:
        # Crear una nueva instancia del request para el procesamiento
        ingest_request = IngestRequest(
            workspace_id=request.workspace_id,
            file_path=request.file_path,
            title=request.title,
            language=request.language,
            chunk_size=request.chunk_size,
            chunk_overlap=request.chunk_overlap
        )
        
        # Procesar el archivo
        result = await ingest_file(ingest_request, BackgroundTasks())
        logger.info(f"✅ Procesamiento asíncrono completado: {result.file_id}")
        
    except Exception as e:
        logger.error(f"❌ Error en procesamiento asíncrono: {e}")

@app.get("/files/{workspace_id}/stats")
async def get_file_stats(workspace_id: str):
    """Obtiene estadísticas de archivos por workspace"""
    try:
        file_manager.set_workspace_context(workspace_id)
        stats = file_manager.get_file_stats(workspace_id)
        return stats
    except Exception as e:
        logger.error(f"Error obteniendo estadísticas: {e}")
        raise HTTPException(status_code=500, detail="Error obteniendo estadísticas")

@app.get("/files/{workspace_id}")
async def list_files(workspace_id: str, limit: int = 50, offset: int = 0):
    """Lista archivos de un workspace"""
    try:
        file_manager.set_workspace_context(workspace_id)
        files = file_manager.list_files(workspace_id, limit, offset)
        return files
    except Exception as e:
        logger.error(f"Error listando archivos: {e}")
        raise HTTPException(status_code=500, detail="Error listando archivos")

@app.delete("/files/{workspace_id}/{file_id}")
async def delete_file(workspace_id: str, file_id: str):
    """Elimina un archivo"""
    try:
        file_manager.set_workspace_context(workspace_id)
        success = file_manager.delete_file(workspace_id, file_id)
        
        if success:
            return {"message": "Archivo eliminado exitosamente", "file_id": file_id}
        else:
            raise HTTPException(status_code=404, detail="Archivo no encontrado")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error eliminando archivo: {e}")
        raise HTTPException(status_code=500, detail="Error eliminando archivo")

@app.get("/supported-types")
async def get_supported_types():
    """Obtiene los tipos de archivos soportados"""
    return {
        "supported_extensions": list(processor.SUPPORTED_EXTENSIONS),
        "embedding_model": EMBEDDING_MODEL,
        "embedding_dimensions": EMBEDDING_DIMS,
        "default_chunk_size": processor.DEFAULT_CHUNK_SIZE,
        "default_chunk_overlap": processor.DEFAULT_CHUNK_OVERLAP
    }

@app.get("/")
async def root():
    """Endpoint raíz"""
    return {
        "service": "Pulpo File Ingestor",
        "version": "1.0.0",
        "status": "running" if service_ready else "starting",
        "uptime": time.time() - startup_time if startup_time else 0
    }

if __name__ == "__main__":
    # Crear directorio de logs si no existe
    os.makedirs("logs", exist_ok=True)
    
    # Configurar uvicorn
    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8080,
        log_level="info",
        access_log=True
    )
    
    server = uvicorn.Server(config)
    
    logger.info("🚀 Iniciando servidor de ingesta de archivos...")
    server.run()

