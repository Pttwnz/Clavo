"""Actualización de datos de empleados existentes."""
from flask import flash, redirect, request

from models import get_db
from reservas.decorators import login_requerido, permiso_mod
from reservas.empleados_helpers import (
    datos_empleado_desde_form,
    dni_en_uso,
    normalizar_dni,
    pin_en_uso,
    sets_para_update,
)
from reservas.empleados_schema import ensure_empleados_rrhh_columns

from .. import bp


@bp.route("/actualizar_empleado/<int:empleado_id>", methods=["POST"])
@login_requerido
@permiso_mod("mod.empleados")
def actualizar_empleado(empleado_id):
    """Actualiza ficha de empleado (mismos campos que el alta)."""
    db = get_db()
    ensure_empleados_rrhh_columns(db)

    row = db.execute("SELECT id FROM empleados WHERE id = ?", (empleado_id,)).fetchone()
    if not row:
        db.close()
        flash("Empleado no encontrado.", "warning")
        return redirect("/empleados")

    data = datos_empleado_desde_form(request.form)

    if not data.get("nombre"):
        db.close()
        flash("El nombre no puede quedar vacío.", "warning")
        return redirect("/empleados")

    pin_val = (data.get("pin") or "").strip()
    if not pin_val:
        data.pop("pin", None)
    else:
        data["pin"] = pin_val

    if pin_val and pin_en_uso(db, pin_val, excluir_id=empleado_id):
        db.close()
        flash("Ese PIN ya lo usa otro empleado. Los PIN no pueden repetirse.", "danger")
        return redirect("/empleados")

    dni_n = normalizar_dni(str(data.get("dni") or ""))
    if dni_n and dni_en_uso(db, dni_n, excluir_id=empleado_id):
        db.close()
        flash("Otro empleado ya usa ese DNI o NIE.", "danger")
        return redirect("/empleados")

    set_sql, vals = sets_para_update(db, data)
    if not set_sql:
        db.close()
        flash("No hay cambios que guardar.", "info")
        return redirect("/empleados")

    vals.append(empleado_id)
    try:
        db.execute(
            f"UPDATE empleados SET {set_sql} WHERE id = ?",
            vals,
        )
        db.commit()
        flash("Ficha del empleado actualizada.", "success")
    except Exception as e:
        db.rollback()
        flash(f"No se pudo guardar: {e}", "danger")
    finally:
        db.close()

    return redirect("/empleados")
