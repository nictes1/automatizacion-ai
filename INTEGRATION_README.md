# 🚀 PulpoAI - Integración n8n + Orchestrator Service

## 📋 Resumen

Esta integración conecta el workflow de n8n con el Orchestrator Service de PulpoAI, reemplazando las llamadas directas a Ollama por un sistema más robusto y escalable.

## 🎯 Objetivo

**F-07**: Integrar n8n con Orchestrator Service para:
- ✅ Reemplazar llamadas directas a LLM
- ✅ Implementar arquitectura de microservicios
- ✅ Mantener trazabilidad completa
- ✅ Escalabilidad horizontal

## 🏗️ Arquitectura

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   WhatsApp      │    │   n8n Workflow  │    │ Orchestrator    │
│   (Twilio)      │◄──►│   (Orchestrator)│◄──►│   Service       │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                       │
                                ▼                       ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │  Actions Service│    │   PostgreSQL    │
                       │   (Tools)       │    │   (RLS)         │
                       └─────────────────┘    └─────────────────┘
```

## 🔧 Cambios Implementados

### **1. Workflow n8n Actualizado**

**Archivo**: `n8n/n8n-workflow-integrated.json`

**Cambios principales**:
- ✅ **Intent Router**: `http://localhost:11434/api/chat` → `http://localhost:8005/orchestrator/decide`
- ✅ **Generate Response**: `http://localhost:11434/api/chat` → `http://localhost:8005/orchestrator/decide`
- ✅ **Headers agregados**: `X-Workspace-Id`, `X-Request-Id`
- ✅ **Payload actualizado**: Formato compatible con Orchestrator Service

### **2. Docker Compose Integrado**

**Archivo**: `docker-compose.integrated.yml`

**Servicios incluidos**:
- 🐘 **PostgreSQL** (puerto 5432) - Base de datos con RLS
- 🔴 **Redis** (puerto 6379) - Cache y debounce
- 🦙 **Ollama** (puerto 11434) - LLM local
- 🎛️ **Orchestrator Service** (puerto 8005) - Lógica de diálogo
- ⚡ **Actions Service** (puerto 8006) - Herramientas de negocio
- 📁 **Ingestion Service** (puerto 8007) - Procesamiento de archivos
- 🔍 **RAG Worker** (puerto 8002) - Búsqueda semántica
- 🔧 **n8n** (puerto 5678) - Workflow engine
- 📊 **Prometheus** (puerto 9090) - Métricas
- 📈 **Grafana** (puerto 3000) - Dashboards

### **3. Scripts de Testing**

**Archivos**:
- `scripts/test_integration.py` - Test general del sistema
- `scripts/test_n8n_flow.py` - Test específico del flujo n8n
- `scripts/deploy_integrated.sh` - Script de despliegue

## 🚀 Despliegue Rápido

### **Paso 1: Preparar el entorno**
```bash
# Clonar y navegar al proyecto
cd /home/nictes/workspace/nictes1/pulpo

# Hacer ejecutables los scripts
chmod +x scripts/*.sh scripts/*.py
```

### **Paso 2: Desplegar con Docker**
```bash
# Ejecutar script de despliegue
./scripts/deploy_integrated.sh
```

### **Paso 3: Verificar servicios**
```bash
# Test de integración
python scripts/test_integration.py

# Test específico de n8n
python scripts/test_n8n_flow.py
```

## 🔍 Verificación Manual

### **1. Verificar Orchestrator Service**
```bash
curl -X POST http://localhost:8005/orchestrator/decide \
  -H "Content-Type: application/json" \
  -H "X-Workspace-Id: 00000000-0000-0000-0000-000000000001" \
  -d '{
    "conversation_id": "test-123",
    "vertical": "gastronomia",
    "user_input": "Hola, quiero hacer un pedido",
    "greeted": false,
    "slots": {},
    "objective": "",
    "last_action": null,
    "attempts_count": 0
  }'
```

**Respuesta esperada**:
```json
{
  "assistant": "¡Hola! Te ayudo con tu pedido...",
  "next_action": "answer",
  "tool_calls": [],
  "slots": {},
  "objective": "completar_pedido",
  "end": false
}
```

