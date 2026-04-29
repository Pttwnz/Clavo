#!/usr/bin/env bash
set -eu
G="/root/Clavo/restaurante/gastro-app"
cp /tmp/gastro-up/config.py "$G/"
cp /tmp/gastro-up/nav_urls.py "$G/reservas/"
cp /tmp/gastro-up/decorators.py "$G/reservas/"
cp /tmp/gastro-up/tablet_middleware.py "$G/reservas/"
cp /tmp/gastro-up/__init__.py "$G/reservas/"
cp /tmp/gastro-up/public.py "$G/reservas/blueprints/"
cp /tmp/gastro-up/chat.py "$G/reservas/blueprints/admin/"
cp /tmp/gastro-up/login.html "$G/templates/"
cp /tmp/docker-compose.clavo.yml /root/Clavo/deploy/docker-compose.yml
cp /etc/nginx/sites-available/elclavo.gastromanager.es "/etc/nginx/sites-available/elclavo.gastromanager.es.bak.$(date +%Y%m%d%H%M)"
cp /tmp/elclavo.gastromanager.es.new /etc/nginx/sites-available/elclavo.gastromanager.es
nginx -t
systemctl reload nginx
ENV="/root/Clavo/deploy/.env"
if grep -q '^NEXT_PUBLIC_GASTRO_BASE_URL=' "$ENV"; then sed -i 's|^NEXT_PUBLIC_GASTRO_BASE_URL=.*|NEXT_PUBLIC_GASTRO_BASE_URL=https://elclavo.gastromanager.es|' "$ENV"; else echo 'NEXT_PUBLIC_GASTRO_BASE_URL=https://elclavo.gastromanager.es' >> "$ENV"; fi
if grep -q '^AUTH_URL=' "$ENV"; then sed -i 's|^AUTH_URL=.*|AUTH_URL=https://elclavo.gastromanager.es|' "$ENV"; else echo 'AUTH_URL=https://elclavo.gastromanager.es' >> "$ENV"; fi
if grep -q '^FLASK_MERGED_HOST_ROOT=' "$ENV"; then sed -i 's|^FLASK_MERGED_HOST_ROOT=.*|FLASK_MERGED_HOST_ROOT=1|' "$ENV"; else echo 'FLASK_MERGED_HOST_ROOT=1' >> "$ENV"; fi
if grep -q '^FLASK_SECURE_COOKIES=' "$ENV"; then sed -i 's|^FLASK_SECURE_COOKIES=.*|FLASK_SECURE_COOKIES=1|' "$ENV"; else echo 'FLASK_SECURE_COOKIES=1' >> "$ENV"; fi
cd /root/Clavo/deploy
docker compose build web gastro
docker compose up -d web gastro
echo "OK elclavo nginx + docker"
