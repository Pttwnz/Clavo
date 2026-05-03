# Despliegue en VPS (Docker)

**Primera subida paso a paso:** [`SUBIR-VPS.md`](./SUBIR-VPS.md) · script: `./vps-up.sh` (tras crear `.env`).  
**Dominios `clavo` = web / `app` = Gastro:** [`DOMINIOS-GASTROMANAGER.md`](./DOMINIOS-GASTROMANAGER.md) · ejemplo Nginx: `nginx-snippet.example.conf`.  
**Mismo host (p. ej. elclavo…): web en `/` y Gastro en `/panel`:** `nginx-sites/elclavo.gastromanager.es` + `FLASK_MERGED_HOST_ROOT=1` en `.env`. Instalación en el VPS: `sudo bash deploy/setup-elclavo-nginx.sh` (y opción `--patch-env`).  
**App legacy puerto 8000 en subdominio:** `nginx-sites/app.gastromanager.es-reservas-8000` → `https://app.gastromanager.es` (en el VPS ya está + certificado Let’s Encrypt). Los `.conf` de Nginx deben ser **LF** (sin CRLF de Windows) o `nginx` puede ignorar `server_name` y capturar mal el tráfico.

Stack listo para **migrar Taberna El Clavo** a un servidor Linux sin pisar servicios habituales: la web Next.js y la app Flask (Gastro) publican en **puertos altos fijos por defecto**:

| Servicio | Puerto host (defecto) | Contenedor | Descripción breve |
|----------|------------------------|------------|-------------------|
| **web** | **37891** | 3000 | Sitio público, `/admin`, API Prisma, proxy de reservas a Gastro |
| **gastro** | **37892** | 37892 | Panel Gastro, tablet, SQLite propio de Gastro |

Puedes cambiar el puerto del host con `CLAVO_WEB_PUBLISH` y `CLAVO_GASTRO_PUBLISH` en `.env` (ver `env.example`).

---

## Requisitos del VPS

- **SO**: Linux x86_64 (Ubuntu 22.04/24.04 LTS o Debian 12 recomendado).
- **RAM**: mínimo **2 GB** (el `docker compose build` de Next es pesado; 4 GB evita swaps).
- **Disco**: **10 GB** libres como mínimo (imágenes Docker + volúmenes SQLite creciendo).
- **Software**: Docker Engine **24+** y Docker Compose plugin v2 (`docker compose`).
- **Red**: IPv4 accesible; abre en el cortafuegos solo los puertos que vayas a usar (p. ej. `37891`, `37892`).
- **Opcional**: dominio + reverse proxy (Caddy/Nginx) en **443** apuntando a `127.0.0.1:37891` y, si quieres Gastro bajo el mismo dominio, rutas o subdominio — no va incluido aquí para no duplicar tu configuración actual.

### Comandos típicos (Ubuntu)

```bash
sudo apt update && sudo apt install -y ca-certificates curl
# Instalación Docker: https://docs.docker.com/engine/install/ubuntu/
sudo ufw allow OpenSSH
sudo ufw allow 37891/tcp comment 'clavo-next'
sudo ufw allow 37892/tcp comment 'clavo-gastro'
sudo ufw enable
```

---

## Qué incluye el stack

1. **web** (`restaurante/`): Next.js 16 en producción, Prisma + **SQLite** en volumen `clavo_prisma_sqlite` (`/data/clavo.db`). Al arrancar ejecuta `prisma migrate deploy`.
2. **gastro** (`restaurante/gastro-app/`): Flask + Gunicorn, **SQLite** en volumen `clavo_gastro_sqlite` (`/data/gastro.db`). Crea tablas al iniciar si faltan.

Las reservas web pueden delegarse en Gastro vía `GASTRO_RESERVAS_BASE_URL` (en Compose ya apunta a `http://gastro:37892`).

---

## Pasos de despliegue

Desde tu máquina o el VPS, con el repo clonado (esta carpeta es `Clavo/deploy/`):

```bash
cd deploy
cp env.example .env
nano .env   # AUTH_SECRET, GASTRO_SECRET_KEY, NEXT_PUBLIC_GASTRO_BASE_URL, ADMIN_PASSWORD_HASH
```

Importante:

- `NEXT_PUBLIC_GASTRO_BASE_URL` debe ser la URL **que el navegador** usará (ej. `http://203.0.113.10:37892`). Se **congela en el build** del cliente Next; si cambias dominio o IP, vuelve a ejecutar **`docker compose build web`**.
- En producción define **`ADMIN_PASSWORD_HASH`** y deja `ADMIN_PASSWORD` vacío.

Construir y levantar:

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f --tail=80 web
```

Prueba en el navegador:

- `http://TU_IP:37891` — home y carta.
- `http://TU_IP:37892/login` — panel Gastro (PIN según tu base Gastro).

### Datos iniciales (Prisma / empleados tablet)

Si necesitas semilla de desarrollo en la BD de Next:

```bash
docker compose exec web npx prisma db seed
```

(Revisa `restaurante/prisma/seed.ts` y variables `SEED_*` si existen.)

---

## Copias de seguridad (SQLite)

Los datos viven en volúmenes Docker. Listar:

```bash
docker volume ls | grep clavo
```

Copia en frío (con los contenedores parados o al menos sin escrituras activas):

