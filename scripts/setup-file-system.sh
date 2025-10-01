#!/bin/bash

# =====================================================
# Script de Configuración del Sistema de Archivos RAG
# =====================================================

set -e

echo "🚀 Configurando sistema de gestión de archivos RAG..."

# Colores para output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Función para imprimir mensajes
print_status() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Verificar que estamos en el directorio correcto
if [ ! -f "file_processor.py" ]; then
    print_error "Este script debe ejecutarse desde el directorio raíz del proyecto"
    exit 1
fi

# 1. Crear directorios necesarios
print_status "Creando directorios de trabajo..."
mkdir -p uploads/raw
mkdir -p uploads/processed
mkdir -p uploads/chunks
mkdir -p uploads/embeddings
mkdir -p logs
print_success "Directorios creados"

# 2. Verificar variables de entorno
print_status "Verificando variables de entorno..."
if [ -z "$DATABASE_URL" ]; then
    print_warning "DATABASE_URL no está configurada"
    print_status "Configurando DATABASE_URL por defecto..."
    export DATABASE_URL="postgresql://pulpo_user:pulpo_password@localhost:5432/pulpo_db"
fi

if [ -z "$OPENAI_API_KEY" ]; then
    print_warning "OPENAI_API_KEY no está configurada"
    print_status "Por favor configura tu API key de OpenAI:"
    echo "export OPENAI_API_KEY='tu-api-key-aqui'"
fi

# 3. Instalar dependencias de Python
print_status "Instalando dependencias de Python..."
if [ -f "requirements-files.txt" ]; then
    pip install -r requirements-files.txt
    print_success "Dependencias instaladas"
else
    print_error "Archivo requirements-files.txt no encontrado"
    exit 1
fi

# 4. Aplicar migraciones de base de datos
print_status "Aplicando migraciones de base de datos..."
if [ -f "sql/11_file_management_up.sql" ]; then
    # Verificar si PostgreSQL está corriendo
    if ! pg_isready -h localhost -p 5432 > /dev/null 2>&1; then
        print_warning "PostgreSQL no está corriendo. Iniciando con Docker..."
        if command -v docker &> /dev/null; then
            docker-compose up -d postgres
            sleep 10
        else
            print_error "Docker no está instalado. Por favor inicia PostgreSQL manualmente"
            exit 1
        fi
    fi
    
    # Aplicar migración
    psql "$DATABASE_URL" -f sql/11_file_management_up.sql
    print_success "Migraciones aplicadas"
else
    print_error "Archivo de migración sql/11_file_management_up.sql no encontrado"
    exit 1
fi

# 5. Verificar extensión vector en PostgreSQL
print_status "Verificando extensión vector en PostgreSQL..."
psql "$DATABASE_URL" -c "CREATE EXTENSION IF NOT EXISTS vector;" || {
    print_warning "No se pudo crear la extensión vector. Instalando pgvector..."
    print_status "Para instalar pgvector, ejecuta:"
    echo "git clone https://github.com/pgvector/pgvector.git"
    echo "cd pgvector"
    echo "make"
    echo "sudo make install"
    echo "psql $DATABASE_URL -c 'CREATE EXTENSION vector;'"
}

# 6. Crear archivo de configuración
print_status "Creando archivo de configuración..."
cat > .env.files << EOF
# Configuración del Sistema de Archivos RAG
DATABASE_URL=$DATABASE_URL
OPENAI_API_KEY=$OPENAI_API_KEY

# Configuración de archivos
UPLOAD_DIR=uploads
MAX_FILE_SIZE=52428800  # 50MB
CHUNK_SIZE=1000
CHUNK_OVERLAP=200

# Configuración de embeddings
EMBEDDING_MODEL=text-embedding-ada-002
EMBEDDING_DIMENSIONS=1536

# Configuración de API
API_HOST=0.0.0.0
API_PORT=8001
API_WORKERS=4

# Logging
LOG_LEVEL=INFO
LOG_FILE=logs/file_system.log
EOF
print_success "Archivo de configuración creado"

# 7. Crear script de inicio
print_status "Creando script de inicio..."
cat > start-file-api.sh << 'EOF'
#!/bin/bash

# Cargar variables de entorno
if [ -f ".env.files" ]; then
    export $(cat .env.files | grep -v '^#' | xargs)
fi

# Verificar que las dependencias estén instaladas
if ! python3 -c "import fastapi, uvicorn" 2>/dev/null; then
    echo "Instalando dependencias..."
    pip install -r requirements-files.txt
fi

# Iniciar la API
echo "🚀 Iniciando API de gestión de archivos..."
python3 file_api.py
EOF

chmod +x start-file-api.sh
print_success "Script de inicio creado"

# 8. Crear script de prueba
print_status "Creando script de prueba..."
cat > test-file-system.py << 'EOF'
#!/usr/bin/env python3
"""
Script de prueba para el sistema de archivos
"""

import os
import requests
import json
from pathlib import Path

# Configuración
API_BASE_URL = "http://localhost:8001"
WORKSPACE_ID = "00000000-0000-0000-0000-000000000001"  # Workspace de prueba

