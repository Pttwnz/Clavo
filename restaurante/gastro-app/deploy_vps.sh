#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$PROJECT_DIR"

echo "[1/6] Instalando dependencias del sistema..."
sudo apt update
sudo apt install -y python3 python3-venv python3-pip nginx

echo "[2/6] Creando entorno virtual..."
python3 -m venv .venv
source .venv/bin/activate

echo "[3/6] Instalando dependencias Python..."
pip install --upgrade pip
pip install -r requirements.txt

echo "[4/6] Configurando entorno..."
if [ ! -f .env ]; then
  cp .env.example .env
  echo "Se creó .env desde .env.example. Edita SECRET_KEY antes de producción."
fi

echo "[5/6] Probando arranque con gunicorn..."
pkill -f "gunicorn.*wsgi:app" >/dev/null 2>&1 || true
nohup .venv/bin/gunicorn -w 3 -b 0.0.0.0:8000 wsgi:app > gunicorn.log 2>&1 &
sleep 2

echo "[6/6] Estado:"
ss -ltnp | rg ":8000" || true
echo "Gunicorn levantado en puerto 8000."
echo "Siguiente paso: configurar nginx reverse proxy a 127.0.0.1:8000."
