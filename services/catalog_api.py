"""
Catalog API - REST API para gestión de catálogos de negocio
Endpoints para UI/dashboard externo
"""

from fastapi import FastAPI, HTTPException, Header, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr
from typing import Optional, List, Any
import asyncpg
import os
import logging
from datetime import datetime
import json

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI app
app = FastAPI(
    title="PulpoAI Catalog API",
    description="API REST para gestión de catálogos de negocio (staff, servicios, etc.)",
    version="1.0.0"
)

# CORS (ajustar origins según tu UI)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restringir en producción
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Database
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://pulpo:pulpo@localhost:5432/pulpo")
pool: Optional[asyncpg.Pool] = None

# =========================
# Pydantic Models
# =========================

# Staff
class StaffCreate(BaseModel):
    name: str
    email: EmailStr
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: bool = True
    google_calendar_id: Optional[str] = None
    skills: List[str] = []
    working_hours: dict = {}
    metadata: dict = {}

class StaffUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None
    google_calendar_id: Optional[str] = None
    skills: Optional[List[str]] = None
    working_hours: Optional[dict] = None
    metadata: Optional[dict] = None

class StaffResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    email: str
    phone: Optional[str]
    role: Optional[str]
    is_active: bool
    google_calendar_id: Optional[str]
    skills: List[str]
    working_hours: dict
    metadata: dict
    created_at: datetime
    updated_at: datetime

# Service Types
class ServiceTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price: float
    currency: str = "ARS"
    duration_minutes: int = 60
    is_active: bool = True
    requires_staff: bool = True
    metadata: dict = {}

class ServiceTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    category: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    duration_minutes: Optional[int] = None
    is_active: Optional[bool] = None
    requires_staff: Optional[bool] = None
    metadata: Optional[dict] = None

class ServiceTypeResponse(BaseModel):
    id: str
    workspace_id: str
    name: str
    description: Optional[str]
    category: Optional[str]
    price: float
    currency: str
    duration_minutes: int
    is_active: bool
    requires_staff: bool
    metadata: dict
    created_at: datetime
    updated_at: datetime

# Appointments (read-only)
class AppointmentResponse(BaseModel):
    id: str
    workspace_id: str
    conversation_id: str
    service_type_id: Optional[str]
    service_name: Optional[str]
    staff_id: Optional[str]
    staff_name: Optional[str]
    client_name: Optional[str]
    client_email: Optional[str]
    client_phone: Optional[str]
    scheduled_at: datetime
    duration_minutes: int
    status: str
    notes: Optional[str]
    google_event_id: Optional[str]
    created_at: datetime

# =========================
# Database Connection
# =========================

@app.on_event("startup")
async def startup():
    global pool
    pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    logger.info("Database pool created")

@app.on_event("shutdown")
async def shutdown():
    global pool
    if pool:
        await pool.close()
    logger.info("Database pool closed")

async def get_connection():
    """Get database connection from pool"""
    if not pool:
        raise HTTPException(status_code=500, detail="Database pool not initialized")
    return await pool.acquire()

async def release_connection(conn):
    """Release connection back to pool"""
    await pool.release(conn)

def validate_workspace_id(workspace_id: Optional[str]) -> str:
    """Validate workspace_id header"""
    if not workspace_id:
        raise HTTPException(status_code=400, detail="X-Workspace-Id header required")
    return workspace_id

# =========================
# Health Check
# =========================

@app.get("/health")
async def health():
    """Health check endpoint"""
    return {
        "status": "ok",
        "service": "catalog_api",
        "timestamp": datetime.utcnow().isoformat()
    }

# =========================
# STAFF ENDPOINTS
# =========================

