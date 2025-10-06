"""
Script para cargar catálogos de negocio desde CSV
Carga: staff, servicios, items de menú
"""

import asyncio
import asyncpg
import csv
import json
import os
import sys
from pathlib import Path

# Database configuration
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@localhost:5432/pulpo")

async def load_csv_to_dict(csv_path: str) -> list[dict]:
    """Carga CSV y retorna lista de dicts"""
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        return list(reader)

async def load_staff(conn: asyncpg.Connection, workspace_id: str, csv_path: str):
    """Carga staff desde CSV"""
    print(f"\n📋 Cargando staff desde: {csv_path}")

    # Leer CSV
    rows = await load_csv_to_dict(csv_path)

    # Insertar cada empleado
    inserted = 0
    for row in rows:
        # Parsear skills JSON
        skills = json.loads(row['skills']) if row.get('skills') else []

        try:
            await conn.execute("""
                INSERT INTO pulpo.staff (
                    workspace_id, name, email, phone, role,
                    is_active, google_calendar_id, skills
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (workspace_id, email) DO NOTHING
            """,
                workspace_id,
                row['name'],
                row['email'],
                row.get('phone'),
                row.get('role'),
                row.get('is_active', 'true').lower() == 'true',
                row.get('google_calendar_id'),
                json.dumps(skills)
            )
            inserted += 1
            print(f"  ✅ {row['name']} ({row['role']})")
        except Exception as e:
            print(f"  ❌ Error insertando {row['name']}: {e}")

    print(f"\n✅ Staff cargado: {inserted}/{len(rows)}")

async def load_service_types(conn: asyncpg.Connection, workspace_id: str, csv_path: str):
    """Carga tipos de servicio desde CSV"""
    print(f"\n📋 Cargando servicios desde: {csv_path}")

    # Leer CSV
    rows = await load_csv_to_dict(csv_path)

    # Insertar cada servicio
    inserted = 0
    for row in rows:
        try:
            await conn.execute("""
                INSERT INTO pulpo.service_types (
                    workspace_id, name, description, category,
                    price, currency, duration_minutes,
                    is_active, requires_staff
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (workspace_id, name) DO UPDATE
                SET price = EXCLUDED.price,
                    duration_minutes = EXCLUDED.duration_minutes,
                    is_active = EXCLUDED.is_active
            """,
                workspace_id,
                row['name'],
                row.get('description'),
                row.get('category'),
                float(row.get('price', 0)),
                row.get('currency', 'ARS'),
                int(row.get('duration_minutes', 60)),
                row.get('is_active', 'true').lower() == 'true',
                row.get('requires_staff', 'true').lower() == 'true'
            )
            inserted += 1
            print(f"  ✅ {row['name']} (${row.get('price', 0)} - {row.get('duration_minutes', 60)}min)")
        except Exception as e:
            print(f"  ❌ Error insertando {row['name']}: {e}")

    print(f"\n✅ Servicios cargados: {inserted}/{len(rows)}")

async def load_menu_items(conn: asyncpg.Connection, workspace_id: str, csv_path: str):
    """Carga items de menú desde CSV"""
    print(f"\n📋 Cargando menú desde: {csv_path}")

    # Leer CSV
    rows = await load_csv_to_dict(csv_path)

    # Insertar cada item
    inserted = 0
    for row in rows:
        try:
            await conn.execute("""
                INSERT INTO pulpo.menu_items (
                    workspace_id, sku, nombre, descripcion,
                    precio, categoria, disponible, imagen_url
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8)
                ON CONFLICT (workspace_id, sku) DO UPDATE
                SET precio = EXCLUDED.precio,
                    disponible = EXCLUDED.disponible,
                    descripcion = EXCLUDED.descripcion
            """,
                workspace_id,
                row.get('sku'),
                row['nombre'],
                row.get('descripcion'),
                float(row.get('precio', 0)),
                row.get('categoria'),
                row.get('disponible', 'true').lower() == 'true',
                row.get('imagen_url')
            )
            inserted += 1
            print(f"  ✅ {row['nombre']} (${row.get('precio', 0)})")
        except Exception as e:
            print(f"  ❌ Error insertando {row['nombre']}: {e}")

    print(f"\n✅ Menú cargado: {inserted}/{len(rows)}")

