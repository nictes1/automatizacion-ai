"""
Policy Engine - Validación de políticas para Tool Calling (Planner LLM)

Este módulo valida que las acciones solicitadas por el Planner LLM
cumplan con las políticas del workspace (tier, permisos, rate limits, etc.)

NOTA: Este PolicyEngine es para el NUEVO sistema (Planner + Tool Broker).
      El PolicyEngine viejo en orchestrator_service.py se eliminará en Fase 2.
"""

from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field
from enum import Enum
import re
import logging
import time

from services.tool_manifest import (
    ToolManifest,
    ToolSpec,
    TierLevel,
    ToolScope,
    get_manifest
)
from services.canonical_slots import normalize_slots, redact_pii

try:
    import jsonschema
    from jsonschema import validate, ValidationError
    HAS_JSONSCHEMA = True
except ImportError:
    HAS_JSONSCHEMA = False
    logging.warning("jsonschema not installed - args validation will be skipped")

logger = logging.getLogger(__name__)


class PolicyDecision(str, Enum):
    """Decisiones del policy engine"""
    ALLOW = "allow"
    DENY = "deny"
    ASK_CLARIFICATION = "ask_clarification"


class PlanAction(BaseModel):
    """Acción planeada por el LLM"""
    tool: str = Field(..., description="Nombre del tool")
    args: Dict[str, Any] = Field(default_factory=dict, description="Argumentos del tool")


class PolicyResult(BaseModel):
    """Resultado de validación de política"""
    decision: PolicyDecision
    reason: str
    missing_slots: List[str] = Field(default_factory=list)
    validation_errors: List[str] = Field(default_factory=list)
    allowed: bool = Field(default=False)

    # Mejoras para Planner (needs/why explicables)
    needs: List[str] = Field(default_factory=list, description="Qué necesita para proceder")
    why: str = Field(default="", description="Explicación detallada para el LLM")
    normalized_args: Dict[str, Any] = Field(default_factory=dict, description="Args normalizados con coerción")
    manifest_version: str = Field(default="v1", description="Versión del manifest usada")

    @property
    def is_allowed(self) -> bool:
        return self.decision == PolicyDecision.ALLOW


class WorkspacePolicy(BaseModel):
    """
    Políticas configurables por workspace
    """
    max_tool_calls: int = Field(default=3, description="Máximo de tool calls por turno")
    one_slot_per_turn: bool = Field(default=True, description="Máximo 1 slot por turno")
    tools_first: List[str] = Field(default_factory=list, description="Tools que deben llamarse antes de responder")
    forbid_patterns: List[str] = Field(default_factory=list, description="Patterns de tools prohibidos (regex)")
    min_confidence: float = Field(default=0.55, description="Confianza mínima para intent")
    allow_offers_without_stock: bool = Field(default=False, description="Permitir ofrecer sin validar stock")
    require_confirmation: bool = Field(default=True, description="Requiere confirmación antes de write")


