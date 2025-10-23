#!/bin/bash
# Helper para cambiar feature flags de canary
# Uso: ./scripts/set_canary.sh [legacy|canary10|canary50|full|rollback]

set -e

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Función para mostrar uso
show_usage() {
  echo "Uso: $0 [mode]"
  echo ""
  echo "Modos disponibles:"
  echo "  legacy      - 100% Legacy (ENABLE_SLM_PIPELINE=false)"
  echo "  canary10    - 10% SLM, 90% Legacy"
  echo "  canary50    - 50% SLM, 50% Legacy"
  echo "  full        - 100% SLM (ENABLE_SLM_PIPELINE=true, CANARY=0)"
  echo "  rollback    - Igual a legacy (rollback instantáneo)"
  echo ""
  echo "Ejemplo:"
  echo "  $0 legacy       # Paso 1: Validar Legacy"
  echo "  $0 canary10     # Paso 3: Activar Canary 10%"
  echo "  $0 full         # Escalado final: 100% SLM"
  echo ""
  exit 1
}

# Función para aplicar configuración
apply_config() {
  local mode=$1
  local enable_slm=$2
  local canary_pct=$3
  
  echo -e "${BLUE}[CONFIG]${NC} Aplicando modo: $mode"
  echo "  ENABLE_SLM_PIPELINE=$enable_slm"
  echo "  SLM_CANARY_PERCENT=$canary_pct"
  echo ""
  
  # Exportar para sesión actual
  export ENABLE_SLM_PIPELINE=$enable_slm
  export SLM_CANARY_PERCENT=$canary_pct
  
  # Actualizar .env si existe
  if [ -f .env ]; then
    echo -e "${BLUE}[CONFIG]${NC} Actualizando .env..."
    
    # Backup
    cp .env .env.backup.$(date +%Y%m%d_%H%M%S)
    
    # Actualizar o agregar variables
    if grep -q "ENABLE_SLM_PIPELINE" .env; then
      sed -i "s/^ENABLE_SLM_PIPELINE=.*/ENABLE_SLM_PIPELINE=$enable_slm/" .env
    else
      echo "ENABLE_SLM_PIPELINE=$enable_slm" >> .env
    fi
    
    if grep -q "SLM_CANARY_PERCENT" .env; then
      sed -i "s/^SLM_CANARY_PERCENT=.*/SLM_CANARY_PERCENT=$canary_pct/" .env
    else
      echo "SLM_CANARY_PERCENT=$canary_pct" >> .env
    fi
    
    echo -e "${GREEN}✓${NC} .env actualizado"
  else
    echo -e "${YELLOW}[WARN]${NC} .env no encontrado, usando solo export"
  fi
  
  echo ""
  echo -e "${BLUE}[CONFIG]${NC} Reiniciando servicio..."
  docker compose up -d pulpo-app
  
  echo ""
  echo "Esperando 3 segundos para inicialización..."
  sleep 3
  
  echo ""
  echo -e "${GREEN}✓${NC} Configuración aplicada"
  echo ""
  echo "Verificar logs:"
  echo "  docker compose logs pulpo-app | grep 'SLM Pipeline'"
  echo ""
}

# Main
if [ $# -eq 0 ]; then
  show_usage
fi

MODE=$1

case $MODE in
  legacy)
    echo -e "${YELLOW}[MODE]${NC} Legacy 100%"
    echo "Uso: Validación inicial (Paso 1)"
    echo ""
    apply_config "legacy" "false" "0"
    echo "Próximo paso:"
    echo "  ./tests/smoke/validate_legacy.sh"
    ;;
    
  canary10)
    echo -e "${YELLOW}[MODE]${NC} Canary 10%"
    echo "Uso: Activación inicial del SLM (Paso 3)"
    echo ""
    apply_config "canary10" "true" "10"
    echo "Próximo paso:"
    echo "  ./tests/smoke/validate_slm_canary.sh"
    ;;
    
  canary50)
    echo -e "${YELLOW}[MODE]${NC} Canary 50%"
    echo "Uso: Escalado intermedio"
    echo ""
    apply_config "canary50" "true" "50"
    echo "Próximo paso:"
    echo "  Monitorear métricas 24-48hs"
    ;;
    
  full)
    echo -e "${YELLOW}[MODE]${NC} Full SLM (100%)"
    echo "Uso: Escalado final"
    echo ""
    apply_config "full" "true" "0"
    echo "Próximo paso:"
    echo "  Monitorear métricas 1 semana"
    echo "  Deprecar Legacy si todo OK"
    ;;
    
  rollback)
    echo -e "${RED}[MODE]${NC} Rollback (100% Legacy)"
    echo "Uso: Rollback de emergencia"
    echo ""
    apply_config "rollback" "false" "0"
    echo "Próximo paso:"
    echo "  Revisar logs de errores"
    echo "  Ajustar prompts/schemas si es necesario"
    ;;
    
  *)
    echo -e "${RED}[ERROR]${NC} Modo desconocido: $MODE"
    echo ""
    show_usage
    ;;
esac

echo "═══════════════════════════════════════════════════════════════════"
echo -e "${GREEN}✅ Configuración completada${NC}"
echo "═══════════════════════════════════════════════════════════════════"



