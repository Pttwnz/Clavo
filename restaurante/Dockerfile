# Next.js (Taberna web + API Prisma) — context: restaurante/
FROM node:22-bookworm-slim AS build

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends openssl ca-certificates python3 make g++ \
    && rm -rf /var/lib/apt/lists/*

COPY package.json package-lock.json ./
RUN npm ci

COPY prisma ./prisma
COPY . .

ARG NEXT_PUBLIC_GASTRO_BASE_URL=http://127.0.0.1:37892
ENV NEXT_PUBLIC_GASTRO_BASE_URL=${NEXT_PUBLIC_GASTRO_BASE_URL}
ARG NEXT_PUBLIC_MERGED_HOST_ROOT=0
ENV NEXT_PUBLIC_MERGED_HOST_ROOT=${NEXT_PUBLIC_MERGED_HOST_ROOT}
ARG NEXT_PUBLIC_TURNSTILE_SITE_KEY=
ENV NEXT_PUBLIC_TURNSTILE_SITE_KEY=${NEXT_PUBLIC_TURNSTILE_SITE_KEY}

RUN npx prisma generate
RUN npm run build
RUN npm install -g prisma@7.7.0 && npm prune --omit=dev

ENV NODE_ENV=production \
    NEXT_TELEMETRY_DISABLED=1

RUN mkdir -p /data

EXPOSE 3000

# Sin script externo: evita fallos en Docker por CRLF (Windows) en docker-entrypoint-web.sh.
ENTRYPOINT ["sh", "-c", "set -e; mkdir -p /data; export DATABASE_URL=\"${DATABASE_URL:-file:/data/clavo.db}\"; prisma migrate deploy; exec npx next start -H 0.0.0.0 -p 3000"]
