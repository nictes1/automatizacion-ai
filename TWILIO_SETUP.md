# 📱 Configuración Twilio WhatsApp

## ✅ Pre-requisitos completados

- ✅ Todos los servicios corriendo
- ✅ Funciones SQL aplicadas
- ✅ Workflow n8n importado y activado
- ✅ Ngrok tunnel activo

---

## 🔗 Información del Tunnel

**URL de ngrok:** `https://3dfe97464081.ngrok-free.app`

**Webhook completo:** `https://3dfe97464081.ngrok-free.app/webhook/pulpo/twilio/wa/inbound`

> ⚠️ **IMPORTANTE:** Esta URL cambia cada vez que reiniciás ngrok. Guardala porque la necesitás para Twilio.

---

## 📝 Pasos para configurar Twilio

### 1. Ir a Twilio Console

Abrir: https://console.twilio.com/

### 2. Configurar WhatsApp Sandbox (desarrollo)

1. Menú lateral: **Messaging** → **Try it out** → **Send a WhatsApp message**
2. Click en **Sandbox Settings**
3. En **"WHEN A MESSAGE COMES IN"**:
   - URL: `https://3dfe97464081.ngrok-free.app/webhook/pulpo/twilio/wa/inbound`
   - Method: **POST**
4. Click **Save**

### 3. Unirse al Sandbox desde tu WhatsApp

1. En Twilio Console, copiar el código de sandbox (algo como `join <palabra-clave>`)
2. Desde tu WhatsApp personal, enviar al número de Twilio Sandbox
3. Enviar: `join <palabra-clave>`
4. Deberías recibir confirmación de Twilio

---

## 🧪 Testing

### Test 1: Enviar mensaje desde WhatsApp

1. Desde tu celular, enviar al número de Twilio Sandbox:
   ```
   Hola
   ```

2. **Esperado:**
   - Recibes respuesta del bot
   - Mensaje se guarda en DB

### Test 2: Verificar en base de datos

```bash
docker exec pulpo-postgres psql -U pulpo -d pulpo -c \
  "SELECT sender, content, to_char(created_at, 'HH24:MI:SS') as time
   FROM pulpo.messages
   ORDER BY created_at DESC
   LIMIT 10;"
```

**Deberías ver:**
- Mensaje `user` con tu texto
- Mensaje `assistant` con la respuesta

### Test 3: Ver logs en tiempo real

```bash
# Logs de n8n (workflow execution)
docker logs -f pulpo-n8n

# Logs del Orchestrator
docker logs -f pulpo-orchestrator

# Logs de Twilio (en otra terminal)
tail -f /tmp/ngrok.log
```

---

## 🔍 Monitoreo en tiempo real

### Ver dashboard de ngrok

Abrir en el navegador: http://localhost:4040

Aquí podés ver:
- Requests entrantes en tiempo real
- Headers de cada request
- Response codes
- Muy útil para debugging

### Ver workflow en n8n

Abrir: http://localhost:5678

- Ver ejecuciones del workflow
- Ver datos que pasan por cada nodo
- Identificar errores

---

## 🐛 Troubleshooting

### Error: "No se recibe respuesta en WhatsApp"

**Verificar:**

1. Workflow está activado en n8n
   ```
   n8n → Workflows → Check que el toggle está ON
   ```

2. Orchestrator está respondiendo
   ```bash
   curl http://localhost:8005/health
   ```

3. Credenciales de Twilio configuradas en n8n
   ```
   n8n → Nodo "Send Twilio" → Credentials
   ```

---

### Error: "Webhook not found" en Twilio

**Solución:**

Verificar que la URL en Twilio coincide exactamente con ngrok:

```bash
# Obtener URL actual de ngrok
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'
```

Actualizar en Twilio si cambió.

---

### Error: "Ngrok se cayó"

**Solución:**

```bash
# Matar ngrok anterior
pkill ngrok

# Iniciar nuevo
nohup ngrok http 5678 > /tmp/ngrok.log 2>&1 &

# Esperar 3 segundos
sleep 3

# Obtener nueva URL
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'

# Actualizar en Twilio con la nueva URL
```

---

## 📊 Verificar que todo funciona

### Checklist completo:

- [ ] ngrok corriendo (`http://localhost:4040`)
- [ ] Workflow activado en n8n
- [ ] Webhook configurado en Twilio
- [ ] Joined al sandbox de WhatsApp
- [ ] Mensaje de prueba enviado
- [ ] Respuesta recibida en WhatsApp
- [ ] Mensajes guardados en DB

### Comando de verificación rápida:

```bash
echo "=== SERVICIOS ==="
curl -s http://localhost:8005/health | jq -r .status
curl -s http://localhost:8006/health | jq -r .status
curl -s http://localhost:8007/rag/health | jq -r .status

echo -e "\n=== NGROK ==="
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'

echo -e "\n=== ÚLTIMOS MENSAJES ==="
docker exec pulpo-postgres psql -U pulpo -d pulpo -c \
  "SELECT sender, left(content, 30), to_char(created_at, 'HH24:MI:SS')
   FROM pulpo.messages
   ORDER BY created_at DESC LIMIT 5;"
```

---

## 🎯 Flujo completo esperado

```
1. Usuario envía "Hola" por WhatsApp
   ↓
2. Twilio recibe mensaje → POST a ngrok
   ↓
3. ngrok → n8n webhook
   ↓
4. n8n workflow:
   - Normalize Input
   - Resolve Channel
   - Persist Inbound (guarda en DB)
   - Call Orchestrator
   - Parse Intent
   - (si hay tool_calls) Execute Actions
   - Prepare Response
   - Persist Outbound (guarda respuesta)
   - Send Twilio
   ↓
5. Usuario recibe respuesta por WhatsApp
```

---

## 📚 Referencias

- **Twilio Console:** https://console.twilio.com/
- **Twilio WhatsApp Docs:** https://www.twilio.com/docs/whatsapp
- **ngrok Dashboard:** http://localhost:4040
- **n8n UI:** http://localhost:5678
- **MVP Setup completo:** `MVP_SETUP.md`

---

## 🚀 Próximos pasos (después de que funcione)

1. **Agregar documentos al RAG:**
   ```bash
   # Subir PDFs, docs, etc. para que el bot responda con contexto
   python scripts/generate_embeddings.py
   ```

2. **Configurar acciones específicas:**
   - Modificar `services/actions_service_v2.py`
   - Agregar acciones por vertical (gastronomía, inmobiliaria, etc.)

3. **Mejorar prompts:**
   - Editar `services/vertical_manager.py`
   - Ajustar system prompts por vertical

4. **Producción:**
   - Dominio propio en lugar de ngrok
   - Número de WhatsApp propio (no sandbox)
   - SSL/TLS certificates
   - Monitoreo con Prometheus/Grafana
