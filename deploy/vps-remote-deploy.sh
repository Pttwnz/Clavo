#!/usr/bin/env bash
# Desde tu PC: tras git push, ejecuta el mismo pull + rebuild que en el VPS.
#
#   export VPS_SSH=root@203.0.113.10
#   export VPS_REPO_PATH=/root/clavo          # opcional; si no pones nada, en el servidor se usa $HOME/Clavo
#   export VPS_SSH_IDENTITY_FILE=~/.ssh/id_rsa # opcional
#   bash deploy/vps-remote-deploy.sh          # rama por defecto: main
#   bash deploy/vps-remote-deploy.sh master
#
set -euo pipefail
TARGET="${VPS_SSH:?Define VPS_SSH, p. ej. export VPS_SSH=root@TU_IP}"
BRANCH="${1:-main}"
# Vacío: el remoto usa $HOME/Clavo (evita que Git Bash en Windows expanda ~/ a la carpeta local).
REMOTE_BASE="${VPS_REPO_PATH:-}"

SSH_OPTS=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new)
if [ -n "${VPS_SSH_IDENTITY_FILE:-}" ]; then
  SSH_OPTS+=(-i "$VPS_SSH_IDENTITY_FILE")
fi

QBASE=$(printf %q "$REMOTE_BASE")
QBR=$(printf %q "$BRANCH")

echo "→ $TARGET  cd ${VPS_REPO_PATH:-\$HOME/Clavo (remoto)}  @ $BRANCH"
ssh "${SSH_OPTS[@]}" "$TARGET" "REMOTE_BASE=$QBASE BRANCH=$QBR bash -s" <<'REMOTE'
set -euo pipefail
CD_TARGET="${REMOTE_BASE:-$HOME/Clavo}"
cd "$CD_TARGET"
git fetch origin --prune
git checkout "$BRANCH"
git pull --ff-only origin "$BRANCH" || git pull --ff-only
exec bash deploy/vps-pull-rebuild.sh
REMOTE
