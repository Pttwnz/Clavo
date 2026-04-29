"""Rutas del portal de empleado."""
import base64
import os
from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)

from config import RESERVAS_ONLY
from models import get_db
from reservas.db_helpers import tabla_existe
from reservas.decorators import empleado_permiso, empleado_requerido, login_requerido
from reservas.rrhh_peticiones_schema import contar_pendientes_empleado, ensure_rrhh_peticiones_schema

bp = Blueprint("empleado", __name__)


@bp.route("/area_personal")
@empleado_requerido
@empleado_permiso("emp.area_personal")
def area_personal():
    """Pantalla principal del empleado: planning semanal y acceso a fichaje."""
    db = get_db()
    ensure_rrhh_peticiones_schema(db)
    empleado_id = session["empleado_id"]

    empleado = db.execute(
        "SELECT * FROM empleados WHERE id=?",
        (empleado_id,),
    ).fetchone()

    semanas_horario = []
    if empleado and (not RESERVAS_ONLY) and tabla_existe(db, "horarios"):
        from reservas.blueprints.admin.horarios import matriz_semanal_empleado

        hoy_d = date.today()
        lun0 = hoy_d - timedelta(days=hoy_d.weekday())
        for w in range(6):
            lun = lun0 + timedelta(weeks=w)
            dom = lun + timedelta(days=6)
            semanas_horario.append(matriz_semanal_empleado(db, lun, dom, empleado_id))

    n_rrhh_pend, n_sol_pend = contar_pendientes_empleado(db, empleado_id)

    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
    from reservas.vacaciones_fichaje import resumen_jornada_vacaciones

    ensure_config_empresa_table(db)
    cfg_emp = get_config_empresa(db)
    emp_d = dict(empleado) if empleado else {}
    jornada_vacaciones = resumen_jornada_vacaciones(
        db, empleado_id, cfg_emp, emp_d.get("fecha_alta"), emp_d.get("horas_contrato")
    )

    db.close()

    return render_template(
        "area_personal.html",
        mostrar_nav=True,
        empleado=emp_d,
        n_rrhh_pend=n_rrhh_pend,
        n_sol_pend=n_sol_pend,
        semanas_horario=semanas_horario,
        jornada_vacaciones=jornada_vacaciones,
    )


@bp.route("/peticiones_rrhh")
@empleado_requerido
@empleado_permiso("emp.rrhh")
def peticiones_rrhh():
    """Mensajes a RRHH, solicitudes formales y PDFs de horarios publicados."""
    db = get_db()
    ensure_rrhh_peticiones_schema(db)
    empleado_id = session["empleado_id"]

    solicitudes = []
    if tabla_existe(db, "solicitudes"):
        solicitudes = [
            dict(x)
            for x in db.execute(
                """
                SELECT * FROM solicitudes
                WHERE empleado_id=?
                ORDER BY id DESC
                """,
                (empleado_id,),
            ).fetchall()
        ]

    mensajes_rrhh = []
    if tabla_existe(db, "mensajes_rrhh"):
        mensajes_rrhh = [
            dict(x)
            for x in db.execute(
                """
                SELECT * FROM mensajes_rrhh
                WHERE empleado_id=?
                ORDER BY id DESC
                LIMIT 40
                """,
                (empleado_id,),
            ).fetchall()
        ]

    horarios_pdf_docs = []
    try:
        from reservas.horarios_entregas_schema import ensure_horarios_entregas_table, listar_entregas_empleado

        ensure_horarios_entregas_table(db)
        horarios_pdf_docs = listar_entregas_empleado(db, empleado_id, 30)
    except Exception:
        horarios_pdf_docs = []

    n_rrhh_pend, n_sol_pend = contar_pendientes_empleado(db, empleado_id)

    db.close()

    return render_template(
        "peticiones_rrhh.html",
        mostrar_nav=True,
        solicitudes=solicitudes,
        mensajes_rrhh=mensajes_rrhh,
        n_rrhh_pend=n_rrhh_pend,
        n_sol_pend=n_sol_pend,
        horarios_pdf_docs=horarios_pdf_docs,
    )


@bp.route("/rrhh_chat", methods=["POST"])
@empleado_requerido
@empleado_permiso("emp.rrhh")
def rrhh_chat():
    """Registra un mensaje para RRHH (sin respuesta automática)."""
    mensaje = (request.form.get("mensaje") or "").strip()
    if not mensaje:
        flash("Escribe un mensaje para RRHH.", "warning")
        return redirect(url_for("empleado.peticiones_rrhh"))

    empleado_id = session["empleado_id"]
    db = get_db()
    ensure_rrhh_peticiones_schema(db)
    emp = db.execute(
        "SELECT * FROM empleados WHERE id=?",
        (empleado_id,),
    ).fetchone()
    if not emp:
        db.close()
        flash("Sesión inválida.", "danger")
        return redirect("/login_empleado")

    if tabla_existe(db, "mensajes_rrhh"):
        db.execute(
            """
            INSERT INTO mensajes_rrhh (empleado_id, mensaje, respuesta_ia)
            VALUES (?,?,?)
            """,
            (empleado_id, mensaje, None),
        )
        db.commit()

    db.close()
    flash(
        "Mensaje enviado a RRHH. Dirección o encargado lo revisará en la bandeja de peticiones.",
        "success",
    )
    return redirect(url_for("empleado.peticiones_rrhh"))


