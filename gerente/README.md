# Gerente (uso personal)

PWA móvil + API en un solo contenedor: proveedores con plantilla, pedidos (borrador → enviado → recibido, texto para WhatsApp), tareas con vencimiento y resumen opcional por **Telegram**.

## Desarrollo local

**API** (puerto 37893):

```powershell
cd gerente/server
$env:GERENTE_API_KEY = "dev-local"
$env:DATABASE_PATH = "$PWD/data/gerente.db"
npm run dev
```

**Cliente** (puerto 5178, proxy `/api` → 37893):

```powershell
cd gerente/client
npm run dev
```

Abre `http://127.0.0.1:5178`, pestaña **Clave** y pega la misma `GERENTE_API_KEY`.

## VPS (Docker)

En `deploy/.env` define al menos:

- `GERENTE_API_KEY` — clave que introduces en la PWA.
- Opcional: `GERENTE_CRON_SECRET`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `GERENTE_TZ`.

Desde `deploy/`:

```bash
docker compose build gerente
docker compose up -d gerente
```

URL típica: `http://TU_IP:37893` (o el puerto que pongas en `CLAVO_GERENTE_PUBLISH`). En el iPhone: Safari → **Añadir a la pantalla de inicio**.

Si la PWA y la API no comparten origen, crea el cliente con `VITE_API_BASE=https://tu-dominio-o-ip:37893` y vuelve a construir la imagen.

## Cron + Telegram

Ejemplo en el VPS (sustituye el secreto):

```bash
curl -sS -X POST "http://127.0.0.1:37893/api/internal/digest" \
  -H "X-Cron-Secret: TU_GERENTE_CRON_SECRET"
```

Programa eso con `cron` dos veces al día. Sin token de Telegram, el endpoint responde `ok` pero no envía nada.
