#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
#  deploy.sh — Script de despliegue en producción para Authent
#  Uso: ./deploy.sh [--no-pull]
#
#  Pasos:
#    1. Pull del último código (omitir con --no-pull)
#    2. Bajar todos los contenedores
#    3. Build + arranque con override de producción
#    4. Verificación de salud
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

# ── Colores ───────────────────────────────────────────────────────────────────
GREEN="\033[0;32m"
YELLOW="\033[1;33m"
RED="\033[0;31m"
CYAN="\033[0;36m"
RESET="\033[0m"

log()  { echo -e "${CYAN}[deploy]${RESET} $*"; }
ok()   { echo -e "${GREEN}[  OK  ]${RESET} $*"; }
warn() { echo -e "${YELLOW}[ WARN ]${RESET} $*"; }
fail() { echo -e "${RED}[ FAIL ]${RESET} $*"; exit 1; }

# ── Directorio raíz del proyecto ──────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# ── Argumentos ────────────────────────────────────────────────────────────────
NO_PULL=false
for arg in "$@"; do
  [[ "$arg" == "--no-pull" ]] && NO_PULL=true
done

COMPOSE="docker compose"

# ── 1. Git pull ───────────────────────────────────────────────────────────────
if [ "$NO_PULL" = false ]; then
  log "Actualizando código desde git..."
  git pull origin main || fail "Error al hacer git pull"
  ok "Código actualizado"
else
  warn "Omitiendo git pull (--no-pull)"
fi

# ── 2. Bajar contenedores ─────────────────────────────────────────────────────
log "Bajando contenedores..."
$COMPOSE down --remove-orphans
ok "Contenedores detenidos"

# ── 3. Build y arranque ───────────────────────────────────────────────────────
log "Construyendo imágenes y levantando servicios..."
$COMPOSE up -d --build
ok "Servicios en marcha"

# ── 4. Health check ───────────────────────────────────────────────────────────
log "Esperando que Django esté disponible..."
RETRIES=20
WAIT=3
for i in $(seq 1 $RETRIES); do
  STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost/health/ 2>/dev/null || echo "000")
  if [[ "$STATUS" == "200" ]]; then
    ok "Health check OK (HTTP 200)"
    break
  fi
  if [[ "$i" -eq "$RETRIES" ]]; then
    fail "El servicio no respondió tras $((RETRIES * WAIT))s — revisa: docker compose logs web"
  fi
  echo -e "  intento $i/$RETRIES — HTTP $STATUS, reintentando en ${WAIT}s..."
  sleep $WAIT
done

# ── Resumen ───────────────────────────────────────────────────────────────────
echo ""
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo -e "${GREEN}  Authent desplegado correctamente en producción ✓${RESET}"
echo -e "${GREEN}  https://authent.atharix.com${RESET}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${RESET}"
echo ""
echo -e "  Logs:    ${CYAN}docker compose logs -f${RESET}"
echo -e "  Estado:  ${CYAN}docker compose ps${RESET}"
echo ""
