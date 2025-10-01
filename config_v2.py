"""
Configuración para PulpoAI v2 - Arquitectura de Servicios
"""

import os
from typing import Dict, Any, Optional
from dotenv import load_dotenv

load_dotenv()

class Config:
    """Configuración centralizada para todos los servicios"""
    
    # Base de datos
    DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@localhost:5432/pulpo")
    
    # Redis
    REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
    REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
    REDIS_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}"
    
    # Ollama
    OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
    OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b")
    
    # N8N
    N8N_BASE_URL = os.getenv("N8N_BASE_URL", "http://localhost:5678")
    
    # Twilio
    TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER", "whatsapp:+14155238886")
    
    # Servicios
    SERVICES = {
        "rag": {
            "host": "0.0.0.0",
            "port": 8003,
            "url": "http://localhost:8003"
        },
        "actions": {
            "host": "0.0.0.0", 
            "port": 8004,
            "url": "http://localhost:8004"
        },
        "orchestrator": {
            "host": "0.0.0.0",
            "port": 8005,
            "url": "http://localhost:8005"
        },
        "message_router": {
            "host": "0.0.0.0",
            "port": 8006,
            "url": "http://localhost:8006"
        },
        "ingestion": {
            "host": "0.0.0.0",
            "port": 8007,
            "url": "http://localhost:8007"
        }
    }
    
    # Almacenamiento
    UPLOAD_DIR = os.getenv("UPLOAD_DIR", "uploads")
    
    # RAG Configuration
    RAG_CONFIG = {
        "chunk_size": 1000,
        "chunk_overlap": 200,
        "embedding_model": "text-embedding-3-large",
        "vector_dimensions": 1024,
        "similarity_threshold": 0.7,
        "max_results": 20,
        "hybrid_search": {
            "k": 60,
            "top_n_bm25": 50,
            "top_n_vector": 50
        }
    }
    
    # Orchestrator Configuration
    ORCHESTRATOR_CONFIG = {
        "max_attempts": 3,
        "debounce_window_ms": 700,
        "timeout_seconds": 30,
        "policies": {
            "gastronomia": {
                "required_slots": ["categoria", "items", "metodo_entrega"],
                "optional_slots": ["extras", "direccion", "metodo_pago", "notas"],
                "max_attempts": 3
            },
            "inmobiliaria": {
                "required_slots": ["operation", "type", "zone"],
                "optional_slots": ["price_range", "bedrooms", "bathrooms"],
                "max_attempts": 3
            },
            "servicios": {
                "required_slots": ["service_type", "preferred_date"],
                "optional_slots": ["preferred_time", "staff_preference", "notes"],
                "max_attempts": 3
            }
        }
    }
    
    # Message Router Configuration
    MESSAGE_ROUTER_CONFIG = {
        "deduplication_ttl": 3600,  # 1 hora
        "debounce_window_ms": 700,
        "max_messages_in_buffer": 5,
        "buffer_ttl": 10  # 10 segundos
    }
    
    # Actions Configuration
    ACTIONS_CONFIG = {
        "idempotency_ttl": 86400,  # 24 horas
        "timeout_seconds": 30,
        "retry_attempts": 3,
        "actions": {
            "crear_pedido": {
                "timeout": 30,
                "retry_attempts": 3
            },
            "schedule_visit": {
                "timeout": 30,
                "retry_attempts": 3
            },
            "book_slot": {
                "timeout": 30,
                "retry_attempts": 3
            }
        }
    }
    
    # Ingestion Configuration
    INGESTION_CONFIG = {
        "supported_formats": [
            "pdf", "docx", "txt", "html", "json", "csv", "xlsx",
            "png", "jpg", "jpeg", "gif", "bmp"
        ],
        "max_file_size_mb": 50,
        "processing_timeout": 300,  # 5 minutos
        "chunking": {
            "default_chunk_size": 1000,
            "default_overlap": 200,
            "menu_chunking": "by_category",
            "text_chunking": "by_tokens"
        }
    }
    
    # Logging Configuration
    LOGGING_CONFIG = {
        "level": "INFO",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/pulpo_v2.log",
        "max_size_mb": 100,
        "backup_count": 5
    }
    
    # Monitoring Configuration
    MONITORING_CONFIG = {
        "enabled": True,
        "metrics_port": 9090,
        "health_check_interval": 30,
        "alerts": {
            "enabled": True,
            "webhook_url": None,
            "thresholds": {
                "response_time_ms": 5000,
                "error_rate_percent": 5,
                "memory_usage_percent": 80
            }
        }
    }
    
    @classmethod
    def get_service_url(cls, service_name: str) -> str:
        """Obtiene la URL de un servicio"""
        return cls.SERVICES.get(service_name, {}).get("url", "")
    
    @classmethod
    def get_service_config(cls, service_name: str) -> Dict[str, Any]:
        """Obtiene la configuración de un servicio"""
        return cls.SERVICES.get(service_name, {})
    
    @classmethod
    def validate_config(cls) -> bool:
        """Valida la configuración"""
        required_vars = [
            "DATABASE_URL",
            "OLLAMA_URL"
        ]
        
        missing_vars = []
        for var in required_vars:
            if not getattr(cls, var):
                missing_vars.append(var)
        
        if missing_vars:
            print(f"❌ Variables de entorno faltantes: {', '.join(missing_vars)}")
            return False
        
        return True
    
    @classmethod
    def print_config(cls):
        """Imprime la configuración actual"""
        print("🐙 PulpoAI v2 - Configuración")
        print("=" * 40)
        print(f"Base de datos: {cls.DATABASE_URL}")
        print(f"Redis: {cls.REDIS_URL}")
        print(f"Ollama: {cls.OLLAMA_URL}")
        print(f"N8N: {cls.N8N_BASE_URL}")
        print(f"Twilio: {'✅ Configurado' if cls.TWILIO_ACCOUNT_SID else '❌ No configurado'}")
        print("\nServicios:")
        for name, config in cls.SERVICES.items():
            print(f"  {name}: {config['url']}")
        print(f"\nUpload dir: {cls.UPLOAD_DIR}")
        print(f"Logging: {cls.LOGGING_CONFIG['level']}")

