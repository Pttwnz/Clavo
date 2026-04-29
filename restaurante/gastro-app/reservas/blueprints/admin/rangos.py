"""Editor de rangos y permisos (solo PIN administrador)."""
from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.decorators import admin_requerido, login_requerido
from reservas.rbac_catalog import CODIGOS_EMP, CODIGOS_MOD, etiqueta
from reservas.rbac_schema import ensure_rbac_tables, guardar_permisos_rango, listar_rangos, permisos_de_rango

from . import bp


@bp.route("/rangos_permisos", methods=["GET", "POST"])
@login_requerido
@admin_requerido
def rangos_permisos():
    """Matriz de permisos por rango (solo administrador PIN)."""
    db = get_db()
    ensure_rbac_tables(db)
    rangos = listar_rangos(db, jerarquia_desc=True)

    if request.method == "POST":
        rid = request.form.get("rango_id", type=int)
        if not rid:
            db.close()
            flash("Rango no válido.", "warning")
            return redirect(url_for("admin.rangos_permisos"))
        codigos: set[str] = set()
        for key in request.form:
            if key.startswith("perm_"):
                codigos.add(key.replace("perm_", "", 1))
        guardar_permisos_rango(db, rid, codigos)
        db.close()
        flash("Permisos actualizados.", "success")
        return redirect(url_for("admin.rangos_permisos"))

    matrices = []
    for r in rangos:
        matrices.append(
            {
                "rango": r,
                "permisos": permisos_de_rango(db, int(r["id"])),
            }
        )
    db.close()

    return render_template(
        "rangos_permisos.html",
        mostrar_nav=True,
        rangos_matrices=matrices,
        codigos_mod=CODIGOS_MOD,
        codigos_emp=CODIGOS_EMP,
        etiqueta=etiqueta,
    )