class PolicyEngine:
    """
    Engine de validación de políticas para tool calling

    Valida:
    - Tier del workspace
    - Scopes/permisos
    - Rate limits
    - Requires_slots completos
    - Args válidos contra JSON Schema
    - Políticas específicas del workspace
    """

    def __init__(self):
        self._rate_limit_cache: Dict[str, List[float]] = {}

    def validate(
        self,
        action: PlanAction,
        state: Dict[str, Any],
        workspace: Dict[str, Any],
        manifest: ToolManifest
    ) -> PolicyResult:
        """
        Valida una acción contra las políticas del workspace

        Args:
            action: Acción que el LLM quiere ejecutar
            state: Estado actual (slots, summary, etc.)
            workspace: Info del workspace (tier, policy, etc.)
            manifest: Tool manifest del vertical

        Returns:
            PolicyResult con decisión, razones, needs y args normalizados
        """
        workspace_id = workspace.get("id", "unknown")
        tier = TierLevel(workspace.get("tier", "basic"))
        policy = WorkspacePolicy(**workspace.get("policy", {}))

        # Redactar PII en logs
        redacted_args = redact_pii(action.args)
        logger.info(f"[POLICY] Validando {action.tool} para workspace {workspace_id} (tier: {tier}), args: {redacted_args}")

        # 1. Verificar que el tool existe
        tool_spec = manifest.get_tool(action.tool)
        if not tool_spec:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Tool '{action.tool}' no existe en manifest",
                why=f"El tool '{action.tool}' no está disponible en el catálogo",
                needs=[],
                allowed=False,
                manifest_version=manifest.version
            )

        # 1.5. Normalizar args (coerción de tipos: fechas, emails, etc.)
        normalized_args, norm_errors = normalize_slots(action.args)

        if norm_errors:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Errores de normalización: {'; '.join(norm_errors)}",
                why=f"Los argumentos tienen formato incorrecto: {', '.join(norm_errors)}",
                needs=[],
                validation_errors=norm_errors,
                allowed=False,
                manifest_version=manifest.version
            )

        # 2. Validar tier requerido
        tier_result = self._validate_tier(tool_spec, tier, manifest.version)
        if not tier_result.allowed:
            return tier_result

        # 3. Validar patterns prohibidos
        forbid_result = self._validate_forbid_patterns(action.tool, policy, manifest.version)
        if not forbid_result.allowed:
            return forbid_result

        # 4. Validar scopes/permisos
        scope_result = self._validate_scopes(tool_spec, workspace, manifest.version)
        if not scope_result.allowed:
            return scope_result

        # 5. Validar requires_slots
        slots_result = self._validate_required_slots(tool_spec, state.get("slots", {}), manifest.version)
        if not slots_result.allowed:
            return slots_result

        # 6. Validar args contra JSON Schema
        if HAS_JSONSCHEMA:
            args_result = self._validate_args_schema(normalized_args, tool_spec, manifest.version)
            if not args_result.allowed:
                return args_result

        # 7. Validar rate limits
        rate_result = self._validate_rate_limit(tool_spec, workspace_id, manifest.version)
        if not rate_result.allowed:
            return rate_result

        # 8. Validar tools_first (debe llamar pricing antes de prometer)
        first_result = self._validate_tools_first(action.tool, policy, state, manifest.version)
        if not first_result.allowed:
            return first_result

        # ✅ Todas las validaciones pasaron
        logger.info(f"[POLICY] ✅ {action.tool} PERMITIDO")
        return PolicyResult(
            decision=PolicyDecision.ALLOW,
            reason=f"Tool '{action.tool}' permitido para tier {tier}",
            why="Todas las validaciones pasaron",
            needs=[],
            normalized_args=normalized_args,
            allowed=True,
            manifest_version=manifest.version
        )

    def _validate_tier(self, tool_spec: ToolSpec, workspace_tier: TierLevel, manifest_version: str) -> PolicyResult:
        """Valida que el workspace tenga el tier necesario"""
        tier_order = {TierLevel.BASIC: 0, TierLevel.PRO: 1, TierLevel.MAX: 2}

        required_level = tier_order.get(tool_spec.tier_required, 0)
        workspace_level = tier_order.get(workspace_tier, 0)

        if workspace_level < required_level:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Tool '{tool_spec.name}' requiere tier {tool_spec.tier_required}, workspace tiene {workspace_tier}",
                why=f"Tu plan actual ({workspace_tier}) no incluye esta funcionalidad. Necesitas tier {tool_spec.tier_required}",
                needs=[f"upgrade_tier_{tool_spec.tier_required}"],
                allowed=False,
                manifest_version=manifest_version
            )

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="Tier OK", allowed=True, manifest_version=manifest_version)

    def _validate_forbid_patterns(self, tool_name: str, policy: WorkspacePolicy, manifest_version: str) -> PolicyResult:
        """Valida que el tool no esté en la lista de prohibidos"""
        for pattern in policy.forbid_patterns:
            if re.match(pattern, tool_name):
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Tool '{tool_name}' prohibido por pattern '{pattern}'",
                    why=f"Esta acción está prohibida por políticas de seguridad",
                    needs=[],
                    allowed=False,
                    manifest_version=manifest_version
                )

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="No forbid patterns", allowed=True, manifest_version=manifest_version)

    def _validate_scopes(self, tool_spec: ToolSpec, workspace: Dict[str, Any], manifest_version: str) -> PolicyResult:
        """Valida que el workspace tenga los scopes necesarios"""
        # TODO: Implementar scopes granulares cuando tengamos tabla de permisos
        # Por ahora, validar solo write vs read

        if ToolScope.WRITE in tool_spec.scopes or ToolScope.ADMIN in tool_spec.scopes:
            # Write/Admin tools requieren verificación adicional
            if workspace.get("status") != "active":
                return PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Tool '{tool_spec.name}' requiere workspace activo",
                    why="Tu cuenta no está activa. Contactá soporte",
                    needs=["activate_workspace"],
                    allowed=False,
                    manifest_version=manifest_version
                )

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="Scopes OK", allowed=True, manifest_version=manifest_version)

    def _validate_required_slots(self, tool_spec: ToolSpec, slots: Dict[str, Any], manifest_version: str) -> PolicyResult:
        """Valida que todos los slots requeridos estén completos"""
        missing_slots = []

        for slot_name in tool_spec.requires_slots:
            if not slots.get(slot_name):
                missing_slots.append(slot_name)

        if missing_slots:
            # Generar mensaje why explicable
            slot_names_es = ", ".join([f"'{s}'" for s in missing_slots])
            return PolicyResult(
                decision=PolicyDecision.ASK_CLARIFICATION,
                reason=f"Faltan slots requeridos: {', '.join(missing_slots)}",
                why=f"Necesito que me proporciones: {slot_names_es}",
                needs=missing_slots,
                missing_slots=missing_slots,
                allowed=False,
                manifest_version=manifest_version
            )

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="Slots completos", allowed=True, manifest_version=manifest_version)

    def _validate_args_schema(self, args: Dict[str, Any], tool_spec: ToolSpec, manifest_version: str) -> PolicyResult:
        """Valida argumentos contra JSON Schema"""
        if not HAS_JSONSCHEMA:
            return PolicyResult(decision=PolicyDecision.ALLOW, reason="JSON Schema no disponible", allowed=True, manifest_version=manifest_version)

        try:
            validate(instance=args, schema=tool_spec.args_schema)
            return PolicyResult(decision=PolicyDecision.ALLOW, reason="Args válidos", allowed=True, manifest_version=manifest_version)

        except ValidationError as e:
            error_msg = f"Args inválidos: {e.message}"
            logger.warning(f"[POLICY] {error_msg}")

            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=error_msg,
                why=f"El argumento proporcionado tiene formato incorrecto: {e.message}",
                needs=[],
                validation_errors=[e.message],
                allowed=False,
                manifest_version=manifest_version
            )

    def _validate_rate_limit(self, tool_spec: ToolSpec, workspace_id: str, manifest_version: str) -> PolicyResult:
        """Valida rate limits por tool"""
        if not tool_spec.rate_limit_per_min:
            return PolicyResult(decision=PolicyDecision.ALLOW, reason="Sin rate limit", allowed=True, manifest_version=manifest_version)

        # Clave para cache: workspace:tool
        cache_key = f"{workspace_id}:{tool_spec.name}"

        # Limpiar timestamps viejos (> 1 minuto)
        now = time.time()
        if cache_key in self._rate_limit_cache:
            self._rate_limit_cache[cache_key] = [
                ts for ts in self._rate_limit_cache[cache_key]
                if now - ts < 60
            ]

        # Contar llamadas en el último minuto
        recent_calls = len(self._rate_limit_cache.get(cache_key, []))

        if recent_calls >= tool_spec.rate_limit_per_min:
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Rate limit excedido: {recent_calls}/{tool_spec.rate_limit_per_min} calls/min",
                why="Demasiadas consultas en poco tiempo. Esperá un momento e intentá de nuevo",
                needs=["wait"],
                allowed=False,
                manifest_version=manifest_version
            )

        # Registrar esta llamada
        if cache_key not in self._rate_limit_cache:
            self._rate_limit_cache[cache_key] = []
        self._rate_limit_cache[cache_key].append(now)

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="Rate limit OK", allowed=True, manifest_version=manifest_version)

    def _validate_tools_first(
        self,
        tool_name: str,
        policy: WorkspacePolicy,
        state: Dict[str, Any],
        manifest_version: str
    ) -> PolicyResult:
        """
        Valida que se hayan llamado tools obligatorios antes de responder

        Ejemplo: Si tools_first=["get_services"], no se puede book_appointment
        sin haber consultado get_services primero
        """
        if not policy.tools_first:
            return PolicyResult(decision=PolicyDecision.ALLOW, reason="Sin tools_first", allowed=True, manifest_version=manifest_version)

        # Si el tool actual está en tools_first, siempre permitir
        if tool_name in policy.tools_first:
            return PolicyResult(decision=PolicyDecision.ALLOW, reason="Tool es tools_first", allowed=True, manifest_version=manifest_version)

        # Si es un write tool, verificar que se hayan llamado los tools_first
        called_tools = state.get("called_tools", [])

        missing_tools = [t for t in policy.tools_first if t not in called_tools]

        if missing_tools:
            tools_names = ", ".join([f"'{t}'" for t in missing_tools])
            return PolicyResult(
                decision=PolicyDecision.DENY,
                reason=f"Debe llamar {missing_tools} antes de '{tool_name}'",
                why=f"Primero necesito consultar {tools_names} antes de proceder",
                needs=missing_tools,
                allowed=False,
                manifest_version=manifest_version
            )

        return PolicyResult(decision=PolicyDecision.ALLOW, reason="Tools_first cumplidos", allowed=True, manifest_version=manifest_version)

    def validate_plan(
        self,
        actions: List[PlanAction],
        state: Dict[str, Any],
        workspace: Dict[str, Any],
        manifest: ToolManifest
    ) -> List[PolicyResult]:
        """
        Valida un plan completo (múltiples acciones)

        Returns:
            Lista de PolicyResult, uno por cada acción
        """
        results = []
        policy = WorkspacePolicy(**workspace.get("policy", {}))

        # Validar max_tool_calls
        if len(actions) > policy.max_tool_calls:
            # Todas las acciones denegadas
            for action in actions:
                results.append(PolicyResult(
                    decision=PolicyDecision.DENY,
                    reason=f"Excede max_tool_calls: {len(actions)} > {policy.max_tool_calls}",
                    why=f"Solo puedo ejecutar {policy.max_tool_calls} acciones por vez",
                    needs=[],
                    allowed=False,
                    manifest_version=manifest.version
                ))
            return results

        # Validar cada acción individualmente
        for action in actions:
            result = self.validate(action, state, workspace, manifest)
            results.append(result)

        return results
