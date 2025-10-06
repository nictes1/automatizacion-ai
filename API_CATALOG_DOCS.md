# 📡 Catalog API - Documentación

API REST para gestión de catálogos de negocio (peluquería).

## 🚀 Inicio Rápido

### Iniciar API

```bash
# Puerto: 8008
python3 services/catalog_api.py

# Con uvicorn (recomendado)
uvicorn services.catalog_api:app --host 0.0.0.0 --port 8008 --reload
```

### Health Check

```bash
curl http://localhost:8008/health
```

**Response:**
```json
{
  "status": "ok",
  "service": "catalog_api",
  "timestamp": "2025-10-06T..."
}
```

## 🔑 Autenticación

Todas las requests (excepto `/health`) requieren header:

```
X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000
```

## 📋 Endpoints

### Staff Management

#### 1. Listar Staff

```bash
GET /api/staff
```

**Query params:**
- `is_active` (bool): Filtrar por activos
- `role` (str): Filtrar por rol
- `limit` (int): Máximo resultados (default 100)
- `offset` (int): Paginación

**Ejemplo:**

```bash
curl -X GET 'http://localhost:8008/api/staff?is_active=true' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

**Response:**
```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "name": "María García",
    "email": "maria.garcia@peluqueria.com",
    "phone": "+5491123456789",
    "role": "Peluquera Senior",
    "is_active": true,
    "google_calendar_id": "maria.garcia@gmail.com",
    "skills": ["corte", "coloración", "brushing"],
    "working_hours": {
      "monday": ["09:00-13:00", "14:00-18:00"],
      "tuesday": ["09:00-13:00", "14:00-18:00"]
    },
    "metadata": {},
    "created_at": "2025-10-06T...",
    "updated_at": "2025-10-06T..."
  }
]
```

#### 2. Obtener Staff por ID

```bash
GET /api/staff/{staff_id}
```

**Ejemplo:**

```bash
curl -X GET 'http://localhost:8008/api/staff/uuid-del-staff' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

**Response:** Igual que item en lista

**Errores:**
- `404`: Staff no encontrado

#### 3. Crear Staff

```bash
POST /api/staff
```

**Body:**
```json
{
  "name": "Nuevo Empleado",
  "email": "nuevo@peluqueria.com",
  "phone": "+5491123456789",
  "role": "Peluquero",
  "is_active": true,
  "google_calendar_id": "nuevo@gmail.com",
  "skills": ["corte", "barba"],
  "working_hours": {
    "monday": ["09:00-18:00"],
    "wednesday": ["09:00-18:00"],
    "friday": ["09:00-18:00"]
  },
  "metadata": {}
}
```

**Ejemplo:**

```bash
curl -X POST 'http://localhost:8008/api/staff' \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{
    "name": "Nuevo Empleado",
    "email": "nuevo@peluqueria.com",
    "role": "Peluquero",
    "skills": ["corte"]
  }'
```

**Response:** Staff creado (igual estructura)

**Errores:**
- `409`: Email ya existe

#### 4. Actualizar Staff

```bash
PUT /api/staff/{staff_id}
```

**Body:** (todos los campos opcionales)
```json
{
  "name": "Nombre Actualizado",
  "phone": "+5491199999999",
  "is_active": false
}
```

**Ejemplo:**

```bash
curl -X PUT 'http://localhost:8008/api/staff/uuid-del-staff' \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{
    "is_active": false
  }'
```

**Response:** Staff actualizado

**Errores:**
- `404`: Staff no encontrado
- `400`: No hay campos para actualizar

#### 5. Eliminar Staff (Soft Delete)

```bash
DELETE /api/staff/{staff_id}
```

**Ejemplo:**

```bash
curl -X DELETE 'http://localhost:8008/api/staff/uuid-del-staff' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

**Response:** `204 No Content`

**Nota:** Es soft delete, solo marca `is_active=false`

**Errores:**
- `404`: Staff no encontrado

---

### Service Types Management

#### 1. Listar Servicios

```bash
GET /api/service-types
```

**Query params:**
- `is_active` (bool): Filtrar por activos
- `category` (str): Filtrar por categoría
- `limit` (int): Máximo resultados (default 100)
- `offset` (int): Paginación

**Ejemplo:**

```bash
curl -X GET 'http://localhost:8008/api/service-types?is_active=true&category=hair' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

