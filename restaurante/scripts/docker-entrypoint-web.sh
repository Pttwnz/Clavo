#!/bin/sh
set -e
mkdir -p /data
export DATABASE_URL="${DATABASE_URL:-file:/data/clavo.db}"
prisma migrate deploy
exec npx next start -H 0.0.0.0 -p 3000
