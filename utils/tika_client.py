#!/usr/bin/env python3
"""
Cliente para Apache Tika Server
Extrae texto de archivos usando Tika Server
"""

import requests
import logging
from typing import Optional, Dict, Any
from pathlib import Path
import time

logger = logging.getLogger(__name__)

class TikaClient:
    """Cliente para Apache Tika Server"""
    
    def __init__(self, base_url: str = "http://localhost:9998", timeout: int = 90):
        self.base_url = base_url.rstrip('/')
        self.timeout = timeout
        self.session = requests.Session()
        
    def health_check(self) -> bool:
        """Verifica si Tika Server está disponible"""
        try:
            response = self.session.get(f"{self.base_url}/tika", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Tika health check failed: {e}")
            return False
    
    def extract_text(self, file_path: str, mime_type: Optional[str] = None) -> str:
        """Extrae texto de un archivo"""
        try:
            with open(file_path, 'rb') as f:
                return self._extract_from_stream(f, mime_type)
        except Exception as e:
            logger.error(f"Error extrayendo texto de {file_path}: {e}")
            raise
    
    def extract_text_from_bytes(self, file_bytes: bytes, mime_type: Optional[str] = None) -> str:
        """Extrae texto de bytes de archivo"""
        try:
            import io
            stream = io.BytesIO(file_bytes)
            return self._extract_from_stream(stream, mime_type)
        except Exception as e:
            logger.error(f"Error extrayendo texto de bytes: {e}")
            raise
    
    def _extract_from_stream(self, stream, mime_type: Optional[str] = None) -> str:
        """Extrae texto de un stream"""
        try:
            headers = {
                'Accept': 'text/plain; charset=UTF-8'
            }
            
            if mime_type:
                headers['Content-Type'] = mime_type
            
            response = self.session.put(
                f"{self.base_url}/tika",
                data=stream,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code >= 300:
                raise Exception(f"Tika error {response.status_code}: {response.text}")
            
            return response.text
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout extrayendo texto (>{self.timeout}s)")
        except Exception as e:
            logger.error(f"Error en extracción Tika: {e}")
            raise
    
    def extract_metadata(self, file_path: str) -> Dict[str, Any]:
        """Extrae metadatos de un archivo"""
        try:
            with open(file_path, 'rb') as f:
                return self._extract_metadata_from_stream(f)
        except Exception as e:
            logger.error(f"Error extrayendo metadatos de {file_path}: {e}")
            raise
    
    def _extract_metadata_from_stream(self, stream) -> Dict[str, Any]:
        """Extrae metadatos de un stream"""
        try:
            headers = {
                'Accept': 'application/json'
            }
            
            response = self.session.put(
                f"{self.base_url}/meta",
                data=stream,
                headers=headers,
                timeout=self.timeout
            )
            
            if response.status_code >= 300:
                raise Exception(f"Tika metadata error {response.status_code}: {response.text}")
            
            return response.json()
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout extrayendo metadatos (>{self.timeout}s)")
        except Exception as e:
            logger.error(f"Error en extracción de metadatos Tika: {e}")
            raise
    
    def detect_mime_type(self, file_path: str) -> str:
        """Detecta el tipo MIME de un archivo"""
        try:
            with open(file_path, 'rb') as f:
                return self._detect_mime_type_from_stream(f)
        except Exception as e:
            logger.error(f"Error detectando MIME type de {file_path}: {e}")
            raise
    
    def _detect_mime_type_from_stream(self, stream) -> str:
        """Detecta el tipo MIME de un stream"""
        try:
            response = self.session.put(
                f"{self.base_url}/detect/stream",
                data=stream,
                timeout=self.timeout
            )
            
            if response.status_code >= 300:
                raise Exception(f"Tika MIME detection error {response.status_code}: {response.text}")
            
            return response.text.strip()
            
        except requests.exceptions.Timeout:
            raise Exception(f"Timeout detectando MIME type (>{self.timeout}s)")
        except Exception as e:
            logger.error(f"Error en detección MIME Tika: {e}")
            raise
    
    def wait_for_ready(self, max_retries: int = 30, retry_delay: int = 2) -> bool:
        """Espera a que Tika Server esté listo"""
        for attempt in range(max_retries):
            if self.health_check():
                logger.info("Tika Server está listo")
                return True
            
            logger.info(f"Esperando Tika Server... intento {attempt + 1}/{max_retries}")
            time.sleep(retry_delay)
        
        logger.error("Tika Server no está disponible después de todos los intentos")
        return False

# Función de utilidad para normalizar texto extraído
def normalize_extracted_text(text: str) -> str:
    """Normaliza el texto extraído por Tika"""
    if not text:
        return ""
    
    # Normalizar espacios en blanco
    import re
    text = re.sub(r'\s+', ' ', text)
    
    # Limpiar caracteres de control
    text = ''.join(char for char in text if ord(char) >= 32 or char in '\n\t')
    
    # Normalizar saltos de línea
    lines = text.split('\n')
    normalized_lines = []
    
    for line in lines:
        line = line.strip()
        if line:  # Solo agregar líneas no vacías
            normalized_lines.append(line)
    
    return '\n'.join(normalized_lines)

if __name__ == "__main__":
    # Prueba del cliente
    client = TikaClient()
    
    if client.wait_for_ready():
        print("✅ Tika Server está disponible")
        
        # Prueba con un archivo de ejemplo
        test_file = "test.txt"
        if Path(test_file).exists():
            try:
                text = client.extract_text(test_file)
                print(f"✅ Texto extraído: {len(text)} caracteres")
                print(f"Primeras 200 caracteres: {text[:200]}...")
            except Exception as e:
                print(f"❌ Error: {e}")
        else:
            print("⚠️ Archivo de prueba no encontrado")
    else:
        print("❌ Tika Server no está disponible")