def test_api():
    """Prueba básica de la API"""
    print("🧪 Probando API de gestión de archivos...")
    
    # 1. Health check
    try:
        response = requests.get(f"{API_BASE_URL}/health")
        if response.status_code == 200:
            print("✅ Health check OK")
        else:
            print("❌ Health check falló")
            return False
    except Exception as e:
        print(f"❌ Error en health check: {e}")
        return False
    
    # 2. Obtener tipos soportados
    try:
        response = requests.get(f"{API_BASE_URL}/supported-types")
        if response.status_code == 200:
            types = response.json()
            print(f"✅ Tipos soportados: {len(types['supported_extensions'])} extensiones")
        else:
            print("❌ Error obteniendo tipos soportados")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # 3. Listar archivos
    try:
        response = requests.get(f"{API_BASE_URL}/files?workspace_id={WORKSPACE_ID}")
        if response.status_code == 200:
            files = response.json()
            print(f"✅ Archivos encontrados: {len(files)}")
        else:
            print("❌ Error listando archivos")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    # 4. Obtener estadísticas
    try:
        response = requests.get(f"{API_BASE_URL}/files/stats?workspace_id={WORKSPACE_ID}")
        if response.status_code == 200:
            stats = response.json()
            print(f"✅ Estadísticas: {stats['total_files']} archivos, {stats['total_size']} bytes")
        else:
            print("❌ Error obteniendo estadísticas")
    except Exception as e:
        print(f"❌ Error: {e}")
    
    print("🎉 Pruebas completadas")
    return True

if __name__ == "__main__":
    test_api()
EOF

chmod +x test-file-system.py
print_success "Script de prueba creado"

# 9. Crear documentación de uso
print_status "Creando documentación de uso..."
cat > docs/FILE_SYSTEM_USAGE.md << 'EOF'
# 📁 Guía de Uso del Sistema de Archivos RAG

## 🚀 Inicio Rápido

### 1. Iniciar la API
```bash
./start-file-api.sh
```

### 2. Probar el sistema
```bash
python3 test-file-system.py
```

## 📋 Endpoints Disponibles

### Subir Archivo
```bash
curl -X POST "http://localhost:8001/files/upload?workspace_id=YOUR_WORKSPACE_ID" \
     -H "Content-Type: multipart/form-data" \
     -F "file=@documento.pdf"
```

### Listar Archivos
```bash
curl "http://localhost:8001/files?workspace_id=YOUR_WORKSPACE_ID"
```

### Obtener Estadísticas
```bash
curl "http://localhost:8001/files/stats?workspace_id=YOUR_WORKSPACE_ID"
```

### Buscar Archivos
```bash
curl "http://localhost:8001/search?workspace_id=YOUR_WORKSPACE_ID&query=busqueda"
```

### Descargar Archivo
```bash
curl "http://localhost:8001/files/FILE_ID/download?workspace_id=YOUR_WORKSPACE_ID" \
     -o archivo_descargado.pdf
```

### Eliminar Archivo
```bash
curl -X DELETE "http://localhost:8001/files/FILE_ID?workspace_id=YOUR_WORKSPACE_ID"
```

## 🔧 Configuración

### Variables de Entorno
- `DATABASE_URL`: URL de conexión a PostgreSQL
- `OPENAI_API_KEY`: API key de OpenAI para embeddings
- `MAX_FILE_SIZE`: Tamaño máximo de archivo (default: 50MB)
- `CHUNK_SIZE`: Tamaño de chunks para embeddings (default: 1000 tokens)

### Tipos de Archivos Soportados
- Documentos: PDF, DOCX, XLSX, PPTX
- Texto: TXT, MD, RTF
- Web: HTML, XML, JSON
- Código: PY, JS, TS, JAVA, CPP, C, SQL
- Configuración: YAML, INI, CFG, CONF, ENV

## 🗄️ Base de Datos

### Tablas Principales
- `pulpo.files`: Metadatos de archivos
- `pulpo.file_chunks`: Chunks de texto
- `pulpo.file_embeddings`: Vectores de embeddings

### Índices Vectoriales
- Búsqueda semántica con pgvector
- Índice IVFFlat para búsqueda rápida

## 🔍 Búsqueda RAG

El sistema genera embeddings automáticamente y permite:
- Búsqueda semántica por contenido
- Búsqueda por texto exacto
- Filtrado por tipo de archivo
- Ranking por relevancia

## 🛠️ Mantenimiento

### Limpiar Archivos Eliminados
```sql
SELECT pulpo.cleanup_deleted_files();
```

### Obtener Estadísticas
```sql
SELECT * FROM pulpo.get_file_stats('workspace-id');
```

### Reindexar Embeddings
```python
# Regenerar embeddings para un archivo
processor = FileProcessor(db_url, openai_key)
file_metadata = processor.process_file("archivo.pdf", "workspace-id")
```
EOF

print_success "Documentación creada"

# 10. Resumen final
print_status "Configuración completada!"
echo ""
print_success "✅ Directorios creados"
print_success "✅ Dependencias instaladas"
print_success "✅ Migraciones aplicadas"
print_success "✅ Scripts de inicio creados"
print_success "✅ Documentación generada"
echo ""
print_status "Próximos pasos:"
echo "1. Configura tu OPENAI_API_KEY en .env.files"
echo "2. Ejecuta: ./start-file-api.sh"
echo "3. Prueba el sistema: python3 test-file-system.py"
echo ""
print_status "La API estará disponible en: http://localhost:8001"
print_status "Documentación disponible en: docs/FILE_SYSTEM_USAGE.md"
echo ""
print_success "🎉 Sistema de archivos RAG configurado exitosamente!"


