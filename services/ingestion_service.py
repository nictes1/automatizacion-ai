"""
Ingestion Service - Servicio para ingesta de documentos
Maneja upload, procesamiento, chunking y embeddings de archivos
"""

import os
import logging
import asyncio
import json
import hashlib
import mimetypes
import time
from typing import Dict, List, Any, Optional, Tuple
from datetime import datetime, timezone
from pathlib import Path
import uuid

from fastapi import FastAPI, HTTPException, UploadFile, File, Header, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
import psycopg2
from psycopg2.extras import RealDictCursor
import httpx
import aiofiles
from dotenv import load_dotenv

# Importar procesadores de documentos
from utils.tika_client import TikaClient
from utils.ollama_embeddings import OllamaEmbeddings
from core.rag.smart_document_processor import SmartDocumentProcessor
from utils.db_async import run_db, exec_with_ws, exec_with_ws_transaction

load_dotenv()

# Configuración de logging estructurado
level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(
    level=getattr(logging, level, logging.INFO),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Aplicar nivel a todos los handlers
for handler in logging.getLogger().handlers:
    handler.setLevel(getattr(logging, level, logging.INFO))

def log_structured(level: str, message: str, **kwargs):
    """Log estructurado con contexto"""
    log_data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        **kwargs
    }
    getattr(logger, level.lower())(json.dumps(log_data))

def _set_ws(cur, ws): 
    """Helper para establecer contexto RLS"""
    cur.execute("SELECT set_config('app.workspace_id', %s, true)", (ws,))

# Métricas Prometheus (con hash de workspace para evitar cardinalidad)
def get_workspace_hash(workspace_id: str) -> str:
    """Genera hash corto del workspace_id para métricas"""
    import hashlib
    return hashlib.sha1(workspace_id.encode()).hexdigest()[:8]

FILES_UPLOADED = Counter("ing_files_uploaded_total", "Archivos subidos", ["workspace_hash"])
FILES_PROCESSED = Counter("ing_files_processed_total", "Archivos procesados", ["workspace_hash"])
FILES_FAILED = Counter("ing_files_failed_total", "Archivos con error", ["workspace_hash"])
PROCESS_LATENCY = Histogram(
    "ing_file_process_seconds",
    "Duración del procesamiento (s)",
    ["workspace_hash"],
    buckets=(0.5, 1, 2, 5, 10, 20, 30, 45, 60, 90, 120, 180, 300, 600)
)

# Métricas granulares de OCR
OCR_ATTEMPTS = Counter("ing_ocr_attempts_total", "OCR intentos", ["workspace_hash"])
OCR_SUCCESS = Counter("ing_ocr_success_total", "OCR éxitos", ["workspace_hash"])
OCR_FAIL = Counter("ing_ocr_fail_total", "OCR fallos", ["workspace_hash"])

# Métricas de reintentos
RETRY_SCHEDULED = Counter("ing_retry_scheduled_total", "Reintentos programados", [])
RETRY_EXHAUSTED = Counter("ing_retry_exhausted_total", "Reintentos agotados", [])

# Modelos Pydantic
class FileUploadResponse(BaseModel):
    """Response para upload de archivo"""
    file_id: str = Field(..., description="ID del archivo")
    filename: str = Field(..., description="Nombre del archivo")
    status: str = Field(..., description="Estado del archivo")
    message: str = Field(..., description="Mensaje informativo")

class FileInfo(BaseModel):
    """Información de un archivo"""
    file_id: str = Field(..., description="ID del archivo")
    filename: str = Field(..., description="Nombre del archivo")
    mime_type: str = Field(..., description="Tipo MIME")
    size_bytes: int = Field(..., description="Tamaño en bytes")
    status: str = Field(..., description="Estado del archivo")
    created_at: datetime = Field(..., description="Fecha de creación")
    processed_at: Optional[datetime] = Field(None, description="Fecha de procesamiento")
    error_message: Optional[str] = Field(None, description="Mensaje de error")

class JobStatus(BaseModel):
    """Estado de un job de procesamiento"""
    job_id: str = Field(..., description="ID del job")
    file_id: str = Field(..., description="ID del archivo")
    status: str = Field(..., description="Estado del job")
    progress: int = Field(..., description="Progreso (0-100)")
    message: str = Field(..., description="Mensaje del job")
    created_at: datetime = Field(..., description="Fecha de creación")
    completed_at: Optional[datetime] = Field(None, description="Fecha de finalización")
    error_message: Optional[str] = Field(None, description="Mensaje de error")

class HealthResponse(BaseModel):
    """Response de health check"""
    status: str
    timestamp: datetime
    service: str
    version: str

