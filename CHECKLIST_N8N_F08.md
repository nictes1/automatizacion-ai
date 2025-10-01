# 🔧 Checklist n8n F-08 - Fixes Imprescindibles

## ⚡ **5 Fixes Críticos (2-3 minutos en n8n UI)**

### **1. Headers en HTTP Request** ✅
**Nodos a modificar:** `Intent Router`, `Generate Response`, `Execute Action`

**En cada nodo → Options → Headers:**
```
Content-Type: application/json
X-Workspace-Id: {{ $('Prepare Context').item.json.workspace_id }}
X-Request-Id: {{ $('Prepare Context').item.json.message_id }}
```

**Para Execute Action (X-Request-Id especial):**
```
X-Request-Id: {{ $('Parse Intent').item.json.message_id }}-{{$json.name}}
```

---

### **2. Bucle del SplitInBatches** ✅
**Conectar:** `Prepare Action Response` ➜ `Split Tool Calls` (entrada pequeña "Continue here")

**Alternativa:** `Persist Action Result` ➜ `Split Tool Calls` (Continue here)

---

### **3. Salida "No Items" del Split** ✅
**En Split Tool Calls:**
- Rama actual: `Split Tool Calls` ➜ `Final Response` (Output 0)
- **Cambiar a:** `Split Tool Calls` ➜ `Final Response` (Output 1 - "No Items")

---

### **4. Rama SIN tool calls** ✅
**Verificar conexión:**
`Prepare Response` ➜ `Persist Response` ➜ `Update Flow` ➜ `Send Twilio` ➜ `Final Response`

**Campo Twilio correcto:**
`Send Twilio` → Body: `{{ $('Prepare Response').item.json.response_text }}`

---

### **5. Referencias consistentes** ✅
**Verificar que NO quede ninguna referencia sin sufijo:**

- ✅ `$('Parse Intent')` → `$('Parse Intent')` (ya corregido)
- ✅ `$('Prepare Context')` → `$('Prepare Context')` (ya corregido)  
- ✅ `$('Prepare Response')` → `$('Prepare Response')` (ya corregido)

---

## 🧪 **Test Manual (Paso a Paso)**

### **Paso 1: Guardar y Ejecutar**
1. Guardar el workflow en n8n
2. Click en `Webhook Inbound` → "Execute Node"
3. n8n queda esperando webhook

### **Paso 2: Enviar WhatsApp**
```
Mensaje: "hola, quiero hacer un pedido"
Desde: +5491111111111
Hacia: +14155238886 (sandbox Twilio)
```

### **Paso 3: Verificar en n8n**
**Execution preview debe mostrar:**
- ✅ `Resolve Channel` → ws_id y display_phone
- ✅ `Persist Inbound` → conversation_id y message_id  
- ✅ `Intent Router`/`Generate Response` → 200 OK
- ✅ Si NO hay tool calls: `Prepare Response` ➜ `Final Response`
- ✅ Si HAY tool calls: iterar `Split Tool Calls` ➜ `Execute Action` ➜ `Persist Action Result` ➜ `Prepare Action Response` ➜ (vuelve al Split)

### **Paso 4: Verificar WhatsApp**
- ✅ Te llega respuesta de la IA en WhatsApp

### **Paso 5: Verificar Base de Datos**
```sql
SELECT last_message_sender, last_message_text, total_messages
FROM pulpo.conversations
ORDER BY last_message_at DESC
LIMIT 3;
```

---

## 🚨 **Problemas Típicos (30s para detectar)**

### **Flujo no avanza después de acción**
- ❌ **Problema:** Falta cable `Prepare Action Response` ➜ `Split Tool Calls` (Continue here)
- ✅ **Solución:** Conectar entrada pequeña del Split

### **"Node not found" en expresiones**
- ❌ **Problema:** Referencia sin sufijo (ej. `$('Parse Intent')` en lugar de `$('Parse Intent')`)
- ✅ **Solución:** Abrir Execute Log del nodo que falla, ver expresión exacta

### **HTTP 403/401 en servicios Python**
- ❌ **Problema:** Faltan headers `X-Workspace-Id` / `X-Request-Id`
- ✅ **Solución:** Agregar headers en los 3 HTTP nodes

### **Twilio envía vacío**
- ❌ **Problema:** Body de `Send Twilio` incorrecto
- ✅ **Solución:** Usar `{{ $('Prepare Response').item.json.response_text }}`

---

## 🧪 **Smoke Test Automático**

```bash
# Test webhook
curl -X POST http://localhost:5678/webhook/pulpo/twilio/wa/inbound \
  -H "Content-Type: application/json" \
  -d '{"Body":"hola, quiero una docena","From":"whatsapp:+5491111111111","To":"whatsapp:+14155238886","SmsSid":"SM_test_1"}'

# Esperado:
# ✅ 200 en n8n
# ✅ 200 desde Generate Response  
# ✅ Si hay tool calls: 1..N llamadas a Execute Action
# ✅ WhatsApp responde desde sandbox
```

---

## ✅ **Checklist Final**

- [ ] Headers agregados en 3 HTTP nodes
- [ ] Bucle del Split conectado (Continue here)
- [ ] Salida "No Items" del Split conectada
- [ ] Rama sin tool calls completa
- [ ] Referencias consistentes (sin sufijos)
- [ ] Test manual ejecutado
- [ ] WhatsApp responde
- [ ] Base de datos actualizada

---

## 🎯 **Resultado Esperado**

**Con estos 5 fixes, el workflow debe:**
1. ✅ Recibir WhatsApp → n8n
2. ✅ Procesar con Orchestrator Service
3. ✅ Ejecutar tool calls si los hay
4. ✅ Responder por WhatsApp
5. ✅ Persistir en base de datos
6. ✅ Terminar correctamente

**¡Listo para producción!** 🚀