@bp.route("/crear_solicitud", methods=["POST"])
@empleado_requerido
@empleado_permiso("emp.rrhh")
def crear_solicitud():
    """Registra solicitud de vacaciones / permiso para el empleado logueado."""
    empleado_id = session["empleado_id"]
    tipo = request.form.get("tipo")
    fecha_inicio = request.form.get("fecha_inicio")
    fecha_fin = request.form.get("fecha_fin")
    comentario = request.form.get("comentario")

    db = get_db()
    if not tabla_existe(db, "solicitudes"):
        db.close()
        flash("La tabla de solicitudes no está disponible.", "danger")
        return redirect(url_for("empleado.peticiones_rrhh"))

    db.execute(
        """
        INSERT INTO solicitudes
        (empleado_id, tipo, fecha_inicio, fecha_fin, estado, fecha_solicitud, comentario)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            empleado_id,
            tipo,
            fecha_inicio,
            fecha_fin,
            "Pendiente",
            date.today().strftime("%Y-%m-%d"),
            comentario or "",
        ),
    )
    db.commit()
    db.close()
    flash("Solicitud enviada. Estado: pendiente de revisión.", "success")
    return redirect(url_for("empleado.peticiones_rrhh"))


@bp.route("/mi_horario_pdf/<int:doc_id>")
@empleado_requerido
@empleado_permiso("emp.area_personal")
def descargar_horario_pdf(doc_id):
    """Descarga un PDF de horarios publicado para este empleado."""
    empleado_id = session["empleado_id"]
    db = get_db()
    try:
        from reservas.horarios_entregas_schema import ensure_horarios_entregas_table

        ensure_horarios_entregas_table(db)
        row = db.execute(
            """
            SELECT empleado_id, archivo_relativo, etiqueta, periodo_desde, periodo_hasta
            FROM horarios_pdf_entregas WHERE id = ?
            """,
            (doc_id,),
        ).fetchone()
    finally:
        db.close()

    if not row or row["empleado_id"] != empleado_id:
        abort(404)

    rel = (row["archivo_relativo"] or "").strip().replace("\\", "/")
    if not rel.startswith("uploads/horarios_empleado/") or ".." in rel:
        abort(404)

    static_root = current_app.static_folder
    path = os.path.join(static_root or "", *rel.split("/"))
    if not os.path.isfile(path):
        abort(404)

    slug = f"horarios_{row['periodo_desde']}_{row['periodo_hasta']}".replace("-", "")
    fname = f"{slug[:60]}.pdf"
    return send_file(path, as_attachment=True, download_name=fname, mimetype="application/pdf")


@bp.route("/panel_empleado")
@empleado_requerido
@empleado_permiso("emp.panel")
def panel_empleado():
    """Panel de inicio para el empleado autenticado."""
    empleado_id = session["empleado_id"]
    db = get_db()
    ensure_rrhh_peticiones_schema(db)
    n_rrhh_pend, n_sol_pend = contar_pendientes_empleado(db, empleado_id)
    db.close()
    return render_template(
        "panel_empleado.html",
        mostrar_nav=True,
        n_rrhh_pend=n_rrhh_pend,
        n_sol_pend=n_sol_pend,
    )


@bp.route("/conformidad_jornada", methods=["GET", "POST"])
@empleado_requerido
@empleado_permiso("emp.conformidad")
def conformidad_jornada():
    """Conformidad del trabajador con el registro de jornada (validación digital + firma opcional)."""
    from reservas.jornada_schema import ensure_jornada_tables, get_conformidad_mes, upsert_conformidad
    from reservas.jornada_texto import texto_conformidad_trabajador
    from reservas.i18n import translate

    empleado_id = session["empleado_id"]
    db = get_db()
    ensure_jornada_tables(db)

    if request.method == "GET":
        mes = (request.args.get("mes") or "").strip()
        if not mes:
            mes = date.today().strftime("%Y-%m")
        conformidad = get_conformidad_mes(db, empleado_id, mes)
        db.close()
        return render_template(
            "conformidad_jornada.html",
            mostrar_nav=True,
            mes=mes,
            conformidad=conformidad,
            texto_legal=texto_conformidad_trabajador(),
        )

    mes = (request.form.get("mes") or "").strip()
    acepto = request.form.get("acepto")
    firma_data = (request.form.get("firma_png") or "").strip()

    if not mes or not acepto:
        db.close()
        flash(translate("page.conformidad.flash_warn"), "warning")
        return redirect(f"/conformidad_jornada?mes={mes or date.today().strftime('%Y-%m')}")

    static_root = current_app.static_folder
    rel_firma = None
    if firma_data.startswith("data:image") and "base64," in firma_data:
        try:
            b64 = firma_data.split("base64,", 1)[1]
            raw = base64.b64decode(b64)
            if len(raw) > 400_000:
                raise ValueError("firma grande")
            dest_dir = os.path.join(static_root or "", "uploads", "firmas")
            os.makedirs(dest_dir, exist_ok=True)
            fname = f"firma_{empleado_id}_{mes.replace('-', '_')}.png"
            path = os.path.join(dest_dir, fname)
            with open(path, "wb") as f:
                f.write(raw)
            rel_firma = f"uploads/firmas/{fname}".replace("\\", "/")
        except Exception:
            rel_firma = None

    if rel_firma is None:
        prev = get_conformidad_mes(db, empleado_id, mes)
        if prev and prev.get("firma_relativa"):
            rel_firma = prev["firma_relativa"]

    upsert_conformidad(
        db,
        empleado_id,
        mes,
        texto_conformidad_trabajador(),
        request.remote_addr,
        (request.headers.get("User-Agent") or "")[:500],
        rel_firma,
    )
    db.close()
    flash(translate("page.conformidad.flash_ok"), "success")
    return redirect("/area_personal")


@bp.before_request
def _empleado_reservas_only_redirect():
    """En modo solo reservas el portal de empleado (RRHH, fichajes, etc.) no aplica."""
    if not RESERVAS_ONLY:
        return None
    return redirect(url_for("admin.reservas"))
