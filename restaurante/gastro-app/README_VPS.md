# Despliegue rápido en VPS

## 1) Qué subir al VPS

Sube la carpeta del proyecto con estos elementos:

- `reservas/`
- `templates/`
- `static/`
- `app.py`
- `wsgi.py`
- `models.py`
- `config.py`
- `requirements.txt`
- `.env.example`
- `database.db` (tu base actual)
- `deploy_vps.sh`

No subas `.venv/`, `__pycache__/`, `.pytest_cache/`.

## 2) Instalar y arrancar en 1 comando

En el VPS:

```bash
cd /ruta/de/tu/proyecto
chmod +x deploy_vps.sh
./deploy_vps.sh
```

La app quedará escuchando en `:8000` con Gunicorn.

## 3) (Opcional recomendado) Nginx

Config mínima de servidor:

```nginx
server {
    listen 80;
    server_name TU_DOMINIO_O_IP;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Luego:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

## 4) Notas importantes

- Edita `.env` y define un `SECRET_KEY` fuerte.
- `database.db` viaja con los datos actuales de tu sistema.
- Si cambias código, vuelve a subir y reinicia gunicorn:

```bash
pkill -f "gunicorn.*wsgi:app"
nohup .venv/bin/gunicorn -w 3 -b 0.0.0.0:8000 wsgi:app > gunicorn.log 2>&1 &
```
