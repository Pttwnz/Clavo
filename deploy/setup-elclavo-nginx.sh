#!/usr/bin/env bash
# Instala Nginx para https://elclavo.gastromanager.es (Next en /, Gastro en /panel, …).
# Ejecutar EN EL VPS, desde la raíz del repo o con ruta absoluta al script:
#   sudo bash deploy/setup-elclavo-nginx.sh
#   sudo bash deploy/setup-elclavo-nginx.sh --patch-env   # ajusta deploy/.env (URLs fusionadas)
#
# Requisitos: DNS tipo A «elclavo» → IP de este VPS. Docker Clavo en 37891 (web) y 37892 (gastro).
set -euo pipefail

DOMAIN="elclavo.gastromanager.es"
PATCH_ENV=0
for a in "$@"; do
  if [[ "$a" == "--patch-env" ]]; then PATCH_ENV=1; fi
done

if [[ "${EUID:-}" -ne 0 ]]; then
  echo "Ejecuta con sudo: sudo bash $0 $*"
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SITE_SRC="${SCRIPT_DIR}/nginx-sites/elclavo.gastromanager.es"
INIT_SRC="${SCRIPT_DIR}/nginx-sites/elclavo.gastromanager.es-init-acme.conf"
ENV_FILE="${SCRIPT_DIR}/.env"
CERT="/etc/letsencrypt/live/${DOMAIN}/fullchain.pem"

if [[ ! -f "$SITE_SRC" ]]; then
  echo "No encuentro: $SITE_SRC"
  exit 1
fi

mkdir -p /etc/nginx/snippets /var/www/html

SNIP="/etc/nginx/snippets/letsencrypt-acme-noauth.conf"
if [[ ! -f "$SNIP" ]]; then
  cat >"$SNIP" <<'SNIPET'
# HTTP-01 Let's Encrypt (incluido por sitios Clavo)
location ^~ /.well-known/acme-challenge/ {
    default_type "text/plain";
    root /var/www/html;
}
SNIPET
  echo "Creado $SNIP"
fi

install -m 644 "$INIT_SRC" /etc/nginx/sites-available/"${DOMAIN}-init-acme"
install -m 644 "$SITE_SRC" /etc/nginx/sites-available/"${DOMAIN}"

if [[ ! -f "$CERT" ]]; then
  echo ""
  echo "== Aún no hay certificado TLS en $CERT =="
  echo "1) Activo solo el sitio temporal para ACME (puerto 80)."
  rm -f "/etc/nginx/sites-enabled/${DOMAIN}"
  ln -sf "/etc/nginx/sites-available/${DOMAIN}-init-acme" "/etc/nginx/sites-enabled/${DOMAIN}-init-acme"
  nginx -t
  systemctl reload nginx || systemctl restart nginx
  echo ""
  echo "2) Obtén el certificado (elige UNA opción):"
  echo "   sudo certbot certonly --webroot -w /var/www/html -d ${DOMAIN}"
  echo "   # o: sudo certbot certonly --nginx -d ${DOMAIN}"
  echo ""
  echo "3) Vuelve a ejecutar este mismo script:"
  echo "   sudo bash deploy/setup-elclavo-nginx.sh"
  echo ""
  if [[ "$PATCH_ENV" -eq 1 ]]; then
    echo "(Opcional) Tras el certificado y el paso 3, con --patch-env se actualiza deploy/.env"
  fi
  exit 0
fi

echo "== Certificado encontrado; activando sitio completo (443 + 80) =="
rm -f "/etc/nginx/sites-enabled/${DOMAIN}-init-acme"
ln -sf "/etc/nginx/sites-available/${DOMAIN}" "/etc/nginx/sites-enabled/${DOMAIN}"
nginx -t
systemctl reload nginx || systemctl restart nginx
echo "Nginx OK: https://${DOMAIN}/ y https://${DOMAIN}/panel"

if [[ "$PATCH_ENV" -eq 1 && -f "$ENV_FILE" ]]; then
  set +e
  grep -q '^NEXT_PUBLIC_GASTRO_BASE_URL=' "$ENV_FILE" && sed -i "s|^NEXT_PUBLIC_GASTRO_BASE_URL=.*|NEXT_PUBLIC_GASTRO_BASE_URL=https://${DOMAIN}|" "$ENV_FILE" || echo "NEXT_PUBLIC_GASTRO_BASE_URL=https://${DOMAIN}" >>"$ENV_FILE"
  grep -q '^AUTH_URL=' "$ENV_FILE" && sed -i "s|^AUTH_URL=.*|AUTH_URL=https://${DOMAIN}|" "$ENV_FILE" || echo "AUTH_URL=https://${DOMAIN}" >>"$ENV_FILE"
  grep -q '^FLASK_MERGED_HOST_ROOT=' "$ENV_FILE" && sed -i 's|^FLASK_MERGED_HOST_ROOT=.*|FLASK_MERGED_HOST_ROOT=1|' "$ENV_FILE" || echo "FLASK_MERGED_HOST_ROOT=1" >>"$ENV_FILE"
  grep -q '^TRUST_PROXY=' "$ENV_FILE" && sed -i 's|^TRUST_PROXY=.*|TRUST_PROXY=1|' "$ENV_FILE" || echo "TRUST_PROXY=1" >>"$ENV_FILE"
  grep -q '^FLASK_SECURE_COOKIES=' "$ENV_FILE" && sed -i 's|^FLASK_SECURE_COOKIES=.*|FLASK_SECURE_COOKIES=1|' "$ENV_FILE" || echo "FLASK_SECURE_COOKIES=1" >>"$ENV_FILE"
  set -e
  echo "Actualizado $ENV_FILE (rebuild web: cd $SCRIPT_DIR && docker compose build web && docker compose up -d web gastro)"
elif [[ "$PATCH_ENV" -eq 1 ]]; then
  echo "No existe $ENV_FILE — copia deploy/env.example a deploy/.env y vuelve a pasar --patch-env"
fi
