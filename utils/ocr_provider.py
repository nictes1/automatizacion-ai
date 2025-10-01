"""
OCR Provider - Interfaz pluggable para extracción de texto
Soporta Tesseract por defecto, extensible para GCP/AWS
"""
import os
import subprocess
import tempfile
import logging
from abc import ABC, abstractmethod
from typing import Tuple, Dict, Any

import anyio

logger = logging.getLogger(__name__)

class OCRProvider(ABC):
    """Interfaz abstracta para providers de OCR"""
    
    @abstractmethod
    async def extract_text(self, storage_url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extrae texto de un archivo
        
        Args:
            storage_url: URL del archivo (file://, s3://, gs://, etc.)
            
        Returns:
            Tuple[texto_extraido, metadatos]
        """
        pass

class TesseractOCRProvider(OCRProvider):
    """
    Provider de OCR usando Tesseract CLI
    Soporta: PDF/TIFF/JPG/PNG descargados a archivo temporal
    """
    
    def __init__(self):
        self.cmd = os.getenv("TESSERACT_CMD", "tesseract")
        self.lang = os.getenv("TESSERACT_LANG", "spa")
    
    async def _download(self, storage_url: str, dst_path: str):
        """
        Descarga archivo desde storage_url a dst_path
        Placeholder: implementar fetch real para S3/GCS
        """
        if storage_url.startswith("file://"):
            # Archivo local
            src = storage_url.replace("file://", "")
            await anyio.Path(src).copy(dst_path)
        elif storage_url.startswith("/"):
            # Ruta absoluta
            await anyio.Path(storage_url).copy(dst_path)
        else:
            # URL remota - implementar según necesidad
            raise RuntimeError(f"storage_url no soportado: {storage_url} (implementa fetch S3/GCS)")
    
    async def extract_text(self, storage_url: str) -> Tuple[str, Dict[str, Any]]:
        """
        Extrae texto usando Tesseract
        """
        meta: Dict[str, Any] = {
            "engine": "tesseract",
            "lang": self.lang,
            "source_url": storage_url
        }
        
        with tempfile.TemporaryDirectory() as td:
            in_file = os.path.join(td, "input")
            out_file = os.path.join(td, "out")
            
            # Descargar archivo
            await self._download(storage_url, in_file)
            
            # Comando Tesseract
            cmd = [
                self.cmd, 
                in_file, 
                out_file, 
                "-l", self.lang,
                "--oem", "1",  # LSTM OCR Engine Mode
                "--psm", "3"   # Fully automatic page segmentation
            ]
            
            # Ejecutar Tesseract
            proc = await anyio.to_thread.run_sync(
                subprocess.run, 
                cmd, 
                capture_output=True, 
                text=True
            )
            
            if proc.returncode != 0:
                logger.error(f"Tesseract error: {proc.stderr}")
                raise RuntimeError(f"Tesseract failed: {proc.stderr}")
            
            # Leer resultado
            txt = await anyio.Path(out_file + ".txt").read_text(encoding='utf-8')
            
            # Metadatos adicionales
            meta.update({
                "text_length": len(txt),
                "extraction_time": "now",  # En producción, medir tiempo real
                "tesseract_version": proc.stdout.strip() if proc.stdout else "unknown"
            })
            
            return txt, meta

class MockOCRProvider(OCRProvider):
    """
    Provider mock para testing
    """
    
    async def extract_text(self, storage_url: str) -> Tuple[str, Dict[str, Any]]:
        """Mock que devuelve texto de prueba"""
        mock_text = f"Texto extraído de {storage_url} usando OCR mock"
        mock_meta = {
            "engine": "mock",
            "source_url": storage_url,
            "text_length": len(mock_text),
            "extraction_time": "now"
        }
        return mock_text, mock_meta

# Factory function para crear providers
def create_ocr_provider(provider_type: str = None) -> OCRProvider:
    """
    Factory para crear providers de OCR
    
    Args:
        provider_type: Tipo de provider ("tesseract", "mock", etc.)
        
    Returns:
        Instancia del provider
    """
    if provider_type == "mock":
        return MockOCRProvider()
    else:
        return TesseractOCRProvider()
