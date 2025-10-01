# 📚 Documentación Completa del Código - PulpoAI

## 🎯 **Propósito de esta Documentación**

Esta documentación explica **cada archivo** del sistema PulpoAI, su propósito, funcionalidad y cómo se relaciona con el resto del sistema. Incluye correcciones de errores y mejoras de documentación.

---

## 🗄️ **ARCHIVOS SQL - Base de Datos**

### **📁 Estructura y Orden de Ejecución:**

Los archivos SQL deben ejecutarse en este orden específico:

```
00_all_up.sql → 01_core_up.sql → 02_seed_dev.sql → 03_functions.sql → ... → 13_workflow_functions.sql
```

---

### **1. `00_all_up.sql` - Script Maestro**
**Propósito**: Script principal que ejecuta todos los demás archivos SQL en orden
**Funcionalidad**:
- ✅ Ejecuta todos los archivos SQL en secuencia
- ✅ Maneja errores con `\set ON_ERROR_STOP on`
- ✅ Establece el search_path correcto

**Uso**:
```bash
docker exec -i pulpo-postgres-integrated psql -U pulpo -d pulpo < sql/00_all_up.sql
```

---

### **2. `01_core_up.sql` - Esquema Base del Sistema**
**Propósito**: Estructura fundamental del SaaS multi-tenant
**Funcionalidad**:
- ✅ **Extensiones**: pgcrypto, vector, citext
- ✅ **Esquema**: Crea schema `pulpo`
- ✅ **Tablas principales**:
  - `workspaces`: Clientes/empresas
  - `users`: Usuarios del sistema
  - `workspace_members`: Relación usuarios-workspaces
  - `channels`: Canales de comunicación (WhatsApp)
  - `contacts`: Contactos de clientes
  - `conversations`: Conversaciones activas
  - `messages`: Mensajes individuales
  - `faqs`: Base de conocimiento
  - `handoff_tickets`: Escalamiento a humanos
  - `workspace_configs`: Configuración por workspace
- ✅ **ENUMs**: message_role, message_dir, message_type
- ✅ **RLS**: Row Level Security para aislamiento
- ✅ **Índices**: Para performance
- ✅ **Políticas**: Aislamiento por workspace

**Errores encontrados**:
- ❌ Línea 10: Falta coma después de `'agent_custom')`
- ❌ Línea 10: `vertical text NOT NULL,` está mal formateada

**Corrección**:
```sql
plan_tier text NOT NULL CHECK (plan_tier IN ('agent_basic','agent_pro','agent_premium', 'agent_custom')),
vertical text NOT NULL,
```

---

### **3. `02_seed_dev.sql` - Datos de Desarrollo**
**Propósito**: Poblar la base de datos con datos de prueba
**Funcionalidad**:
- ✅ **Workspace de prueba**: ID fijo para desarrollo
- ✅ **Configuración completa**: Settings para restaurante
- ✅ **Usuario demo**: Para testing
- ✅ **Canal WhatsApp**: Configuración de prueba
- ✅ **Contacto demo**: Cliente de prueba
- ✅ **Conversación demo**: Mensajes de ejemplo
- ✅ **Policy JSON**: Configuración de negocio

**Datos incluidos**:
- Workspace: "El Local de Prueba" (gastronomía)
- Usuario: dev@pulpo.local
- Canal: WhatsApp de prueba
- Conversación: Mensajes de ejemplo

---

### **4. `03_functions.sql` - Funciones de Persistencia**
**Propósito**: Funciones para manejar mensajes entrantes y salientes
**Funcionalidad**:
- ✅ **`persist_inbound()`**: Persiste mensajes entrantes
  - Crea/actualiza contactos
  - Busca/crea conversaciones
  - Inserta mensajes con deduplicación
  - Actualiza contadores
- ✅ **`persist_outbound()`**: Persiste mensajes salientes
  - Inserta respuestas del asistente
  - Actualiza conversaciones
  - No afecta unread_count

