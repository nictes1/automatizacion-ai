# **La “Biblia” de Pulpo.**

# **1\. Visión General**

## **1.1 Objetivo de la plataforma Pulpo**

Pulpo es una plataforma SaaS multitenant que automatiza la atención por canales de mensajería —inicia en WhatsApp y es extensible a voz, Telegram e Instagram DM— ofreciendo respuestas útiles y ejecución de acciones según el plan contratado. Los objetivos son:  
 • Reducir costos operativos y tiempos de respuesta.  
 • Estandarizar la calidad de atención con controles de entrada y salida (guardrails).  
 • Aumentar la conversión (reservas, pedidos, visitas) mediante flujos de acción.  
 • Centralizar la operación en un dashboard web (con takeover humano on-demand).  
 • Escalar por vertical (inmobiliaria, gastronomía, e-commerce) con configuraciones y prompts específicos.  
 • Integrarse con sistemas del negocio (Google Calendar/Sheets, Shopify, MercadoLibre, POS, CRM) para ejecutar acciones confiables.  
 • Asegurar aislamiento entre clientes mediante RLS y políticas por workspace en la base de datos.

Resultado esperado: cada negocio conecta su número de WhatsApp; Pulpo recibe los mensajes, clasifica la intención, responde con RAG y, según el plan, puede ejecutar acciones (disponible desde el Plan Empleado; los planes superiores amplían integraciones, límites y métricas).

---

## **1.2 Problemas que resuelve por vertical**

**Inmobiliaria**

* Dolores: alto volumen de consultas repetidas; coordinación de visitas; pre-calificación confusa; info de propiedades dispersas.

* Pulpo resuelve: respuestas consistentes sobre fichas y requisitos; agenda visitas con confirmación; pre-califica (presupuesto, garantía, zona); comparte fichas correctamente mediante acciones (`crear_visita`, `enviar_ficha`, `precalificar_cliente`).

* Impacto: menor tiempo operativo, más visitas útiles, mayor tasa de cierre.  
  

**Gastronomía**

* Dolores: toma de pedidos por WhatsApp caótica; horarios/promos inconsistentes; reservas manuales; olvidos.

* Pulpo resuelve: toma pedidos con chequeo de disponibilidad; reserva mesas con confirmación; comunica horarios/promos actuales mediante acciones (`crear_pedido`, `reservar_mesa`, `consultar_stock`).

* Impacto: menos errores, más tickets cerrados por chat, menor abandono.

**E-commerce**

* Dolores: preguntas repetidas (stock, envío, cuotas, garantías); derivaciones a agentes; costos altos por operario.

* Pulpo resuelve: cotizaciones; inicio de checkout con enlace; consulta de estado de pedido; entrega de políticas claras mediante acciones (`cotizar`, `iniciar_checkout`, `consultar_estado_pedido`).

* Impacto: autoservicio efectivo, reducción de escaladas, aumento de conversión asistida.


**Servicios profesionales (ej. salud, educación, soporte técnico)**

* Dolores: coordinación de turnos o clases por mensajes dispersos; recordatorios olvidados; preguntas repetitivas sobre requisitos o precios.

* Pulpo resuelve: agenda turnos/clases con confirmación automática; envía recordatorios; responde FAQs normalizadas mediante acciones (`crear_turno`, `enviar_recordatorio`, `consultar_faq`).

* Impacto: mayor cumplimiento de turnos, menos ausencias, atención consistente y menor carga operativa.

**Nota transversal**  
 Cada vertical puede integrar sistemas externos específicos (Google Calendar, POS, CRM, pasarelas de pago) para que las acciones sean confiables y auditables.

**KPIs comunes**

* Tasa de autoservicio (respuestas resueltas sin humano).

* Tasa de conversión por intención (reservas, pedidos, visitas concretadas).

* Tiempo fin-a-fin de resolución.

* Reducción de errores operativos en comparación con atención manual.

---

## **1.3 Planes de servicio**

Pulpo ofrece tres planes progresivos que se adaptan al grado de automatización que necesita cada negocio:

**Pulpo Start**

* Incluye RAG para responder preguntas frecuentes y consultas básicas.

* Acciones iniciales por vertical (ej.: `crear_pedido`, `reservar_mesa`, `crear_visita`, `iniciar_checkout`).

* Confirmación natural en el chat y takeover humano disponible desde el dashboard.

* Orientado a negocios que buscan comenzar con autoservicio y reducir carga operativa.

**Pulpo Pro**

* Todo lo de Start.

* Integraciones con Google Calendar y Google Sheets para agendado y registro automático.

* Límites ampliados de mensajes, métricas de uso y reporting detallado.

* Enfoque en equipos que requieren trazabilidad y optimización de procesos.

**Pulpo Max**

* Todo lo de Pro.

* Integraciones externas avanzadas (Shopify, MercadoLibre, POS gastronómicos, CRMs inmobiliarios).

* Soporte prioritario y SLA para operaciones críticas.

* Diseñado para negocios que dependen de la automatización en producción y necesitan máxima confiabilidad.

**KPIs comunes en todos los planes**

* Tasa de éxito en acciones ejecutadas.

* Conversión por intención (reservas, pedidos, visitas concretadas).

* Tiempo fin-a-fin de resolución.

* Reducción de escaladas a agentes humanos.

El **takeover humano** está disponible en todos los planes: desde el dashboard, el operador puede interrumpir la IA y responder manualmente; el sistema etiqueta quién respondió (IA o humano).

---

## **1.4 Principios de diseño**

1. **Multitenant real**  
    Aislamiento por `workspace_id` en datos, cachés y búsquedas. Un solo software, múltiples clientes, sin cruces.  
2. **Contratos estables y microflujos**  
    Cada flujo (n8n) tiene entradas y salidas claras; si falla una etapa, se corrige ese bloque sin romper el resto.  
3. **Seguridad por defecto**  
    RBAC por workspace (owner/admin/editor/viewer), superadmin global de plataforma, API keys con scopes, webhooks firmados, PII minimizada.  
    En producción, todo tráfico cifrado (TLS), secretos gestionados en vault y backups cifrados en reposo.  
4. **Observabilidad desde el día 1**  
    Logs estructurados, métricas (TTFR, hit-rate RAG, costo/conversación), contadores de uso diarios para facturación/BI/control de costo.  
    Incluye alertas automáticas y retries configurados para fallos en flujos n8n e integraciones externas.  
5. **Costo controlado**  
    Cache de respuestas frecuentes, resúmenes por conversación cada N mensajes, clasificador previo para no invocar LLM grande en todos los casos.  
    Los límites de uso y métricas de cada plan (Start, Pro, Max) forman parte de esta estrategia.  
6. **Asincronía donde importa**  
    REST para consultas/CRUD sincrónicos; Redis Streams para ingesta de documentos, eventos de mensajes, outbox e integraciones.  
7. **Portabilidad de proveedores**  
    LLM/embeddings intercambiables (OpenAI, Anthropic, local vía Ollama). Vector store por defecto en pgvector, con opción Qdrant/Weaviate.  
    Backups portables a almacenamiento externo (ej. S3).  
8. **Enfoque por vertical con plantillas**  
    Prompts y acciones pensadas por rubro; Start con prompt parametrizable; Pro/Max con políticas y herramientas específicas por vertical.  
9. **DX y mantenibilidad**  
    Monorepo (TS) con tipos compartidos, migraciones versionadas, tests de contrato y feature flags para iterar sin romper.  
10. **Privacidad y uso agregado**  
     Análisis y métricas a nivel agregado (por vertical/plan), nunca identificando individuos. Retención y archivado definidos.  
11. **Resiliencia infra**  
     Todos los servicios cuentan con healthchecks activos y volúmenes persistentes para asegurar continuidad operativa.

## **1.5 Entornos soportados y criterios de despliegue (Dev/Staging/Prod)**

**Objetivo**  
 Estandarizar cómo se levanta Pulpo en distintos entornos y qué componentes son obligatorios u opcionales.

**Entornos**

* **Desarrollo (Dev):**

  * Despliegue local con Docker Compose.

  * Servicios obligatorios: Postgres+pgvector, Redis, n8n y Ollama (LLMs locales), pgAdmin opcional.

  * Uso de modelos locales 7–8B cuantizados (Q5/Q4) para bajo costo y latencia predecible.

  * Healthchecks activos y volúmenes persistentes para datos (`dbdata`, `redisdata`, `n8ndata`, `ollamadata`).

* **Staging:**

  * Similar a Prod pero con bajo tráfico.

  * Servicios obligatorios: Postgres+pgvector, Redis, n8n, Ollama.

  * Pruebas con datos realistas y credenciales de prueba (Stripe/MercadoPago sandbox).

  * Observabilidad mínima: logs centralizados, métricas básicas (latencia, costo/conversación) y alertas sobre fallos críticos.

  * Backups automáticos diarios con retención de 7 días.

* **Producción (Prod):**

  * Infraestructura administrada (Kubernetes o VM en HA).

  * Servicios obligatorios: Postgres+pgvector, Redis, n8n; Ollama local opcional con fallback a cloud; Qdrant/Weaviate opcional según volumen.

  * Modelos en cloud cuando se requieran \>14B parámetros, context windows grandes o alta concurrencia.

  * Seguridad: TLS obligatorio, WAF, secretos en vault, RLS activo en DB.

  * Observabilidad completa: logs estructurados, métricas (TTFR, hit-rate, costos), alertas en tiempo real y dashboards de monitoreo.

  * Backups automáticos con retención ≥30 días y pruebas periódicas de restauración.

**Criterios de selección de LLM**

* LLM local (Ollama): ideal para Dev/Staging por costo y privacidad.

* LLM cloud: necesario en Prod cuando se requiera gran escala o SLA estricto, siempre con fallback habilitado.

**Criterios de vector DB**

* pgvector en MVP y entornos pequeños.

* Qdrant/Weaviate habilitado cuando el volumen o la latencia lo justifique.

* Mantener interfaz abstracta de retrieval para portabilidad.

* TLS, WAF y secretos en vault.

## **1.6 Entorno local de desarrollo (Compose \+ GPUs \+ LLMs locales)**

**Objetivo**  
 Proveer un entorno reproducible para desarrollar y testear Pulpo con todos los servicios necesarios: DB (Postgres+pgvector), Redis, n8n, Ollama (LLM local) y utilitarios opcionales como pgAdmin.

**Premisas**

* Multi-tenant por `workspace_id` con RLS activo en todas las tablas.

* Webhooks accesibles públicamente (no localhost) para BSP de WhatsApp.

* Idempotencia en la ingesta de mensajes inbound.

**Lineamientos**

* **LLMs locales**: usar Ollama con modelos 7–8B cuantizados (Q5/Q4) para bajo costo y latencia predecible.

* **Embeddings locales**: bge-m3 por cobertura multilenguaje y buen rendimiento en RAG.

* **Vector DB**: Postgres+pgvector por defecto en MVP; habilitar Qdrant con el perfil `with-qdrant` cuando volumen/latencia lo justifique.

* **Seguridad**: credenciales por variables de entorno (.env), diagnósticos de n8n desactivados en Dev, aislamiento por red interna de Docker.

* **Orquestador**: n8n obligatorio para ejecutar flujos locales.

* **pgAdmin**: opcional para debug de base de datos.

**Infraestructura (Compose)**

* Soporte GPU: si hay GPU disponible, Ollama se ejecuta con `NVIDIA_VISIBLE_DEVICES=all`; si no, fallback a CPU.

* Volúmenes persistentes: `dbdata`, `redisdata`, `n8ndata`, `ollamadata`, `qdrantdata`.

* Healthchecks activos en todos los servicios para garantizar estabilidad durante desarrollo.

**Modelos sugeridos (Dev)**

* Chat general: `llama3.1:8b-instruct (Q5_K_M)` o `qwen2:7b-instruct (Q5_K_M)`.

* Código: `codellama:7b-instruct (Q5)` o `deepseek-coder:6-7b`.

* Embeddings: `bge-m3`.

**Estrategia híbrida**

* Desarrollo/Staging: ejecución local con Ollama.

* Producción: modelos en cloud para picos de tráfico y modelos grandes, con fallback automático si el local no alcanza (flag de feature).

**Observabilidad mínima en Dev**

* Logs locales legibles para debug.

* Métricas básicas de requests y tokens para validar consumos antes de pasar a Staging.

# **2\. Arquitectura de Alto Nivel**

## **2.1 Diagrama de Componentes**

![][image1]

**Resumen:**

* **Message API:** recibe webhooks de WhatsApp, normaliza y publica en Redis Streams; persiste en Postgres+pgvector.

* **n8n Orchestrator:** decide el flujo según plan (Start/Pro/Max) y distribuye hacia RAG, Actions o respuestas directas. Soporta workers paralelos.

* **Core/Directory API:** gestión de workspaces, usuarios, roles, configuraciones y métricas.

* **RAG API:** ingesta de documentos, chunking, embeddings, búsquedas; usa Postgres+pgvector o Qdrant como vector DB.

* **Action API:** catálogo de acciones por vertical con confirmación natural y ejecución vía integraciones externas.

* **LLM Service (Ollama/Cloud):** procesamiento de prompts y generación de respuestas. En Dev/Staging usa Ollama con GPU local; en Prod puede escalar a LLMs cloud con fallback automático.

* **Jobs/Usage:** agregadores, limpieza, retries y métricas; publica logs estructurados y usage counters.

* **Data Layer:**

  * Postgres (estado y metadatos).

  * Redis (async/cache, colas, streams).

  * MinIO/S3 (archivos originales).

  * Volúmenes persistentes para asegurar continuidad de datos.

* **Dashboard Pulpo:** front React/Next.js que consume Core API y muestra métricas, chats, documentos y control de takeover humano.

* **Infraestructura:** todos los servicios corren con healthchecks activos para resiliencia.


## **2.2 Diagrama de Despliegue**

![][image2]

**Notas:**

* Kubernetes cluster con servicios desacoplados y healthchecks por pod.

* API Gateway gestiona tráfico externo (REST/GraphQL) y aplica autenticación.

* Redis usado para colas (Streams) y cache distribuido.

* Postgres+pgvector como almacenamiento principal; Qdrant opcional según perfil y volumen.

* MinIO/S3 para archivos/documentos originales y backups cifrados.

* n8n desplegado como microservicio con **workers paralelos escalables**, orquestados vía Redis.

* Ollama desplegado con soporte GPU en Dev/Staging; en Prod se combina con LLMs cloud con fallback automático.

* Observabilidad integrada: Prometheus para métricas, Grafana para dashboards, alertas conectadas a incident response.

* Políticas de backup/restore configuradas con retención mínima de 30 días en Prod.


---

## **2.3 Estrategia Sync vs Async**

**REST síncrono (respuesta inmediata)**

* Dashboard ↔ Core API (CRUD usuarios, docs, configs).

* n8n ↔ RAG API (consulta/search de chunks).

* n8n ↔ Action API (ejecutar acción).

* n8n ↔ Core API (guardar mensajes/estados).

* **Buenas prácticas**: timeouts por endpoint, circuit breakers a externos, validación de esquema, tracing por `x-correlation-id`.

**Redis Streams (asíncrono)**

* Mensajes entrantes (Webhook → Stream → múltiples consumidores).

* Ingesta de documentos (upload → parse → embeddings).

* Outbox de acciones (eventos confirmados → integraciones externas).

* Alertas/eventos para Jobs/Monitoring.

* **Políticas**:

  * Reintentos exponenciales con límite; al exceder → **DLQ** por stream.

  * **Idempotencia** por `workspace_id` \+ `wa_message_id` (o `event_id`).

  * Persistir estado de job (pendiente/ok/fallo) y métricas (latencia, intentos, costo).

  * Logs estructurados y trazabilidad con `correlation-id` entre REST y Streams.

**Filosofía**

* **REST** para operaciones críticas con feedback al usuario.

* **Streams** para trabajos pesados, desacoplados o fan-out (ingesta, métricas, notificaciones).

* Regla de oro: todo proceso asíncrono debe ser **re-ejecutable** e **idempotente**.  
* 

**Superadmin global (plataforma)**

* Existe fuera de los workspaces.

* Accede a todos los datos y configuraciones.

* Operaciones: crear/eliminar workspaces, cambiar planes, ver métricas globales, administrar infraestructura y políticas de seguridad.

* Rol exclusivo para el equipo Pulpo.

* Autenticación reforzada con MFA obligatoria.

**Roles tenant (por workspace/negocio)**

* **owner:** dueño del negocio; administra todo en su workspace y es responsable del billing (planes, pagos, facturación).

* **admin:** gestiona configuraciones y usuarios, no facturación.

* **editor:** sube documentos, responde manualmente y toma handoff.

* **viewer:** solo visualiza métricas y conversaciones.

**Separación clara**

* Superadmin controla la plataforma Pulpo.

* Owner controla su negocio dentro de Pulpo.

**Límites y seguridad**

* Los límites de uso (mensajes, acciones, integraciones) se aplican por workspace y dependen del plan contratado (Start, Pro, Max).

* Todas las acciones críticas quedan registradas en logs de auditoría (cambios de plan, takeover humano, edición de configuración).

* Acceso mediante API keys firmadas con scopes específicos por rol.

## **2.5 Protocolos de Integración y Colaboración (MCP / A2A)**

**Objetivo**  
 Estandarizar la integración con sistemas legados y la colaboración entre agentes para reducir acoplamiento, costos de mantenimiento y tiempos de integración.

**MCP (Model Context Protocol)**

* Uso: conectar sistemas de datos y APIs heredadas con el LLM/agentes.

* Beneficio: formato estándar para pasar contexto y evidencias al modelo (evita prompts ad-hoc y errores).

* Implementación en Pulpo: adapter MCP desplegado como microservicio en Kubernetes, que traduce ERP/BD/API → contratos Core/RAG/Action.

* Seguridad: autenticación con API keys o JWT firmados, scopes por sistema integrado.

* Observabilidad: logs estructurados y métricas de uso por integración.

* Contratos: deben versionarse y mantener compatibilidad retroactiva.

**A2A (Agent-to-Agent)**

* Uso: colaboración directa entre agentes (ej. Ventas ↔ Pagos ↔ Logística).

* Beneficio: descubrimiento de capacidades, enrutamiento de tareas, negociación y resolución de conflictos.

* Implementación en Pulpo: adapter A2A como microservicio aislado para intercambio estandarizado entre agentes, manteniendo Core/Action como orígenes de verdad.

* Seguridad: autenticación mutua con tokens de corta duración; cada agente debe estar autorizado a exponer solo ciertas capacidades.

* Observabilidad: métricas y logs de cada interacción para debugging y BI.

**Complementariedad**

* MCP integra el mundo externo → Pulpo.

* A2A coordina agentes dentro y fuera de Pulpo.

* Ambos se despliegan como pods independientes dentro del cluster, con políticas de seguridad y monitoreo consistentes.


# **3\. Modelo de Datos**

## **3.1 Esquema lógico (tablas y relaciones)**

**Nota base:** todos los registros almacenan **workspace\_id**. Cualquier lectura ES OBLIGATORIO que filtre por workspace\_id.

### **3.1.1 Tenancy, usuarios y canales**

* **workspaces**  
   • id (uuid, PK)  
   • name (text)  
   • plan\_tier (enum: start, pro, max)  
   • vertical (text)  
   • settings\_json (jsonb)  
   • created\_at (timestamptz)  
* **users**  
   • id (uuid, PK)  
   • email (citext, unique)  
   • name (text)  
   • created\_at (timestamptz)  
* **workspace\_members**  
   • id (uuid, PK)  
   • workspace\_id (fk)  
   • user\_id (fk)  
   • role (enum: owner, admin, editor, viewer)  
   • created\_at (timestamptz)  
   • UNIQUE(workspace\_id, user\_id)  
* **channels**  
   • id (uuid, PK)  
   • workspace\_id (fk)  
   • type (enum: whatsapp, telegram, instagram, voice)  
   • provider (enum: meta\_whatsapp, telegram\_bot, meta\_ig, twilio\_voice)  
   • business\_phone\_id (text, unique por workspace, solo aplica a whatsapp/meta\_whatsapp; NULL en otros)  
   • display\_phone (text, E164 cuando aplique; p.ej. voice/whatsapp)  
   • provider\_ref (text, identificador específico por canal: p.ej. telegram\_bot\_token\_hash, ig\_business\_id, twilio\_sid)  
   • status (enum: active, disabled)  
   • created\_at (timestamptz)  
   • UNIQUE(workspace\_id, type, provider, display\_phone)

**Notas de integridad**  
 • Todos los registros almacenan workspace\_id y RLS es OBLIGATORIO.  
 • FKs compuestas “workspace-consistentes” (patrón): p.ej. messages(workspace\_id, conversation\_id) → conversations(workspace\_id, id).  
 • display\_phone normalizado a E164 cuando exista; para canales sin teléfono usar provider\_ref.

Í**ndices recomendados**  
 • idx\_channels\_ws\_type\_provider (workspace\_id, type, provider)  
 • idx\_members\_ws\_role (workspace\_id, role)

## **3.1.2 Contactos, conversaciones y mensajes**

**contacts**

* id (uuid, PK)

* workspace\_id (fk)

* user\_phone (text, E164, unique por workspace)

* attributes\_json (jsonb)

* last\_seen\_at (timestamptz)

* created\_at (timestamptz)

**conversations**

* id (uuid, PK)

* workspace\_id (fk)

* contact\_id (fk)

* channel\_id (fk compuesto: workspace\_id, id → channels)

* status (enum: open, closed; default open)

* total\_messages (int, default 0\)

* unread\_count (int, default 0\)

* last\_message\_at (timestamptz)

* created\_at (timestamptz)

* índice único opcional: una open por contact

  * UNIQUE(workspace\_id, contact\_id) WHERE status \= 'open'

**messages**

* id (uuid, PK)

* workspace\_id (fk)

* conversation\_id (fk compuesto: workspace\_id, id → conversations)

* role (enum: user, assistant, system, tool)

* direction (enum: inbound, outbound)

* message\_type (enum: text, image, document, audio, video, interactive, location, template)

* status (enum: pending, sent, delivered, read, failed; default pending)

* wa\_message\_id (text, unique por workspace para idempotencia)

* content\_text (text)

* media\_url (text, apunta a MinIO/S3 si guardamos copia; expiración configurable por política de retención)

* meta\_json (jsonb)

* tokens\_in (int), tokens\_out (int)

* created\_at (timestamptz)

**Integridad workspace-consistente**

* Mensajes referencian conversaciones bajo el mismo workspace.

* Se exige FK compuesta:

  * FOREIGN KEY (workspace\_id, conversation\_id) REFERENCES conversations(workspace\_id, id) ON DELETE CASCADE.

* Conversations deben referenciar channels con FK compuesta:

  * FOREIGN KEY (workspace\_id, channel\_id) REFERENCES channels(workspace\_id, id) ON DELETE CASCADE.

**Índices recomendados**

* idx\_messages\_ws\_conv\_time (workspace\_id, conversation\_id, created\_at DESC) → scroll eficiente por conversación.

* idx\_conversations\_ws\_contact\_status (workspace\_id, contact\_id, status).

* idx\_messages\_ws\_status\_time (workspace\_id, status, created\_at DESC).

* Mantener índices por (conversation\_id, created\_at DESC) y (workspace\_id, created\_at DESC) según vistas de auditoría.

**Notas**

El takeover humano debe registrarse en `audit_logs` además de marcarse en `messages.meta_json`.

* `media_url` sigue política de retención configurable (ej. 30/90 días).

## **3.1.2.x Funciones de persistencia (Inbound/Outbound robustas)**

**Persistencia de Inbound (usuario → negocio)**

* Deduplicación estricta por (workspace\_id, wa\_message\_id).

* Solo si se inserta un nuevo mensaje:

  * conversations.total\_messages \+= 1

  * conversations.unread\_count \+= 1

  * conversations.last\_message\_\* \= (‘user’, texto)

* Si es duplicado (retry BSP): no se alteran contadores, pero se registra en logs como duplicado.

* Se inserta en `event_outbox` un evento `message.created` con payload del mensaje.

**Persistencia de Outbound (negocio → usuario)**

* Inserta con role='assistant', direction='outbound', message\_type según corresponda.

* conversations.total\_messages \+= 1

* conversations.unread\_count no cambia (opcional: decrementar si la UI marca como leído tras responder).

* conversations.last\_message\_\* \= (‘assistant’, texto)

* messages.status inicial \= 'pending'. Luego, actualizaciones a 'sent/delivered/read/failed' vía callbacks del BSP.

* Se inserta en `event_outbox` un evento `message.created`.

**Tokens y trazabilidad**

* tokens\_in se setea en inbound si aplica (longitud del prompt usuario).

* tokens\_out se setea en outbound si hay respuesta IA.

* Si el takeover humano responde, debe quedar registrado en `audit_logs` con acción \= `take_handoff`.

**Seteo de contexto (RLS)**

* Todas las funciones de persistencia ejecutan:  
   `SET LOCAL app.workspace_id = '{ws_id}'`

* Garantiza que todas las lecturas/escrituras se limitan al workspace correspondiente.

## **3.1.3 Documentos y RAG**

**documents**

* id (uuid, PK)

* workspace\_id (fk)

* source\_type (enum: pdf, docx, xlsx, csv, html, txt, image\_ocr)

* title (text)

* storage\_url (text, MinIO/S3; con política de retención definida por workspace/plan)

* file\_hash\_sha256 (text, unique por workspace)

* mime\_type (text)

* version (int, default 1\)

* page\_count (int)

* created\_at, updated\_at (timestamptz)

**rag\_chunks**

* id (uuid, PK)

* workspace\_id (fk)

* document\_id (fk)

* chunk\_index (int, unique por documento)

* text (text)

* heading\_path (text) // ejemplo: H1 \> H2 \> H3

* page\_no (int)

* token\_count (int)

* overlap\_prev (int), overlap\_next (int)

* embedding (vector, dimensión parametrizable según modelo)

* embedding\_model (text, default `bge-m3` u otro según plan/config)

* created\_at (timestamptz)

* índices: (document\_id, chunk\_index), (workspace\_id) y ivfflat sobre embedding

**rag\_search\_logs**

* id (uuid, PK)

* workspace\_id (fk)

* conversation\_id (fk nullable)

* query\_text (text)

* top\_k (int)

* results\_json (jsonb) // lista con chunk\_id, score, doc\_id, chunk\_index

* latency\_ms (int)

* created\_at (timestamptz)

**ingest\_jobs**

* id (uuid, PK)

* workspace\_id (fk)

* document\_id (fk nullable)

* status (enum: pending, running, success, failed)

* retry\_count (int, default 0\)

* stats\_json (jsonb) // chunks, tokens, duration\_ms

* error\_message (text)

* created\_at, updated\_at (timestamptz)

**Notas**

* `embedding_model` configurable por workspace o plan (ej. Start \= local bge-m3, Pro/Max \= OpenAI/Anthropic).

* Políticas de retención: documentos y storage\_url sujetos a expiración según plan (ej. 6 meses en Start, ilimitado en Max).

* `latency_ms` en logs permite medir performance de búsqueda.  
  * 

## **3.1.4 Acciones y outbox**

**actions**

* id (uuid, PK)

* workspace\_id (fk)

* conversation\_id (fk compuesto: workspace\_id, id → conversations)

* type (enum: crear\_pedido, reservar\_mesa, crear\_visita, enviar\_ficha, cotizar, iniciar\_checkout, consultar\_estado\_pedido, crear\_turno, enviar\_recordatorio, consultar\_faq, custom)

* input\_json (jsonb)

* output\_json (jsonb)

* status (enum: pending, running, success, failed; default pending)

* idempotency\_key (text, unique por workspace; opcional pero recomendado)

* error\_code (text), error\_message (text)

* attempt\_count (int, default 0\)

* correlation\_id (text) // para tracing end-to-end

* created\_by\_msg\_id (fk compuesto: workspace\_id, id → messages)

* created\_at, updated\_at (timestamptz)

**Índices recomendados (actions)**

* idx\_actions\_ws\_status\_time (workspace\_id, status, updated\_at DESC)

* idx\_actions\_ws\_type\_status (workspace\_id, type, status)

* UNIQUE(workspace\_id, idempotency\_key) cuando se use idempotencia

**event\_outbox**

* id (uuid, PK)

* workspace\_id (fk)

* aggregate\_type (enum: message, action, document)

* aggregate\_id (uuid)

* event\_type (enum: created, updated, failed, delivered)

* payload\_json (jsonb)

* delivered (bool, default false)

* attempt\_count (int, default 0\)

* error\_code (text), error\_message (text)

* correlation\_id (text)

* created\_at, delivered\_at (timestamptz)

**Índices recomendados (event\_outbox)**

* idx\_outbox\_ws\_undelivered (workspace\_id, delivered) WHERE delivered \= false

* idx\_outbox\_ws\_agg (workspace\_id, aggregate\_type, aggregate\_id)

* idx\_outbox\_ws\_type\_time (workspace\_id, event\_type, created\_at DESC)

**Reglas operativas**

* Cada creación/actualización de `actions` y `messages` emite un evento en `event_outbox`.

