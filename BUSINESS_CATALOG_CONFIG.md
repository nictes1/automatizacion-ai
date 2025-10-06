# 📦 Configuración de Catálogos de Negocio

Sistema para cargar y gestionar catálogos variables por negocio (servicios, staff, menú) **sin usar RAG**.

## 🎯 Objetivo

Cada negocio necesita configurar:
- **Peluquería**: Staff (peluqueros) + Servicios (corte, coloración, etc.)
- **Restaurante**: Items de menú + Precios
- **Inmobiliaria**: Asesores + Propiedades

Los datos se almacenan en **tablas relacionales** para queries rápidos, sin necesidad de RAG/embeddings.

## 📊 Estructura de Datos

### Tablas Creadas

1. **`pulpo.staff`** - Empleados/Staff
   - Peluqueros, chefs, asesores, etc.
   - Integración con Google Calendar
   - Skills/especialidades en JSON

2. **`pulpo.service_types`** - Tipos de Servicio
   - Catálogo de servicios ofrecidos
   - Precio, duración, categoría
   - Activo/inactivo

3. **`pulpo.staff_services`** - Relación M2M
   - Qué servicios puede realizar cada empleado
   - Custom pricing/duration por staff

4. **`pulpo.menu_items`** - Items de Menú (ya existía)
   - SKU, nombre, descripción
   - Precio, categoría
   - Disponible/no disponible

### Archivos SQL

- `database/init/05_business_catalog.sql` - Tablas y funciones
- `database/init/06_business_seed.sql` - Datos de ejemplo

## 🚀 Carga de Datos

### Opción 1: Desde CSV (Recomendado)

#### 1. Templates Disponibles

```bash
config/templates/
├── servicios_staff.csv          # Staff para peluquería/spa
├── servicios_services.csv       # Servicios ofrecidos
└── gastronomia_menu.csv         # Items de menú
```

#### 2. Ejecutar Carga

```bash
# Cargar catálogo de peluquería
python3 scripts/load_business_catalog.py 550e8400-e29b-41d4-a716-446655440000 servicios

# Cargar menú de restaurante
python3 scripts/load_business_catalog.py 550e8400-e29b-41d4-a716-446655440001 gastronomia

# Desde directorio custom
python3 scripts/load_business_catalog.py <workspace_id> servicios path/to/custom/templates
```

#### 3. Salida Esperada

```
================================================================================
📦 CARGANDO CATÁLOGO DE NEGOCIO
================================================================================
Workspace ID: 550e8400-e29b-41d4-a716-446655440000
Vertical: servicios
================================================================================

✅ Workspace encontrado: Peluquería Estilo

📋 Cargando staff desde: config/templates/servicios_staff.csv
  ✅ María García (Peluquera Senior)
  ✅ Juan Pérez (Peluquero)
  ✅ Ana López (Estilista)
  ✅ Carlos Martínez (Barbero)

✅ Staff cargado: 4/4

📋 Cargando servicios desde: config/templates/servicios_services.csv
  ✅ Corte de Cabello ($2500 - 45min)
  ✅ Coloración Completa ($6500 - 120min)
  ...

✅ Servicios cargados: 10/10

🔗 Asignando servicios a staff...
  ✅ María García → Corte de Cabello
  ✅ María García → Coloración Completa
  ...

✅ Asignaciones creadas: 15

================================================================================
✅ CATÁLOGO CARGADO EXITOSAMENTE
================================================================================
```

### Opción 2: Desde SQL (Automático)

Al iniciar Docker, se carga automáticamente `06_business_seed.sql` con datos de ejemplo:

```bash
docker-compose up -d postgres

# Los datos se cargan automáticamente en:
# - Workspace: 550e8400-e29b-41d4-a716-446655440000 (Servicios)
# - Workspace: 550e8400-e29b-41d4-a716-446655440001 (Gastronomía)
# - Workspace: 550e8400-e29b-41d4-a716-446655440002 (Inmobiliaria)
```

### Opción 3: Desde Código (Programático)

```python
import asyncpg

async def load_staff(workspace_id: str):
    conn = await asyncpg.connect(DATABASE_URL)

    await conn.execute("""
        INSERT INTO pulpo.staff (workspace_id, name, email, role, skills)
        VALUES ($1, $2, $3, $4, $5)
    """, workspace_id, "María García", "maria@peluqueria.com", "Peluquera", '["corte", "coloración"]')

    await conn.close()
```

## 📝 Formato de Templates CSV

### servicios_staff.csv

```csv
name,email,phone,role,is_active,google_calendar_id,skills
María García,maria@peluqueria.com,+5491123456789,Peluquera Senior,true,maria@gmail.com,"[""corte"",""coloración""]"
```

**Columnas:**
- `name` (requerido): Nombre del empleado
- `email` (requerido): Email (único por workspace)
- `phone`: Teléfono
- `role`: Rol (Peluquera, Chef, Asesor, etc.)
- `is_active`: `true`/`false`
- `google_calendar_id`: Email de Google Calendar
- `skills`: Array JSON de habilidades

### servicios_services.csv

```csv
name,description,category,price,currency,duration_minutes,is_active,requires_staff
Corte de Cabello,Corte con lavado incluido,hair,2500,ARS,45,true,true
```

**Columnas:**
- `name` (requerido): Nombre del servicio (único por workspace)
- `description`: Descripción
- `category`: Categoría (hair, nails, spa, etc.)
- `price`: Precio numérico
- `currency`: Moneda (ARS, USD, etc.)
- `duration_minutes`: Duración en minutos
- `is_active`: `true`/`false`
- `requires_staff`: Si requiere asignación de empleado

### gastronomia_menu.csv

