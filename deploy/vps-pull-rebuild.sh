#!/usr/bin/env bash
# Ejecutar EN EL VPS, desde la raíz del repo (p. ej. /root/Clavo).
# git pull + rebuild imágenes web + gastro + up -d.
#
# También lo invoca GitHub Actions (.github/workflows/deploy-vps.yml) y deploy/vps-remote-deploy.sh
set -euo pipefail
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$REPO_ROOT"
echo "== vps-pull-rebuild $(date -Iseconds) @ $(git rev-parse --short HEAD 2>/dev/null || echo '?') =="
git pull
cd deploy
docker compose build web gastro
docker compose up -d web gastro
docker compose ps
echo ""
echo "Hecho. Prueba en el navegador (Ctrl+F5 si parece igual):"
echo "  Web:    puerto publicado en CLAVO_WEB_PUBLISH (defecto 37891)"
echo "  Gastro: puerto publicado en CLAVO_GASTRO_PUBLISH (defecto 37892)"
