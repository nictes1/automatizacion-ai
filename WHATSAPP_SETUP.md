# 📱 Configuración WhatsApp + Twilio

## ✅ Sistema Listo

Todos los servicios están corriendo y el webhook está expuesto públicamente.

### Funciones SQL para n8n
✅ **`pulpo.persist_inbound()`** - Guarda mensajes entrantes de Twilio
✅ **`pulpo.load_state()`** - Carga estado conversacional
✅ **`pulpo.persist_outbound()`** - Guarda mensajes salientes del bot
✅ **Endpoint `/orchestrator/persist_message`** - HTTP wrapper para persist_outbound

---

## 🔧 Configuración de Twilio

### 1. Acceder a Twilio Console
https://console.twilio.com/us1/develop/sms/try-it-out/whatsapp-learn

### 2. Obtener URL actual de ngrok

⚠️ **La URL de ngrok cambia cada vez que se reinicia**

Para ver la URL actual:
```bash
curl -s http://localhost:4040/api/tunnels | jq -r '.tunnels[0].public_url'
```

**URL actual**: `https://9e57a2e2fc93.ngrok-free.app`

### 3. Configurar Webhook en Twilio

**En "Sandbox Settings" o tu número de WhatsApp configurado:**

```
When a message comes in:
  URL: https://9e57a2e2fc93.ngrok-free.app/webhook/pulpo/twilio/wa/inbound
  Method: POST
  Content-Type: application/x-www-form-urlencoded
```

**Guardar cambios**

### 4. Configurar Credenciales de Twilio en n8n

1. Acceder a n8n: http://localhost:5678 (admin/admin123)
2. Ir a **Settings** → **Credentials**
3. Buscar o crear "Twilio account" con:
   - **Account SID**: Tu Account SID de Twilio (empieza con "AC...")
   - **Auth Token**: Tu Auth Token de Twilio

⚠️ **El workflow referencia credential ID: `STjKxgq55vOri0dm`** - Asegúrate de que exista o actualiza el workflow

---

## 📞 Número de WhatsApp de Prueba

```
+14155238886
```

**Nota:** Si estás usando Twilio Sandbox, primero debes enviar el código de join desde tu WhatsApp.

### Actualizar número en la base de datos

⚠️ **Importante**: El número en `pulpo.channels` debe coincidir con tu número de Twilio.

```bash
docker exec pulpo-postgres psql -U pulpo -d pulpo -c "
UPDATE pulpo.channels
SET display_phone = 'whatsapp:+14155238886'
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003';
"
```

Verifica que se actualizó:
```bash
docker exec pulpo-postgres psql -U pulpo -d pulpo -c "
SELECT id, display_phone FROM pulpo.channels
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440003';
"
```

---

## 🎯 Workspace de Prueba: Peluquería Estilo

### Información del Negocio
- **Nombre:** Estilo Peluquería & Spa
- **Dirección:** Av. Cabildo 9012, CABA
- **Teléfono:** +5491198765432
- **Workspace ID:** 550e8400-e29b-41d4-a716-446655440003

### Servicios Disponibles
| Servicio | Precio |
|----------|--------|
| Corte de Cabello | $3,500 - $6,000 |
| Coloración | $9,500 |
| Barba | $3,000 |

### Staff Disponible
- **Carlos Rodríguez** (Senior) - Corte $6,000, Barba $3,000
- **Juan Martínez** - Corte $4,500
- **María Fernández** (Estilista) - Corte $3,500, Coloración $9,500

### Horarios de Atención
- **Lunes a Viernes:** 9:00 - 19:00
- **Sábado:** 9:00 - 14:00
- **Domingo:** Cerrado

---

## 🧪 Flujos de Prueba

### Ejemplo 1: Consultar Servicios
```
Usuario: Hola, ¿qué servicios ofrecen?
Bot: Responde con lista de servicios y precios
```

### Ejemplo 2: Reservar Turno
```
Usuario: Quiero turno para corte mañana a las 10am
Bot: Pide nombre y confirma
Usuario: Juan Pérez, juan@email.com
Bot: Confirma reserva con detalles
```

### Ejemplo 3: Consultar Horarios
```
Usuario: ¿Qué horarios tienen?
Bot: Responde con horarios de atención
```

### Ejemplo 4: Consultar Precios por Staff
```
Usuario: ¿Cuánto cobra Carlos por un corte?
Bot: Carlos Rodríguez cobra $6,000 por corte (45 min)
```

---

## 🔍 Monitoreo en Tiempo Real

Para ver los logs mientras probás:

```bash
/tmp/monitor_whatsapp.sh
```

Esto mostrará en tiempo real:
- ✅ Webhooks recibidos en n8n
- ✅ Llamadas al orchestrator
- ✅ Ejecución de acciones
- ❌ Errores si los hay

---

## 📊 Arquitectura del Flujo

```
WhatsApp → Twilio → Ngrok → n8n → Orchestrator → MCP Tools → Actions → DB
                                ↓
                            Response
                                ↓
                            n8n → Twilio → WhatsApp
```

### Componentes Activos
1. **PostgreSQL** (5432) - Base de datos normalizada
2. **Redis** (6379) - Cache
3. **Ollama** (11434) - AI/LLM
4. **Orchestrator** (8005) - Lógica de conversación
5. **Actions** (8006) - Ejecución de acciones (reservas)
6. **MCP** (8010) - Tools integration (consultas en tiempo real)
7. **n8n** (5678) - Workflow engine
8. **Ngrok** - Túnel público

---

## 🐛 Troubleshooting

### Webhook no responde
```bash
# Verificar n8n
curl http://localhost:5678/healthz

# Verificar ngrok
curl http://localhost:4040/api/tunnels | python3 -m json.tool
```

### Orchestrator no responde
```bash
# Ver logs
docker logs pulpo-orchestrator -f

# Test directo
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440003" \
  -d '{"conversation_id":"test","vertical":"servicios","user_input":"Hola"}'
```

### Tools no funcionan
```bash
# Ver logs de MCP
docker logs pulpo-mcp -f

# Test directo
curl "http://localhost:8010/mcp/tools/get_available_services?workspace_id=550e8400-e29b-41d4-a716-446655440003"
```

---

## ✅ Checklist de Validación

Antes de probar desde WhatsApp:

- [x] PostgreSQL corriendo con schema normalizado
- [x] Orchestrator respondiendo
- [x] Actions respondiendo
- [x] MCP Tools respondiendo
- [x] n8n corriendo
- [x] Ngrok expuesto públicamente
- [x] Webhook configurado en Twilio
- [ ] Mensaje de prueba desde WhatsApp

---

## 🚀 ¡A Probar!

1. Configurá el webhook en Twilio con la URL de arriba
2. Abrí WhatsApp
3. Enviá mensaje a **+14155238886**
4. Ejecutá `/tmp/monitor_whatsapp.sh` en otra terminal para ver logs
5. ¡Chateá con tu AI de peluquería!

**Ejemplo de conversación:**
```
Vos: Hola
Bot: ¡Hola! Bienvenido a Estilo Peluquería...

Vos: Quiero turno para corte mañana 10am
Bot: ¿Tu nombre y email?

Vos: Juan Pérez, juan@test.com
Bot: ✅ Turno confirmado para mañana 10am con María...
```

---

**Nota:** La URL de ngrok (`https://9e57a2e2fc93.ngrok-free.app`) cambia cada vez que reiniciás ngrok. Si ngrok se cae, tendrás que actualizar el webhook en Twilio con la nueva URL.