**Response:**
```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "name": "Corte de Cabello",
    "description": "Corte de cabello con lavado incluido",
    "category": "hair",
    "price": 2500.0,
    "currency": "ARS",
    "duration_minutes": 45,
    "is_active": true,
    "requires_staff": true,
    "metadata": {},
    "created_at": "2025-10-06T...",
    "updated_at": "2025-10-06T..."
  }
]
```

#### 2. Obtener Servicio por ID

```bash
GET /api/service-types/{service_type_id}
```

**Ejemplo:**

```bash
curl -X GET 'http://localhost:8008/api/service-types/uuid-del-servicio' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

#### 3. Crear Servicio

```bash
POST /api/service-types
```

**Body:**
```json
{
  "name": "Nuevo Servicio",
  "description": "Descripción del servicio",
  "category": "hair",
  "price": 3000.0,
  "currency": "ARS",
  "duration_minutes": 60,
  "is_active": true,
  "requires_staff": true,
  "metadata": {}
}
```

**Ejemplo:**

```bash
curl -X POST 'http://localhost:8008/api/service-types' \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{
    "name": "Peinado Express",
    "description": "Peinado rápido sin lavado",
    "category": "hair",
    "price": 1500.0,
    "duration_minutes": 20
  }'
```

**Errores:**
- `409`: Servicio con ese nombre ya existe

#### 4. Actualizar Servicio

```bash
PUT /api/service-types/{service_type_id}
```

**Body:** (todos los campos opcionales)
```json
{
  "price": 3500.0,
  "duration_minutes": 50,
  "is_active": false
}
```

**Ejemplo:**

```bash
curl -X PUT 'http://localhost:8008/api/service-types/uuid-del-servicio' \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{
    "price": 2800.0
  }'
```

#### 5. Eliminar Servicio (Soft Delete)

```bash
DELETE /api/service-types/{service_type_id}
```

**Ejemplo:**

```bash
curl -X DELETE 'http://localhost:8008/api/service-types/uuid-del-servicio' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

**Response:** `204 No Content`

---

### Appointments (Read-Only)

#### 1. Listar Turnos

```bash
GET /api/appointments
```

**Query params:**
- `status` (str): scheduled, confirmed, completed, cancelled
- `staff_id` (uuid): Filtrar por staff
- `from_date` (ISO): Fecha desde
- `to_date` (ISO): Fecha hasta
- `limit` (int): Máximo resultados
- `offset` (int): Paginación

**Ejemplo:**

```bash
# Turnos de hoy
curl -X GET 'http://localhost:8008/api/appointments?from_date=2025-10-06T00:00:00&to_date=2025-10-06T23:59:59&status=scheduled' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'

# Turnos de un staff específico
curl -X GET 'http://localhost:8008/api/appointments?staff_id=uuid-del-staff' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000'
```

**Response:**
```json
[
  {
    "id": "uuid",
    "workspace_id": "uuid",
    "conversation_id": "uuid",
    "service_type_id": "uuid",
    "service_name": "Corte de Cabello",
    "staff_id": "uuid",
    "staff_name": "María García",
    "client_name": "Juan Pérez",
    "client_email": "juan@example.com",
    "client_phone": "+5491123456789",
    "scheduled_at": "2025-10-07T15:00:00",
    "duration_minutes": 45,
    "status": "scheduled",
    "notes": null,
    "google_event_id": "google-calendar-event-id",
    "created_at": "2025-10-06T..."
  }
]
```

---

## 🔍 Ejemplos de Integración con UI

### React/Next.js Example

```typescript
// api/catalog.ts
const API_BASE = 'http://localhost:8008'
const WORKSPACE_ID = '550e8400-e29b-41d4-a716-446655440000'

const headers = {
  'Content-Type': 'application/json',
  'X-Workspace-Id': WORKSPACE_ID
}

// List staff
export async function listStaff(isActive?: boolean) {
  const params = new URLSearchParams()
  if (isActive !== undefined) params.append('is_active', String(isActive))

  const response = await fetch(`${API_BASE}/api/staff?${params}`, { headers })
  return response.json()
}

// Create staff
export async function createStaff(data: StaffCreate) {
  const response = await fetch(`${API_BASE}/api/staff`, {
    method: 'POST',
    headers,
    body: JSON.stringify(data)
  })
  return response.json()
}

// Update staff
export async function updateStaff(staffId: string, data: Partial<StaffCreate>) {
  const response = await fetch(`${API_BASE}/api/staff/${staffId}`, {
    method: 'PUT',
    headers,
    body: JSON.stringify(data)
  })
  return response.json()
}

// Delete staff
export async function deleteStaff(staffId: string) {
  await fetch(`${API_BASE}/api/staff/${staffId}`, {
    method: 'DELETE',
    headers
  })
}
```

