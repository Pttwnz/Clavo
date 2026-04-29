"""Configuración del PIN del modo tablet (local)."""
from flask import flash, redirect, render_template, request, url_for

from auth import hash_pin, verificar_pin
from models import get_db
from reservas.decorators import login_requerido, permiso_mod
from reservas.tablet_schema import ensure_tablet_schema

from . import bp


@bp.route("/configuracion_pin_tablet", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.servicio_tablet")
def configuracion_pin_tablet():
    """Establecer o cambiar el PIN usado en /tablet/acceso (distinto del panel si se desea)."""
    db = get_db()
    ensure_tablet_schema(db)
    row = db.execute(
        "SELECT id, pin_hash, pin_tablet_hash FROM admin ORDER BY id LIMIT 1"
    ).fetchone()
    if not row or not row["pin_hash"]:
        db.close()
        flash("No hay PIN de administrador configurado.", "danger")
        return redirect(url_for("admin.panel"))

    admin_id = row["id"]
    admin_hash = row["pin_hash"]
    tiene_tablet_distinto = bool(
        (row["pin_tablet_hash"] or "").strip()
        and row["pin_tablet_hash"] != row["pin_hash"]
    )

    if request.method == "POST":
        accion = (request.form.get("accion") or "").strip()
        pin_admin = (request.form.get("pin_admin") or "").strip()

        if not pin_admin or not verificar_pin(pin_admin, admin_hash):
            db.close()
            flash("El PIN de administrador no es correcto.", "danger")
            return redirect(url_for("admin.configuracion_pin_tablet"))

        if accion == "restablecer":
            db.execute(
                "UPDATE admin SET pin_tablet_hash = ? WHERE id = ?",
                (admin_hash, admin_id),
            )
            db.commit()
            db.close()
            flash(
                "PIN de tablet restablecido: coincide con el PIN de administrador.",
                "success",
            )
            return redirect(url_for("admin.configuracion_pin_tablet"))

        pin_a = (request.form.get("pin_tablet_nuevo") or "").strip()
        pin_b = (request.form.get("pin_tablet_confirmar") or "").strip()

        if len(pin_a) < 4:
            db.close()
            flash("El PIN tablet debe tener al menos 4 caracteres.", "warning")
            return redirect(url_for("admin.configuracion_pin_tablet"))
        if pin_a != pin_b:
            db.close()
            flash("Los PIN nuevos no coinciden.", "warning")
            return redirect(url_for("admin.configuracion_pin_tablet"))

        db.execute(
            "UPDATE admin SET pin_tablet_hash = ? WHERE id = ?",
            (hash_pin(pin_a), admin_id),
        )
        db.commit()
        db.close()
        flash("PIN de modo tablet actualizado correctamente.", "success")
        return redirect(url_for("admin.configuracion_pin_tablet"))

    db.close()
    return render_template(
        "configuracion_pin_tablet.html",
        mostrar_nav=True,
        tiene_tablet_distinto=tiene_tablet_distinto,
    )
