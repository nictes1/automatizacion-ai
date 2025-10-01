#!/usr/bin/env python3
"""
Configuración central del sistema PulpoAI
Centraliza todas las variables de entorno y configuraciones
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Cargar variables de entorno
load_dotenv()

class Config:
    """Configuración central del sistema"""
    
    # Base de datos
    DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://pulpo:pulpo@localhost:5432/pulpo')
    
    # Redis
    REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379')
    
    # Ollama
    OLLAMA_URL = os.getenv('OLLAMA_URL', 'http://localhost:11434')
    OLLAMA_MODEL = os.getenv('OLLAMA_MODEL', 'llama3.1:8b')
    EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
    EMBEDDING_DIMS = int(os.getenv('EMBEDDING_DIMS', '768'))
    
    # N8N
    N8N_BASE_URL = os.getenv('N8N_BASE_URL', 'http://localhost:5678')
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
    TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
    TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')
    
    # Tika
    TIKA_URL = os.getenv('TIKA_URL', 'http://localhost:9998')
    
    # Weaviate
    WEAVIATE_URL = os.getenv('WEAVIATE_URL', 'http://localhost:8080')
    
    # Directorios
    UPLOAD_DIR = Path(os.getenv('UPLOAD_DIR', 'uploads/documents'))
    LOGS_DIR = Path(os.getenv('LOGS_DIR', 'logs'))
    
    # Configuración de logging
    LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
    
    # Configuración de archivos
    MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', '10485760'))  # 10MB
    ALLOWED_EXTENSIONS = os.getenv('ALLOWED_EXTENSIONS', 'pdf,txt,docx,html,json,csv').split(',')
    
    # Configuración de RAG
    CHUNK_SIZE = int(os.getenv('CHUNK_SIZE', '800'))
    CHUNK_OVERLAP = int(os.getenv('CHUNK_OVERLAP', '120'))
    TOP_K_RESULTS = int(os.getenv('TOP_K_RESULTS', '5'))
    
    # Configuración de debounce
    DEBOUNCE_TIMEOUT = int(os.getenv('DEBOUNCE_TIMEOUT', '10'))  # segundos
    
    # Configuración de API
    API_HOST = os.getenv('API_HOST', '0.0.0.0')
    API_PORT = int(os.getenv('API_PORT', '8002'))
    
    @classmethod
    def create_directories(cls):
        """Crea los directorios necesarios"""
        cls.UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        cls.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    
    @classmethod
    def validate_config(cls):
        """Valida la configuración requerida"""
        required_vars = [
            'DATABASE_URL',
            'OLLAMA_URL',
            'N8N_BASE_URL'
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            raise ValueError(f"Variables de entorno faltantes: {', '.join(missing_vars)}")
        
        return True

# Configuración por vertical
VERTICAL_CONFIGS = {
    "gastronomia": {
        "document_types": {
            "menu": {
                "extraction_prompt": "Extrae información del menú gastronómico incluyendo platos, precios, categorías y descripciones",
                "chunking_strategy": "semantic",
                "search_fields": ["name", "price", "category", "description"]
            },
            "policy": {
                "extraction_prompt": "Extrae políticas del restaurante como horarios, métodos de pago, delivery, etc.",
                "chunking_strategy": "paragraph",
                "search_fields": ["policy_type", "content", "conditions"]
            },
            "promotion": {
                "extraction_prompt": "Extrae promociones, ofertas y descuentos del restaurante",
                "chunking_strategy": "semantic",
                "search_fields": ["title", "description", "discount", "valid_until"]
            }
        }
    },
    "inmobiliaria": {
        "document_types": {
            "properties": {
                "extraction_prompt": "Extrae información de propiedades inmobiliarias incluyendo ubicación, precio, características y amenities",
                "chunking_strategy": "property",
                "search_fields": ["address", "price", "type", "features", "city", "neighborhood"]
            },
            "policy": {
                "extraction_prompt": "Extrae políticas inmobiliarias como comisiones, términos de venta, etc.",
                "chunking_strategy": "paragraph",
                "search_fields": ["policy_type", "content", "conditions"]
            },
            "catalog": {
                "extraction_prompt": "Extrae catálogo de propiedades disponibles para venta o alquiler",
                "chunking_strategy": "semantic",
                "search_fields": ["property_id", "type", "location", "price", "features"]
            }
        }
    },
    "servicios": {
        "document_types": {
            "services": {
                "extraction_prompt": "Extrae información de servicios ofrecidos incluyendo descripción, precios y disponibilidad",
                "chunking_strategy": "semantic",
                "search_fields": ["service_name", "description", "price", "duration", "category"]
            },
            "schedule": {
                "extraction_prompt": "Extrae horarios de atención y disponibilidad de servicios",
                "chunking_strategy": "paragraph",
                "search_fields": ["day", "time", "service", "availability"]
            },
            "policy": {
                "extraction_prompt": "Extrae políticas de servicios como cancelaciones, pagos, etc.",
                "chunking_strategy": "paragraph",
                "search_fields": ["policy_type", "content", "conditions"]
            }
        }
    }
}

# Inicializar configuración
Config.create_directories()