**Parámetros**:
- `p_ws_id`: ID del workspace
- `p_channel_id`: ID del canal
- `p_user_phone`: Teléfono del usuario
- `p_wamid`: ID del mensaje de WhatsApp
- `p_text`: Contenido del mensaje

---

### **5. `04_views_debug.sql` - Vistas de Debugging**
**Propósito**: Vistas para facilitar el debugging y monitoreo
**Funcionalidad**:
- ✅ **`v_conversations_last`**: Estado actual de conversaciones
- ✅ **`v_messages_recent`**: Últimos 200 mensajes
- ✅ **`v_conversations_overview`**: Resumen de conversaciones

**Uso**:
```sql
SELECT * FROM pulpo.v_conversations_last;
SELECT * FROM pulpo.v_messages_recent;
```

---

### **6. `05_settings_and_helpers.sql` - Helpers y Configuración**
**Propósito**: Funciones auxiliares para configuración
**Funcionalidad**:
- ✅ **Configuración por canal**: Overrides de settings
- ✅ **`get_plan_vertical_settings()`**: Merge de configuración
- ✅ **`resolve_channel_by_phone()`**: Resolución de canales

**Funciones**:
- `get_plan_vertical_settings(ws_id, channel_id)`: Combina settings
- `resolve_channel_by_phone(phone)`: Encuentra canal por teléfono

---

### **7. `06_plg_up.sql` - Analytics y Métricas**
**Propósito**: Tracking de intenciones y métricas de plan
**Funcionalidad**:
- ✅ **`intent_events`**: Registro de intenciones detectadas
- ✅ **`plan_opportunities_daily`**: Contadores diarios
- ✅ **`email_outbox`**: Cola de emails
- ✅ **`inc_plan_metric()`**: Helper para métricas

**Tablas**:
- `intent_events`: Intención, confianza, bloqueo por plan
- `plan_opportunities_daily`: Métricas por día
- `email_outbox`: Emails pendientes

---

### **8. `07_rag_up.sql` - Sistema RAG Completo**
**Propósito**: Implementación completa del sistema RAG
**Funcionalidad**:
- ✅ **Extensiones**: vector, unaccent, pg_trgm
- ✅ **Tablas RAG**:
  - `documents`: Archivos cargados
  - `chunks`: Fragmentos de texto
  - `chunk_embeddings`: Vectores de 1024 dimensiones
  - `ingest_jobs`: Jobs de procesamiento
- ✅ **Índices optimizados**:
  - IVFFLAT para vectores (cosine similarity)
  - GIN para full-text search en español
  - Trigram para similitud
- ✅ **RLS**: Aislamiento por workspace

**Configuración**:
- Dimensiones: 1024 (BGE-M3)
- Idioma: Español con unaccent
- Similarity: Cosine para vectores

---

### **9. `08_vertical_packs_up.sql` - Paquetes por Vertical**
**Propósito**: Configuración específica por tipo de negocio
**Funcionalidad**:
- ✅ **`vertical_packs`**: Configuración por vertical
- ✅ **`conversation_slots`**: Estado de slots por conversación
- ✅ **`conversation_flow_state`**: Estado del flujo
- ✅ **Verticales soportadas**: gastronomía, ecommerce, inmobiliaria, genérico

**Configuración por vertical**:
- `role_prompt`: Prompt del asistente
- `intents_json`: Intenciones soportadas
- `slots_config`: Configuración de slots
- `tools_config`: Herramientas disponibles
- `policies_config`: Políticas de negocio
- `handoff_rules`: Reglas de escalamiento
- `rag_sources`: Fuentes de conocimiento

---

### **10. `09_orchestrator_functions.sql` - Funciones del Orquestador**
**Propósito**: Lógica de negocio para el orquestador
**Funcionalidad**:
- ✅ **Funciones de slot filling**
- ✅ **Validación de datos**
- ✅ **Transiciones de estado**
- ✅ **Herramientas por vertical**

---