async def assign_services_to_staff(conn: asyncpg.Connection, workspace_id: str):
    """Asigna servicios a staff basado en skills"""
    print(f"\n🔗 Asignando servicios a staff...")

    # Obtener staff con skills
    staff = await conn.fetch("""
        SELECT id, name, skills
        FROM pulpo.staff
        WHERE workspace_id = $1 AND is_active = true
    """, workspace_id)

    # Obtener servicios
    services = await conn.fetch("""
        SELECT id, name, category
        FROM pulpo.service_types
        WHERE workspace_id = $1 AND is_active = true
    """, workspace_id)

    assigned = 0
    for staff_member in staff:
        skills = json.loads(staff_member['skills']) if staff_member['skills'] else []

        for service in services:
            # Lógica simple: si skill contiene parte del nombre del servicio
            should_assign = False
            service_name_lower = service['name'].lower()

            for skill in skills:
                if skill.lower() in service_name_lower or service_name_lower in skill.lower():
                    should_assign = True
                    break

            # También asignar si la categoría matchea
            if service['category'] in skills:
                should_assign = True

            if should_assign:
                try:
                    await conn.execute("""
                        INSERT INTO pulpo.staff_services (workspace_id, staff_id, service_type_id)
                        VALUES ($1, $2, $3)
                        ON CONFLICT (staff_id, service_type_id) DO NOTHING
                    """, workspace_id, staff_member['id'], service['id'])
                    assigned += 1
                    print(f"  ✅ {staff_member['name']} → {service['name']}")
                except Exception as e:
                    print(f"  ❌ Error asignando: {e}")

    print(f"\n✅ Asignaciones creadas: {assigned}")

async def load_catalog(workspace_id: str, vertical: str, templates_dir: str = "config/templates"):
    """Carga catálogo completo para un workspace"""

    print("="*70)
    print(f"📦 CARGANDO CATÁLOGO DE NEGOCIO")
    print("="*70)
    print(f"Workspace ID: {workspace_id}")
    print(f"Vertical: {vertical}")
    print(f"Templates dir: {templates_dir}")
    print("="*70)

    # Conectar a database
    conn = await asyncpg.connect(DATABASE_URL)

    try:
        # Set workspace context
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Verificar que workspace existe
        workspace = await conn.fetchrow("""
            SELECT id, name FROM pulpo.workspaces WHERE id = $1
        """, workspace_id)

        if not workspace:
            print(f"❌ Workspace {workspace_id} no encontrado")
            return

        print(f"\n✅ Workspace encontrado: {workspace['name']}")

        # Cargar según vertical
        if vertical == "servicios":
            # Staff
            staff_csv = Path(templates_dir) / "servicios_staff.csv"
            if staff_csv.exists():
                await load_staff(conn, workspace_id, str(staff_csv))

            # Servicios
            services_csv = Path(templates_dir) / "servicios_services.csv"
            if services_csv.exists():
                await load_service_types(conn, workspace_id, str(services_csv))

            # Asignar servicios a staff
            await assign_services_to_staff(conn, workspace_id)

        elif vertical == "gastronomia":
            # Menú
            menu_csv = Path(templates_dir) / "gastronomia_menu.csv"
            if menu_csv.exists():
                await load_menu_items(conn, workspace_id, str(menu_csv))

            # Staff (opcional para gastronomía)
            staff_csv = Path(templates_dir) / "gastronomia_staff.csv"
            if staff_csv.exists():
                await load_staff(conn, workspace_id, str(staff_csv))

        elif vertical == "inmobiliaria":
            # Staff (asesores)
            staff_csv = Path(templates_dir) / "inmobiliaria_staff.csv"
            if staff_csv.exists():
                await load_staff(conn, workspace_id, str(staff_csv))

            # Propiedades (ya existe tabla pulpo.properties)
            print("\n📋 Para inmobiliaria, usar tabla 'properties' existente")

        print("\n" + "="*70)
        print("✅ CATÁLOGO CARGADO EXITOSAMENTE")
        print("="*70)

    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()

    finally:
        await conn.close()

async def main():
    """Main entry point"""

    # Argumentos por defecto
    if len(sys.argv) < 3:
        print("Uso: python scripts/load_business_catalog.py <workspace_id> <vertical> [templates_dir]")
        print("\nEjemplos:")
        print("  python scripts/load_business_catalog.py 550e8400-e29b-41d4-a716-446655440000 servicios")
        print("  python scripts/load_business_catalog.py 550e8400-e29b-41d4-a716-446655440001 gastronomia")
        print("\nVerticales soportadas: servicios, gastronomia, inmobiliaria")
        sys.exit(1)

    workspace_id = sys.argv[1]
    vertical = sys.argv[2]
    templates_dir = sys.argv[3] if len(sys.argv) > 3 else "config/templates"

    await load_catalog(workspace_id, vertical, templates_dir)

if __name__ == "__main__":
    asyncio.run(main())
