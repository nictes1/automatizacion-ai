"""
MCP Mock - Servidor mock para simular MCP
Simula las funciones MCP para testing local
"""

from fastapi import FastAPI
from pydantic import BaseModel
from typing import Dict, Any, List

app = FastAPI(title="MCP Mock", version="1.0.0")

class Payload(BaseModel):
    workspace_id: str | None = None
    service_type: str | None = None
    preferred_date: str | None = None
    preferred_time: str | None = None
    client_name: str | None = None
    client_email: str | None = None
    client_phone: str | None = None
    staff_preference: str | None = None
    notes: str | None = None
    date: str | None = None
    time: str | None = None
    appointment_id: str | None = None
    new_date: str | None = None
    new_time: str | None = None

@app.post("/api/get_services")
def get_services(_: Payload):
    return {"services": [
        {"name": "Corte", "price_min": 7000, "price_max": 7000},
        {"name": "Coloración", "price_min": 12000, "price_max": 18000},
        {"name": "Barba", "price_min": 5000, "price_max": 5000},
    ]}

@app.post("/api/get_prices")
def get_prices(_: Payload):
    return {"prices": [
        {"name": "Corte", "price_min": 7000, "price_max": 7000},
        {"name": "Coloración", "price_min": 12000, "price_max": 18000},
    ]}

@app.post("/api/get_business_hours")
def get_business_hours(_: Payload):
    return {"open": "09:00", "close": "19:00", "days": "Lun-Sáb"}

@app.post("/api/check_availability")
def check_availability(_: Payload):
    return {"available": True, "available_slots": ["10:00", "14:00", "17:00"]}

@app.post("/api/book_appointment")
def book_appointment(p: Payload):
    return {"booking_id": "ABC123", "status": "confirmed", "service": p.service_type}

@app.post("/api/cancel_appointment")
def cancel_appointment(_: Payload):
    return {"cancelled": True}

@app.post("/api/modify_appointment")
def modify_appointment(_: Payload):
    return {"modified": True}
