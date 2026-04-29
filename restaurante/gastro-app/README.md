# GastroManager (`reservas_app`)

Aplicación web **Flask** para restaurantes: **reservas**, **plano de salón** y **sala en vivo**, **modo tablet**, empleados y fichajes, inventario, proveedores, calendario laboral, cierre de caja y más. Los datos viven en **SQLite** (`database.db` por defecto).

---

## Qué hace el proyecto (resumen)

| Área | Descripción breve |
|------|-------------------|
| **Reservas** | Listado por día, crear/editar, estados, mesas y solapes de horario. |
| **Salón** | Editor de plano, mesas, **uniones de mesas** para grupos grandes. |
| **Sala en vivo** | Vista operativa del salón (mapa, reservas, walk-in). |
| **Tablet** | Flujo táctil con PIN y permisos configurables. |
| **RRHH / empleado** | Fichajes, peticiones, parte del empleado. |
| **Otros** | Escandallos, stock, proveedores, caja, clientes, i18n (ca / es / en). |

---

## Requisitos previos

- **Python 3.10+** (recomendado 3.11 o 3.12).
- **Git** (para clonar y actualizar).
- En producción: ver **[README_VPS.md](README_VPS.md)** (Gunicorn, opcional Nginx).

---

## Cómo clonar el repositorio

```bash
git clone git@github.com:Pttwnz/Gastro.git
cd Gastro
```

Si usas HTTPS en lugar de SSH, GitHub te mostrará la URL equivalente.

---

## Instalación en tu máquina (desarrollo)

**1.** Crear entorno virtual e instalar dependencias:

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install --upgrade pip
pip install -r requirements.txt
```

**2.** Variables de entorno: copia el ejemplo y edítalo.

```bash
cp .env.example .env
nano .env    # o el editor que uses
```

**3.** Arrancar la aplicación:

```bash
python3 app.py
```

Por defecto queda en **http://127.0.0.1:5050** (`app.py`; el 5000 suele estar ocupado por otra copia del proyecto). Con `PORT=5000` puedes forzar otro puerto. Abre el navegador e inicia sesión según tu base (PIN / admin).

**4.** (Opcional) Instalar dependencias de **tests**:

```bash
pip install -r requirements-dev.txt
pytest
```

---

## Variables importantes en `.env`

| Variable | Para qué sirve |
|----------|----------------|
| `SECRET_KEY` | Firma de sesiones; **obligatorio** usar un valor largo y aleatorio en producción. |
| `DATABASE` | Ruta al fichero SQLite. Puede ser relativa al proyecto o **absoluta** (útil en VPS). Si no se define, se usa `database.db` junto al código. |
| `FLASK_PRODUCTION` | Si es `1` / `true`, activa avisos de configuración segura (p. ej. `SECRET_KEY` débil). |
| `SUGERENCIA_UNION_DESDE_PAX` | A partir de cuántos comensales se considera el API de **sugerencias de unión de mesas** (por defecto **8**, máximo **20** en `config.py`). |
| `FLASK_SECURE_COOKIES` | Opcional: `1` para cookies solo por HTTPS detrás de proxy TLS. |

No subas nunca el fichero **`.env`** al repositorio (está en `.gitignore`). Sí puedes versionar **`.env.example`** como plantilla.

---

## Dependencias Python (`requirements.txt`)

Fichero pensado solo para **ejecución** (Flask, login, bcrypt, Pillow, ReportLab para PDFs, festivos oficiales con `holidays`, Gunicorn para producción). Las librerías que Flask y ReportLab necesitan a nivel interno las instala **pip** automáticamente.

Se eliminaron del listado principal paquetes que **ya no importa el código** (búsqueda/IA antigua, etc.) para evitar confusiones; si en el futuro vuelves a añadir integraciones, añade aquí su paquete con versión fijada.

Para desarrollo: **`requirements-dev.txt`** incluye `-r requirements.txt` y **pytest**.

---

## Estructura de carpetas (orientación)

```
Gastro/
├── app.py              # Arranque directo (desarrollo)
├── wsgi.py             # Entrada para Gunicorn / WSGI
├── config.py           # Rutas de BD, SECRET_KEY, opciones desde .env
├── models.py           # Conexión SQLite y esquema base
├── requirements.txt
├── requirements-dev.txt
├── reservas/           # Paquete principal: factory Flask, blueprints, utilidades
├── templates/          # Plantillas Jinja2
├── static/             # CSS, JS, iconos, PWA (manifest, service worker)
└── scripts/            # Scripts auxiliares (demo, reset de layout, …)
```

---

## Despliegue en servidor (VPS)

Pasos concretos (subir archivos, `deploy_vps.sh`, puertos, Nginx): **[README_VPS.md](README_VPS.md)**.

---

## Licencia y uso (propiedad intelectual)

Este proyecto **no es open source**: el código es **propietario**. Los
derechos de explotación los tiene el titular; el fichero **[LICENSE](LICENSE)**
resume la prohibición de copia, distribución o uso no autorizado.

**Importante (técnico + legal):**

- **Nadie puede “copiarlo desde GitHub”** si el repositorio está en
  **privado** y no das acceso a otras cuentas: GitHub no muestra el código
  al público.
- Si el repo fuera **público**, cualquiera podría **clonar** el código; la
  licencia y el derecho de autor sirven para **reclamar** ante usos ilegales,
  pero no bloquean técnicamente una copia (igual que un libro en una tienda).
- La **protección fuerte** en la práctica es: **repo privado**, accesos
  mínimos, no compartir ZIP del proyecto, y asesoría legal si el negocio lo
  justifica (contratos, registro de marca, etc.).
- Contenido generado o asistido con **IA**: según país y condiciones del
  servicio, puede afectar a quién se considera titular de ciertos fragmentos;
  conviene contrastar con un **abogado** si necesitas certeza jurídica para
  inversores o litigios.

No soy abogado; el fichero `LICENSE` es una base clara de “todos los derechos
reservados”, no asesoramiento legal.
