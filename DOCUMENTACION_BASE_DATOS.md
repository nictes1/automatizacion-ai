# 📊 Documentación Completa de la Base de Datos - PulpoAI

## 🎯 **Propósito General**

PulpoAI es un sistema de diálogo orientado a tareas con slot filling, diseñado como un SaaS multitenant que permite a diferentes empresas gestionar conversaciones automatizadas a través de WhatsApp. La base de datos está optimizada para manejar múltiples verticales (gastronomía, inmobiliaria, ecommerce) con aislamiento completo entre workspaces.

---

## 🏗️ **Arquitectura Multitenant**

### **Concepto Clave: Row Level Security (RLS)**
- **Aislamiento por Workspace**: Cada tabla implementa RLS para garantizar que los datos de un workspace nunca sean visibles para otro
- **Contexto de Sesión**: Se utiliza `current_setting('app.workspace_id')` para establecer el contexto de workspace
- **Función Helper**: `pulpo.set_ws_context(workspace_uuid)` establece el contexto de sesión

### **Esquema Principal**
- **Schema**: `pulpo` (todas las tablas están en este esquema)
- **Extensiones**: `pgcrypto`, `vector`, `citext`, `uuid-ossp`, `unaccent`, `pg_trgm`

---

## 📋 **Tablas del Sistema**

### **1. 🏢 Tablas de Gestión de Workspaces**

#### **`pulpo.workspaces`** - Configuración de Clientes
**Propósito**: Almacena la configuración de cada cliente/empresa que usa el sistema.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único del workspace |
| `name` | TEXT | Nombre del workspace/cliente |
| `plan_tier` | TEXT | Plan de suscripción (agent_basic, agent_pro, agent_premium, agent_custom) |
| `vertical` | TEXT | Vertical de negocio (gastronomia, inmobiliaria, ecommerce, generico) |
| `settings_json` | JSONB | Configuración específica del workspace |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Relaciones**:
- **1:N** → `workspace_members`, `channels`, `contacts`, `conversations`, `messages`

#### **`pulpo.users`** - Usuarios del Sistema
**Propósito**: Usuarios que pueden acceder al sistema (administradores, editores, etc.).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único del usuario |
| `email` | CITEXT | Email único (case insensitive) |
| `name` | TEXT | Nombre del usuario |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Relaciones**:
- **N:M** → `workspaces` (a través de `workspace_members`)

#### **`pulpo.workspace_members`** - Relación Usuarios-Workspaces
**Propósito**: Define qué usuarios tienen acceso a qué workspaces y con qué rol.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `user_id` | UUID | FK → `users.id` |
| `role` | TEXT | Rol (owner, admin, editor, viewer) |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, user_id)` - Un usuario no puede tener múltiples roles en el mismo workspace

---

### **2. 📱 Tablas de Comunicación**

#### **`pulpo.channels`** - Canales de Comunicación
**Propósito**: Configuración de canales de comunicación (WhatsApp, etc.).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único del canal |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `type` | TEXT | Tipo de canal (whatsapp) |
| `provider` | TEXT | Proveedor (meta_whatsapp) |
| `business_phone_id` | TEXT | ID del teléfono de negocio en el proveedor |
| `display_phone` | TEXT | Número de teléfono visible |
| `status` | TEXT | Estado (active, disabled) |
| `settings_json` | JSONB | Configuración específica del canal |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, business_phone_id)` - Un workspace no puede tener el mismo business_phone_id duplicado

