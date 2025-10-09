# 🚀 MVP Setup - WhatsApp → Twilio → n8n → Orchestrator

## ✅ Completado

1. ✅ Funciones SQL de persistencia (`persist_inbound`, `persist_outbound`, `load_state`)
2. ✅ Índices para deduplicación
3. ✅ Campo `display_phone` en tabla `channels`
4. ✅ Workflow n8n actualizado

---

## 📋 Pasos para levantar el MVP

### 1. Aplicar cambios a la base de datos

```bash
# Conectar a PostgreSQL y aplicar cambios
docker exec -it pulpo-postgres psql -U pulpo -d pulpo

# Verificar que las nuevas funciones existen
\df pulpo.persist_*
\df pulpo.load_state

# Salir
\q
```

O aplicar el script directamente:

```bash
# Aplicar schema actualizado (si es fresh install)
docker exec -i pulpo-postgres psql -U pulpo -d pulpo < database/init/01_schema.sql

# Aplicar funciones actualizadas
docker exec -i pulpo-postgres psql -U pulpo -d pulpo < database/init/02_functions.sql
```

---

### 2. Crear datos de prueba

```bash
docker exec -it pulpo-postgres psql -U pulpo -d pulpo
```

```sql
-- Crear workspace de prueba
INSERT INTO pulpo.workspaces (id, name, plan, settings)
VALUES (
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'Workspace Test',
  'premium',
  '{"vertical": "gastronomia"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET settings = EXCLUDED.settings;

-- Crear canal de WhatsApp (reemplazar con tu número de Twilio)
INSERT INTO pulpo.channels (id, workspace_id, type, name, display_phone, config)
VALUES (
  'bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb',
  'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa',
  'whatsapp',
  'WhatsApp Principal',
  '+14155238886',  -- TU NÚMERO DE TWILIO AQUÍ
  '{"provider": "twilio"}'::jsonb
)
ON CONFLICT (id) DO UPDATE SET display_phone = EXCLUDED.display_phone, config = EXCLUDED.config;

-- Verificar
SELECT * FROM pulpo.workspaces WHERE id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
SELECT * FROM pulpo.channels WHERE workspace_id = 'aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa';
```

---

### 3. Verificar servicios

```bash
# Orchestrator
curl http://localhost:8005/orchestrator/health

# Actions
curl http://localhost:8006/actions/health

# RAG
curl http://localhost:8007/rag/health

# n8n
curl http://localhost:5678/healthz
```

---

### 4. Importar workflow a n8n

1. Abrir n8n: http://localhost:5678
2. Login: `admin` / `admin123`
3. Ir a **Workflows → Import from File**
4. Seleccionar `n8n/n8n-workflow.json`
5. **Guardar** el workflow
6. **Activar** el workflow (toggle en la esquina superior)

---

### 5. Configurar credenciales de Twilio en n8n

1. En n8n, ir al nodo **"Send Twilio"**
2. Click en **Credentials** → **Create New Credential**
3. Ingresar:
   - **Account SID**: `ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX` (o el tuyo)
   - **Auth Token**: (tu token de Twilio)
4. **Save**

---

### 6. Obtener URL del webhook de n8n

1. Abrir el workflow en n8n
2. Click en el nodo **"Webhook Inbound"**
3. Copiar la **Production URL**, algo como:
   ```
   http://localhost:5678/webhook/pulpo/twilio/wa/inbound
   ```

4. **Si usás ngrok para exponer n8n:**
   ```bash
   ngrok http 5678
   ```

   Luego usa la URL de ngrok:
   ```
   https://abc123.ngrok.io/webhook/pulpo/twilio/wa/inbound
   ```

---

### 7. Configurar webhook en Twilio

