"""Restringe el modo tablet a reservas, fichaje y rutas públicas mínimas."""
from __future__ import annotations

from flask import flash, redirect, request, session, url_for

# Endpoints permitidos con sesión modo_tablet (resto → hub tablet).
TABLET_ENDPOINTS_ALLOWED = frozenset(
    {
        "public.logout",
        "public.login_cliente_redirect",
        "public.service_worker",
        "public.tablet_acceso",
        "public.tablet_inicio",
        "public.tablet_cierre_caja",
        # Permitimos entrar para poder redirigir con mensaje específico
        # (la revisión de solicitudes ya no se hace en tablet).
        "public.tablet_preregistro_gestion",
        "admin.reservas",
        "admin.crear",
        "admin.editar",
        "admin.actualizar",
        "admin.cambiar_estado",
        "admin.api_reserva_estado",
        "admin.api_walkin",
        "admin.api_asignar_mesa_reserva",
        "admin.api_sala_mesas_opciones",
        "admin.api_ocupacion_mesas",
        "admin.api_sugerencias_union_mesa",
        "admin.api_union_mesas_list",
        "admin.api_union_mesas_crear",
        "admin.api_union_mesas_borrar",
        "admin.reserva_autorizada",
        "admin.eliminar_reserva",
        "admin.fichaje",
        "admin.fichar",
        "admin.confirmar_fichaje",
        "admin.buscar_global",
        "static",
    }
)


def tablet_before_request():
    """Redirige a /tablet si el usuario en modo local intenta otra sección."""
    if not session.get("modo_tablet"):
        return None
    path = request.path or ""
    if path.startswith("/static"):
        return None
    ep = request.endpoint
    allowed = set(TABLET_ENDPOINTS_ALLOWED)
    try:
        from models import get_db

        db = get_db()
        from reservas.tablet_config_schema import tablet_endpoints_extra

        allowed |= tablet_endpoints_extra(db)
        db.close()
    except Exception:
        pass
    if ep in allowed or ep == "static":
        return None
    if ep in ("public.inicio", "public.acceso_interno"):
        return redirect(url_for("public.tablet_inicio"))
    flash(
        "En modo tablet del local solo están disponibles las secciones permitidas por configuración.",
        "warning",
    )
    return redirect(url_for("public.tablet_inicio"))