* Consumidores externos aplican **reintentos exponenciales**; al exceder umbral → mover a **DLQ** (stream/tabla separada) conservando `correlation_id`.

* Idempotencia de acciones por `idempotency_key` para evitar efectos dobles en sistemas externos.

* FKs y consultas siempre **workspace-consistentes**.

  * 

## **3.1.5 Prompts, config y planes**

**prompt\_packs**

* id (uuid, PK)

* name (text, unique)

* vertical (text)

* system\_prompt (text)

* input\_schema\_json (jsonb)

* is\_default (bool, default false)

* created\_at (timestamptz)

**workspace\_configs**

* id (uuid, PK)

* workspace\_id (fk, unique)

* prompt\_pack\_id (fk nullable)

* policy\_json (jsonb) // top\_k, overlap, min\_score, max\_tokens, require\_confirmation, etc.

* updated\_at (timestamptz)

**plans**

* id (uuid, PK)

* code (enum: start, pro, max)

* name (text)

* policy\_json (jsonb) // incluye:

  * max\_messages\_month

  * max\_tokens\_month

  * max\_actions\_month

  * storage\_limit\_mb

  * integraciones\_habilitadas\[\]

* created\_at (timestamptz)

**subscriptions**

* id (uuid, PK)

* workspace\_id (fk, unique)

* plan\_id (fk)

* status (enum: active, past\_due, canceled)

* current\_period\_start, current\_period\_end (timestamptz)

* renewal\_method (enum: manual, auto)

* cancel\_at (timestamptz nullable)

* created\_at (timestamptz)

**usage\_counters**

* id (uuid, PK)

* workspace\_id (fk)

* period\_ym (text, ej 2025-09)

* messages\_in, messages\_out (bigint)

* tokens\_prompt, tokens\_completion (bigint)

* actions\_executed (bigint)

* storage\_mb (bigint)

* cost\_usd (numeric, default 0\)

* UNIQUE(workspace\_id, period\_ym)

**Notas**

* `plans.policy_json` define explícitamente límites por plan Start/Pro/Max.

* `usage_counters.cost_usd` permite facturación transparente.

* `renewal_method` y `cancel_at` soportan control flexible de suscripciones.

* `prompt_packs.is_default` distingue plantillas globales de personalizadas por vertical.  
  * 

## **3.1.6 Seguridad y auditoría**

**api\_keys**

* id (uuid, PK)

* workspace\_id (fk)

* name (text)

* key\_prefix (text) // identificador público (p.ej. `pulpo_live_xxx`)

* key\_hash (text, Argon2id; nunca guardar la llave en claro)

* scopes\_json (jsonb) // p.ej. \["core.read", "actions.write"\]

* role\_hint (enum: owner, admin, editor, viewer) // opcional, guía de permisos

* rate\_limit\_rps (int, default 10\)

* created\_at (timestamptz)

* last\_used\_at (timestamptz nullable)

* expires\_at (timestamptz nullable)

* revoked\_at (timestamptz nullable)

* UNIQUE(workspace\_id, name)

**Políticas de API Keys**

* Rotación obligatoria anual o ante incidente.

* Validación por `key_prefix` \+ verificación Argon2id.

* Aplicar `rate_limit_rps` por key y por workspace.

* Scopes mínimos necesarios (principio de menor privilegio).

**audit\_logs**

* id (uuid, PK)

* workspace\_id (fk)

* user\_id (fk nullable)

* api\_key\_prefix (text nullable) // si vino por API key

* action (text) // upload\_document, change\_settings, take\_handoff, etc.

* target\_type (text) // document, workspace, channel, prompt

* target\_id (uuid nullable)

* request\_id (text) // idem `x-request-id`

* correlation\_id (text) // traza entre servicios

* ip (inet nullable), user\_agent (text nullable)

* meta\_json (jsonb)

* created\_at (timestamptz)

* índice (workspace\_id, created\_at DESC)

**Lineamientos**

* Toda acción sensible (cambios de plan, takeover humano, rotación/revocación de keys) debe registrarse en `audit_logs`.

* Retención: mínimo 12 meses online; export a Parquet en MinIO/S3 para histórico extendido.

* Acceso a `audit_logs` restringido por rol; superadmin puede consultar global con fines de seguridad.  
  * 

![][image3]

## **3.2 Políticas multitenant y acceso**

**Regla de oro**  
 Todas las consultas deben llevar `WHERE workspace_id = :ws`.

**RLS (Row Level Security)**

* Obligatorio en todas las tablas con `workspace_id`.

* Políticas por defecto: `USING (workspace_id = current_setting('app.workspace_id')::uuid)`.

* Requiere que el pooler ejecute al inicio de cada request:  
  SET LOCAL app.workspace\_id \= '\<uuid\>';  
    
* Funciones de persistencia deben incluir este seteo antes de acceder a datos.

**Índices mínimos por tenant**

* btree(workspace\_id) en todas las tablas grandes.

* Índices compuestos por uso frecuente (ej. messages(conversation\_id, created\_at)).

**Idempotencia WhatsApp**

* UNIQUE(workspace\_id, wa\_message\_id) en messages.

**Cache Redis**

* Claves prefijadas: `tenant:${workspace_id}:...` para evitar colisiones.

* TTL configurable por tipo de dato (ej. 60s para contextos de RAG, 1h para sesiones).

**Pruebas de seguridad**

* Cada migración y query debe validarse con test unitario que simule acceso sin `workspace_id`.

* Debe fallar o devolver vacío, nunca filtrar datos de otro workspace.

**Auditoría**

* Accesos fallidos o intentos de bypass de RLS deben quedar registrados en `audit_logs` con acción \= `security_violation`.


---

## **3.3 Particionamiento, retención y archivo**

**Estrategia de particionado (Postgres declarativo)**

* `messages`: partición **mensual** por `created_at` (`messages_YYYY_MM`).

* `rag_search_logs`: partición **mensual** por `created_at`.

* `audit_logs`: partición **mensual** por `created_at`.

* (Opcional) Particionado por `workspace_id` para pocos tenants muy grandes.

* Índices por partición: replicar los índices del parent (p. ej. `(workspace_id, conversation_id, created_at DESC)` en `messages`).

**Retención (online) y archivo (frío)**

* `rag_search_logs`: **180 días online** → export a Parquet y borrado de Postgres.

* `messages`: **12 meses online** → export a Parquet si se requiere conservación larga.

* `audit_logs`: **12 meses online** → export opcional a Parquet.

* Políticas ajustables por plan (Start/Pro/Max) vía `plans.policy_json`.

* **Jobs automáticos** (cron): ejecutan diariamente la política de retención y el archivado.

**Archivo en Parquet (MinIO/S3)**

* Ruta y particiones:  
   `s3://pulpo-archive/{table}/year={YYYY}/month={MM}/workspace_id={UUID}/part-*.parquet`

* Compresión: **ZSTD** (preferente) o **Snappy**.

* Esquema estable \+ versionado en metadatos del archivo (compatibilidad retroactiva).

* Catálogo externo (opcional) para BI: Glue/Delta/iceberg si aplica.

**GDPR / Derecho al olvido**

* Borrado dirigido por **identidad** (ej. `contacts.user_phone` o `contact_id`):

  * Hard-delete en tablas primarias y relacionadas (`messages`, `conversations`, `actions`, `audit_logs` si aplica).

  * **Shredding de media**: eliminar objetos en MinIO/S3 referenciados por `media_url`.

  * Registrar en `audit_logs` acción `gdpr_delete` con `target_id` y `evidencia`.

* En archivos fríos (Parquet): marcar **tombstones** y re-empaquetar particiones afectadas (job batch).

**Autovacuum y mantenimiento**

* Tablas/particiones de alto churn (`messages`, `rag_chunks`):

  * `autovacuum_vacuum_scale_factor` bajo (p. ej. 0.05) y `autovacuum_analyze_scale_factor` 0.02.

  * `autovacuum_vacuum_cost_limit` elevado en ventanas de baja carga.

  * Freeze por calendario para evitar bloat en particiones antiguas.

* **Reindex** programado si detectás `n_dead_tup` alto.

* **Partition pruning**: asegurar filtros por `created_at` y `workspace_id` en consultas.

**Restauración / DR**

* Backups lógicos/phys (mínimo diario en Prod) con **retención ≥30 días**.

* **Restore de prueba** mensual hacia un entorno aislado (staging-restore) con verificación de integridad:

  * Conteos por tabla/partición.

  * Queries de sanity (último día/mes por workspace).

  * Hash de muestras contra Parquet archivado.

**Operación**

* Jobs: `retention_job`, `parquet_export_job`, `gdpr_delete_job`, `vacuum_maintenance_job`.

* Telemetría: métricas por job (`duration_ms`, `rows_affected`, `bytes_archived`, `errors`).


---

## **3.4 Estrategia de versionado de documentos**

* Cada nueva carga del mismo archivo (mismo `file_hash_sha256` cambia) crea `version = version + 1` en `documents`.

* `rag_chunks`: se regeneran por cada versión; versiones previas se marcan como **inactive** en `documents.is_active` (boolean).

* El sistema mantiene shadow index para auditoría si se requiere.

* En producción, para optimizar costos, se recomienda conservar solo la última versión activa (planes Start) y hasta N versiones anteriores (planes Pro/Max, configurable).

* Políticas de expiración:

  * Start: 1 versión activa, anteriores se eliminan.

  * Pro: hasta 3 versiones retenidas.

  * Max: versiones ilimitadas, con opción de archivado en S3/MinIO.

* `ingest_jobs` debe registrar explícitamente el número de versión procesada.

* Reindexación:

  * Por documento → borra chunks activos de esa versión y regenera.

  * Por workspace → job batch con throttling y logging.

* Rollback: se puede reactivar una versión previa marcándola como `is_active=true` y desactivando la actual.

* Métricas: `stats_json` en `ingest_jobs` debe incluir tokens/chunks por versión.


---

## **3.5 Búsqueda semántica y desempeño (pgvector)**

**Modelo y dimensión**

* `embedding` usa dimensión acorde al modelo elegido (ej. 768 para `bge-m3`, 1536 para OpenAI). Definido en config por workspace/plan.

**Índices ANN (pgvector)**

* `ivfflat(embedding) WITH (lists = 100)` como base; regla dedo: `lists ≈ sqrt(n_chunks)`.

* Ajustes por carga: aumentar `lists` para recall, subir `ivfflat.probes` en runtime para precisión (costo ↑).

**Búsqueda híbrida (recomendada)**

* Combinar **BM25** (texto) \+ **Vector** (embedding) y hacer **re-ranking**:

  1. BM25: `to_tsvector('simple', text)` con `plainto_tsquery`.

  2. Vector: `ORDER BY embedding <-> $1`.

  3. Fusionar (top\_k x 2 cada una) y re-rank con **MMR** o score mixto `α*bm25_norm + (1-α)*(1-distance_norm)`; `α` típico 0.35–0.6.

* Boost por `heading_path` y `page_no` según política.

**Consulta típica (vector puro)**

\-- $1 \= embedding consulta, $2 \= workspace\_id  
SELECT id, document\_id, chunk\_index, text, embedding \<-\> $1 AS distance  
FROM rag\_chunks  
WHERE workspace\_id \= $2  
ORDER BY embedding \<-\> $1  
LIMIT 6;

**Consulta híbrida (esquema)**

* Paso A (BM25 top 20\) \+ Paso B (Vector top 20\) → Merge \+ MMR a top\_k final (p.ej. 8).

* Filtrar por `document_id`, `page_no` o `heading_path` si hay señales del usuario.

**Parámetros por defecto (overridables en policy\_json)**

* `top_k = 6..10`, `min_score`/`max_distance` por modelo, `mmr_lambda = 0.5`, `max_tokens_context` del plan.

* `ivfflat.probes = 10` (ajustar por latencia/recall).

**Desempeño**

* `chunk_size ≈ 450` tokens, `overlap ≈ 10–15%`.

* Precomputar y cachear embeddings de consultas frecuentes (Redis, TTL corto).

* Evitar `SELECT *`; traer solo columnas necesarias para re-rank.

**Monitoreo de calidad**

* Loggear en `rag_search_logs`: `latency_ms`, `top_k`, `scores`, `model`, `hybrid=true/false`.

* Medir `hit-rate@k`, `Recall@k` en sets de validación por vertical.

**Alternativa Qdrant (HNSW)**

* Cuando el volumen/latencia lo justifique, usar Qdrant con **HNSW (M, ef\_construction, ef\_search)**.

* Mantener interfaz de retrieval abstracta para switchear entre pgvector y Qdrant.

**Seguridad**

* Siempre `WHERE workspace_id = :ws` (RLS activo). No exponer contenidos de otros tenants en resultados.

## **3.6 Reglas de consistencia y auditoría**

**Mensajes**

* Guardar siempre `direction` y `role`.

* Etiquetar `assistant` vs `user`; si takeover humano, marcar en `meta_json` quién respondió y registrar en `audit_logs`.

* Actualizar `status` en outbound (`pending → sent → delivered → read/failed`) vía callbacks del BSP.

* Cada creación/actualización emite evento `message.*` en `event_outbox`.

* Todos los eventos deben llevar `correlation_id` para trazar flujo end-to-end.

**Acciones**

* Registrar `created_by_msg_id`, `status`, `input_json`, `output_json`, `error_code`, `attempt_count`.

* Cada acción debe tener `idempotency_key` único por workspace.

* Todo éxito o fallo genera evento en `event_outbox`.

* Reintentos deben loggear `attempt_count` y `error_message`.

**Audit trail**

* Toda operación sensible (upload\_document, change\_settings, take\_handoff, rotate\_api\_key, gdpr\_delete) se guarda en `audit_logs` con `user_id`/`api_key_prefix`.

* Campos mínimos: `action`, `target_type`, `target_id`, `meta_json`, `request_id`, `correlation_id`, `ip`, `user_agent`.

* Retención: 12 meses online; export a Parquet para histórico.

**Consistencia eventual**

* `event_outbox` implementa retries con backoff y DLQ al exceder.

* Reconciliación periódica entre `actions.status` y entregas efectivas en sistemas externos.

* Toda inconsistencia detectada dispara alerta (`security_violation` o `consistency_error`) registrada en `audit_logs`.


---

**3.7 Campos críticos para BI agregado**

**Mensajes / Conversaciones**

* messages.tokens\_in, messages.tokens\_out → coste LLM por conversación.

* messages.status (pending/sent/delivered/read/failed) → embudo de entrega por canal.

* messages.channel\_meta: `channel_type`, `provider` (whatsapp/meta, telegram, ig, voice).

* conversations.total\_messages, conversations.unread\_count, conversations.last\_message\_at.

* conversations.intent\_label (opcional) → intención dominante inferida.

* conversations.takeover (bool) y takeover\_by (user\_id) → impacto de intervención humana.

**RAG**

* rag\_search\_logs.latency\_ms, top\_k, model, hybrid (bool).

* rag\_search\_logs.results\_json → medir hit-rate@k y Recall@k.

* document\_id, page\_no, heading\_path (para análisis de fuentes).

**Acciones**

* actions.type, actions.status, attempt\_count, error\_code.

* actions.conversion\_flag (bool) → si la acción cumplió el objetivo (p.ej. visita creada, pedido confirmado).

* actions.time\_to\_action\_ms → tiempo desde intención detectada a acción exitosa.

* idempotency\_key → control de duplicados en integraciones.

**Uso y Costos**

* usage\_counters.period\_ym, messages\_in/out, tokens\_prompt/completion, actions\_executed, storage\_mb, **cost\_usd**.

* cost\_usd\_detail (opcional en tabla auxiliar) con desagregado: LLM\_prompt\_usd, LLM\_completion\_usd, embeddings\_usd, storage\_usd, egress\_usd.

* workspace.plan\_tier (start/pro/max), vertical.

**Derivados (métricas calculadas)**

* Conversión por intención \= acciones.conversion\_flag / \#intenciones detectadas.

* Tasa de autoservicio \= conversaciones sin takeover / total conversaciones.

* Tiempo fin-a-fin \= t(primera pregunta) → t(acción/respuesta final).

* Costo por conversación \= sum(cost\_usd\_detail) / \#conversaciones.

* CAC asistido (si aplica) \= costo atribuible / \#ventas/visitas cerradas.

**Segmentación recomendada**

* Por workspace, plan\_tier, vertical, canal/proveedor, intención, rango temporal (día/semana/mes).

**Calidad de datos**

* Todos los datasets deben incluir `workspace_id` y `correlation_id` para joins seguros.

* Para privacidad: solo reportes **agregados**; no exponer PII.

# **4\. Planes de servicio y Prompt parametrizable**

**4.1 Pulpo Start — RAG \+ Acciones (base)**  
 **4.1.1 Alcance**  
 Además de RAG, puede ejecutar acciones con confirmación y trazabilidad end-to-end.

**4.1.2 Catálogo inicial de acciones (por vertical)**  
 **Inmobiliaria**: `crear_visita(fecha, hora, property_id, datos_cliente)`, `enviar_ficha(property_id, canal)`, `precalificar_cliente(ingresos, garantia, presupuesto)`  
 **Gastronomía**: `crear_pedido(items[], retiro|envio, horario)`, `reservar_mesa(personas, fecha, hora)`, `consultar_stock(items[])`  
 **E-commerce**: `cotizar(items[], envio)`, `iniciar_checkout(carrito_id)`, `consultar_estado_pedido(order_id)`

**4.1.3 Decisión de herramienta y confirmación**  
 Policy: si `intent ∈ acciones` y `confidence ≥ τ` (p.ej. 0.70) ⇒ proponer acción.  
 Confirmación natural antes de ejecutar: “¿Confirmás reserva para 4 personas el viernes 20:30?”  
 Respuestas válidas: Sí / No / Cambiar.  
 Ejecución: llamada a **Action API**; registrar en **actions** y **event\_outbox** con `correlation_id`.  
 Errores: mensaje claro al usuario \+ reintento o derivación a humano (takeover).

**4.1.4 Seguridad y permisos**  
 Acción habilitada por plan y por workspace (lista blanca).  
 Validación estricta de inputs (esquemas Zod).  
 Auditoría completa (actions, audit\_logs); RLS obligatorio.

**4.1.5 KPIs**  
 Tasa de éxito por tipo de acción, conversión por intención, tiempo fin-a-fin (mensaje → acción OK), % confirmaciones vs. cancelaciones.

**4.2 Pulpo Pro — Integraciones Google, límites ampliados**  
 Todo lo de Start \+ integraciones con **Google Calendar/Sheets**, más métricas y límites superiores.

**4.3 Pulpo Max — Integraciones externas y soporte prioritario**  
 Todo lo de Pro \+ integraciones **Shopify, MercadoLibre, POS, CRM** y soporte con SLA.

**4.4 Límites por plan (sugeridos, configurables por política)**

| Dimensión | Start | Pro | Max |
| ----- | ----- | ----- | ----- |
| Conversaciones | 3.000 | 8.000 | 20.000 |
| Documentos | 200 | 500 | 1.000 |
| Tamaño archivo | 20MB | 30MB | 50MB |
| Acciones | Sí | Sí | Sí |
| Integraciones | – | Google | Google \+ Ecommerce \+ CRM |
| Soporte | Email 48h | Email+Chat 24h | Prioritario \<12h |

Estos límites viven en **plans.policy\_json** y se copian/overridean en **workspace\_configs.policy\_json** si el plan del cliente lo requiere.

## **4.5 Políticas JSON por defecto (por workspace)**

{  
   "start": {  
       "require\_confirmation": true,  
       "min\_intent\_confidence": 0.70,  
       "enabled\_actions": \[  
           "reservar\_mesa","crear\_pedido","crear\_visita",  
           "cotizar","iniciar\_checkout","consultar\_estado\_pedido"  
       \],  
       "limits": {  
           "conversaciones\_mes": 3000,  
           "documentos\_mes": 200,  
           "acciones\_mes": 300,  
           "max\_file\_mb": 20  
       },  
       "integraciones": \[\]  
   },  
   "pro": {  
       "inherits": "start",  
       "limits": {  
           "conversaciones\_mes": 8000,  
           "documentos\_mes": 500,  
           "acciones\_mes": 1000,  
           "max\_file\_mb": 30  
       },  
       "integraciones": \["google\_calendar","google\_sheets"\]  
   },  
   "max": {  
       "inherits": "pro",  
       "limits": {  
           "conversaciones\_mes": 20000,  
           "documentos\_mes": 1000,  
           "acciones\_mes": 3000,  
           "max\_file\_mb": 50  
       },  
       "integraciones": \[  
           "google\_calendar","google\_sheets",  
           "shopify","mercadolibre","pos\_local","crm\_inmobiliario"  
       \],  
       "soporte": { "sla\_horas": 12 }  
   }  
}

**4.6 Criterios de aceptación por plan**  
 **Start**

* El negocio completa el formulario; el bot responde en el tono elegido sin inventar datos no cargados (RAG con fuentes).

* Cambiar un campo en la UI impacta la siguiente respuesta.

* Cache operativa en FAQs repetidas.

**Pro**

* Subida de PDF/DOCX/XLSX/CSV/HTML; ingesta → chunks → embeddings.

* Preguntas sobre datos presentes devuelven respuesta con fuente; si no hay contexto suficiente, usa fallback.

* hit-rate ≥ 0.75 en golden set inicial.

* Integraciones Google (Calendar/Sheets) funcionando con confirmación.

**Max**

* Confirmaciones previas a ejecutar; acciones registradas en `actions` y `event_outbox` con `correlation_id`.

* Errores de acción se comunican y ofrecen alternativa; retries con backoff y DLQ.

* Métricas de conversión por intención disponibles y dashboards activos.  
  

# **5\. Orquestación en n8n (microflujos)**

**Convención general**

* Todos los flujos reciben/propagan: `request_id` (uuid v4), `workspace_id`, `channel_id`, `conversation_id`, `message_id`.

* **Persistencia:** `request_id` se guarda como `correlation_id` en DB (messages/actions/audit/outbox).

* **Idempotencia:** cuando el origen es WhatsApp, usar `wa_message_id` como `idempotency_key`.

* **Errores:** cualquier fallo NO debe perder el mensaje; va a **F-DeadLetter** con contexto completo.

* **Tiempo máx. online:** ≤ 3–5 s antes de enviar “typing/processing…”. Si se supera, enviar aviso y continuar en background.

* **RLS:** toda operación a DB debe ejecutarse con contexto de workspace (ej.: `SET LOCAL app.workspace_id = '<WS_ID>'`).

  ---

## **5.1 F-00 Channel Resolver (Webhook → normalización)**

**Objetivo:** recibir el webhook del BSP (único endpoint), resolver tenant y normalizar evento.

**Dispara:** webhook `POST /webhooks/whatsapp`.

**Entradas (raw BSP):**

{  
 "entry": \[  
   {  
     "changes": \[  
       {  
         "value": {  
           "metadata": { "phone\_number\_id": "BSP\_PHONE\_ID" },  
           "messages": \[  
             { "id": "wamid.HBg...", "from": "54911...", "timestamp": "..." , "type": "text", "text": {"body":"hola, horario?"} }  
           \]  
         }  
       }  
     \]  
   }  
 \]  
}

**Pasos / Nodos n8n:**

1. Webhook (WhatsApp).

2. Function “parse”: extraer `wa_message_id`, `user_phone`, `business_phone_id`, `type`, `payload`.

3. HTTP → Core `/resolve-channel/{business_phone_id}` → `{workspace_id, channel_id, plan_tier}` (**plan\_tier: start|pro|max**).

4. HTTP → Core `/messages/inbound` (crea contact/conversation si no existe; guarda message). **(RLS activo)**

5. Set: armar evento normalizado.

**Salida (evento normalizado):**

{  
   "request\_id": "uuid",  
   "workspace\_id": "ws-uuid",  
   "channel\_id": "ch-uuid",  
   "conversation\_id": "conv-uuid",  
   "message\_id": "msg-uuid",  
   "wa\_message\_id": "wamid...",  
   "from": "54911...",  
   "plan\_tier": "start|pro|max",  
   "message": { "type": "text", "text": "hola, horario?" },  
   "ts": "2025-09-01T15:45:10Z"  
}

**Post-condiciones:** mensaje persistido; tenant resuelto.

**Errores → F-DeadLetter** con `dlq_reason: "resolve_failed|db_write_failed"`.

## **5.2 F-01 Intent (clasificación)**

**Objetivo:** etiquetar intención, vertical y entidades con modelo liviano.

**Trigger:** evento de F-00.

**Pasos:**

1. **IF**: `message.type != "text"` → `intent="media"` y seguir (o derivar a humano según política).  
2. **HTTP Request** → Core `/intent/classify` (modelo chico o reglas).  
3. **Set**: adjuntar `intent`, `confidence`, `vertical`, `entities`..

**Salida:**