### **11. `10_vertical_packs_seed.sql` - Datos de Verticales**
**Propósito**: Datos de ejemplo para cada vertical
**Funcionalidad**:
- ✅ **Configuraciones predefinidas**
- ✅ **Datos de prueba**
- ✅ **Ejemplos de uso**

---

### **12. `11_file_management_improved.sql` - Gestión de Archivos**
**Propósito**: Sistema mejorado de gestión de archivos
**Funcionalidad**:
- ✅ **Tabla `files` extendida**
- ✅ **Metadatos por vertical**
- ✅ **Sistema de versiones**
- ✅ **Borrado consistente**

---

### **13. `12_raw_files_system_fixed.sql` - Sistema de Archivos Raw**
**Propósito**: Sistema de archivos crudos y versiones
**Funcionalidad**:
- ✅ **Archivos crudos con almacenamiento**
- ✅ **Sistema de versiones**
- ✅ **Metadatos por vertical y tipo**
- ✅ **Borrado consistente**
- ✅ **Columnas agregadas**:
  - `vertical`: Tipo de negocio
  - `document_type`: Tipo de documento
  - `storage_uri`: URI de almacenamiento
  - `mime_type`: Tipo MIME
  - `file_hash`: Hash del archivo
  - `processing_status`: Estado del procesamiento
  - `deleted_at`: Timestamp de borrado

---

### **14. `13_workflow_functions.sql` - Funciones de Workflow**
**Propósito**: Funciones específicas para el workflow de N8N
**Funcionalidad**:
- ✅ **`persist_inbound()`**: Persiste mensajes entrantes
- ✅ **`persist_outbound()`**: Persiste mensajes salientes
- ✅ **Funciones de slot filling**
- ✅ **Validación de datos**
- ✅ **Herramientas por vertical**

**Errores encontrados**:
- ❌ Función `persist_inbound` duplicada (ya existe en 03_functions.sql)
- ❌ Lógica inconsistente entre versiones

---

## 🐍 **ARCHIVOS PYTHON - Lógica de Negocio**

### **📁 Estructura de Directorios:**

```
services/          # APIs REST
core/              # Lógica de negocio
├── slot_filling/  # Sistema de diálogo
├── rag/           # Búsqueda inteligente
├── orchestrator/  # Coordinador principal
└── tools/         # Herramientas por vertical
utils/             # Utilidades
auth/              # Autenticación
```

---

### **🔧 SERVICIOS (APIs REST)**

#### **1. `services/document_api_fixed.py` - API Principal**
**Propósito**: API REST genérica para gestión de documentos
**Funcionalidad**:
- ✅ **Endpoints principales**:
  - `POST /upload`: Subir documentos
  - `GET /documents`: Listar documentos
  - `GET /search`: Búsqueda en documentos
  - `DELETE /documents/{id}`: Eliminar documento
- ✅ **Configuración por vertical**: gastronomía, inmobiliaria, servicios
- ✅ **Procesamiento de archivos**: Extracción de texto, chunking
- ✅ **Búsqueda híbrida**: Vector + full-text search

**Errores encontrados**:
- ❌ Imports faltantes: `from core.ingestion.document_ingestion import DocumentIngestionPipeline`
- ❌ Imports faltantes: `from core.rag.rag_worker import RAGWorker`
- ❌ Imports faltantes: `from core.search.hybrid_search import hybrid_search_engine`
- ❌ Configuración de base de datos hardcodeada
- ❌ Manejo de errores inconsistente

**Correcciones necesarias**:
```python
# Agregar imports faltantes
from core.ingestion.document_ingestion import DocumentIngestionPipeline
from core.rag.rag_worker import RAGWorker
from core.search.hybrid_search import hybrid_search_engine

# Usar variables de entorno
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://pulpo:pulpo@localhost:5432/pulpo')
```

#### **2. `services/menu_api.py` - API de Menús**
**Propósito**: API específica para gestión de menús gastronómicos
**Funcionalidad**:
- ✅ **Endpoints de menús**:
  - `POST /upload-menu`: Subir menú
  - `GET /menu`: Obtener menú
  - `GET /search-menu`: Buscar en menú
