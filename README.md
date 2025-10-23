# 🐙 PulpoAI - Agente Inteligente para Servicios y Reservas

**Un agente conversacional que actúa como empleado de tu negocio de servicios.**

PulpoAI es un SaaS multi-tenant que brinda a negocios de servicios (peluquerías, spas, salones, etc.) un agente inteligente capaz de:
- 💬 Conversar naturalmente con clientes vía WhatsApp
- 📊 Consultar información del negocio (servicios, precios, horarios)
- 📅 Gestionar reservas de turnos automáticamente
- 🔄 Integrarse con Google Calendar

---

## 🎯 Filosofía del Proyecto

**No es un bot. Es un agente inteligente.**

- **IA para comprender**: LLM para entender intenciones y contexto
- **Código determinístico para ejecutar**: Validaciones, políticas y acciones confiables
- **Multi-tenant real**: Cada workspace aislado, sin mezcla de datos
- **Medible y escalable**: Métricas en cada paso, telemetría completa

---

## 🏗️ Arquitectura del Agente

### Loop Principal: **Percepción → Cognición → Acción**

```
Usuario (WhatsApp) 
    ↓
1. PERCEPCIÓN: Intent Detection + Entity Extraction (LLM)
    ↓
2. COGNICIÓN: Planner decide qué tools ejecutar (LLM)
    ↓  
3. VALIDACIÓN: PolicyEngine valida permisos y args
    ↓
4. ACCIÓN: ToolBroker ejecuta tools via MCP
    ↓
5. MEMORIA: StateReducer actualiza estado conversacional
    ↓
6. RESPUESTA: LLM genera respuesta natural
```

### Componentes Core

#### 1. **OrchestratorService** (`services/orchestrator_service.py`)
- Cerebro del agente
- Coordina todo el flujo de decisión
- Gestiona memoria conversacional de 3 capas

#### 2. **Planner** (LLM-powered)
- Decide dinámicamente qué tools ejecutar
- No usa reglas hardcodeadas
- Se adapta al contexto de la conversación

#### 3. **PolicyEngine** (`services/policy_engine.py`)
- Valida permisos y argumentos
- Rate limiting per tenant
- Tier gating (basic/pro/max)

#### 4. **ToolBroker** (`services/tool_broker.py`)
- Ejecuta tools con robustez
- Retry logic + circuit breaker
- Idempotencia en writes

#### 5. **StateReducer** (`services/state_reducer.py`)
- Actualiza estado basado en observaciones
- Maneja slots canónicos
- Normaliza datos

#### 6. **Tools de Servicios** (`services/servicios_tools.py`)
- `get_available_services`: Lista servicios con precios
- `get_business_hours`: Horarios de atención
- `check_service_availability`: Verifica disponibilidad
- `book_appointment`: Crea reserva
- `cancel_appointment`: Cancela reserva
- `find_appointment_by_phone`: Busca reservas

---

## 🚀 Setup Rápido

### Requisitos
- Python 3.11+
- PostgreSQL 14+ con pgvector
- Docker & Docker Compose
- Cuenta de WhatsApp Business (Twilio)
- API Key de Claude/OpenAI

### Instalación

```bash
# 1. Clonar repo
git clone <repo-url>
cd pulpo

# 2. Variables de entorno
cp .env.example .env
# Editar .env con tus credenciales

# 3. Levantar base de datos
docker-compose up -d postgres

# 4. Aplicar migraciones
python scripts/apply_new_migrations.py

# 5. Cargar datos iniciales
python scripts/load_business_catalog.py

# 6. Levantar servicios
docker-compose up -d
```

### Configuración de WhatsApp

```bash
# Configurar webhook de Twilio
# URL: https://<tu-dominio>/api/orchestrator/webhook
# Método: POST
```

Ver detalles en la sección de WhatsApp más abajo.

---

## 📊 Estructura del Proyecto

```
/pulpo
├── /services              # Core del agente
│   ├── orchestrator_service.py      # Cerebro principal
│   ├── tool_broker.py               # Ejecución de tools
│   ├── policy_engine.py             # Validaciones
│   ├── state_reducer.py             # Gestión de estado
│   ├── servicios_tools.py           # Tools de servicios
│   ├── appointments_service.py      # Servicio de turnos
│   ├── vertical_prompt_generator.py # Prompts dinámicos
│   ├── intent_classifier.py         # Detección de intents
│   ├── canonical_slots.py           # Normalización
│   └── mcp_client.py                # Cliente MCP
│
├── /ai                    # Cliente LLM
│   └── multi_model_client.py
│
├── /api                   # REST API
│   └── orchestrator.py
│
├── /database              # PostgreSQL
│   ├── /init              # Schemas iniciales
│   └── /migrations        # Migraciones
│
├── /config                # Configuración
│   ├── vertical_prompts.yml
│   └── /tools
│       └── servicios.yml
│
├── /scripts               # Scripts de setup
│   ├── apply_new_migrations.py
│   ├── load_business_catalog.py
│   ├── setup_google_calendar.py
│   └── generate_jwt_token.py
│
├── /tests                 # Tests
│   ├── /unit
│   ├── /integration
│   └── /e2e
│
└── README.md              # Este archivo
```

---

## 🔧 Configuración

### Variables de Entorno Clave

```bash
# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/pulpo

# LLM
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# WhatsApp (Twilio)
TWILIO_ACCOUNT_SID=AC...
TWILIO_AUTH_TOKEN=...
TWILIO_WHATSAPP_NUMBER=whatsapp:+14155238886

# Google Calendar (opcional)
GOOGLE_OAUTH_CREDENTIALS_FILE=credentials/google_oauth_credentials.json

# Observability
ENABLE_TELEMETRY=true
LOG_LEVEL=INFO
```

