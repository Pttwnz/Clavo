"""Cierre de caja X/Z: guía, SMTP e historial (panel administración)."""
from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.cierre_caja_informe import construir_asunto_y_cuerpos, payload_desde_form
from reservas.cierre_caja_mail import enviar_informe_cierre, smtp_config_valida
from reservas.cierre_caja_schema import (
    ensure_cierre_caja_tables,
    get_config_cierre_caja,
    insert_registro_cierre,
    listar_registros_cierre,
    save_config_cierre_caja,
)
from reservas.decorators import login_requerido, permiso_mod
from reservas.empresa_config import get_config_empresa

from . import bp


def _nombre_local(db) -> str:
    emp = get_config_empresa(db)
    return (emp.get("nombre_comercial") or emp.get("razon_social") or "").strip()


@bp.route("/cierre_caja", methods=["GET"])
@login_requerido
@permiso_mod("mod.cierre_caja")
def cierre_caja_index():
    db = get_db()
    ensure_cierre_caja_tables(db)
    cfg = get_config_cierre_caja(db)
    emp = get_config_empresa(db)
    nombre_dueno = (emp.get("nombre_dueno") or "").strip()
    historial = listar_registros_cierre(db, 60)
    db.close()
    return render_template(
        "cierre_caja.html",
        mostrar_nav=True,
        cfg_cierre=cfg,
        historial=historial,
        smtp_ok=smtp_config_valida(cfg),
        nombre_dueno=nombre_dueno,
    )


@bp.route("/cierre_caja/config", methods=["POST"])
@login_requerido
@permiso_mod("mod.cierre_caja")
def cierre_caja_config():
    db = get_db()
    ensure_cierre_caja_tables(db)
    save_config_cierre_caja(db, request.form)
    db.close()
    flash("Configuración de envío de cierres guardada.", "success")
    return redirect(url_for("admin.cierre_caja_index"))


@bp.route("/cierre_caja/probar_email", methods=["POST"])
@login_requerido
@permiso_mod("mod.cierre_caja")
def cierre_caja_probar_email():
    db = get_db()
    cfg = get_config_cierre_caja(db)
    nombre = _nombre_local(db)
    db.close()
    ok, err = enviar_informe_cierre(
        cfg,
        asunto=f"[{nombre or 'GastroManager'}] Prueba de correo — cierre de caja",
        cuerpo_texto="Si recibes este mensaje, el envío SMTP está configurado correctamente.",
        cuerpo_html="<p>Si recibes este mensaje, el envío SMTP está <strong>configurado correctamente</strong>.</p>",
    )
    if ok:
        flash("Correo de prueba enviado. Revisa la bandeja del dueño (y spam).", "success")
    else:
        flash(f"No se pudo enviar la prueba: {err}", "danger")
    return redirect(url_for("admin.cierre_caja_index"))


@bp.route("/cierre_caja/enviar_manual", methods=["POST"])
@login_requerido
@permiso_mod("mod.cierre_caja")
def cierre_caja_enviar_manual():
    """Mismo formulario que tablet, desde admin (opcional)."""
    db = get_db()
    ensure_cierre_caja_tables(db)
    cfg = get_config_cierre_caja(db)
    nombre = _nombre_local(db)
    payload = payload_desde_form(request.form)
    asunto, txt, html = construir_asunto_y_cuerpos(payload, nombre)

    enviado = False
    err = ""
    if smtp_config_valida(cfg):
        enviado, err = enviar_informe_cierre(cfg, asunto=asunto, cuerpo_texto=txt, cuerpo_html=html)
    else:
        err = "SMTP incompleto: revisa correo del dueño, usuario y contraseña."

    insert_registro_cierre(
        db,
        tipo=str(payload.get("tipo") or "X"),
        origen="admin",
        payload=payload,
        enviado=enviado,
        email_error=None if enviado else err,
    )
    db.close()

    if enviado:
        flash("Informe de cierre enviado por correo.", "success")
    else:
        flash(f"Registro guardado en historial. Correo no enviado: {err}", "warning")
    return redirect(url_for("admin.cierre_caja_index"))
