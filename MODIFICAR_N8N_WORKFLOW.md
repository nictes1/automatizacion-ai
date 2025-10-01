# 🔧 Cómo Modificar tu Workflow de N8N para usar PulpoAI Services

## 📋 Resumen

Tu workflow de N8N ya está muy bien estructurado. Solo necesitas **cambiar algunas URLs** para que use los servicios de PulpoAI en lugar de Ollama directamente.

## 🎯 Cambios Necesarios

### 1. **Nodo "Intent Router"** 
**Cambiar de Ollama a Orchestrator Service:**

```json
// ANTES (llamada directa a Ollama):
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:11434/api/chat",
    "jsonBody": "{\n  \"model\": \"llama3.1:8b\",\n  \"format\": \"json\",\n  \"options\": { \"temperature\": 0.1 },\n  \"messages\": [...]\n}"
  }
}

// DESPUÉS (llamada a Orchestrator Service):
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:8005/orchestrator/decide",
    "jsonBody": "{\n  \"message\": \"{{ $('Parse Intent').item.json.user_text }}\",\n  \"user_id\": \"{{ $('Normalize Input').item.json.user_phone }}\",\n  \"workspace_id\": \"{{ $('Get Workspace Config').item.json.result[0] }}\",\n  \"conversation_id\": \"{{ $('Persist Inbound').item.json.result[0].conversation_id }}\"\n}"
  }
}
```

### 2. **Nodo "Generate Response"**
**Cambiar de Ollama a Orchestrator Service:**

```json
// ANTES (llamada directa a Ollama):
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:11434/api/chat",
    "jsonBody": "{\n  \"model\": \"llama3.1:8b\",\n  \"options\": { \"temperature\": 0.3 },\n  \"messages\": [...]\n}"
  }
}

// DESPUÉS (llamada a Orchestrator Service):
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:8005/orchestrator/decide",
    "jsonBody": "{\n  \"message\": \"{{ $('Parse Intent').item.json.user_text }}\",\n  \"user_id\": \"{{ $('Normalize Input').item.json.user_phone }}\",\n  \"workspace_id\": \"{{ $('Get Workspace Config').item.json.result[0] }}\",\n  \"conversation_id\": \"{{ $('Persist Inbound').item.json.result[0].conversation_id }}\",\n  \"intent\": \"{{ $('Parse Intent').item.json.intent }}\",\n  \"confidence\": {{ $('Parse Intent').item.json.confidence }}\n}"
  }
}
```

### 3. **Agregar nodo para RAG (opcional)**
**Si quieres usar RAG para contexto, agrega un nodo antes de "Generate Response":**

```json
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:8003/tools/retrieve_context",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "{\n  \"query\": \"{{ $('Parse Intent').item.json.user_text }}\",\n  \"workspace_id\": \"{{ $('Get Workspace Config').item.json.result[0] }}\",\n  \"limit\": 5\n}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [-2160, 2200],
  "id": "rag-context-node",
  "name": "Get RAG Context"
}
```

### 4. **Agregar nodo para Actions (opcional)**
**Si quieres ejecutar acciones, agrega un nodo después de "Generate Response":**

```json
{
  "parameters": {
    "method": "POST",
    "url": "http://localhost:8004/tools/execute_action",
    "sendBody": true,
    "specifyBody": "json",
    "jsonBody": "{\n  \"action_type\": \"{{ $('Generate Response').item.json.action_type }}\",\n  \"payload\": {{ $('Generate Response').item.json.payload }},\n  \"user_id\": \"{{ $('Normalize Input').item.json.user_phone }}\",\n  \"workspace_id\": \"{{ $('Get Workspace Config').item.json.result[0] }}\"\n}",
    "options": {}
  },
  "type": "n8n-nodes-base.httpRequest",
  "typeVersion": 4.2,
  "position": [-1500, 2200],
  "id": "execute-action-node",
  "name": "Execute Action"
}
```

## 🚀 Pasos para Implementar

### Paso 1: Iniciar el sistema
```bash
# Iniciar todos los servicios
./start_with_n8n.sh
```

### Paso 2: Abrir N8N
```bash
# Abrir N8N en el navegador
open http://localhost:5678
```

### Paso 3: Importar tu workflow
1. En N8N, ve a **Workflows**
2. Haz clic en **Import from file**
3. Selecciona `n8n/n8n-flow-improved.json`

### Paso 4: Modificar los nodos
1. **Abre el nodo "Intent Router"**
2. Cambia la URL de `http://localhost:11434/api/chat` a `http://localhost:8005/orchestrator/decide`
3. Modifica el JSON body según el ejemplo anterior
4. **Abre el nodo "Generate Response"**
5. Cambia la URL de `http://localhost:11434/api/chat` a `http://localhost:8005/orchestrator/decide`
6. Modifica el JSON body según el ejemplo anterior

### Paso 5: Probar el flujo
1. **Guarda el workflow** en N8N
2. **Activa el workflow**
3. **Envía un mensaje de prueba** desde WhatsApp
4. **Verifica que funcione** correctamente

## 🧪 Testing

### Test individual de servicios:
```bash
# Test Orchestrator
curl -X POST http://localhost:8005/orchestrator/test

# Test RAG
curl -X POST http://localhost:8003/search/test

# Test Actions
curl -X POST http://localhost:8004/actions/test

# Test Message Router
curl -X POST http://localhost:8006/test/message
```

### Test completo:
```bash
# Simular mensaje de WhatsApp
curl -X POST http://localhost:8006/webhooks/twilio/wa/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "From": "whatsapp:+1234567890",
    "To": "whatsapp:+14155238886",
    "Body": "Hola, quiero hacer un pedido",
    "MessageSid": "test-123",
    "MessageType": "text"
  }'
```

## 📊 Beneficios de la Integración

### ✅ Mantienes tu workflow de N8N
- No necesitas crear uno nuevo
- Conservas toda la lógica existente
- Solo cambias las URLs

### ✅ Obtienes todas las funcionalidades de PulpoAI
- RAG para contexto
- Actions para ejecutar acciones
- Orchestrator para lógica compleja
- Message Router para manejo de mensajes

### ✅ Fácil de mantener
- Un solo punto de entrada (N8N)
- Servicios especializados (PulpoAI)
- Logs centralizados
- Debugging simplificado

## 🎯 Resultado Final

**Flujo completo:**
```
WhatsApp → Twilio → N8N → PulpoAI Services → Respuesta → WhatsApp
```

**Servicios utilizados:**
- **N8N**: Orquestación y flujo
- **Orchestrator Service**: Lógica de decisión
- **RAG Service**: Contexto y búsqueda
- **Actions Service**: Ejecución de acciones
- **Message Router**: Manejo de mensajes
- **PostgreSQL**: Persistencia de datos
- **Ollama**: LLM local (opcional)

## 🚨 Solución de Problemas

### Problema: Servicio no responde
```bash
# Verificar que el servicio esté corriendo
curl http://localhost:8005/health

# Ver logs del servicio
tail -f logs/orchestrator.log
```

### Problema: N8N no conecta
```bash
# Verificar que N8N esté corriendo
curl http://localhost:5678

# Ver logs de N8N
tail -f logs/n8n.log
```

### Problema: Workflow no funciona
1. **Verificar URLs** en los nodos de N8N
2. **Verificar JSON body** en las llamadas HTTP
3. **Verificar conexiones** entre nodos
4. **Verificar logs** de N8N y PulpoAI

---

**¡Con estos cambios tendrás tu workflow de N8N funcionando con todos los servicios de PulpoAI!** 🐙✨
