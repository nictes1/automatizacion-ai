"""
Tool Manifest - Catálogo declarativo de herramientas para el Planner LLM

Este módulo define el catálogo de tools disponibles por vertical/workspace,
incluyendo schemas, permisos, rate limits y políticas de uso.
"""

from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field, validator
from enum import Enum
import yaml
import json
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class ToolScope(str, Enum):
    """Scopes de permisos para tools"""
    READ = "read"
    WRITE = "write"
    ADMIN = "admin"


class TierLevel(str, Enum):
    """Niveles de tier para workspaces"""
    BASIC = "basic"
    PRO = "pro"
    MAX = "max"


class ToolSpec(BaseModel):
    """
    Especificación de una herramienta disponible para el Planner LLM
    """
    name: str = Field(..., description="Nombre único del tool")
    description: str = Field(..., description="Descripción para el LLM")
    args_schema: Dict[str, Any] = Field(..., description="JSON Schema de argumentos")
    requires_slots: List[str] = Field(default_factory=list, description="Slots requeridos antes de ejecutar")
    scopes: List[ToolScope] = Field(default_factory=lambda: [ToolScope.READ], description="Permisos necesarios")
    tier_required: TierLevel = Field(default=TierLevel.BASIC, description="Tier mínimo del workspace")
    rate_limit_per_min: Optional[int] = Field(default=None, description="Máximo de llamadas por minuto")
    cost_tokens: int = Field(default=0, description="Costo estimado en tokens")
    timeout_ms: int = Field(default=5000, description="Timeout de ejecución en ms")

    @validator('args_schema')
    def validate_json_schema(cls, v):
        """Valida que el schema sea JSON Schema válido"""
        if not isinstance(v, dict):
            raise ValueError("args_schema debe ser un diccionario")
        if 'type' not in v:
            raise ValueError("args_schema debe tener 'type'")
        return v

    def to_llm_format(self) -> Dict[str, Any]:
        """Convierte el spec a formato para el LLM (function calling)"""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.args_schema
        }


class ToolManifest(BaseModel):
    """
    Manifiesto completo de tools para un vertical/workspace
    """
    workspace_id: Optional[str] = Field(default=None, description="ID del workspace (None = default)")
    vertical: str = Field(..., description="Vertical del negocio")
    version: str = Field(default="v1", description="Versión del manifest")
    tools: List[ToolSpec] = Field(..., description="Lista de tools disponibles")

    def get_tool(self, name: str) -> Optional[ToolSpec]:
        """Obtiene un tool por nombre"""
        return next((t for t in self.tools if t.name == name), None)

    def filter_by_tier(self, tier: TierLevel) -> List[ToolSpec]:
        """Filtra tools disponibles para un tier dado"""
        tier_order = {TierLevel.BASIC: 0, TierLevel.PRO: 1, TierLevel.MAX: 2}
        tier_value = tier_order.get(tier, 0)

        return [
            tool for tool in self.tools
            if tier_order.get(tool.tier_required, 0) <= tier_value
        ]

    def to_llm_tools(self, tier: TierLevel = TierLevel.BASIC) -> List[Dict[str, Any]]:
        """Convierte manifest a formato para LLM (solo tools permitidos por tier)"""
        available_tools = self.filter_by_tier(tier)
        return [tool.to_llm_format() for tool in available_tools]


class ToolManifestLoader:
    """
    Carga y cachea tool manifests desde YAML/DB
    """

    def __init__(self, config_dir: str = "config/tools"):
        self.config_dir = Path(config_dir)
        self._cache: Dict[str, ToolManifest] = {}

    def load_from_yaml(self, vertical: str) -> ToolManifest:
        """Carga manifest desde archivo YAML"""
        cache_key = f"{vertical}:default"

        if cache_key in self._cache:
            return self._cache[cache_key]

        yaml_path = self.config_dir / f"{vertical}.yml"

        if not yaml_path.exists():
            logger.warning(f"No se encontró manifest para vertical '{vertical}' en {yaml_path}")
            # Retornar manifest vacío
            return ToolManifest(vertical=vertical, tools=[])

        try:
            with open(yaml_path, 'r', encoding='utf-8') as f:
                data = yaml.safe_load(f)

            manifest = ToolManifest(**data)
            self._cache[cache_key] = manifest

            logger.info(f"Manifest cargado para {vertical}: {len(manifest.tools)} tools")
            return manifest

        except Exception as e:
            logger.error(f"Error cargando manifest para {vertical}: {e}")
            return ToolManifest(vertical=vertical, tools=[])

    def load(self, workspace_id: str, vertical: str) -> ToolManifest:
        """
        Carga manifest para un workspace específico

        Orden de precedencia:
        1. DB override para workspace_id (futuro)
        2. YAML default para vertical
        """
        # TODO: Implementar carga desde DB cuando tengamos la tabla
        # Por ahora, solo YAML defaults
        return self.load_from_yaml(vertical)

    def clear_cache(self):
        """Limpia el cache de manifests"""
        self._cache.clear()


# Instancia global del loader
_loader = ToolManifestLoader()


def get_manifest(workspace_id: str, vertical: str) -> ToolManifest:
    """
    Función helper para obtener manifest

    Args:
        workspace_id: ID del workspace
        vertical: Vertical del negocio (servicios, gastronomia, inmobiliaria)

    Returns:
        ToolManifest con los tools disponibles
    """
    return _loader.load(workspace_id, vertical)


def reload_manifests():
    """Recarga todos los manifests (útil para development)"""
    _loader.clear_cache()