1. Ir a [Twilio Console](https://console.twilio.com/)
2. **Messaging** → **Try it out** → **Send a WhatsApp message**
3. En **Sandbox Settings** o en tu número configurado:
   - **WHEN A MESSAGE COMES IN**: `<TU_URL_NGROK>/webhook/pulpo/twilio/wa/inbound`
   - Method: `POST`
4. **Save**

---

## 🧪 Testing

### Test 1: Simular webhook de Twilio (sin WhatsApp real)

```bash
curl -X POST http://localhost:5678/webhook/pulpo/twilio/wa/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "Body": "Hola, quiero pedir empanadas",
    "From": "whatsapp:+5491112345678",
    "To": "whatsapp:+14155238886",
    "SmsSid": "SM_test_001"
  }'
```

**Esperado:**
- Código 200
- Mensaje persistido en DB
- Respuesta del orchestrator generada
- (No se envía por Twilio en este test)

---

### Test 2: Verificar persistencia en DB

```bash
docker exec -it pulpo-postgres psql -U pulpo -d pulpo
```

```sql
-- Ver últimas conversaciones
SELECT
  id,
  metadata->>'user_phone' AS user_phone,
  metadata->>'last_message_sender' AS last_sender,
  metadata->>'last_message_text' AS last_text,
  metadata->>'total_messages' AS total_msgs
FROM pulpo.conversations
ORDER BY updated_at DESC
LIMIT 5;

-- Ver últimos mensajes
SELECT
  id,
  sender,
  content,
  metadata->>'wa_message_id' AS wa_msg_id,
  metadata->>'origin' AS origin,
  created_at
FROM pulpo.messages
ORDER BY created_at DESC
LIMIT 10;
```

**Esperado:**
- 1 conversación nueva
- 2 mensajes: 1 user + 1 assistant

---

### Test 3: Test real con WhatsApp

1. Desde tu celular, enviar al **WhatsApp Sandbox de Twilio**:
   ```
   join <sandbox-code>
   ```

2. Luego enviar:
   ```
   Hola
   ```

3. **Esperado:**
   - Recibes respuesta del bot
   - Se guarda en DB
   - Aparece en logs de n8n

---

### Test 4: Verificar deduplicación

Enviar el mismo mensaje 2 veces (mismo `SmsSid`):

```bash
# Primera vez
curl -X POST http://localhost:5678/webhook/pulpo/twilio/wa/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "Body": "Test dedupe",
    "From": "whatsapp:+5491112345678",
    "To": "whatsapp:+14155238886",
    "SmsSid": "SM_DEDUPE_TEST"
  }'

# Segunda vez (mismo SmsSid)
curl -X POST http://localhost:5678/webhook/pulpo/twilio/wa/inbound \
  -H "Content-Type": application/json" \
  -d '{
    "Body": "Test dedupe",
    "From": "whatsapp:+5491112345678",
    "To": "whatsapp:+14155238886",
    "SmsSid": "SM_DEDUPE_TEST"
  }'
```

**Verificar en DB:**
```sql
SELECT COUNT(*) FROM pulpo.messages WHERE metadata->>'wa_message_id' = 'SM_DEDUPE_TEST';
-- Debe ser 1 (no duplicado)
```

---

## 📊 Monitoreo

### Logs en tiempo real

```bash
# n8n
docker logs -f pulpo-n8n

# Orchestrator
docker logs -f pulpo-orchestrator

# PostgreSQL
docker logs -f pulpo-postgres | grep persist_inbound
```

---

## 🐛 Troubleshooting

### Error: "Channel not found"

```sql
-- Verificar que el número de Twilio coincide
SELECT * FROM pulpo.channels WHERE display_phone LIKE '%4155238886%';

-- Si está vacío, insertar manualmente (ver paso 2)
```

---

### Error: "Orchestrator not responding"

```bash
# Verificar que está corriendo
docker ps | grep orchestrator

# Ver logs
docker logs pulpo-orchestrator --tail 50

# Restart si es necesario
docker restart pulpo-orchestrator
```

---

### Error: "Función pulpo.persist_inbound no existe"

```bash
# Aplicar funciones de nuevo
docker exec -i pulpo-postgres psql -U pulpo -d pulpo < database/init/02_functions.sql

# Verificar
docker exec -it pulpo-postgres psql -U pulpo -d pulpo -c "\df pulpo.persist_inbound"
```

---

## ✅ Criterio de aceptación

1. ✅ Envías "hola" desde WhatsApp
2. ✅ Recibes respuesta del Orchestrator por WhatsApp
3. ✅ Aparecen 2 filas en `messages` (user + assistant)
4. ✅ `conversations` actualiza `last_message_*`
5. ✅ No hay duplicados si llega el mismo `SmsSid` 2 veces

---

## 🎯 Próximos pasos (cuando esto funcione)

1. Añadir **Check Tool Calls** → ejecutar `actions_service` si el Orchestrator devuelve `tool_calls`
2. Añadir **Slot Manager** simple (catálogo por vertical en DB)
3. Conectar `/rag/search` para respuestas con contexto (cuando `next_action=RETRIEVE_CONTEXT`)
4. Implementar intent classifier con umbral de confianza

---

## 📚 Documentación de referencia

- [Twilio WhatsApp Sandbox](https://www.twilio.com/console/sms/whatsapp/sandbox)
- [n8n Webhook Node](https://docs.n8n.io/integrations/builtin/core-nodes/n8n-nodes-base.webhook/)
- [Orchestrator API](services/orchestrator_service.py)
- [Funciones SQL](database/init/02_functions.sql)