# Configuración de desarrollo
class DevelopmentConfig(Config):
    """Configuración para desarrollo"""
    
    LOGGING_CONFIG = {
        "level": "DEBUG",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/pulpo_v2_dev.log",
        "max_size_mb": 50,
        "backup_count": 3
    }
    
    MONITORING_CONFIG = {
        "enabled": False,
        "metrics_port": 9090,
        "health_check_interval": 10,
        "alerts": {
            "enabled": False
        }
    }

# Configuración de producción
class ProductionConfig(Config):
    """Configuración para producción"""
    
    LOGGING_CONFIG = {
        "level": "WARNING",
        "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        "file": "logs/pulpo_v2_prod.log",
        "max_size_mb": 200,
        "backup_count": 10
    }
    
    MONITORING_CONFIG = {
        "enabled": True,
        "metrics_port": 9090,
        "health_check_interval": 60,
        "alerts": {
            "enabled": True,
            "webhook_url": os.getenv("ALERT_WEBHOOK_URL"),
            "thresholds": {
                "response_time_ms": 3000,
                "error_rate_percent": 2,
                "memory_usage_percent": 70
            }
        }
    }

# Seleccionar configuración según entorno
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

if ENVIRONMENT == "production":
    config = ProductionConfig()
elif ENVIRONMENT == "development":
    config = DevelopmentConfig()
else:
    config = Config()

# Validar configuración al importar
if not config.validate_config():
    print("⚠️  Configuración inválida. Algunos servicios pueden no funcionar correctamente.")

# Exportar configuración
__all__ = ["config", "Config", "DevelopmentConfig", "ProductionConfig"]



