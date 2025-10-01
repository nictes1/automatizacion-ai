# 🚀 Sistema de Gestión de Archivos RAG Mejorado

## 📋 Resumen

Hemos implementado un sistema de gestión de archivos para RAG basado en la propuesta de ChatGPT, adaptado a nuestro stack tecnológico. Este sistema es más robusto, escalable y profesional que la implementación anterior.

## 🏗️ Arquitectura

### Componentes Principales

1. **Apache Tika Server**: Extracción de texto de múltiples formatos
2. **Ollama**: Generación de embeddings locales
3. **PostgreSQL + pgvector**: Almacenamiento vectorial
4. **Servicio de Ingesta**: Orquestación del procesamiento
5. **RLS (Row Level Security)**: Multi-tenancy seguro

### Flujo de Procesamiento

```mermaid
graph TD
    A[Archivo Subido] --> B[Verificar Tipo]
    B --> C[Calcular SHA256]
    C --> D[Deduplicación]
    D --> E[Tika Server]
    E --> F[Extracción de Texto]
    F --> G[Normalización]
    G --> H[Chunking]
    H --> I[Ollama Embeddings]
    I --> J[Almacenamiento Vectorial]
    J --> K[Actualizar Estado]
```

## 📁 Estructura de Archivos

```
pulpo/
├── sql/
│   └── 11_file_management_improved.sql    # Esquema mejorado
├── file_ingestor.py                       # Servicio principal
├── file_processor_improved.py             # Procesador de archivos
├── tika_client.py                         # Cliente Tika
├── ollama_embeddings.py                   # Cliente Ollama
├── docker-compose.tika.yml                # Docker Compose
├── Dockerfile.file-ingestor               # Dockerfile del servicio
├── requirements-file-ingestor.txt         # Dependencias
└── scripts/
    └── test-file-ingestor.py              # Script de pruebas
```

## 🗄️ Esquema de Base de Datos

### Tablas Principales

1. **`pulpo.files`**: Metadatos de archivos crudos
2. **`pulpo.documents`**: Documentos extraídos
3. **`pulpo.doc_chunks`**: Chunks de texto
4. **`pulpo.doc_chunk_embeddings`**: Vectores de embeddings

### Características del Esquema

- **Multi-tenancy**: RLS por workspace
- **Deduplicación**: SHA256 único por workspace
- **Índices vectoriales**: Búsqueda semántica eficiente
- **Metadatos ricos**: Información detallada de procesamiento

## 🚀 Instalación y Configuración

### 1. Aplicar Migraciones

```bash
# Aplicar el nuevo esquema
psql $DATABASE_URL -f sql/11_file_management_improved.sql
```

### 2. Iniciar Servicios

```bash
# Iniciar Tika Server
docker-compose -f docker-compose.tika.yml up -d

# Iniciar Ollama (si no está corriendo)
docker-compose up -d ollama

# Instalar dependencias
pip install -r requirements-file-ingestor.txt

# Iniciar servicio de ingesta
python file_ingestor.py
```

### 3. Verificar Instalación

```bash
# Ejecutar pruebas
python scripts/test-file-ingestor.py
```

## 📋 API Endpoints

### Health Check
```bash
GET /health
```

### Ingesta de Archivos
```bash
POST /ingest
{
  "workspace_id": "uuid",
  "file_path": "/path/to/file.pdf",
  "title": "Título del documento",
  "language": "es"
}
```

### Ingesta Asíncrona
```bash
POST /ingest/async
{
  "workspace_id": "uuid",
  "file_path": "/path/to/file.pdf"
}
```

### Estadísticas
```bash
GET /files/{workspace_id}/stats
```

### Listar Archivos
```bash
GET /files/{workspace_id}?limit=50&offset=0
```

### Eliminar Archivo
```bash
DELETE /files/{workspace_id}/{file_id}
```

## 🔧 Configuración

### Variables de Entorno

```bash
# Base de datos
DATABASE_URL=postgresql://user:pass@host:5432/db

# Servicios
TIKA_URL=http://localhost:9998
OLLAMA_URL=http://localhost:11434

# Embeddings
EMBEDDING_MODEL=nomic-embed-text
EMBEDDING_DIMS=768

# Servidor
SERVER_ADDR=:8080
READ_LOCAL_FILES=true
```

### Tipos de Archivos Soportados

