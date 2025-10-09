"""
State Reducer - Aplica observaciones de tools al estado conversacional

Responsabilidades:
- Procesar ToolObservations del ToolBroker
- Actualizar slots con resultados de tools
- Mantener historial de observaciones (last_k_turns)
- Generar ConversationStatePatch para aplicar cambios
- Invalidar cache cuando hay cambios relevantes
- Comprimir observaciones para contexto LLM
"""

from typing import Dict, Any, List, Optional, Tuple
from pydantic import BaseModel, Field
from enum import Enum
from dataclasses import dataclass
import time
import json
import logging
from collections import deque

from services.tool_broker import ToolObservation, ToolStatus
from services.canonical_slots import redact_pii, CANONICAL_SLOTS

logger = logging.getLogger(__name__)


# ==========================================
# MODELOS Y ENUMS
# ==========================================

class StateChangeType(str, Enum):
    """Tipos de cambios en el estado conversacional"""
    SLOT_UPDATE = "slot_update"          # Nuevo valor en slot
    TOOL_SUCCESS = "tool_success"        # Tool ejecutado exitosamente
    TOOL_FAILURE = "tool_failure"        # Tool falló
    VALIDATION_ERROR = "validation_error" # Error de validación
    CONTEXT_REFRESH = "context_refresh"   # Contexto actualizado
    OBJECTIVE_CHANGE = "objective_change" # Objetivo cambió


@dataclass
class ConversationStatePatch:
    """
    Patch para aplicar cambios al ConversationSnapshot
    
    Representa cambios incrementales que deben aplicarse al estado
    sin mutar el estado original.
    """
    slots_patch: Dict[str, Any]                    # Slots a actualizar/agregar
    slots_to_remove: List[str]                     # Slots a eliminar
    objective_update: Optional[str] = None         # Nuevo objetivo (si cambió)
    summary_update: Optional[str] = None           # Nuevo summary (si relevante)
    last_k_observations: List[ToolObservation]     # Últimas K observaciones
    cache_invalidation_keys: List[str]             # Keys de cache a invalidar
    change_reasons: List[str]                      # Razones de los cambios
    confidence_score: float = 1.0                  # Confianza en los cambios


class ObservationSummary(BaseModel):
    """Resumen compacto de observación para contexto LLM"""
    tool: str
    status: ToolStatus
    key_data: Dict[str, Any]  # Datos más relevantes (no todo el result)
    error_summary: Optional[str] = None
    execution_time_ms: int
    timestamp: float


# ==========================================
# STATE REDUCER
# ==========================================

