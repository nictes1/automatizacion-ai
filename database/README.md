# 🗄️ PulpoAI Database Service

## 📋 **Descripción**

Servicio de base de datos independiente para PulpoAI que incluye:
- **PostgreSQL 16** con extensión pgvector para embeddings
- **Redis** para cache y sesiones
- **pgAdmin** para administración
- **Esquema consolidado** con todas las tablas y funciones
- **RLS (Row Level Security)** para multitenancy
- **Datos iniciales** para desarrollo

## 🚀 **Inicio Rápido**

### **1. Levantar el servicio**
```bash
cd database
docker-compose up -d
```

### **2. Verificar que esté funcionando**
```bash
# PostgreSQL
docker exec -it pulpo-postgres psql -U pulpo -d pulpo -c "SELECT version();"

# Redis
docker exec -it pulpo-redis redis-cli ping

# Verificar tablas
docker exec -it pulpo-postgres psql -U pulpo -d pulpo -c "\dt pulpo.*"
```

### **3. Acceder a pgAdmin**
- URL: http://localhost:8080
- Email: admin@pulpo.ai
- Password: admin123

## 📊 **Estructura de la Base de Datos**

### **Esquemas**
- `pulpo` - Esquema principal con todas las tablas

### **Tablas Principales**
- **Core**: `workspaces`, `users`, `channels`, `contacts`, `conversations`, `messages`
- **Dialogue State**: `dialogue_states`, `dialogue_state_history`, `dialogue_slots`
- **RAG**: `documents`, `document_chunks`
- **Business Logic**: `business_actions`, `orders`, `properties`, `appointments`
- **Monitoring**: `system_metrics`, `error_logs`

### **Funciones PL/pgSQL**
- `pulpo.set_ws_context()` - Configurar contexto de workspace
- `pulpo.upsert_dialogue_state()` - Actualizar estado de diálogo
- `pulpo.apply_event()` - Aplicar eventos FSM
- `pulpo.search_documents()` - Búsqueda semántica
- `pulpo.execute_action()` - Ejecutar acciones de negocio

## 🔒 **Seguridad (RLS)**

### **Políticas de Acceso**
- **Usuarios autenticados**: Solo ven datos de sus workspaces
- **Servicios internos**: Acceso completo con rol `pulpo_service`
- **Aislamiento total**: Cada workspace solo ve sus propios datos

### **Configuración de Contexto**
```sql
-- Para usuarios
SELECT pulpo.set_ws_context('workspace-id');
SET pulpo.user_id = 'user-id';

-- Para servicios
SET ROLE pulpo_service;
```

## 🧪 **Datos de Prueba**

### **Workspaces de Ejemplo**
- **Restaurante El Buen Sabor** (gastronomía)
- **Inmobiliaria San Martín** (inmobiliaria)
- **Peluquería Estilo** (servicios)

### **Conversaciones de Ejemplo**
- Pedidos de comida
- Búsqueda de propiedades
- Agendamiento de turnos

## 🔧 **Configuración**

### **Variables de Entorno**
```bash
POSTGRES_DB=pulpo
POSTGRES_USER=pulpo
POSTGRES_PASSWORD=pulpo
```

### **Puertos**
- **PostgreSQL**: 5432
- **Redis**: 6379
- **pgAdmin**: 8080

### **Volúmenes**
- `postgres_data` - Datos de PostgreSQL
- `redis_data` - Datos de Redis
- `pgadmin_data` - Configuración de pgAdmin

## 📈 **Monitoreo**

### **Métricas de Sistema**
```sql
-- Ver métricas por workspace
SELECT * FROM pulpo.system_metrics 
WHERE workspace_id = 'workspace-id' 
ORDER BY recorded_at DESC;

-- Ver errores recientes
SELECT * FROM pulpo.error_logs 
WHERE workspace_id = 'workspace-id' 
ORDER BY created_at DESC;
```

### **Health Checks**
```bash
# PostgreSQL
docker exec pulpo-postgres pg_isready -U pulpo -d pulpo

# Redis
docker exec pulpo-redis redis-cli ping
```

## 🚨 **Troubleshooting**

### **Problemas Comunes**

1. **Error de conexión**
   ```bash
   # Verificar que el contenedor esté corriendo
   docker ps | grep pulpo
   
   # Ver logs
   docker logs pulpo-postgres
   ```

2. **Error de permisos RLS**
   ```sql
   -- Verificar contexto
   SELECT current_setting('pulpo.workspace_id', true);
   
   -- Configurar contexto
   SELECT pulpo.set_ws_context('workspace-id');
   ```

3. **Error de extensión pgvector**
   ```sql
   -- Verificar que esté instalada
   SELECT * FROM pg_extension WHERE extname = 'vector';
   ```

## 🔄 **Migraciones**

### **Estructura de Archivos**
```
database/
├── init/
│   ├── 01_schema.sql      # Esquema de tablas
│   ├── 02_functions.sql   # Funciones PL/pgSQL
│   ├── 03_rls.sql         # Políticas RLS
│   └── 04_seed.sql        # Datos iniciales
└── migrations/            # Migraciones futuras
```

### **Aplicar Cambios**
```bash
# Reiniciar con nuevos scripts
docker-compose down
docker-compose up -d
```

## 📚 **Documentación Adicional**

- [Esquema de Base de Datos](../docs/DATABASE_SCHEMA.md)
- [Funciones PL/pgSQL](../docs/DATABASE_FUNCTIONS.md)
- [Políticas RLS](../docs/DATABASE_RLS.md)
- [Guía de Migraciones](../docs/DATABASE_MIGRATIONS.md)