#### **`pulpo.contacts`** - Contactos de Clientes
**Propósito**: Información de los contactos/clientes que interactúan con el sistema.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único del contacto |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `user_phone` | TEXT | Número de teléfono del cliente |
| `attributes_json` | JSONB | Atributos adicionales (nombre, preferencias, etc.) |
| `last_seen_at` | TIMESTAMPTZ | Última vez que se vio al contacto |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, user_phone)` - Un contacto no puede existir dos veces en el mismo workspace

---

### **3. 💬 Tablas de Conversaciones**

#### **`pulpo.conversations`** - Conversaciones
**Propósito**: Representa una conversación activa entre un contacto y el sistema.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único de la conversación |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `contact_id` | UUID | FK → `contacts.id` |
| `channel_id` | UUID | FK → `channels.id` |
| `status` | TEXT | Estado (open, closed) |
| `last_message_at` | TIMESTAMPTZ | Timestamp del último mensaje |
| `last_message_text` | TEXT | Texto del último mensaje |
| `last_message_sender` | TEXT | Quien envió el último mensaje |
| `total_messages` | INT | Contador total de mensajes |
| `unread_count` | INT | Contador de mensajes no leídos |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, contact_id) WHERE status = 'open'` - Solo una conversación abierta por contacto

#### **`pulpo.messages`** - Mensajes Individuales
**Propósito**: Almacena cada mensaje individual dentro de una conversación.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único del mensaje |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `conversation_id` | UUID | FK → `conversations.id` |
| `role` | ENUM | Rol (user, assistant, system, tool) |
| `direction` | ENUM | Dirección (inbound, outbound) |
| `message_type` | ENUM | Tipo (text, image, document, audio, video, interactive, location, template) |
| `wa_message_id` | TEXT | ID del mensaje en WhatsApp (para deduplicación) |
| `content_text` | TEXT | Contenido del mensaje |
| `model` | TEXT | Modelo de IA usado (si aplica) |
| `tool_name` | TEXT | Herramienta usada (si aplica) |
| `media_url` | TEXT | URL de media (si aplica) |
| `meta_json` | JSONB | Metadatos adicionales |
| `tokens_in` | INT | Tokens de entrada |
| `tokens_out` | INT | Tokens de salida |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, wa_message_id)` - Evita duplicación de mensajes de WhatsApp

---

### **4. 🤖 Tablas de IA y Configuración**

#### **`pulpo.vertical_packs`** - Configuración por Vertical
**Propósito**: Configuración específica de IA para cada vertical de negocio.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `vertical` | TEXT | Vertical (gastronomia, ecommerce, inmobiliaria, generico) |
| `role_prompt` | TEXT | Prompt del rol del asistente |
| `intents_json` | JSONB | Configuración de intenciones |
| `slots_config` | JSONB | Configuración de slots |
| `tools_config` | JSONB | Configuración de herramientas |
| `policies_config` | JSONB | Configuración de políticas |
| `handoff_rules` | JSONB | Reglas de escalamiento |
| `rag_sources` | JSONB | Fuentes de RAG |
| `is_active` | BOOLEAN | Si está activo |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Fecha de actualización |

**Restricciones**:
- `UNIQUE(workspace_id, vertical)` - Un workspace no puede tener múltiples configuraciones para el mismo vertical

#### **`pulpo.conversation_slots`** - Estado de Slots
**Propósito**: Maneja el estado de los slots (información que se está recolectando) en cada conversación.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `conversation_id` | UUID | FK → `conversations.id` |
| `intent` | TEXT | Intención actual |
| `slots_json` | JSONB | Estado actual de los slots |
| `required_slots` | JSONB | Slots requeridos |
| `completed_slots` | JSONB | Slots completados |
| `current_question` | TEXT | Pregunta actual |
| `attempts_count` | INT | Número de intentos |
| `max_attempts` | INT | Máximo de intentos |
| `status` | TEXT | Estado (collecting, completed, failed, handoff) |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Fecha de actualización |

**Restricciones**:
- `UNIQUE(workspace_id, conversation_id, intent)` - Una conversación no puede tener múltiples estados de slots para la misma intención

#### **`pulpo.conversation_flow_state`** - Estado del Flujo
**Propósito**: Maneja el estado actual del flujo de conversación (máquina de estados).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `conversation_id` | UUID | FK → `conversations.id` |
| `current_state` | TEXT | Estado actual del flujo |
| `previous_state` | TEXT | Estado anterior |
| `state_data` | JSONB | Datos del estado |
| `automation_enabled` | BOOLEAN | Si la automatización está habilitada |
| `handoff_reason` | TEXT | Razón del escalamiento |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Fecha de actualización |

**Restricciones**:
- `UNIQUE(workspace_id, conversation_id)` - Una conversación solo puede tener un estado de flujo

---

### **5. 🛠️ Tablas de Herramientas y Analytics**

#### **`pulpo.available_tools`** - Herramientas Disponibles
**Propósito**: Registra las herramientas/agentes disponibles para cada workspace.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `tool_name` | TEXT | Nombre de la herramienta |
| `tool_config` | JSONB | Configuración de la herramienta |
| `is_active` | BOOLEAN | Si está activa |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, tool_name)` - Un workspace no puede tener la misma herramienta duplicada

