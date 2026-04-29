"""Resumen de jornada y vacaciones (referencia) para todos los empleados — vista administración."""
from __future__ import annotations

from flask import render_template

from models import get_db
from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.decorators import login_requerido, permiso_mod
from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
from reservas.vacaciones_fichaje import ratio_vacacion_desde_config, resumen_jornada_vacaciones

from . import bp


def _nombre_empleado_dict(e: dict) -> str:
    n = (e.get("nombre") or "").strip()
    if e.get("apellido"):
        n = f"{n} {(e.get('apellido') or '').strip()}".strip()
    return n or "—"


@bp.route("/vacaciones_jornada")
@login_requerido
@permiso_mod("mod.vacaciones")
def vacaciones_jornada_resumen():
    """Tabla orientativa: horas fichadas, vacaciones referencia y trimestres por contrato."""
    db = get_db()
    ensure_config_empresa_table(db)
    cfg = get_config_empresa(db)
    ratio_global = ratio_vacacion_desde_config(cfg)

    filas = []
    if tabla_existe(db, "empleados"):
        cols = columnas_tabla(db, "empleados")
        q = "SELECT id, nombre, horas_contrato, fecha_alta"
        if "apellido" in cols:
            q += ", apellido"
        else:
            q += ", NULL AS apellido"
        if "activo" in cols:
            q += " FROM empleados WHERE activo = 1 ORDER BY nombre, apellido"
        else:
            q += " FROM empleados ORDER BY nombre"

        for row in db.execute(q).fetchall():
            e = dict(row)
            jd = resumen_jornada_vacaciones(
                db,
                int(e["id"]),
                cfg,
                e.get("fecha_alta"),
                e.get("horas_contrato"),
            )
            filas.append(
                {
                    "id": e["id"],
                    "nombre": _nombre_empleado_dict(e),
                    "jornada": jd,
                }
            )

    db.close()

    return render_template(
        "admin_vacaciones_jornada.html",
        mostrar_nav=True,
        filas=filas,
        config_empresa=cfg,
        ratio_global=ratio_global,
    )