```csv
sku,nombre,descripcion,precio,categoria,disponible,imagen_url
PIZZA-001,Pizza Margherita,Salsa de tomate con mozzarella,3500,pizzas,true,https://example.com/pizza.jpg
```

**Columnas:**
- `sku` (requerido): Código único (único por workspace)
- `nombre` (requerido): Nombre del plato
- `descripcion`: Descripción
- `precio`: Precio numérico
- `categoria`: Categoría (pizzas, pastas, etc.)
- `disponible`: `true`/`false`
- `imagen_url`: URL de imagen

## 🔍 Consultar Datos

### Listar Staff

```sql
SELECT id, name, email, role, skills
FROM pulpo.staff
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'
  AND is_active = true;
```

### Listar Servicios

```sql
SELECT id, name, price, duration_minutes, category
FROM pulpo.service_types
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'
  AND is_active = true;
```

### Servicios por Staff

```sql
SELECT
  s.name as staff_name,
  st.name as service_name,
  st.price,
  st.duration_minutes
FROM pulpo.staff s
JOIN pulpo.staff_services ss ON ss.staff_id = s.id
JOIN pulpo.service_types st ON st.id = ss.service_type_id
WHERE s.workspace_id = '550e8400-e29b-41d4-a716-446655440000'
  AND s.is_active = true
ORDER BY s.name, st.name;
```

### Staff Disponible para Servicio

```sql
SELECT * FROM pulpo.get_available_staff_for_service(
  '550e8400-e29b-41d4-a716-446655440000'::uuid,  -- workspace_id
  'service-type-id'::uuid,                       -- service_type_id
  '2025-10-07'::date,                            -- date
  '15:00'::time                                   -- time
);
```

### Menú por Categoría

```sql
SELECT nombre, descripcion, precio, categoria
FROM pulpo.menu_items
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001'
  AND disponible = true
ORDER BY categoria, precio;
```

## 🔄 Actualizar Datos

### Actualizar Precio de Servicio

```sql
UPDATE pulpo.service_types
SET price = 3000, updated_at = now()
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'
  AND name = 'Corte de Cabello';
```

### Desactivar Empleado

```sql
UPDATE pulpo.staff
SET is_active = false, updated_at = now()
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440000'
  AND email = 'maria@peluqueria.com';
```

### Marcar Item como No Disponible

```sql
UPDATE pulpo.menu_items
SET disponible = false, updated_at = now()
WHERE workspace_id = '550e8400-e29b-41d4-a716-446655440001'
  AND sku = 'PIZZA-001';
```

## 🎯 Uso en Actions Service

El Actions Service puede consultar estos catálogos para:

### 1. Validar Servicio Existe

```python
async def validate_service(workspace_id: str, service_name: str):
    result = await conn.fetchrow("""
        SELECT id, name, price, duration_minutes
        FROM pulpo.service_types
        WHERE workspace_id = $1 AND name ILIKE $2 AND is_active = true
    """, workspace_id, service_name)

    if not result:
        raise ValueError(f"Servicio '{service_name}' no encontrado")

    return result
```

### 2. Asignar Staff Automáticamente

```python
async def assign_staff_for_service(workspace_id: str, service_type_id: str):
    # Obtener staff que puede realizar el servicio
    staff = await conn.fetch("""
        SELECT s.id, s.name, s.email, s.google_calendar_id
        FROM pulpo.staff s
        JOIN pulpo.staff_services ss ON ss.staff_id = s.id
        WHERE s.workspace_id = $1
          AND ss.service_type_id = $2
          AND s.is_active = true
        ORDER BY RANDOM()  -- Asignación aleatoria
        LIMIT 1
    """, workspace_id, service_type_id)

    if not staff:
        # Fallback: cualquier staff activo
        staff = await conn.fetchrow("""
            SELECT id, name, email, google_calendar_id
            FROM pulpo.staff
            WHERE workspace_id = $1 AND is_active = true
            ORDER BY RANDOM()
            LIMIT 1
        """, workspace_id)

    return staff
```

### 3. Calcular Total de Pedido

```python
async def calculate_order_total(workspace_id: str, items: list[dict]):
    total = 0
    for item in items:
        result = await conn.fetchrow("""
            SELECT precio FROM pulpo.menu_items
            WHERE workspace_id = $1 AND sku = $2 AND disponible = true
        """, workspace_id, item['sku'])

        if result:
            total += result['precio'] * item['quantity']

    return total
```

## 🚀 Próximos Pasos

### Corto Plazo
- [x] Tablas base (staff, service_types)
- [x] Templates CSV
- [x] Script de carga
- [x] Seed data de ejemplo
- [ ] API REST para CRUD (dashboard admin)
- [ ] Validación de horarios de staff
- [ ] Gestión de disponibilidad

### Mediano Plazo
- [ ] Dashboard web para gestión
- [ ] Import/export masivo
- [ ] Integración con POS (punto de venta)
- [ ] Reportes de servicios más solicitados

### Largo Plazo
- [ ] Recomendaciones automáticas (ML)
- [ ] Precios dinámicos por demanda
- [ ] Multi-sucursal (diferentes locations)

## 📚 Referencias

### Archivos
- `database/init/05_business_catalog.sql` - Schema
- `database/init/06_business_seed.sql` - Seed data
- `scripts/load_business_catalog.py` - Carga desde CSV
- `config/templates/*.csv` - Templates

### Documentación Relacionada
- `CLAUDE.md` - Documentación general del proyecto
- `database/README.md` - Documentación de database
- `SISTEMA_CONVERSACIONAL_FINAL.md` - Sistema conversacional

---

**Última Actualización**: 2025-10-06
**Estado**: ✅ Production Ready
**Método**: SQL Directo (NO RAG)