#### **`pulpo.intent_classifications`** - Clasificación de Intenciones
**Propósito**: Registra las clasificaciones de intenciones para analytics.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `conversation_id` | UUID | FK → `conversations.id` |
| `message_id` | UUID | FK → `messages.id` (opcional) |
| `input_text` | TEXT | Texto de entrada |
| `detected_intent` | TEXT | Intención detectada |
| `confidence` | NUMERIC(3,2) | Nivel de confianza (0.00-1.00) |
| `vertical` | TEXT | Vertical del workspace |
| `router_version` | TEXT | Versión del router |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

#### **`pulpo.handoff_events`** - Eventos de Escalamiento
**Propósito**: Registra cuando una conversación es escalada a un humano.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `conversation_id` | UUID | FK → `conversations.id` |
| `trigger_reason` | TEXT | Razón del escalamiento |
| `trigger_data` | JSONB | Datos del trigger |
| `status` | TEXT | Estado (triggered, acknowledged, resolved, escalated) |
| `assigned_to` | UUID | FK → `users.id` (opcional) |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `resolved_at` | TIMESTAMPTZ | Fecha de resolución |

---

### **6. 📚 Tablas de RAG (Retrieval Augmented Generation)**

#### **`pulpo.documents`** - Documentos
**Propósito**: Metadatos de documentos subidos para RAG.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `title` | TEXT | Título del documento |
| `mime` | TEXT | Tipo MIME |
| `storage_url` | TEXT | URL de almacenamiento |
| `size_bytes` | BIGINT | Tamaño en bytes |
| `hash` | TEXT | Hash del contenido |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, hash)` - Evita duplicados por workspace

#### **`pulpo.chunks`** - Fragmentos de Documentos
**Propósito**: Fragmentos de texto extraídos de documentos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `document_id` | UUID | FK → `documents.id` |
| `pos` | INT | Posición en el documento |
| `text` | TEXT | Contenido del fragmento |
| `meta` | JSONB | Metadatos del fragmento |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, document_id, pos)` - Un documento no puede tener fragmentos duplicados en la misma posición

#### **`pulpo.chunk_embeddings`** - Embeddings Vectoriales
**Propósito**: Embeddings vectoriales de los fragmentos para búsqueda semántica.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `chunk_id` | UUID | FK → `chunks.id` (PK) |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `document_id` | UUID | FK → `documents.id` |
| `embedding` | VECTOR(1024) | Vector de embeddings (1024 dimensiones) |

#### **`pulpo.ingest_jobs`** - Trabajos de Ingesta
**Propósito**: Controla el proceso de ingesta de documentos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `document_id` | UUID | FK → `documents.id` (opcional) |
| `status` | TEXT | Estado (queued, processing, success, failed) |
| `error_message` | TEXT | Mensaje de error (si aplica) |
| `stats_json` | JSONB | Estadísticas del trabajo |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Fecha de actualización |