### Configuración de Workspace

Cada negocio es un workspace. Configurar en `database/init/`:

```sql
INSERT INTO pulpo.workspaces (name, vertical, tier, settings) VALUES 
('Mi Peluquería', 'servicios', 'basic', '{
  "business_hours": {
    "lunes": "09:00-18:00",
    "martes": "09:00-18:00",
    ...
  },
  "services": [
    {"name": "Corte de Cabello", "price": 5000, "duration": 30},
    {"name": "Coloración", "price": 8000, "duration": 60}
  ]
}');
```

---

## 🧠 Cómo Funciona el Agente

### Ejemplo de Conversación

**Cliente:** "Hola, quiero un turno para corte"

```
1. Intent Detection (LLM)
   → intent: "execute_action" (booking)
   → confidence: 0.92

2. Planner (LLM)
   → Decide ejecutar: get_available_services, check_service_availability
   
3. Policy Validation
   → ✅ Workspace tiene tier "basic" → permitido
   → ✅ Args completos → permitido

4. Tool Execution
   → get_available_services(workspace_id="abc") 
   → Resultado: [{name: "Corte", price: 5000}, ...]

5. State Update
   → slots: {service_type: "corte", ...}
   
6. Response Generation (LLM)
   → "Perfecto, tenemos corte disponible a $5000. ¿Qué día te viene bien?"
```

**Cliente:** "Mañana a las 3pm"

```
1. Entity Extraction (LLM)
   → preferred_date: "2025-10-16"
   → preferred_time: "15:00"

2. Planner
   → check_service_availability(date="2025-10-16", time="15:00")
   
3. Tool Execution
   → Disponible: ✅

4. Response
   → "Perfecto, confirmo corte para mañana 16/10 a las 15:00. ¿Cuál es tu nombre y email?"
```

---

## 📱 Integración WhatsApp (Twilio)

### 1. Crear Cuenta Twilio
- https://www.twilio.com/
- Activar WhatsApp Sandbox o número productivo

### 2. Configurar Webhook

```
URL: https://tu-dominio.com/api/orchestrator/webhook
Método: POST
```

### 3. Probar Conexión

```bash
# Enviar mensaje de prueba
curl -X POST https://tu-dominio.com/api/orchestrator/webhook \
  -H "Content-Type: application/json" \
  -d '{
    "From": "whatsapp:+5491123456789",
    "Body": "Hola",
    "WaId": "5491123456789"
  }'
```

---

## 📊 Métricas y Observabilidad

El agente registra todas las operaciones para análisis:

### Eventos Clave
- `intent_detected`: Intent clasificado con confianza
- `fsm_state_change`: Cambio de estado conversacional
- `tool_called`: Ejecución de tool (success/error)
- `booking_confirmed`: Reserva completada
- `booking_cancelled`: Cancelación procesada

### Métricas en Tiempo Real

```python
# Ver métricas de un workspace
from services.telemetry_logger import telemetry_logger

summary = telemetry_logger.get_workspace_summary("workspace-123")
print(f"Booking Success Rate: {summary['booking_success_rate']}")
print(f"Avg Response Time: {summary['avg_response_time_ms']}ms")
```

### Integración Prometheus/Grafana

```yaml
# config/prometheus.yml ya configurado
# Levantar stack de monitoreo:
docker-compose --profile monitoring up -d
```

---

## 🧪 Testing

```bash
# Tests unitarios
pytest tests/unit/

# Tests de integración
pytest tests/integration/

# Tests E2E (simula WhatsApp)
pytest tests/e2e/

# Test manual de conversación
python -m services.orchestrator_app
# Luego enviar POST a http://localhost:8000/decide
```

---

## 🔒 Seguridad Multi-tenant

### Principios
1. **Aislamiento total**: Cada workspace ve solo sus datos
2. **RLS en Postgres**: Row Level Security en todas las tablas
3. **Workspace context**: Todas las queries filtran por `workspace_id`
4. **Validación de permisos**: PolicyEngine valida cada acción

### Ejemplo de Query Segura

```python
# ❌ MAL - Sin filtro de workspace
SELECT * FROM appointments;

# ✅ BIEN - Con workspace_id
SELECT * FROM appointments WHERE workspace_id = $1;
```

---

## 📈 Roadmap

### ✅ Fase 1 (Completada)
- Agent loop con LLM planner
- Tools de servicios básicos
- Intent detection inteligente
- Multi-tenant con RLS

### 🚧 Fase 2 (En Progreso)
- Mejora de extracción de entidades
- Reagendamiento inteligente
- Cancelación por teléfono
- Mejor manejo de ambigüedad

### 📋 Fase 3 (Próximamente)
- Integración con más calendarios
- Reportes para negocios
- Sistema de notificaciones
- Panel de admin

---

## 🤝 Contribuir

Este es un proyecto privado, pero si tenés acceso:

1. Crear branch desde `main`
2. Hacer cambios siguiendo principios SOLID
3. Agregar tests
4. PR con descripción clara
5. Review requerido antes de merge

### Principios de Código
- **SOLID**: Cada clase tiene una responsabilidad
- **No hardcodear**: Usar config/prompts dinámicos
- **Logs estructurados**: Sin `print()`, usar logger
- **Tests obligatorios**: Especialmente para tools
- **Documentación inline**: Docstrings en funciones complejas

---

## 📞 Soporte

**Equipo PulpoAI**

Para consultas: [contacto interno]

---

## 📄 Licencia

Propietario - Todos los derechos reservados

---

**Última actualización**: 2025-01-15  
**Versión**: 2.0