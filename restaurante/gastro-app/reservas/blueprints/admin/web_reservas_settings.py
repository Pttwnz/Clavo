"""Configuración de reservas web públicas (franjas, cupo, email de confirmación)."""
from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.decorators import login_requerido, permiso_reservas
from reservas.salon_helpers import ensure_salon_tables, seed_salon_if_empty
from reservas.utils import hora_texto_a_minutos
from reservas.web_reservas_logic import suma_capacidad_aforo
from reservas.web_reservas_schema import (
    get_web_reserva_config,
    list_all_franjas_admin,
    replace_franjas_from_form,
    save_web_reserva_config,
)

from . import bp


def _minutos_desde_hhmm(s: str) -> int | None:
    return hora_texto_a_minutos((s or "").strip())


@bp.route("/configuracion_reservas_web", methods=["GET", "POST"])
@login_requerido
@permiso_reservas
def configuracion_reservas_web():
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)

    if request.method == "POST":
        save_web_reserva_config(db, request.form)
        dias = request.form.getlist("franja_dia")
        mis = request.form.getlist("franja_m_ini")
        mfs = request.form.getlist("franja_m_fin")
        labels = request.form.getlist("franja_etiqueta")
        pcts = request.form.getlist("franja_pct")
        activos = request.form.getlist("franja_activo")
        rows: list[dict] = []
        n = max(len(dias), len(mis), len(mfs), len(activos))
        for i in range(n):
            dia_raw = dias[i] if i < len(dias) else ""
            if not str(dia_raw).strip():
                continue
            try:
                dia = int(dia_raw)
            except (TypeError, ValueError):
                continue
            mi_s = mis[i] if i < len(mis) else ""
            mf_s = mfs[i] if i < len(mfs) else ""
            mi = _minutos_desde_hhmm(mi_s)
            mf = _minutos_desde_hhmm(mf_s)
            if mi is None or mf is None:
                continue
            pct_raw = pcts[i] if i < len(pcts) else ""
            pct_v = str(pct_raw).strip()
            act_raw = activos[i] if i < len(activos) else "1"
            rows.append(
                {
                    "dia_semana": dia,
                    "min_inicio": mi,
                    "min_fin": mf,
                    "etiqueta": labels[i] if i < len(labels) else "",
                    "pct_web": pct_v if pct_v else None,
                    "activo": str(act_raw).strip() in ("1", "on", "true", "yes", "si", "sí"),
                }
            )
        replace_franjas_from_form(db, rows)
        db.close()
        flash("Configuración de reservas web guardada.", "success")
        return redirect(url_for("admin.configuracion_reservas_web"))

    cfg = get_web_reserva_config(db)
    franjas = list_all_franjas_admin(db)
    aforo = suma_capacidad_aforo(db)
    db.close()

    dias_nombre = [
        (1, "Lunes"),
        (2, "Martes"),
        (3, "Miércoles"),
        (4, "Jueves"),
        (5, "Viernes"),
        (6, "Sábado"),
        (7, "Domingo"),
    ]
    return render_template(
        "configuracion_reservas_web.html",
        mostrar_nav=True,
        cfg=cfg,
        franjas=franjas,
        aforo=aforo,
        dias_nombre=dias_nombre,
    )