### Vue.js Example

```javascript
// composables/useCatalog.js
import { ref } from 'vue'

export function useCatalog() {
  const API_BASE = 'http://localhost:8008'
  const WORKSPACE_ID = '550e8400-e29b-41d4-a716-446655440000'

  const staff = ref([])
  const serviceTypes = ref([])

  const headers = {
    'Content-Type': 'application/json',
    'X-Workspace-Id': WORKSPACE_ID
  }

  async function fetchStaff() {
    const response = await fetch(`${API_BASE}/api/staff`, { headers })
    staff.value = await response.json()
  }

  async function fetchServiceTypes() {
    const response = await fetch(`${API_BASE}/api/service-types`, { headers })
    serviceTypes.value = await response.json()
  }

  return {
    staff,
    serviceTypes,
    fetchStaff,
    fetchServiceTypes
  }
}
```

---

## 🐛 Errores Comunes

### 400 - Bad Request

```json
{
  "detail": "X-Workspace-Id header required"
}
```

**Solución:** Agregar header `X-Workspace-Id`

### 404 - Not Found

```json
{
  "detail": "Staff not found"
}
```

**Solución:** Verificar que el ID existe

### 409 - Conflict

```json
{
  "detail": "Staff with this email already exists"
}
```

**Solución:** Usar otro email o actualizar el staff existente

### 500 - Internal Server Error

```json
{
  "detail": "Database pool not initialized"
}
```

**Solución:**
1. Verificar que PostgreSQL está activo: `docker ps | grep postgres`
2. Verificar DATABASE_URL correcto

---

## 🧪 Testing

### Verificar API Funciona

```bash
# 1. Iniciar API
python3 services/catalog_api.py

# 2. Health check
curl http://localhost:8008/health

# 3. Listar staff (debe tener seed data)
curl -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  http://localhost:8008/api/staff

# 4. Listar servicios
curl -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  http://localhost:8008/api/service-types
```

### Crear Staff Completo

```bash
curl -X POST 'http://localhost:8008/api/staff' \
  -H 'Content-Type: application/json' \
  -H 'X-Workspace-Id: 550e8400-e29b-41d4-a716-446655440000' \
  -d '{
    "name": "Test Staff",
    "email": "test@test.com",
    "phone": "+5491111111111",
    "role": "Tester",
    "is_active": true,
    "skills": ["test"],
    "working_hours": {
      "monday": ["09:00-18:00"]
    }
  }'
```

---

## 🚀 Deployment

### Docker

Agregar a `docker-compose.yml`:

```yaml
services:
  catalog-api:
    build: .
    command: uvicorn services.catalog_api:app --host 0.0.0.0 --port 8008
    ports:
      - "8008:8008"
    environment:
      - DATABASE_URL=postgresql://pulpo:pulpo@postgres:5432/pulpo
    depends_on:
      - postgres
```

### Con Nginx Reverse Proxy

```nginx
server {
    listen 80;
    server_name api.tudominio.com;

    location /catalog/ {
        proxy_pass http://localhost:8008/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }
}
```

---

## 📚 Documentación Interactiva

### Swagger UI (automático)

```
http://localhost:8008/docs
```

### ReDoc

```
http://localhost:8008/redoc
```

### OpenAPI JSON

```
http://localhost:8008/openapi.json
```

---

## 🔐 Seguridad en Producción

### TODO antes de producción:

1. **CORS**: Restringir origins
   ```python
   allow_origins=["https://tu-dominio.com"]
   ```

2. **Authentication**: Agregar JWT
   ```python
   from fastapi.security import HTTPBearer
   ```

3. **Rate Limiting**: Limitar requests
   ```python
   from slowapi import Limiter
   ```

4. **HTTPS**: Usar certificado SSL

5. **Environment Variables**: No hardcodear workspace_id

---

**Documentación completa:** Ver código en `services/catalog_api.py`

**Próximos endpoints:**
- Staff availability check
- Bulk operations
- Export/import CSV
- Statistics/analytics