```bash
docker compose stop
docker run --rm -v deploy_clavo_prisma_sqlite:/from -v "$(pwd)/backup":/to alpine \
  tar czf /to/clavo_prisma_$(date +%F).tgz -C /from .
docker run --rm -v deploy_clavo_gastro_sqlite:/from -v "$(pwd)/backup":/to alpine \
  tar czf /to/clavo_gastro_$(date +%F).tgz -C /from .
docker compose start
```

(Ajusta el nombre del volumen si tu carpeta de proyecto tiene otro prefijo; `docker volume inspect` muestra la ruta real.)

---

## Actualizar versión

La web pública **no se actualiza sola**: hay que **subir el código al VPS** (p. ej. `git push` desde tu PC y luego `git pull` en el servidor) y **reconstruir la imagen Docker** `web`. Si solo editas en local o en Cursor sin desplegar, `https://elclavo.gastromanager.es` seguirá sirviendo la imagen antigua.

```bash
cd /ruta/al/repo
git pull
cd deploy
docker compose build
docker compose up -d
```

Desde la raíz del repo en el VPS también puedes usar: **`bash deploy/vps-pull-rebuild.sh`** (equivale a `git pull` + `build web gastro` + `up -d`).

### Despliegue sin entrar al VPS (desde tu PC)

1. **`deploy/vps-remote-deploy.sh`** (Linux / macOS / Git Bash en Windows), tras `git push` al remoto que el VPS hace `pull`:

   ```bash
   export VPS_SSH=root@TU_IP
   export VPS_REPO_PATH=/root/Clavo   # opcional si el clon no está en ~/Clavo
   bash deploy/vps-remote-deploy.sh     # rama main
   bash deploy/vps-remote-deploy.sh master
   ```

2. **Windows (PowerShell)** con Git Bash en PATH: **`deploy/vps-remote-deploy.ps1`** (mismas variables `VPS_SSH`, opcional `VPS_REPO_PATH`).

3. **GitHub Actions** (push o manual): archivo **`.github/workflows/deploy-vps.yml`**.

   - **Manual:** en GitHub → *Actions* → *Deploy VPS* → *Run workflow* (elige rama).
   - **Automático en cada push a `main`/`master`:** activo por defecto (mismos secrets). Para pausar temporalmente los despliegues por push, variable **`VPS_DEPLOY_SKIP`** = `1` (*Settings* → *Variables* → *Actions*); el despliegue manual desde Actions sigue disponible.
   - **Secrets** (*Settings* → *Secrets* → *Actions*): `VPS_HOST`, `VPS_USER`, `VPS_SSH_KEY` (clave privada PEM/OpenSSH), `VPS_REPO_PATH` (ruta absoluta del clon en el servidor, p. ej. `/root/Clavo`). El SSH usa el puerto **22**; si necesitas otro, edita `port:` en el workflow.

   El VPS debe tener el repo clonado una vez (`git clone …`) y Docker funcionando como en [`SUBIR-VPS.md`](./SUBIR-VPS.md).

---

## HTTPS y un solo puerto 443

Cuando tengas Caddy/Nginx delante:

- Proxy `https://taberna.ejemplo.com` → `http://127.0.0.1:37891`.
- Para Gastro en el mismo dominio hace falta **otro host** (p. ej. `gastro.taberna.ejemplo.com`) → `http://127.0.0.1:37892`, y entonces **reconstruir** la web con `NEXT_PUBLIC_GASTRO_BASE_URL=https://gastro.taberna.ejemplo.com` (sin puerto si va por 443).

Configura `FLASK_SECURE_COOKIES=1` en gastro cuando todo el tráfico público sea HTTPS (añádelo al servicio `gastro` en `docker-compose.yml` cuando toque).

---

## Solución de problemas

| Síntoma | Qué revisar |
|---------|-------------|
| El sitio no cambia tras editar código | En el VPS: `git pull` en el repo, luego `cd deploy && docker compose build web && docker compose up -d`. Comprueba que el `git remote` del servidor apunta al mismo repositorio donde haces push. |
| Web 502 / no arranca | `docker compose logs web` — migraciones Prisma, `AUTH_SECRET` faltante. |
| Reservas no llegan a Gastro | `GASTRO_RESERVAS_BASE_URL` en `web` debe ser `http://gastro:37892`; Gastro arriba (`docker compose logs gastro`). |
| Enlaces del pie a Gastro mal | Rebuild de `web` con `NEXT_PUBLIC_GASTRO_BASE_URL` correcto. |
| Puerto en uso | Cambia `CLAVO_WEB_PUBLISH` / `CLAVO_GASTRO_PUBLISH` en `.env` y `docker compose up -d`. |

---

## Archivos de referencia

- `docker-compose.yml` — servicios y volúmenes.
- `restaurante/Dockerfile` y `restaurante/gastro-app/Dockerfile` — imágenes de producción (context = cada carpeta).
- `env.example` — plantilla de variables.
- `vps-pull-rebuild.sh` — en el VPS: pull + `docker compose build` + `up -d`.
- `vps-remote-deploy.sh` / `vps-remote-deploy.ps1` — desde tu PC: SSH + mismo flujo.
- `../.github/workflows/deploy-vps.yml` — despliegue desde GitHub Actions.