@app.get("/api/staff", response_model=List[StaffResponse])
async def list_staff(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    is_active: Optional[bool] = Query(None),
    role: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List staff members

    Query params:
    - is_active: Filter by active status
    - role: Filter by role
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Build query
        query = """
            SELECT
                id::text, workspace_id::text, name, email, phone, role,
                is_active, google_calendar_id, skills, working_hours,
                metadata, created_at, updated_at
            FROM pulpo.staff
            WHERE workspace_id = $1
        """
        params = [workspace_id]
        param_count = 1

        if is_active is not None:
            param_count += 1
            query += f" AND is_active = ${param_count}"
            params.append(is_active)

        if role:
            param_count += 1
            query += f" AND role ILIKE ${param_count}"
            params.append(f"%{role}%")

        query += " ORDER BY name LIMIT $" + str(param_count + 1) + " OFFSET $" + str(param_count + 2)
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        result = []
        for row in rows:
            result.append({
                "id": row['id'],
                "workspace_id": row['workspace_id'],
                "name": row['name'],
                "email": row['email'],
                "phone": row['phone'],
                "role": row['role'],
                "is_active": row['is_active'],
                "google_calendar_id": row['google_calendar_id'],
                "skills": json.loads(row['skills']) if row['skills'] else [],
                "working_hours": json.loads(row['working_hours']) if row['working_hours'] else {},
                "metadata": json.loads(row['metadata']) if row['metadata'] else {},
                "created_at": row['created_at'],
                "updated_at": row['updated_at']
            })

        return result

    finally:
        await release_connection(conn)

@app.get("/api/staff/{staff_id}", response_model=StaffResponse)
async def get_staff(
    staff_id: str,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Get single staff member by ID"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        row = await conn.fetchrow("""
            SELECT
                id::text, workspace_id::text, name, email, phone, role,
                is_active, google_calendar_id, skills, working_hours,
                metadata, created_at, updated_at
            FROM pulpo.staff
            WHERE workspace_id = $1 AND id = $2
        """, workspace_id, staff_id)

        if not row:
            raise HTTPException(status_code=404, detail="Staff not found")

        return {
            "id": row['id'],
            "workspace_id": row['workspace_id'],
            "name": row['name'],
            "email": row['email'],
            "phone": row['phone'],
            "role": row['role'],
            "is_active": row['is_active'],
            "google_calendar_id": row['google_calendar_id'],
            "skills": json.loads(row['skills']) if row['skills'] else [],
            "working_hours": json.loads(row['working_hours']) if row['working_hours'] else {},
            "metadata": json.loads(row['metadata']) if row['metadata'] else {},
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }

    finally:
        await release_connection(conn)

@app.post("/api/staff", response_model=StaffResponse, status_code=201)
async def create_staff(
    staff: StaffCreate,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Create new staff member"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Check if email already exists
        existing = await conn.fetchrow("""
            SELECT id FROM pulpo.staff
            WHERE workspace_id = $1 AND email = $2
        """, workspace_id, staff.email)

        if existing:
            raise HTTPException(status_code=409, detail="Staff with this email already exists")

        # Insert
        row = await conn.fetchrow("""
            INSERT INTO pulpo.staff (
                workspace_id, name, email, phone, role,
                is_active, google_calendar_id, skills, working_hours, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING
                id::text, workspace_id::text, name, email, phone, role,
                is_active, google_calendar_id, skills, working_hours,
                metadata, created_at, updated_at
        """,
            workspace_id, staff.name, staff.email, staff.phone, staff.role,
            staff.is_active, staff.google_calendar_id,
            json.dumps(staff.skills), json.dumps(staff.working_hours),
            json.dumps(staff.metadata)
        )

        logger.info(f"Staff created: {row['id']} ({staff.name})")

        return {
            "id": row['id'],
            "workspace_id": row['workspace_id'],
            "name": row['name'],
            "email": row['email'],
            "phone": row['phone'],
            "role": row['role'],
            "is_active": row['is_active'],
            "google_calendar_id": row['google_calendar_id'],
            "skills": json.loads(row['skills']) if row['skills'] else [],
            "working_hours": json.loads(row['working_hours']) if row['working_hours'] else {},
            "metadata": json.loads(row['metadata']) if row['metadata'] else {},
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }

    finally:
        await release_connection(conn)

@app.put("/api/staff/{staff_id}", response_model=StaffResponse)
async def update_staff(
    staff_id: str,
    staff: StaffUpdate,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Update staff member"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Check exists
        existing = await conn.fetchrow("""
            SELECT id FROM pulpo.staff
            WHERE workspace_id = $1 AND id = $2
        """, workspace_id, staff_id)

        if not existing:
            raise HTTPException(status_code=404, detail="Staff not found")

        # Build update query dynamically
        update_fields = []
        params = [workspace_id, staff_id]
        param_count = 2

        if staff.name is not None:
            param_count += 1
            update_fields.append(f"name = ${param_count}")
            params.append(staff.name)

        if staff.email is not None:
            param_count += 1
            update_fields.append(f"email = ${param_count}")
            params.append(staff.email)

        if staff.phone is not None:
            param_count += 1
            update_fields.append(f"phone = ${param_count}")
            params.append(staff.phone)

        if staff.role is not None:
            param_count += 1
            update_fields.append(f"role = ${param_count}")
            params.append(staff.role)

        if staff.is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(staff.is_active)

        if staff.google_calendar_id is not None:
            param_count += 1
            update_fields.append(f"google_calendar_id = ${param_count}")
            params.append(staff.google_calendar_id)

        if staff.skills is not None:
            param_count += 1
            update_fields.append(f"skills = ${param_count}")
            params.append(json.dumps(staff.skills))

        if staff.working_hours is not None:
            param_count += 1
            update_fields.append(f"working_hours = ${param_count}")
            params.append(json.dumps(staff.working_hours))

        if staff.metadata is not None:
            param_count += 1
            update_fields.append(f"metadata = ${param_count}")
            params.append(json.dumps(staff.metadata))

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_fields.append("updated_at = now()")

        query = f"""
            UPDATE pulpo.staff
            SET {', '.join(update_fields)}
            WHERE workspace_id = $1 AND id = $2
            RETURNING
                id::text, workspace_id::text, name, email, phone, role,
                is_active, google_calendar_id, skills, working_hours,
                metadata, created_at, updated_at
        """

        row = await conn.fetchrow(query, *params)

        logger.info(f"Staff updated: {staff_id}")

        return {
            "id": row['id'],
            "workspace_id": row['workspace_id'],
            "name": row['name'],
            "email": row['email'],
            "phone": row['phone'],
            "role": row['role'],
            "is_active": row['is_active'],
            "google_calendar_id": row['google_calendar_id'],
            "skills": json.loads(row['skills']) if row['skills'] else [],
            "working_hours": json.loads(row['working_hours']) if row['working_hours'] else {},
            "metadata": json.loads(row['metadata']) if row['metadata'] else {},
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }

    finally:
        await release_connection(conn)

@app.delete("/api/staff/{staff_id}", status_code=204)
async def delete_staff(
    staff_id: str,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Delete staff member (soft delete - sets is_active=false)"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Soft delete (set is_active = false)
        result = await conn.execute("""
            UPDATE pulpo.staff
            SET is_active = false, updated_at = now()
            WHERE workspace_id = $1 AND id = $2
        """, workspace_id, staff_id)

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Staff not found")

        logger.info(f"Staff deleted (soft): {staff_id}")

    finally:
        await release_connection(conn)

# =========================
# SERVICE TYPES ENDPOINTS
# =========================

@app.get("/api/service-types", response_model=List[ServiceTypeResponse])
async def list_service_types(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    is_active: Optional[bool] = Query(None),
    category: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List service types

    Query params:
    - is_active: Filter by active status
    - category: Filter by category
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        query = """
            SELECT
                id::text, workspace_id::text, name, description, category,
                price, currency, duration_minutes, is_active, requires_staff,
                metadata, created_at, updated_at
            FROM pulpo.service_types
            WHERE workspace_id = $1
        """
        params = [workspace_id]
        param_count = 1

        if is_active is not None:
            param_count += 1
            query += f" AND is_active = ${param_count}"
            params.append(is_active)

        if category:
            param_count += 1
            query += f" AND category ILIKE ${param_count}"
            params.append(f"%{category}%")

        query += " ORDER BY name LIMIT $" + str(param_count + 1) + " OFFSET $" + str(param_count + 2)
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        result = []
        for row in rows:
            result.append({
                "id": row['id'],
                "workspace_id": row['workspace_id'],
                "name": row['name'],
                "description": row['description'],
                "category": row['category'],
                "price": float(row['price']) if row['price'] else 0,
                "currency": row['currency'],
                "duration_minutes": row['duration_minutes'],
                "is_active": row['is_active'],
                "requires_staff": row['requires_staff'],
                "metadata": json.loads(row['metadata']) if row['metadata'] else {},
                "created_at": row['created_at'],
                "updated_at": row['updated_at']
            })

        return result

    finally:
        await release_connection(conn)

@app.get("/api/service-types/{service_type_id}", response_model=ServiceTypeResponse)
async def get_service_type(
    service_type_id: str,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Get single service type by ID"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        row = await conn.fetchrow("""
            SELECT
                id::text, workspace_id::text, name, description, category,
                price, currency, duration_minutes, is_active, requires_staff,
                metadata, created_at, updated_at
            FROM pulpo.service_types
            WHERE workspace_id = $1 AND id = $2
        """, workspace_id, service_type_id)

        if not row:
            raise HTTPException(status_code=404, detail="Service type not found")

        return {
            "id": row['id'],
            "workspace_id": row['workspace_id'],
            "name": row['name'],
            "description": row['description'],
            "category": row['category'],
            "price": float(row['price']) if row['price'] else 0,
            "currency": row['currency'],
            "duration_minutes": row['duration_minutes'],
            "is_active": row['is_active'],
            "requires_staff": row['requires_staff'],
            "metadata": json.loads(row['metadata']) if row['metadata'] else {},
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }

    finally:
        await release_connection(conn)

@app.post("/api/service-types", response_model=ServiceTypeResponse, status_code=201)
async def create_service_type(
    service_type: ServiceTypeCreate,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Create new service type"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Check if name already exists
        existing = await conn.fetchrow("""
            SELECT id FROM pulpo.service_types
            WHERE workspace_id = $1 AND name = $2
        """, workspace_id, service_type.name)

        if existing:
            raise HTTPException(status_code=409, detail="Service type with this name already exists")

        # Insert
        row = await conn.fetchrow("""
            INSERT INTO pulpo.service_types (
                workspace_id, name, description, category,
                price, currency, duration_minutes, is_active, requires_staff, metadata
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10)
            RETURNING
                id::text, workspace_id::text, name, description, category,
                price, currency, duration_minutes, is_active, requires_staff,
                metadata, created_at, updated_at
        """,
            workspace_id, service_type.name, service_type.description, service_type.category,
            service_type.price, service_type.currency, service_type.duration_minutes,
            service_type.is_active, service_type.requires_staff, json.dumps(service_type.metadata)
        )

        logger.info(f"Service type created: {row['id']} ({service_type.name})")

        return {
            "id": row['id'],
            "workspace_id": row['workspace_id'],
            "name": row['name'],
            "description": row['description'],
            "category": row['category'],
            "price": float(row['price']) if row['price'] else 0,
            "currency": row['currency'],
            "duration_minutes": row['duration_minutes'],
            "is_active": row['is_active'],
            "requires_staff": row['requires_staff'],
            "metadata": json.loads(row['metadata']) if row['metadata'] else {},
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }

    finally:
        await release_connection(conn)

@app.put("/api/service-types/{service_type_id}", response_model=ServiceTypeResponse)
async def update_service_type(
    service_type_id: str,
    service_type: ServiceTypeUpdate,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Update service type"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        # Check exists
        existing = await conn.fetchrow("""
            SELECT id FROM pulpo.service_types
            WHERE workspace_id = $1 AND id = $2
        """, workspace_id, service_type_id)

        if not existing:
            raise HTTPException(status_code=404, detail="Service type not found")

        # Build update query
        update_fields = []
        params = [workspace_id, service_type_id]
        param_count = 2

        if service_type.name is not None:
            param_count += 1
            update_fields.append(f"name = ${param_count}")
            params.append(service_type.name)

        if service_type.description is not None:
            param_count += 1
            update_fields.append(f"description = ${param_count}")
            params.append(service_type.description)

        if service_type.category is not None:
            param_count += 1
            update_fields.append(f"category = ${param_count}")
            params.append(service_type.category)

        if service_type.price is not None:
            param_count += 1
            update_fields.append(f"price = ${param_count}")
            params.append(service_type.price)

        if service_type.currency is not None:
            param_count += 1
            update_fields.append(f"currency = ${param_count}")
            params.append(service_type.currency)

        if service_type.duration_minutes is not None:
            param_count += 1
            update_fields.append(f"duration_minutes = ${param_count}")
            params.append(service_type.duration_minutes)

        if service_type.is_active is not None:
            param_count += 1
            update_fields.append(f"is_active = ${param_count}")
            params.append(service_type.is_active)

        if service_type.requires_staff is not None:
            param_count += 1
            update_fields.append(f"requires_staff = ${param_count}")
            params.append(service_type.requires_staff)

        if service_type.metadata is not None:
            param_count += 1
            update_fields.append(f"metadata = ${param_count}")
            params.append(json.dumps(service_type.metadata))

        if not update_fields:
            raise HTTPException(status_code=400, detail="No fields to update")

        update_fields.append("updated_at = now()")

        query = f"""
            UPDATE pulpo.service_types
            SET {', '.join(update_fields)}
            WHERE workspace_id = $1 AND id = $2
            RETURNING
                id::text, workspace_id::text, name, description, category,
                price, currency, duration_minutes, is_active, requires_staff,
                metadata, created_at, updated_at
        """

        row = await conn.fetchrow(query, *params)

        logger.info(f"Service type updated: {service_type_id}")

        return {
            "id": row['id'],
            "workspace_id": row['workspace_id'],
            "name": row['name'],
            "description": row['description'],
            "category": row['category'],
            "price": float(row['price']) if row['price'] else 0,
            "currency": row['currency'],
            "duration_minutes": row['duration_minutes'],
            "is_active": row['is_active'],
            "requires_staff": row['requires_staff'],
            "metadata": json.loads(row['metadata']) if row['metadata'] else {},
            "created_at": row['created_at'],
            "updated_at": row['updated_at']
        }

    finally:
        await release_connection(conn)

@app.delete("/api/service-types/{service_type_id}", status_code=204)
async def delete_service_type(
    service_type_id: str,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Delete service type (soft delete - sets is_active=false)"""
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        result = await conn.execute("""
            UPDATE pulpo.service_types
            SET is_active = false, updated_at = now()
            WHERE workspace_id = $1 AND id = $2
        """, workspace_id, service_type_id)

        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail="Service type not found")

        logger.info(f"Service type deleted (soft): {service_type_id}")

    finally:
        await release_connection(conn)

# =========================
# APPOINTMENTS ENDPOINTS (Read-only)
# =========================

@app.get("/api/appointments", response_model=List[AppointmentResponse])
async def list_appointments(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    status: Optional[str] = Query(None),
    staff_id: Optional[str] = Query(None),
    from_date: Optional[str] = Query(None),
    to_date: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0)
):
    """
    List appointments

    Query params:
    - status: Filter by status (scheduled, confirmed, completed, cancelled)
    - staff_id: Filter by staff ID
    - from_date: Filter from date (ISO format)
    - to_date: Filter to date (ISO format)
    - limit: Max results (default 100)
    - offset: Pagination offset
    """
    workspace_id = validate_workspace_id(x_workspace_id)
    conn = await get_connection()

    try:
        await conn.execute("SELECT set_config('app.workspace_id', $1, false)", workspace_id)

        query = """
            SELECT
                a.id::text, a.workspace_id::text, a.conversation_id::text,
                a.service_type_id::text, st.name as service_name,
                a.staff_id::text, s.name as staff_name,
                a.client_name, a.client_email, a.client_phone,
                a.scheduled_at, a.duration_minutes, a.status, a.notes,
                a.google_event_id, a.created_at
            FROM pulpo.appointments a
            LEFT JOIN pulpo.service_types st ON st.id = a.service_type_id
            LEFT JOIN pulpo.staff s ON s.id = a.staff_id
            WHERE a.workspace_id = $1
        """
        params = [workspace_id]
        param_count = 1

        if status:
            param_count += 1
            query += f" AND a.status = ${param_count}"
            params.append(status)

        if staff_id:
            param_count += 1
            query += f" AND a.staff_id = ${param_count}"
            params.append(staff_id)

        if from_date:
            param_count += 1
            query += f" AND a.scheduled_at >= ${param_count}"
            params.append(from_date)

        if to_date:
            param_count += 1
            query += f" AND a.scheduled_at <= ${param_count}"
            params.append(to_date)

        query += " ORDER BY a.scheduled_at DESC LIMIT $" + str(param_count + 1) + " OFFSET $" + str(param_count + 2)
        params.extend([limit, offset])

        rows = await conn.fetch(query, *params)

        result = []
        for row in rows:
            result.append({
                "id": row['id'],
                "workspace_id": row['workspace_id'],
                "conversation_id": row['conversation_id'],
                "service_type_id": row['service_type_id'],
                "service_name": row['service_name'],
                "staff_id": row['staff_id'],
                "staff_name": row['staff_name'],
                "client_name": row['client_name'],
                "client_email": row['client_email'],
                "client_phone": row['client_phone'],
                "scheduled_at": row['scheduled_at'],
                "duration_minutes": row['duration_minutes'] or 60,
                "status": row['status'],
                "notes": row['notes'],
                "google_event_id": row['google_event_id'],
                "created_at": row['created_at']
            })

        return result

    finally:
        await release_connection(conn)

# =========================
# Run Server
# =========================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8008)
