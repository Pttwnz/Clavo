"""Ruta histórica /chat: desactivada (sin asistente conversacional)."""
from flask import flash, redirect, session, url_for

from reservas.decorators import login_requerido, permiso_mod
from reservas.nav_urls import public_entry_url

from . import bp


@bp.route("/chat", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.panel")
def chat():
    """El chat libre del panel está desactivado."""
    flash(
        "El chat del panel de administración está desactivado. "
        "Los mensajes a RRHH desde el portal del empleado los revisa dirección en la bandeja de peticiones.",
        "info",
    )
    session.pop("mensajes_chat", None)
    if session.get("rol") == "admin":
        return redirect(url_for("admin.panel"))
    if session.get("empleado_id") is not None:
        return redirect(url_for("empleado.panel_empleado"))
    if session.get("modo_tablet"):
        return redirect(url_for("public.tablet_inicio"))
    return redirect(public_entry_url())
