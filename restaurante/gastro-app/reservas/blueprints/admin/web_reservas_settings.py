"""Configuración de reservas web públicas (franjas, cupo, email de confirmación)."""
from __future__ import annotations

import re
from datetime import timedelta
from urllib.parse import quote

from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.cierre_caja_mail import enviar_correo_externo, smtp_config_valida
from reservas.cierre_caja_schema import get_config_cierre_caja
from reservas.decorators import login_requerido, permiso_reservas
from reservas.next_site_http import next_site_base_url
from reservas.salon_helpers import ensure_salon_tables, seed_salon_if_empty
from reservas.utils import ahora_madrid, hora_texto_a_minutos
from reservas.web_reservas_logic import slots_disponibles_payload, suma_capacidad_aforo
from reservas.web_reservas_schema import (
    ensure_web_reservas_tables,
    franjas_plantilla_comida_cena_semana,
    franjas_plantilla_desde_rangos_empresa,
    franjas_plantilla_solo_cena_semana,
    get_web_reserva_config,
    list_all_franjas_admin,
    list_franjas,
    replace_franjas_from_form,
    save_web_reserva_config,
)

from . import bp


def _minutos_desde_hhmm(s: str) -> int | None:
    return hora_texto_a_minutos((s or "").strip())


def _franja_rows_solapan(rows: list[dict]) -> bool:
    """True si dos franjas activas del mismo día comparten algún minuto."""
    activas_por_dia: dict[int, list[tuple[int, int]]] = {}
    for r in rows:
        if not r.get("activo", True):
            continue
        d = int(r["dia_semana"])
        activas_por_dia.setdefault(d, []).append((int(r["min_inicio"]), int(r["min_fin"])))
    for ranges in activas_por_dia.values():
        ranges.sort(key=lambda x: (x[0], x[1]))
        for i in range(len(ranges) - 1):
            a0, a1 = ranges[i]
            b0, b1 = ranges[i + 1]
            if b0 <= a1:
                return True
    return False


def _default_preview_fecha(db, cfg: dict) -> str:
    hoy = ahora_madrid().date()
    max_ahead = max(1, min(60, int(cfg.get("max_dias_antelacion") or 60)))
    franjas = list_franjas(db)
    dias = {int(f["dia_semana"]) for f in franjas}
    for n in range(1, max_ahead + 1):
        d = hoy + timedelta(days=n)
        if d.isoweekday() in dias:
            return d.isoformat()
    return (hoy + timedelta(days=1)).isoformat()


def _int_form(key: str, default: int) -> int:
    try:
        return int(str(request.form.get(key) or default).strip() or default)
    except (TypeError, ValueError):
        return default


