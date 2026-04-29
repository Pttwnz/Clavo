"""Decoradores de autorización por sesión (admin y empleado)."""
from functools import wraps

from flask import flash, jsonify, redirect, request, session, url_for

from reservas.nav_urls import public_entry_url


def login_requerido(f):
    """Exige administrador, empleado o modo tablet (local); si no, redirige a la raíz."""

    @wraps(f)
    def decorador(*args, **kwargs):
        if (
            session.get("admin_logueado")
            or session.get("empleado_id") is not None
            or session.get("modo_tablet")
        ):
            return f(*args, **kwargs)
        return redirect(public_entry_url(next=request.path))

    return decorador


def empleado_requerido(f):
    """Exige `empleado_id` en sesión; si no, redirige al login de empleado."""

    @wraps(f)
    def decorador(*args, **kwargs):
        if "empleado_id" not in session:
            return redirect("/login_empleado")
        return f(*args, **kwargs)

    return decorador


def admin_requerido(f):
    """Exige rol `admin` (PIN) en sesión; si no, redirige al panel de empleado."""

    @wraps(f)
    def decorador(*args, **kwargs):
        if session.get("rol") != "admin":
            return redirect("/panel_empleado")
        return f(*args, **kwargs)

    return decorador


def permiso_mod(codigo: str):
    """
    Admin (PIN) o empleado cuyo rango incluye `codigo` (p.ej. mod.panel).
    No aplica en modo tablet (salvo admin explícito).
    """

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from reservas.rbac_session import puede

            if not (
                session.get("admin_logueado")
                or session.get("empleado_id") is not None
            ):
                return redirect(public_entry_url(next=request.path))
            if session.get("modo_tablet") and not session.get("admin_logueado"):
                flash("Esta sección no está disponible en el modo tablet del local.", "warning")
                return redirect(url_for("public.tablet_inicio"))
            if session.get("admin_logueado") and session.get("rol") == "admin":
                return f(*args, **kwargs)
            if session.get("empleado_id") and puede(codigo):
                return f(*args, **kwargs)
            flash("No tienes permiso para acceder a esta sección.", "warning")
            return redirect("/panel_empleado")

        return wrapped

    return decorator


def sesion_puede_gestionar_reservas() -> bool:
    """Misma regla que @permiso_reservas (tablet / admin PIN / mod.servicio / emp.reservas)."""
    from reservas.rbac_session import puede

    if session.get("modo_tablet"):
        return True
    if not (
        session.get("admin_logueado")
        or session.get("empleado_id") is not None
    ):
        return False
    if session.get("admin_logueado") and session.get("rol") == "admin":
        return True
    if puede("mod.servicio"):
        return True
    if session.get("empleado_id") and puede("emp.reservas"):
        return True
    return False


def permiso_reservas(f):
    """Reservas: tablet, admin, mod.servicio o portal emp.reservas."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        if sesion_puede_gestionar_reservas():
            return f(*args, **kwargs)
        if not (
            session.get("admin_logueado")
            or session.get("empleado_id") is not None
        ):
            return redirect(public_entry_url())
        flash("No tienes permiso para gestionar reservas.", "warning")
        return redirect("/panel_empleado")

    return wrapped


def permiso_union_mesas_sala(f):
    """
    Crear/listar/borrar uniones de mesas desde Sala en vivo.
    Misma idea que la gestión de sala en vivo: tablet, admin PIN, mod.servicio,
    mod.salon o emp.reservas. Respuestas JSON (sin redirecciones HTML) para fetch.
    """

    @wraps(f)
    def wrapped(*args, **kwargs):
        from reservas.rbac_session import puede

        if session.get("modo_tablet"):
            return f(*args, **kwargs)
        if not (
            session.get("admin_logueado")
            or session.get("empleado_id") is not None
        ):
            return jsonify({"ok": False, "error": "unauthorized"}), 401
        if session.get("admin_logueado") and session.get("rol") == "admin":
            return f(*args, **kwargs)
        if puede("mod.servicio"):
            return f(*args, **kwargs)
        if session.get("empleado_id") and (
            puede("emp.reservas") or puede("mod.salon")
        ):
            return f(*args, **kwargs)
        return jsonify({"ok": False, "error": "forbidden"}), 403

    return wrapped


def permiso_reservas_api(f):
    """Igual que `permiso_reservas`, pero respuestas JSON (sin redirect) para peticiones fetch."""

    @wraps(f)
    def wrapped(*args, **kwargs):
        from reservas.rbac_session import puede

        if session.get("modo_tablet"):
            return f(*args, **kwargs)
        if not (
            session.get("admin_logueado")
            or session.get("empleado_id") is not None
        ):
            return jsonify({"error": "unauthorized"}), 401
        if session.get("admin_logueado") and session.get("rol") == "admin":
            return f(*args, **kwargs)
        if puede("mod.servicio"):
            return f(*args, **kwargs)
        if session.get("empleado_id") and puede("emp.reservas"):
            return f(*args, **kwargs)
        return jsonify({"error": "forbidden"}), 403

    return wrapped


def empleado_permiso(codigo: str):
    """Portal empleado: exige sesión de empleado (no admin) y permiso del rango."""

    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            from reservas.rbac_session import puede

            if session.get("empleado_id") is None:
                return redirect(url_for("public.login_empleado"))
            if not puede(codigo):
                flash("Tu rango no incluye acceso a esta sección.", "warning")
                return redirect("/panel_empleado")
            return f(*args, **kwargs)

        return wrapped

    return decorator
