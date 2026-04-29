#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -f .env ]]; then
  echo "No existe deploy/.env — copia env.example:  cp env.example .env  y edítalo."
  exit 1
fi

docker compose build
docker compose up -d
docker compose ps

ip=$( (hostname -I 2>/dev/null || true) | awk '{print $1}' )
[[ -z "${ip}" ]] && ip="TU_IP"

# Puertos por defecto del compose (cámbialos en .env con CLAVO_WEB_PUBLISH / CLAVO_GASTRO_PUBLISH)
echo ""
echo "Prueba en el navegador (sustituye ${ip} si hace falta):"
echo "  Web:    http://${ip}:37891"
echo "  Gastro: http://${ip}:37892"
