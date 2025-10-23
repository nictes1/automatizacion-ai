"""
Telemetry Logger para Fase 1 - Quick Wins
Logging estructurado de intent_detected y tools_called
"""

import logging
import json
import time
from typing import Dict, Any, List, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class TelemetryLogger:
    """
    Logger estructurado para telemetría del sistema
    """
    
    def __init__(self):
        self.telemetry_logger = logging.getLogger("telemetry")
        
        # Configurar handler específico para telemetría si no existe
        if not self.telemetry_logger.handlers:
            handler = logging.StreamHandler()
            formatter = logging.Formatter('%(asctime)s - TELEMETRY - %(message)s')
            handler.setFormatter(formatter)
            self.telemetry_logger.addHandler(handler)
            self.telemetry_logger.setLevel(logging.INFO)
    
    def log_intent_detection(self, 
                           conversation_id: str,
                           user_input: str,
                           intent: str,
                           confidence: float,
                           method: str,
                           processing_time_ms: int,
                           workspace_id: Optional[str] = None):
        """
        Log de detección de intent
        """
        telemetry_data = {
            "event": "intent_detected",
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "user_input": user_input[:100],  # Limitar tamaño
            "intent": intent,
            "confidence": round(confidence, 3),
            "method": method,  # "regex", "contextual", "llm"
            "processing_time_ms": processing_time_ms
        }
        
        self.telemetry_logger.info(json.dumps(telemetry_data, ensure_ascii=False))
    
    def log_tools_called(self,
                        conversation_id: str,
                        tools: List[Dict[str, Any]],
                        intent: str,
                        method: str,  # "deterministic", "planner", "fallback"
                        success_count: int,
                        total_count: int,
                        processing_time_ms: int,
                        workspace_id: Optional[str] = None):
        """
        Log de tools ejecutados
        """
        telemetry_data = {
            "event": "tools_called",
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "tools": [
                {
                    "name": tool.get("tool", tool.get("name", "unknown")),
                    "args": tool.get("args", {}),
                    "success": tool.get("success", True)
                } for tool in tools
            ],
            "intent": intent,
            "method": method,
            "success_count": success_count,
            "total_count": total_count,
            "success_rate": round(success_count / total_count * 100, 1) if total_count > 0 else 0,
            "processing_time_ms": processing_time_ms
        }
        
        self.telemetry_logger.info(json.dumps(telemetry_data, ensure_ascii=False))
    
    def log_deterministic_response(self,
                                 conversation_id: str,
                                 intent: str,
                                 response_type: str,  # "greeting", "services", "hours", "booking"
                                 template_used: str,
                                 processing_time_ms: int,
                                 workspace_id: Optional[str] = None):
        """
        Log de respuesta determinística
        """
        telemetry_data = {
            "event": "deterministic_response",
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "intent": intent,
            "response_type": response_type,
            "template_used": template_used,
            "processing_time_ms": processing_time_ms,
            "llm_bypassed": True
        }
        
        self.telemetry_logger.info(json.dumps(telemetry_data, ensure_ascii=False))
    
    def log_planner_decision(self,
                           conversation_id: str,
                           user_input: str,
                           tools_planned: List[str],
                           confidence: float,
                           processing_time_ms: int,
                           workspace_id: Optional[str] = None):
        """
        Log de decisión del planner
        """
        telemetry_data = {
            "event": "planner_decision",
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "user_input": user_input[:100],
            "tools_planned": tools_planned,
            "tools_count": len(tools_planned),
            "confidence": round(confidence, 3),
            "processing_time_ms": processing_time_ms
        }
        
        self.telemetry_logger.info(json.dumps(telemetry_data, ensure_ascii=False))
    
    def log_conversation_turn(self,
                            conversation_id: str,
                            user_input: str,
                            assistant_response: str,
                            intent: str,
                            method: str,
                            total_processing_time_ms: int,
                            workspace_id: Optional[str] = None):
        """
        Log de turno completo de conversación
        """
        telemetry_data = {
            "event": "conversation_turn",
            "timestamp": datetime.now().isoformat(),
            "conversation_id": conversation_id,
            "workspace_id": workspace_id,
            "user_input": user_input[:100],
            "assistant_response": assistant_response[:200],
            "intent": intent,
            "method": method,  # "deterministic", "planner", "fallback"
            "total_processing_time_ms": total_processing_time_ms,
            "response_length": len(assistant_response)
        }
        
        self.telemetry_logger.info(json.dumps(telemetry_data, ensure_ascii=False))

# Instancia global
telemetry_logger = TelemetryLogger()
