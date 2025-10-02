# 📦 PulpoAI Shared Libraries

## 📋 **Descripción**

Librerías compartidas para todos los microservicios de PulpoAI. Estas librerías proporcionan funcionalidades comunes como base de datos, autenticación, monitoreo y utilidades.

## 🏗️ **Estructura**

```
shared/
├── database/              # Cliente de base de datos
│   ├── __init__.py
│   ├── client.py         # Cliente principal
│   ├── models.py         # Modelos de datos
│   └── exceptions.py     # Excepciones de BD
├── auth/                 # Autenticación y autorización
│   ├── __init__.py
│   ├── client.py         # Cliente de auth
│   ├── jwt_handler.py    # Manejo de JWT
│   ├── middleware.py     # Middleware FastAPI
│   └── exceptions.py     # Excepciones de auth
├── monitoring/           # Monitoreo y métricas
│   ├── __init__.py
│   ├── client.py         # Cliente de monitoreo
│   ├── metrics.py        # Recolector de métricas
│   ├── logger.py         # Logger estructurado
│   └── exceptions.py     # Excepciones de monitoreo
├── utils/               # Utilidades comunes
│   ├── __init__.py
│   ├── helpers.py        # Funciones helper
│   ├── validators.py     # Validadores
│   ├── formatters.py     # Formateadores
│   └── exceptions.py     # Excepciones de utils
├── requirements.txt      # Dependencias
└── README.md            # Este archivo
```

## 🚀 **Uso en Microservicios**

### **1. Database Client**
```python
from shared.database import DatabaseClient, Workspace, Conversation

# Inicializar cliente
db = DatabaseClient()

# Configurar contexto de workspace
await db.set_workspace_context("workspace-id")

# Ejecutar consulta
results = await db.execute_query("SELECT * FROM pulpo.workspaces")

# Usar modelos
workspace = Workspace(
    id="workspace-123",
    name="Mi Workspace",
    plan_tier="agent_pro",
    vertical="gastronomia"
)
```

### **2. Auth Client**
```python
from shared.auth import AuthClient, get_current_user

# Inicializar cliente
auth = AuthClient()

# Autenticar usuario
user_data = auth.authenticate_user("admin@pulpo.ai", "admin123")

# Crear tokens
tokens = auth.create_user_tokens(user_data)

# Validar token
user_context = auth.validate_token(token)

# En FastAPI
@app.get("/protected")
async def protected_route(user: dict = Depends(get_current_user)):
    return {"user": user}
```

### **3. Monitoring Client**
```python
from shared.monitoring import MonitoringClient

# Inicializar cliente
monitoring = MonitoringClient("my-service")

# Registrar métricas
monitoring.record_request("GET", "/health", 200, 0.1)
monitoring.record_conversation("workspace-123", "gastronomia")
monitoring.record_error("database_error", "Connection failed")

# Logging estructurado
monitoring.logger.info("Service started", service="my-service")
monitoring.logger.log_request("GET", "/api", 200, 0.05)
```

### **4. Utils**
```python
from shared.utils import (
    generate_uuid, validate_email, format_currency,
    validate_workspace_id, format_phone_number
)

# Generar UUID
id = generate_uuid()

# Validar datos
is_valid = validate_email("user@example.com")
is_valid = validate_workspace_id("workspace-123")

# Formatear datos
phone = format_phone_number("+5491111111111")
currency = format_currency(123.45, "ARS", "$")
```

## 🔧 **Configuración**

### **Variables de Entorno**
```bash
# Database
DB_HOST=postgres
DB_PORT=5432
DB_NAME=pulpo
DB_USER=pulpo
DB_PASSWORD=pulpo

# Redis
REDIS_URL=redis://redis:6379

# JWT
JWT_SECRET=your-secret-key-here
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# Monitoring
LOG_LEVEL=INFO
METRICS_PORT=8000
```

### **Instalación en Microservicio**
```bash
# En el microservicio
pip install -r ../shared/requirements.txt

# O agregar al requirements.txt del microservicio
-e ../shared
```

## 📊 **Métricas Disponibles**

### **Request Metrics**
- `{service}_requests_total` - Total de requests
- `{service}_request_duration_seconds` - Duración de requests

### **Database Metrics**
- `{service}_db_queries_total` - Total de consultas
- `{service}_db_query_duration_seconds` - Duración de consultas

### **Business Metrics**
- `{service}_conversations_total` - Total de conversaciones
- `{service}_messages_total` - Total de mensajes
- `{service}_actions_executed_total` - Total de acciones

### **RAG Metrics**
- `{service}_rag_searches_total` - Total de búsquedas RAG
- `{service}_documents_ingested_total` - Total de documentos
- `{service}_embeddings_generated_total` - Total de embeddings

## 🧪 **Testing**

### **Test de Database Client**
```python
import pytest
from shared.database import DatabaseClient

@pytest.mark.asyncio
async def test_database_client():
    db = DatabaseClient()
    await db.initialize()
    
    # Test connection
    result = await db.execute_one("SELECT 1 as test")
    assert result["test"] == 1
    
    await db.close()
```

### **Test de Auth Client**
```python
import pytest
from shared.auth import AuthClient

def test_auth_client():
    auth = AuthClient()
    
    # Test authentication
    user_data = auth.authenticate_user("admin@pulpo.ai", "admin123")
    assert user_data["email"] == "admin@pulpo.ai"
    
    # Test token creation
    tokens = auth.create_user_tokens(user_data)
    assert "access_token" in tokens
```

### **Test de Utils**
```python
import pytest
from shared.utils import validate_email, format_currency

def test_utils():
    # Test validation
    assert validate_email("user@example.com") == True
    assert validate_email("invalid-email") == False
    
    # Test formatting
    assert format_currency(123.45) == "$ 123.45"
```

## 🔄 **Integración con Microservicios**

### **En FastAPI App**
```python
from fastapi import FastAPI, Depends
from shared.database import DatabaseClient
from shared.auth import get_current_user
from shared.monitoring import MonitoringClient

app = FastAPI()
monitoring = MonitoringClient("my-service")

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/protected")
async def protected_route(user: dict = Depends(get_current_user)):
    monitoring.record_request("GET", "/protected", 200, 0.1)
    return {"user": user}
```

### **En Dockerfile**
```dockerfile
# Copiar librerías compartidas
COPY ../shared /app/shared

# Instalar dependencias
RUN pip install -r /app/shared/requirements.txt

# Agregar al PYTHONPATH
ENV PYTHONPATH=/app:/app/shared
```

## 🚨 **Troubleshooting**

### **Problemas Comunes**

1. **Error de importación**
   ```python
   # Verificar PYTHONPATH
   import sys
   sys.path.append('/path/to/shared')
   ```

2. **Error de conexión a base de datos**
   ```python
   # Verificar configuración
   from shared.database import DatabaseClient
   db = DatabaseClient()
   await db.initialize()
   ```

3. **Error de autenticación**
   ```python
   # Verificar JWT secret
   from shared.auth import AuthClient
   auth = AuthClient()
   ```

## 📚 **Documentación Adicional**

- [Database Client](./database/README.md)
- [Auth Client](./auth/README.md)
- [Monitoring Client](./monitoring/README.md)
- [Utils](./utils/README.md)