---

### **7. 📁 Tablas de Gestión de Archivos**

#### **`pulpo.files`** - Archivos Subidos
**Propósito**: Metadatos de archivos subidos para procesamiento.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `storage_uri` | TEXT | URI de almacenamiento (S3, local, etc.) |
| `filename` | TEXT | Nombre del archivo |
| `mime_type` | TEXT | Tipo MIME |
| `sha256` | TEXT | Hash SHA256 para deduplicación |
| `bytes` | BIGINT | Tamaño en bytes |
| `status` | TEXT | Estado (uploaded, processing, processed, failed) |
| `error` | TEXT | Mensaje de error (si aplica) |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `updated_at` | TIMESTAMPTZ | Fecha de actualización |

**Restricciones**:
- `UNIQUE(workspace_id, sha256)` - Evita duplicados exactos por workspace

#### **`pulpo.documents`** (Versión de Archivos) - Documentos Extraídos
**Propósito**: Documentos lógicos extraídos de archivos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `file_id` | UUID | FK → `files.id` |
| `title` | TEXT | Título del documento |
| `language` | TEXT | Idioma (es, en, etc.) |
| `raw_text` | TEXT | Texto consolidado |
| `token_count` | INT | Número de tokens |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

#### **`pulpo.doc_chunks`** - Fragmentos de Documentos
**Propósito**: Fragmentos de documentos para procesamiento.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `document_id` | UUID | FK → `documents.id` |
| `chunk_index` | INT | Índice del fragmento |
| `content` | TEXT | Contenido del fragmento |
| `token_count` | INT | Número de tokens |
| `metadata` | JSONB | Metadatos del fragmento |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(document_id, chunk_index)` - Un documento no puede tener fragmentos duplicados en el mismo índice

#### **`pulpo.doc_chunk_embeddings`** - Embeddings de Fragmentos
**Propósito**: Embeddings vectoriales de fragmentos de documentos.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `chunk_id` | UUID | FK → `doc_chunks.id` |
| `model` | TEXT | Modelo usado para generar embeddings |
| `dims` | INT | Dimensiones del vector |
| `embedding` | VECTOR | Vector de embeddings |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(chunk_id)` - Un fragmento solo puede tener un embedding

---

### **8. ⚙️ Tablas de Configuración**

#### **`pulpo.workspace_configs`** - Configuración de Workspace
**Propósito**: Configuración específica de políticas y comportamiento por workspace.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `workspace_id` | UUID | FK → `workspaces.id` (PK) |
| `policy_json` | JSONB | Configuración de políticas |
| `updated_at` | TIMESTAMPTZ | Fecha de actualización |

#### **`pulpo.faqs`** - Preguntas Frecuentes
**Propósito**: Base de conocimiento de preguntas y respuestas.

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `slug` | TEXT | Identificador único de la FAQ |
| `q` | TEXT | Pregunta |
| `a` | TEXT | Respuesta |
| `created_at` | TIMESTAMPTZ | Fecha de creación |

**Restricciones**:
- `UNIQUE(workspace_id, slug)` - Un workspace no puede tener FAQs duplicadas

#### **`pulpo.handoff_tickets`** - Tickets de Escalamiento
**Propósito**: Tickets de escalamiento a humanos (versión legacy).

| Campo | Tipo | Descripción |
|-------|------|-------------|
| `id` | UUID | Identificador único |
| `workspace_id` | UUID | FK → `workspaces.id` |
| `conversation_id` | UUID | FK → `conversations.id` |
| `last_message_id` | UUID | FK → `messages.id` (opcional) |
| `status` | TEXT | Estado (open, ack, closed) |
| `reason` | TEXT | Razón del escalamiento |
| `detail` | TEXT | Detalles adicionales |
| `created_at` | TIMESTAMPTZ | Fecha de creación |
| `acknowledged_at` | TIMESTAMPTZ | Fecha de reconocimiento |
| `closed_at` | TIMESTAMPTZ | Fecha de cierre |

