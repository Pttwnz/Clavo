"""Vista de listado de empleados."""
import json

from flask import render_template, request, session

from models import get_db
from reservas.db_helpers import columnas_tabla
from reservas.decorators import login_requerido, permiso_mod
from reservas.empleados_schema import ensure_empleados_rrhh_columns
from reservas.preregistro_schema import ensure_preregistro_tables, obtener_preregistro
from reservas.rbac_schema import ensure_rbac_tables, listar_rangos

from .. import bp

PUESTOS_SUGERIDOS = (
    "Camarero/a",
    "Ayudante de sala",
    "Cocinero/a",
    "Ayudante de cocina",
    "Jefe/a de sala",
    "Jefe/a de cocina",
    "Encargado/a",
    "Sommelier",
    "Recepción",
    "Administración",
    "Gerencia",
    "Limpieza",
    "Seguridad",
    "Otro",
)

DEPARTAMENTOS_SUGERIDOS = (
    "Sala",
    "Barra",
    "Cocina",
    "Almacén",
    "Administración",
    "Dirección",
)


@bp.route("/empleados")
@login_requerido
@permiso_mod("mod.empleados")
def empleados():
    """Listado de empleados con datos para la vista enriquecida."""
    db = get_db()
    ensure_empleados_rrhh_columns(db)
    ensure_rbac_tables(db)
    rangos_list = listar_rangos(db)

    cols = columnas_tabla(db, "empleados")
    if "apellido" in cols:
        order_sql = "COALESCE(apellido, '') COLLATE NOCASE, nombre COLLATE NOCASE"
    else:
        order_sql = "nombre COLLATE NOCASE"

    rows = db.execute(f"SELECT * FROM empleados ORDER BY {order_sql}").fetchall()

    empleados_list = [dict(r) for r in rows]

    total = len(empleados_list)
    activos = sum(1 for e in empleados_list if int(e.get("activo") or 1) == 1)

    empleados_json = json.dumps(empleados_list, ensure_ascii=False)

    prereg_fill = None
    pid = request.args.get("preregistro_id", type=int)
    if pid:
        ensure_preregistro_tables(db)
        pr = obtener_preregistro(db, pid)
        if pr:
            try:
                rid = int(pr.get("rango_id") or 1)
            except (TypeError, ValueError):
                rid = 1
            if rid < 1:
                rid = 1
            prereg_fill = {
                "preregistro_id": str(pid),
                "nombre": pr.get("nombre") or "",
                "apellido": pr.get("apellido") or "",
                "dni": pr.get("dni") or "",
                "telefono": pr.get("telefono") or "",
                "email": pr.get("email") or "",
                "puesto": pr.get("puesto") or "",
                "departamento": pr.get("departamento") or "",
                "fecha_nacimiento": pr.get("fecha_nacimiento") or "",
                "tipo_contrato": pr.get("tipo_contrato") or "Indefinido",
                "fecha_alta": pr.get("fecha_alta") or "",
                "horas_contrato": pr.get("horas_contrato") or "40",
                "numero_ss": pr.get("numero_ss") or "",
                "observaciones": pr.get("observaciones") or "",
                "rango_id": rid,
                "foto_perfil": pr.get("foto_perfil") or "",
            }

    db.close()

    alta_borrador = session.pop("empleado_alta_borrador", None)
    alta_pin_error = session.pop("empleado_alta_pin_error", False)
    alta_dni_error = session.pop("empleado_alta_dni_error", False)
    if not alta_borrador and prereg_fill:
        alta_borrador = prereg_fill

    return render_template(
        "empleados.html",
        mostrar_nav=True,
        empleados=empleados_list,
        empleados_json=empleados_json,
        total_empleados=total,
        empleados_activos=activos,
        puestos_sugeridos=PUESTOS_SUGERIDOS,
        departamentos_sugeridos=DEPARTAMENTOS_SUGERIDOS,
        alta_borrador=alta_borrador,
        alta_pin_error=alta_pin_error,
        alta_dni_error=alta_dni_error,
        rangos=rangos_list,
    )
