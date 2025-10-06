"""
FastAPI application para el Actions Service
Incluye endpoints para appointments (agendamiento de turnos)
"""

from fastapi import FastAPI, HTTPException, Header
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Dict, List, Any
from datetime import date, time
from uuid import UUID
import logging
import asyncpg
import os

from services.appointments_service import appointments_service

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="PulpoAI Actions Service",
    description="Servicio de acciones y herramientas para el agente conversacional",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# =========================
# Modelos Pydantic
# =========================

class ServiceTypeResponse(BaseModel):
    id: str
    name: str
    description: Optional[str]
    duration_minutes: int
    price: float
    currency: str

class StaffMemberResponse(BaseModel):
    id: str
    name: str
    email: str
    phone: Optional[str]
    photo_url: Optional[str]
    specialties: List[str]

class CreateAppointmentRequest(BaseModel):
    conversation_id: Optional[str] = None
    service_type_name: str
    client_name: str
    client_email: str
    client_phone: Optional[str] = None
    appointment_date: str  # YYYY-MM-DD
    appointment_time: str  # HH:MM
    staff_id: Optional[str] = None
    notes: Optional[str] = None

class AppointmentResponse(BaseModel):
    appointment_id: str
    staff_name: str
    staff_email: str
    service_name: str
    date: str
    time: str
    duration_minutes: int
    google_event_id: Optional[str]
    status: str

class CheckAvailabilityRequest(BaseModel):
    staff_id: str
    appointment_date: str  # YYYY-MM-DD
    appointment_time: str  # HH:MM
    duration_minutes: int

class CancelAppointmentRequest(BaseModel):
    appointment_id: str
    cancellation_reason: Optional[str] = None

class ExecuteActionRequest(BaseModel):
    """Request para ejecutar una acción genérica desde el orchestrator"""
    conversation_id: str
    action_name: str
    payload: Dict[str, Any]
    idempotency_key: str

class ExecuteActionResponse(BaseModel):
    """Response de ejecución de acción"""
    status: str  # success, failed, error
    summary: str
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# =========================
# Endpoints
# =========================

@app.get("/health")
async def health():
    return {"status": "healthy", "service": "actions"}

# --- Service Types ---