class FileStorage:
    """Manejador de almacenamiento de archivos"""
    
    def __init__(self):
        self.upload_dir = Path(os.getenv("UPLOAD_DIR", "uploads"))
        self.upload_dir.mkdir(exist_ok=True)
    
    async def save_file(self, file: UploadFile, workspace_id: str) -> Tuple[str, str, str]:
        """Guarda un archivo y retorna (file_id, file_path)"""
        # Generar ID único
        file_id = str(uuid.uuid4())
        
        # Crear directorio del workspace
        workspace_dir = self.upload_dir / workspace_id
        workspace_dir.mkdir(exist_ok=True)
        
        # Generar nombre de archivo único
        file_extension = Path(file.filename).suffix if file.filename else ""
        filename = f"{file_id}{file_extension}"
        temp_file_path = workspace_dir / f"{filename}.tmp"
        final_file_path = workspace_dir / filename
        
        # Guardar archivo temporal por chunks (streaming real)
        async with aiofiles.open(temp_file_path, 'wb') as f:
            chunk = await file.read(1024 * 1024)  # 1MB chunks
            while chunk:
                await f.write(chunk)
                chunk = await file.read(1024 * 1024)
        
        # Establecer permisos seguros (0o640)
        os.chmod(temp_file_path, 0o640)
        
        # Resetear posición del archivo para uso posterior
        await file.seek(0)
        
        return file_id, str(temp_file_path), str(final_file_path)
    
    def get_file_path(self, workspace_id: str, file_id: str) -> Optional[str]:
        """Obtiene la ruta de un archivo, priorizando el final sobre .tmp"""
        workspace_dir = self.upload_dir / workspace_id
        
        # Priorizar archivo final (sin .tmp)
        final = list(workspace_dir.glob(f"{file_id}.*")) + list(workspace_dir.glob(f"{file_id}"))
        if final:
            return str(final[0])
        
        # Fallback a archivo temporal
        tmp = list(workspace_dir.glob(f"{file_id}*.tmp"))
        return str(tmp[0]) if tmp else None
    
    def delete_file(self, workspace_id: str, file_id: str) -> bool:
        """Elimina un archivo"""
        file_path = self.get_file_path(workspace_id, file_id)
        if file_path and os.path.exists(file_path):
            os.remove(file_path)
            return True
        return False
    
    def cleanup_temp_file(self, temp_file_path: str) -> None:
        """Limpia archivo temporal"""
        if os.path.exists(temp_file_path):
            try:
                os.remove(temp_file_path)
                logger.info(f"Archivo temporal eliminado: {temp_file_path}")
            except Exception as e:
                logger.warning(f"Error eliminando archivo temporal {temp_file_path}: {e}")
    
    def finalize_file(self, temp_file_path: str, final_file_path: str) -> None:
        """Mueve archivo temporal a ubicación final"""
        try:
            os.replace(temp_file_path, final_file_path)
            logger.info(f"Archivo finalizado: {final_file_path}")
        except Exception as e:
            logger.error(f"Error finalizando archivo {temp_file_path} -> {final_file_path}: {e}")
            raise