- ✅ **Procesamiento específico**: Extracción de platos, precios, categorías
- ✅ **Validación**: Verificación de datos de menú

#### **3. `services/rag_query_api.py` - API de Consultas RAG**
**Propósito**: API para consultas del sistema RAG
**Funcionalidad**:
- ✅ **Endpoints RAG**:
  - `POST /query`: Consulta RAG
  - `GET /similar`: Búsqueda de similitud
  - `GET /stats`: Estadísticas de uso

#### **4. `services/file_ingestor.py` - Ingestor de Archivos**
**Propósito**: Servicio de ingesta de archivos para RAG
**Funcionalidad**:
- ✅ **Procesamiento de archivos**: OCR, extracción de texto
- ✅ **Chunking**: División en fragmentos
- ✅ **Embeddings**: Generación de vectores
- ✅ **Persistencia**: Almacenamiento en base de datos

**Errores encontrados**:
- ❌ Imports faltantes: `from file_processor_improved import FileProcessorImproved`
- ❌ Imports faltantes: `from tika_client import TikaClient`
- ❌ Imports faltantes: `from ollama_embeddings import OllamaEmbeddings`

---

### **🧠 CORE - Lógica de Negocio**

#### **1. `core/slot_filling/integrated_chatbot.py` - Chatbot Integrado**
**Propósito**: Sistema integrado de chatbot con todas las funcionalidades
**Funcionalidad**:
- ✅ **Slot filling**: Llenado de campos de formulario
- ✅ **RAG integration**: Búsqueda en documentos
- ✅ **Debounce**: Acumulación de mensajes
- ✅ **Multi-vertical**: Soporte para diferentes negocios

**Errores encontrados**:
- ❌ Imports faltantes: `from slot_filling_system import SlotFillingSystem`
- ❌ Imports faltantes: `from debounce_system import DebounceSystem`
- ❌ Imports faltantes: `from smart_document_processor import SmartDocumentProcessor`

#### **2. `core/rag/` - Sistema RAG**
**Propósito**: Búsqueda inteligente con vectores
**Funcionalidad**:
- ✅ **Generación de embeddings**
- ✅ **Búsqueda vectorial**
- ✅ **Búsqueda híbrida**
- ✅ **Chunking inteligente**

#### **3. `core/orchestrator/` - Orquestador**
**Propósito**: Coordinador principal del sistema
**Funcionalidad**:
- ✅ **Gestión de flujos**
- ✅ **Coordinación de componentes**
- ✅ **Manejo de errores**

#### **4. `core/tools/` - Herramientas por Vertical**
**Propósito**: Herramientas específicas por tipo de negocio
**Funcionalidad**:
- ✅ **Gastronomía**: search_menu, suggest_upsell, create_order
- ✅ **Inmobiliaria**: list_properties, schedule_visit
- ✅ **Servicios**: list_services, list_slots, book_slot

---

### **🔧 UTILS - Utilidades**

#### **1. `utils/ollama_embeddings.py` - Cliente Ollama**
**Propósito**: Cliente para generación de embeddings con Ollama
**Funcionalidad**:
- ✅ **Health check**: Verificación de disponibilidad
- ✅ **Generación de embeddings**: Para textos
- ✅ **Información del modelo**: Detalles del modelo
- ✅ **Batch processing**: Procesamiento en lote

**Errores encontrados**:
- ❌ Dimensiones hardcodeadas: `self.dims = 768`
- ❌ Modelo por defecto: `nomic-embed-text`
- ❌ Falta validación de respuestas

**Correcciones necesarias**:
```python
# Usar variables de entorno
self.dims = int(os.getenv('EMBEDDING_DIMS', '768'))
self.model = os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
```

