# Subir el proyecto al VPS (primera vez)

Guía corta para tener **web (37891)** y **Gastro (37892)** en un Linux con Docker. Lo afinamos después en el servidor (dominio, HTTPS, SMTP, textos).

## 1. En el VPS (Ubuntu/Debian)

```bash
sudo apt update && sudo apt install -y git ca-certificates curl
# Docker: https://docs.docker.com/engine/install/ubuntu/
sudo usermod -aG docker "$USER"
# Cierra sesión y vuelve a entrar para que aplique el grupo `docker`.
```

Abre puertos si usas UFW:

```bash
sudo ufw allow OpenSSH
sudo ufw allow 37891/tcp comment 'clavo-next'
sudo ufw allow 37892/tcp comment 'clavo-gastro'
sudo ufw enable
```

## 2. Código en el servidor

**Opción A — Git (recomendado)**  
Sustituye la URL por tu repo (GitHub/GitLab/…):

```bash
cd ~
git clone https://github.com/TU_ORG/Clavo.git
cd Clavo/deploy
```

**Opción B — Sin Git**  
Desde tu PC, comprime la carpeta del proyecto (sin `node_modules` ni `.next`) y súbela con `scp`/WinSCP; en el VPS descomprime y entra en `.../Clavo/deploy`.

> El `docker-compose.yml` espera que existan `../restaurante` y `../restaurante/gastro-app` respecto a la carpeta `deploy/`.

## 3. Variables de entorno

```bash
cd ~/Clavo/deploy   # ajusta la ruta
cp env.example .env
nano .env
```

Rellena como mínimo:

| Variable | Ejemplo |
|----------|---------|
| `NEXT_PUBLIC_GASTRO_BASE_URL` | `http://203.0.113.10:37892` (IP o dominio **público** del VPS + puerto Gastro) |
| `AUTH_SECRET` | cadena larga aleatoria (`openssl rand -hex 32`) |
| `GASTRO_SECRET_KEY` | otra cadena larga (`openssl rand -hex 32`) |
| `ADMIN_PASSWORD_HASH` | hash bcrypt del PIN del `/admin` de Next (ver comentario en `env.example`) |

**Importante:** `NEXT_PUBLIC_*` se mete en el **build** del front. Si más adelante pones dominio o HTTPS en Gastro, tendrás que **`docker compose build web`** otra vez con el `.env` actualizado.

## 4. Arranque

```bash
docker compose build
docker compose up -d
docker compose ps
docker compose logs -f --tail=50 web
```

Prueba en el navegador:

- `http://TU_IP:37891` — web  
- `http://TU_IP:37892/login` — Gastro  

### Pasar de IP a DNS (script en el VPS)

No podemos editar tu servidor desde aquí; en el VPS, con DNS y proxy ya configurados:

```bash
cd ~/Clavo   # tu ruta al repo
git pull
bash deploy/apply-public-urls.sh 'https://app.gastromanager.es' \
  --auth-url 'https://clavo.gastromanager.es' \
  --legacy-host '178.104.143.67:37892' \
  --rebuild
```

Sustituye dominios e IP por los tuyos. Si `deploy/.env` ya tenía `NEXT_PUBLIC_GASTRO_BASE_URL=http://IP:37892`, puedes **omitir** `--legacy-host` y el script inferirá `GASTRO_LEGACY_HOSTS`. Ayuda: `python3 deploy/apply_public_urls.py --help`.

## 5. Afinar después (checklist)

- [ ] Panel Gastro: usuario admin, **Cierre de caja → SMTP** (o `CIERRE_CAJA_SMTP_PASSWORD` en `.env` + reinicio `docker compose up -d gastro`).  
- [ ] **Reservas web** en Gastro: URL pública base acorde a tu dominio/puerto (para el enlace del email de confirmación).  
- [ ] Next `/admin`: login con el hash que pusiste.  
- [ ] Copias de seguridad de volúmenes SQLite (ver `README.md` en esta carpeta).  
- [ ] Cuando tengas dominio + Nginx/Caddy en 443: proxy a `127.0.0.1:37891` / `37892` y **rebuild** de `web` con `NEXT_PUBLIC_GASTRO_BASE_URL` en `https://…`.

## 6. Despliegue desde tu PC o GitHub (sin SSH manual)

- **Script:** `bash deploy/vps-remote-deploy.sh` (variable `VPS_SSH=user@ip`). Ver comentarios al inicio del archivo.
- **Windows:** `deploy/vps-remote-deploy.ps1` si tienes Git Bash en el PATH.
- **CI:** `.github/workflows/deploy-vps.yml` — en GitHub, *Actions* → *Deploy VPS*; para auto-despliegue en cada push a `main`, variable de repositorio `VPS_DEPLOY_AUTO=1` y los secrets indicados en el propio workflow.

## 7. Script rápido (en el VPS)

Desde `deploy/`:

```bash
chmod +x vps-up.sh
./vps-up.sh
```

Solo construye y levanta; **no** edita `.env` por ti.