---

## 🔗 **Relaciones Principales**

### **Jerarquía de Workspace**
```
workspaces (1) ←→ (N) workspace_members ←→ (N) users
workspaces (1) ←→ (N) channels
workspaces (1) ←→ (N) contacts
workspaces (1) ←→ (N) conversations
workspaces (1) ←→ (N) messages
```

### **Flujo de Conversación**
```
contacts (1) ←→ (N) conversations
channels (1) ←→ (N) conversations
conversations (1) ←→ (N) messages
conversations (1) ←→ (1) conversation_flow_state
conversations (1) ←→ (N) conversation_slots
```

### **Sistema RAG**
```
workspaces (1) ←→ (N) documents
documents (1) ←→ (N) chunks
chunks (1) ←→ (1) chunk_embeddings
documents (1) ←→ (N) ingest_jobs
```

### **Gestión de Archivos**
```
workspaces (1) ←→ (N) files
files (1) ←→ (N) documents
documents (1) ←→ (N) doc_chunks
doc_chunks (1) ←→ (1) doc_chunk_embeddings
```

---

## 🔒 **Seguridad y Aislamiento**

### **Row Level Security (RLS)**
Todas las tablas implementan RLS con políticas que filtran por `workspace_id`:

```sql
-- Ejemplo de política RLS
CREATE POLICY ws_isolation_workspaces ON pulpo.workspaces
  USING (id = current_setting('app.workspace_id', true)::uuid);
```

### **Función de Contexto**
```sql
-- Establecer contexto de workspace
SELECT pulpo.set_ws_context('workspace-uuid-here');
```

### **Aislamiento Garantizado**
- **Nivel de Sesión**: Cada conexión debe establecer su workspace
- **Políticas Automáticas**: RLS filtra automáticamente todos los datos
- **Sin Cross-Workspace**: Imposible acceder a datos de otros workspaces

---

## 📊 **Índices y Performance**

### **Índices Principales**
- **Búsqueda por Workspace**: Todas las tablas tienen índices en `workspace_id`
- **Búsqueda Temporal**: Índices en `created_at` para consultas temporales
- **Búsqueda Vectorial**: Índice IVFFLAT para embeddings con `vector_cosine_ops`
- **Búsqueda de Texto**: Índices GIN para búsqueda full-text en español
- **Deduplicación**: Índices únicos para evitar duplicados

### **Índices Vectoriales**
```sql
-- Índice para búsqueda semántica
CREATE INDEX ivf_chunk_embeddings
  ON pulpo.chunk_embeddings
  USING ivfflat (embedding vector_cosine_ops)
  WITH (lists = 100);
```

### **Índices de Texto**
```sql
-- Búsqueda full-text en español
CREATE INDEX idx_chunks_tsv_expr
  ON pulpo.chunks
  USING GIN (to_tsvector('spanish', pulpo.immutable_unaccent(coalesce(text,''))));

-- Búsqueda por similitud
CREATE INDEX idx_chunks_trgm
  ON pulpo.chunks
  USING GIN (text gin_trgm_ops);
```

---

## 🔧 **Funciones y Triggers**

### **Funciones Principales**

#### **`pulpo.persist_inbound()`** - Persistir Mensajes Entrantes
```sql
-- Persiste mensajes entrantes con deduplicación
SELECT * FROM pulpo.persist_inbound(
  workspace_id, channel_id, user_phone, wa_message_id, text
);
```

#### **`pulpo.persist_outbound()`** - Persistir Mensajes Salientes
```sql
-- Persiste mensajes salientes
SELECT * FROM pulpo.persist_outbound(
  workspace_id, conversation_id, text, message_type, model, meta
);
```

### **Triggers Automáticos**
- **`updated_at`**: Actualiza automáticamente el campo `updated_at` en todas las tablas
- **Contadores**: Mantiene contadores de mensajes y estados actualizados

