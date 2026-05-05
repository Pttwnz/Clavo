# Build cliente (PWA) + servidor API en una sola imagen.
FROM node:20-bookworm AS client-build
WORKDIR /client
COPY client/package.json ./
RUN npm install
COPY client/ ./
RUN npm run build

FROM node:20-bookworm AS server-build
WORKDIR /server
COPY server/package.json ./
RUN npm install
COPY server/ ./
RUN npm run build

FROM node:20-bookworm-slim
RUN apt-get update \
  && apt-get install -y --no-install-recommends ca-certificates \
  && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY server/package.json ./
RUN npm install --omit=dev
COPY --from=server-build /server/dist ./dist
COPY --from=client-build /client/dist ./public
ENV NODE_ENV=production
ENV PORT=37893
EXPOSE 37893
CMD ["node", "dist/index.js"]