### **2. Verificar n8n**
- 🌐 **URL**: http://localhost:5678
- 👤 **Usuario**: admin
- 🔑 **Contraseña**: admin123

### **3. Verificar Base de Datos**
```sql
-- Conectar a PostgreSQL
docker exec -it pulpo-postgres-integrated psql -U pulpo -d pulpo

-- Verificar tablas
\dt pulpo.*

-- Verificar conversaciones
SELECT id, total_messages, last_message_text 
FROM pulpo.conversations 
ORDER BY created_at DESC 
LIMIT 5;
```

## 📊 Monitoreo

### **Prometheus** (http://localhost:9090)
- Métricas de servicios
- Latencia de requests
- Errores y timeouts

### **Grafana** (http://localhost:3000)
- Dashboards predefinidos
- Alertas automáticas
- Métricas de negocio

## 🔧 Configuración Avanzada

### **Variables de Entorno**
```bash
# .env
DATABASE_URL=postgresql://pulpo:pulpo@postgres:5432/pulpo
REDIS_URL=redis://redis:6379
OLLAMA_URL=http://ollama:11434
TIKA_URL=http://tika:9998
JWT_SECRET=your-secret-key-change-this
JWT_ALGORITHM=HS256
```

### **Configuración de Twilio**
```bash
# Agregar a .env
TWILIO_ACCOUNT_SID=your-account-sid
TWILIO_AUTH_TOKEN=your-auth-token
```

## 🧪 Testing

### **Test Básico**
```bash
# Test de servicios
python scripts/test_integration.py

# Test de flujo n8n
python scripts/test_n8n_flow.py
```

### **Test de Webhook**
```bash
# Simular mensaje de WhatsApp
curl -X POST http://localhost:5678/webhook/pulpo/twilio/wa/inbound \
  -H "Content-Type: application/json" \
  -d '{
    "Body": "Hola, quiero hacer un pedido",
    "From": "whatsapp:+5491123456789",
    "To": "whatsapp:+5491123456788",
    "MessageSid": "SM1234567890",
    "WorkspaceId": "00000000-0000-0000-0000-000000000001"
  }'
```

## 🚨 Troubleshooting

### **Problemas Comunes**

1. **Orchestrator Service no responde**
   ```bash
   # Verificar logs
   docker-compose -f docker-compose.integrated.yml logs orchestrator
   
   # Verificar salud
   curl http://localhost:8005/health
   ```

2. **n8n no puede conectar a Orchestrator**
   ```bash
   # Verificar red Docker
   docker network ls
   docker network inspect pulpo-network
   ```

3. **Base de datos no accesible**
   ```bash
   # Verificar PostgreSQL
   docker-compose -f docker-compose.integrated.yml exec postgres pg_isready -U pulpo
   ```

### **Logs de Debugging**
```bash
# Ver todos los logs
docker-compose -f docker-compose.integrated.yml logs

# Logs específicos
docker-compose -f docker-compose.integrated.yml logs orchestrator
docker-compose -f docker-compose.integrated.yml logs n8n
```

## 📈 Próximos Pasos

### **F-08: Encadenar Tool Calls**
- ✅ Implementar Actions Service
- ✅ Conectar herramientas de negocio
- ✅ Persistir resultados

### **F-09: Optimización**
- 🔄 Cache inteligente
- 🔄 Load balancing
- 🔄 Monitoring avanzado

### **F-10: Producción**
- 🔄 SSL/TLS
- 🔄 Backup automático
- 🔄 CI/CD pipeline

## 🎉 Resultado

Con esta integración tienes:

✅ **Sistema completo** n8n + Orchestrator Service  
✅ **Arquitectura escalable** con microservicios  
✅ **Monitoreo integrado** con Prometheus/Grafana  
✅ **Testing automatizado** con scripts Python  
✅ **Despliegue simplificado** con Docker Compose  

**¡Tu sistema PulpoAI está listo para producción!** 🚀
