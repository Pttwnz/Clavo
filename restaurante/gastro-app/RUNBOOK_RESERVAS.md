# Gastro Reservas (sin fichaje) - Runbook local

Este módulo reemplaza el flujo de reservas anterior con la app Flask de `Gastro`,
configurada en modo **solo reservas** (sin fichaje).

## Ubicación

- App Flask: `e:\Clavo\restaurante\gastro-app`
- Base de datos Flask: `e:\Clavo\restaurante\gastro-app\database.db`
- Base origen (Next/Prisma) para migración: `e:\Clavo\restaurante\dev.db`

## 1) Instalación (solo primera vez)

```powershell
cd "e:\Clavo\restaurante\gastro-app"
python -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## 2) Migrar datos mínimos desde la app anterior

```powershell
cd "e:\Clavo\restaurante\gastro-app"
.\.venv\Scripts\python scripts\migrate_from_next_sqlite.py --source "e:\Clavo\restaurante\dev.db"
```

Migra:
- mesas
- reservas
- clientes (vinculados por teléfono)
- empleados y PIN tablet/admin

## 3) PIN demo para pruebas

```powershell
cd "e:\Clavo\restaurante\gastro-app"
.\.venv\Scripts\python scripts\set_demo_pins.py --pin 1234
```

## 4) Arranque local

```powershell
cd "e:\Clavo\restaurante\gastro-app"
.\.venv\Scripts\python app.py
```

En consola debe aparecer una línea `[gastro-app Clavo/resaurante] ... root=...\restaurante\gastro-app`. Si no coincide esa ruta, no estás ejecutando esta copia.

URL (puerto por defecto **5050**; otra app antigua suele quedarse en **5000**, p. ej. `gastro-source`):

- `http://127.0.0.1:5050`

Para usar el 5000 tras cerrar el proceso viejo: `set PORT=5000` (PowerShell: `$env:PORT='5000'`) y vuelve a lanzar `app.py`.

## 5) Accesos de prueba

- Admin (PIN): entrar por `/` y usar **PIN `1234`** en "verificar admin".
- Tablet: `/tablet/acceso` con **PIN `1234`**.

## 6) Qué quedó desactivado (modo reservas-only)

Con `RESERVAS_ONLY=1` la app es **solo módulo de reservas** (más sala en vivo, editor de salón, clientes y ajustes mínimos: empresa, tablet, permisos). El resto de rutas admin devuelve 404; el portal de empleado redirige a `/reservas`; tablet no sirve cierre de caja, equipo, propinas ni preregistro.

- Fichaje, horarios, RRHH, inventario, escandallo, proveedores, calendario interno, chat, cierre de caja: no registrados o bloqueados.
- Pantalla inicial: sin acceso «empleado» por PIN (solo admin y tablet del local).
- Parámetros de reservas «web» previstos en un editor admin dedicado (pendiente de producto).

Variable usada:
- `RESERVAS_ONLY=1` en `.env` (por defecto en `config.py`). Pon `RESERVAS_ONLY=0` para el Gastro completo.

## 7) Smoke test rápido

```powershell
cd "e:\Clavo\restaurante\gastro-app"
.\.venv\Scripts\python -c "from reservas import create_app; app=create_app(); c=app.test_client(); print('admin', c.post('/verificar_admin', data={'pin':'1234'}).status_code); print('panel', c.get('/panel').status_code); print('reservas', c.get('/reservas').status_code); c2=app.test_client(); print('tablet', c2.post('/tablet/acceso', data={'pin':'1234'}).status_code)"
```

Esperado: redirecciones/200 en login y 200 en `/panel` y `/reservas`.