- **Documentos**: PDF, DOCX, XLSX, PPTX, ODT, ODS, ODP
- **Texto**: TXT, MD, RTF, CSV
- **Web**: HTML, XML, JSON
- **Código**: PY, JS, TS, JAVA, CPP, C, SQL, YAML, SH, BAT
- **Configuración**: INI, CFG, CONF, ENV, PROPERTIES
- **Imágenes**: PNG, JPG, JPEG, TIFF, BMP (con OCR)

## 🔍 Búsqueda RAG

### Búsqueda Semántica

```sql
-- Búsqueda por similitud coseno
SELECT * FROM pulpo.semantic_search(
    'workspace-id',
    '[0.1, 0.2, ...]'::vector,  -- embedding de la consulta
    10,                          -- límite de resultados
    0.7                          -- umbral de similitud
);
```

### Búsqueda de Texto

```sql
-- Búsqueda por contenido
SELECT * FROM pulpo.search_files_by_content(
    'workspace-id',
    'consulta de búsqueda',
    10
);
```

## 🎯 Ventajas del Sistema Mejorado

### vs. Implementación Anterior

| Aspecto | Anterior | Mejorado |
|---------|----------|----------|
| **Extracción** | Librerías Python | Apache Tika Server |
| **Storage** | Sistema de archivos | S3/MinIO + metadatos |
| **Multi-tenancy** | RLS básico | RLS avanzado con contexto |
| **Escalabilidad** | Limitada | Alta (microservicio) |
| **OCR** | No incluido | Tika con OCR |
| **Deduplicación** | Hash básico | SHA256 + constraints |
| **Búsqueda** | Texto simple | Semántica + texto |

### Características Clave

1. **Robustez**: Tika Server maneja más formatos y casos edge
2. **Escalabilidad**: Arquitectura de microservicios
3. **Seguridad**: RLS estricto por workspace
4. **Eficiencia**: Deduplicación automática
5. **Flexibilidad**: Configuración por tipo de archivo
6. **Observabilidad**: Logs detallados y métricas

## 🔄 Integración con n8n

### Webhook de Ingesta

```json
{
  "webhook": {
    "url": "http://file-ingestor:8080/ingest",
    "method": "POST",
    "body": {
      "workspace_id": "{{ $json.workspace_id }}",
      "file_path": "{{ $json.file_path }}",
      "title": "{{ $json.title }}"
    }
  }
}
```

### Webhook de Búsqueda

```json
{
  "webhook": {
    "url": "http://file-ingestor:8080/search",
    "method": "POST",
    "body": {
      "workspace_id": "{{ $json.workspace_id }}",
      "query": "{{ $json.query }}",
      "limit": 10
    }
  }
}
```

## 🧪 Pruebas

### Ejecutar Suite Completa

```bash
python scripts/test-file-ingestor.py
```

### Pruebas Individuales

```bash
# Health checks
curl http://localhost:8080/health

# Tipos soportados
curl http://localhost:8080/supported-types

# Ingesta de archivo
curl -X POST http://localhost:8080/ingest \
  -H "Content-Type: application/json" \
  -d '{
    "workspace_id": "00000000-0000-0000-0000-000000000001",
    "file_path": "/path/to/file.pdf",
    "title": "Documento de prueba"
  }'
```

## 📊 Monitoreo

### Logs

```bash
# Logs del servicio
tail -f logs/file_ingestor.log

# Logs de Tika
docker logs pulpo-tika

# Logs de Ollama
docker logs ollama
```

### Métricas

- Tiempo de procesamiento por archivo
- Número de chunks generados
- Tasa de éxito/fallo
- Uso de memoria y CPU

## 🚨 Troubleshooting

### Problemas Comunes

1. **Tika no responde**
   ```bash
   docker restart pulpo-tika
   ```

2. **Ollama no tiene el modelo**
   ```bash
   docker exec ollama ollama pull nomic-embed-text
   ```

3. **Error de permisos en archivos**
   ```bash
   chmod 755 uploads/
   ```

4. **Base de datos no conecta**
   ```bash
   # Verificar variables de entorno
   echo $DATABASE_URL
   ```

## 🔮 Próximos Pasos

1. **Integración con S3/MinIO** para storage en producción
2. **Interfaz web** para gestión de archivos
3. **Búsqueda avanzada** con filtros y ranking
4. **Métricas y dashboards** de monitoreo
5. **Integración completa** con workflow n8n

---

**Fecha**: Enero 2025  
**Versión**: 2.0  
**Estado**: ✅ Implementado  
**Próximo**: Integración con n8n y pruebas en producción


