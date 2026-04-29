"""Blueprint de administración: rutas divididas por dominio en submódulos."""
from flask import Blueprint, abort, request
from config import RESERVAS_ONLY

bp = Blueprint("admin", __name__)

from . import chat  # noqa: E402, F401
from . import calendario  # noqa: E402, F401
from . import clientes  # noqa: E402, F401
from . import cierre_caja  # noqa: E402, F401
from . import dashboard  # noqa: E402, F401
from . import empleados  # noqa: E402, F401
from . import escandallos  # noqa: E402, F401
if not RESERVAS_ONLY:
    from . import horarios  # noqa: E402, F401
from . import proveedores  # noqa: E402, F401
from . import reservas  # noqa: E402, F401
from . import web_reservas_settings  # noqa: E402, F401
from . import rrhh_peticiones  # noqa: E402, F401
from . import salon  # noqa: E402, F401
from . import stock  # noqa: E402, F401
from . import tablet_pin  # noqa: E402, F401
from . import tablet_settings  # noqa: E402, F401
from . import web_clavo_next  # noqa: E402, F401
from . import rangos  # noqa: E402, F401

if not RESERVAS_ONLY:
    from . import fichajes  # noqa: E402, F401
    from . import vacaciones_jornada  # noqa: E402, F401

if RESERVAS_ONLY:
    from reservas.admin_reservas_only_paths import admin_path_allowed_reservas_only

    @bp.before_request
    def _admin_reservas_only_gate():
        if admin_path_allowed_reservas_only(request.path or ""):
            return None
        abort(404)
