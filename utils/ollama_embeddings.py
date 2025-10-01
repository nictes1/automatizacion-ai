#!/usr/bin/env python3
"""
Cliente para generación de embeddings con Ollama
"""

import requests
import logging
import json
import os
from typing import List, Optional, Dict, Any
import time
from config import Config

logger = logging.getLogger(__name__)

class OllamaEmbeddings:
    """Cliente para generar embeddings con Ollama"""
    
    def __init__(self, base_url: str = None, model: str = None):
        """
        Inicializa el cliente de embeddings de Ollama
        
        Args:
            base_url: URL base de Ollama (por defecto desde variable de entorno)
            model: Modelo de embeddings (por defecto desde variable de entorno)
        """
        self.base_url = (base_url or Config.OLLAMA_URL).rstrip('/')
        self.model = model or Config.EMBEDDING_MODEL
        self.session = requests.Session()
        self.dims = Config.EMBEDDING_DIMS
        
    def health_check(self) -> bool:
        """Verifica si Ollama está disponible"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=10)
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Ollama health check failed: {e}")
            return False
    
    def get_model_info(self) -> Dict[str, Any]:
        """Obtiene información del modelo"""
        try:
            response = self.session.get(f"{self.base_url}/api/tags")
            if response.status_code == 200:
                models = response.json().get('models', [])
                for model_info in models:
                    if model_info['name'].startswith(self.model):
                        return model_info
            return {}
        except Exception as e:
            logger.error(f"Error obteniendo info del modelo: {e}")
            return {}
    
    def generate_embedding(self, text: str) -> List[float]:
        """Genera embedding para un texto"""
        try:
            payload = {
                "model": self.model,
                "prompt": text
            }
            
            response = self.session.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=60
            )
            
            if response.status_code != 200:
                raise Exception(f"Ollama error {response.status_code}: {response.text}")
            
            result = response.json()
            embedding = result.get('embedding', [])
            
            if not embedding:
                raise Exception("No se recibió embedding del modelo")
            
            # Actualizar dimensiones si es la primera vez
            if len(embedding) != self.dims:
                self.dims = len(embedding)
                logger.info(f"Dimensiones del modelo actualizadas: {self.dims}")
            
            return embedding
            
        except requests.exceptions.Timeout:
            raise Exception("Timeout generando embedding (>60s)")
        except Exception as e:
            logger.error(f"Error generando embedding: {e}")
            raise
    
    def generate_embeddings_batch(self, texts: List[str], batch_size: int = 10) -> List[List[float]]:
        """Genera embeddings para múltiples textos en lotes"""
        embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            logger.info(f"Procesando lote {i//batch_size + 1}/{(len(texts) + batch_size - 1)//batch_size}")
            
            batch_embeddings = []
            for text in batch:
                try:
                    embedding = self.generate_embedding(text)
                    batch_embeddings.append(embedding)
                except Exception as e:
                    logger.error(f"Error en embedding del lote: {e}")
                    # Agregar embedding de ceros como fallback
                    batch_embeddings.append([0.0] * self.dims)
            
            embeddings.extend(batch_embeddings)
            
            # Pequeña pausa entre lotes para no sobrecargar
            if i + batch_size < len(texts):
                time.sleep(0.1)
        
        return embeddings
    
    def wait_for_ready(self, max_retries: int = 30, retry_delay: int = 2) -> bool:
        """Espera a que Ollama esté listo"""
        for attempt in range(max_retries):
            if self.health_check():
                # Verificar que el modelo esté disponible
                model_info = self.get_model_info()
                if model_info:
                    logger.info(f"Ollama está listo con modelo: {self.model}")
                    return True
                else:
                    logger.warning(f"Modelo {self.model} no encontrado, intentando descargar...")
                    self._pull_model()
            
            logger.info(f"Esperando Ollama... intento {attempt + 1}/{max_retries}")
            time.sleep(retry_delay)
        
        logger.error("Ollama no está disponible después de todos los intentos")
        return False
    
    def _pull_model(self) -> bool:
        """Descarga el modelo si no está disponible"""
        try:
            payload = {
                "name": self.model,
                "stream": False
            }
            
            response = self.session.post(
                f"{self.base_url}/api/pull",
                json=payload,
                timeout=300  # 5 minutos para descargar
            )
            
            if response.status_code == 200:
                logger.info(f"Modelo {self.model} descargado exitosamente")
                return True
            else:
                logger.error(f"Error descargando modelo: {response.status_code} - {response.text}")
                return False
                
        except Exception as e:
            logger.error(f"Error descargando modelo: {e}")
            return False
    
    def get_embedding_dimensions(self) -> int:
        """Retorna las dimensiones del embedding"""
        return self.dims
    
    def test_embedding(self) -> bool:
        """Prueba la generación de embeddings"""
        try:
            test_text = "Este es un texto de prueba para generar embeddings."
            embedding = self.generate_embedding(test_text)
            
            if len(embedding) > 0:
                logger.info(f"✅ Test de embedding exitoso: {len(embedding)} dimensiones")
                return True
            else:
                logger.error("❌ Test de embedding falló: embedding vacío")
                return False
                
        except Exception as e:
            logger.error(f"❌ Test de embedding falló: {e}")
            return False

# Función de utilidad para calcular similitud coseno
def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
    """Calcula la similitud coseno entre dos vectores"""
    import math
    
    if len(vec1) != len(vec2):
        raise ValueError("Los vectores deben tener la misma dimensión")
    
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    magnitude1 = math.sqrt(sum(a * a for a in vec1))
    magnitude2 = math.sqrt(sum(a * a for a in vec2))
    
    if magnitude1 == 0 or magnitude2 == 0:
        return 0.0
    
    return dot_product / (magnitude1 * magnitude2)

# Función de utilidad para normalizar vectores
def normalize_vector(vec: List[float]) -> List[float]:
    """Normaliza un vector a longitud unitaria"""
    import math
    
    magnitude = math.sqrt(sum(a * a for a in vec))
    if magnitude == 0:
        return vec
    
    return [a / magnitude for a in vec]

if __name__ == "__main__":
    # Prueba del cliente
    client = OllamaEmbeddings()
    
    if client.wait_for_ready():
        print("✅ Ollama está disponible")
        
        if client.test_embedding():
            print("✅ Generación de embeddings funcionando")
            
            # Prueba con múltiples textos
            test_texts = [
                "Este es el primer texto de prueba.",
                "Este es el segundo texto de prueba.",
                "Este es un texto completamente diferente."
            ]
            
            try:
                embeddings = client.generate_embeddings_batch(test_texts)
                print(f"✅ Generados {len(embeddings)} embeddings")
                
                # Calcular similitudes
                sim1_2 = cosine_similarity(embeddings[0], embeddings[1])
                sim1_3 = cosine_similarity(embeddings[0], embeddings[2])
                
                print(f"Similitud texto 1-2: {sim1_2:.4f}")
                print(f"Similitud texto 1-3: {sim1_3:.4f}")
                
            except Exception as e:
                print(f"❌ Error en prueba de lotes: {e}")
        else:
            print("❌ Test de embedding falló")
    else:
        print("❌ Ollama no está disponible")

