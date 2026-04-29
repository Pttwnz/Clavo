"""Pantalla de administración: opciones del modo tablet (además del PIN)."""
import json

from flask import current_app, flash, redirect, render_template, request, url_for

from models import get_db
from reservas.decorators import login_requerido, permiso_mod
from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

from . import bp


@bp.route("/configuracion_tablet", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.servicio_tablet")
def configuracion_tablet():
    """Opciones que aplican a quien entra con la sesión modo tablet en el local."""
    db = get_db()
    ensure_tablet_config(db)

    if request.method == "POST":
        cfg_existing = get_tablet_config(db)
        vis = 1 if request.form.get("permitir_visualizar_sala") else 0
        todas = 1 if request.form.get("permitir_ver_todas_reservas") else 0

        # En RESERVAS_ONLY el formulario no envía módulos extra ni propinas: no pisar la BD.
        if current_app.config.get("RESERVAS_ONLY", False):
            equipo = cfg_existing["permitir_ver_equipo_turno"]
            cierre = cfg_existing["permitir_cierre_caja"]
            propinas = cfg_existing["permitir_propinas"]
            prereg = cfg_existing["permitir_preregistro"]
            pv = cfg_existing["propinas_periodo_vista"]
            md = cfg_existing["propinas_modo_defecto"]
            ag = cfg_existing["propinas_agrupacion"]
            fh = cfg_existing["propinas_franja_horas"]
            pfm = cfg_existing["propinas_franja_modo"]
            manual_json = (cfg_existing.get("propinas_franjas_manual_json") or "").strip()
        else:
            equipo = 1 if request.form.get("permitir_ver_equipo_turno") else 0
            cierre = 1 if request.form.get("permitir_cierre_caja") else 0
            propinas = 1 if request.form.get("permitir_propinas") else 0
            prereg = 1 if request.form.get("permitir_preregistro") else 0
            pv = (request.form.get("propinas_periodo_vista") or "dia").strip().lower()
            if pv not in ("dia", "semana", "mes"):
                pv = "dia"
            md = (request.form.get("propinas_modo_defecto") or "igual").strip().lower()
            if md not in ("igual", "horas"):
                md = "igual"
            ag = (request.form.get("propinas_agrupacion") or "dia").strip().lower()
            if ag not in ("dia", "franja"):
                ag = "dia"
            try:
                fh = int(request.form.get("propinas_franja_horas") or 8)
            except (TypeError, ValueError):
                fh = 8
            if fh not in (4, 6, 8, 12) or (24 % fh != 0):
                fh = 8
            from reservas.propinas_schema import franjas_manual_desde_texto

            pfm = (request.form.get("propinas_franja_modo") or "auto").strip().lower()
            if pfm not in ("auto", "manual"):
                pfm = "auto"
            manual_json = ""
            if ag == "dia":
                pfm = "auto"
                manual_json = ""
            elif pfm == "manual":
                txt = (request.form.get("propinas_franjas_manual_texto") or "").strip()
                lst, err = franjas_manual_desde_texto(txt)
                if err:
                    db.close()
                    flash(err, "danger")
                    return redirect(url_for("admin.configuracion_tablet"))
                if not lst:
                    db.close()
                    flash("Indica al menos una franja en modo personalizado.", "danger")
                    return redirect(url_for("admin.configuracion_tablet"))
                manual_json = json.dumps([{"inicio": x["inicio"], "fin": x["fin"]} for x in lst])
            else:
                manual_json = ""
        msg = (request.form.get("mensaje_inicio") or "").strip()
        db.execute(
            """
            UPDATE config_tablet SET
                permitir_visualizar_sala = ?,
                permitir_ver_todas_reservas = ?,
                permitir_ver_equipo_turno = ?,
                permitir_cierre_caja = ?,
                permitir_propinas = ?,
                permitir_preregistro = ?,
                propinas_periodo_vista = ?,
                propinas_modo_defecto = ?,
                propinas_agrupacion = ?,
                propinas_franja_horas = ?,
                propinas_franja_modo = ?,
                propinas_franjas_manual_json = ?,
                mensaje_inicio = ?
            WHERE id = 1
            """,
            (vis, todas, equipo, cierre, propinas, prereg, pv, md, ag, fh, pfm, manual_json or None, msg or None),
        )
        db.commit()
        db.close()
        flash("Opciones del modo tablet guardadas.", "success")
        return redirect(url_for("admin.configuracion_tablet"))

    cfg = get_tablet_config(db)
    db.close()
    return render_template(
        "configuracion_tablet.html",
        mostrar_nav=True,
        cfg=cfg,
    )