@bp.route("/configuracion_reservas_web", methods=["GET", "POST"])
@login_requerido
@permiso_reservas
def configuracion_reservas_web():
    db = get_db()
    ensure_web_reservas_tables(db)
    ensure_salon_tables(db)
    seed_salon_if_empty(db)

    if request.method == "POST":
        accion = (request.form.get("accion") or "").strip()
        if accion == "plantilla_comida_cena":
            replace_franjas_from_form(db, franjas_plantilla_comida_cena_semana(pct_web=None))
            db.close()
            flash(
                "Franjas web guardadas: plantilla «Comida + cena» (13:00–16:00 y 20:00–23:30, todos los días). "
                "Ajusta límites o intervalo abajo y pulsa «Guardar todo» si lo necesitas.",
                "success",
            )
            return redirect(url_for("admin.configuracion_reservas_web"))
        if accion == "plantilla_solo_cena":
            replace_franjas_from_form(db, franjas_plantilla_solo_cena_semana(pct_web=None))
            db.close()
            flash(
                "Franjas web guardadas: plantilla «Solo cena» (20:00–23:30, todos los días).",
                "success",
            )
            return redirect(url_for("admin.configuracion_reservas_web"))
        if accion == "plantilla_desde_empresa":
            try:
                filas = franjas_plantilla_desde_rangos_empresa(db)
            except Exception as ex:
                db.close()
                flash(f"No se pudo generar desde empresa: {ex}", "danger")
                return redirect(url_for("admin.configuracion_reservas_web"))
            replace_franjas_from_form(db, filas)
            db.close()
            flash(
                "Franjas web guardadas según los rangos de Configuración empresa. Revisa la tabla y los cupos.",
                "success",
            )
            return redirect(url_for("admin.configuracion_reservas_web"))

        if accion == "prueba_correo_confirmacion":
            dest = (request.form.get("prueba_email") or "").strip()
            if not dest or "@" not in dest:
                db.close()
                flash("Indica un correo válido para la prueba.", "danger")
                return redirect(url_for("admin.configuracion_reservas_web"))
            cfg_mail = get_config_cierre_caja(db)
            if not smtp_config_valida(cfg_mail):
                db.close()
                flash(
                    "SMTP no configurado: en Cierre de caja indica correo del dueño, servidor y contraseña "
                    "(o variable CIERRE_CAJA_SMTP_PASSWORD).",
                    "danger",
                )
                return redirect(url_for("admin.configuracion_reservas_web"))
            cfg_w = get_web_reserva_config(db)
            base = (cfg_w.get("public_base_url") or "").strip().rstrip("/") or request.url_root.rstrip("/")
            ejemplo = f"{base}/confirmar-reserva?token={quote('EJEMPLO-PRUEBA-CONFIG', safe='')}"
            subj = "[Prueba] Confirma tu reserva (panel Gastro)"
            txt = (
                "Este es un correo de prueba desde Reservas web → configuración.\n\n"
                "Así vería el cliente el enlace de confirmación (no es válido para confirmar):\n"
                f"{ejemplo}\n\n"
                "Si recibes este mensaje, el SMTP del cierre de caja funciona para reservas web.\n"
            )
            html = (
                "<p>Este es un <strong>correo de prueba</strong> desde el panel Gastro "
                "(Reservas web → configuración).</p>"
                f'<p><a href="{ejemplo}">Enlace de ejemplo (no confirmará ninguna reserva)</a></p>'
                f"<p><code>{ejemplo}</code></p>"
            )
            ok, err = enviar_correo_externo(
                cfg_mail,
                destinatarios=[dest],
                asunto=subj,
                cuerpo_texto=txt,
                cuerpo_html=html,
            )
            db.close()
            if ok:
                flash(f"Correo de prueba enviado a {dest}.", "success")
            else:
                flash(f"No se pudo enviar la prueba: {err}", "danger")
            return redirect(url_for("admin.configuracion_reservas_web"))

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
        if not rows:
            db.close()
            flash(
                "No se guardó nada: hace falta al menos una franja con día, inicio y fin, o usa una plantilla rápida arriba.",
                "danger",
            )
            return redirect(url_for("admin.configuracion_reservas_web"))

        pmin = max(1, _int_form("min_personas", 1))
        pmax = max(1, _int_form("max_personas", 12))
        if pmin > pmax:
            db.close()
            flash("El mínimo de comensales no puede ser mayor que el máximo.", "danger")
            return redirect(url_for("admin.configuracion_reservas_web"))

        for r in rows:
            if int(r["min_inicio"]) >= int(r["min_fin"]):
                db.close()
                flash(
                    "Revisa las franjas: la hora de inicio debe ser anterior a la de fin en cada fila.",
                    "danger",
                )
                return redirect(url_for("admin.configuracion_reservas_web"))

        if _franja_rows_solapan(rows):
            db.close()
            flash(
                "Hay franjas activas solapadas el mismo día. Separa horarios o marca «No» en Activa en una de ellas.",
                "danger",
            )
            return redirect(url_for("admin.configuracion_reservas_web"))

        rows.sort(key=lambda r: (int(r["dia_semana"]), int(r["min_inicio"]), int(r["min_fin"])))

        save_web_reserva_config(db, request.form)
        replace_franjas_from_form(db, rows)
        db.close()
        flash("Configuración de reservas web guardada.", "success")
        return redirect(url_for("admin.configuracion_reservas_web"))

    cfg = get_web_reserva_config(db)
    franjas = list_all_franjas_admin(db)
    aforo = suma_capacidad_aforo(db)

    preview_fecha = (request.args.get("preview_fecha") or "").strip()[:10]
    if not preview_fecha or not re.match(r"^\d{4}-\d{2}-\d{2}$", preview_fecha):
        preview_fecha = _default_preview_fecha(db, cfg)
    try:
        preview_personas = int(request.args.get("preview_personas") or "2")
    except (TypeError, ValueError):
        preview_personas = 2
    preview_personas = max(1, min(99, preview_personas))

    preview_payload = slots_disponibles_payload(
        db,
        fecha_iso=preview_fecha,
        personas=preview_personas,
        cfg=cfg,
        for_preview=True,
    )
    preview_payload["for_preview"] = True

    web_base = next_site_base_url().rstrip("/")
    url_reserva_publica = f"{web_base}/#reserva"

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
        preview_fecha=preview_fecha,
        preview_personas=preview_personas,
        preview_payload=preview_payload,
        url_reserva_publica=url_reserva_publica,
    )