@app.get("/actions/service-types", response_model=List[ServiceTypeResponse])
async def get_service_types(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Obtiene los tipos de servicio disponibles para un workspace"""
    try:
        workspace_id = UUID(x_workspace_id)
        services = await appointments_service.get_service_types(workspace_id)

        return [
            ServiceTypeResponse(
                id=str(s['id']),
                name=s['name'],
                description=s['description'],
                duration_minutes=s['duration_minutes'],
                price=float(s['price']),
                currency=s['currency']
            )
            for s in services
        ]

    except Exception as e:
        logger.error(f"Error getting service types: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Staff Members ---

@app.get("/actions/staff", response_model=List[StaffMemberResponse])
async def get_staff_members(
    x_workspace_id: str = Header(..., alias="X-Workspace-Id"),
    service_type: Optional[str] = None
):
    """Obtiene los empleados disponibles, opcionalmente filtrado por tipo de servicio"""
    try:
        workspace_id = UUID(x_workspace_id)
        staff = await appointments_service.get_staff_members(workspace_id, service_type)

        return [
            StaffMemberResponse(
                id=str(s['id']),
                name=s['name'],
                email=s['email'],
                phone=s.get('phone'),
                photo_url=s.get('photo_url'),
                specialties=s['specialties']
            )
            for s in staff
        ]

    except Exception as e:
        logger.error(f"Error getting staff: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# --- Availability ---

@app.post("/actions/check-availability")
async def check_availability(
    request: CheckAvailabilityRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Verifica si un staff member está disponible en un horario específico"""
    try:
        workspace_id = UUID(x_workspace_id)
        staff_id = UUID(request.staff_id)

        # Parsear fecha y hora
        appt_date = date.fromisoformat(request.appointment_date)
        appt_time = time.fromisoformat(request.appointment_time)

        is_available = await appointments_service.check_availability(
            workspace_id=workspace_id,
            staff_id=staff_id,
            appointment_date=appt_date,
            appointment_time=appt_time,
            duration_minutes=request.duration_minutes
        )

        return {
            "available": is_available,
            "staff_id": request.staff_id,
            "date": request.appointment_date,
            "time": request.appointment_time
        }

    except Exception as e:
        logger.error(f"Error checking availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# Tools Endpoint (Orchestrator Integration)
# =========================

@app.post("/tools/execute_action", response_model=ExecuteActionResponse)
async def execute_action(
    request: ExecuteActionRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """
    Endpoint genérico para ejecutar acciones desde el orchestrator.
    Mapea action_name a la lógica correspondiente.
    """
    try:
        workspace_id = UUID(x_workspace_id)
        action_name = request.action_name
        payload = request.payload

        logger.info(f"Executing action: {action_name} for conversation {request.conversation_id}")

        # Mapeo de acciones
        if action_name == "schedule_appointment" or action_name == "agendar_cita":
            # Extraer datos del payload
            service_type_name = payload.get("service_type_name") or payload.get("servicio")
            client_name = payload.get("client_name") or payload.get("nombre_cliente")
            client_email = payload.get("client_email") or payload.get("email_cliente")
            client_phone = payload.get("client_phone") or payload.get("telefono_cliente")
            appointment_date_str = payload.get("appointment_date") or payload.get("fecha")
            appointment_time_str = payload.get("appointment_time") or payload.get("hora")
            notes = payload.get("notes") or payload.get("notas")

            # Validar datos requeridos
            if not all([service_type_name, client_name, client_email, appointment_date_str, appointment_time_str]):
                return ExecuteActionResponse(
                    status="failed",
                    summary="Faltan datos requeridos para agendar el turno",
                    error="Missing required fields: service_type_name, client_name, client_email, appointment_date, appointment_time"
                )

            # Parsear fecha y hora
            appt_date = date.fromisoformat(appointment_date_str)
            appt_time = time.fromisoformat(appointment_time_str)

            # Crear el turno
            # Parsear conversation_id (puede ser UUID string, None, o string no-UUID para tests)
            conv_id = None
            if request.conversation_id:
                try:
                    conv_id = UUID(request.conversation_id)
                except ValueError:
                    # Si no es UUID válido, dejarlo como None
                    logger.warning(f"conversation_id '{request.conversation_id}' is not a valid UUID, setting to None")

            result = await appointments_service.create_appointment(
                workspace_id=workspace_id,
                conversation_id=conv_id,
                service_type_name=service_type_name,
                client_name=client_name,
                client_email=client_email,
                client_phone=client_phone,
                appointment_date=appt_date,
                appointment_time=appt_time,
                staff_id=None,  # Asignación automática
                notes=notes
            )

            # Formatear respuesta de éxito
            summary = f"Turno confirmado para {result['date']} a las {result['time']} con {result['staff_name']}"

            return ExecuteActionResponse(
                status="success",
                summary=summary,
                data=result
            )

        else:
            # Acción no reconocida
            return ExecuteActionResponse(
                status="failed",
                summary=f"Acción '{action_name}' no reconocida",
                error=f"Unknown action: {action_name}"
            )

    except ValueError as e:
        logger.error(f"Validation error in execute_action: {e}")
        return ExecuteActionResponse(
            status="failed",
            summary=str(e),
            error=str(e)
        )
    except Exception as e:
        import traceback
        logger.error(f"Error in execute_action: {e}")
        logger.error(traceback.format_exc())
        return ExecuteActionResponse(
            status="error",
            summary="Error interno al ejecutar la acción",
            error=str(e)
        )

# --- Create Appointment ---

@app.post("/actions/create-appointment", response_model=AppointmentResponse)
async def create_appointment(
    request: CreateAppointmentRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """
    Crea un nuevo turno
    - Verifica disponibilidad
    - Asigna staff automáticamente si no se especifica
    - Crea evento en Google Calendar del negocio
    - Envía invitaciones a empleado y cliente
    """
    try:
        workspace_id = UUID(x_workspace_id)
        conversation_id = UUID(request.conversation_id) if request.conversation_id else None
        staff_id = UUID(request.staff_id) if request.staff_id else None

        # Parsear fecha y hora
        appt_date = date.fromisoformat(request.appointment_date)
        appt_time = time.fromisoformat(request.appointment_time)

        result = await appointments_service.create_appointment(
            workspace_id=workspace_id,
            conversation_id=conversation_id,
            service_type_name=request.service_type_name,
            client_name=request.client_name,
            client_email=request.client_email,
            client_phone=request.client_phone,
            appointment_date=appt_date,
            appointment_time=appt_time,
            staff_id=staff_id,
            notes=request.notes
        )

        return AppointmentResponse(**result)

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        logger.error(f"Error creating appointment: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

# --- Cancel Appointment ---

@app.post("/actions/cancel-appointment")
async def cancel_appointment(
    request: CancelAppointmentRequest,
    x_workspace_id: str = Header(..., alias="X-Workspace-Id")
):
    """Cancela un turno existente"""
    try:
        workspace_id = UUID(x_workspace_id)
        appointment_id = UUID(request.appointment_id)

        success = await appointments_service.cancel_appointment(
            workspace_id=workspace_id,
            appointment_id=appointment_id,
            cancellation_reason=request.cancellation_reason
        )

        if not success:
            raise HTTPException(status_code=404, detail="Appointment not found")

        return {
            "success": True,
            "appointment_id": request.appointment_id,
            "message": "Appointment cancelled successfully"
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling appointment: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# =========================
# Startup/Shutdown
# =========================

@app.on_event("startup")
async def startup():
    logger.info("Actions Service starting up...")

    # Inicializar pool de DB
    db_pool = await asyncpg.create_pool(
        host=os.getenv("DB_HOST", "postgres"),
        port=int(os.getenv("DB_PORT", 5432)),
        user=os.getenv("DB_USER", "pulpo"),
        password=os.getenv("DB_PASSWORD", "pulpodev2024"),
        database=os.getenv("DB_NAME", "pulpo"),
        min_size=2,
        max_size=10
    )

    # Inicializar appointments service
    await appointments_service.initialize_db(db_pool)

    logger.info("✅ Actions Service initialized")

@app.on_event("shutdown")
async def shutdown():
    logger.info("Actions Service shutting down...")
    if appointments_service.db_pool:
        await appointments_service.db_pool.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
