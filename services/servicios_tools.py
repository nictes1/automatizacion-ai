"""
Tools para vertical Servicios (Peluquería)
Funciones que el orchestrator puede llamar para obtener información
"""

import asyncpg
import os
import json
from typing import Dict, List, Any, Optional
from datetime import datetime, date, time, timedelta
import logging

logger = logging.getLogger(__name__)

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@localhost:5432/pulpo")

# =========================
# Database Connection
# =========================

async def get_db_connection(workspace_id: str) -> asyncpg.Connection:
    """Get database connection with workspace context"""
    conn = await asyncpg.connect(DATABASE_URL)
    await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)
    return conn

# =========================
# TOOLS - Para usar en orchestrator
# =========================

async def get_available_services(workspace_id: str, category: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool: Obtiene lista de servicios disponibles con rangos de precio por staff

    Args:
        workspace_id: ID del workspace
        category: Filtrar por categoría (hair, nails, etc.)

    Returns:
        {
            "success": true,
            "services": [
                {
                    "id": "uuid",
                    "name": "Corte de Cabello",
                    "description": "...",
                    "price_min": 3500,
                    "price_max": 6000,
                    "currency": "ARS",
                    "staff_count": 3,
                    "staff_options": [
                        {"name": "Carlos", "price": 3500, "duration": 35},
                        {"name": "Juan", "price": 4500, "duration": 30},
                        {"name": "María", "price": 6000, "duration": 45}
                    ]
                }
            ]
        }
    """
    conn = await get_db_connection(workspace_id)

    try:
        query = """
            SELECT
                st.id::text as service_id,
                st.name as service_name,
                st.description,
                COALESCE(MIN(ss.price), 0) as price_min,
                COALESCE(MAX(ss.price), 0) as price_max,
                COALESCE(ss.currency, st.currency, 'ARS') as currency,
                COUNT(DISTINCT ss.staff_id) as staff_count,
                COALESCE(
                    json_agg(
                        json_build_object(
                            'staff_id', s.id::text,
                            'staff_name', s.name,
                            'price', ss.price,
                            'duration_minutes', ss.duration_minutes
                        ) ORDER BY ss.price
                    ) FILTER (WHERE ss.id IS NOT NULL),
                    '[]'::json
                ) as staff_options
            FROM pulpo.service_types st
            LEFT JOIN pulpo.staff_services ss ON ss.service_type_id = st.id AND ss.is_active = true
            LEFT JOIN pulpo.staff s ON s.id = ss.staff_id AND s.is_active = true
            WHERE st.workspace_id = $1 AND st.is_active = true
            GROUP BY st.id, st.name, st.description, ss.currency, st.currency
            ORDER BY price_min
        """
        params = [workspace_id]

        rows = await conn.fetch(query, *params)

        services = []
        for row in rows:
            # Parse staff_options if it's a JSON string
            staff_opts = row['staff_options'] if row['staff_options'] else []
            if isinstance(staff_opts, str):
                try:
                    staff_opts = json.loads(staff_opts)
                except:
                    staff_opts = []

            services.append({
                "id": row['service_id'],
                "name": row['service_name'],
                "description": row['description'],
                "price_min": float(row['price_min']) if row['price_min'] else 0,
                "price_max": float(row['price_max']) if row['price_max'] else 0,
                "currency": row['currency'],
                "staff_count": row['staff_count'],
                "staff_options": staff_opts
            })

        return {
            "success": True,
            "services": services,
            "count": len(services)
        }

    except Exception as e:
        logger.error(f"Error getting services: {e}")
        return {
            "success": False,
            "error": str(e),
            "services": []
        }
    finally:
        await conn.close()


async def check_service_availability(
    workspace_id: str,
    service_name: str,
    date_str: str,
    time_str: Optional[str] = None
) -> Dict[str, Any]:
    """
    Tool: Verifica disponibilidad para un servicio

    Args:
        workspace_id: ID del workspace
        service_name: Nombre del servicio
        date_str: Fecha en formato YYYY-MM-DD
        time_str: Hora en formato HH:MM (opcional)

    Returns:
        {
            "success": true,
            "available": true,
            "time_slots": ["09:00", "09:30", "10:00", ...],
            "service_info": {...}
        }
    """
    conn = await get_db_connection(workspace_id)

    try:
        # Get service info
        service = await conn.fetchrow("""
            SELECT id::text, name, duration_minutes, price_reference as price, currency
            FROM pulpo.service_types
            WHERE workspace_id = $1 AND name ILIKE $2 AND is_active = true
            LIMIT 1
        """, workspace_id, f"%{service_name}%")

        if not service:
            return {
                "success": False,
                "error": f"Servicio '{service_name}' no encontrado",
                "available": False
            }

        service_info = {
            "id": service['id'],
            "name": service['name'],
            "duration_minutes": service['duration_minutes'],
            "price": float(service['price']),
            "currency": service['currency']
        }

        # Parse date
        try:
            check_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except:
            return {
                "success": False,
                "error": "Formato de fecha inválido (usar YYYY-MM-DD)",
                "available": False
            }

        # Check if specific time requested
        if time_str:
            try:
                check_time = datetime.strptime(time_str, "%H:%M").time()
            except:
                return {
                    "success": False,
                    "error": "Formato de hora inválido (usar HH:MM)",
                    "available": False
                }

            # Check if business is open
            is_open = await conn.fetchval("""
                SELECT pulpo.is_business_open($1, $2, $3)
            """, workspace_id, check_date, check_time)

            if not is_open:
                return {
                    "success": True,
                    "available": False,
                    "reason": "Negocio cerrado en ese horario",
                    "service_info": service_info
                }

            # Check staff availability
            available_staff = await conn.fetch("""
                SELECT s.id::text, s.name
                FROM pulpo.staff s
                JOIN pulpo.staff_services ss ON ss.staff_id = s.id
                WHERE s.workspace_id = $1
                  AND ss.service_type_id = $2
                  AND s.is_active = true
                  AND pulpo.is_staff_available(
                    $1, s.id, $3, $4,
                    ($4::time + ($5 || ' minutes')::interval)::time
                  )
                LIMIT 1
            """, workspace_id, service['id'], check_date, check_time, service['duration_minutes'])

            if not available_staff:
                return {
                    "success": True,
                    "available": False,
                    "reason": "No hay staff disponible en ese horario",
                    "service_info": service_info
                }

            return {
                "success": True,
                "available": True,
                "time_slot": time_str,
                "service_info": service_info,
                "staff_assigned": {
                    "id": available_staff[0]['id'],
                    "name": available_staff[0]['name']
                }
            }

        # No specific time - return available slots
        slots = await conn.fetch("""
            SELECT time_slot::text, available
            FROM pulpo.get_available_time_slots($1, $2, $3, NULL)
            WHERE available = true
            LIMIT 20
        """, workspace_id, check_date, service['id'])

        time_slots = [row['time_slot'][:5] for row in slots]  # HH:MM format

        return {
            "success": True,
            "available": len(time_slots) > 0,
            "time_slots": time_slots,
            "service_info": service_info,
            "date": date_str
        }

    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        return {
            "success": False,
            "error": str(e),
            "available": False
        }
    finally:
        await conn.close()


async def get_service_packages(workspace_id: str) -> Dict[str, Any]:
    """
    Tool: Obtiene paquetes/combos disponibles

    Returns:
        {
            "success": true,
            "packages": [
                {
                    "id": "uuid",
                    "name": "Paquete Look Completo",
                    "services": ["Corte", "Coloración"],
                    "package_price": 7650,
                    "regular_price": 9000,
                    "savings": 1350
                }
            ]
        }
    """
    conn = await get_db_connection(workspace_id)

    try:
        rows = await conn.fetch("""
            SELECT
                id::text, name, description,
                service_type_ids, package_price, regular_price,
                currency, total_duration_minutes
            FROM pulpo.service_packages
            WHERE workspace_id = $1 AND is_active = true
            ORDER BY package_price
        """, workspace_id)

        packages = []
        for row in rows:
            service_ids = json.loads(row['service_type_ids'])

            # Get service names
            service_names = await conn.fetch("""
                SELECT name FROM pulpo.service_types
                WHERE id = ANY($1::uuid[])
            """, service_ids)

            packages.append({
                "id": row['id'],
                "name": row['name'],
                "description": row['description'],
                "services": [s['name'] for s in service_names],
                "package_price": float(row['package_price']),
                "regular_price": float(row['regular_price']) if row['regular_price'] else None,
                "savings": float(row['regular_price'] - row['package_price']) if row['regular_price'] else 0,
                "currency": row['currency'],
                "duration_minutes": row['total_duration_minutes']
            })

        return {
            "success": True,
            "packages": packages,
            "count": len(packages)
        }

    except Exception as e:
        logger.error(f"Error getting packages: {e}")
        return {
            "success": False,
            "error": str(e),
            "packages": []
        }
    finally:
        await conn.close()


async def get_active_promotions(workspace_id: str, check_date: Optional[str] = None) -> Dict[str, Any]:
    """
    Tool: Obtiene promociones activas

    Args:
        workspace_id: ID del workspace
        check_date: Fecha a verificar (YYYY-MM-DD), default hoy

    Returns:
        {
            "success": true,
            "promotions": [
                {
                    "id": "uuid",
                    "name": "20% OFF Martes",
                    "description": "...",
                    "discount_type": "percentage",
                    "discount_value": 20
                }
            ]
        }
    """
    conn = await get_db_connection(workspace_id)

    try:
        if not check_date:
            check_date = datetime.now().date().isoformat()

        check_date_obj = datetime.strptime(check_date, "%Y-%m-%d").date()
        day_of_week = check_date_obj.weekday() + 1  # Monday=1
        if day_of_week == 7:
            day_of_week = 0  # Sunday=0

        rows = await conn.fetch("""
            SELECT
                id::text, name, description,
                discount_type, discount_value,
                applies_to, valid_from, valid_until,
                valid_days_of_week
            FROM pulpo.promotions
            WHERE workspace_id = $1
              AND is_active = true
              AND valid_from <= $2
              AND valid_until >= $2
              AND (
                max_uses IS NULL OR current_uses < max_uses
              )
        """, workspace_id, check_date_obj)

        promotions = []
        for row in rows:
            valid_days = json.loads(row['valid_days_of_week'])

            # Check if applies to this day of week
            if day_of_week not in valid_days:
                continue

            promotions.append({
                "id": row['id'],
                "name": row['name'],
                "description": row['description'],
                "discount_type": row['discount_type'],
                "discount_value": float(row['discount_value']) if row['discount_value'] else 0,
                "applies_to": row['applies_to'],
                "valid_from": row['valid_from'].isoformat(),
                "valid_until": row['valid_until'].isoformat()
            })

        return {
            "success": True,
            "promotions": promotions,
            "count": len(promotions)
        }

    except Exception as e:
        logger.error(f"Error getting promotions: {e}")
        return {
            "success": False,
            "error": str(e),
            "promotions": []
        }
    finally:
        await conn.close()


async def get_business_hours(workspace_id: str) -> Dict[str, Any]:
    """
    Tool: Obtiene horarios del negocio

    Returns:
        {
            "success": true,
            "hours": {
                "monday": [{"open": "09:00", "close": "13:00"}, ...],
                "tuesday": [...],
                ...
            }
        }
    """
    conn = await get_db_connection(workspace_id)

    try:
        rows = await conn.fetch("""
            SELECT day_of_week, is_open, time_blocks
            FROM pulpo.business_hours
            WHERE workspace_id = $1
            ORDER BY day_of_week
        """, workspace_id)

        day_names = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
        hours = {}

        for row in rows:
            day_name = day_names[row['day_of_week']]

            if not row['is_open']:
                hours[day_name] = {"open": False}
            else:
                blocks = json.loads(row['time_blocks'])
                hours[day_name] = {
                    "open": True,
                    "blocks": blocks
                }

        return {
            "success": True,
            "hours": hours
        }

    except Exception as e:
        logger.error(f"Error getting business hours: {e}")
        return {
            "success": False,
            "error": str(e),
            "hours": {}
        }
    finally:
        await conn.close()


# =========================
# TOOL REGISTRY - Para orchestrator
# =========================

SERVICIOS_TOOLS = {
    "get_available_services": {
        "function": get_available_services,
        "description": "Obtiene lista de servicios disponibles (corte, coloración, etc.) con precios y duración",
        "parameters": {
            "workspace_id": {"type": "string", "required": True},
            "category": {"type": "string", "required": False, "description": "Filtrar por categoría (hair, nails, spa)"}
        }
    },
    "check_service_availability": {
        "function": check_service_availability,
        "description": "Verifica si hay disponibilidad para un servicio en fecha/hora específica. Retorna slots disponibles si no se especifica hora",
        "parameters": {
            "workspace_id": {"type": "string", "required": True},
            "service_name": {"type": "string", "required": True, "description": "Nombre del servicio"},
            "date_str": {"type": "string", "required": True, "description": "Fecha en formato YYYY-MM-DD"},
            "time_str": {"type": "string", "required": False, "description": "Hora en formato HH:MM"}
        }
    },
    "get_service_packages": {
        "function": get_service_packages,
        "description": "Obtiene paquetes/combos de servicios con descuento",
        "parameters": {
            "workspace_id": {"type": "string", "required": True}
        }
    },
    "get_active_promotions": {
        "function": get_active_promotions,
        "description": "Obtiene promociones activas vigentes",
        "parameters": {
            "workspace_id": {"type": "string", "required": True},
            "check_date": {"type": "string", "required": False, "description": "Fecha a verificar (YYYY-MM-DD)"}
        }
    },
    "get_business_hours": {
        "function": get_business_hours,
        "description": "Obtiene horarios de atención del negocio por día de semana",
        "parameters": {
            "workspace_id": {"type": "string", "required": True}
        }
    }
}


async def execute_tool(tool_name: str, **kwargs) -> Dict[str, Any]:
    """
    Ejecuta un tool por nombre

    Args:
        tool_name: Nombre del tool
        **kwargs: Parámetros del tool

    Returns:
        Resultado del tool
    """
    if tool_name not in SERVICIOS_TOOLS:
        return {
            "success": False,
            "error": f"Tool '{tool_name}' no encontrado"
        }

    tool = SERVICIOS_TOOLS[tool_name]
    func = tool["function"]

    try:
        result = await func(**kwargs)
        return result
    except Exception as e:
        logger.error(f"Error executing tool {tool_name}: {e}")
        return {
            "success": False,
            "error": str(e)
        }
