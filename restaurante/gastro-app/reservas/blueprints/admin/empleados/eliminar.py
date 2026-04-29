"""Baja de empleado y limpieza de fichajes."""
from flask import flash, redirect

from models import get_db
from reservas.decorators import admin_requerido, login_requerido

from .. import bp


@bp.route("/eliminar_empleado/<int:id>", methods=["POST"])
@login_requerido
@admin_requerido
def eliminar_empleado(id):
    """Elimina fichajes del empleado y el registro de empleado."""
    db = get_db()

    try:
        db.execute(
            "DELETE FROM fichajes WHERE empleado_id = ?",
            (id,),
        )

        db.execute(
            "DELETE FROM empleados WHERE id = ?",
            (id,),
        )

        db.commit()
        flash("Empleado eliminado del registro.", "success")

    except Exception as e:
        db.rollback()
        flash(f"No se pudo eliminar: {e}", "danger")

    finally:
        db.close()

    return redirect("/empleados")