#### **2. `utils/tika_client.py` - Cliente Tika**
**Propósito**: Cliente para extracción de texto con Apache Tika
**Funcionalidad**:
- ✅ **Extracción de texto**: De múltiples formatos
- ✅ **Metadatos**: Información del archivo
- ✅ **Health check**: Verificación de disponibilidad

#### **3. `utils/audio_video_processor.py` - Procesador AV**
**Propósito**: Procesamiento de archivos de audio y video
**Funcionalidad**:
- ✅ **Transcripción**: Audio a texto
- ✅ **Extracción de audio**: De video
- ✅ **Procesamiento de metadatos**

#### **4. `utils/language_detector.py` - Detector de Idioma**
**Propósito**: Detección automática de idioma
**Funcionalidad**:
- ✅ **Detección de idioma**: Español, inglés, etc.
- ✅ **Confianza**: Nivel de certeza
- ✅ **Fallback**: Idioma por defecto

---

### **🔐 AUTH - Autenticación**

#### **1. `auth/pulpo_token_validator.py` - Validador de Tokens**
**Propósito**: Validación de tokens JWT
**Funcionalidad**:
- ✅ **Validación JWT**: Verificación de tokens
- ✅ **Extracción de claims**: Información del usuario
- ✅ **Verificación de permisos**: Roles y workspaces

---

## 🚨 **ERRORES CRÍTICOS ENCONTRADOS**

### **1. Imports Faltantes**
**Problema**: Muchos archivos Python tienen imports que no existen
**Solución**: Crear los módulos faltantes o corregir los imports

### **2. Configuración Hardcodeada**
**Problema**: URLs y configuraciones están hardcodeadas
**Solución**: Usar variables de entorno

### **3. Funciones SQL Duplicadas**
**Problema**: `persist_inbound` existe en múltiples archivos
**Solución**: Consolidar en un solo archivo

### **4. Errores de Sintaxis SQL**
**Problema**: Errores de formato en archivos SQL
**Solución**: Corregir sintaxis

### **5. Falta de Manejo de Errores**
**Problema**: Manejo inconsistente de errores
**Solución**: Implementar manejo robusto

---

## 🔧 **PLAN DE CORRECCIÓN**

### **Fase 1: Corrección de Errores Críticos**
1. ✅ Corregir errores de sintaxis SQL
2. ✅ Crear módulos Python faltantes
3. ✅ Corregir imports
4. ✅ Implementar variables de entorno

### **Fase 2: Mejora de Documentación**
1. ✅ Agregar docstrings a todas las funciones
2. ✅ Documentar parámetros y retornos
3. ✅ Agregar ejemplos de uso
4. ✅ Documentar errores comunes

### **Fase 3: Optimización**
1. ✅ Mejorar performance de queries
2. ✅ Optimizar índices
3. ✅ Implementar caching
4. ✅ Mejorar manejo de errores

---

## 📋 **COMANDOS DE VERIFICACIÓN**

### **Verificar Base de Datos:**
```bash
# Conectar a PostgreSQL
docker exec -it pulpo-postgres-integrated psql -U pulpo -d pulpo

# Verificar tablas
\dt pulpo.*

# Verificar funciones
\df pulpo.*

# Verificar extensiones
\dx
```

### **Verificar Python:**
```bash
# Verificar imports
python3 -c "import services.document_api_fixed"

# Verificar sintaxis
python3 -m py_compile services/document_api_fixed.py

# Ejecutar tests
python3 scripts/test_generic_system.py
```

---

## 🎯 **PRÓXIMOS PASOS**

1. **Corregir errores críticos** identificados
2. **Crear módulos faltantes** en Python
3. **Implementar variables de entorno** para configuración
4. **Agregar documentación** a todas las funciones
5. **Crear tests** para validar funcionalidad
6. **Optimizar performance** de queries y código

---

## 📞 **Soporte**

Para dudas sobre el código:
- Revisar esta documentación
- Verificar logs del sistema
- Ejecutar comandos de verificación
- Consultar la guía completa del sistema

**¡El sistema PulpoAI ahora tiene documentación completa de todo el código!** 🐙✨




