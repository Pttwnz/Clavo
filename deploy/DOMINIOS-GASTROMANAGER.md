# Dominios: `clavo` = web Next · `app` = Gastro

Objetivo:

| Dominio | Qué sirve |
|---------|-----------|
| **https://clavo.gastromanager.es** | Web pública Next (taberna, carta, reserva proxy, `/admin`) |
| **https://app.gastromanager.es** | Gastro (Flask): panel, tablet, `/api/web/reservas`, confirmación de reservas por email |

Antes Gastro vivía en `clavo.gastromanager.es`; ahora **Gastro pasa a `app`** y **la web nueva ocupa `clavo`**.

---

## 1. DNS

En el panel DNS de `gastromanager.es`:

- **A** (o **CNAME**) `clavo` → IP del VPS (la misma que ya usabas).
- **A** (o **CNAME**) `app` → **la misma IP** (Nginx/Caddy elige el sitio por `Host`).

Espera propagación (minutos–horas).

---

## 2. Proxy inverso (Nginx) en el VPS

Dos `server` en **443**, cada uno con su `server_name` y certificado (Let's Encrypt: `certbot certonly --nginx -d clavo.gastromanager.es -d app.gastromanager.es` o dos certs).

Puertos internos Docker (por defecto): Next **37891**, Gastro **37892**.

Cabeceras típicas:

```nginx
proxy_set_header Host $host;
proxy_set_header X-Real-IP $remote_addr;
proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
proxy_set_header X-Forwarded-Proto $scheme;
```

- `clavo.gastromanager.es` → `http://127.0.0.1:37891`
- `app.gastromanager.es` → `http://127.0.0.1:37892`

Ejemplo completo: **`nginx-snippet.example.conf`** en esta carpeta (bloques listos para copiar y ajustar rutas de certificados).

---

## 3. Docker / `.env` en `deploy/.env`

Tras tener HTTPS en ambos hosts:

```env
# URL pública de Gastro (enlaces en el navegador: pie, tablet, login panel)
NEXT_PUBLIC_GASTRO_BASE_URL=https://app.gastromanager.es

# URL pública de la web Next (Auth.js / cookies)
AUTH_URL=https://clavo.gastromanager.es
```

Luego **reconstruir solo la web** (el `NEXT_PUBLIC_*` va en el build):

```bash
cd /ruta/Clavo/deploy
docker compose build web
docker compose up -d web
```

En el mismo `.env` puedes activar cookies seguras en Gastro:

```env
FLASK_SECURE_COOKIES=1
```

(y `docker compose up -d gastro` o `docker compose up -d`).

---

## 4. Panel Gastro (datos en BD)

1. **Panel → Configuración reservas web**  
   Campo **«URL pública base»** (`public_base_url`):  
   `https://app.gastromanager.es`  

   Así los enlaces de confirmación por email apuntan a **app**, no a clavo.

2. Si algo seguía enlazando a `https://clavo.gastromanager.es/login`, cámbialo a **`https://app.gastromanager.es/login`**.

---

## 5. Comprobar

- Abrir **https://clavo.gastromanager.es** → home taberna.  
- Abrir **https://app.gastromanager.es/login** → login Gastro.  
- Desde la web, enlace «Acceso / panel» → debe ir a **app**.  
- Hacer una reserva de prueba con email → el enlace debe ser bajo **app**.

---

## 6. Quitar el viejo uso de `clavo` para Gastro

Cuando Nginx ya enruta **solo** Next a `clavo`, el tráfico antiguo a Gastro en ese host deja de aplicar. Asegúrate de que **no** quede otro `server` con `server_name clavo.gastromanager.es` apuntando al puerto de Gastro.
