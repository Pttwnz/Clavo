"""Registro de nuevos empleados (POST)."""
from flask import current_app, flash, redirect, request, session

from models import get_db
from reservas.db_helpers import columnas_tabla
from reservas.decorators import login_requerido, permiso_mod
from reservas.empleado_fotos import copiar_foto_perfil_a_empleado
from reservas.empleados_helpers import (
    datos_empleado_desde_form,
    dni_en_uso,
    fila_para_insert,
    normalizar_dni,
    pin_en_uso,
)
from reservas.empleados_schema import ensure_empleados_rrhh_columns
from reservas.preregistro_schema import obtener_preregistro

from .. import bp


def _borrador_serializable(data: dict) -> dict:
    """Guarda el intento de alta en sesión (todo excepto el PIN conflictivo se rellena de nuevo)."""
    out = {}
    for k, v in data.items():
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            out[k] = v
        elif v is None:
            out[k] = ""
        else:
            out[k] = str(v)
    return out


def _guardar_borrador_sesion(data: dict) -> None:
    br = _borrador_serializable(data)
    pid = request.form.get("preregistro_id", type=int)
    if pid:
        br["preregistro_id"] = str(pid)
    session["empleado_alta_borrador"] = br


@bp.route("/crear_empleado", methods=["POST"])
@login_requerido
@permiso_mod("mod.empleados")
def crear_empleado():
    """Alta de empleado con datos de RRHH."""
    db = get_db()
    ensure_empleados_rrhh_columns(db)

    data = datos_empleado_desde_form(request.form)

    if not data.get("nombre"):
        db.close()
        flash("Indica al menos el nombre del empleado.", "warning")
        return redirect("/empleados")

    if not data.get("pin"):
        db.close()
        flash("El PIN es obligatorio para el acceso al portal.", "warning")
        return redirect("/empleados")

    if pin_en_uso(db, str(data["pin"])):
        db.close()
        _guardar_borrador_sesion(data)
        session["empleado_alta_pin_error"] = True
        flash("Ese PIN ya está asignado a otro empleado. Elige otro PIN.", "danger")
        return redirect("/empleados#nuevo-empleado")

    dni_n = normalizar_dni(str(data.get("dni") or ""))
    if dni_n and dni_en_uso(db, dni_n):
        db.close()
        _guardar_borrador_sesion(data)
        session["empleado_alta_dni_error"] = True
        flash("Ya existe un empleado con ese DNI o NIE.", "danger")
        return redirect("/empleados#nuevo-empleado")

    cols, vals = fila_para_insert(db, data)
    if not cols:
        db.close()
        flash("No se pudo guardar: esquema de empleados incompleto.", "danger")
        return redirect("/empleados")

    placeholders = ", ".join("?" * len(cols))
    prereg_id = request.form.get("preregistro_id", type=int)
    try:
        cur = db.execute(
            f"INSERT INTO empleados ({', '.join(cols)}) VALUES ({placeholders})",
            vals,
        )
        db.commit()
        emp_id = int(cur.lastrowid)
        if prereg_id and emp_id and "foto_perfil" in columnas_tabla(db, "empleados"):
            pr = obtener_preregistro(db, prereg_id)
            rel = (pr.get("foto_perfil") or "").strip() if pr else ""
            if rel:
                nuevo = copiar_foto_perfil_a_empleado(current_app.static_folder, rel, emp_id)
                if nuevo:
                    db.execute(
                        "UPDATE empleados SET foto_perfil = ? WHERE id = ?",
                        (nuevo, emp_id),
                    )
                    db.commit()
        flash(f"Empleado «{data['nombre']}» dado de alta correctamente.", "success")
    except Exception as e:
        db.rollback()
        flash(f"No se pudo crear el empleado: {e}", "danger")
    finally:
        db.close()

    return redirect("/empleados")