class DatabaseManager:
    """Manejador de base de datos para archivos"""
    
    def __init__(self):
        self.db_url = os.getenv("DATABASE_URL")
    
    async def create_file_record(
        self, 
        file_id: str, 
        workspace_id: str, 
        filename: str, 
        mime_type: str, 
        size_bytes: int,
        temp_file_path: str,
        final_file_path: str
    ) -> tuple[str, bool]:
        """Crea un registro de archivo en la base de datos con deduplicación por hash"""
        def _fn(conn):
            from psycopg2.errors import UniqueViolation
            
            # Calcular hash del archivo temporal
            file_hash = self._calculate_file_hash(temp_file_path)
            
            with conn.cursor() as cur:
                # Establecer contexto RLS
                _set_ws(cur, workspace_id)
                
                try:
                    cur.execute("""
                        INSERT INTO pulpo.files (
                            id, workspace_id, storage_uri, filename, mime_type, 
                            sha256, bytes, status, created_at
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                        RETURNING id
                    """, (
                        file_id, workspace_id, final_file_path, filename, mime_type,
                        file_hash, size_bytes, "uploaded", datetime.now(timezone.utc)
                    ))
                    
                    result = cur.fetchone()
                    conn.commit()
                    return str(result[0]), True  # (file_id, is_new)
                    
                except UniqueViolation:
                    conn.rollback()
                    # Buscar archivo existente con mismo hash
                    cur.execute("""
                        SELECT id FROM pulpo.files 
                        WHERE workspace_id = %s AND sha256 = %s
                    """, (workspace_id, file_hash))
                    row = cur.fetchone()
                    if row:
                        logger.info(f"Archivo duplicado encontrado, reutilizando: {row[0]}")
                        return str(row[0]), False  # (existing_file_id, is_new=False)
                    raise
        
        return await run_db(_fn)
    
    async def update_file_status(self, file_id: str, status: str, error_message: str = None):
        """Actualiza el estado de un archivo"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Obtener workspace_id para contexto RLS
                cur.execute("SELECT workspace_id::text FROM pulpo.files WHERE id=%s", (file_id,))
                row = cur.fetchone()
                if not row: 
                    raise Exception("file not found")
                _set_ws(cur, row[0])
                
                cur.execute("""
                    UPDATE pulpo.files 
                    SET status = %s, last_error = %s, updated_at = %s
                    WHERE id = %s
                """, (status, error_message, datetime.now(timezone.utc), file_id))
                conn.commit()
        
        try:
            await run_db(_fn)
        except Exception as e:
            logger.error(f"Error actualizando estado de archivo: {e}")
            raise
    
    async def get_file_info(self, file_id: str, workspace_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene información de un archivo"""
        try:
            rows = await exec_with_ws(
                workspace_id,
                "SELECT * FROM pulpo.files WHERE id = %s AND workspace_id = %s",
                (file_id, workspace_id),
                dict_cursor=True
            )
            return dict(rows[0]) if rows else None
        except Exception as e:
            logger.error(f"Error obteniendo información de archivo: {e}")
            return None
    
    async def list_files(self, workspace_id: str, limit: int = 50, offset: int = 0, include_deleted: bool = False) -> List[Dict[str, Any]]:
        """Lista archivos de un workspace"""
        try:
            where_clause = "WHERE workspace_id = %s" + ("" if include_deleted else " AND deleted_at IS NULL")
            rows = await exec_with_ws(
                workspace_id,
                f"""
                    SELECT * FROM pulpo.files 
                    {where_clause}
                    ORDER BY created_at DESC 
                    LIMIT %s OFFSET %s
                """,
                (workspace_id, limit, offset),
                dict_cursor=True
            )
            return [dict(row) for row in rows]
        except Exception as e:
            logger.error(f"Error listando archivos: {e}")
            return []
    
    async def delete_file_record(self, file_id: str, workspace_id: str) -> bool:
        """Elimina el registro de un archivo"""
        def _fn(conn):
            with conn.cursor() as cur:
                cur.execute("""
                    DELETE FROM pulpo.files 
                    WHERE id = %s AND workspace_id = %s
                """, (file_id, workspace_id))
                
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        
        try:
            return await run_db(_fn)
        except Exception as e:
            logger.error(f"Error eliminando registro de archivo: {e}")
            return False
    
    def _calculate_file_hash(self, file_path: str) -> str:
        """Calcula hash SHA256 de un archivo"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(4096), b""):
                sha256_hash.update(chunk)
        return sha256_hash.hexdigest()

class DocumentProcessor:
    """Procesador de documentos"""
    
    def __init__(self):
        self.tika_client = TikaClient()
        self.embeddings = OllamaEmbeddings()
        self.smart_processor = SmartDocumentProcessor()
    
    async def process_file(self, file_path: str, workspace_id: str, file_id: str) -> Dict[str, Any]:
        """Procesa un archivo completo"""
        try:
            logger.info(f"Procesando archivo: {file_path}")
            
            # 1. Extraer texto
            text_content = await self._extract_text(file_path, workspace_id)
            if not text_content:
                raise ValueError("No se pudo extraer texto del archivo")
            
            # 2. Procesar con LLM para estructuración
            structured_data = await self._structure_with_llm(text_content, file_path)
            
            # 3. Crear documento
            document_id = await self._create_document(workspace_id, file_id, text_content, structured_data)
            
            # 4. Chunking
            chunks = await self._create_chunks(document_id, text_content, structured_data)
            
            # 5. Generar embeddings
            await self._generate_embeddings(chunks)
            
            return {
                "document_id": document_id,
                "chunks_count": len(chunks),
                "text_length": len(text_content),
                "structured_data": structured_data
            }
            
        except Exception as e:
            logger.error(f"Error procesando archivo: {e}")
            raise
    
    async def _extract_text(self, file_path: str, workspace_id: str) -> str:
        """Extrae texto de un archivo con fallback OCR para PDFs"""
        try:
            # Usar Tika para extracción
            text = await self.tika_client.extract_text(file_path)
            text = (text or "").strip()
            
            # Verificar si hay suficiente texto
            min_text_threshold = int(os.getenv("TIKA_MIN_TEXT_THRESHOLD", "400"))
            if text and len(text) >= min_text_threshold:
                return text
            
            # Fallback OCR si es PDF y está habilitado
            if file_path.lower().endswith(".pdf") and os.getenv("OCR_ENABLED", "false").lower() == "true":
                try:
                    import tempfile
                    import subprocess
                    
                    # Métricas de OCR
                    OCR_ATTEMPTS.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                    
                    logger.info(f"Texto insuficiente ({len(text)} chars), intentando OCR para {file_path}")
                    
                    with tempfile.TemporaryDirectory() as tmp:
                        ocr_pdf = os.path.join(tmp, "ocr.pdf")
                        # Generar PDF "searchable" con OCR (hardening)
                        result = subprocess.run([
                            "ocrmypdf", 
                            "--skip-text", 
                            "--force-ocr", 
                            "--safe-mode",  # Modo seguro
                            "--clean",      # Limpiar PDFs "sucios"
                            file_path, 
                            ocr_pdf
                        ], 
                        check=True, 
                        capture_output=True, 
                        text=True,
                        timeout=120,  # Timeout de 2 minutos
                        cwd=tmp  # Directorio de trabajo seguro
                        )
                        
                        # Re-extraer con Tika sobre el PDF OCR
                        ocr_text = await self.tika_client.extract_text(ocr_pdf)
                        ocr_text = (ocr_text or "").strip()
                        
                        if ocr_text and len(ocr_text) > len(text):
                            OCR_SUCCESS.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                            log_structured("INFO", "OCR exitoso", 
                                         chars_before=len(text), 
                                         chars_after=len(ocr_text),
                                         improvement=len(ocr_text) - len(text))
                            return ocr_text
                        else:
                            OCR_FAIL.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                            log_structured("WARNING", "OCR no mejoró la extracción", 
                                         chars_before=len(text), 
                                         chars_after=len(ocr_text))
                            
                except subprocess.TimeoutExpired as e:
                    OCR_FAIL.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                    logger.error(f"OCR timeout (120s) en {file_path}: {e}")
                except subprocess.CalledProcessError as e:
                    OCR_FAIL.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                    logger.error(f"Error en OCR: {e.stderr}")
                except Exception as e:
                    OCR_FAIL.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                    logger.exception("Error en fallback OCR")
            
            return text
            
        except Exception as e:
            logger.error(f"Error extrayendo texto: {e}")
            return ""
    
    async def _structure_with_llm(self, text_content: str, file_path: str) -> Dict[str, Any]:
        """Estructura el contenido usando LLM"""
        try:
            # Determinar tipo de documento por extensión
            file_extension = Path(file_path).suffix.lower()
            
            if file_extension in ['.pdf', '.docx', '.txt']:
                # Procesar como menú o documento general
                return await self.smart_processor.process_document(text_content, file_path)
            else:
                # Procesar como texto plano
                return {"type": "text", "content": text_content}
                
        except Exception as e:
            logger.error(f"Error estructurando con LLM: {e}")
            return {"type": "text", "content": text_content}
    
    async def _create_document(self, workspace_id: str, file_id: str, text_content: str, structured_data: Dict[str, Any]) -> str:
        """Crea un documento en la base de datos"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Obtener información del archivo
                cur.execute("""
                    SELECT filename, mime_type FROM pulpo.files 
                    WHERE id = %s AND workspace_id = %s
                """, (file_id, workspace_id))
                
                file_info = cur.fetchone()
                if not file_info:
                    raise ValueError("Archivo no encontrado")
                
                filename, mime_type = file_info
                
                # Crear documento
                cur.execute("""
                    INSERT INTO pulpo.documents (
                        workspace_id, file_id, title, language, raw_text, 
                        token_count, created_at
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    workspace_id, file_id, filename, "es", text_content,
                    len(text_content.split()), datetime.now()
                ))
                
                document_id = cur.fetchone()[0]
                conn.commit()
                return str(document_id)
        
        try:
            return await run_db(_fn)
        except Exception as e:
            logger.error(f"Error creando documento: {e}")
            raise
    
    async def _create_revision(self, document_id: str, raw_text: str, structured_data: Dict[str, Any]) -> str:
        """Crea una revisión de documento"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Obtener próximo número de versión
                cur.execute("""
                    SELECT COALESCE(MAX(version), 0) + 1 
                    FROM pulpo.document_revisions 
                    WHERE document_id = %s
                """, (document_id,))
                version = cur.fetchone()[0]
                
                # Crear revisión
                cur.execute("""
                    INSERT INTO pulpo.document_revisions (
                        document_id, version, raw_text, structured_json, created_at
                    ) VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                """, (
                    document_id, version, raw_text, 
                    json.dumps(structured_data), datetime.now()
                ))
                
                revision_id = cur.fetchone()[0]
                conn.commit()
                return str(revision_id)
        
        try:
            return await run_db(_fn)
        except Exception as e:
            logger.error(f"Error creando revisión: {e}")
            raise
    
    async def _create_chunks(self, document_id: str, text_content: str, structured_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Crea chunks del documento con versionado"""
        try:
            # Crear revisión del documento
            revision_id = await self._create_revision(document_id, text_content, structured_data)
            
            # Chunking inteligente basado en el tipo de documento
            if structured_data.get("type") == "menu":
                chunks = await self._chunk_menu(structured_data)
            else:
                chunks = await self._chunk_text(text_content)
            
            # Guardar chunks en base de datos usando helper no bloqueante
            def _fn(conn):
                saved_chunks = []
                with conn.cursor() as cur:
                    for i, chunk_text in enumerate(chunks):
                        cur.execute("""
                            INSERT INTO pulpo.chunks (
                                workspace_id, document_id, pos, text, meta, created_at, revision_id
                            )
                            SELECT 
                                d.workspace_id, 
                                d.id, 
                                %s, 
                                %s, 
                                %s, 
                                %s,
                                %s
                            FROM pulpo.documents d
                            WHERE d.id = %s
                            RETURNING id
                        """, (
                            i, chunk_text,
                            json.dumps({
                                "chunk_index": i, 
                                "doc_type": structured_data.get("type", "text"),
                                "revision_id": revision_id
                            }), 
                            datetime.now(), 
                            revision_id,
                            document_id
                        ))
                        
                        chunk_id = cur.fetchone()[0]
                        saved_chunks.append({
                            "chunk_id": str(chunk_id),
                            "text": chunk_text,
                            "index": i,
                            "revision_id": revision_id
                        })
                    
                    conn.commit()
                return saved_chunks
            
            return await run_db(_fn)
            
        except Exception as e:
            logger.error(f"Error creando chunks: {e}")
            raise
    
    async def _chunk_menu(self, structured_data: Dict[str, Any]) -> List[str]:
        """Chunking específico para menús"""
        chunks = []
        
        # Chunk por categoría
        for categoria, items in structured_data.get("categorias", {}).items():
            chunk_text = f"Categoría: {categoria}\n\n"
            for item in items:
                chunk_text += f"- {item.get('nombre', '')}: ${item.get('precio', 0)}\n"
                if item.get('descripcion'):
                    chunk_text += f"  {item['descripcion']}\n"
            chunks.append(chunk_text.strip())
        
        return chunks
    
    async def _chunk_text(self, text_content: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """Chunking general de texto"""
        words = text_content.split()
        chunks = []
        
        for i in range(0, len(words), chunk_size - overlap):
            chunk_words = words[i:i + chunk_size]
            chunk_text = " ".join(chunk_words)
            chunks.append(chunk_text)
        
        return chunks
    
    async def _generate_embeddings(self, chunks: List[Dict[str, Any]], batch_size: int = 16):
        """Genera embeddings para los chunks en lotes"""
        try:
            # Procesar en lotes para mejor performance
            for i in range(0, len(chunks), batch_size):
                batch = chunks[i:i + batch_size]
                
                # Generar embeddings para el lote
                embeddings = []
                for chunk in batch:
                    embedding = await self.embeddings.generate_embedding(chunk["text"])
                    embeddings.append(embedding)
                
                # Guardar embeddings del lote
                def _fn(conn):
                    with conn.cursor() as cur:
                        for chunk, embedding in zip(batch, embeddings):
                            # Formatear embedding como vector
                            embedding_str = "[" + ",".join(f"{x:.8f}" for x in embedding) + "]"
                            
                            # INSERT con SELECT para obtener workspace_id y document_id
                            cur.execute("""
                                INSERT INTO pulpo.chunk_embeddings (
                                    chunk_id, workspace_id, document_id, embedding, created_at, updated_at
                                )
                                SELECT 
                                    c.id, 
                                    c.workspace_id, 
                                    c.document_id, 
                                    %s::vector,
                                    %s,
                                    %s
                                FROM pulpo.chunks c
                                WHERE c.id = %s
                                ON CONFLICT (chunk_id) DO UPDATE SET
                                    embedding = EXCLUDED.embedding,
                                    updated_at = EXCLUDED.updated_at
                            """, (embedding_str, datetime.now(), datetime.now(), chunk["chunk_id"]))
                        
                        conn.commit()
                
                await run_db(_fn)
                logger.info(f"Embeddings generados para lote {i//batch_size + 1}: {len(batch)} chunks")
                    
        except Exception as e:
            logger.error(f"Error generando embeddings: {e}")
            raise

class IngestionService:
    """Servicio principal de ingesta"""
    
    def __init__(self):
        self.file_storage = FileStorage()
        self.db_manager = DatabaseManager()
        self.document_processor = DocumentProcessor()
        self.processing_jobs = {}  # En producción usar Redis o base de datos
        
        # Límite de concurrencia para procesamiento
        max_concurrent = int(os.getenv("INGESTION_MAX_CONCURRENT", "5"))
        self.processing_limiter = asyncio.Semaphore(max_concurrent)
    
    async def upload_file(
        self, 
        file: UploadFile, 
        workspace_id: str, 
        background_tasks: BackgroundTasks
    ) -> FileUploadResponse:
        """Sube y procesa un archivo"""
        try:
            logger.info(f"Subiendo archivo: {file.filename} para workspace {workspace_id}")
            
            # Validar archivo
            if not file.filename:
                raise HTTPException(status_code=400, detail="Nombre de archivo requerido")
            
            # Validar límite de tamaño
            max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", "10485760"))  # 10MB default
            content_length = int((file.headers or {}).get("content-length", "0") or 0)
            if content_length and content_length > max_bytes:
                raise HTTPException(
                    status_code=413, 
                    detail=f"Archivo demasiado grande. Máximo permitido: {max_bytes} bytes"
                )
            
            # Validar tipo MIME permitido
            allowed_mimes = {
                "application/pdf",
                "text/plain", 
                "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "application/msword",
                "text/csv",
                "application/json"
            }
            
            mime_type, _ = mimetypes.guess_type(file.filename)
            if not mime_type:
                mime_type = "application/octet-stream"
            
            # Fallback por extensión para tipos genéricos
            if mime_type == "application/octet-stream":
                ext = (Path(file.filename).suffix or "").lower()
                fallback = {
                    ".txt": "text/plain",
                    ".pdf": "application/pdf", 
                    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    ".csv": "text/csv",
                    ".json": "application/json",
                    ".doc": "application/msword"
                }
                mime_type = fallback.get(ext, mime_type)
            
            if mime_type not in allowed_mimes:
                raise HTTPException(
                    status_code=415, 
                    detail=f"Tipo MIME no permitido: {mime_type}. Tipos permitidos: {', '.join(allowed_mimes)}"
                )
            
            # Guardar archivo a disco (streaming)
            file_id, temp_file_path, final_file_path = await self.file_storage.save_file(file, workspace_id)
            
            # Obtener tamaño desde el archivo guardado (sin leer a memoria)
            size_bytes = os.stat(temp_file_path).st_size
            
            # Validar tamaño real del archivo
            if size_bytes > max_bytes:
                # Limpiar archivo temporal
                self.file_storage.cleanup_temp_file(temp_file_path)
                raise HTTPException(
                    status_code=413, 
                    detail=f"Archivo demasiado grande. Tamaño real: {size_bytes} bytes, máximo: {max_bytes} bytes"
                )
            
            # Protección contra MIME spoofing (opcional)
            if os.getenv("STRICT_MIME", "false").lower() == "true":
                try:
                    import magic
                    sniffed_mime = magic.from_file(temp_file_path, mime=True)
                    if sniffed_mime not in allowed_mimes:
                        self.file_storage.cleanup_temp_file(temp_file_path)
                        raise HTTPException(
                            status_code=415, 
                            detail=f"Tipo MIME real no permitido: {sniffed_mime}"
                        )
                except ImportError:
                    logger.warning("python-magic no disponible, saltando validación estricta de MIME")
                except Exception as e:
                    logger.warning(f"Error en validación MIME: {e}")
            
            # Crear registro en base de datos con deduplicación
            actual_file_id, is_new = await self.db_manager.create_file_record(
                file_id, workspace_id, file.filename, mime_type, size_bytes, temp_file_path, final_file_path
            )
            
            # Manejar archivos duplicados
            if not is_new:
                # Archivo duplicado - limpiar archivo temporal
                self.file_storage.cleanup_temp_file(temp_file_path)
                logger.info(f"Archivo duplicado detectado, reutilizando: {actual_file_id}")
            else:
                # Archivo nuevo - finalizar guardado
                self.file_storage.finalize_file(temp_file_path, final_file_path)
                # Programar procesamiento en background
                background_tasks.add_task(
                    self._process_file_background, actual_file_id, workspace_id, final_file_path
                )
            
            # Métricas
            FILES_UPLOADED.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
            
            return FileUploadResponse(
                file_id=actual_file_id,
                filename=file.filename,
                status="uploaded" if is_new else "duplicate",
                message="Archivo subido exitosamente, procesamiento iniciado" if is_new else "Archivo duplicado, reutilizando existente"
            )
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error subiendo archivo: {e}")
            raise HTTPException(status_code=500, detail=f"Error subiendo archivo: {str(e)}")
    
    async def _process_file_background(self, file_id: str, workspace_id: str, file_path: str):
        """Procesa archivo en background con límite de concurrencia"""
        import time
        start_time = time.perf_counter()
        
        # Usar semáforo para limitar concurrencia
        async with self.processing_limiter:
            try:
                logger.info(f"Iniciando procesamiento de archivo: {file_id}")
                
                # Marcar como procesando de forma atómica
                if not await self._try_mark_processing(file_id):
                    logger.warning(f"Archivo {file_id} ya no es candidato a procesar, saltando")
                    return
                
                # Procesar archivo con timeout
                timeout_seconds = int(os.getenv("INGESTION_PROCESS_TIMEOUT", "300"))  # 5 min default
                result = await asyncio.wait_for(
                    self.document_processor.process_file(file_path, workspace_id, file_id),
                    timeout=timeout_seconds
                )
                
                # Actualizar estado a procesado
                await self.db_manager.update_file_status(file_id, "processed")
                
                # Métricas de éxito
                FILES_PROCESSED.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                
                logger.info(f"Archivo procesado exitosamente: {file_id}, chunks: {result['chunks_count']}")
                
            except asyncio.TimeoutError:
                error_msg = f"Timeout de procesamiento ({timeout_seconds}s)"
                logger.error(f"Timeout procesando archivo {file_id}: {error_msg}")
                FILES_FAILED.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                await self._mark_failed_with_retry(file_id, error_msg)
                
            except Exception as e:
                # Log completo del error con stack trace
                logger.exception(f"Error procesando archivo {file_id}: {e}")
                
                # Métricas de error
                FILES_FAILED.labels(workspace_hash=get_workspace_hash(workspace_id)).inc()
                
                # Marcar fallo con reintento
                await self._mark_failed_with_retry(file_id, str(e))
            
            finally:
                # Métricas de latencia
                duration = time.perf_counter() - start_time
                PROCESS_LATENCY.labels(workspace_hash=get_workspace_hash(workspace_id)).observe(duration)
    
    async def _try_mark_processing(self, file_id: str) -> bool:
        """Marca un archivo como 'processing' de forma atómica"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Obtener workspace_id para contexto RLS
                cur.execute("SELECT workspace_id::text FROM pulpo.files WHERE id=%s", (file_id,))
                row = cur.fetchone()
                if not row: 
                    return False
                _set_ws(cur, row[0])
                
                cur.execute("""
                    UPDATE pulpo.files
                       SET status = 'processing', updated_at = %s
                     WHERE id = %s
                       AND status NOT IN ('processing','processed')
                       AND deleted_at IS NULL
                """, (datetime.now(timezone.utc), file_id))
                conn.commit()
                return cur.rowcount == 1
        
        try:
            return await run_db(_fn)
        except Exception as e:
            logger.error(f"Error marcando archivo como processing {file_id}: {e}")
            return False
    
    async def get_file_info(self, file_id: str, workspace_id: str) -> Optional[FileInfo]:
        """Obtiene información de un archivo"""
        file_data = await self.db_manager.get_file_info(file_id, workspace_id)
        if not file_data:
            return None
        
        return FileInfo(
            file_id=file_data["id"],
            filename=file_data["filename"],
            mime_type=file_data["mime_type"],
            size_bytes=file_data["bytes"],
            status=file_data["status"],
            created_at=file_data["created_at"],
            processed_at=file_data.get("updated_at") if file_data["status"] == "processed" else None,
            error_message=file_data.get("last_error")
        )
    
    async def list_files(self, workspace_id: str, limit: int = 50, offset: int = 0, include_deleted: bool = False) -> List[FileInfo]:
        """Lista archivos de un workspace"""
        files_data = await self.db_manager.list_files(workspace_id, limit, offset, include_deleted)
        
        return [
            FileInfo(
                file_id=file_data["id"],
                filename=file_data["filename"],
                mime_type=file_data["mime_type"],
                size_bytes=file_data["bytes"],
                status=file_data["status"],
                created_at=file_data["created_at"],
                processed_at=file_data.get("updated_at") if file_data["status"] == "processed" else None,
                error_message=file_data.get("last_error")
            )
            for file_data in files_data
        ]
    
    async def delete_file(self, file_id: str, workspace_id: str) -> bool:
        """Elimina un archivo y purga todos sus datos RAG"""
        try:
            # Eliminar archivo del almacenamiento (best effort)
            self.file_storage.delete_file(workspace_id, file_id)
            
            # Purga completa en cascada
            return await self.purge_file_everywhere(file_id, workspace_id)
            
        except Exception as e:
            logger.error(f"Error eliminando archivo: {e}")
            return False
    
    async def soft_delete_file(self, file_id: str, workspace_id: str) -> bool:
        """Marca un archivo para eliminación (soft-delete) con ventana de gracia"""
        PURGE_WINDOW_DAYS = int(os.getenv("INGESTION_PURGE_WINDOW_DAYS", "7"))
        
        def _fn(conn):
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE pulpo.files
                       SET deleted_at = now(),
                           purge_at   = now() + (%s || ' days')::interval,
                           status     = CASE WHEN status='processed' THEN status ELSE 'deleted' END
                     WHERE id = %s AND workspace_id = %s
                """, (PURGE_WINDOW_DAYS, file_id, workspace_id))
                updated = cur.rowcount > 0
                conn.commit()
                return updated
        
        try:
            return await run_db(_fn)
        except Exception as e:
            logger.error(f"Error en soft-delete: {e}")
            return False
    
    async def _mark_failed_with_retry(self, file_id: str, error_message: str):
        """Marca un archivo como fallido con lógica de reintentos"""
        MAX_ATTEMPTS = int(os.getenv("INGESTION_MAX_ATTEMPTS", "3"))
        
        def _fn(conn):
            with conn.cursor() as cur:
                # Obtener workspace_id para contexto RLS
                cur.execute("SELECT workspace_id::text FROM pulpo.files WHERE id=%s", (file_id,))
                row = cur.fetchone()
                if not row: 
                    return
                _set_ws(cur, row[0])
                
                # Leer intentos actuales
                cur.execute("SELECT attempts FROM pulpo.files WHERE id = %s", (file_id,))
                result = cur.fetchone()
                attempts = (result[0] if result else 0) or 0
                attempts += 1
                
                if attempts < MAX_ATTEMPTS:
                    # Backoff exponencial: 5 * 3^(attempts-1) minutos
                    backoff_minutes = 5 * (3 ** max(attempts - 1, 0))
                    cur.execute("""
                        UPDATE pulpo.files
                           SET status = 'failed',
                               last_error = %s,
                               attempts = %s,
                               next_retry_at = %s + ((%s || ' minutes')::interval)
                         WHERE id = %s
                    """, (error_message[:4000], attempts, datetime.now(timezone.utc), backoff_minutes, file_id))
                    RETRY_SCHEDULED.inc()
                    logger.info(f"Archivo {file_id} marcado para reintento {attempts}/{MAX_ATTEMPTS} en {backoff_minutes} minutos")
                else:
                    cur.execute("""
                        UPDATE pulpo.files
                           SET status = 'failed',
                               last_error = %s,
                               attempts = %s,
                               next_retry_at = NULL
                         WHERE id = %s
                    """, (error_message[:4000], attempts, file_id))
                    RETRY_EXHAUSTED.inc()
                    logger.warning(f"Archivo {file_id} falló definitivamente después de {attempts} intentos")
                
                conn.commit()
        
        try:
            await run_db(_fn)
        except Exception as e:
            logger.error(f"Error marcando fallo con reintento: {e}")
    
    async def purge_file_everywhere(self, file_id: str, workspace_id: str) -> bool:
        """Purga archivo y todos sus datos RAG en cascada"""
        def _fn(conn):
            with conn.cursor() as cur:
                # Encontrar documentos de ese archivo
                cur.execute("""
                    SELECT id FROM pulpo.documents 
                    WHERE file_id = %s AND workspace_id = %s
                """, (file_id, workspace_id))
                docs = [r[0] for r in cur.fetchall()]
                
                # Borrar en orden seguro (dependencias primero)
                if docs:
                    # Borrar embeddings de chunks
                    cur.execute("""
                        DELETE FROM pulpo.chunk_embeddings 
                        WHERE document_id = ANY(%s) AND workspace_id = %s
                    """, (docs, workspace_id))
                    
                    # Borrar chunks
                    cur.execute("""
                        DELETE FROM pulpo.chunks 
                        WHERE document_id = ANY(%s) AND workspace_id = %s
                    """, (docs, workspace_id))
                    
                    # Borrar documentos
                    cur.execute("""
                        DELETE FROM pulpo.documents 
                        WHERE id = ANY(%s) AND workspace_id = %s
                    """, (docs, workspace_id))
                
                # Finalmente, borrar archivo
                cur.execute("""
                    DELETE FROM pulpo.files 
                    WHERE id = %s AND workspace_id = %s
                """, (file_id, workspace_id))
                
                deleted = cur.rowcount > 0
                conn.commit()
                return deleted
        
        return await run_db(_fn)
    
    async def reingest_file(self, file_id: str, workspace_id: str, background_tasks: BackgroundTasks) -> bool:
        """Re-procesa un archivo"""
        try:
            # Obtener información del archivo
            file_data = await self.db_manager.get_file_info(file_id, workspace_id)
            if not file_data:
                return False
            
            # Obtener ruta del archivo
            file_path = self.file_storage.get_file_path(workspace_id, file_id)
            if not file_path:
                return False
            
            # Programar re-procesamiento
            background_tasks.add_task(
                self._process_file_background, file_id, workspace_id, file_path
            )
            
            return True
            
        except Exception as e:
            logger.error(f"Error re-procesando archivo: {e}")
            return False

# Crear aplicación FastAPI
app = FastAPI(
    title="PulpoAI Ingestion Service",
    description="Servicio para ingesta y procesamiento de documentos",
    version="2.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Función de validación de UUID
def validate_workspace_uuid(value: str) -> str:
    """Valida que el workspace_id sea un UUID v4 válido"""
    try:
        uuid.UUID(value, version=4)
        return value
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid workspace ID format. Must be a valid UUID v4")

# Instancia del servicio
ingestion_service = IngestionService()

@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check del servicio"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now(timezone.utc),
        service="ingestion",
        version="2.0.0"
    )

@app.get("/metrics")
async def metrics(x_metrics_key: Optional[str] = Header(None, alias="X-Metrics-Key")):
    """Endpoint de métricas Prometheus"""
    # Verificar clave de métricas si está configurada
    key = os.getenv("METRICS_KEY")
    if key and x_metrics_key != key:
        raise HTTPException(status_code=403, detail="Forbidden")
    
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)

@app.post("/files", response_model=FileUploadResponse)
async def upload_file(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """
    Sube un archivo para procesamiento
    """
    workspace_id = validate_workspace_uuid(x_workspace_id)
    return await ingestion_service.upload_file(file, workspace_id, background_tasks)

@app.get("/files", response_model=List[FileInfo])
async def list_files(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    limit: int = 50,
    offset: int = 0,
    include_deleted: bool = False
):
    """
    Lista archivos de un workspace
    """
    workspace_id = validate_workspace_uuid(x_workspace_id)
    return await ingestion_service.list_files(workspace_id, limit, offset, include_deleted)

@app.get("/files/{file_id}", response_model=FileInfo)
async def get_file_info(file_id: str, x_workspace_id: str = Header(..., alias="X-Workspace-Id")):
    """
    Obtiene información de un archivo específico
    """
    workspace_id = validate_workspace_uuid(x_workspace_id)
    file_info = await ingestion_service.get_file_info(file_id, workspace_id)
    if not file_info:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return file_info

@app.delete("/files/{file_id}")
async def soft_delete_file(file_id: str, x_workspace_id: str = Header(..., alias="X-Workspace-Id")):
    """
    Marca un archivo para eliminación (soft-delete) con ventana de gracia
    """
    workspace_id = validate_workspace_uuid(x_workspace_id)
    success = await ingestion_service.soft_delete_file(file_id, workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"message": "Archivo marcado para eliminación (soft-delete)"}

@app.delete("/files/{file_id}/purge")
async def hard_delete_file(file_id: str, x_workspace_id: str = Header(..., alias="X-Workspace-Id")):
    """
    Elimina un archivo inmediatamente (hard-delete) - solo para casos especiales
    """
    workspace_id = validate_workspace_uuid(x_workspace_id)
    success = await ingestion_service.delete_file(file_id, workspace_id)
    if not success:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"message": "Archivo y datos asociados eliminados exitosamente"}

@app.post("/files/{file_id}/reingest")
async def reingest_file(
    file_id: str,
    background_tasks: BackgroundTasks,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """
    Re-procesa un archivo
    """
    workspace_id = validate_workspace_uuid(x_workspace_id)
    success = await ingestion_service.reingest_file(file_id, workspace_id, background_tasks)
    if not success:
        raise HTTPException(status_code=404, detail="Archivo no encontrado")
    return {"message": "Re-procesamiento iniciado"}

@app.post("/files/test")
async def test_upload():
    """
    Endpoint de testing para validar el funcionamiento de la ingesta
    (solo disponible si ENABLE_TEST_ENDPOINT=true)
    """
    if os.getenv("ENABLE_TEST_ENDPOINT", "false").lower() != "true":
        raise HTTPException(status_code=404, detail="Not found")
    
    try:
        # Crear archivo de prueba
        test_content = """
        MENÚ DEL RESTAURANTE
        
        EMPANADAS
        - Empanada de Carne: $500
        - Empanada de Pollo: $500
        - Empanada de Jamón y Queso: $500
        
        PIZZAS
        - Pizza Margherita: $1200
        - Pizza Napolitana: $1400
        - Pizza Especial: $1600
        """
        
        # Simular upload
        from io import BytesIO
        from starlette.datastructures import UploadFile as StarletteUploadFile
        test_file = StarletteUploadFile(
            filename="test_menu.txt",
            file=BytesIO(test_content.encode())
        )
        
        # Usar un UUID válido para tests
        TEST_WS = os.getenv("TEST_WORKSPACE_ID", "123e4567-e89b-12d3-a456-426614174000")
        
        # Procesar archivo de prueba
        result = await ingestion_service.upload_file(test_file, TEST_WS, BackgroundTasks())
        
        return {
            "test": "success",
            "file_id": result.file_id,
            "filename": result.filename,
            "status": result.status
        }
        
    except Exception as e:
        logger.error(f"Error en test: {e}")
        raise HTTPException(status_code=500, detail=f"Error en test: {str(e)}")

# Event handlers
@app.on_event("startup")
async def startup_event():
    """Evento de inicio de la aplicación"""
    logger.info("🚀 Ingestion Service iniciado")
    logger.info("📋 Endpoints disponibles:")
    logger.info("  - POST /files - Subir archivo")
    logger.info("  - GET /files - Listar archivos")
    logger.info("  - GET /files/{file_id} - Info de archivo")
    logger.info("  - DELETE /files/{file_id} - Eliminar archivo")
    logger.info("  - POST /files/{file_id}/reingest - Re-procesar archivo")
    logger.info("  - POST /files/test - Testing")
    logger.info("  - GET /health - Health check")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "ingestion_service:app",
        host="0.0.0.0",
        port=8007,
        reload=True,
        log_level="info"
    )