---

## 📈 **Vistas y Analytics**

### **Vistas Principales**

#### **`pulpo.conversation_summary`** - Resumen de Conversaciones
```sql
-- Vista que agrega información de workspace y estado de slots
SELECT * FROM pulpo.conversation_summary;
```

#### **`pulpo.tool_analytics`** - Analytics de Herramientas
```sql
-- Estadísticas de uso de herramientas por día
SELECT * FROM pulpo.tool_analytics;
```

---

## 🚀 **Casos de Uso por Vertical**

### **Gastronomía**
- **Slots**: `categoria`, `items`, `extras`, `metodo_entrega`, `direccion`, `metodo_pago`
- **Estados**: `START` → `PEDIR_CATEGORIA` → `ARMAR_ITEMS` → `UPSELL` → `ENTREGA` → `PAGO` → `CONFIRMAR`
- **Herramientas**: `search_menu`, `suggest_upsell`, `create_order`

### **Inmobiliaria**
- **Slots**: `operation`, `type`, `zone`, `price_range`, `bedrooms`, `bathrooms`
- **Estados**: `START` → `BUSCAR_PROPIEDADES` → `FILTRAR` → `AGENDAR_VISITA` → `CONFIRMAR`
- **Herramientas**: `search_properties`, `schedule_visit`

### **Ecommerce**
- **Slots**: `categoria`, `productos`, `cantidad`, `metodo_pago`, `direccion`
- **Estados**: `START` → `CATALOGO` → `CARRITO` → `CHECKOUT` → `CONFIRMAR`
- **Herramientas**: `search_products`, `add_to_cart`, `process_order`

---

## 🔄 **Flujo de Datos Típico**

### **1. Mensaje Entrante**
```
WhatsApp → persist_inbound() → contacts (upsert) → conversations (find/create) → messages (insert)
```

### **2. Procesamiento de IA**
```
messages → intent_classifications → conversation_slots → conversation_flow_state → available_tools
```

### **3. Respuesta**
```
tool_results → persist_outbound() → messages → conversations (update counters)
```

### **4. Escalamiento**
```
handoff_rules → handoff_events → handoff_tickets
```

---

## 📝 **Consideraciones de Diseño**

### **Ventajas del Diseño**
- ✅ **Multitenant Seguro**: RLS garantiza aislamiento completo
- ✅ **Escalable**: Índices optimizados para grandes volúmenes
- ✅ **Flexible**: JSONB permite configuración dinámica
- ✅ **Extensible**: Fácil agregar nuevos verticales
- ✅ **Analytics**: Tablas dedicadas para métricas

### **Limitaciones**
- ⚠️ **Complejidad**: Muchas tablas requieren conocimiento del dominio
- ⚠️ **JSONB**: Consultas complejas pueden ser lentas
- ⚠️ **RLS**: Requiere contexto de sesión en todas las consultas

### **Recomendaciones**
- 🔧 **Monitoreo**: Implementar alertas para consultas lentas
- 🔧 **Backup**: Backup regular de datos críticos
- 🔧 **Índices**: Monitorear uso de índices y optimizar según necesidad
- 🔧 **RLS**: Siempre establecer contexto de workspace antes de consultas

---

## 🎯 **Conclusión**

La base de datos de PulpoAI está diseñada como un sistema robusto, escalable y seguro para manejar conversaciones automatizadas multitenant. Su arquitectura permite:

- **Aislamiento completo** entre workspaces
- **Flexibilidad** para diferentes verticales de negocio
- **Escalabilidad** para grandes volúmenes de conversaciones
- **Analytics** detallados para optimización
- **RAG** integrado para conocimiento contextual

El diseño prioriza la seguridad, performance y mantenibilidad, haciendo que sea una base sólida para un sistema de IA conversacional empresarial.
