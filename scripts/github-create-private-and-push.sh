#!/usr/bin/env bash
# Igual que el .ps1: crea repo privado vía API y push de main.
#
#   export GITHUB_TOKEN=github_pat_...
#   export GITHUB_OWNER=tu_usuario
#   export GITHUB_REPO=Clavo
#   bash scripts/github-create-private-and-push.sh
#
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

: "${GITHUB_TOKEN:?GITHUB_TOKEN}"
: "${GITHUB_OWNER:?GITHUB_OWNER}"
: "${GITHUB_REPO:?GITHUB_REPO}"

CREATE='{"name":"'"$GITHUB_REPO"'","private":true,"description":"Clavo — Taberna (Next + Gastro)"}'
code="$(curl -sS -o /tmp/gh-create.json -w "%{http_code}" -X POST \
  -H "Accept: application/vnd.github+json" \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "X-GitHub-Api-Version: 2022-11-28" \
  "https://api.github.com/user/repos" \
  -d "$CREATE")"

if [ "$code" = "201" ]; then
  echo "Repositorio privado creado: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"
elif [ "$code" = "422" ]; then
  echo "Repo ya existe o nombre inválido (422). Continuando con push."
else
  echo "Error API GitHub HTTP $code"; cat /tmp/gh-create.json; exit 1
fi

git remote remove origin 2>/dev/null || true
git remote add origin "https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git"
git push "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_OWNER}/${GITHUB_REPO}.git" "main:main"
git branch --set-upstream-to=origin/main main

echo "Listo: https://github.com/${GITHUB_OWNER}/${GITHUB_REPO}"
