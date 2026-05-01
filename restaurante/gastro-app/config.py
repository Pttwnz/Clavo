import os
import warnings

from dotenv import load_dotenv

# Rutas relativas al directorio de este archivo, no al cwd del proceso (Gunicorn, scripts, etc.).
_ROOT = os.path.dirname(os.path.abspath(__file__))
# .env sin ruta solo mira el cwd; así falla si arrancas Flask desde `restaurante/` u otro sitio.
_REPO_ROOT = os.path.dirname(_ROOT)
_load_kw = {"encoding": "utf-8-sig"}
try:
    from pathlib import Path

    _here = Path(_ROOT).resolve()
    # De la raíz del FS hacia gastro-app: cada .env puede sobrescribir el anterior; el último gana.
    for _p in reversed(list(_here.parents)[:14]):
        _ef = _p / ".env"
        if _ef.is_file():
            load_dotenv(_ef, override=True, **_load_kw)
    load_dotenv(_here / ".env", override=True, **_load_kw)
except Exception:
    load_dotenv(os.path.join(_REPO_ROOT, ".env"), override=True, **_load_kw)
    load_dotenv(os.path.join(_ROOT, ".env"), override=True, **_load_kw)
load_dotenv(override=False, **_load_kw)
_db_env = (os.getenv("DATABASE") or "database.db").strip()
DATABASE = _db_env if os.path.isabs(_db_env) else os.path.join(_ROOT, _db_env)

SECRET_KEY = os.getenv("SECRET_KEY", "clave-secreta-restaurante-2024")

# A partir de este nº de comensales se puede activar el API de sugerencias de unión de mesas
# (si no hay mesa individual libre con aforo suficiente). Rango razonable 4–20.
try:
    SUGERENCIA_UNION_DESDE_PAX = max(1, min(20, int(os.getenv("SUGERENCIA_UNION_DESDE_PAX", "8"))))
except ValueError:
    SUGERENCIA_UNION_DESDE_PAX = 8

# Producción: definir FLASK_PRODUCTION=1 y un SECRET_KEY aleatori fort (p. ex. openssl rand -hex 32)
FLASK_PRODUCTION = os.getenv("FLASK_PRODUCTION", "").lower() in ("1", "true", "yes")
# 1 = la raíz del dominio la sirve otra app (p. ej. Next); Gastro usa /acceso-interno como hub de login.
MERGED_HOST_ROOT = os.getenv("FLASK_MERGED_HOST_ROOT", "").lower() in ("1", "true", "yes")
# Modo producto «solo reservas»: oculta RRHH, horarios, fichaje, inventario, etc. El panel admin queda en
# reservas + sala en vivo + clientes + ajustes de empresa/tablet y permisos. Por defecto activo (1).
RESERVAS_ONLY = os.getenv("RESERVAS_ONLY", "1").lower() in ("1", "true", "yes")

# URL pública del panel Gastro (misma que NEXT_PUBLIC_GASTRO_BASE_URL en Docker). Sirve para redirigir IP→DNS.
GASTRO_PUBLIC_BASE_URL = (
    (os.getenv("GASTRO_PUBLIC_BASE_URL") or os.getenv("NEXT_PUBLIC_GASTRO_BASE_URL") or "").strip().rstrip("/")
)

# Web Next (Prisma): estadísticas de visitas, carta editable. Mismo valor que CLAVO_INTERNAL_API_SECRET en Next.
# Puedes definir solo CLAVO_INTERNAL_API_SECRET en restaurante/.env (un solo secreto para ambos).
# NEXT_SITE_BASE_URL por defecto coincide con el dev de Next en el puerto del proyecto restaurante.
NEXT_SITE_BASE_URL = (os.getenv("NEXT_SITE_BASE_URL") or "http://127.0.0.1:31047").strip().rstrip("/")
def _env_strip_quotes(raw: str | None) -> str:
    if not raw:
        return ""
    v = raw.strip()
    if len(v) >= 2 and v[0] == v[-1] and v[0] in "\"'":
        return v[1:-1].strip()
    return v


_NEXT_SITE_SECRET = (os.getenv("NEXT_SITE_INTERNAL_SECRET") or "").strip()
_NEXT_SITE_SECRET = _NEXT_SITE_SECRET or (os.getenv("CLAVO_INTERNAL_API_SECRET") or "").strip()
# AUTH_SECRET antes que ADMIN_PASSWORD: en Docker Next suele tener solo ADMIN_PASSWORD_HASH (sin
# ADMIN_PASSWORD en claro); si Gastro enviara el PIN aquí, Next rechazaría el Bearer (401) en
# estadísticas / carta. CLAVO_INTERNAL_API_SECRET sigue teniendo prioridad si lo defines.
if not _NEXT_SITE_SECRET:
    _NEXT_SITE_SECRET = _env_strip_quotes(os.getenv("AUTH_SECRET"))
if not _NEXT_SITE_SECRET:
    _NEXT_SITE_SECRET = _env_strip_quotes(os.getenv("ADMIN_PASSWORD"))
NEXT_SITE_INTERNAL_SECRET = _NEXT_SITE_SECRET
if FLASK_PRODUCTION and NEXT_SITE_INTERNAL_SECRET:
    _dedicated = (
        (os.getenv("CLAVO_INTERNAL_API_SECRET") or "").strip()
        or (os.getenv("NEXT_SITE_INTERNAL_SECRET") or "").strip()
        or _env_strip_quotes(os.getenv("AUTH_SECRET"))
        or _env_strip_quotes(os.getenv("ADMIN_PASSWORD"))
    )
    if (
        not _dedicated
        and NEXT_SITE_INTERNAL_SECRET == _env_strip_quotes(os.getenv("AUTH_SECRET"))
    ):
        warnings.warn(
            "API interna Gastro→Next usa AUTH_SECRET. Para separar credenciales, define CLAVO_INTERNAL_API_SECRET.",
            UserWarning,
            stacklevel=1,
        )
_DEFAULT_WEAK = "clave-secreta-restaurante-2024"
if FLASK_PRODUCTION and (not SECRET_KEY or SECRET_KEY == _DEFAULT_WEAK):
    warnings.warn(
        "SECRET_KEY per defecte o buit en mode producció. Defineix SECRET_KEY al .env.",
        UserWarning,
        stacklevel=1,
    )
