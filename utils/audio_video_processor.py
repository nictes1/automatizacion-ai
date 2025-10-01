#!/usr/bin/env python3
"""
Procesador de Audio y Video para RAG
Convierte audio/video a texto para generar embeddings
"""

import os
import logging
import subprocess
import tempfile
from typing import Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class AudioVideoProcessor:
    """Procesador de archivos de audio y video"""
    
    # Tipos de archivos soportados
    AUDIO_EXTENSIONS = {
        '.mp3', '.wav', '.flac', '.aac', '.ogg', '.m4a', '.wma'
    }
    
    VIDEO_EXTENSIONS = {
        '.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm', '.m4v'
    }
    
    def __init__(self, whisper_model: str = "base"):
        self.whisper_model = whisper_model
        self._check_dependencies()
    
    def _check_dependencies(self):
        """Verifica que las dependencias estén instaladas"""
        try:
            # Verificar ffmpeg
            subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
            logger.info("✅ FFmpeg disponible")
        except (subprocess.CalledProcessError, FileNotFoundError):
            logger.warning("⚠️ FFmpeg no encontrado. Instalar con: apt-get install ffmpeg")
        
        try:
            # Verificar whisper
            import whisper
            logger.info("✅ Whisper disponible")
        except ImportError:
            logger.warning("⚠️ Whisper no encontrado. Instalar con: pip install openai-whisper")
    
    def is_audio_file(self, file_path: str) -> bool:
        """Verifica si es un archivo de audio"""
        return Path(file_path).suffix.lower() in self.AUDIO_EXTENSIONS
    
    def is_video_file(self, file_path: str) -> bool:
        """Verifica si es un archivo de video"""
        return Path(file_path).suffix.lower() in self.VIDEO_EXTENSIONS
    
    def extract_audio_from_video(self, video_path: str) -> str:
        """Extrae audio de un video"""
        try:
            # Crear archivo temporal para el audio
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio.close()
            
            # Extraer audio con ffmpeg
            cmd = [
                'ffmpeg', '-i', video_path,
                '-vn',  # No video
                '-acodec', 'pcm_s16le',  # Codec de audio
                '-ar', '16000',  # Sample rate para Whisper
                '-ac', '1',  # Mono
                '-y',  # Sobrescribir
                temp_audio.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Error extrayendo audio: {result.stderr}")
            
            logger.info(f"✅ Audio extraído: {temp_audio.name}")
            return temp_audio.name
            
        except Exception as e:
            logger.error(f"Error extrayendo audio: {e}")
            raise
    
    def transcribe_audio(self, audio_path: str, language: str = None) -> str:
        """Transcribe audio a texto usando Whisper"""
        try:
            import whisper
            
            # Cargar modelo Whisper
            model = whisper.load_model(self.whisper_model)
            
            # Transcribir
            result = model.transcribe(
                audio_path,
                language=language,
                fp16=False  # Para compatibilidad con CPU
            )
            
            text = result["text"].strip()
            logger.info(f"✅ Transcripción completada: {len(text)} caracteres")
            
            return text
            
        except ImportError:
            logger.error("Whisper no está instalado. Instalar con: pip install openai-whisper")
            raise
        except Exception as e:
            logger.error(f"Error transcribiendo audio: {e}")
            raise
    
    def process_audio_file(self, file_path: str, language: str = None) -> str:
        """Procesa un archivo de audio completo"""
        if not self.is_audio_file(file_path):
            raise ValueError(f"No es un archivo de audio soportado: {file_path}")
        
        # Convertir a formato compatible con Whisper si es necesario
        temp_audio = self._convert_audio_for_whisper(file_path)
        
        try:
            # Transcribir
            text = self.transcribe_audio(temp_audio, language)
            return text
        finally:
            # Limpiar archivo temporal
            if temp_audio != file_path and os.path.exists(temp_audio):
                os.unlink(temp_audio)
    
    def process_video_file(self, file_path: str, language: str = None) -> str:
        """Procesa un archivo de video completo"""
        if not self.is_video_file(file_path):
            raise ValueError(f"No es un archivo de video soportado: {file_path}")
        
        # Extraer audio del video
        temp_audio = self.extract_audio_from_video(file_path)
        
        try:
            # Transcribir audio
            text = self.transcribe_audio(temp_audio, language)
            return text
        finally:
            # Limpiar archivo temporal
            if os.path.exists(temp_audio):
                os.unlink(temp_audio)
    
    def _convert_audio_for_whisper(self, audio_path: str) -> str:
        """Convierte audio a formato compatible con Whisper"""
        try:
            # Verificar si ya está en formato compatible
            if audio_path.lower().endswith('.wav'):
                return audio_path
            
            # Crear archivo temporal
            temp_audio = tempfile.NamedTemporaryFile(suffix='.wav', delete=False)
            temp_audio.close()
            
            # Convertir con ffmpeg
            cmd = [
                'ffmpeg', '-i', audio_path,
                '-acodec', 'pcm_s16le',
                '-ar', '16000',
                '-ac', '1',
                '-y',
                temp_audio.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode != 0:
                raise Exception(f"Error convirtiendo audio: {result.stderr}")
            
            return temp_audio.name
            
        except Exception as e:
            logger.error(f"Error convirtiendo audio: {e}")
            # Si falla la conversión, intentar con el archivo original
            return audio_path
    
    def get_audio_duration(self, audio_path: str) -> float:
        """Obtiene la duración del audio en segundos"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-show_entries', 'format=duration',
                '-of', 'csv=p=0',
                audio_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                return float(result.stdout.strip())
            else:
                return 0.0
                
        except Exception as e:
            logger.error(f"Error obteniendo duración: {e}")
            return 0.0
    
    def get_video_info(self, video_path: str) -> dict:
        """Obtiene información del video"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet',
                '-print_format', 'json',
                '-show_format',
                '-show_streams',
                video_path
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            
            if result.returncode == 0:
                import json
                return json.loads(result.stdout)
            else:
                return {}
                
        except Exception as e:
            logger.error(f"Error obteniendo info del video: {e}")
            return {}

# Función de utilidad para detectar idioma automáticamente
def detect_audio_language(audio_path: str) -> str:
    """Detecta el idioma del audio usando Whisper"""
    try:
        import whisper
        
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, language=None)  # Auto-detectar
        
        # Whisper retorna el idioma detectado
        detected_language = result.get("language", "en")
        
        # Mapear códigos de idioma
        language_map = {
            "es": "español",
            "en": "inglés", 
            "fr": "francés",
            "de": "alemán",
            "it": "italiano",
            "pt": "portugués"
        }
        
        return language_map.get(detected_language, detected_language)
        
    except Exception as e:
        logger.error(f"Error detectando idioma: {e}")
        return "desconocido"

if __name__ == "__main__":
    # Prueba del procesador
    processor = AudioVideoProcessor()
    
    # Probar con archivo de audio
    audio_file = "test_audio.mp3"
    if os.path.exists(audio_file):
        try:
            text = processor.process_audio_file(audio_file)
            print(f"✅ Transcripción: {text[:200]}...")
        except Exception as e:
            print(f"❌ Error: {e}")
    
    # Probar con archivo de video
    video_file = "test_video.mp4"
    if os.path.exists(video_file):
        try:
            text = processor.process_video_file(video_file)
            print(f"✅ Transcripción: {text[:200]}...")
        except Exception as e:
            print(f"❌ Error: {e}")

