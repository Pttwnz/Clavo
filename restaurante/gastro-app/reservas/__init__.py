"""Paquete de la aplicación de reservas (fábrica Flask y blueprints)."""
import os
from datetime import timedelta

# Antes de Flask/blueprints: en Windows a veces Pillow no carga (DLL bloqueada);
# ReportLab necesita un PIL importable. Ver reservas/pil_fix.py.
from . import pil_fix  # noqa: F401

from flask import Flask, url_for

from config import RESERVAS_ONLY, SECRET_KEY, SUGERENCIA_UNION_DESDE_PAX


def create_app():
    """Crea la instancia Flask, configura secretos y registra todos los blueprints."""
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    app = Flask(
        __name__,
        template_folder=os.path.join(root, "templates"),
        static_folder=os.path.join(root, "static"),
    )
    # Con debug=False (p. ej. `app.run(debug=False)`), Jinja por defecto cachea plantillas en
    # memoria: editar solo .html no se ve hasta reiniciar. Forzar recarga desde disco.
    app.config["TEMPLATES_AUTO_RELOAD"] = True
    app.secret_key = SECRET_KEY
    app.config["SUGERENCIA_UNION_DESDE_PAX"] = SUGERENCIA_UNION_DESDE_PAX
    app.config["RESERVAS_ONLY"] = RESERVAS_ONLY
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=16)
    if os.getenv("FLASK_SECURE_COOKIES", "").lower() in ("1", "true", "yes"):
        app.config["SESSION_COOKIE_SECURE"] = True

    from reservas.i18n import init_i18n

    init_i18n(app)

    @app.context_processor
    def inject_gastro_login_home():
        from config import MERGED_HOST_ROOT
        from flask import url_for

        def gastro_login_home_url(next_url: str = "") -> str:
            ep = "public.acceso_interno" if MERGED_HOST_ROOT else "public.inicio"
            if (next_url or "").strip():
                return url_for(ep, next=(next_url or "").strip())
            return url_for(ep)

        return {"gastro_login_home_url": gastro_login_home_url}

    @app.context_processor
    def inject_sugerencia_union_pax():
        return {"sugerencia_union_desde_pax": app.config["SUGERENCIA_UNION_DESDE_PAX"]}

    @app.context_processor
    def inject_reservas_only():
        return {"reservas_only": app.config.get("RESERVAS_ONLY", False)}

    @app.context_processor
    def inject_rbac():
        from reservas.rbac_session import puede, tiene_algun_modulo_backoffice

        return {"puede": puede, "nav_backoffice": tiene_algun_modulo_backoffice}

    @app.after_request
    def _security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        response.headers.setdefault("Permissions-Policy", "camera=(), microphone=(), geolocation=()")
        return response

    from reservas.blueprints.admin import bp as admin_bp
    from reservas.blueprints.api import bp as api_bp
    from reservas.blueprints.empleado import bp as empleado_bp
    from reservas.blueprints.public import bp as public_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(empleado_bp)
    app.register_blueprint(api_bp)

    from reservas.tablet_middleware import tablet_before_request

    app.before_request(tablet_before_request)

    @app.context_processor
    def inject_tablet_config_modo():
        """Opciones del modo tablet para plantillas (nav táctil, reservas…)."""
        from flask import session

        from models import get_db

        if not session.get("modo_tablet"):
            return {"tablet_cfg_modo": None}
        try:
            from reservas.tablet_config_schema import get_tablet_config

            db = get_db()
            cfg = get_tablet_config(db)
            db.close()
            return {"tablet_cfg_modo": cfg}
        except Exception:
            return {"tablet_cfg_modo": None}

    @app.context_processor
    def inject_copyright_year():
        from datetime import date

        return {"current_year": date.today().year}

    @app.context_processor
    def inject_branding():
        """Logo y colores de marca (config_empresa) para toda la interfaz."""
        try:
            from models import get_db
            from reservas.branding import build_branding_dict
            from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa

            db = get_db()
            ensure_config_empresa_table(db)
            cfg = get_config_empresa(db)
            db.close()
            b = build_branding_dict(cfg)
            rel = b.get("logo_relativo") or ""
            logo_url = url_for("static", filename=rel) if rel else None
            return {"branding": {**b, "logo_url": logo_url}}
        except Exception:
            return {
                "branding": {
                    "logo_relativo": "",
                    "color_primario": "#2563eb",
                    "color_acento": "#1d4ed8",
                    "nombre_mostrar": "GastroManager",
                    "primary_rgb": "37,99,235",
                    "logo_url": None,
                }
            }

    @app.context_processor
    def inject_admin_rrhh_pendientes():
        """Contador RRHH para admin (campana en la barra superior)."""
        from flask import session

        zeros = {
            "admin_rrhh_msg_pend": 0,
            "admin_rrhh_sol_pend": 0,
            "admin_rrhh_pend_total": 0,
        }
        from reservas.rbac_session import puede

        if app.config.get("RESERVAS_ONLY"):
            return zeros
        if not (
            (session.get("rol") == "admin" and session.get("admin_logueado"))
            or puede("mod.rrhh")
        ):
            return zeros
        try:
            from models import get_db
            from reservas.rrhh_peticiones_schema import contar_pendientes_admin, ensure_rrhh_peticiones_schema

            db = get_db()
            ensure_rrhh_peticiones_schema(db)
            n_msg, n_sol = contar_pendientes_admin(db)
            db.close()
            n_msg = n_msg or 0
            n_sol = n_sol or 0
            return {
                "admin_rrhh_msg_pend": n_msg,
                "admin_rrhh_sol_pend": n_sol,
                "admin_rrhh_pend_total": n_msg + n_sol,
            }
        except Exception:
            return zeros

    return app