class StateReducer:
    """
    Reducer que aplica observaciones de tools al estado conversacional
    
    Características:
    - Extrae slots de resultados de tools
    - Mantiene historial de observaciones (LRU con K=8)
    - Detecta cambios relevantes para invalidar cache
    - Genera patches inmutables para aplicar al estado
    - Comprime observaciones para contexto LLM eficiente
    """
    
    def __init__(self, max_observations: int = 8, cache_ttl_seconds: int = 1800):
        self.max_observations = max_observations
        self.cache_ttl = cache_ttl_seconds
        
        # Historial de observaciones por conversación (LRU)
        self._observation_history: Dict[str, deque] = {}
        
        # Cache de summaries compactos por conversación
        self._summary_cache: Dict[str, Tuple[List[ObservationSummary], float]] = {}
    
    def apply_observation(
        self,
        observation: ToolObservation,
        current_state: Dict[str, Any],
        workspace_config: Dict[str, Any],
        conversation_id: str
    ) -> ConversationStatePatch:
        """
        Aplica una ToolObservation al estado conversacional
        
        Args:
            observation: Observación del ToolBroker
            current_state: Estado actual (slots del ConversationSnapshot)
            workspace_config: Configuración del workspace (vertical, etc.)
            conversation_id: ID de la conversación
            
        Returns:
            ConversationStatePatch con cambios a aplicar
        """
        logger.info(f"[REDUCER] Applying observation: {observation.tool} -> {observation.status}")
        
        # 1. Agregar observación al historial
        self._add_to_history(conversation_id, observation)
        
        # 2. Inicializar patch
        patch = ConversationStatePatch(
            slots_patch={},
            slots_to_remove=[],
            last_k_observations=list(self._get_history(conversation_id)),
            cache_invalidation_keys=[],
            change_reasons=[]
        )
        
        # 3. Procesar según status de la observación
        if observation.status == ToolStatus.SUCCESS:
            self._process_success(observation, patch, current_state, workspace_config)
        elif observation.status in [ToolStatus.FAILURE, ToolStatus.TIMEOUT, ToolStatus.RATE_LIMITED]:
            self._process_failure(observation, patch, current_state)
        elif observation.status == ToolStatus.CIRCUIT_OPEN:
            self._process_circuit_open(observation, patch, current_state)
        elif observation.status == ToolStatus.DUPLICATE:
            self._process_duplicate(observation, patch, current_state)
        
        # 4. Detectar cambios relevantes para cache invalidation
        self._detect_cache_invalidation(observation, patch, current_state)
        
        # 5. Calcular confianza del patch
        patch.confidence_score = self._calculate_confidence(observation, patch)
        
        logger.info(f"[REDUCER] Generated patch: {len(patch.slots_patch)} slot updates, "
                   f"{len(patch.cache_invalidation_keys)} cache invalidations")
        
        return patch
    
    def apply_multiple_observations(
        self,
        observations: List[ToolObservation],
        current_state: Dict[str, Any],
        workspace_config: Dict[str, Any],
        conversation_id: str
    ) -> ConversationStatePatch:
        """
        Aplica múltiples observaciones en batch
        
        Útil cuando se ejecutan varios tools en paralelo
        """
        # Aplicar observaciones secuencialmente y mergear patches
        merged_patch = ConversationStatePatch(
            slots_patch={},
            slots_to_remove=[],
            last_k_observations=[],
            cache_invalidation_keys=[],
            change_reasons=[]
        )
        
        working_state = dict(current_state)
        
        for observation in observations:
            patch = self.apply_observation(observation, working_state, workspace_config, conversation_id)
            
            # Merge patches
            merged_patch.slots_patch.update(patch.slots_patch)
            merged_patch.slots_to_remove.extend(patch.slots_to_remove)
            merged_patch.cache_invalidation_keys.extend(patch.cache_invalidation_keys)
            merged_patch.change_reasons.extend(patch.change_reasons)
            
            # Aplicar cambios al working_state para siguiente iteración
            working_state.update(patch.slots_patch)
            for key in patch.slots_to_remove:
                working_state.pop(key, None)
        
        # Usar las observaciones finales
        merged_patch.last_k_observations = list(self._get_history(conversation_id))
        
        # Promediar confianza
        if observations:
            confidences = [self._calculate_confidence(obs, merged_patch) for obs in observations]
            merged_patch.confidence_score = sum(confidences) / len(confidences)
        
        return merged_patch
    
    def get_observation_context(self, conversation_id: str, max_tokens: int = 1000) -> str:
        """
        Genera contexto compacto de observaciones para el LLM
        
        Args:
            conversation_id: ID de la conversación
            max_tokens: Límite aproximado de tokens (heurística: ~4 chars = 1 token)
            
        Returns:
            String con contexto de observaciones para incluir en prompt
        """
        summaries = self._get_compressed_summaries(conversation_id)
        
        if not summaries:
            return ""
        
        # Construir contexto compacto
        context_lines = ["HERRAMIENTAS EJECUTADAS RECIENTEMENTE:"]
        
        for summary in summaries[-5:]:  # Últimas 5 observaciones
            if summary.status == ToolStatus.SUCCESS:
                key_info = ", ".join([f"{k}: {v}" for k, v in summary.key_data.items()][:3])
                line = f"✅ {summary.tool}: {key_info}"
            elif summary.status in [ToolStatus.FAILURE, ToolStatus.TIMEOUT]:
                line = f"❌ {summary.tool}: {summary.error_summary or 'error'}"
            elif summary.status == ToolStatus.RATE_LIMITED:
                line = f"⏳ {summary.tool}: rate limited"
            else:
                line = f"⚠️ {summary.tool}: {summary.status}"
            
            context_lines.append(line)
        
        context = "\n".join(context_lines)
        
        # Truncar si es muy largo (heurística: 4 chars ≈ 1 token)
        if len(context) > max_tokens * 4:
            context = context[:max_tokens * 4 - 3] + "..."
        
        return context
    
    def _process_success(
        self,
        observation: ToolObservation,
        patch: ConversationStatePatch,
        current_state: Dict[str, Any],
        workspace_config: Dict[str, Any]
    ):
        """Procesa observación exitosa extrayendo slots relevantes"""
        if not observation.result:
            return
        
        tool_name = observation.tool
        result_data = observation.result
        
        # Extraer slots según el tipo de tool
        if tool_name == "get_services":
            self._extract_services_slots(result_data, patch)
        elif tool_name == "get_availability":
            self._extract_availability_slots(result_data, patch)
        elif tool_name == "book_appointment":
            self._extract_booking_slots(result_data, patch)
        elif tool_name == "search_menu" or "search" in tool_name:
            self._extract_search_slots(result_data, patch)
        else:
            # Tool genérico - extraer campos obvios
            self._extract_generic_slots(result_data, patch, tool_name)
        
        # Marcar tool como ejecutado exitosamente
        patch.slots_patch[f"_tool_{tool_name}_success"] = True
        patch.slots_patch[f"_tool_{tool_name}_last_run"] = time.time()
        
        patch.change_reasons.append(f"Tool {tool_name} executed successfully")
    
    def _process_failure(
        self,
        observation: ToolObservation,
        patch: ConversationStatePatch,
        current_state: Dict[str, Any]
    ):
        """Procesa observación fallida"""
        tool_name = observation.tool
        
        # Marcar tool como fallido
        patch.slots_patch[f"_tool_{tool_name}_success"] = False
        patch.slots_patch[f"_tool_{tool_name}_error"] = observation.error or "unknown_error"
        patch.slots_patch[f"_tool_{tool_name}_last_run"] = time.time()
        
        # Si es un tool crítico, agregar a validation_errors
        if tool_name in ["book_appointment", "cancel_appointment"]:
            current_errors = current_state.get("_validation_errors", [])
            error_msg = f"Error ejecutando {tool_name}: {observation.error}"
            if error_msg not in current_errors:
                patch.slots_patch["_validation_errors"] = current_errors + [error_msg]
        
        patch.change_reasons.append(f"Tool {tool_name} failed: {observation.error}")
    
    def _process_circuit_open(
        self,
        observation: ToolObservation,
        patch: ConversationStatePatch,
        current_state: Dict[str, Any]
    ):
        """Procesa circuit breaker abierto"""
        tool_name = observation.tool
        
        patch.slots_patch[f"_tool_{tool_name}_circuit_open"] = True
        patch.slots_patch[f"_tool_{tool_name}_last_run"] = time.time()
        
        # Agregar mensaje informativo
        current_errors = current_state.get("_validation_errors", [])
        error_msg = f"Servicio {tool_name} temporalmente no disponible"
        if error_msg not in current_errors:
            patch.slots_patch["_validation_errors"] = current_errors + [error_msg]
        
        patch.change_reasons.append(f"Circuit breaker open for {tool_name}")
    
    def _process_duplicate(
        self,
        observation: ToolObservation,
        patch: ConversationStatePatch,
        current_state: Dict[str, Any]
    ):
        """Procesa observación duplicada (idempotencia)"""
        # No hacer cambios, solo logging
        patch.change_reasons.append(f"Duplicate call to {observation.tool} (idempotent)")
    
    def _extract_services_slots(self, result_data: Dict[str, Any], patch: ConversationStatePatch):
        """Extrae slots de get_services"""
        if "services" in result_data:
            services = result_data["services"]
            if isinstance(services, list) and services:
                # Guardar lista de servicios disponibles
                service_names = [s.get("name", s.get("service_name", str(s))) for s in services if s]
                patch.slots_patch["_available_services"] = service_names
                
                # Si hay precios, guardarlos
                prices = {}
                for service in services:
                    if isinstance(service, dict):
                        name = service.get("name", service.get("service_name"))
                        price = service.get("price", service.get("cost"))
                        if name and price:
                            prices[name] = price
                
                if prices:
                    patch.slots_patch["_service_prices"] = prices
    
    def _extract_availability_slots(self, result_data: Dict[str, Any], patch: ConversationStatePatch):
        """Extrae slots de get_availability"""
        if "available_slots" in result_data:
            slots = result_data["available_slots"]
            if isinstance(slots, list) and slots:
                patch.slots_patch["_available_times"] = slots
        
        if "next_available" in result_data:
            patch.slots_patch["_next_available"] = result_data["next_available"]
    
    def _extract_booking_slots(self, result_data: Dict[str, Any], patch: ConversationStatePatch):
        """Extrae slots de book_appointment"""
        if "booking_id" in result_data:
            patch.slots_patch["booking_id"] = result_data["booking_id"]
        
        if "confirmation_code" in result_data:
            patch.slots_patch["confirmation_code"] = result_data["confirmation_code"]
        
        if "appointment_date" in result_data:
            patch.slots_patch["confirmed_date"] = result_data["appointment_date"]
        
        if "appointment_time" in result_data:
            patch.slots_patch["confirmed_time"] = result_data["appointment_time"]
    
    def _extract_search_slots(self, result_data: Dict[str, Any], patch: ConversationStatePatch):
        """Extrae slots de herramientas de búsqueda"""
        if "results" in result_data:
            results = result_data["results"]
            if isinstance(results, list) and results:
                # Guardar contexto de búsqueda
                patch.slots_patch["_search_results_count"] = len(results)
                patch.slots_patch["_last_search_timestamp"] = time.time()
    
    def _extract_generic_slots(self, result_data: Dict[str, Any], patch: ConversationStatePatch, tool_name: str):
        """Extrae slots de tools genéricos"""
        # Buscar campos que coincidan con canonical slots
        for key, value in result_data.items():
            if key in CANONICAL_SLOTS:
                # Es un slot canónico, extraerlo
                patch.slots_patch[key] = value
            elif key in ["id", "confirmation", "reference"]:
                # IDs importantes
                patch.slots_patch[f"{tool_name}_{key}"] = value
    
    def _detect_cache_invalidation(
        self,
        observation: ToolObservation,
        patch: ConversationStatePatch,
        current_state: Dict[str, Any]
    ):
        """Detecta qué caches invalidar basado en los cambios"""
        tool_name = observation.tool
        
        # Invalidar cache de servicios si cambió información relevante
        if tool_name in ["get_services", "search_menu"]:
            patch.cache_invalidation_keys.append("services_cache")
        
        # Invalidar cache de disponibilidad si cambió
        if tool_name in ["get_availability", "book_appointment", "cancel_appointment"]:
            patch.cache_invalidation_keys.append("availability_cache")
        
        # Invalidar cache de contexto si hay nuevos datos relevantes
        if patch.slots_patch:
            patch.cache_invalidation_keys.append("context_cache")
    
    def _calculate_confidence(self, observation: ToolObservation, patch: ConversationStatePatch) -> float:
        """Calcula confianza en los cambios del patch"""
        base_confidence = 1.0
        
        # Reducir confianza si el tool falló
        if observation.status != ToolStatus.SUCCESS:
            base_confidence *= 0.3
        
        # Reducir confianza si hay pocos cambios
        if len(patch.slots_patch) == 0:
            base_confidence *= 0.5
        
        # Reducir confianza si el tiempo de ejecución fue muy alto (posible timeout)
        if observation.execution_time_ms > 10000:  # 10s
            base_confidence *= 0.7
        
        return max(0.1, min(1.0, base_confidence))
    
    def _add_to_history(self, conversation_id: str, observation: ToolObservation):
        """Agrega observación al historial LRU"""
        if conversation_id not in self._observation_history:
            self._observation_history[conversation_id] = deque(maxlen=self.max_observations)
        
        self._observation_history[conversation_id].append(observation)
        
        # Invalidar cache de summaries
        if conversation_id in self._summary_cache:
            del self._summary_cache[conversation_id]
    
    def _get_history(self, conversation_id: str) -> deque:
        """Obtiene historial de observaciones"""
        return self._observation_history.get(conversation_id, deque())
    
    def _get_compressed_summaries(self, conversation_id: str) -> List[ObservationSummary]:
        """Obtiene summaries compactos con cache"""
        now = time.time()
        
        # Check cache
        if conversation_id in self._summary_cache:
            summaries, cached_at = self._summary_cache[conversation_id]
            if now - cached_at < self.cache_ttl:
                return summaries
        
        # Generar summaries
        history = self._get_history(conversation_id)
        summaries = []
        
        for obs in history:
            # Extraer datos clave (no todo el result)
            key_data = {}
            if obs.result:
                # Extraer solo campos más importantes
                for key in ["id", "name", "price", "date", "time", "status", "count"]:
                    if key in obs.result:
                        value = obs.result[key]
                        # Truncar strings largas
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:47] + "..."
                        key_data[key] = value
            
            summary = ObservationSummary(
                tool=obs.tool,
                status=obs.status,
                key_data=key_data,
                error_summary=obs.error[:100] if obs.error else None,
                execution_time_ms=obs.execution_time_ms,
                timestamp=obs.timestamp
            )
            summaries.append(summary)
        
        # Cache summaries
        self._summary_cache[conversation_id] = (summaries, now)
        
        return summaries
    
    def clear_history(self, conversation_id: str):
        """Limpia historial de una conversación"""
        self._observation_history.pop(conversation_id, None)
        self._summary_cache.pop(conversation_id, None)
    
    def get_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del reducer"""
        total_conversations = len(self._observation_history)
        total_observations = sum(len(hist) for hist in self._observation_history.values())
        
        return {
            "total_conversations": total_conversations,
            "total_observations": total_observations,
            "cache_size": len(self._summary_cache),
            "max_observations_per_conversation": self.max_observations
        }


# ==========================================
# SINGLETON GLOBAL
# ==========================================

_reducer_instance: Optional[StateReducer] = None


def get_state_reducer() -> StateReducer:
    """Obtiene instancia singleton del reducer"""
    global _reducer_instance
    if _reducer_instance is None:
        _reducer_instance = StateReducer()
    return _reducer_instance


def apply_patch_to_snapshot(snapshot_dict: Dict[str, Any], patch: ConversationStatePatch) -> Dict[str, Any]:
    """
    Aplica un ConversationStatePatch a un diccionario de snapshot
    
    Helper function para aplicar patches de forma inmutable
    """
    # Crear copia del snapshot
    new_snapshot = dict(snapshot_dict)
    
    # Aplicar slots_patch
    if "slots" not in new_snapshot:
        new_snapshot["slots"] = {}
    
    new_slots = dict(new_snapshot["slots"])
    new_slots.update(patch.slots_patch)
    
    # Remover slots marcados para eliminación
    for key in patch.slots_to_remove:
        new_slots.pop(key, None)
    
    new_snapshot["slots"] = new_slots
    
    # Aplicar otros cambios
    if patch.objective_update:
        new_snapshot["objective"] = patch.objective_update
    
    if patch.summary_update:
        new_snapshot["summary"] = patch.summary_update
    
    return new_snapshot
