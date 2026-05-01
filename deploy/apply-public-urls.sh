#!/usr/bin/env bash
# Wrapper: aplica DNS en deploy/.env y opcional rebuild.
# Uso (VPS, raíz del repo):
#   bash deploy/apply-public-urls.sh 'https://app.gastromanager.es' --auth-url 'https://clavo.gastromanager.es' --rebuild
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec python3 "$ROOT/deploy/apply_public_urls.py" "$@"