{  
   "...": "...",  
   "intent": "consulta\_horario|pedido|reserva|cotizacion|visita|faq|otro",  
   "confidence": 0.86,  
   "vertical": "gastronomia|inmobiliaria|ecommerce",  
   "entities": { "personas": 2, "fecha":"2025-09-10", "hora":"20:30" }

**Post-condiciones:**  log en `intent_logs`.

**Errores → F-DeadLetter (`dlq_reason: "intent_failed"`).**

---

## 

## **5.3 F-02 Plan Router**

**Objetivo:** rutear al microflujo correcto según **`plan_tier` y `intent`.**

**Trigger:** evento desde F-01.

**Nodos:**

* Switch por `plan_tier` (**start / pro / max**).

* IF `confidence < min_confidence (p.ej. 0.6)` → enviar pregunta de aclaración (respuesta corta) y terminar.  
   **Rutas:**

* **start** → F-Prompt o F-RAG (según intent/política) o F-Agent (acciones básicas).

* **pro** → F-Agent (con integraciones Google habilitadas).

* **max** → F-Agent (con integraciones avanzadas y soporte prioritario).  
   

**Errores:** plan desconocido → **F-DeadLetter** (`dlq_reason: "unknown_plan"`).

---

## **5.4 F-Prompt (Plan Basic — prompt parametrizable)**

**Objetivo:** responder con prompt armado desde `workspace_configs.policy_json.start`.

**Pasos:**

1. **HTTP Request** → Core `/workspace/config` (trae `policy_json.start` y `prompt_pack`).

2. **Function**: construir **system prompt \+ contexto de hechos**.  
3. **HTTP Request** →LLM Provider `/chat/completions` (o vía Core centralizado).  
4. **HTTP Request** → Core `/messages/outbound` (persistir) y **Message API `/send/whatsapp`**. **(RLS activo)**

**Entrada mínima:**

{ "...": "...", "intent": "faq|consulta\_horario|...", "language": "es|en" }

**Salida (al usuario):** texto \+ quick-replies opcionales.

**Post-condiciones:** respuesta enviada y guardada (`direction=outbound`, `role=assistant`).

## **5.5 F-RAG (retrieval semántico \+ respuesta con contexto)**

**Objetivo:** RAG con políticas por plan (Start/Pro/Max).

**Pasos:**

1. **HTTP Request** → Core `/workspace/config` (obtener RAG policy).  
2. **HTTP Request** → RAG API `/search` `{workspace_id, query, top_k}`.  
3. **IF**: `results.length == 0` o `max_score < min_score` → **fallback** (“No tengo ese dato, ¿podés enviar el menú actual?”).  
4. **Function**: formar CONTEXTO con top\_k chunks \+ metadatos.  
5. **HTTP Request** → LLM con **system RAG** \+ CONTEXTO.  
6. Persistir y responder (Core/Message API). **(RLS activo)**

**Entrada RAG /search:**

{ "workspace\_id":"ws-uuid", "query":"tienen pizza sin TACC?", "top\_k":6 }

**Salida RAG:**

{  
   "results":\[  
       {"chunk\_id":"c1","doc\_id":"d1","chunk\_index":12,"score":0.82,"meta":{"title":"Menu 2025","page":2},"text":"..."}  
   \]  
}

## **5.6 F-Agent → Guardrails \+ confirmación \+ persistencias**

**Objetivo:** RAG \+ decisión de herramienta \+ confirmación \+ acción.

**Resumen operativo:**

1. **Intent \+ Slots: `/intent` → `{intent, slots, confidence}`. Si `confidence < umbral`, pedir clarificación.**

2. **RAG (si aplica): `/rag/search` con `top_k/min_score`. Loggear `request_id` (persistido como `correlation_id`).**

3. **Policy/Guardrails: `/policy/guardrails` valida reglas (horarios, stock, montos, pagos habilitados por plan).**

4. **Confirmación natural: “¿Confirmás pedido de X por $Y?” (Sí/No/Cambiar).**

5. **Ejecución de Acción: `/action/execute` (o endpoints específicos). `idempotency_key` correlada a `conversation_id`/`wa_message_id`.**

6. **Persistencias:**

   * **inbound: `pulpo.persist_inbound(...)` (ajusta contadores solo si insertó).**

   * **outbound: `pulpo.persist_outbound(...)` (actualiza `last_message_*` y `total_messages`, no toca `unread_count`).**

7. **Post-ejecución: si cobro, esperar webhook de pago y luego `/order/create`. Si error, fallback y handoff.**

**Contrato actions/execute (ejemplo reservar mesa):**

{  
 "workspace\_id":"ws-uuid",  
 "conversation\_id":"conv-uuid",  
 "type":"reservar\_mesa",  
 "input":{"personas":4,"fecha":"2025-09-05","hora":"20:30","nombre":"Nico","telefono":"54911..."}  
}

**Respuesta**

{ "ok": true, "data": { "reserva\_id": "R-8342" }, "message": "Reserva confirmada" }

**Errores**:

* Validación input → pedir corrección.

* Error Action API → “No pude confirmarlo, ¿querés que te derive con un humano?”.

* Timeout confirmación → recordar una vez y cerrar estado.

---

## 

## 

## 

## 

## **5.7 F-Human Handoff (toma manual)**

**Objetivo:** permitir que un usuario del negocio responda manualmente.

**Triggers posibles:**

* Botón en dashboard “Tomar conversación”

* Palabra clave del usuario final (“hablar con humano”)

**Pasos:**

1. **HTTP Request** → Core /conversations/{id}/auto-reply:off (marca auto\_reply=false).

2. Mensaje al cliente: “Listo, te atiende una persona en breve.”

3. Todo mensaje enviado desde el dashboard se persistirá con role=assistant y meta\_json.handled\_by\_user\_id.

**Volver a IA:** /conversations/{id}/auto-reply:on.

* **Nota:** los mensajes del dashboard se guardan con `role=assistant` y `meta_json.handled_by_user_id`; **registrar en `audit_logs` acción `take_handoff`**.

---

## **5.8 F-Ingest (pipeline de documentos)**

**Objetivo:** subir archivo → parsear → chunkear → embed → persistir.

**Entradas (desde dashboard/Core):**

{  
 "workspace\_id":"ws-uuid",  
 "document\_id":"doc-uuid",  
 "storage\_url":"s3://bucket/path.pdf",  
 "source\_type":"pdf",  
 "embedding\_model":"text-embedding-3-small"  
}

**Pasos:**

1. **HTTP Request** → RAG API /ingest/start → crea ingest\_job.

2. **Function** / **HTTP**: descargar archivo de MinIO.

3. **Execute Command** (o **HTTP a RAG API**): parse (unstructured/docling).

4. **Function**: chunking (450/12%).

5. **HTTP**: embeddings batch (provider).

6. **HTTP**: RAG API /chunks/bulk-insert.

7. Marcar ingest\_job.status \= success y actualizar documents.version.

**Errores**:

* Si cualquier etapa falla → ingest\_job.status=failed, error\_message y evento a **F-Alerts**.

**Nota:** `ingest_job.status`, `retry_count`, `error_message`; al fallar → **F-Alerts** \+ DLQ si corresponde.

## **5.9 F-Reindex**

**Objetivo:** regenerar embeddings de un documento/vertical/workspace.

**Entradas:**

{ "workspace\_id":"...", "scope":"document|vertical|workspace", "target\_id":"..." }

**Pasos:** listar chunks actuales → borrar/archivar → repetir 5.8.

---

## **5.10 F-Usage (agregadores diarios)**

**Objetivo:** llenar usage\_counters por workspace/período.

**Trigger:** cron diario 02:00 AM.

**Pasos:**

1. **HTTP** Core /usage/aggregate?date=YYYY-MM-DD.

2. Sumar: messages\_in/out, tokens\_prompt/completion, actions\_executed, storage\_mb.

3. **UPSERT** en usage\_counters(period\_ym).

**Errores**: enviar evento a **F-Alerts**.

---

## **5.11 F-Alerts (monitoring)**

**Objetivo:** emitir alertas ante métricas fuera de rango o fallas.

**Triggers:**

* ingest\_job.failed

* hit\_rate\_rag \< 0.7 (ventana 1h)

* TTFR p95 \> X s

* tasa 5xx \> umbral

* costos diarios fuera de banda

**Acciones:**

* Enviar a Slack/email/Telegram interno.

* Registrar en audit\_logs con action="alert".

---

## **5.12 F-DeadLetter (DLQ)**

**Objetivo:** asegurar que ningún evento se pierda.

**Entradas:** cualquier payload \+ dlq\_reason.

**Pasos:**

1. Guardar en tabla dead\_letters (si querés) o en MinIO con clave dlq/{YYYY-MM}/{workspace\_id}/{request\_id}.json.

2. Contador por tipo de error.

3. Job de **replay manual** (opcional) que reinyecta a F-00 o al flujo que corresponda.

**Contrato DLQ:**

{  
 "request\_id":"uuid",  
 "workspace\_id":"ws-uuid",  
 "flow":"F-XX",  
 "dlq\_reason":"resolve\_failed|intent\_failed|unknown\_plan|rag\_error|action\_error|timeout",  
 "payload":{...},  
 "ts":"2025-09-01T16:20:00Z"  
}

## **5.13 Manejo de errores y reintentos (política general)**

* **HTTP 5xx**: reintentos exponenciales (3 intentos: 1s, 4s, 10s).

* **HTTP 4xx**: no reintentar salvo 429 (esperar Retry-After).

* **Embeddings / LLM**: si timeout, 1 reintento; si vuelve a fallar → fallback al usuario.

* **Acciones**: si Action API falla, registrar actions.status=failed, explicar al usuario y ofrecer humano.  
* 429 respeta `Retry-After`; LLM/Embeddings 1 retry; acciones failed → explicar y ofrecer humano

---

## **5.14 Trazabilidad end-to-end**

* `request_id` propagado por TODOS los servicios y guardado en **DB como `correlation_id`** (messages, rag\_search\_logs, actions, audit\_logs, outbox).

* En dashboard, timeline por conversación usando `request_id`/`correlation_id` para agrupar.  
  

## **5.15 Políticas de Contexto y KV Cache**

**Objetivo:** controlar costo/latencia y reducir errores optimizando contexto e inferencia.  
 **Políticas:**

* **Pruning:** mantener N últimos turnos útiles; descartar ruido.

* **Summarization:** condensar historial largo con resúmenes parciales por tema.

* **Offloading:** mover memoria extensa a RAG; no cargar catálogos enteros en el prompt.

* **Tool Loadout explícito:** declarar herramientas disponibles para evitar alucinaciones.

* **KV Cache:** habilitar cache por conversación para acelerar respuestas largas; eviction LRU \+ límites por token.

---

## 

## **5.15 Esquema resumido de entradas/salidas por flujo**

| Flujo | Entrada | Salida | Respuesta al usuario |
| ----- | ----- | ----- | ----- |
| F-00 Resolver | Webhook BSP | Evento normalizado \+ persistencia | No |
| F-01 Intent | Evento normalizado | \+ intent, confidence, entities | No |
| F-02 Router | Evento \+ intent | Derivación a plan | No |
| F-Prompt | Evento \+ config basic | Mensaje outbound | Sí |
| F-RAG | Evento \+ rag policy | Mensaje outbound | Sí |
| F-Agent | Evento \+ RAG \+ decisión | Mensaje(s) de confirmación \+ acción | Sí |
| F-Handoff | Comando dashboard | Flag auto\_reply y etiquetas | Sí (notifica) |
| F-Ingest | Orden de ingesta | Chunks \+ embeddings | No |
| F-Reindex | Orden reindex | Chunks regenerados | No |
| F-Usage | Cron | usage\_counters | No |
| F-Alerts | Métrica o error | Notificación interna | No |
| F-DeadLetter | Payload con error | Registro DLQ | No |

{  
   "flows": {  
       "F-00 Resolver": {  
           "entrada": "Webhook BSP",  
           "salida": "Evento normalizado \+ persistencia",  
           "respuesta\_usuario": false  
       },  
       "F-01 Intent": {  
           "entrada": "Evento normalizado",  
           "salida": "+ intent, confidence, entities",  
           "respuesta\_usuario": false  
       },  
       "F-02 Router": {  
           "entrada": "Evento \+ intent",  
           "salida": "Derivación a plan",  
           "respuesta\_usuario": false  
       },  
       "F-Prompt": {  
           "entrada": "Evento \+ config basic",  
           "salida": "Mensaje outbound",  
           "respuesta\_usuario": true  
       },  
       "F-RAG": {  
           "entrada": "Evento \+ rag policy",  
           "salida": "Mensaje outbound",  
           "respuesta\_usuario": true  
       },  
       "F-Agent": {  
           "entrada": "Evento \+ RAG \+ decisión",  
           "salida": "Mensaje(s) de confirmación \+ acción",  
           "respuesta\_usuario": true  
       },  
       "F-Handoff": {  
           "entrada": "Comando dashboard",  
           "salida": "Flag auto\_reply y etiquetas",  
           "respuesta\_usuario": true  
       },  
       "F-Ingest": {  
           "entrada": "Orden de ingesta",  
           "salida": "Chunks \+ embeddings",  
           "respuesta\_usuario": false  
       },  
       "F-Reindex": {  
           "entrada": "Orden reindex",  
           "salida": "Chunks regenerados",  
           "respuesta\_usuario": false  
       },  
       "F-Usage": {  
           "entrada": "Cron",  
           "salida": "usage\_counters",  
           "respuesta\_usuario": false  
       },  
       "F-Alerts": {  
           "entrada": "Métrica o error",  
           "salida": "Notificación interna",  
           "respuesta\_usuario": false  
       },  
       "F-DeadLetter": {  
           "entrada": "Payload con error",  
           "salida": "Registro DLQ",  
           "respuesta\_usuario": false  
       }  
   }  
}

# **6\. RAG y Embeddings**

## **6.1 Objetivo**

Permitir que Pulpo responda con fidelidad usando conocimiento del cliente, con costo controlado, trazabilidad de fuentes (correlation\_id=request\_id), y operación multitenant bajo RLS. El pipeline debe ser portable de proveedor (pgvector/Qdrant), con políticas por plan (Start/Pro/Max) y auditoría completa.

---

## **6.2 Pipeline de ingesta (E2E)**

**Entradas**: workspace\_id, document\_id, storage\_url, source\_type, mime\_type, embedding\_model (opcional).  
**Salidas**: ingest\_job.status, ingest\_job.stats\_json, filas en rag\_chunks con metadatos completos; JSON normalizado almacenado en MinIO.

**Pasos:**

1. **Crear ingest\_job(status=pending, retry\_count=0) y validar inputs.**

2. **Descargar archivo de storage\_url (MinIO/S3).**

3. **Parsear (6.3) → producir JSON normalizado (6.4) y guardar copia: documents/{document\_id}/normalized.json.**

4. **Chunking (6.5) → lista de textos con metadatos.**

5. **Embeddings batch (6.6) con control de rate-limit por workspace.**

6. **Persistencia bulk en rag\_chunks (transaccional); crear/actualizar índice ANN si corresponde.**

7. **Marcar ingest\_job.status=success y actualizar documents.version/is\_active según política de versionado.**

8. **Emitir event\_outbox(document.ingested).**  
    **stats\_json (ejemplo):**  
    **{**  
    **"pages": 120, "blocks": 980, "chunks": 164,**  
    **"tokens\_text": 84500, "tokens\_embed": 84500,**  
    **"duration\_ms": 74210, "cost\_embeddings\_usd": 0.97**  
    **}**  
    **Errores: cualquier fallo → status=failed, error\_message, evento a F-Alerts y envío a F-DeadLetter con payload.**

## **6.3 Parsers soportados**

| Tipo | Herramienta | Notas |
| ----- | ----- | ----- |
| PDF | Docling (recomendado) → fallback a unstructured | Extrae títulos/secciones; tablas a texto tabulado; mejor en PDFs complejos. |
| DOCX | Docling/unstructured | Extrae encabezados, párrafos, listas. |
| HTML | readability \+ sanitizado | Mantener títulos/secciones; sanitizar y bloquear scripts. |
| TXT | directo | Normalizar encoding (UTF-8). |
| XLSX/CSV | openpyxl/pandas | Convertir a texto tabulado con encabezados; hoja por hoja. |
| Imagen | OCR (Tesseract) **opt-in** | Opt-in. Habilitado solo en **Plan Max** o bajo feature\_flag; almacenar score de OCR en metadata. |

**Recomendación:** priorizar Docling; si falla, usar unstructured. Todo parser debe producir el JSON uniforme de 6.4 y persistirlo en MinIO para auditoría y reindexación.

---

## **6.4 Normalización (esquema interno)**

Cada parser produce un JSON uniforme con secciones y bloques:

{  
   "doc": {  
       "title": "Menu 2025",  
       "source\_type": "pdf",  
       "mime": "application/pdf",  
       "page\_count": 12,  
       "lang": "es",  
       "sections": \[  
           {  
               "heading\_path": \["Menu", "Pizzas"\],  
               "page\_start": 2,  
               "page\_end": 3,  
               "blocks": \[  
                   {"type":"paragraph","text":"Pizza muzzarella ...","page":2,"lang":"es"},  
                   {"type":"table","text":"Producto | Precio\\nMuzza | 5000","page":2,"lang":"es"}  
               \]  
           }  
       \]  
   }  
}

**Reglas:**

* `heading_path`: jerarquía textual (H1 \> H2 \> H3).

* `blocks.type`: paragraph | list | table | figure\_caption.

* `blocks.page`: obligatorio (enteros ≥1).

* `blocks.lang`: detectar idioma a nivel bloque para consultas multilingües (ver 6.9).

* Tablas → convertido a texto tabulado.

* El JSON normalizado debe guardarse en MinIO en `documents/{document_id}/normalized.json` para auditoría, reindexación y debugging.

* Logging: registrar en `ingest_jobs.stats_json` el tamaño del JSON y número de secciones.

* Políticas por plan:

  * Start: PDF/DOCX.

  * Pro: \+ XLSX/CSV.

  * Max: \+ HTML, TXT, Imagen/OCR (flag).

---

## **6.5 Chunking (reglas de producción)**

Objetivo: generar chunks semánticos para buen recall sin inflar embeddings.

* **Tamaño:** 450 tokens (±50).

* **Overlap:** 12% (\~54 tokens).

* **Agrupación:** por `heading_path`, manteniendo consistencia de páginas.

* **Segmentación:** preferir sentence-aware; si no posible, sliding window.

* **Tablas:** no cortar filas; si exceden, repetir encabezado en chunk siguiente.

* **Duplicados:** evitar reinsertar bloques idénticos (dedupe simple por hash de texto).

**Metadatos por chunk:**

* document\_id, chunk\_index, heading\_path, page\_no, token\_count, overlap\_prev, overlap\_next, embedding\_model, version, lang.

**Control de calidad:**

* Rechazar chunks con \<20 tokens (ruido).

* Normalizar whitespace, remover páginas vacías.

* Guardar métricas en `ingest_jobs.stats_json`: `{chunks_total, tokens_total, avg_tokens_per_chunk, dropped_chunks}`.

**Políticas por plan:**

* **Start:** chunk básico (sliding window, sin dedupe).

* **Pro:** sentence-aware \+ dedupe \+ logging detallado.

* **Max:** sentence-aware, multilingüe, optimización avanzada (detectar topics por cluster, ajuste dinámico de chunk\_size).

---

## **6.6 Embeddings**

**6.6.1 Proveedor y dimensión**

* **Default: `text-embedding-3-small` (1536).**

* **Alternativas locales (flag): `all-MiniLM-L6-v2` (384) o `nomic-embed` (768/1024).**

* **Estrategia de esquema:**

  * Mantener una dimensión fija por tabla.

  * Si se cambia de modelo, crear columna `embedding_v2` o reindexar completo.

* **Diferenciación por plan:**

  * **Start:** solo default cloud/local pequeño.

  * **Pro:** habilita alternativos (MiniLM).

  * **Max:** soporta múltiples embeddings paralelos (shadow index).


### **6.6.2 Batching y límites**

* **Batch size**: 64–128 textos.

* **Rate limit**: token bucket por workspace, configurable en `policy_json`.

* **Reintentos**: máximo 2, backoff 1s/4s.

* Registrar en `ingest_jobs.stats_json`:  
  { "tokens\_embed": 84500, "requests": 1320, "retries": 4, "duration\_ms": 74210, "cost\_usd": 0.97 }

### **6.6.3 Texto a embeddear**

Formato:

* "{heading\_path\_str} :: {block\_or\_chunk\_text}"

Prefijo con headings → ayuda a separación semántica.  
Guardar `lang` detectado junto con cada chunk para búsquedas multilingües.

### **6.6.4 Manejo de errores**

* Timeout → 1 reintento; si vuelve a fallar → marcar `failed`.

* provider\_down → fallback a modelo alternativo si `feature_flag` habilitado.

* Loggear en `audit_logs` con action="embedding\_failed".

---

## **6.7 Persistencia (pgvector)**

* Tabla `rag_chunks` con columna `embedding vector(D)`, donde D \= dimensión activa del modelo configurado.

* Regla: mantener una sola dimensión activa por tabla. Si cambia modelo → crear `embedding_v2` y migrar o reindexar.

**Índices recomendados:**

CREATE INDEX idx\_rag\_chunks\_embed\_ivf

 ON rag\_chunks USING ivfflat (embedding vector\_cosine\_ops)

 WITH (lists \= 100);

* Parámetro `lists`: ajustar ≈ √n\_chunks (ej. 100–1000).

* Crear índice tras primer gran batch para acelerar ingesta masiva.

* En Pro/Max: permitir HNSW (`CREATE INDEX … USING hnsw`) si Postgres/pgvector versión lo soporta.

**Validaciones:**

* FK workspace\_id consistente (cross-tenant prohibido).

* UNIQUE (document\_id, chunk\_index) para evitar duplicados.

* Cada insert bulk debe correr dentro de `SET LOCAL app.workspace_id = '<ws_id>'`.

**Logging:**

* `ingest_jobs.stats_json` debe registrar:

{ "chunks\_inserted": 164, "duration\_insert\_ms": 1280, "index\_build\_ms": 421 }

**Políticas por plan:**

* Start → pgvector \+ ivfflat básico.

* Pro → tuning dinámico de `lists`, opción hnsw.

* Max → habilitar proveedor alternativo (Qdrant/Weaviate) vía Provider Interface (6.14).

---

## **6.8 Búsqueda y ranking**

**Retrieval híbrido**

* **Base:** similitud vectorial (pgvector HNSW/IVFFlat).

* **Filtros:** por metadata (`vertical`, `precio`, `estado`, `idioma`).

* **Complemento:** keyword BM25 → usado para consultas exactas (SKU, códigos).

* **Fallback:** si embeddings fallan → solo BM25.

### **6.8.1 Consulta base**

SELECT id, document\_id, chunk\_index, text, heading\_path, page\_no,  
      embedding \<-\> $1 AS distance  
FROM rag\_chunks  
WHERE workspace\_id \= $2  
ORDER BY embedding \<-\> $1  
LIMIT $k;

* $1 \= embedding de la query.

* $2 \= workspace\_id.

* k por defecto: 6\.

### **6.8.2 Re-ranking ligero en aplicación**

* Boost si `heading_path` contiene palabras de la query.

* Penalizar chunks \<40 tokens o repetidos (TF-IDF simple).

* Tie-breakers: menor chunk\_index, proximidad de page\_no.

* Medir `precision@k` además de recall/hit-rate.


### **6.8.3 Reformulación de consulta (opcional)**

* consultas pobres (“precio?”) → query\_rewriter (LLM chico o heurística).

* Solo disponible en **Pro** y **Max**.

### **6.8.4 Políticas de “no inventar”**

* Si max\_score \< min\_score (0.60 default) → no responder con RAG.

* Fallback: pedir dato al usuario o derivar a humano.

* Log obligatorio en `rag_search_logs` con intent, query y resultados.

**Políticas por plan**

* **Start:** similitud básica \+ min\_score, sin rewriter.

* **Pro:** similitud \+ re-ranking \+ query\_rewriter.

* **Max:** híbrido vector+BM25 \+ filtros avanzados \+ query\_rewriter.

---

## **6.9 Multilenguaje**

* **Detección:** se hace en dos niveles:

  * Conversación → detectar idioma del usuario (ej. con fastText/langdetect).

  * Chunk → cada bloque normalizado (6.4) guarda `lang`.

* **Respuesta:** el LLM debe contestar en el idioma detectado en la conversación.

* **Indexación:** documentos multilingües se almacenan en la misma tabla `rag_chunks`, con `lang` a nivel chunk.

* **Consulta:** si el usuario consulta en ES pero hay chunks EN, se incluyen ambos idiomas en el contexto.

* **Traducción/fallback:** si embeddings no son robustos (ej. MiniLM), habilitar re-ranking con traducción ligera (`translate_query`) antes de vectorizar.

* **Métricas:** medir recall@k y precision@k por idioma para detectar sesgos.

**Políticas por plan**

* **Start:** soporta un idioma principal (configurable en workspace).

* **Pro:** soporte multilingüe ES/EN con embeddings multilingües.

* **Max:** soporte extendido (ES/EN/PT/otros) \+ fallback de traducción automática y métricas específicas por idioma.

---

## **6.10 Versionado y actualización**

* Cada nueva carga de un mismo documento → incrementa `documents.version` y genera nuevos `rag_chunks`.

* **Active set:** por defecto, el retriever solo consulta chunks con `is_active=true`.

* **Versiones viejas:** se marcan como `is_active=false` y pueden archivarse en MinIO/Parquet (ver Cap. 3.3 Retención).

* **Reindexación:**

  * Por documento → borra chunks activos de esa versión y regenera.

  * Por workspace → reindexa todos los documentos (ej. cambio de embedding\_model).

* **Rollback:** si la ingesta falla, la nueva versión no se marca como activa y se conserva la anterior.

* **Logging:** `ingest_jobs.stats_json` debe registrar `{old_version, new_version, chunks_generated, active_flag, duration_ms}`.

* **Shadow index:** opcional en Plan Max para auditoría; conserva todas las versiones aunque estén inactivas.

**Políticas por plan**

* **Start:** siempre mantiene solo la última versión activa.

* **Pro:** permite conservar N versiones (ej. últimas 3).

* **Max:** habilita shadow index completo \+ rollback manual desde dashboard.

---

## **6.11 Límites y validaciones de archivos**

**Tamaño:** máximo 20 MB por archivo (Start), 30 MB (Pro), 50 MB (Max).

**Páginas:** máximo 500 por PDF.

**Tipos soportados:** pdf, docx, xlsx, csv, html, txt. OCR en imágenes solo habilitado en Plan Max (opt-in).

**Naming:** normalizar nombre a UTF-8, calcular `file_hash_sha256` para idempotencia.

**Validación en ingest:**

* Paso previo a parser: si el archivo excede límite → marcar ingest\_job.status=`failed`, error\_message=`file_too_large|too_many_pages|unsupported_type`.

* Core API devuelve 400 con detalle al dashboard.  
  **Logging en stats\_json:**  
  { "validated": true, "file\_size\_mb": 18.3, "page\_count": 220, "hash": "abcd123...", "validation\_status": "ok" }

**Seguridad:** bloquear tipos no listados; sanitizar HTML y rechazar scripts embebidos.

---

## **6.12 Manejo de errores**

**Parser error**:

* Acción: `ingest_job.status=failed`, guardar `error_message="parser_failed"`.  
* Emitir evento → `F-Alerts` \+ registrar en `audit_logs(action="parser_failed")`.  
  **Embeddings timeout**:  
* 1 reintento (Start), hasta 2 (Pro/Max).

* Si vuelve a fallar → marcar `failed`, `error_message="embedding_failed"`.

* Fallback en Max: usar modelo alternativo si está habilitado (`feature_flag`).  
  **Persistencia DB**:  
* Inserts en bulk transaccional.

* Si falla → rollback completo, `status=failed`, `error_message="db_failed"`.  
  **Consistencia**:  
* No marcar documento como activo si la ingesta no completó correctamente.

* Evitar queries RAG en documentos con `status != success`.

  **Propagación a DLQ**:  
* Todo error manda payload completo a `F-DeadLetter` con `dlq_reason`.  
  **Logging en stats\_json**:

{ "status":"failed", "error\_type":"parser\_failed", "retries":1, "duration\_ms":3500 }

**Políticas por plan**

* **Start:** 1 reintento en embeddings, fallback deshabilitado.

* **Pro:** 2 reintentos en embeddings, log extendido.

* **Max:** reintentos extendidos \+ fallback a modelo alternativo si enabled.

---

## **6.13 Interfaces y contratos (resumen)**

### **6.13.1 Ingest start (RAG API)**

**`POST /ingest/start`**

{  
   "workspace\_id": "ws-uuid",  
   "document\_id": "doc-uuid",  
   "storage\_url": "s3://pulpo/docs/d1.pdf",  
   "source\_type": "pdf",  
   "mime\_type": "application/pdf",  
   "embedding\_model": "text-embedding-3-small"  
}

**200 OK**

{ "ingest\_job\_id": "job-uuid", "status": "pending" }

Headers obligatorios:

* `x-request-id` (uuid v4)  
* `x-workspace-id`

### 

### **6.13.2  Ingest status**

**`GET /ingest/{job_id}/status`**

{  
   "workspace\_id": "ws-uuid",  
   "document\_id": "doc-uuid",  
   "storage\_url": "s3://pulpo/docs/d1.pdf",  
   "source\_type": "pdf",  
   "mime\_type": "application/pdf",  
   "embedding\_model": "text-embedding-3-small"  
}

**200 OK**

{ "ingest\_job\_id": "job-uuid", "status": "pending" }

## **6.13.3 Bulk insert chunks (interno**

**`POST /chunks/bulk-insert`**

{

   "workspace\_id": "ws-uuid",

   "document\_id": "doc-uuid",

   "chunks": \[

       { "chunk\_index": 0, "text": "Pizza muzzarella...", "embedding": \[0.1,0.2,...\] }

   \]

}

**200 OK**

{ "inserted": 164 }

## **6.13.4 Search**

**`POST /search`**

{ "workspace\_id": "ws-uuid", "query": "precio pizza muzzarella", "top\_k": 6 }

**200 OK**

{

   "results": \[

       {

           "chunk\_id": "c-uuid",

           "doc\_id": "d-uuid",

           "chunk\_index": 12,

           "score": 0.82,

           "meta": { "title": "Menu 2025", "page": 2, "heading": "Pizzas" },

           "text": "Pizza muzzarella ... $5000"

       }

   \]

}

**Políticas por plan**

* **Start:** `/ingest/start`, `/search`.

* **Pro:** agrega `/ingest/status`.

* **Max:** habilita `/chunks/bulk-insert` y `/reindex`.

**Auditoría:** cada request se loguea en `audit_logs` con `action`, `target_id` y `request_id`.

## **6.14 Provider Interface (VectorStore)**

Contrato en TypeScript:

interface VectorStore {  
   initWorkspace(wsId: string, dim: number): Promise\<void\>;  
   upsertChunks(wsId: string, chunks: ChunkInput\[\]): Promise\<void\>;  
   query(wsId: string, queryEmbedding: number\[\], k: number): Promise\<SearchHit\[\]\>;  
   deleteByDocument(wsId: string, documentId: string): Promise\<void\>;  
   stats(wsId: string): Promise\<{ chunks: number, dim: number }\>;  
}

**Notas:**

* `initWorkspace`: crea tabla/colección si no existe, parametrizada por dimensión.  
* `dim`: dimensión activa de embeddings; debe ser consistente en cada workspace.  
* `upsertChunks`: idempotente (dedupe por `(doc_id, chunk_index)`).  
* `query`: soporta filtros opcionales (ej. idioma, fecha, vertical).  
* `stats`: devuelve total de chunks y dimensión activa.

**Implementaciones:**

* **pgvector (default)**

  * SQL directo (`INSERT … ON CONFLICT …`).  
  * Índice IVFFlat/HNSW por workspace.

* **Qdrant**

  * gRPC/HTTP.  
  * Collections \= workspace\_id, con payloads para metadata.

* **LEANN**

  * Feature flag, solo en Max.  
  * Evaluar footprint y recall antes de habilitar globalmente.

**Políticas por plan:**

* **Start:** solo pgvector.  
  **Pro:** puede elegir entre pgvector y Qdrant (feature flag).  
* **Max:** habilita Qdrant/LEANN y soporta migración de embeddings entre proveedores.

**Errores:**

* Si proveedor falla → log en `audit_logs(action="vectorstore_failed")` y enviar a F-DeadLetter.

## **6.15 Métricas específicas de RAG**

* **Ingest performance**

  * Tiempo promedio por 100 páginas.  
  * Tokens totales procesados.  
  * Costo embeddings (USD).  
  * Guardar en `ingest_jobs.stats_json`.

* **Calidad de recuperación**

  * Recall@k (golden set).  
  * Precision@k (relevancia de top\_k).  
    MRR (Mean Reciprocal Rank).  
  * Hit-rate online: % respuestas con ≥1 chunk score ≥ min\_score.  
  * Log en `rag_search_logs.results_json`.

* **Contexto y costo**

  * Longitud media de contexto (tokens por respuesta).  
  * Tokens out del LLM (costo monetario).  
  * Distribución por plan y vertical.

* **Errores y robustez**

  * Tasa de parser\_failed / embedding\_failed.  
  * Outliers de latencia (p95/p99).

**Políticas por plan**

* **Start:** métricas básicas (ingest performance, hit-rate).  
* **Pro:** añade Recall@k y Precision@k.  
* **Max:** todas \+ MRR \+ breakdown por idioma/vertical.

**Alertas**

* Si `hit_rate < 0.7` en ventana de 1h → enviar a F-Alerts.  
* Si `costo_embeddings_usd` \> umbral mensual → alerta a Owner del workspace.

---

## **6.16 Seguridad y privacidad**

**Minimización de datos**

* No almacenar PII innecesaria dentro de `rag_chunks.text`.  
* Si el documento contiene PII → marcar `documentos.sensitivity="pii"`.

  **Controles de acceso**  
* Documentos sensibles solo accesibles a roles `owner|admin`.  
* Aplicar RLS en todas las tablas (`workspace_id` obligatorio en queries).

  **Cifrado y transporte**  
* Documentos originales y JSON normalizados en MinIO/S3 cifrados con AES256.  
* Acceso vía TLS obligatorio (Dev/Staging/Prod).

  **HTML y fuentes externas**  
* Sanitizar HTML (remover scripts, iframes).  
* Bloquear ejecución de recursos externos en la ingesta.

  **Políticas por plan**  
* **Start:** seguridad base (RLS \+ TLS).  
* **Pro:** incluye auditoría extendida en `audit_logs`.  
* **Max:** compliance reforzado (PII tagging obligatorio, retención configurable, auditorías externas).

  **Auditoría**  
* Toda acción sensible (upload, reindex, delete) debe quedar en `audit_logs` con `user_id`, `target_id`, `action`, `request_id`.

---

## **6.17 Defaults recomendados (configurables)**

{  
   "rag": {  
       "chunk\_size": 450,  
       "overlap": 0.12,  
       "top\_k": 6,  
       "min\_score": 0.60,  
       "embedding\_model": "text-embedding-3-small",  
       "max\_tokens\_out": {  
           "start": 250,  
           "pro": 350,  
           "max": 500  
       },  
       "query\_rewrite": {  
           "start": false,  
           "pro": true,  
           "max": true  
       },  
       "max\_file\_mb": {  
           "start": 20,  
           "pro": 30,  
           "max": 50  
       },  
       "max\_pdf\_pages": 500,  
       "ocr\_enabled": {  
           "start": false,  
           "pro": false,  
           "max": true  
       }  
   }  
}

**Notas**

* Los valores se copian a `workspace_configs.policy_json` al crear workspace.  
* El Owner puede sobreescribir (si su plan lo permite).  
* Logs: registrar `defaults_applied=true` en `audit_logs` cuando se inicializa un workspace.

## **6.18 Gestión de Contexto (Pruning, Summarization, Offloading)**

**Objetivo**: controlar costo/latencia y mejorar precisión reduciendo ruido en prompts.

* **Pruning**

  * Mantener N últimos turnos relevantes (configurable).  
  * N por plan: Start=5, Pro=15, Max=30.  
  * Implementación: cortar historial en `messages` antes de formar prompt.

* **Summarization**

  * Generar resúmenes temáticos (ej. pedidos, pagos, preferencias).  
  * Guardar en tabla `conversation_summaries` con `workspace_id`, `conversation_id`, `summary_text`, `created_at`.

  * Usar resúmenes en lugar de historial completo al formar prompt.

* **Offloading**

  * Catálogos extensos (ej. menú, propiedades, stock) se indexan en RAG.  
  * El LLM no recibe todo en prompt, sino que consulta chunks on-demand.

* **Tool Loadout explícito**

  * Declarar herramientas disponibles al LLM para evitar alucinaciones.  
  * Guardar en `workspace_configs.policy_json`.

* **KV Cache (decoders)**

  * Cachear atenciones del LLM por conversación.  
  * Política LRU de eviction.  
  * Métricas de uso → F-Usage (`tokens_saved`, `cache_hits`).

* **Medición**

  * TTFR, costo/token y recall comparados antes/después de aplicar pruning/summarization.  
  * Logs en `audit_logs(action="context_policy_applied")`.

**Políticas por plan**

* **Start:** pruning básico (5 turnos).  
* **Pro:** pruning \+ summarization.  
* **Max:** pruning \+ summarization \+ KV cache \+ offloading avanzado.

# **7\. Autenticación, Autorización y Roles**

## **7.1 Objetivo**

Garantizar acceso seguro **multi-tenant** y trazable, con controles por rol y por workspace, y contratos claros para integraciones. Objetivos medibles:  
 • **Aislamiento por workspace:** toda operación requiere `X-Workspace-Id` válido y RLS activo en DB.  
 • **Autenticación fuerte:** JWT RS256 con JWKS público; **2FA TOTP obligatorio** para `owner` y `superadmin`.  
 • **Autorización granular:** verificación de **rol** y **scope** por endpoint; denegación por defecto.  
 • **Integraciones seguras:** API keys **con scopes** (y expiración opcional) aisladas por workspace.  
 • **Auditoría completa:** registro de sesiones, cambios de configuración, rotación de llaves y handoff humano.  
 • **Privacidad por diseño:** PII fuera de logs de aplicación; solo IDs y metadatos mínimos.

Criterios de aceptación

1. Ningún endpoint protegido responde sin JWT válido **y** membresía en `X-Workspace-Id`.  
2. Usuarios `owner`/`superadmin` no pueden autenticarse sin 2FA habilitado.  
3. Una API key sin scope requerido debe recibir `403 scope_denied`.  
4. Toda acción sensible queda en `audit_logs` con `user_id|apikey_id`, `action`, `target`, `request_id`.  
5. Tests de RLS confirman que registros de otro workspace no son accesibles (JOINs y FKs workspace-consistentes).

Notas de implementación  
 • Frontera de confianza: **Frontend → Gateway (valida JWT/JWKS) → Servicios (revalidan claims y rol/scope)**.  
 • Propagación de contexto: `X-Workspace-Id` se valida y se ejecuta `SELECT pulpo.set_ws_context('<WS_ID>');` antes de acceder a datos.  
 • Denegar por defecto: endpoints sin `scope` explícito devuelven `403`.

---

## **7.2 Arquitectura de identidad**

* **Issuer auth:** Core API emite JWT RS256 con claims de usuario, memberships y default\_ws; JWKS público para validación.

* **Frontend (Next.js):** usa Auth.js con email+password, Google OAuth y 2FA TOTP; guarda JWT en cookie httpOnly/secure.

* **API Gateway:** valida JWT contra JWKS, renueva por refresh token cuando expira, y propaga `Authorization: Bearer`, `X-Workspace-Id` y `request_id`.

* **Servicios internos:** middleware de autorización por rol/scope; todas las rutas protegidas deniegan acceso por defecto si no hay claim válido.

* **Integraciones (n8n, externos):** se autentican con API keys por workspace (no sesiones de usuario), con scopes explícitos.

* **Contexto multi-tenant:** cada request ejecuta `SET LOCAL app.workspace_id = '<WS_ID>'` para habilitar RLS en DB y trazabilidad consistente.

---

## **7.3 Flujos de login**

### **7.3.1 Credenciales con 2FA**

1. Usuario envía email y password.

2. Si credenciales ok y **2FA habilitado** → API responde totp\_required=true.

3. Usuario envía TOTP.

4. Core emite JWT con exp. 12 h.

5. Front guarda token en **cookie httpOnly secure** o memoria con fetch que adjunta Authorization.

**Endpoints**

* POST /auth/login → { email, password }

  * 200 { jwt } o 401 { totp\_required: true, tmp\_token }

* POST /auth/totp/verify → { tmp\_token, code } → 200 { jwt }

* POST /auth/logout → 204

### **7.3.2 Google OAuth**

* Redirige a /auth/oauth/google y vuelve con callback → Core emite JWT.

* Si es **primera vez**, requiere **aceptar invitación** o **crear workspace** según flujo.

### **7.3.3 Registro, invitaciones y recuperación**

* POST /auth/register → crea usuario y **workspace** inicial (plan trial).  
* POST /workspaces/{id}/invite (rol requerido: owner o admin) → envía email con **invite\_token**.  
* POST /auth/accept-invite → une usuario existente o crea nuevo.  
* POST /auth/password/reset-request → email con link.  
* POST /auth/password/reset-confirm → setea password.

**7.3.4 Refresh tokens (rotativos)**

**Objetivo**: extender sesiones sin re-logueo, manteniendo seguridad ante robo de tokens mediante rotación y detección de reuso.

POST /auth/token/refresh

{ "refresh\_token": "opaque\_base64" }

200 OK

{ "jwt": "\<access\_jwt\_rs256\>", "refresh\_token": "\<nuevo\_refresh\_opaque\>" }

**Reglas**:

* Access JWT expira a las 12 h. Refresh expira a los 7 días (deslizable: al refrescar se emite uno nuevo y se invalida el anterior).  
* Opaque (256 bits) almacenado con hash Argon2id y device metadata (ua, ip).  
* Rotación obligatoria: si se presenta un refresh ya invalidado → “reuse detected”: revocar toda la familia y forzar re-login.  
* Máximo 5 sesiones activas por usuario (rotación LRU). Password reset o deshabilitar 2FA → revoca todas las sesiones.

**Gestión de sesiones**  
 GET /auth/sessions → lista de sesiones (dispositivo, ip, last\_used\_at, expires\_at).  
 DELETE /auth/sessions/{id} → revoca esa sesión (logout remoto).

**Seguridad**  
 • Hash en DB (nunca almacenar el token plano).  
 • family\_id por refresh para revocar en cascada.  
 • Rate limit al refresh: p.ej. 10/min por user.  
 • Auditoría: audit\_logs(action="session\_refresh"|"session\_revoke"|"refresh\_reuse\_detected").

7.3.5 Políticas adicionales de login

* **Intentos fallidos:** máximo 5 intentos de password o TOTP en 10 minutos por usuario. Superado el límite → bloqueo temporal de 15 min (`429 rate_limited`). Todos los intentos (éxito o fallo) se registran en `audit_logs` con `user_id/email`, `ip`, `ua`.

* **Invitaciones:** los `invite_token` expiran a las 48 h (configurable). Creación y aceptación se registran en `audit_logs`.

* **Recuperación de contraseña:** máximo 3 requests de reset por hora por email; exceso → `429 rate_limited`.

* **Google OAuth:** el parámetro `state` se valida para prevenir CSRF. Auditoría de primer login (acción `oauth_login`).

* **Gestión de sesiones:** `GET /auth/sessions` devuelve además `ua`, `ip` y `device_label` (opcional, si se guardó en login).

---

## **7.4 2FA TOTP**

**Setup**

POST /auth/totp/setup → { otpauth\_url, secret\_base32 }

* El `secret_base32` se **cifra en reposo** (KMS/HSM) y jamás se registra en logs.  
* El QR incluye issuer=`Pulpo` y account=`{email}`.

**Enable**

POST /auth/totp/enable → { code }

* Valida TOTP con tolerancia ±1 intervalo (30s).  
* Rate limit: 5 intentos/10 min por usuario; exceder → `429 rate_limited`.  
* Marca `user.totp_enabled=true` y audita `totp_enabled`.

**Recovery codes**

 POST /auth/totp/recovery/rotate → devuelve 10 códigos **de un solo uso**.

* Se almacenan **hasheados (Argon2id)** y se consumen de forma **atómica**.  
* Auditoría: `recovery_rotated`.  
* Al usar un recovery code: endpoint de login acepta `{ email, recovery_code }` → invalida ese code, emite JWT y exige **re-setup TOTP** al ingresar.

**Step-up auth (acciones sensibles)**

 Requiere TOTP reciente (≤5 min) o recovery code válido para:

* Rotar/crear **API keys**, cambiar **plan/billing**, borrar documentos o ejecutar **reindex** global.  
* Endpoint estándar: si falta verificación fuerte → `401 totp_required`.

**Política**

* 2FA **obligatoria** para `owner` y `superadmin`; sugerida para `admin`.  
* Reset 2FA: solo con **recovery code** o por `superadmin` con doble control (aprobación \+ auditoría `totp_reset_forced`).  
* Deshabilitar 2FA exige TOTP válido en la misma sesión (`totp_disable_confirmed`).

**Auditoría**  
 Se registran: `totp_setup`, `totp_enabled`, `totp_disable_requested`, `totp_disabled`, `recovery_rotated`, `recovery_used`, `totp_reset_forced`, con `user_id`, `ip`, `ua`, `request_id`.

---

## **7.5 JWT y claims**

**Formato (claims principales)**

* **Header:** `{ "alg": "RS256", "kid": "<key_id>", "typ": "JWT" }`.  
* Mantener al menos 2 claves activas; retirar la anterior tras 48 h.

{  
   "iss": "pulpo.auth",  
   "aud": "pulpo.api",  
   "sub": "user-uuid",  
   "email": "user@dominio.com",  
   "superadmin": false,  
   "memberships": \[  
       { "workspace\_id": "ws-uuid", "role": "owner" },  
       { "workspace\_id": "ws-uuid-2", "role": "viewer" }  
   \],  
   "default\_ws": "ws-uuid",  
   "jti": "uuid",  
   "iat": 1693560000,  
   "nbf": 1693560000,  
   "exp": 1693603200  
}

**Claims opcionales (impersonación)**

* `impersonated: true`, `actor_sub: "<admin-uuid>"`, `reason: "soporte|debug|auditoría"`.

**Políticas**

* **Audience**: `aud` debe coincidir con el servicio destino (gateway o microservicio).  
* **Default workspace**: `default_ws` **debe existir en `memberships`**; si no, `401 invalid_token`.  
* **PII mínima**: no incluir datos sensibles en claims (solo IDs/roles).  
* **Duración**: access **12 h**; refresh **rotativo 7 días** (ver 7.3.4).  
* **Reloj**: tolerancia **±60 s** en `iat/nbf/exp`.  
* **Revocación puntual**: mantener **blacklist de `jti`** comprometidos (memoria/Redis) hasta `exp`.  
* **Tamaño**: payload del JWT ≤ **2 KB**.

**Validación (Gateway/Servicios)**

1. Resolver `kid` → JWKS (cache **10 min**; si falla, usar cache local y alertar).  
2. Verificar firma RS256 \+ `iss/aud/nbf/exp`.  
3. Verificar `jti` no listado como revocado.  
4. Verificar `default_ws ∈ memberships`.  
5. Autorizar por **rol**/**scope** (deny-by-default).  
6. Propagar `request_id` y `X-Workspace-Id`.

**Publicación de JWKS**

* `GET /auth/.well-known/jwks.json` con rotación planificada (key add/retire auditada).

**Errores estándar**

* `401 invalid_token | expired_token | nbf_violation | aud_mismatch | jti_revoked`  
* `403 missing_membership | insufficient_role`

---

## **7.6 Selección de workspace y contexto**

**Entrada y prioridad de fuentes**

1. `X-Workspace-Id` (header) — requerido para usuarios finales.  
2. `workspace_id` embebido en **API key** (integraciones/n8n).  
3. **Impersonación** (superadmin): `X-Workspace-Id` \+ claims `impersonated=true, actor_sub`.  
    Regla: si hay conflicto, **rechazar** con `422 validation_error (workspace_conflict)`.

**Validación de membresía**

* Usuarios con JWT: `default_ws` debe existir en `memberships`.  
  Para cada request protegido: verificar que `X-Workspace-Id ∈ memberships`. Si no, `403 missing_membership`.  
* Superadmin: puede operar en cualquier workspace **solo** si `impersonated=true` y se registra auditoría.

**Enforcement de contexto (DB/RLS)**

* Antes de cualquier consulta a Postgres:  
  SELECT pulpo.*set\_ws\_context*(:workspace\_id);  
    
  * Rechazar la operación si no se ejecutó (`401 invalid_context`).  
  * Políticas RLS filtran por `current_setting('app.workspace_id')`.

* **Consistencia de FKs** (obligatoria):

  * Ej.: `messages (workspace_id, conversation_id) → conversations (workspace_id, id)`  
  * Cualquier JOIN debe incluir `AND m.workspace_id = c.workspace_id`.

**Propagación end-to-end**

* REST: Gateway → Servicios → DB: propagar `X-Workspace-Id` \+ `request_id`.  
* n8n/Workflows: todos los microflujos deben incluir `workspace_id` en el **payload**.  
* Redis Streams/Outbox: cada evento debe llevar `{workspace_id, request_id, channel_id, conversation_id}`.  
* RAG/Action API: contratos exigen `workspace_id` y lo validan antes de ejecutar.

**Service accounts y API keys**

* API key está **scoped a un workspace**; al autenticarse, el middleware inyecta `X-Workspace-Id` desde la key.  
* Jobs batch (p.ej. F-Usage) usan **service account** con `workspace_id` explícito por iteración; queda auditado el scope.

**Auditoría**

* Registrar `context_set` con `{user_id|apikey_id, workspace_id, request_id}` cuando se establece contexto.  
* Impersonación: `impersonate_start/impersonate_end` con `actor_sub`, `target_workspace_id`, `reason`.

**Errores estándar**

* `422 validation_error (missing_workspace_header | workspace_conflict)`  
* `403 missing_membership | insufficient_role`  
* `401 invalid_context` (no se ejecutó `set_ws_context`)

**Notas operativas**

* **Deny by default** si falta `X-Workspace-Id` en endpoints que lo requieran.  
* Para Webhooks externos (WhatsApp BSP) el **Channel Resolver (F-00)** determina `workspace_id` desde `business_phone_id` y lo propaga al resto.


---

## **7.7 Roles y permisos**

Política general

* **Menor privilegio** y **deny-by-default**: si un endpoint no declara permiso, se **deniega**.  
* **Orden de evaluación**: primero `scope` (API key/token), luego `membership` en `X-Workspace-Id`, luego **rol**.  
* **Acciones sensibles** requieren **step-up** (TOTP reciente o recovery) según 7.4.  
* Todos los cambios de miembros/roles se registran en `audit_logs` (ver 7.13).

### **7.7.1 Rol global de plataforma**

* **superadmin**: administración total de la **plataforma** (no aparece para clientes).

  * Crear y eliminar workspaces.

  * Ver métricas globales, diagnosticar.

  * Impersonar usuario de un workspace con consentimiento y **auditoría**.  
  * Impersonación siempre con `impersonated=true`, `actor_sub` y `reason` (ver 7.5).

  * Prohibido usar impersonación para operaciones de billing sin step-up (ver 7.4).  
    

### **7.7.2 Roles por workspace**

| Capability | owner | admin | editor | viewer |
| ----- | ----- | ----- | ----- | ----- |
| Ver conversaciones | ✓ | ✓ | ✓ | ✓ |
| Responder manual y handoff | ✓ | ✓ | ✓ | ✗ |
| Configurar prompts basic | ✓ | ✓ | ✓ | ✗ |
| Subir documentos RAG | ✓ | ✓ | ✓ | ✗ |
| Ejecutar reindex | ✓ | ✓ | ✓ | ✗ |
| Ver métricas y usage | ✓ | ✓ | ✓ | ✓ |
| Gestionar miembros | ✓ | ✓ | ✗ | ✗ |
| Cambiar plan y billing | ✓ | ✗ | ✗ | ✗ |
| Gestionar API keys | ✓ | ✓ | ✗ | ✗ |
| Configurar canales | ✓ | ✓ | ✗ | ✗ |
| Ver audit logs | ✓ | ✓ | ✗ | ✗ |
| Exportar datos (conversaciones/BI) | ✓ | ✓ | ✗ |  ✗ |
| Descargar originales de documentos | ✓ | ✓ | ✓ | ✗ |

Nota: “Descargar originales” refiere a los archivos fuente en MinIO; si `documents.sensitivity="pii"`, limitar a **owner/admin**.

### **7.7.3 Invitaciones y cambios de rol**

* ### **Rol por defecto en invitaciones**: `viewer`, a menos que el **owner/admin** especifique otro. 

* **Ascensos** a `owner`: solo puede hacerlo **otro owner** del workspace.

* **Degradaciones o expulsiones** de miembros con rol ≥admin: solo `owner`.

* Auditoría obligatoria: `member_invited`, `member_role_changed`, `member_removed` con `{by_user_id, target_user_id, old_role, new_role}`.

### **7.7.4 Service accounts (API keys)**

* Las **API keys** actúan como **service accounts** scopeadas al workspace (ver 7.8).

* Las capacidades se otorgan por **scopes**, no por roles humanos.

* Recomendación: crear keys específicas por microflujo (p. ej. `rag.ingest`, `actions.execute`) con **expiración** cuando aplique.

## **7.8 API Keys por workspace**

**Modelo y política**

* Las API keys se generan **opacas**, se muestran **una sola vez** y se almacenan **hasheadas (Argon2id)**.  
* Cada key está **scopeada a un workspace** y opera sin rol humano (service account).  
* Campos clave: `name`, `scopes[]`, `expires_at` (opcional), `revoked_at`, `last_used_at`, `ip_allowlist[]` (CIDR), `description` (opcional).  
* **Deny-by-default**: sin scope requerido ⇒ `403 scope_denied`.  
* Auditoría obligatoria en `audit_logs`: `apikey_created`, `apikey_rotated`, `apikey_revoked`, `apikey_revoked_all`.

**Scopes**

* Atómicos: `messages.read|messages.write`, `rag.ingest|rag.search`, `actions.execute`, `config.read|config.write`, `usage.read`, `audit.read`.  
* Comodín controlado (opcional por superadmin): `rag.*`, `messages.*`.  
* Recomendación: **una key por microflujo** con el mínimo de scopes.

**Expiración y seguridad**

* `expires_at` configurable (p.ej. 30/90 días). Si expira ⇒ `401 invalid_api_key`.  
* `ip_allowlist[]` (CIDR) opcional: si set, solo se acepta desde esas IPs.  
* **Rate limit por key** y por scope (sliding window en Redis).  
* `last_used_at` se actualiza en cada uso; rotación recomendada si inactivo \>90 días.

**Endpoints**

* **POST** `/workspaces/{id}/apikeys` → `{ name, scopes[], expires_at?, ip_allowlist?, description? }`  
   **201** `{ id, name, masked_key_prefix, created_at, expires_at }` \+ **clave completa solo en esta respuesta**  
* **GET** `/workspaces/{id}/apikeys` → lista `{ id, name, scopes, created_at, expires_at, revoked_at, last_used_at, ip_allowlist }` (sin la clave)  
* **DELETE** `/workspaces/{id}/apikeys/{key_id}` → **204** (revoca)  
* **POST** `/workspaces/{id}/apikeys:revoke-all` → **204** (revocación masiva por compromiso)

**Validación en middleware**

1. Localizar key por **hash**.  
2. Verificar `revoked_at IS NULL` y `now() < expires_at` si existe.  
3. Verificar `ip_allowlist` si aplica.  
4. Verificar `scope` requerido por endpoint (deny-by-default).  
5. Inyectar `X-Workspace-Id` del registro de la key y propagar `request_id`.  
6. Actualizar `last_used_at` (debounce 60s para evitar hot writes).

---

## **7.9 Autorización en servicios**

**Política y orden de evaluación**

1. **Scope** (token/API key) → si falta el requerido del endpoint: `403 scope_denied`.  
2. **Membership** en `X-Workspace-Id` (solo para usuarios con JWT) → si no pertenece: `403 missing_membership`.  
3. **Rol** → si el rol no alcanza: `403 insufficient_role`.  
4. **Step-up** (si aplica) → si falta TOTP reciente: `401 totp_required` (ver 7.4).

**Fuentes y contexto**

* Usuarios (JWT): `X-Workspace-Id` proviene del header; validar `default_ws ∈ memberships` y pertenencia al workspace.  
* API keys / service accounts: el **workspace\_id** se inyecta desde el registro de la key; **no** se usa membership ni rol humano (solo scopes).  
* Siempre ejecutar `SELECT pulpo.set_ws_context(:workspace_id);` antes de acceder a DB (RLS).

**Declaración por endpoint (ejemplos)**

`POST /messages/send` → scopes: `messages.write`, rol: `editor+`.

`POST /rag/ingest` → scopes: `rag.ingest`, rol: `editor+`.

`GET /audit/logs` → scopes: `audit.read`, rol: `admin+`.

`POST /apikeys` → scopes: `config.write`, step-up requerido (ver 7.4).

`DELETE /documents/{id}` → scopes: `config.write`, rol: `admin+`, step-up.

**Decorators / Guards (NestJS)**

* `@RequiresScope('rag.search')`, `@RequiresRole('editor')`, `@WorkspaceGuard()` (valida header/key y setea contexto), `@StepUpGuard()` (cuando corresponda).  
*  Deny-by-default: endpoints sin decorator explícito se rechazan.

**Errores estándar**

* 401: `invalid_token | totp_required`  
*  403: `scope_denied | missing_membership | insufficient_role`  
* 422: `validation_error (missing_workspace_header | workspace_conflict)`  
* Siempre loguear con `request_id`, `user_id|apikey_id`, `workspace_id`, `endpoint`, `decision`.

**Trazabilidad**

* Adjuntar `request_id` en todos los servicios; auditar autorizaciones denegadas con motivo y contexto mínimo.

---

## **7.10 Rate limiting y anti-abuso**

**Objetivo**  
 Proteger disponibilidad y costos aplicando límites por workspace, contacto y API key; detectar abuso y mitigar sin perder mensajes legítimos.

**Algoritmo y almacenamiento**

* Redis **sliding window** \+ **token bucket** híbrido.

* Claves:

  * `rl:ws:{workspace_id}:{scope}`  
  * `rl:contact:{workspace_id}:{e164}`  
  * `rl:apikey:{workspace_id}:{key_id}:{scope}`

* Cada entrada guarda `tokens`, `window_start`, `last_seen_ip/ua`. TTL \= ventana.

**Límites por defecto (overridables por plan)**

* Workspace (mensajes totales): 60/min, 1000/h.  
* Contacto (por número E164): 5/10s, 60/5min.  
* API key: 120/min por key; adicional por **scope** (p.ej. `rag.search`: 60/min).  
* WhatsApp BSP inbound: aceptar y **procesar async**; si excede, responder 200 y enrutar a cola con **throttle** (no 429 al BSP).

**Política por plan**

* **Start**: 60/min ws, 600/h; `rag.search` 30/min.  
* **Pro**: 120/min ws, 2k/h; `rag.search` 60/min.  
* **Max**: 240/min ws, 5k/h; `rag.search` 120/min.  
   Se configuran en `plans.policy_json.rate_limits` y pueden sobrescribirse en `workspace_configs`.

**Headers y respuestas**

* En endpoints rate-limited:

  * `HTTP 429 Too Many Requests`  
  * `Retry-After: <segundos>`  
  * `X-RateLimit-Limit: <limit>`  
  * `X-RateLimit-Remaining: <remaining>`  
  * `X-RateLimit-Reset: <epoch_segundos>`

* Para WhatsApp webhooks: **nunca** 429 (Meta reintenta agresivo); usar DLQ/throttle interno.

**Anti-abuso (detecciones y acciones)**

* **Replay de webhooks**: dedupe por `(workspace_id, wa_message_id)` (único). Acción: descartar y log `replay_detected`.

* **Loop eco** (bot↔bot): si `direction=outbound` seguido de inbound idéntico \>3 veces/60s ⇒ pausar auto-reply conversación y alertar.

* **Burst anómalo**: si tráfico ↑ 10× del p95 horario ⇒ activar “modo protección” (reduce límites 50% por 5 min) y alerta.  
* **Flood por contacto**: si contacto supera 3× el límite 3 veces seguidas ⇒ cuarentena 15 min (solo respuestas informativas).  
* **Firma inválida webhook** (7.11): si tasa \>1% en 5 min ⇒ bloquear IP por 15 min.  
* **IP deny/allow lists** para API keys (`ip_allowlist` en 7.8).

**Telemetría y auditoría**

* Métricas: `rate_limit_hits{scope}`, `429_count`, `mode_protection_active`, p95/p99 por endpoint.  
* Auditoría (`audit_logs`): `rate_limited`, `contact_quarantined`, `loop_autoreply_paused`, `ip_blocked`, con `workspace_id`, `scope`, `counts`, `window`.

**Configuración (defaults sugeridos)**

**{**

   **"rate\_limits": {**

       **"workspace": { "per\_min": 60, "per\_hour": 1000 },**

       **"contact":   { "per\_10s": 5, "per\_5min": 60 },**

       **"apikey":    { "per\_min": 120 },**

       **"scopes": {**

           **"rag.search": { "per\_min": 60 },**

           **"rag.ingest": { "per\_min": 10 },**

           **"messages.write": { "per\_min": 120 }**

       **},**

       **"whatsapp\_webhook": { "soft\_throttle": true }  // nunca 429**

   **}**

**}**

**Orden de evaluación**

1. `apikey` (si aplica) → 429 si excede.  
2. `workspace` → 429 si excede (excepto webhook BSP: throttle interno).  
3. `contact` (si hay E164) → 429/cuaren.

4. Registrar métricas y headers.

**Errores estándar**

* 429 `rate_limited` (con `Retry-After`).  
* 200 (webhook) \+ evento `soft_throttle_enqueued`.  
* 403 `ip_not_allowed` (si no cumple allowlist).

---

## **7.11 Webhooks y verificación de origen**

**Objetivo**  
 Aceptar solo webhooks auténticos, procesarlos sin pérdida y evitar duplicados o replays.

**Registro del endpoint**

* `GET /webhooks/whatsapp`: responder al **challenge** con `hub.challenge` verificando `hub.verify_token` (config workspace/canal).  
* `POST /webhooks/whatsapp`: recibir eventos firmados.

**Verificación de firma (HMAC-SHA256)**

* Header: `X-Hub-Signature-256: sha256=HEX`.  
* Canonización: usar **el body crudo exacto** (bytes) tal como lo envía el BSP; **no** reserializar JSON.  
* Clave: `WHATSAPP_APP_SECRET` del **channel** (no global).  
* Cálculo: `hex(hmac_sha256(secret, raw_body))` y comparar en **tiempo constante**.  
* Si falta/ no coincide → **403 invalid\_signature** (auditar `signature_failed`).

**Protecciones anti-replay**

* `X-Pulpo-Received-At` (servidor) y `entry[0].changes[0].value.messaging_product`/`messages[0].timestamp`.  
* Rechazar si `|now - ts| > 5 min` → **202 ignored\_stale** (auditar `stale_event`).  
* Dedupe por **UNIQUE(workspace\_id, wa\_message\_id)** → duplicado: **200 ok\_duplicate** (no tocar contadores).

**Reintentos e idempotencia**

* Siempre **200** al BSP si la firma es válida, aunque internamente falle; encolar a **DLQ** con `dlq_reason`.  
* Idempotency key: `wa_message_id`; si no existe (ej. eventos sin message), usar `request_id` generado \+ hash del payload.

**Allowlist de IPs (opcional)**

* `ip_allowlist` por canal; fuera de lista → **403 ip\_not\_allowed** (auditar).  
* No reemplaza la firma: **ambos** controles deben pasar.

**Rutas de procesamiento**

* F-00 Channel Resolver: resuelve `{workspace_id, channel_id}` por `business_phone_id`, **setea contexto** y persiste inbound (idempotente).  
* Publica evento normalizado en Stream y retorna **200**.

**Errores estándar**

* 403 `invalid_signature | ip_not_allowed`  
* 202 `ignored_stale`  
* 200 `ok | ok_duplicate` (Meta no debe reintentar)

**Métricas y auditoría**

* Métricas: `webhook_valid`, `webhook_invalid_signature`, `webhook_duplicates`, `webhook_stale`, p95 de parse.  
* Auditoría: `webhook_received`, `signature_failed`, `duplicate_ignored`, `stale_ignored`, `enqueued_dlq`.

---

## **7.12 Manejo de secretos**

**Objetivo**  
 Proteger credenciales y llaves de la plataforma con rotación, mínima exposición y trazabilidad.

**Almacenamiento por entorno**

* **Dev**: `.env.local` (solo en máquina de dev, git-ignored).  
* **Staging/Prod**: **Vault/Doppler/KMS** (recomendado: Doppler para app \+ KMS/Vault para llaves).  
* **Kubernetes**: inyección por `Secret` \+ `envFrom` (no montar a disco si no es necesario). Prohibido bake en imagen.

**Rotación y “doble secreto”**

* Mantener **dos versiones activas** por secreto durante rotación (old+new) y conmutar por flag:  
  * `JWT_SIGNING_KEY_v1`, `JWT_SIGNING_KEY_v2` (RS256/PEM) → publicar ambos en **JWKS** 48 h.

  * `WHATSAPP_APP_SECRET_v1|v2` por canal (permitir validación con cualquiera).

* Calendario:  
  * **JWT**: 90 días. **API keys internas**: 90 días. **WHATSAPP\_APP\_SECRET**: 180 días o ante sospecha. **DB/Redis/S3**: 180 días.  
* Rotación \= emitir nueva credencial, poner en paralelo, monitorear, retirar vieja, auditar.

**Inyección y scopes**

* Cada microservicio recibe **solo** los secretos que necesita (principio de mínimo privilegio).  
* Separar: **signing keys** (JWT) vs **at-rest keys** (KMS/S3 SSE).  
* Credenciales de DB específicas por servicio (usuario/rol por servicio, no “superusuario”).

**Políticas de uso**

* **Nunca** loguear secretos. Habilitar **masking** (`****`) en logs/APM/UI.  
* Validar en arranque: variables críticas presentes (fail-fast).  
* Secret scanning en CI (gitleaks/trufflehog) \+ commit hooks.  
* Backups: **excluir** stores de secretos; si hay snapshots de Vault, cifrados y con control de acceso.

**Procedimientos especiales**

* **JWKS**: publicar en `/auth/.well-known/jwks.json`; agregar key nueva, esperar propagación, luego retirar la anterior.  
* **WhatsApp BSP**: rotación por **canal**; mantener `*_v1|v2` y elegir en validación.  
* **S3/MinIO**: habilitar SSE-KMS y rotar `SSE_MASTER_KEY`.

**Variables recomendadas (naming)**  
 `PULPO_JWT_PRIVATE_KEY`, `PULPO_JWT_PUBLIC_JWKS`,  
 `WHATSAPP_APP_SECRET_v1|v2`,  
 `DB_URL`, `REDIS_URL`,  
 `S3_ENDPOINT`, `S3_ACCESS_KEY`, `S3_SECRET_KEY`, `S3_SSE_MASTER_KEY`,  
 `N8N_WEBHOOK_SECRET`,  
 `RAG_EMBEDDINGS_API_KEY`,  
 `OAUTH_GOOGLE_CLIENT_ID`, `OAUTH_GOOGLE_CLIENT_SECRET`.

**Auditoría**

* `audit_logs`: `secret_rotated`, `jwks_key_added/removed`, `bsp_secret_rotated`, con `{actor, target, when}`.  
* Alertas si variable crítica falta/cambia en runtime.

---

## 

## **7.13 Auditoría y privacidad**

**audit\_logs**: registrar acciones sensibles en formato estandarizado.

* Action: string jerárquico (ej. "auth.login.success", "auth.login.failed", "apikey.rotate", "workspace.plan.change").  
* target\_type: string (document, workspace, channel, user, apikey, session).  
* target\_id: uuid nullable.  
* user\_id: uuid nullable (si acción es automática, null).  
* meta\_json: detalles, sin PII directo (usar ofuscación: ej. "54911\*\*\*\*\*123").  
* created\_at: timestamptz.

**Políticas**:

* Tabla append-only (sin UPDATE/DELETE), solo insert.  
* Acceso restringido: superadmin global y roles owner por workspace.  
* Integración con F-Alerts: detección de anomalías (ej. \>5 logins fallidos, abuso impersonación).  
* Retención: 12 meses online → export a Parquet → borrado en DB.  
* Logs de aplicación nunca deben contener contenido de mensajes ni PII cruda; solo IDs y hashes.

---

## **7.15 Errores estándar**

Formato uniforme de error (todas las APIs):

{ "error":"\<error\_key\>", "message":"\<humano breve\>", "request\_id":"\<uuid\>", "details":{...} }

* `error`: clave estable (snake\_case).  
* `message`: texto para UI; no filtra secretos.  
* `request_id`: para trazabilidad end-to-end.  
* `details`: opcional (ej. campos inválidos).

**Catálogo y códigos**

* **401 Unauthorized**: `invalid_credentials`, `totp_required`, `invalid_totp`, `invalid_token`

* **403 Forbidden**: `insufficient_role`, `missing_membership`, `scope_denied`, `ip_not_allowed`  
  **409 Conflict**: `apikey_exists`, `wa_message_dup`, `state_conflict`  
* **422 Unprocessable Entity**: `validation_error` (con `details.field_errors[]`)  
* **429 Too Many Requests**: `rate_limited` (incluir `Retry-After` en header)  
* **400 Bad Request** (genérico): `bad_request` (evitar salvo necesidad)  
* **500 Internal Server Error**: `internal_error` (sin filtrar stack)

**Notas**

* WhatsApp webhook: firma inválida ⇒ **403 `invalid_signature`**; duplicado ⇒ **200 `ok_duplicate`**.  
* Siempre incluir `request_id` y loguear con mismo id en servicios.

## **QA (sanity)**

* Forzar login inválido ⇒ `401 invalid_credentials` con `request_id`.  
* Llamar endpoint sin `X-Workspace-Id` ⇒ `422 validation_error` (`details.missing=["X-Workspace-Id"]`).  
* Rebasar rate ⇒ `429 rate_limited` \+ `Retry-After`.

## **Riesgos / Troubleshooting**

* Mensajes demasiado verborrágicos ⇒ acotar `message`, detalle técnico en logs.

* Inconsistencia de claves ⇒ tests contractuales de errores en CI.

---

## **7.16 Checklist de aceptación**

**Auth & sesiones**

* Login email+password con 2FA TOTP (obligatorio para owner/superadmin).  
* Google OAuth operativo.  
* JWT RS256 con `memberships` y `default_ws`; **JWKS publicado** y probado.  
* **Refresh tokens rotativos** (7 días), reuse-detection y tope ≤5 sesiones por usuario.  
* Endpoint de sesiones: listar/revocar con auditoría.

**Autorización & planes**

* Middleware valida `X-Workspace-Id`; orden: **scope → membership → rol → step-up**.  
* API keys: creación (clave mostrada una vez), **hash Argon2id**, `expires_at` opcional, `ip_allowlist` opcional, auditoría de alta/baja.  
* Scopes efectivos por endpoint (deny-by-default).

**Rate limit & webhooks**

* Límites por workspace/contact/apikey activos; headers `Retry-After` en 429\.  
* Webhook WhatsApp: **HMAC firma válida**, challenge OK, idempotencia por `(workspace_id, wa_message_id)`, 200 rápido; DLQ en fallas.

**Seguridad & privacidad**

* Manejo de secretos (7.12): **doble secreto** en rotación (JWKS/WhatsApp), masking en logs, secret scanning CI.  
* RLS y contexto: `SELECT pulpo.set_ws_context(:ws_id)` en requests que tocan DB.  
* Auditoría completa en `audit_logs` con taxonomía (`auth.login.success`, etc.) y retención (3.3).  
* Logs sin PII; `meta_json` ofuscada (tel/email truncados).

**Métricas & observabilidad (mínimo)**

* Tasa de 401/403/429 por endpoint; p95 auth; `webhook_invalid_signature`, `ok_duplicate`.  
* Trazabilidad por `request_id` en todos los servicios.

**Criterios de aprobación (smoke tests)**

* `POST /auth/login` → 200 con 2FA; reuse refresh ⇒ 401 y familia revocada.  
* `POST /rag/ingest` con API key sin scope ⇒ 403 `scope_denied`.  
* Duplicar `wa_message_id` ⇒ 200 `ok_duplicate`, contadores intactos.  
* Rotar JWKS (dos claves activas) ⇒ tokens v1 y v2 válidos durante ventana.

# **8\. Acciones y Verticales**

Habilitar un catálogo de acciones transaccionales por vertical que el asistente pueda **proponer, confirmar y ejecutar** con **validación de políticas**, **idempotencia** y **trazabilidad completa**.  
 Orquestación: n8n decide (slots/confirmación) y **Action API** ejecuta; todo queda en `actions`, `event_outbox` y `audit_logs`.  
 Disponibilidad por plan: **Start** (solo info, sin ejecutar), **Pro** (acciones internas: agendas/planillas), **Max** (integraciones externas y pagos).  
 Requisitos:

* **Guardrails**: validar horarios, stock, montos y scopes por plan/vertical antes de ejecutar.

* **Idempotencia**: `idempotency_key = hash(workspace_id + conversation_id + action_type + input_json_normalizado)`.

* **Trazabilidad**: propagar `request_id` a `actions`, `messages`, `audit_logs`.

* **Seguridad**: RLS por `workspace_id`, scopes `actions.execute`, confirmación natural previa.

## **8.1 — Entradas / Salidas (JSON schema breve)**

Entrada (propuesta a Action API):

{  
   "workspace\_id": "uuid",  
   "conversation\_id": "uuid",  
   "action\_type": "reservar\_mesa|crear\_pedido|crear\_visita|...",  
   "input": { "...campos de la acción..." },  
   "idempotency\_key": "sha256"  
}

Salida: 

{  
"ok": true|false,  
"data": { "...resultado..." },  
"message": "texto para el usuario"  
}

## **8.1 — Diseño / Proceso (resumen)**

* Clasificar intención y **completar slots** → Guardrails(policy) → **Confirmación** del usuario.  
* Ejecutar Action API con `idempotency_key` → Persistir en `actions` (+ `event_outbox`) → Responder.

## **8.1 — QA (aceptación mínima)**

* Repetir la misma acción confirmada ⇒ **no duplica** (idempotencia) y devuelve mismo `data`.  
* Acción bloqueada por política ⇒ `ok:false`, `message` explica el motivo.  
* Trazabilidad: `request_id` visible en timeline de la conversación.

## **8.1 — Riesgos / Troubleshooting**

* Doble ejecución por reintentos → verificar `idempotency_key` y locks a nivel Action API.  
* Inputs ambiguos → re-preguntar slots críticos antes de confirmar.  
* Desalineo de planes → testear gating Start/Pro/Max por vertical.

---

## **8.2 Filosofía de diseño de acciones**

* **Estandarizadas**: todas siguen el mismo contrato (`actions` con `input_json`, `output_json`, `status`).

* **Determinísticas**: requieren confirmación natural antes de ejecutar (prompt instruye a validar con el usuario).

* **Seguras**:

  * Inputs validados con esquemas estrictos (Zod/JSON Schema).  
  * Outputs sanitizados antes de mostrarse al usuario.

* **Multi-tenant**: tabla `actions` con `workspace_id` protegido por RLS; ninguna acción puede ser vista fuera de su workspace.

* **Idempotentes**: `UNIQUE(workspace_id, created_by_msg_id, action_type)` para evitar duplicados; reintentos con backoff en integraciones externas.

* **Extensibles**: catálogo inicial acotado, luego ampliable por vertical.

* **Auditable**: todo intento de acción queda registrado en `actions` y `audit_logs`.

* **Orquestadas**: ejecución siempre vía **Action API**, que llama a adapters externos (n8n, CRM, POS, etc.); nunca directo desde el LLM.

---

## 

## **8.3 Catálogo inicial de acciones** 

Formato común: todas las acciones usan `Action API` con:

* **Input**: `{ workspace_id, conversation_id, action_type, input, idempotency_key }`

* **Output**: `{ ok, data, message }`

* **Idempotencia**: `idempotency_key = sha256(ws + conv + action_type + input_normalizado)`

* **Planes**: **Start** \= solo informativo (no ejecuta); **Pro** \= internas (Calendar/Sheets); **Max** \= integraciones externas (POS/CRM/e-commerce/pagos).

## **8.3.1 Inmobiliaria**  **crear\_visita**

* Input: `{ fecha:"YYYY-MM-DD", hora:"HH:mm", property_id:"string", cliente:{ nombre, telefono:"+E164", email? } }`

* Output: `{ visita_id:"string", slot:"ISO8601" }`

* Plan: Pro (Google Calendar) / Max (CRM). Notas: valida ventana horaria y solapamientos.  
   **enviar\_ficha**

* Input: `{ property_id:"string", canal:"whatsapp|email" }`

* Output: `{ envio_id:"string" }`

* Plan: Pro (plantillas internas) / Max (CRM/doc store).  
   **precalificar\_cliente**

* Input: `{ ingresos:number, presupuesto:number, garantia:"propietaria|seguro|no_tiene" }`

* Output: `{ apto:boolean, razones:[string] }`

* Plan: Pro/Max. Notas: guarda etiqueta en CRM si disponible (Max).

## **8.3.2 Gastronomía**  **crear\_pedido**

* Input: `{ items:[{sku:string, qty:int}], modalidad:"retiro|envio", horario?: "HH:mm", direccion?:{ calle, numero, localidad }, pago?:"efectivo|mp|pos" }`

* Output: `{ pedido_id:"string", total:number, eta_min:int }`

* Plan: Pro (Sheets) / Max (POS). Notas: fuera de horario → ofrece pedido diferido.  
   **reservar\_mesa**

* Input: `{ personas:int(1..20), fecha:"YYYY-MM-DD", hora:"HH:mm", nombre:string, telefono:"+E164" }`

* Output: `{ reserva_id:"string", mesa?:string }`

* Plan: Pro (Calendar) / Max (POS/Reserva).  
   **consultar\_stock**

* Input: `{ items:[{sku:string}] }`

* Output: `{ disponibilidad:[{sku, en_stock:boolean}]}`

* Plan: Pro (catálogo local) / Max (POS).

## **8.3.3 E-commerce**  **cotizar**

* Input: `{ items:[{sku:string, qty:int}], envio?:{cp:string, modalidad:"domicilio|sucursal"} }`

* Output: `{ total:number, items:[{sku, unit:number, subtotal:number}], envio?:{costo:number, eta_dias:int} }`

* Plan: Pro (Sheets/rules) / Max (Shopify/ML).  
   **iniciar\_checkout**

* Input: `{ carrito_id?:string, items?:[{sku, qty}] }`

* Output: `{ checkout_url:"https://..." }`

* Plan: Max. Notas: si no hay `carrito_id`, lo crea y devuelve URL.  
   **consultar\_estado\_pedido**

* Input: `{ order_id:"string" }`

* Output: `{ estado:"pendiente|pagado|enviado|entregado|cancelado", tracking?:{courier,codigo,url} }`

* Plan: Max (integración tienda).

## **8.3.4 Reglas por vertical según estado (negocio cerrado)**  **Gastronomía**

* Start: responder horarios/menú (RAG), sin crear pedidos/reservas.

* Pro: permitir **reserva/pedido diferido** con confirmación y registro en Calendar/Sheets.

* Max: integrarse a POS; siempre confirmar y validar ventanas.  
   **Inmobiliaria**

* Start: tomar datos y prometer contacto.

* Pro: validar disponibilidad y **pre-agendar** con Calendar.

* Max: agendar directo en CRM/Calendar.  
   **E-commerce**

* Start: info de stock/políticas (RAG).

* Pro: cotizaciones simples; no checkout.

* Max: checkout URL y estado de pedido.

## **QA (mínimo)**

* Reintentar **mismo input** ⇒ mismo `pedido_id/reserva_id` (idempotencia).

* Horario fuera de rango ⇒ `ok:false`, `message` explicando ventana.  
* Acción no habilitada por plan ⇒ `403 scope_denied`.

## **Riesgos / Troubleshooting**

* SKUs inexistentes ⇒ devolver lista de inválidos en `details`.  
* Integración externa lenta ⇒ timeout controlado \+ fallback “te confirmo en breve” \+ `event_outbox`.  
* Teléfono/formato inválido ⇒ `422 validation_error`.

## ---

## **8.4 Contratos JSON (Action API)**

**Headers comunes (todas las rutas)**

* `Authorization: Bearer <jwt|api-key>`

* `X-Workspace-Id: <uuid>`

* `X-Request-Id: <uuid-v4>` (obligatorio; se propaga a `actions`/`audit_logs`)

* `Idempotency-Key: <sha256>` (obligatorio en ejecuciones)

**Formato de respuesta (éxito/fracaso)**

{ "ok": true, "data": { ... }, "message": "texto para el usuario", "request\_id": "uuid" }

### 

{ "ok": false, "error":"\<error\_key\>", "message":"humano breve", "request\_id":"uuid", "details":{...} }

(errores: usar catálogo 7.15)

### 

### **Ejemplo: reservar mesa**

`POST /actions/execute`

Request:

{  
   "workspace\_id": "uuid",  
   "conversation\_id": "uuid",  
   "action\_type": "reservar\_mesa|crear\_pedido|crear\_visita|cotizar|iniciar\_checkout|consultar\_estado\_pedido|enviar\_ficha|precalificar\_cliente|consultar\_stock",  
   "input": { "…payload específico de la acción…" },  
   "plan\_tier": "start|pro|max"  
}

**Reglas**

* Autorización: scope `actions.execute`.

* **Guardrails** previos (horarios/stock/montos) → si no pasa, `ok:false` con razón.

* **Idempotencia**: `Idempotency-Key = sha256(ws + conv + action_type + input_normalizado)`

* Si se reintenta con la misma key y ya hubo éxito → devolver el **mismo resultado** (HTTP 200).

* Si la acción no está habilitada por plan → `403 scope_denied`.

**Response (éxito, ejemplo reservar\_mesa)**

{  
   "ok": true,  
   "data": { "reserva\_id": "R-10293", "slot": "2025-09-05T20:30:00-03:00" },  
   "message": "Reserva confirmada para 4 personas el 05/09 a las 20:30.",  
   "request\_id": "uuid"  
}

**Response (fallo validación/guardrails)**

{  
   "ok": false,  
   "error": "validation\_error",  
   "message": "Necesito que la hora esté en formato HH:mm.",  
   "request\_id": "uuid",  
   "details": { "field\_errors": \["hora"\] }  
}

### **2\) Pre-chequeo de acción (opcional)**

`POST /actions/validate`  
 Valida **solo políticas y esquema**, no ejecuta.

**Request** \= mismo cuerpo de `/actions/execute`.  
 **Response**

{ "ok": true, "normalized\_input": { ... }, "reasons":\[\] , "request\_id":"uuid" }

o

{ "ok": false, "error":"policy\_denied", "reasons":\["fuera\_de\_horario"\], "request\_id":"uuid" }

### **3\) Obtener estado de una acción**

`GET /actions/{id}`  
 **Response**

{  
   "ok": true,  
   "data": {  
       "id": "uuid",  
       "status": "pending|success|failed",  
       "action\_type": "reservar\_mesa",  
       "input": { ... },  
       "output": { ... },  
       "created\_at": "ts",  
       "updated\_at": "ts"  
   },  
   "request\_id": "uuid"  
}

### **4\) Listar acciones por conversación (paginado)**

`GET /conversations/{id}/actions?limit=20&cursor=<opaque>`  
 **Response**

{  
   "ok": true,  
   "data": { "items":\[{ "id":"uuid","status":"success","action\_type":"crear\_pedido","created\_at":"ts"}\], "next\_cursor": null },  
   "request\_id":"uuid"  
}

### **Notas por acción (inputs mínimos)**

* **reservar\_mesa**: `{ personas:int(1..20), fecha:"YYYY-MM-DD", hora:"HH:mm", nombre:string, telefono:"+E164" }`

* **crear\_pedido**: `{ items:[{sku,qty}], modalidad:"retiro|envio", horario?:"HH:mm", direccion?:{...}, pago?:"efectivo|mp|pos" }`  
* **crear\_visita**: `{ fecha, hora, property_id, cliente:{nombre, telefono:+E164, email?} }`  
* **cotizar**: `{ items:[{sku,qty}], envio?:{cp, modalidad} }`  
* **iniciar\_checkout**: `{ carrito_id?:string, items?:[{sku,qty}] }`  
* **consultar\_estado\_pedido**: `{ order_id:string }`  
* **enviar\_ficha**: `{ property_id:string, canal:"whatsapp|email" }`  
* **precalificar\_cliente**: `{ ingresos:number, presupuesto:number, garantia:"propietaria|seguro|no_tiene" }`  
* **consultar\_stock**: `{ items:[{sku}] }`

---

### **Seguridad y auditoría**

* Inserción en `actions` con `status` inicial `pending`; actualizar a `success|failed` y persistir `output_json`.  
* Emitir `event_outbox` (`aggregate_type:"action"`, `event_type:"created|updated|failed"`).  
* `audit_logs` con `action:"action.execute"`, `target_type:"action"`, `target_id`, y `meta_json` (sin PII cruda).

---

## **QA (mínimo)**

* Reintentar `/actions/execute` con **misma** `Idempotency-Key` ⇒ mismo `reserva_id`.  
* Acción fuera de plan (`start`) ⇒ **403 `scope_denied`**.  
* `validate` falla por horario ⇒ `ok:false`, `policy_denied` con `reasons`.

## **Riesgos / Troubleshooting**

* Tiempos de terceros → usar timeout coherente y fallback “te confirmo en breve”; completar por webhook y actualizar acción.  
* Doble confirmación del usuario → conservar solo el **último** `pending_action` en `conversation.meta`.  
* SKUs inválidos → `422 validation_error` con `details.invalid_skus`.

## **8.5 Validación de inputs**

**Objetivo**  
 Asegurar entradas **coherentes, normalizadas y auditables** antes de ejecutar acciones; evitar duplicados e inconsistencias.

**Entradas / Salidas (esquema breve)**

Entrada a validator:  
{ action\_type, input, plan\_tier, workspace\_id }

Salida:   
{ ok: true, normalized\_input } | { ok: false, error, message, details }

**Diseño / Proceso**

1. Normalización: trim strings; fechas “YYYY-MM-DD”; horas “HH:mm”; teléfonos E164 (+54911…); enums en minúscula; SKUs upper.

2. Validación por acción (Zod/JSON Schema) \+ reglas cruzadas:

   * crear\_pedido: si modalidad=envio ⇒ direccion requerida; qty ≥1; items únicos.

   * reservar\_mesa: 1≤personas≤20; fecha futura; hora en rango negocio.

   * crear\_visita: fecha/hora futuras; property\_id no vacío; teléfono/email válidos.

   * iniciar\_checkout: carrito\_id XOR items (uno de los dos).

3. Guardrails/Policy: ventanas horarias, stock, montos máximos por plan.

4. Resultado: ok \+ normalized\_input; si falla ⇒ error 422 validation\_error o policy\_denied (7.15).

5. Idempotencia: idempotency\_key \= sha256(wsId+convId+action\_type+JSON.stringify(normalized\_input)).

**Catálogo de Schemas (JSON Schema 2020-12, extracto operativo)**

**reservar\_mesa**  
**{**  
   **"type":"object","properties":{**  
   **"personas":{"type":"integer","minimum":1,"maximum":20},**  
   **"fecha":{"type":"string","format":"date"},**  
   **"hora":{"type":"string","pattern":"^(\[01\]\[0-9\]|2\[0-3\]):\[0-5\]\[0-9\]$"},**  
   **"nombre":{"type":"string","minLength":1},**  
   **"telefono":{"type":"string","pattern":"^\\+\[1-9\]\[0-9\]{7,14}$"}**  
**},**  
   **"required":\["personas","fecha","hora","nombre","telefono"\]**  
**}**

**crear\_pedido**  
**{**  
   **"type":"object","properties":{**  
   **"items":{"type":"array","minItems":1,"items":{**  
       **"type":"object","properties":{**  
           **"sku":{"type":"string","minLength":1},**  
           **"qty":{"type":"integer","minimum":1}**  
       **},"required":\["sku","qty"\]**  
   **}},**  
   **"modalidad":{"enum":\["retiro","envio"\]},**  
   **"horario":{"type":"string","pattern":"^(\[01\]\[0-9\]|2\[0-3\]):\[0-5\]\[0-9\]$"},**  
   **"direccion":{"type":"object","properties":{**  
       **"calle":{"type":"string"},"numero":{"type":"string"},**  
       **"localidad":{"type":"string"},"cp":{"type":"string"}**  
   **}}**  
**},**  
   **"required":\["items","modalidad"\],**  
   **"allOf":\[**  
       **{"if":{"properties":{"modalidad":{"const":"envio"}}},**  
           **"then":{"required":\["direccion"\]}}**  
   **\]**  
**}**

**crear\_visita**  
**{**  
   **"type":"object","properties":{**  
   **"fecha":{"type":"string","format":"date"},**  
   **"hora":{"type":"string","pattern":"^(\[01\]\[0-9\]|2\[0-3\]):\[0-5\]\[0-9\]$"},**  
   **"property\_id":{"type":"string","minLength":1},**  
   **"cliente":{"type":"object","properties":{**  
       **"nombre":{"type":"string","minLength":1},**  
       **"telefono":{"type":"string","pattern":"^\\+\[1-9\]\[0-9\]{7,14}$"},**  
       **"email":{"type":"string","format":"email"}**  
   **},"required":\["nombre","telefono"\]}**  
**},**  
   **"required":\["fecha","hora","property\_id","cliente"\]**  
**}**

**iniciar\_checkout**  
**{**  
   **"type":"object","properties":{**  
   **"carrito\_id":{"type":"string"},**  
   **"items":{"type":"array","minItems":1,"items":{**  
       **"type":"object","properties":{"sku":{"type":"string"},"qty":{"type":"integer","minimum":1}},**  
       **"required":\["sku","qty"\]**  
   **}}**  
**},**  
   **"oneOf":\[**  
       **{"required":\["carrito\_id"\]},**  
       **{"required":\["items"\]}**  
   **\]**  
**}**

**Manejo de errores (map a 7.15)**

* Campo inválido → 422 validation\_error (details.field\_errors=\["hora","telefono"\]).

* Regla de negocio → 403 policy\_denied / scope\_denied (según plan/política).

* Faltan slots clave → 422 validation\_error \+ message con ejemplo.  
   Mensajes i18n: plantillas “Necesito {campo} en formato {formato}”.

**QA (aceptación)**

* Modalidad=envio sin dirección ⇒ 422 con details.field\_errors=\["direccion"\].

* Teléfono sin “+” o \<8 dígitos ⇒ 422 en reservar\_mesa/crear\_visita.

* Hora fuera del horario negocio ⇒ policy\_denied (403) con reasons=\["fuera\_de\_horario"\].

* Repetir mismo input normalizado ⇒ misma idempotency\_key.

**Riesgos / Troubleshooting**

* SKUs desconocidos: responder 422 con details.invalid\_skus=\[…\]; sugerir similares opcional.

* Zona no cubierta (delivery): policy\_denied con reasons=\["zona\_no\_cubierta"\].

* Ambigüedad de fecha (formato regional): siempre “YYYY-MM-DD”; si detectás dd/mm ⇒ pedir confirmación.  
  * 

## **8.6 Confirmación antes de ejecutar**

* **System prompt** instruye al LLM:

  * Proponer acción **solo** si alta confianza (≥ 0.7).

  * Generar mensaje natural de confirmación:

     “¿Confirmás reserva para 4 personas el 5 de septiembre a las 20:30?”

* Respuestas válidas: Sí / No / Cambiar.

* Se guarda pending\_action en conversation.meta.

---

## **8.7 Persistencia y estado**

**Objetivo**: asegurar que toda acción se ejecute solo tras confirmación explícita, con trazabilidad, idempotencia y buena UX.

**Entradas / Salidas**  
\- Entrada (del orquestador): { workspace\_id, conversation\_id, action\_type, normalized\_input }  
\- Salida (al usuario): mensaje de confirmación claro \+ opciones (sí / no / cambiar)

**Diseño / Proceso**

**Preparación**

* Generar \`confirmation\_text\` natural y concreta.  
* Calcular \`idempotency\_key \= sha256(ws+conv+action\_type+normalized\_input)\`.  
* Persistir intención pendiente en \`conversation.meta.pending\_action \= { action\_type, normalized\_input, idempotency\_key, status:"awaiting\_confirm", expires\_at: now()+10m, attempts:0 }\`.  
* Registrar en \`actions\` un placeholder (status="pending\_confirm", idempotency\_key).


**Pedir confirmación**

* Enviar: “¿Confirmás reservar mesa para 4 el 2025-09-05 20:30 a nombre de Nico? (Sí / No / Cambiar)”.  
* Adjuntar quick replies: \["Sí","No","Cambiar"\].

**Interpretar respuesta del usuario**

* Sí/OK/Afirmativo ⇒ transicionar \`actions.status → executing\` y llamar \`/actions/execute\` (mismo idempotency\_key).  
* No/Cancelar ⇒ \`pending\_action.status="cancelled"\`, registrar en \`actions\` y \`audit\_logs\`.  
* Cambiar/Edit ⇒ pedir campos faltantes, regenerar \`pending\_action\` con nueva key.  
* Silencio: recordatorio a los 2m; expiración automática a los 10m (\`status="expired"\`).

**Idempotencia fuerte**

* Lookup sobre \`actions.idempotency\_key\`.  
* Confirmaciones duplicadas devuelven el mismo resultado/reserva\_id sin re-ejecutar.

**Mensajes seguros**

* Nunca incluir datos sensibles no requeridos.  
* Totales/costos solo si fueron validados por Policy/Guardrails.

**Reglas de UX**

* Siempre ofrecer “No” y “Cambiar”.  
* En negocio cerrado, ofrecer diferido válido y explicitar ventana.

**Estados de confirmación** a

* waiting\_confirm → confirmed → executing → success|failed  
* cancelled | expired | replaced

Contrato \`pending\_action\`  
{  
   "action\_type": "reservar\_mesa",  
   "normalized\_input": { ... },  
   "idempotency\_key": "sha256...",  
   "status": "awaiting\_confirm",  
   "expires\_at": "2025-09-05T20:40:00-03:00",  
   "attempts": 0  
}

**Plantillas de confirmación (ejemplos)**

* reservar\_mesa: “¿Confirmás reserva para {personas} el {fecha} {hora} a nombre de {nombre} (tel {telefono})?”

* crear\_pedido: “¿Confirmás pedido {items\_descrip} — total {total} — {modalidad} {direccion?}?”

* crear\_visita: “¿Confirmás visita a {propiedad} el {fecha} {hora} con {nombre}/{telefono}?”

**Excepciones**

* Acciones informativas (consultar\_stock, consultar\_estado\_pedido) pueden ejecutarse directo si policy lo permite.

* Reintentos técnicos tras timeout de Action API reutilizan idempotency\_key (no piden confirmación de nuevo).

**QA (aceptación)**

* “Sí” dentro de 10m ⇒ una sola ejecución, resultado estable.

* “No” ⇒ `status="cancelled"`, sin efectos secundarios.

* “Cambiar” ⇒ nueva confirmación requerida.

* Sin respuesta ⇒ recordatorio \+ expiración.

* Ambigüedad persistente ⇒ abrir `handoff_ticket`.

**Riesgos / Troubleshooting**

* Desfase horario ⇒ normalizar TZ workspace, mostrar hora local.

* Multi-dispositivo ⇒ detener en primera confirmación, devolver resultado previo.

* Auditoría: todas las transiciones de estado logueadas en `audit_logs`.

## ---

## **8.8 Integración con verticales externas**

**Objetivo**  
 Conectar acciones de Pulpo con APIs externas (CRM inmobiliario, Calendar, POS/Sheets, e-commerce) mediante **adapters** desacoplados, seguros e idempotentes.

**Entradas / Salidas (JSON breve)**

 Entrada (Action API → Adapter):  
 `{ workspace_id, action_type, payload, idempotency_key, request_id }`  
 Salida (Adapter → Action API):

* OK: `{ ok:true, provider:"google|tokko|shopify|...", provider_ref, data, message }`

* Error: `{ ok:false, provider, error_key, http_status?, retryable?, details? }`

**Diseño / Proceso (patrón Adapter)**

* **Descubrimiento**: `GET /adapters/capabilities?workspace_id=...` ⇒ lista de acciones soportadas por workspace (según integraciones habilitadas).

* **Resolución**: `POST /actions/execute` mapea `action_type` → `{adapter, provider_action}` (tabla de ruteo).

* **Idempotencia**: enviar `Idempotency-Key: <idempotency_key>` al adapter; si el proveedor lo soporta (p.ej., Stripe/Shopify), propagar; si no, persistir cache interna por `(workspace_id, idempotency_key)`.

* **Backoff**: reintentos exponenciales 429/5xx (1s, 4s, 10s; máx 3), no reintentar 4xx salvo 409 (conflicto idempotente).

* **Normalización**: cada adapter traduce `payload` estándar ↔ contrato del proveedor y devuelve `provider_ref` (id externo) \+ `data` homogénea.

* **Webhooks**: adapters exponen `/provider/webhooks/...` → confirman eventos (p.ej., pago acreditado) publicando en `event_outbox`.

* **Entornos**: `mode: "sandbox"|"prod"` por workspace; secretos desde `api_keys`/vault; nunca credenciales de usuario final.

* **Logs/Auditoría**: registrar `request_id`, `provider`, `latency_ms`, `status`, sin PII.

**Contratos por vertical (ejemplos “listos”)**

* **Inmobiliaria → Google Calendar (crear\_visita)**  
   Request a adapter-google:  
   `{ action:"calendar.create_event", payload:{ calendar_id, title, start, end, attendee:{name, phone}, notes, tz } }`  
   Respuesta OK:  
   `{ ok:true, provider:"google", provider_ref:"evt_1A2B", data:{ html_link, start, end } }`

* **Gastronomía → Google Sheets (crear\_pedido / consultar\_stock)**  
   `action:"sheets.append_row", payload:{ sheet_id, range:"Pedidos!A:F", values:[ts, nombre, items_json, total, modalidad, estado] }`  
   OK: `{ ok:true, provider:"google", provider_ref:"append_987", data:{ updatedRange:"Pedidos!A42:F42" } }`

* **E-commerce → Shopify (iniciar\_checkout / cotizar)**  
   `action:"shopify.draft_order_create", payload:{ line_items:[{sku, qty}], customer:{email, phone}, shipping_address?, discounts? }`  
   OK: `{ ok:true, provider:"shopify", provider_ref:"do_123", data:{ invoice_url, total, currency } }`

**QA (criterios de aceptación)**

* Capabilities devuelve sólo acciones habilitadas por plan/config.

* Repetir `actions/execute` con la **misma** `idempotency_key` ⇒ misma `provider_ref` (sin duplicar).

* Timeouts 5xx/429 reintentan; 4xx no (salvo 409).

* Webhook de proveedor genera `event_outbox` y actualiza `actions.status` coherentemente.

**Riesgos / Troubleshooting**

* **Desfasaje TZ**: siempre mandar `tz` del workspace y validar en provider.

* **Duplicados**: revisar cache idempotente del adapter y 409 del proveedor.

* **Cortes parciales**: si adapter OK pero persistencia falla, usar “confirm write” (releer por `provider_ref` y re-persistir).

* **Scopes insuficientes**: mapear `error_key="insufficient_scope"` y guiar setup.

---

## **8.9 Seguridad de acciones**

**Objetivo**: ejecutar acciones sólo si cumplen reglas de negocio, límites de plan y políticas de seguridad; proteger entradas/salidas, secretos y eventos externos.

**Alcance y permisos**

* Habilitación por workspace: enabled\_actions en workspace\_configs.policy\_json.  
* Roles: sólo editor+ puede disparar acciones; owner/admin habilitan/deshabilitan.  
* Scope: una acción sólo opera sobre recursos del mismo workspace\_id (FKs consistentes).

**Validación e idempotencia**

* Validación fuerte: JSON Schema/Zod por acción; normalización previa (types, rangos, enums).  
* Guardrails Service (obligatorio): /policy/guardrails valida horarios, stock mínimo, límites monetarios, métodos de pago permitidos por plan. Devuelve {allowed, reasons\[\], normalized\_payload}.  
* Idempotencia E2E: idempotency\_key obligatorio; lookup en actions y propagación al proveedor (cabecera Idempotency-Key cuando aplique). Reintentos sólo si retryable=true.

**Rate limiting y cuotas**

* Por workspace: acciones.execute → 10/min (configurable por plan).  
* Por conversación: 2 acciones “commit” en 2 min (evita spam).  
* Por tipo de acción: límites mensuales en plans.policy\_json (acciones\_mes). Exceso → error “quota\_exceeded”.

**Salidas y mensajes seguros**

* Sanitizar output\_json antes de mostrar: sin HTML/script; truncar strings largas; ocultar PII no necesaria.  
* Cifras/monedas: usar formato y decimales del workspace; nunca prometer montos si guardrails=denied.  
* No interpolar datos no validados en plantillas de confirmación.

**Webhooks y callbacks de proveedores**

* Verificación de origen: firma HMAC o JWKS del proveedor; clock skew ±60s; nonce/`X-Idempotency-Replay-Guard`.  
* Replay protection: almacenar recent\_nonce 10 min; si se repite, descartar.  
* Procesamiento idempotente: actualizar actions por provider\_ref si ya existe.

**Red de salida y secretos**

* Egress allowlist: adapters sólo pueden llamar dominios aprobados por proveedor.  
* Timeouts: 5s connect / 10s total; retries exponenciales 429/5xx (1s,4s,10s; máx 3).  
* Secretos: por workspace en vault; rotación programada; nunca en logs; en memoria el mínimo tiempo posible.

**Límites y ventanas operativas**

* Ventanas horarias por vertical (ej. gastronomía): si fuera de horario → sólo diferido.  
* Límites monetarios por plan: p.ej. Start ≤ ARS 50k/acción, Pro ≤ 200k, Max  configurable; exceder ⇒ require\_human=true.  
* Campos sensibles (teléfono, email): validar formato y país (E164/regex).

**Auditoría y trazabilidad**

* Obligatorio escribir audit\_logs en: validate, confirm, execute, fail, webhook\_received, webhook\_ignored, quota\_exceeded.  
* Guardar request\_id y idempotency\_key en actions, event\_outbox y audit\_logs.

**Política JSON** (extensiones sugeridas)

{  
   "actions\_security": {  
       "rate\_limit\_per\_min": 10,  
       "per\_conversation\_burst": 2,  
       "allowed\_providers": \["google","shopify","sheets","tokko"\],  
       "monetary\_caps": { "start": 50000, "pro": 200000, "max": null },  
       "operating\_hours": { "gastronomia": "11:00-23:30", "inmobiliaria": "09:00-19:00" },  
       "webhook\_replay\_window\_sec": 600,  
       "output\_sanitize": true  
   }  
}

**QA (aceptación)**

* En horario cerrado, reservar\_mesa rechaza en tiempo real y ofrece diferido válido.  
* Reintentar ejecutar con la misma idempotency\_key devuelve mismo provider\_ref (sin duplicar).  
* Webhook con firma inválida o nonce repetido → ignorado \+ audit\_logs.  
* Superar acciones\_mes del plan → error “quota\_exceeded” y registro en audit\_logs.  
* PII ausente en logs; secretos nunca visibles.

**Riesgos / Troubleshooting**

* Duplicados en proveedor: revisar envío del header Idempotency-Key y mapping provider\_ref.  
* Bloqueos por rate limit: observar métricas p95 y ajustar por plan.  
* Errores 4xx: suelen ser de validación/alcance; loguear error\_key y payload normalizado, no el raw.

---

## **8.10 Métricas de acciones**

**Objetivo**: medir efectividad de las acciones por vertical y plan, con datos trazables en BD y visibles en dashboards.

**Indicadores principales**

* **tasa\_éxito** \= success / total acciones ejecutadas.

* **conversión** \= intents detectados → acción confirmada.

* **tiempo\_e2e** \= timestamp\_success – timestamp\_created (ms).

* **cancelaciones** \= porcentaje de acciones que terminan en status=cancelled|expired|replaced.

* **ranking\_vertical** \= top acciones por vertical (ej. reservar\_mesa, crear\_visita).

**Persistencia y cálculo**

* Fuente: tabla `actions` (status, created\_at, completed\_at).

* Vista materializada `v_action_metrics_daily`:

SELECT *date*(created\_at) AS dia,  
      workspace\_id,  
      action\_type,  
      *count*(\*) AS total,  
      *count*(\*) FILTER (WHERE status\='success') AS success,  
      *count*(\*) FILTER (WHERE status IN ('cancelled','expired')) AS canceladas,  
      *avg*(*extract*(epoch from (completed\_at \- created\_at))\*1000) AS tiempo\_e2e\_ms  
FROM actions  
GROUP BY 1,2,3;

* Refrescada por cron cada 15 min.

**Segmentación por plan**

* Métricas se cruzan con `workspaces.plan_tier` → permiten ver uso vs límite (ej. 500 acciones/mes).

* Dashboard muestra barras de consumo y % restante.

**Alertas**

* Si `tasa_éxito < 0.7` en un día → evento a `F-Alerts`.

* Si `cancelaciones > 30%` → warning en dashboard.

**Checklist**

- [ ] Vistas de métricas creadas y probadas.

- [ ] Dashboard con % éxito, conversión, tiempo medio.

- [ ] Límite por plan comparado con consumo.

- [ ] Alertas automáticas conectadas a F-Alerts.

---

## **8.11 Roadmap de expansión**

**Objetivo**: ampliar el catálogo de acciones más allá de las verticales iniciales, garantizando que sigan el mismo contrato y validación.

**Fases previstas:**

* **Servicios profesionales:** agendar turnos (abogados, médicos, consultores).

* **E-commerce avanzado:** devoluciones, cancelaciones y cambios de pedidos.

* **Soporte técnico:** creación de tickets en Helpdesk (Zendesk, Freshdesk, Jira).

* **Pagos:** integración con Stripe/MercadoPago para permitir checkout directo en chat.

* **Omnicanal:** extender ejecución de acciones a Instagram, webchat y otros canales.

**Cada expansión debe cumplir con:**

* Validación de inputs con JSON Schema.

* Confirmación previa al usuario.

* Persistencia en `actions`, `event_outbox` y `audit_logs`.

* Guardrails por plan (no todos los clientes podrán activar pagos o Helpdesk).

---

## **8.12 Checklist de aceptación**

- [ ] Cada acción definida con contrato JSON y esquema de validación.

- [ ] Confirmación previa siempre obligatoria (Sí / No / Cambiar).

- [ ] Registro completo en `actions`, `event_outbox` y `audit_logs`.

- [ ] Adapters listos para integraciones mínimas (Google Calendar, Google Sheets).

- [ ] Métricas disponibles en dashboard (`tasa_éxito`, conversión, cancelaciones, ranking).

- [ ] Límite de acciones configurable por plan en `plans.policy_json`.

# **9\. Observabilidad y Alertas**

### **9.1 Objetivo**

Implementar un sistema de **monitoreo integral** que garantice visibilidad, trazabilidad y respuesta rápida ante fallos o anomalías.

Dimensiones:

* **Logs:** registrar cada request/evento con contexto de workspace, usuario y request\_id.

* **Métricas:** cubrir negocio (conversiones, acciones), LLM (tokens, latencias, costos) y sistema (CPU, memoria, colas).

* **Tracing:** capturar latencia end-to-end por request\_id (desde webhook BSP → orquestador → Action API → respuesta al usuario).

* **Dashboards:**

  * **Internos:** detalle técnico (errores por servicio, latencias p95/p99, costos LLM).

  * **Clientes:** visión resumida en el dashboard (ej. métricas de conversaciones, acciones, éxito/fracaso).

* **Alertas:** notificar incidentes críticos (servicios caídos, colas saturadas), degradaciones (latencia fuera de SLA), anomalías de uso/costo (ej. 10× más tokens que lo normal).

---

## **9.2 Logs**

**Objetivo:** asegurar trazabilidad completa sin exponer PII innecesaria.

**Diseño / Alcance**

* **Formato estructurado JSON** (clave-valor, sin texto libre ambiguo).

* **Campos obligatorios:**

  * `timestamp` (UTC ISO-8601)

  * `request_id` (propagado end-to-end)

  * `workspace_id`

  * `service` (ej. core-api, rag, actions, n8n)

  * `level` (info, warn, error, fatal)

  * `message` (evento claro)

  * `meta` (JSON con detalles: latencia, tokens, ids de acción)

* **Redacción:** sin guardar contenido de mensajes del usuario en logs de aplicación. Solo IDs (message\_id, action\_id).

* **Separación por severidad:**

  * `info`: eventos normales (ingesta completada, acción confirmada).

  * `warn`: condiciones no críticas (reintento embeddings, expiración pending\_action).

  * `error`: fallos que afectan request (API externo caído, acción fallida).

  * `fatal`: caída de servicio o datos corruptos.

**Retención / Exportación**

* Logs en **stdout** para contenedores → recolectados por agente (Fluent Bit / Vector).

* Centralizados en **Elastic / Loki / CloudWatch** (según despliegue).

* Retención:

  * 7 días en caliente (consulta rápida).

  * 90 días en frío (S3 / Glacier).

  * 1 año para logs de auditoría (solo IDs \+ eventos).

**Auditoría cruzada**

* Integrar con tabla `audit_logs` (cap. 7.13) para correlacionar acciones sensibles.

* Clave común: `request_id` \+ `user_id`.

**QA / Validación**

* Generar request artificial → verificar que el mismo `request_id` aparezca en todos los servicios.

* Revisar que ningún log contenga texto libre de usuario → si aparece, sanitizar antes de persistir.

---

# **9.3 Métricas**

1. Objetivo  
    Medir salud y valor del sistema en tres capas (negocio, LLM y plataforma) con series temporales de baja cardinalidad y alertas accionables.

2. Entradas / Salidas (JSON schema breve)  
    Entrada (exporters): `{ "metric": "pulpo_actions_success_total", "labels": {"workspace_id":"...", "vertical":"...", "plan":"..."}, "value": 1 }`  
    Salida (dashboards/APIs): agregados por ventana `{ "ts":"...", "metric":"...", "value":123 }`

3. Diseño / Proceso

* **Stack:** Prometheus (scrape 15s) \+ Pushgateway (jobs batch) \+ Grafana.

* **Espacios de métricas (nombres sugeridos):**

  * Negocio:

    * `pulpo_actions_total{type,vertical,plan}`

    * `pulpo_actions_success_total{type}`

    * `pulpo_actions_e2e_ms_bucket{type}` (histograma p50/p95/p99)

    * `pulpo_conversations_active{workspace_id}`

  * LLM:

    * `pulpo_llm_tokens_prompt_total{provider,model}`

    * `pulpo_llm_tokens_completion_total{provider,model}`

    * `pulpo_llm_cost_usd_total{provider,model}`

    * `pulpo_llm_ttfr_ms_bucket{provider,model}`

  * Plataforma:

    * `pulpo_webhook_in_total{channel}`

    * `pulpo_queue_lag_msgs{stream}`

    * `pulpo_http_request_duration_ms_bucket{service,route,code}`

    * `pulpo_errors_total{service,kind}`

* **Cardinalidad:** etiquetas fijas (`service`, `route`, `type`, `vertical`, `plan`); **no** loguear `message_id`/`contact_id` en labels. `workspace_id` solo en contadores agregados horarios (o sampleada, e.g. top-50).

* **Cálculos clave (PromQL ejemplo):**

  * Tasa de éxito por tipo:  
     `sum(rate(pulpo_actions_success_total[5m])) / sum(rate(pulpo_actions_total[5m]))`

  * p95 e2e acciones: `histogram_quantile(0.95, sum by (le,type) (rate(pulpo_actions_e2e_ms_bucket[10m])))`

  * Costo LLM diario: `sum(increase(pulpo_llm_cost_usd_total[1d]))`

  * Lag de colas: `max(pulpo_queue_lag_msgs)`

* **Exposición:**

  * Core/Action/RAG: `/metrics` (Prometheus client).

  * n8n jobs: push a Pushgateway con `job="ingest"`.

  * Batch de uso → también persistir en `usage_counters` (cap. 5.10).

4. QA

* Health: `/metrics` responde y muestra ≥1 métrica por espacio.

* Validar histograma: buckets con conteo creciente; p95 calculable.

* Cruce: `pulpo_actions_total` ≈ filas `actions` del día (±5%).

* Grafana: dashboards “Ops” y “Cliente” con p95, tasas y costos.

5. Riesgos / Troubleshooting

* **Alta cardinalidad:** reducir etiquetas dinámicas, aplicar `drop` en scrape.

* **Doble conteo:** asegurar contadores **monótonos** y `rate()` en queries.

* **Lag picos:** alertar si `pulpo_queue_lag_msgs > 1000` por 5m; escalar workers.

* **Costos LLM outliers:** alerta si `increase(pulpo_llm_cost_usd_total[1h]) > umbral_plan`.

6. Registro Vivo actualizado  
    Fase: 5 — Observabilidad | Microflujos: F-Alerts | Estado: en progreso | Prioridad: \[P1\]  
    Dependencias: exporters en Core/Action/RAG, Grafana, Prometheus  
    Observaciones: limitar `workspace_id` en labels para evitar explosión de series.

---

# **9.4 Tracing**

1. Objetivo  
    Trazar cada request end-to-end (Webhook BSP → Orquestador → RAG/Action → Respuesta) para aislar cuellos de botella y fallos, y correlacionar con logs y métricas.

2. Entradas / Salidas (JSON schema breve)  
    Entrada (headers):

{ "traceparent":"00-\<trace\_id\>-\<span\_id\>-01", "baggage":"workspace\_id=\<ws\>,plan=\<tier\>" }

Salida (export): spans OTLP → collector → backend (Tempo/Jaeger/Grafana).

3. Diseño / Proceso

* **Stack:** OpenTelemetry SDK (Node/TS) \+ OTLP/HTTP → OTel Collector → Tempo/Jaeger.

* **Propagación W3C:** siempre enviar/leer `traceparent` y `baggage` entre servicios; en ausencia → generar en F-00.

* **Spans mínimos por request:**

  * `webhook.receive` (Message API)

  * `core.resolveChannel`

  * `core.persistInbound` (incluye subspans DB)

  * `n8n.flow.F-01.intent`, `n8n.flow.F-02.router`, `n8n.flow.F-RAG`, `n8n.flow.F-Agent`

  * `rag.search` (subspans: `db.pgvector.search`, `llm.embed` si aplica)

  * `action.execute` (subspans: `adapter.google.calendar`, `adapter.sheets`, `adapter.pos`)

  * `core.persistOutbound` → `bsp.whatsapp.send`

* **Atributos estándar (todas los spans):** `workspace_id`, `conversation_id`, `message_id`, `plan_tier`, `vertical`, `request_id`.

* **n8n:** instrumentar con OTel plugin/HTTP Node wrapper para crear spans por nodo; propagar contexto entre nodos por `X-Traceparent`.

* **DB/Redis/HTTP:** habilitar auto-instrumentations (`@opentelemetry/instrumentation-{http,pg,redis}`) con redacción de parámetros sensibles.

* **Muestreo:** Dev=100%; Staging=20%; Prod base=5% \+ **tail sampling** 100% para spans con `status!=OK` o `ttfr_ms>p95`.

* **Correlación:** incluir `trace_id` en logs (`meta.trace_id`) y en métricas (exemplars) para salto cruzado desde Grafana.

4. QA (aceptación)

* Un webhook genera **un solo trace** con ≥8 spans (lista mínima arriba).

* El `trace_id` es igual en Message API, Core, n8n, RAG y Action.

* p95 de `n8n.flow.F-RAG` visible en Grafana con link “View trace”.

* Errores 5xx muestran spans con `status=ERROR` y evento `exception.stacktrace` redactado.

5. Riesgos / Troubleshooting

* **Huecos en el trace:** falta de propagación → verificar que cada HTTP añada/lea `traceparent`.

* **Cardinalidad alta en atributos:** limitar valores libres; usar IDs, no strings largas.

* **Costo almacenamiento:** aplicar retention 7–14 días y tail sampling por error/latencia.

* **Datos sensibles en spans:** activar `attributeFilter` del Collector para enmascarar payloads (`input_json`, `content_text`).

* **n8n sin spans:** confirmar plugin OTel y variables `OTEL_EXPORTER_OTLP_ENDPOINT`, `OTEL_SERVICE_NAME=n8n`.

---

# **9.5 Dashboards**

1. Objetivo  
    Entregar tableros accionables para dos audiencias: **Ops interno** (profundo) y **Cliente** (resumen), ligados a métricas y traces.

2. Entradas / Salidas (schema breve)  
    Entrada: series Prometheus \+ enlaces a traces (`trace_id`).  
    Salida: paneles Grafana con umbrales y drill-down (link a logs/Tempo).

3. Diseño / Proceso

* **Dashboard Ops (Pulpo – Operaciones)**

  * Visión general: uptime por servicio, `pulpo_errors_total{service,kind}`, `http p95` por ruta.

  * Colas/ingesta: `pulpo_queue_lag_msgs{stream}`, tasa `ingest` y `reindex`.

  * LLM: tokens y **$USD** diarios, `ttfr p95`, split por `provider/model`.

  * Acciones: tasa éxito, e2e p95, “hot intents” y fallas por adapter.

  * RAG: hit-rate, Recall@k (si push), top workspaces por consultas.

  * Tracing hop-links: de p95 a **View trace** (Tempo) por panel.

* **Dashboard Cliente (Pulpo – Mi Negocio)**

  * KPIs: conversaciones, % resueltas por IA, acciones completadas, tiempo medio a primera respuesta.

  * RAG: % respuestas con fuente \+ top documentos.

  * Costos/uso: tokens aprox., acciones del mes vs límite de plan.

  * Calidad: satisfacción (si NPS/emoji), errores visibles y handoffs.

* **Higiene**

  * Variables: `workspace`, `vertical`, `plan`, `service`.

  * Umbrales coloreados y anotaciones de incidentes (F-Alerts).

  * Enlaces rápidos: “Abrir conversación” (dashboard Pulpo) y “Ver logs” (Loki/Kibana).

4. QA (aceptación)

* Todos los paneles cargan en \<2s con rango 24h.

* Click en p95 de acciones abre un trace con spans n8n/Core/Action.

* Conteos del tablero \= ±5% versus tablas (`actions`, `usage_counters`).

* Cliente ve solo su `workspace` (filtro forzado en embed).

5. Riesgos / Troubleshooting

* **Cardinalidad**: limitar “Top N workspaces” y evitar labels de alta entropía.

* **Desfase reloj**: sincronizar NTP; anotar eventos con `request_id`.

* **Paneles pesados**: usar downsampling (recording rules) y rango por defecto 6h.

* **Permisos**: carpetas Grafana separadas (Ops vs Cliente) y viewers sin edición.

---

# **9.6 Alertas**

1. Objetivo  
    Detectar y notificar **fallas, degradaciones y anomalías de costo/uso** con baja fatiga, rutas de escalamiento claras y trazabilidad al `trace_id`.

2. Entradas / Salidas (schema breve)  
    Entrada: series Prometheus/recording rules \+ eventos DLQ/ingest\_jobs.  
    Salida: Alertmanager → Slack \#pulpo-sev, email oncall, (opcional) PagerDuty.

3. Diseño / Proceso

* **Severidades y criterios (mínimos):**

  * **SEV-1 (crítico):** caída de Message API, `bsp_whatsapp_5xx_ratio>0.02 5m`, `queue_lag_msgs{stream="inbound"}>5k 10m`, costo diario \> 2×p7d.

  * **SEV-2 (alto):** `ttfr_p95>5s 10m`, `rag_hit_rate<0.7 15m`, `n8n_flow_fail_rate>5% 10m`, `actions_error_rate>5% 10m`.

  * **SEV-3 (moderado):** `ingest_job_failed_rate>2% 30m`, `dlq_new_events>0 15m`, `rate_limit_near_cap>80% 15m`.

* **Ruteo:** etiquetas `{service, workspace_id?, vertical?, plan?}` → Alertmanager routes: prod vs staging, SEV-1 con alta prioridad.

* **Deduplicación y silencios:** `group_by: [alertname, service, workspace_id]`, `repeat_interval: 2h` y ventanas de mantenimiento (deploys).

* **Acción automática:** crear `audit_logs(action="alert")` y opcional issue en backlog (webhook).

* **Enriquecimiento:** anotar `trace_id` (si aplica), links a Grafana/Tempo y runbook.

4. QA (aceptación)

* Simular: forzar 5xx en webhook → llega **SEV-1** a Slack en \<60s con link a panel.

* Bajar hit-rate RAG a 0.6 en staging → **SEV-2**; al normalizar, alerta resuelta.

* DLQ \>0 → **SEV-3** con payload ejemplo y `request_id`.

5. Riesgos / Troubleshooting

* **Fatiga de alertas:** consolidar por grupo, elevar umbrales con hysteresis, usar recording rules suaves.

* **Falsos positivos en horas pico:** ventanas dependientes de horario y percentiles por vertical.

* **Cardinalidad por workspace:** solo etiquetar `workspace_id` en alertas cliente-facing; para global usar agregados.

* **Canal caído (Slack/Pager):** fallback a email/sms; monitor de “alertas entregadas” (`alerts_fired - alerts_delivered`).

6. Reglas Prometheus (YAML listo para pegar)

groups:

 \- name: pulpo\_core

   rules:

     \- alert: WhatsAppWebhook5xxHigh

       expr: sum(rate(http\_requests\_total{job="message-api",route="/webhooks/whatsapp",code=\~"5.."}\[5m\]))

         / sum(rate(http\_requests\_total{job="message-api",route="/webhooks/whatsapp"}\[5m\])) \> 0.02

       for: 5m

       labels: {severity: SEV-1, service: message-api, env: prod}

       annotations:

         summary: "BSP webhook 5xx \>2%"

         runbook: "https://runbooks/pulpo/webhook-5xx"

     \- alert: QueueInboundLagHigh

       expr: pulpo\_queue\_lag\_msgs{stream="inbound"} \> 5000

       for: 10m

       labels: {severity: SEV-1, service: orchestrator, env: prod}

       annotations:

         summary: "Redis Stream inbound lag \>5k"

         runbook: "https://runbooks/pulpo/redis-lag"

 \- name: pulpo\_rag\_actions

   rules:

     \- alert: RAGHitRateLow

       expr: pulpo\_rag\_hit\_rate \< 0.70

       for: 15m

       labels: {severity: SEV-2, service: rag, env: prod}

       annotations:

         summary: "RAG hit-rate \<0.70"

         runbook: "https://runbooks/pulpo/rag-hitrate"

     \- alert: ActionsErrorRateHigh

       expr: rate(pulpo\_actions\_failed\_total\[10m\]) / clamp\_min(rate(pulpo\_actions\_total\[10m\]),1) \> 0.05

       for: 10m

       labels: {severity: SEV-2, service: action-api, env: prod}

       annotations:

         summary: "Actions fail rate \>5%"

         runbook: "https://runbooks/pulpo/actions-errors"

 \- name: pulpo\_perf\_cost

   rules:

     \- alert: TTFRP95High

       expr: pulpo\_ttfr\_p95\_ms \> 5000

       for: 10m

       labels: {severity: SEV-2, service: n8n, env: prod}

       annotations:

         summary: "TTFR p95 \>5s"

         runbook: "https://runbooks/pulpo/ttfr"

     \- alert: CostAnomalyUSD

       expr: pulpo\_cost\_usd\_1d \> 2 \* pulpo\_cost\_usd\_7d\_avg

       for: 30m

       labels: {severity: SEV-1, service: billing, env: prod}

       annotations:

         summary: "Costo diario \> 2×promedio 7d"

         runbook: "https://runbooks/pulpo/cost-anomaly"

 \- name: pulpo\_reliability

   rules:

     \- alert: DLQNewEvents

       expr: increase(pulpo\_dlq\_events\_total\[15m\]) \> 0

       for: 15m

       labels: {severity: SEV-3, service: orchestrator, env: prod}

       annotations:

         summary: "Aparecieron eventos en DLQ"

         runbook: "https://runbooks/pulpo/dlq"

     \- alert: IngestJobsFailed

       expr: rate(pulpo\_ingest\_jobs\_failed\_total\[30m\]) / clamp\_min(rate(pulpo\_ingest\_jobs\_total\[30m\]),1) \> 0.02

       for: 30m

       labels: {severity: SEV-3, service: rag, env: prod}

       annotations:

         summary: "Ingest failures \>2%"

         runbook: "https://runbooks/pulpo/ingest"

7. Alertmanager (ruta y silencios)

route:

 receiver: slack-sev

 group\_by: \['alertname','service','env'\]

 group\_wait: 30s

 group\_interval: 5m

 repeat\_interval: 2h

 routes:

   \- matchers: \[ 'severity="SEV-1"', 'env="prod"' \]

     receiver: pagerduty-high

   \- matchers: \[ 'env="staging"' \]

     receiver: slack-staging

receivers:

 \- name: slack-sev

   slack\_configs:

     \- channel: '\#pulpo-sev'

       send\_resolved: true

 \- name: pagerduty-high

   pagerduty\_configs: \[{ routing\_key: 'PD\_KEY' }\]

8. Runbook (estructura mínima por alerta)

* **Causa probable**, **Pasos de verificación** (Grafana, Tempo, logs), **Rollback/mitigación**, **Propietario** (servicio), **SLO afectado**.

9. Registro Vivo actualizado  
    Fase: 5 — Observabilidad y seguridad  
    Microflujos: F-Alerts (implementación de reglas)  
    Estado: en progreso | Prioridad: \[P1\]  
    Dependencias: métricas expuestas, recording rules, Alertmanager rutas.  
    Observaciones: activar “silence on deploy” y etiqueta `version` para correlación con releases.

---

**9.7 SLAs (Service Level Agreements)**

**Disponibilidad**

* Uptime mensual ≥ 99.5% (≈ 3.6 h caídas).

* Scope: Core API y endpoints críticos (/auth, /messages, /actions). Servicios auxiliares (n8n, Qdrant, Ollama) se consideran parte del stack pero no tienen SLA independiente.

**Tiempo de respuesta (p95)**

* Conversaciones: \< 3s (excluye cold starts de modelo).

* Ingesta: documento ≤100 páginas \< 5 min. Documentos grandes se procesan en lotes de 100 páginas con SLA proporcional.

* Webhooks (WhatsApp/otros): acuse \< 2s, procesamiento asíncrono posterior.

**Soporte por plan**

* Plan Basic → email, tiempo de respuesta \< 72h hábiles.

* Plan RAG → email \+ portal, tiempo de respuesta \< 48h hábiles.

* Plan Agent → canal prioritario (Slack/WhatsApp/portal) \< 12h corridas.

* Horario de cobertura inicial: lunes a viernes 9–18h (GMT-3).

**Alcance y exclusiones**

* Mantenimiento planificado se notifica con 48h de anticipación y no cuenta como downtime.

* Incidentes derivados de terceros (BSP WhatsApp, Google APIs, proveedores cloud) quedan fuera del SLA.

* Sin créditos financieros en esta etapa; se revisará en futuras versiones.

---

**9.8 Integración con flujos de n8n**

 Cada flujo (F-00 a F-DeadLetter) expone métricas vía Prometheus Exporter:

* **Latencia:** duración start→end en segundos (histogram).

* **Estado:** success|error (counter).

* **Errores:** cada fallo genera evento en `F-Alerts`, que publica alerta en canal correspondiente.

* **Dead Letters:** métrica `dlq_size` monitorizable en Grafana, con alerta si \> 10 mensajes pendientes.

* **Reintentos:** cada retry incrementa métrica `flow_retries_total`.

---

**9.9 Checklist de aceptación**

* Logs JSON estructurados con `request_id` y sin PII sensible (solo IDs).

* Métricas de negocio, LLM e infraestructura recolectadas en Prometheus.

* Tracing OTEL habilitado, visible en Jaeger y Grafana.

* Dashboards internos en Grafana; dashboard resumido disponible en Pulpo App para clientes.

* Alertas configuradas para SEV-1/2/3 con destinos diferenciados:

  * SEV-1 → PagerDuty/WhatsApp on-call.

  * SEV-2 → Slack canal \#oncall.

  * SEV-3 → email semanal al equipo.

* SLA definidos en 9.7 y comunicados en la documentación pública.

# **10\. Seguridad y Cumplimiento**

## **10.1 Objetivo**

Garantizar que Pulpo proteja los datos de clientes y contactos finales, cumpla con normativas de privacidad, mantenga resiliencia operativa y prevenga abusos de la plataforma.

---

**10.2 Protección de PII (Personally Identifiable Information)**

* **PII primaria**: teléfonos (contacts.user\_phone), emails, direcciones.

* **PII sensible opcional**: ingresos (inmobiliaria), nombres en reservas, etc.

**Medidas**:

* **Cifrado en tránsito**: TLS 1.2+ obligatorio.

* **Cifrado en reposo**:

  * Postgres: discos cifrados.

  * MinIO/S3: SSE-KMS (AES-256).

* **Hash en reposo**: api\_keys.key\_hash (Argon2id).

* **Acceso restringido**:

  * RLS en Postgres por workspace\_id.

  * Roles DB: solo Core API accede directamente.

* **Sanitización logs**: nunca loguear contenido de mensajes; solo IDs.

* **Clasificación obligatoria**: documentos o registros con PII deben marcarse con `sensitivity=pii` para activar políticas adicionales de acceso y retención.

---

* ## **10.3 Row-Level Security (RLS)**

* Tablas con RLS habilitado: **workspaces, workspace\_members, channels, contacts, conversations, messages, faqs, handoff\_tickets, workspace\_configs, documentos/RAG**.  
* **Política**:

USING (workspace\_id \= current\_setting('app.workspace\_id', true)::uuid)

WITH CHECK (workspace\_id \= current\_setting('app.workspace\_id', true)::uuid)

**Seteo de contexto**:

* Toda request fija `SET LOCAL app.workspace_id = '{ws_id}'`.

* Funciones SQL lo reafirman para evitar “context bleed”.

**Beneficio**: aislamiento completo cross-tenant.  
 **QA**: tests automáticos verifican que un usuario nunca puede acceder a datos de otro workspace.

---

## **10.4 Backups y recuperación**

* **Postgres**: snapshots diarios (30 días), WAL archiving 5 min, restore test mensual auditado.

* **MinIO/S3**: versioning activo, replicación cross-region.

* **Redis**: sin backup (solo cache).

**Plan de recuperación**:

* RTO \= 1h, RPO \= 5 min.

* Procedimiento documentado \+ checklist de restore auditado (quién ejecuta, resultado).

---

## **10.5 Cumplimiento estilo GDPR/CCPA**

* **Acceso**: `/me/data/export` → JSON \+ ZIP de documentos.

* **Olvido**: `/contacts/{id}/delete` → elimina mensajes, docs vinculados.

* **Portabilidad**: export en JSON \+ CSV para interoperabilidad.

* **Consentimiento**: owner confirma ToS y privacidad; registro en audit\_logs.

* **Data minimization**: solo datos necesarios.

* **Residencia**: AWS sa-east-1 inicial; soporte multi-región en roadmap.

---

## **10.6 Estrategias anti-abuso**

* **Rate limiting**: por workspace, contacto y API key.

* **Flood control**: \>10 mensajes en 30s → throttle.

* **Spam**: detectar \>100 outbound en 5 min sin interacción.

* **Prompt injection defense**: limpiar instrucciones peligrosas \+ loguear intentos.

* **Document poisoning defense**: hash \+ scan antivirus; límites 20 MB y 500 páginas; flag `sensitivity=pii`.

* **API keys**: soporte a expiración opcional y rotación forzada.

---

## **10.7 Seguridad de integraciones externas**

* **WhatsApp BSP**: validar firma X-Hub-Signature-256, idempotencia con wa\_message\_id.

* **Calendarios/POS/CRM**: tokens en `integration_tokens` cifrados (AES-256 \+ KMS), rotación cada 90 días, uso de **refresh tokens rotativos** donde el proveedor lo soporte.

* **n8n**: ejecuta en VPC privada, flujos aislados.

---

## **10.8 Secret management**

* **Dev**: `.env.local` (solo pruebas).

* **Prod**: Vault/Doppler/AWS Secrets Manager.

* **Rotación**: JWT signing keys cada 90 días vía JWKS.

* **Convenciones**:

  * `PULPO_JWT_PRIVATE_KEY`

  * `WHATSAPP_APP_SECRET`

  * `DB_URL`, `REDIS_URL`, `S3_ACCESS_KEY`

---

## **10.9 Endpoints sensibles y protección**

* **/auth/**: lock tras 5 intentos fallidos, cooldown 15 min.

* **/documents/upload**: validar MIME, antivirus (ClamAV).

* **/actions/execute**: confirmación obligatoria, inputs validados, límite 5/min por contacto.

* **Protecciones front**: CSRF tokens y Content-Security-Policy (CSP) activas.

---

## **10.10 Check de cumplimiento**

* RLS activo en todas las tablas core.

* Cifrado en tránsito y reposo.

* Backups \+ restore test mensual auditado.

* GDPR: endpoints export/delete.

* Rate limits \+ flood control.

* Mitigación de prompt injection y doc poisoning.

* Secrets en Vault/Doppler.

* Antivirus en uploads.

* Pentest anual y escaneo continuo de dependencias/imágenes Docker.

* Auditoría de acciones sensibles en audit\_logs.

---

## **10.11 SLA de seguridad**

* Vulnerabilidad crítica: parche \<72h.

* Exposición de datos: notificación \<24h al cliente.

* Backup restore test mensual.

* Rotación de claves: 90 días o ante incidente.

* **Monitoreo**: Security Officer revisa cumplimiento SLA mensualmente y publica reporte interno.

  # **11\. Facturación y Planes**

  ## **11.1 Objetivo**

Gestionar planes de suscripción multi-tenant, con límites de uso claros, facturación automática y soporte para múltiples pasarelas de pago (Stripe, MercadoPago, Cripto).

---

## **11.2 Estructura de planes**

### **11.2.1 Catálogo inicial**

* **Empleado**: 3.000 conversaciones, 200 docs/mes, 300 acciones/mes.

* **Avanzado**: 8.000 conversaciones, 500 docs/mes, 1.000 acciones/mes, integraciones Google.

* **Premium**: 20.000 conversaciones, 1.000 docs/mes, 3.000 acciones/mes, integraciones externas y soporte prioritario.

📌 **Nota**: Excedentes → throttle suave \+ sugerencia de upgrade.

---

### **11.2.2 Tabla `plans`**

* `plans (`  
*  `id uuid pk,`  
*  `name text,           -- empleado, avanzado, premium`  
*  `price_usd numeric,`  
*  `limits_json jsonb,   -- { messages:5000, documents:200, actions:500 }`  
*  `policy_json jsonb,   -- default configs`  
*  `created_at, updated_at`  
* `)`  
    
  ---

  ### **11.2.3 Asociación con workspaces**

Tabla `workspace_plans`:

* workspace\_id

* plan\_id

* status (trial, active, canceled)

* current\_period\_start, current\_period\_end

* payment\_provider (stripe, mpago, crypto)

* subscription\_id (referencia en provider)

* **grace\_period\_end** (fecha límite de uso tras fallo de pago)

  ---

  ## **11.3 Pasarelas de pago**

  ### **11.3.1 Stripe (USD, internacional)**

* Checkout Session → tarjeta o wallet.

* Suscripción: se crea en Stripe con ciclo mensual.

* Webhooks:

  * invoice.paid → activar/renovar workspace\_plan.

  * invoice.payment\_failed → marcar status=grace\_period.

  * customer.subscription.deleted → status=canceled.

📌 Verificación antifraude: validar firma/webhook y conciliar invoice\_id con provider.

---

### **11.3.2 MercadoPago (ARS, Argentina)**

* Preferencia de pago: monto en ARS, con webhook.

* Renovación automática: vía “suscripción recurrente” (beta).

* Webhooks:

  * payment.created y payment.approved.

* Conversión: 1 USD \= cotización BNA \+ markup.

📌 Verificación antifraude: validar firma/webhook y conciliar invoice\_id con provider.

---

### **11.3.3 Cripto (opcional, fase 2\)**

* Via Coinbase Commerce o BitPay.

* Uso puntual para clientes internacionales sin Stripe.

  ---

  ## **11.4 Ciclo de facturación**

* Workspace nuevo → trial (14 días).

* Al terminar trial:

  * Si no hay pago → status=inactive.

  * Si hay pago → status=active.

* Cada período:

  * Core API calcula usage\_counters.

  * Si excede límites → throttle suave (avisos) o upsell.

* Renovación automática: Stripe/MercadoPago informan vía webhook.

* Cancelación: se mantiene acceso hasta current\_period\_end.

  ---

  ## **11.5 Cálculo de uso**

Tabla `usage_counters` (por día, workspace):

* messages\_in, messages\_out

* tokens\_prompt, tokens\_completion

* documents\_ingested, storage\_mb

* actions\_executed

* **concurrent\_sessions** (conexiones simultáneas activas)

📌 Agregación mensual \= suma de días.  
 📌 Core API expone `/usage/current` para dashboard y facturación.

---

## **11.6 Pricing y upsell**

* Basic: bajo precio, objetivo cubrir costos iniciales.

* RAG: margen intermedio, valor real para PyMEs.

* Agent: premium, con acciones que ahorran tiempo humano.

Upsell dinámico:

* Si workspace excede 80% de límite → alerta en dashboard.

* Ofrecer upgrade con un click.

  ---

  ## **11.7 Facturación multimoneda**

* Stripe \= USD (precio fijo).

* MercadoPago \= ARS (precio dinámico, conversión diaria).

* Core guarda ambos precios en plans.price\_usd y plans.price\_ars.

* Al mostrar en dashboard:

  * Si workspace → payment\_provider \= mpago, mostrar ARS.

  * Si stripe, mostrar USD.

📌 Guardar tipo de cambio aplicado en `invoices.rate_used` para trazabilidad.

---

## **11.8 Impuestos y facturación legal**

* **Argentina**:

  * MercadoPago → Pulpo como responsable inscripto.

  * IVA discriminado en comprobante.

* **Internacional**:

  * Stripe genera factura con datos de Pulpo.

  * Impuestos (IVA/VAT) manejados por Stripe Tax si habilitado.

Registro en DB → tabla `invoices`:

* invoice\_id (del provider)

* workspace\_id

* amount

* currency

* status

* pdf\_url (descargable desde provider)

* **rate\_used** (para ARS/USD)

* **tax\_json** (IVA/VAT, percepciones o retenciones)

  ---

  ## **11.9 Integración con Dashboard Pulpo**

Sección Planes y Facturación:

* Ver plan actual, precio, fecha de renovación.

* Ver uso vs límites (barras de progreso).

* Botón Upgrade (redirige a Stripe Checkout o MP).

* Historial de facturas descargables.

* Alertas de “excediste tu plan”.

  ---

  ## **11.10 Alertas internas (equipo Pulpo)**

* Webhook fallido de Stripe/MP → alerta SEV-2.

* Workspace sin pago \>7 días → marcar inactive.

* % de workspaces en trial que convierten → métrica de negocio.

* **Churn mensual: % de cancelaciones sobre base activa.**

  ---

  ## **11.11 Checklist de aceptación**

* Planes definidos en tabla plans con límites claros.

* Asociar plan con workspace y ciclo de facturación.

* Stripe funcionando (USD), MercadoPago funcionando (ARS).

* Webhooks de pago procesados y auditados.

* Usage tracking diario → agregación mensual.

* Dashboard muestra plan, uso y facturas.

* Upsell automático al 80% de límite.

* **Facturas legales generadas correctamente con impuestos (IVA/VAT).**

# **12\. Integraciones Externas**

### **12.1 Objetivo**

Conectar **Pulpo** con sistemas externos críticos (calendarios, POS, CRMs, e-commerce, pagos y soporte) de forma **segura, modular y extensible**, permitiendo a cada vertical aprovechar sus herramientas sin duplicar datos.

La meta es:

* Mejorar la productividad automatizando la comunicación entre Pulpo y herramientas del negocio.

* Mantener la **seguridad y el aislamiento multi-tenant** (cada workspace sólo accede a sus integraciones).

* Garantizar **resiliencia** con retries, DLQ y monitoreo de errores.

* Ofrecer **portabilidad** con un diseño de adapters que abstraiga la API externa y mantenga un contrato estándar en Pulpo.


### **12.2 Arquitectura de integraciones**

Action API \= capa central que recibe `actions.execute`.

Adapters \= plugins que traducen entre contrato estándar Pulpo ↔ API externo.

Integration tokens \= tabla que almacena credenciales/tokens, cifrados con KMS.

Scopes \= por vertical (ej. inmobiliaria \= Google Calendar, gastronomía \= POS).

Outbox pattern \= cada acción ejecutada genera un evento en `event_outbox` → n8n puede despachar a integraciones.

Además, cada adapter implementa **rate limiting interno** y **circuit breaker** para protegerse de bloqueos externos. Toda invocación se registra en `audit_logs` con `integration=provider`, `status` y `latency_ms`, para trazabilidad completa.

---

### **12.3 Almacenamiento de tokens**

Tabla `integration_tokens`:

* id, workspace\_id, provider (google, shopify, mpago, sheets)

* access\_token, refresh\_token, expires\_at

* scopes\[\]

* encrypted=true (AES-256 con master key)

* last\_refresh\_at (última vez que se renovó el token)

* revoked\_at, revoked\_reason (auditoría de desconexión)

Rotación:

* Al expirar, refrescar token automáticamente.

* Notificar si el refresh falla.

Gestión en Dashboard:

* Sección Integraciones: conectar con Google/Shopify/etc.

* UI con OAuth dance o input de API key.

* Mostrar estado (válido / expirado).

Cambios de scopes y revocaciones se registran en `audit_logs` para trazabilidad completa.

---

## **12.4 Integraciones iniciales**

#### **12.4.1 Google Calendar (inmobiliaria)**

* **Uso**: acción `crear_visita`.

* **Flujo**:

  * Workspace conecta Google Calendar (OAuth2).

  * Al reservar, Action API crea evento vía Calendar API.

  * Retorna `event_id`, link y estado.

* **Campos requeridos**:

  * `summary`: “Visita propiedad X”.

  * `attendees`: cliente \+ asesor.

  * `start/end` en formato ISO8601.

* **Fallback**: si falla integración, guardar en tabla `visitas_pendientes` y notificar al asesor.

#### **12.4.2 Google Sheets (gastronomía / pedidos simples)**

* **Uso**: acción `crear_pedido`.

* **Flujo**:

  1. Workspace conecta Google Sheets (OAuth2).

  2. Al ejecutar acción, se agrega fila:  
      `fecha, hora, cliente, items, estado="pendiente"`.

  3. Retorna: `{row_id}`.

* **Fallback**: si no hay hoja conectada, registrar en tabla `pedidos` con estado `"offline"` y enviar alerta al owner.

#### **12.4.3 POS local (gastronomía)**

* **Ejemplos**: Lapos / Poster POS / API del restaurante.

* **Flujo**:

  1. Configuración vía API key o endpoint local.

  2. Al crear pedido/reserva, Action API hace `POST /orders`.

  3. Retorna `{order_id, status}`.

* **Guardrails**: timeout máximo 5s; si falla → fallback a Google Sheets (si disponible).

#### **12.4.4 E-commerce (Shopify / MercadoLibre)**

* **Shopify**

  * Uso: `cotizar`, `iniciar_checkout`.

  * API GraphQL: crear checkout, obtener URL.

  * Retorno: `{checkout_id, checkout_url}`.

* **MercadoLibre**

  * Uso: `consultar_estado_pedido`.

  * API REST: `GET /orders/{id}`.

  * Tokens gestionados en `integration_tokens`.

---

### **12.5 Contratos JSON por integración**

#### **Ejemplo: `crear_visita` con Google Calendar**

**Request**

`{`  
  `"workspace_id": "ws-uuid",`  
  `"type": "crear_visita",`  
  `"input": {`  
    `"fecha": "2025-09-12",`  
    `"hora": "15:00",`  
    `"property_id": "p-102",`  
    `"cliente": {`  
      `"nombre": "Ana",`  
      `"telefono": "54911..."`  
    `}`  
  `}`  
`}`

**Response**

`{`  
  `"ok": true,`  
  `"data": {`  
    `"event_id": "google-event-123",`  
    `"html_link": "https://calendar.google.com/event?eid=...",`  
    `"status": "confirmed"`  
  `},`  
  `"message": "Visita confirmada el 2025-09-12 15:00 para Ana."`  
`}`

---

#### **Ejemplo: `crear_pedido` con Google Sheets**

**Fila creada en la hoja**

`2025-09-12, 13:45, Nico, "Pizza Muzzarella x2, Gaseosa x1", pendiente`

**Response**

`{`  
  `"ok": true,`  
  `"data": { "row_id": 35 },`  
  `"message": "Pedido registrado en hoja de pedidos."`  
`}`

---

#### **Ejemplo: `iniciar_checkout` con Shopify**

**Request**

`{`  
  `"workspace_id": "ws-uuid",`  
  `"type": "iniciar_checkout",`  
  `"input": {`  
    `"items": [`  
      `{ "sku": "iph-13-256", "cantidad": 1 },`  
      `{ "sku": "case-prot-1", "cantidad": 2 }`  
    `]`  
  `}`  
`}`

**Response**

`{`  
  `"ok": true,`  
  `"data": {`  
    `"checkout_id": "chk-90413",`  
    `"checkout_url": "https://shopify.com/checkout/chk-90413"`  
  `},`  
  `"message": "Checkout iniciado, seguí el link para completar la compra."`  
`}`

### **12.6 Gestión de errores**

**Casos principales:**

1. **Token inválido o expirado**

**Respuesta**:

 `{`

  `"ok": false,`

  `"error": "integration_auth_failed",`

  `"message": "La integración expiró o no es válida. Reconectá tu cuenta."`

`}`

*   
  * **Acciones**:

    * Action API devuelve `401 integration_auth_failed`.

    * Dashboard muestra banner **“Reconectar integración”**.

    * Se registra en `audit_logs(action="integration_auth_failed")`.

---

2. **Timeout o error externo**

**Respuesta**:

 `{`

  `"ok": false,`

  `"error": "integration_timeout",`

  `"message": "No se pudo confirmar con el sistema externo, intentá más tarde."`

`}`

*   
  * **Acciones**:

    * Se marca `actions.status="failed"`.

    * Se notifica al usuario con mensaje claro.

    * Se registra latencia en métricas.

---

3. **Validación de input fallida**

**Respuesta**:

 `{`

  `"ok": false,`

  `"error": "invalid_input",`

  `"message": "El campo 'fecha' debe estar en formato AAAA-MM-DD."`

`}`

*   
  * **Acciones**:

    * Validación previa con JSON Schema/Zod antes de llamar API externa.

    * Se guarda `actions.status="failed"`.

    * Input rechazado nunca llega al provider externo.

---

4. **Auditoría de errores**

   * Todos los errores se guardan en `actions.input_json` \+ `actions.output_json`.

   * Si contienen PII sensible, se redacta antes de almacenar.

Ejemplo en `audit_logs`:

 `{`

  `"action": "action_failed",`

  `"workspace_id": "ws-123",`

  `"type": "crear_pedido",`

  `"error": "integration_timeout"`

* `}`

---

### **12.7 Métricas de integraciones**

1. Objetivo  
    Medir salud y efectividad de cada integración (Calendar/Sheets/Shopify/…): éxito, latencia, errores y caducidad de tokens para accionar alertas y mejoras.

2. Entradas / Salidas (JSON schema breve)  
    Entrada (evento Action API → Metrics):

`{`  
  `"workspace_id":"uuid",`  
  `"provider":"google_calendar|google_sheets|shopify|mpago|…",`  
  `"integration_type":"calendar|sheet|ecommerce|…",`  
  `"action_type":"crear_visita|crear_pedido|…",`  
  `"result":"success|failed|timeout|auth_failed",`  
  `"latency_ms": 842,`  
  `"ts":"2025-09-17T12:34:56Z"`  
`}`

Salida (series/labels Prometheus):

* `pulpo_integration_calls_total{provider,action_type,result}` (counter)

* `pulpo_integration_latency_ms{provider,action_type}` (histogram)

* `pulpo_integration_token_expiry_days{provider}` (gauge)

* `pulpo_integration_error_ratio{provider}` (recording rule)

3. Diseño / Proceso

* Emisión: Action API emite métrica por cada ejecución (success/fail).

* Latencia: medir `t_end - t_start` por acción.

* Agrupación: labels `{workspace_id(optional_hash), provider, action_type, vertical}`.

* Token health: job horario calcula `days_to_expiry = (expires_at - now)` por token y publica gauge.

* Recording rules:

  * `error_ratio = rate(pulpo_integration_calls_total{result!="success"}[5m]) / rate(pulpo_integration_calls_total[5m])`

* Alertas (resumen, las reglas completas están en 9.6):

  * `error_ratio > 0.2 for 10m` → SEV-2

  * `token_expiry_days < 7` y `count_by_ws > 0` → warning proactivo

  * `p95_latency_ms > 3000 for 10m` → SEV-2

* Dashboard (Grafana):

  * Barras: éxito/fallo por provider (stacked)

  * Heatmap: p95/p99 latencia por action\_type

  * Tabla: workspaces con tokens por expirar (\<7 días)

4. QA (aceptación)

* Simular 20 éxitos y 5 fallos → `error_ratio ≈ 0.20`.

* Inyectar latencias sintéticas (100ms, 800ms, 3s) → p95 concuerda.

* Setear `expires_at` a 5 días → gauge refleja 5 y dispara alerta de expiración.

* Apagar un provider (timeouts) → regla SEV-2 activa en \<10 min.

5. Riesgos / Troubleshooting

* **Cardinalidad alta por workspace\_id**: usar `workspace_bucket` (hash/ten-range) en métricas públicas y mantener `workspace_id` solo en logs/traces.

* **Picos de latencia del provider**: corroborar con `up` del exporter y logs HTTP (5xx vs timeouts).

* **Tokens mal cargados**: verificar `integration_tokens.expires_at` y reintentos de refresh en logs de Action API.

* **Desbalance por vertical**: segmentar panel por `vertical` para no ocultar fallas en nichos.

---

### **12.8 Roadmap de integraciones**

* **Fase 1 (MVP)**: Google Calendar, Google Sheets, Shopify.

* **Fase 2**: MercadoLibre, POS locales, MercadoPago (pagos dentro del chat).

* **Fase 3**: CRMs verticales (Tokko Broker, HubSpot), sistemas legales y salud (turnos médicos).

* **Fase 4**: Integraciones omnicanal (Instagram, Facebook Messenger, email).

---

### **12.9 Checklist de aceptación**

* Adapters implementados en Action API para Google Calendar, Google Sheets y Shopify.

* Tokens almacenados cifrados (AES-256 con KMS) y refrescados automáticamente.

* Dashboard con gestión de integraciones (conectar, reconectar, ver estado).

* Contratos JSON homogéneos y documentados para todas las integraciones.

* Errores auditados en actions y audit\_logs, con fallback visible para el usuario.

* Métricas de éxito/fallo y latencia expuestas en Prometheus.

# **13\. Dashboard y Experiencia de Usuario**

### **13.1 Objetivo**

Mantener la operación de Pulpo sostenible y escalable, con control proactivo de costos (infraestructura, LLM, storage, integraciones) y herramientas de optimización que permitan reaccionar rápido a desvíos.

---

### **13.2 Categorías de costos**

* **Infraestructura Core**: Postgres, Redis, n8n, Ollama/LLMs, almacenamiento en MinIO/S3.

* **LLM inference**: tokens prompt \+ completion, embeddings, modelos especializados.

* **Integraciones externas**: APIs de terceros con pricing (Google, Shopify, MP).

* **Networking**: ancho de banda de salida (whatsapp, integraciones).

* **Soporte y operaciones**: monitoreo, backups, alertas.

---

### **13.3 Medición y métricas**

* **LLM**: tokens\_in, tokens\_out, costo estimado USD (x modelo).

* **Infraestructura**: uso de CPU/RAM/Storage por servicio (Prometheus \+ Grafana).

* **Networking**: GB/mes enviados, asociado a workspace\_id.

* **Integraciones**: número de llamadas API externas.

* **Costos por workspace**: vista consolidada `workspace_costs` \= { infra\_share, llm\_cost, storage\_cost, total }.

---

### **13.4 Optimización de costos**

* **LLM**:

  * Cache de embeddings.

  * Reuso de contexto (short memory).

  * Modelos locales para consultas low-value (ej: Ollama para FAQ).

  * Switch dinámico: modelos más baratos para intents simples.

* **Infraestructura**:

  * Autoescalado horizontal de workers.

  * Cold storage (archivar docs viejos en S3 IA o Glacier).

  * Redis eviction policy en caché temporal.

* **Integraciones**:

  * Rate limit estricto a APIs externas.

  * Retry con backoff exponencial en lugar de loops agresivos.

---

### **13.5 Dashboards de costos**

* **Interno (Pulpo Ops)**: costo diario y acumulado por workspace, top 10 workspaces más caros, breakdown por categoría.

* **Cliente (Pulpo App)**: uso vs límites del plan \+ alerta de “excediste X% de tu cuota” con sugerencia de upgrade.

---

### **13.6 Alertas de costos**

* **Overbudget global**: si gastos totales \>120% del forecast mensual → alerta SEV-2.

* **Workspace individual**: si workspace excede 150% de su cuota → alerta interna \+ upsell automático.

* **Token spike**: si tokens\_increase \>5x en 1h → alerta SEV-1 (posible abuso).

---

### **13.7 Checklist de aceptación**

* Métricas de costos integradas en Prometheus.

* Tablas de uso (usage\_counters, workspace\_costs) actualizadas diariamente.

* Dashboards de costos internos y visibles en Pulpo App.

* Políticas de optimización habilitadas (cache embeddings, modelos locales).

* Alertas configuradas por desvío de costos.

# 

# **14\. DevOps y Despliegue**

14.1 Objetivo

Garantizar que Pulpo pueda desplegarse, escalar y mantenerse de forma segura, reproducible y con mínima fricción, soportando entornos dev, staging y prod.

14.2 Entornos

 Dev: local (Docker Compose) \+ cluster compartido dev.  
 Staging: cluster Kubernetes espejo de prod, con datos ficticios y llaves sandbox.  
 Prod: cluster Kubernetes dedicado, alta disponibilidad.  
 Separación estricta de credenciales y bases de datos.

14.3 Orquestación

 Kubernetes (EKS/GKE).  
 Namespaces: pulpo-dev, pulpo-stg, pulpo-prod.  
 Services: core-api, message-api, rag-api, action-api, jobs/usage, n8n, dashboard-app.  
 Ingress: NGINX Ingress \+ cert-manager (TLS).

14.4 CI/CD

Monorepo (TurboRepo). GitHub Actions / GitLab CI.  
 Stages:

* Build: Docker multi-stage.

* Test: unit \+ integration \+ lint \+ type-check.

* Security: Snyk/Trivy (todas las imágenes antes del push).

* DB migrations con rollback automático.

* Push: imágenes a registry (ECR/GCR).

* Deploy: Helm/kubectl apply.  
   Policy:

* Push a main → deploy a staging.

* Tag vX.Y.Z → deploy a prod (con aprobación manual).

14.5 Observabilidad  
 Logging: Fluent Bit → Loki/ELK.  
 Métricas: Prometheus \+ Grafana.  
 Tracing: OpenTelemetry → Jaeger/Tempo.  
 Dashboards: KPIs internos \+ métricas SaaS.  
 Alertas extra: CrashLoopBackOff, ImagePullBackOff.

14.6 Escalado y HA  
 APIs stateless: HPA (CPU \>70% o requests \> X/s).  
 Postgres: RDS/CloudSQL con replicación \+ read replicas para queries pesadas.  
 Redis: cluster con persistencia AOF.  
 MinIO/S3: buckets multi-AZ.  
 PodDisruptionBudgets para disponibilidad en upgrades.

14.7 Secretos y configuración  
 Dev: .env.local.  
 Staging/Prod: Kubernetes Secrets gestionados por Vault/Doppler.  
 Secrets en env vars.  
 Variables críticas: DB\_URL, REDIS\_URL, S3\_ACCESS\_KEY, JWT\_PRIVATE\_KEY, WHATSAPP\_APP\_SECRET, STRIPE\_SECRET\_KEY, MPAGO\_ACCESS\_TOKEN.  
 Forzar encryption at rest en etcd.

14.8 Estrategia de despliegue  
 Blue/Green con rollback (últimas 3 imágenes).  
 Canary opcional: 10% tráfico → 100%.  
 Warm-up antes del 100% cutover.

14.9 Testing  
 Unit tests: lógica de negocio.  
 Integration tests: RAG search, actions dummy.  
 Contract tests: JSON n8n \+ Action API.  
 E2E tests: webhook → IA → acción.  
 Load tests: K6.  
 Security tests: brute force /auth, injection /actions.

14.10 Cost management  
 Tags en recursos cloud: project=pulpo, env=prod.  
 Autoscaling para evitar sobrecapacidad.  
 Alertas de billing: \>80% presupuesto mensual.  
 Monitor de crecimiento en storage (S3/MinIO).  
 Cache en Redis para reducir uso LLM.

14.11 DRP (Disaster Recovery Plan)  
 Backups:

* Postgres: snapshot \+ WAL (RPO 5min).

* MinIO: replicado cross-region.  
   Procedimientos:

* Restaurar DB desde snapshot.

* Rehidratar cluster con Helm \+ images.  
   Objetivos: RTO=1h, RPO=5min.  
   Fire drill semestral.

14.12 Checklist de aceptación

 Infra en Kubernetes con namespaces por entorno.  
 CI/CD con tests \+ escaneo de seguridad.  
 Logs centralizados \+ métricas \+ tracing.  
 HA con autoscaling \+ DB replicada.  
 PodDisruptionBudgets definidos.  
 Secrets en Vault/Doppler, encryption en etcd.  
 Blue/Green con rollback.  
 DRP probado y documentado.  
 Alertas de costo activas.

# **15\. Roadmap y Etapas de Implementación**

15.1 Objetivo  
 Definir un plan evolutivo claro para Pulpo, con hitos técnicos y de negocio, junto con un modelo de gobernanza que asegure calidad, seguridad y escalabilidad en el tiempo.

15.2 Fases de evolución  
 Fase 1 (MVP):

* Verticales básicas (inmobiliaria, gastronomía, e-commerce).

* Acciones iniciales (reservas, pedidos, visitas).

* RAG con ingestión de documentos y respuestas básicas.

Fase 2 (Consolidación):

* Planes de suscripción con facturación automática.

* Integraciones externas mínimas (Google Calendar, Google Sheets, Shopify).

* Dashboard con métricas de uso y gestión de planes.

* Auditoría completa y SLA iniciales.

Fase 3 (Escalado):

* Multi-región (clusters en distintas regiones).

* Integraciones avanzadas (MercadoLibre, POS locales, CRM).

* Roles y permisos detallados con scopes por API key.

* Reportes financieros y métricas de negocio avanzadas.

Fase 4 (Enterprise):

* Omnicanal (Instagram, Facebook Messenger, email).

* Pagos integrados en el chat (Stripe, MercadoPago).

* Planes enterprise con soporte dedicado y uptime garantizado.

* Certificaciones de seguridad (ISO 27001, SOC2).

15.3 Gobernanza técnica

* Comité técnico interno: revisa cambios de arquitectura y seguridad.

* Código en monorepo con PR reviews obligatorias.

* Feature flags para lanzamientos controlados.

* Auditoría de dependencias y librerías externas cada 3 meses.

15.4 Gobernanza de producto

* Roadmap público parcial para clientes.

* Feedback de clientes vía dashboard (feature requests).

* Priorización por impacto en verticales clave.

* Releases comunicados en changelog central.

15.5 Gobernanza de datos

* Política de retención clara (ej. mensajes \= 18 meses).

* Export y delete habilitados (cumplimiento GDPR/CCPA).

* Control estricto de accesos a datos sensibles.

* Auditoría continua sobre accesos de superadmin.

15.6 Métricas de éxito

* Conversión trial → pago.

* Retención mensual por vertical.

* Acciones ejecutadas/mes.

* Tasa de errores de integración \< 2%.

* Tiempo medio de respuesta \< 3s en 95% de requests.

15.7 Checklist de aceptación

* Roadmap documentado y aprobado.

* Comité técnico definido con procesos claros.

* Feature flags implementados en core API.

* Políticas de retención y auditoría activas.

* Métricas de éxito definidas y monitoreadas en dashboard.

---

## **16. Extensiones del Sistema**

### **16.1 Extensión E-01 — Dialogue State Tracking**

#### **16.1.1 Objetivo**

Mantener y orquestar el estado conversacional (intent, slots, fsm_state, next_action) por conversación, con persistencia en PostgreSQL + RLS y contratos API para el Orchestrator y n8n.

#### **16.1.2 Entradas / Salidas (JSON Schema breve)**

```json
// DialogueState
{
  "workspace_id": "uuid",
  "conversation_id": "uuid", 
  "fsm_state": "string",
  "intent": "string|null",
  "slots": {"type": "object", "additionalProperties": true},
  "next_action": {"type": "string", "enum": ["answer", "tool_call", "handoff", "wait"]},
  "meta": {"type": "object", "additionalProperties": true},
  "updated_at": "string"
}

// Events (para transiciones)
{
  "event": "user_msg|system|tool_result",
  "payload": {"type": "object", "additionalProperties": true}
}
```

#### **16.1.3 Diseño / Proceso**

**Tablas (núcleo)**
- `pulpo.dialogue_states` (1 row vigente por conversación)
- `pulpo.dialogue_state_history` (append-only de cambios)
- `pulpo.dialogue_slots` (KV tipado opcional por slot_name)

**Funciones**
- `pulpo.upsert_dialogue_state(wid, cid, fsm_state, intent, slots, next_action, meta)` → idempotente
- `pulpo.apply_event(wid, cid, event, payload)` → evalúa transición FSM (pure-SQL/PLpgSQL) y persiste

**RLS**
- Policies por workspace_id; FKs compuestas (workspace_id, conversation_id) coherentes

**API (orchestrator)**
- `GET /dialogue/state?workspace_id&conversation_id`
- `POST /dialogue/events` (aplica transición)
- `PATCH /dialogue/slots` (merge / unset)

**FSM mínimo (gastronomía)**
- START → COLLECTING → CONFIRMING → CHECKOUT → DONE (+ HANDOFF)
- Eventos: user_msg, tool_result, confirm_ok, confirm_edit, abort, handoff

#### **16.1.4 QA**

**Unit (SQL)**: transiciones válidas/inválidas, merge de slots, idempotencia upsert

**n8n (F-29)**: simular user_msg→apply_event→leer next_action→branch

**Sanity (SQL)**:
```sql
SELECT pulpo.set_ws_context('<WS_ID>');
SELECT fsm_state,intent,next_action FROM pulpo.dialogue_states WHERE conversation_id='<CID>';
SELECT count(*) FROM pulpo.dialogue_state_history WHERE conversation_id='<CID>';
```

#### **16.1.5 Riesgos / Troubleshooting**

- **RLS**: 403 en API → verificar set_ws_context y policies
- **Carreras**: mensajes simultáneos → usar FOR UPDATE en apply_event
- **Enums ambiguos**: castear explícito ('answer'::pulpo.dialogue_action)
- **Desalineo n8n**: validar orden de nodos F-29 y reintentos con backoff

#### **16.1.6 Motivación**

Hoy no hay state tracking robusto: el Orchestrator decide por turno sin memoria estructurada. E-01 introduce un modelo explícito de diálogo (FSM + slots) persistido con RLS para coherencia multi-tenant y habilita E-02 (Guardrails) y E-03 (RAG) sobre una base estable.

#### **16.1.7 Propuesta concreta**

- Persistencia del estado actual + historial auditable
- FSM declarativa por vertical (inicia con gastronomía)
- Contratos API para leer/actualizar estado desde Orchestrator/n8n
- Integración en el flujo actual: después de persist_inbound, apply_event(user_msg) decide next_action

#### **16.1.8 Contrato (OpenAPI v3 — extracto)**

```yaml
openapi: 3.0.3
info: {title: Pulpo Dialogue API, version: "1.0"}
paths:
  /dialogue/state:
    get:
      parameters:
        - {in: query, name: workspace_id, schema: {type: string, format: uuid}, required: true}
        - {in: query, name: conversation_id, schema: {type: string, format: uuid}, required: true}
      responses:
        "200": {description: OK}
  /dialogue/events:
    post:
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [workspace_id, conversation_id, event]
              properties:
                workspace_id: {type: string, format: uuid}
                conversation_id: {type: string, format: uuid}
                event: {type: string, enum: [user_msg, system, tool_result, confirm_ok, confirm_edit, abort, handoff]}
                payload: {type: object, additionalProperties: true}
      responses: {"200": {description: State updated}}
  /dialogue/slots:
    patch:
      requestBody:
        content:
          application/json:
            schema:
              type: object
              required: [workspace_id, conversation_id]
              properties:
                workspace_id: {type: string, format: uuid}
                conversation_id: {type: string, format: uuid}
                set: {type: object, additionalProperties: true}
                unset: {type: array, items: {type: string}}
      responses: {"200": {description: Slots merged}}
```

#### **16.1.9 Migraciones SQL (UP seguros / DOWN opcional)**

```sql
-- Ejecutar siempre con contexto:
SELECT pulpo.set_ws_context('<WS_ID>');

-- UP (idempotente)
BEGIN;

-- Enums
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='dialogue_action') THEN
    CREATE TYPE pulpo.dialogue_action AS ENUM ('answer','tool_call','handoff','wait');
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='dialogue_event') THEN
    CREATE TYPE pulpo.dialogue_event AS ENUM ('user_msg','system','tool_result','confirm_ok','confirm_edit','abort','handoff');
  END IF;
END$$;

-- Tabla principal
CREATE TABLE IF NOT EXISTS pulpo.dialogue_states (
  workspace_id UUID NOT NULL,
  conversation_id UUID NOT NULL,
  fsm_state TEXT NOT NULL,
  intent TEXT NULL,
  slots JSONB NOT NULL DEFAULT '{}'::jsonb,
  next_action pulpo.dialogue_action NOT NULL DEFAULT 'wait'::pulpo.dialogue_action,
  meta JSONB NOT NULL DEFAULT '{}'::jsonb,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, conversation_id),
  FOREIGN KEY (workspace_id, conversation_id)
    REFERENCES pulpo.conversations(workspace_id, id) ON DELETE CASCADE
);

-- Historial
CREATE TABLE IF NOT EXISTS pulpo.dialogue_state_history (
  workspace_id UUID NOT NULL,
  conversation_id UUID NOT NULL,
  version BIGSERIAL,
  at TIMESTAMPTZ NOT NULL DEFAULT now(),
  event pulpo.dialogue_event NOT NULL,
  prev_state TEXT,
  new_state TEXT,
  intent TEXT,
  slots JSONB,
  next_action pulpo.dialogue_action,
  meta JSONB,
  PRIMARY KEY (workspace_id, conversation_id, version)
);

-- Slots tipados (opcional)
CREATE TABLE IF NOT EXISTS pulpo.dialogue_slots (
  workspace_id UUID NOT NULL,
  conversation_id UUID NOT NULL,
  slot_name TEXT NOT NULL,
  slot_value JSONB NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  PRIMARY KEY (workspace_id, conversation_id, slot_name),
  FOREIGN KEY (workspace_id, conversation_id)
    REFERENCES pulpo.conversations(workspace_id, id) ON DELETE CASCADE
);

-- RLS
ALTER TABLE pulpo.dialogue_states ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_state_history ENABLE ROW LEVEL SECURITY;
ALTER TABLE pulpo.dialogue_slots ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND tablename='dialogue_states' AND policyname='ws_isolation_states') THEN
    CREATE POLICY ws_isolation_states ON pulpo.dialogue_states
      USING (workspace_id = pulpo.current_ws_id());
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND tablename='dialogue_state_history' AND policyname='ws_isolation_states_hist') THEN
    CREATE POLICY ws_isolation_states_hist ON pulpo.dialogue_state_history
      USING (workspace_id = pulpo.current_ws_id());
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE schemaname='pulpo' AND tablename='dialogue_slots' AND policyname='ws_isolation_slots') THEN
    CREATE POLICY ws_isolation_slots ON pulpo.dialogue_slots
      USING (workspace_id = pulpo.current_ws_id());
  END IF;
END$$;

-- Funciones
CREATE OR REPLACE FUNCTION pulpo.upsert_dialogue_state(
  p_workspace_id UUID, p_conversation_id UUID,
  p_fsm_state TEXT, p_intent TEXT, p_slots JSONB,
  p_next_action pulpo.dialogue_action, p_meta JSONB
) RETURNS VOID LANGUAGE plpgsql AS $$
BEGIN
  INSERT INTO pulpo.dialogue_states AS ds
    (workspace_id, conversation_id, fsm_state, intent, slots, next_action, meta, updated_at)
  VALUES
    (p_workspace_id, p_conversation_id, p_fsm_state, p_intent, COALESCE(p_slots,'{}'::jsonb),
     COALESCE(p_next_action,'wait'::pulpo.dialogue_action), COALESCE(p_meta,'{}'::jsonb), now())
  ON CONFLICT (workspace_id, conversation_id) DO UPDATE
  SET fsm_state=EXCLUDED.fsm_state,
      intent=EXCLUDED.intent,
      slots=EXCLUDED.slots,
      next_action=EXCLUDED.next_action,
      meta=EXCLUDED.meta,
      updated_at=now();
END$$;

CREATE OR REPLACE FUNCTION pulpo.apply_event(
  p_workspace_id UUID, p_conversation_id UUID,
  p_event pulpo.dialogue_event, p_payload JSONB DEFAULT '{}'::jsonb
) RETURNS pulpo.dialogue_states LANGUAGE plpgsql AS $$
DECLARE
  cur pulpo.dialogue_states;
  new_state TEXT;
  new_intent TEXT;
  new_slots JSONB;
  new_action pulpo.dialogue_action;
  new_meta JSONB;
BEGIN
  SELECT * INTO cur FROM pulpo.dialogue_states
   WHERE workspace_id=p_workspace_id AND conversation_id=p_conversation_id
   FOR UPDATE;

  IF NOT FOUND THEN
    cur.workspace_id := p_workspace_id;
    cur.conversation_id := p_conversation_id;
    cur.fsm_state := 'START';
    cur.intent := NULL;
    cur.slots := '{}'::jsonb;
    cur.next_action := 'wait'::pulpo.dialogue_action;
    cur.meta := '{}'::jsonb;
  END IF;

  -- FSM mínima (gastronomía)
  new_state := cur.fsm_state;
  new_intent := COALESCE(cur.intent, (p_payload->>'intent'));
  new_slots := cur.slots || COALESCE(p_payload->'slots','{}'::jsonb);
  new_action := cur.next_action;
  new_meta := cur.meta;

  IF p_event = 'user_msg' THEN
    IF cur.fsm_state = 'START' THEN
      new_state := 'COLLECTING'; new_action := 'answer'::pulpo.dialogue_action;
    ELSIF cur.fsm_state = 'COLLECTING' THEN
      -- si slots completos (ej: item + qty) → CONFIRMING
      IF (new_slots ? 'item') AND (new_slots ? 'qty') THEN
        new_state := 'CONFIRMING'; new_action := 'answer'::pulpo.dialogue_action;
      ELSE
        new_state := 'COLLECTING'; new_action := 'answer'::pulpo.dialogue_action;
      END IF;
    ELSIF cur.fsm_state = 'CONFIRMING' THEN
      new_state := 'CONFIRMING'; new_action := 'answer'::pulpo.dialogue_action;
    END IF;
  ELSIF p_event = 'confirm_ok' THEN
    new_state := 'CHECKOUT'; new_action := 'tool_call'::pulpo.dialogue_action;
  ELSIF p_event = 'tool_result' THEN
    new_state := 'DONE'; new_action := 'answer'::pulpo.dialogue_action;
  ELSIF p_event = 'handoff' THEN
    new_state := 'HANDOFF'; new_action := 'handoff'::pulpo.dialogue_action;
  ELSIF p_event = 'abort' THEN
    new_state := 'START'; new_action := 'answer'::pulpo.dialogue_action;
  END IF;

  PERFORM pulpo.upsert_dialogue_state(p_workspace_id,p_conversation_id,new_state,new_intent,new_slots,new_action,new_meta);

  INSERT INTO pulpo.dialogue_state_history
    (workspace_id,conversation_id,event,prev_state,new_state,intent,slots,next_action,meta)
  VALUES
    (p_workspace_id,p_conversation_id,p_event,cur.fsm_state,new_state,new_intent,new_slots,new_action,new_meta);

  RETURN (SELECT ds FROM pulpo.dialogue_states ds WHERE ds.workspace_id=p_workspace_id AND ds.conversation_id=p_conversation_id);
END$$;

COMMIT;
```

#### **16.1.10 Impacto (seguridad / costos)**

- **Seguridad**: RLS por workspace_id; sin acceso cruzado de tenants
- **Costos**: +2–3 escrituras por turno (historial y estado). Impacto bajo; indexación cubierta por PK/compuestas
- **Privacidad**: slots puede contener PII → respetar políticas de retención y minimización

#### **16.1.11 Plan de rollout**

1. **Dev**: aplicar migración; habilitar F-29 en n8n; probar con Twilio Sandbox
2. **Staging**: tráfico espejo con datos ficticios; validar métricas y concurrencia
3. **Prod**: activar para vertical gastronomía; feature flag por workspace_id

#### **16.1.12 Microflujo n8n — F-29 DialogueStateSync**

- **ID**: F-29
- **Trigger**: Webhook pulpo/twilio/wa/inbound (POST)
- **Entradas (schema)**: body.WaId, body.Body, workspace_id, conversation_id
- **Procesamiento (nodos en orden)**:
  1. Set → Normalize (derive workspace_id, conversation_id, text)
  2. HTTP Node → persist_inbound (POST core-api)
  3. HTTP Node → /dialogue/events {event:"user_msg",payload:{intent?,slots?}}
  4. Switch(next_action) → answer | tool_call | handoff | wait
  5. If(tool_call) → Actions Service → HTTP → /dialogue/events {event:"tool_result",payload:{...}}
  6. HTTP → persist_outbound + Twilio Send
- **Salidas**: next_action, fsm_state, message_id
- **Precondiciones**: .env WEBHOOK_URL público; credenciales Twilio
- **Postcondiciones**: dialogue_state_history.version incrementa

#### **16.1.13 Criterios de Aceptación**

- apply_event('user_msg') crea estado si no existe y retorna COLLECTING|answer
- Completar slots.item y slots.qty lleva a CONFIRMING. confirm_ok → CHECKOUT|tool_call
- Tras tool_result → DONE|answer
- RLS: consultas fuera del workspace fallan
- n8n F-29 enruta por next_action sin errores

#### **16.1.14 Ejemplos (curl)**

```bash
# 1) user message → advance FSM
curl -X POST $ORCH/dialogue/events -H "Content-Type: application/json" -d '{
  "workspace_id":"WS","conversation_id":"CID",
  "event":"user_msg","payload":{"slots":{"item":"pizza","qty":1}}
}'

# 2) confirm
curl -X POST $ORCH/dialogue/events -H "Content-Type: application/json" -d '{
  "workspace_id":"WS","conversation_id":"CID","event":"confirm_ok"
}'

# 3) tool result
curl -X POST $ORCH/dialogue/events -H "Content-Type: application/json" -d '{
  "workspace_id":"WS","conversation_id":"CID",
  "event":"tool_result","payload":{"order_id":"1234"}
}'
```

#### **16.1.15 Troubleshooting (acciones concretas)**

- **RLS**: `SELECT pulpo.set_ws_context('WS'); SELECT * FROM pulpo.dialogue_states WHERE conversation_id='CID';`
- **Concurrencia**: revisar locks: pg_locks por conversation_id
- **n8n**: activar "Always output data" + retry 3x (exponential backoff)
- **Observabilidad**: contar versiones por hora: `SELECT date_trunc('hour',at) h, count(*) FROM pulpo.dialogue_state_history WHERE workspace_id='WS' GROUP BY 1 ORDER BY 1;`

#### **16.1.16 Registro Vivo actualizado**

- **Fase**: 3 (Acciones y verticales) → E-01 habilita robustez conversational
- **Microflujos**:
  - F-29 DialogueStateSync — en progreso — [P1] — Dep: core-api, orchestrator
- **Notas**: Decisión de arquitectura → FSM declarativa + persistencia (criterio: simplicidad, auditabilidad, RLS)
- **Observaciones**: Feature flag por vertical; slots tipados opcionales

[image1]: <data:image/png;base64,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>

[image2]: <data:image/png;base64,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>

[image3]: <data:image/png;base64,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>