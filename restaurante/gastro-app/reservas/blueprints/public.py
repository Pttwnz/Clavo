"""Rutas públicas: visualización, logins y cierre de sesión."""
import json
import time
from datetime import date, timedelta

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from urllib.parse import urlparse

from auth import hash_pin, verificar_pin
from config import RESERVAS_ONLY
from models import get_db
from reservas.decorators import login_requerido, sesion_puede_gestionar_reservas
from reservas.tablet_schema import ensure_tablet_schema, pin_valido_acceso_tablet, pin_valido_admin
from reservas.salon_helpers import ensure_salon_tables, seed_salon_if_empty
from reservas.sala_vivo import build_sala_vivo_data, normalizar_fecha_param, turno_visualizar_por_defecto
from reservas.i18n import SUPPORTED_LANGS, translate
from reservas.nav_urls import public_entry_url
from reservas.web_reservas_http import register_web_reservas_routes

bp = Blueprint("public", __name__)
register_web_reservas_routes(bp)


@bp.route("/sw.js")
def service_worker():
    """Service worker en raíz para alcance '/' (modo app en todo tablet)."""
    return send_from_directory(
        current_app.static_folder,
        "sw.js",
        mimetype="application/javascript",
    )

# Tiempo máximo (segundos) tras validar PIN de encargado para el cierre de caja en tablet.
_TABLET_CIERRE_PIN_TTL = 30 * 60
# Misma ventana para editar parámetros de propinas en tablet (PIN administrador).
_TABLET_PROPINAS_PIN_TTL = 30 * 60
_TABLET_PREREG_PIN_TTL = 30 * 60


def _tablet_cierre_pin_unlocked() -> bool:
    """True si el encargado introdujo el PIN de admin hace menos de _TABLET_CIERRE_PIN_TTL."""
    ts = session.get("tablet_cierre_unlock_ts")
    if ts is None:
        return False
    try:
        return (time.time() - float(ts)) < _TABLET_CIERRE_PIN_TTL
    except (TypeError, ValueError):
        return False


def _tablet_propinas_pin_unlocked() -> bool:
    ts = session.get("tablet_propinas_unlock_ts")
    if ts is None:
        return False
    try:
        return (time.time() - float(ts)) < _TABLET_PROPINAS_PIN_TTL
    except (TypeError, ValueError):
        return False


def _tablet_prereg_pin_unlocked() -> bool:
    ts = session.get("tablet_prereg_unlock_ts")
    if ts is None:
        return False
    try:
        return (time.time() - float(ts)) < _TABLET_PREREG_PIN_TTL
    except (TypeError, ValueError):
        return False


@bp.route("/api/sala_vivo")
def api_sala_vivo():
    """JSON para refresco de Sala en vivo sin recargar (sync_token + mesas/reservas)."""
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    fecha = request.args.get("fecha", "")
    turno = request.args.get("turno", "")
    data = build_sala_vivo_data(db, current_app.static_folder, fecha, turno)
    db.close()
    return jsonify(data)


@bp.route("/visualizar")
def visualizar():
    """Mapa público de mesas y reservas por fecha y turno (sin login)."""
    fecha_raw = request.args.get("fecha", str(date.today()))
    fecha = normalizar_fecha_param(fecha_raw)

    if "turno" in request.args and str(request.args.get("turno", "")).strip():
        turno = str(request.args.get("turno")).strip().lower()
    else:
        turno = turno_visualizar_por_defecto()

    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)

    payload = build_sala_vivo_data(db, current_app.static_folder, fecha, turno)
    db.close()

    ayer = str(date.fromisoformat(fecha[:10]) - timedelta(days=1))
    manana = str(date.fromisoformat(fecha[:10]) + timedelta(days=1))

    next_visualizar = f"/visualizar?fecha={fecha}&turno={turno}"
    mostrar_nav = bool(
        session.get("admin_logueado")
        or session.get("empleado_id") is not None
        or session.get("modo_tablet")
    )

    _legend_spec = (
        ("#94a3b8", "page.salon.legend_free"),
        ("#f59e0b", "page.salon.legend_pending"),
        ("#38bdf8", "page.salon.legend_confirmed"),
        ("#34d399", "page.salon.legend_arrived"),
        ("#64748b", "page.salon.legend_finished"),
        ("#f87171", "page.salon.legend_cancelled"),
    )
    _legend_fallback = {
        "page.salon.legend_free": "Libre",
        "page.salon.legend_pending": "Pendiente",
        "page.salon.legend_confirmed": "Confirmada",
        "page.salon.legend_arrived": "En sala",
        "page.salon.legend_finished": "Finalizada",
        "page.salon.legend_cancelled": "Cancelada",
    }
    sala_legend_chips = []
    for color, key in _legend_spec:
        lbl = translate(key)
        if lbl == key:
            lbl = _legend_fallback.get(key, key)
        sala_legend_chips.append({"color": color, "label": lbl})
    sala_legend_title = translate("page.salon.live_legend")

    html = render_template(
        "visualizar.html",
        mesas=payload["mesas"],
        decor=payload["decor"],
        plano_ancho=payload["plano_ancho"],
        plano_alto=payload["plano_alto"],
        reservas=payload["reservas"],
        totales=payload["totales"],
        sync_token=payload["sync_token"],
        fecha=fecha,
        turno=turno,
        ayer=ayer,
        manana=manana,
        next_visualizar=next_visualizar,
        mostrar_nav=mostrar_nav,
        sala_live_gestion=sesion_puede_gestionar_reservas(),
        sala_server_time=payload.get("server_time_sec") or payload.get("server_time"),
        sala_server_time_sec=payload.get("server_time_sec"),
        sala_server_time_hm=payload.get("server_time"),
        sala_legend_chips=sala_legend_chips,
        sala_legend_title=sala_legend_title,
    )
    resp = make_response(html)
    # Evita caché del HTML (incl. proxies/CDN habituales).
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0, private"
    resp.headers["Pragma"] = "no-cache"
    resp.headers["Expires"] = "0"
    resp.headers["Surrogate-Control"] = "no-store"
    return resp


def _login_selector_view():
    """Selector de tipo de acceso (admin / empleado / tablet)."""
    next_url = (request.args.get("next") or "").strip()
    return render_template(
        "login_selector.html",
        next_url=next_url,
    )


@bp.route("/")
def inicio():
    """Selector en raíz (acceso directo al puerto Gastro)."""
    return _login_selector_view()


@bp.route("/acceso-interno")
def acceso_interno():
    """Mismo hub que `/` cuando la raíz del dominio la sirve la web Next (MERGED_HOST_ROOT)."""
    return _login_selector_view()


@bp.route("/set_lang/<lang_code>")
def set_lang(lang_code: str):
    """Desa l'idioma de la interfície (ca / va / es / en) a la sessió."""
    if lang_code in SUPPORTED_LANGS:
        session["lang"] = lang_code
        session.permanent = True
    ref = request.referrer or ""
    base = request.host_url.rstrip("/")
    if ref.startswith(base):
        return redirect(ref)
    return redirect(public_entry_url())

# =====================================================
# VERIFICAR ADMIN
# =====================================================

@bp.route("/verificar_admin", methods=["POST"])
def verificar_admin():
    """Valida PIN de administrador o inicializa el primero con 1234."""
    pin = request.form.get("pin")
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()

    def _safe_next(raw: str) -> str:
        if not raw:
            return "/panel"
        parsed = urlparse(raw)
        if parsed.scheme or parsed.netloc:
            return "/panel"
        if not raw.startswith("/"):
            return "/panel"
        return raw

    db = get_db()

    admin = db.execute(
        "SELECT pin_hash FROM admin"
    ).fetchone()

    db.close()

    # Si ya existe admin en la base de datos

    if admin and admin['pin_hash']:

        if verificar_pin(pin, admin['pin_hash']):

            session.pop("empleado_id", None)
            session.pop("empleado_nombre", None)
            session['admin_logueado'] = True
            session['rol'] = "admin"
            session.pop("modo_tablet", None)
            from reservas.rbac_session import marcar_superadmin

            marcar_superadmin()

            return redirect(_safe_next(next_url))

    else:

        # Primera vez: si el PIN es 1234, crear hash

        if pin == "1234":

            db = get_db()

            db.execute("DELETE FROM admin")

            db.execute(
                "INSERT INTO admin (pin_hash) VALUES (?)",
                (hash_pin("1234"),)
            )

            db.commit()

            db.close()

            session.pop("empleado_id", None)
            session.pop("empleado_nombre", None)
            session['admin_logueado'] = True
            session['rol'] = "admin"
            session.pop("modo_tablet", None)
            from reservas.rbac_session import marcar_superadmin

            marcar_superadmin()

            return redirect(_safe_next(next_url))

    return render_template(
        "login.html",
        mostrar_nav=False,
        error=True,
        next_url=next_url,
    )
@bp.route("/logout")
def logout():
    """Cierra sesión (admin o empleado) y vuelve al inicio."""
    session.clear()
    return redirect(public_entry_url())
@bp.route("/login_empleado", methods=["GET", "POST"])
def login_empleado():
    """Login de empleado por PIN en claro frente a la tabla empleados."""
    if request.method == "POST":

        pin = request.form.get("pin")

        db = get_db()

        empleado = db.execute(
            """
            SELECT
                id,
                nombre,
                apellido,
                puesto
            FROM empleados
            WHERE pin = ?
            """,
            (pin,)
        ).fetchone()

        db.close()

        if not empleado:

            return render_template(
                "login_empleado.html",
                error="PIN incorrecto"
            )

        session.pop("admin_logueado", None)
        session["empleado_id"] = empleado["id"]
        session["empleado_nombre"] = empleado["nombre"]

        session["rol"] = "empleado"
        session.pop("modo_tablet", None)
        from reservas.rbac_session import cargar_permisos_empleado

        cargar_permisos_empleado(int(empleado["id"]))

        if RESERVAS_ONLY:
            return redirect(url_for("admin.reservas"))
        return redirect("/panel_empleado")

    return render_template("login_empleado.html")
@bp.route("/login_cliente", methods=["GET", "POST"])
def login_cliente_redirect():
    """Acceso cliente descontinuado: usar modo tablet del local."""
    return redirect(url_for("public.tablet_acceso"))


@bp.route("/tablet/acceso", methods=["GET", "POST"])
def tablet_acceso():
    """PIN del modo tablet (local): solo reservas + fichaje; sin editor de salón ni resto."""
    if session.get("modo_tablet"):
        return redirect(url_for("public.tablet_inicio"))
    if request.method == "POST":
        pin = (request.form.get("pin") or "").strip()
        db = get_db()
        ensure_tablet_schema(db)
        ok = pin_valido_acceso_tablet(db, pin) if pin else False
        db.close()
        if ok:
            session.clear()
            session["modo_tablet"] = True
            session["rol"] = "tablet"
            return redirect(url_for("public.tablet_inicio"))
        return render_template(
            "tablet_acceso.html",
            mostrar_nav=False,
            error=True,
        )
    return render_template("tablet_acceso.html", mostrar_nav=False)


@bp.route("/tablet")
def tablet_inicio():
    """Menú táctil: reservas o fichaje."""
    if not session.get("modo_tablet"):
        return redirect(url_for("public.tablet_acceso"))
    return render_template("tablet_inicio.html", mostrar_nav=True)


@bp.route("/tablet/cierre_caja", methods=["GET", "POST"])
@login_requerido
def tablet_cierre_caja():
    """Cierre de caja X/Z desde el tablet: PIN de encargado (admin), calculadora e informe por correo."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.cierre_caja_informe import construir_asunto_y_cuerpos, payload_desde_form
    from reservas.cierre_caja_mail import enviar_informe_cierre, smtp_config_valida
    from reservas.cierre_caja_schema import (
        ensure_cierre_caja_tables,
        get_config_cierre_caja,
        insert_registro_cierre,
    )
    from reservas.empresa_config import get_config_empresa
    from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

    if not session.get("modo_tablet"):
        flash("El cierre de caja desde tablet solo está disponible en el modo tablet del local.", "warning")
        if session.get("admin_logueado"):
            return redirect(url_for("admin.panel"))
        return redirect(public_entry_url())

    db = get_db()
    ensure_tablet_config(db)
    cfg_t = get_tablet_config(db)
    if not cfg_t.get("permitir_cierre_caja"):
        db.close()
        flash(
            "El cierre de caja en tablet no está activado. Un administrador puede activarlo en "
            "Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))
    db.close()

    if request.method == "POST" and request.form.get("accion") == "pin_encargado":
        pin = (request.form.get("pin_encargado") or "").strip()
        db = get_db()
        ensure_tablet_schema(db)
        ok = pin_valido_admin(db, pin) if pin else False
        db.close()
        if ok:
            session["tablet_cierre_unlock_ts"] = time.time()
            session.modified = True
            flash("Acceso autorizado. Puedes completar el cierre de caja.", "success")
            return redirect(url_for("public.tablet_cierre_caja"))
        flash("PIN incorrecto. Usa el PIN de administrador / encargado.", "danger")
        return render_template("tablet_cierre_caja_pin.html", mostrar_nav=True)

    if not _tablet_cierre_pin_unlocked():
        return render_template("tablet_cierre_caja_pin.html", mostrar_nav=True)

    db = get_db()
    ensure_cierre_caja_tables(db)
    cfg_mail = get_config_cierre_caja(db)
    emp = get_config_empresa(db)
    nombre_local = (emp.get("nombre_comercial") or emp.get("razon_social") or "").strip()
    nombre_dueno = (emp.get("nombre_dueno") or "").strip()

    if request.method == "POST":
        if not _tablet_cierre_pin_unlocked():
            db.close()
            flash("La sesión de encargado expiró. Vuelve a introducir el PIN.", "warning")
            return render_template("tablet_cierre_caja_pin.html", mostrar_nav=True)

        payload = payload_desde_form(request.form)
        asunto, txt, html = construir_asunto_y_cuerpos(payload, nombre_local)

        enviado = False
        err = ""
        if smtp_config_valida(cfg_mail):
            enviado, err = enviar_informe_cierre(
                cfg_mail,
                asunto=asunto,
                cuerpo_texto=txt,
                cuerpo_html=html,
            )
        else:
            err = (
                "Correo no configurado: en el panel admin, sección Cierre de caja, "
                "indica Gmail del dueño y SMTP (o variable CIERRE_CAJA_SMTP_PASSWORD)."
            )

        insert_registro_cierre(
            db,
            tipo=str(payload.get("tipo") or "X"),
            origen="tablet",
            payload=payload,
            enviado=enviado,
            email_error=None if enviado else err,
        )
        db.close()

        if enviado:
            if nombre_dueno:
                flash(f"Cierre registrado y enviado por correo a {nombre_dueno}.", "success")
            else:
                flash("Cierre registrado y enviado por correo al dueño.", "success")
        else:
            flash(f"Cierre guardado en historial. {err}", "warning")
        return redirect(url_for("public.tablet_cierre_caja"))

    db.close()
    return render_template(
        "tablet_cierre_caja.html",
        mostrar_nav=True,
        smtp_configurado=smtp_config_valida(cfg_mail),
        nombre_local=nombre_local or "Establecimiento",
        nombre_dueno=nombre_dueno,
    )


@bp.route("/tablet/equipo_hoy")
@login_requerido
def tablet_equipo_hoy():
    """Compañeros y turnos del día según el módulo Horarios (solo lectura, modo tablet)."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.equipo_dia_data import (
        equipo_horarios_para_fecha,
        etiqueta_fecha_es,
        fechas_vecinas,
    )
    from reservas.tablet_config_schema import get_tablet_config

    if not session.get("modo_tablet"):
        flash("Esta pantalla solo está disponible en el modo tablet del local.", "warning")
        if session.get("admin_logueado"):
            return redirect(url_for("admin.panel"))
        return redirect(public_entry_url())

    db = get_db()
    cfg = get_tablet_config(db)
    if not cfg.get("permitir_ver_equipo_turno"):
        db.close()
        flash(
            "La visualización de equipo y turnos no está activada para el tablet. "
            "Un administrador puede activarla en Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))

    fecha_raw = (request.args.get("fecha") or "").strip() or str(date.today())
    try:
        date.fromisoformat(fecha_raw[:10])
        fecha = fecha_raw[:10]
    except ValueError:
        fecha = str(date.today())

    equipo = equipo_horarios_para_fecha(db, fecha)
    db.close()

    ayer, _ref, manana = fechas_vecinas(fecha)
    return render_template(
        "tablet_equipo_hoy.html",
        mostrar_nav=True,
        equipo=equipo,
        fecha=fecha,
        fecha_etiqueta=etiqueta_fecha_es(fecha),
        ayer=ayer,
        manana=manana,
        hoy_iso=str(date.today()),
    )


# =====================================================
# TABLET · PROPINAS
# =====================================================


@bp.route("/tablet/propinas", methods=["GET", "POST"])
@login_requerido
def tablet_propinas():
    """Reparto equitativo de propinas según horarios del día o por franjas horarias."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.propinas_schema import (
        T_LINEAS,
        T_REPARTOS,
        empleados_con_horario_fecha,
        empleados_con_horario_franja,
        ensure_propinas_tables,
        franjas_del_dia,
        franjas_para_reparto,
        horas_solapamiento_franja,
        horas_turno_dia,
        minutos_ventana_franja,
        listar_repartos_fecha,
        reparto_dia_completo_ya_registrado,
        reparto_franja_ya_registrado,
    )
    from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

    if not session.get("modo_tablet"):
        flash("Esta pantalla solo está disponible en el modo tablet del local.", "warning")
        return redirect(public_entry_url())

    db = get_db()
    ensure_tablet_config(db)
    cfg = get_tablet_config(db)
    if not cfg.get("permitir_propinas"):
        db.close()
        flash(
            "El reparto de propinas no está activado. Actívalo en Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))

    agrupacion = (cfg.get("propinas_agrupacion") or "dia").strip().lower()
    if agrupacion not in ("dia", "franja"):
        agrupacion = "dia"
    h_franja = int(cfg.get("propinas_franja_horas") or 8)
    franja_modo_cfg = (cfg.get("propinas_franja_modo") or "auto").strip().lower()
    franjas_cfg = franjas_para_reparto(cfg)
    if agrupacion == "franja" and not franjas_cfg:
        franjas_cfg = franjas_del_dia(h_franja)

    fecha_raw = (request.form.get("fecha") if request.method == "POST" else request.args.get("fecha")) or ""
    try:
        fecha = date.fromisoformat((fecha_raw or str(date.today()))[:10]).isoformat()
    except ValueError:
        fecha = str(date.today())

    franja_sel = 0
    if agrupacion == "franja":
        fs = (request.form.get("franja") if request.method == "POST" else request.args.get("franja")) or "0"
        try:
            franja_sel = int(fs)
        except ValueError:
            franja_sel = 0
        if franja_sel < 0 or franja_sel >= len(franjas_cfg):
            franja_sel = 0

    ensure_propinas_tables(db)
    a_min, b_min = 0, 24 * 60
    fj_actual = None
    if agrupacion == "franja":
        fj_actual = franjas_cfg[franja_sel]
        a_min, b_min = minutos_ventana_franja(fj_actual)
        empleados = empleados_con_horario_franja(db, fecha, a_min, b_min)
    else:
        empleados = empleados_con_horario_fecha(db, fecha)

    if request.method == "POST" and request.form.get("accion") == "repartir":
        monto_s = (request.form.get("monto_total") or "").strip().replace(",", ".")
        modo = (request.form.get("modo") or "igual").strip().lower()
        if modo not in ("igual", "horas"):
            modo = "igual"
        try:
            monto = float(monto_s)
        except ValueError:
            monto = 0.0

        fr_idx = -1
        fi_ins: str | None = None
        ff_ins: str | None = None
        if agrupacion == "franja":
            try:
                fr_idx = int(request.form.get("franja_idx") or franja_sel)
            except ValueError:
                fr_idx = franja_sel
            if fr_idx < 0 or fr_idx >= len(franjas_cfg):
                db.close()
                flash("Franja no válida.", "warning")
                return redirect(url_for("public.tablet_propinas", fecha=fecha, franja=franja_sel))
            fj_post = franjas_cfg[fr_idx]
            a_min, b_min = minutos_ventana_franja(fj_post)
            empleados = empleados_con_horario_franja(db, fecha, a_min, b_min)
            fi_ins = fj_post["inicio"]
            ff_ins = fj_post["fin"]
            if reparto_franja_ya_registrado(db, fecha, fr_idx):
                db.close()
                flash("Ya hay un reparto registrado para esa franja y fecha.", "warning")
                return redirect(url_for("public.tablet_propinas", fecha=fecha, franja=fr_idx))
        else:
            if reparto_dia_completo_ya_registrado(db, fecha):
                db.close()
                flash("Ya hay un reparto registrado para ese día completo.", "warning")
                return redirect(url_for("public.tablet_propinas", fecha=fecha))

        if monto <= 0 or not empleados:
            db.close()
            flash(
                "Indica un importe válido y asegúrate de que haya personal con turno "
                "(en esa franja horaria o en el día, según configuración).",
                "warning",
            )
            q: dict = {"fecha": fecha}
            if agrupacion == "franja":
                q["franja"] = fr_idx
            return redirect(url_for("public.tablet_propinas", **q))

        n = len(empleados)
        lineas: list[tuple[int, float, float]] = []
        if modo == "igual":
            cuota = round(monto / n, 2)
            resto = round(monto - cuota * n, 2)
            for i, emp in enumerate(empleados):
                imp = cuota + (resto if i == 0 else 0.0)
                lineas.append((int(emp["id"]), imp, 0.0))
        else:
            if agrupacion == "franja":
                horas_list = [
                    (int(e["id"]), horas_solapamiento_franja(db, int(e["id"]), fecha, a_min, b_min))
                    for e in empleados
                ]
            else:
                horas_list = [(int(e["id"]), horas_turno_dia(db, int(e["id"]), fecha)) for e in empleados]
            hsum = sum(h for _, h in horas_list) or 1.0
            for eid, h in horas_list:
                imp = round(monto * (h / hsum), 2)
                lineas.append((eid, imp, h))

        if agrupacion == "franja":
            db.execute(
                f"""
                INSERT INTO {T_REPARTOS}
                    (fecha, monto_total, modo, notas, franja_idx, franja_inicio, franja_fin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (fecha, monto, modo, None, fr_idx, fi_ins, ff_ins),
            )
        else:
            db.execute(
                f"""
                INSERT INTO {T_REPARTOS}
                    (fecha, monto_total, modo, notas, franja_idx, franja_inicio, franja_fin)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (fecha, monto, modo, None, -1, None, None),
            )
        db.commit()
        rid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        for eid, imp, hh in lineas:
            db.execute(
                f"INSERT INTO {T_LINEAS} (reparto_id, empleado_id, importe, horas_turno) VALUES (?,?,?,?)",
                (rid, eid, imp, hh or None),
            )
        db.commit()
        db.close()
        etq = f" ({fi_ins}–{ff_ins})" if fi_ins and ff_ins else ""
        flash(f"Reparto registrado{etq}: {n} persona(s). Total {monto:.2f} €.", "success")
        redir_q = {"fecha": fecha}
        if agrupacion == "franja":
            redir_q["franja"] = fr_idx
        return redirect(url_for("public.tablet_propinas", **redir_q))

    modo_defecto = cfg.get("propinas_modo_defecto") or "igual"
    franjas_hechas: list[bool] = []
    if agrupacion == "franja":
        franjas_hechas = [reparto_franja_ya_registrado(db, fecha, i) for i in range(len(franjas_cfg))]
    reparto_dia_hecho = reparto_dia_completo_ya_registrado(db, fecha) if agrupacion == "dia" else False
    ya_esta = (
        reparto_franja_ya_registrado(db, fecha, franja_sel)
        if agrupacion == "franja"
        else reparto_dia_hecho
    )
    repartos_hoy = listar_repartos_fecha(db, fecha)
    db.close()
    return render_template(
        "tablet_propinas.html",
        mostrar_nav=True,
        fecha=fecha,
        empleados=empleados,
        modo_defecto=modo_defecto,
        agrupacion=agrupacion,
        franjas_cfg=franjas_cfg,
        franja_sel=franja_sel,
        fj_actual=fj_actual,
        franjas_hechas=franjas_hechas,
        ya_esta=ya_esta,
        h_franja=h_franja,
        franja_modo_cfg=franja_modo_cfg,
        repartos_hoy=repartos_hoy,
    )


@bp.route("/tablet/propinas/eliminar_reparto", methods=["POST"])
@login_requerido
def tablet_propinas_eliminar_reparto():
    """Quita un reparto concreto (PIN administrador) para poder volver a registrarlo."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.propinas_schema import eliminar_reparto_por_id, ensure_propinas_tables
    from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

    if not session.get("modo_tablet"):
        flash("Esta acción solo está disponible en el modo tablet del local.", "warning")
        return redirect(public_entry_url())

    db = get_db()
    ensure_tablet_config(db)
    cfg = get_tablet_config(db)
    if not cfg.get("permitir_propinas"):
        db.close()
        flash(
            "El reparto de propinas no está activado. Actívalo en Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))

    fecha_back = ((request.form.get("fecha") or "").strip() or str(date.today()))[:10]
    try:
        date.fromisoformat(fecha_back)
    except ValueError:
        fecha_back = str(date.today())

    pin = (request.form.get("pin_encargado") or "").strip()
    ensure_tablet_schema(db)
    if not pin or not pin_valido_admin(db, pin):
        db.close()
        flash("PIN incorrecto. Solo el PIN de administrador / encargado puede eliminar un reparto.", "danger")
        agr = (cfg.get("propinas_agrupacion") or "dia").strip().lower()
        rq: dict = {"fecha": fecha_back}
        if agr == "franja":
            try:
                rq["franja"] = int(request.form.get("franja_redirect") or 0)
            except ValueError:
                pass
        return redirect(url_for("public.tablet_propinas", **rq))

    try:
        rid = int(request.form.get("reparto_id") or 0)
    except ValueError:
        rid = 0
    ensure_propinas_tables(db)
    ok = eliminar_reparto_por_id(db, rid, fecha_back) if rid else False
    db.close()
    if ok:
        flash("Reparto eliminado. Ese registro ya no cuenta; puedes volver a hacer el reparto.", "success")
    else:
        flash("No se pudo eliminar (reparto no encontrado o fecha no coincide).", "warning")

    agr = (cfg.get("propinas_agrupacion") or "dia").strip().lower()
    redir: dict = {"fecha": fecha_back}
    if agr == "franja":
        try:
            redir["franja"] = int(request.form.get("franja_redirect") or 0)
        except ValueError:
            pass
    return redirect(url_for("public.tablet_propinas", **redir))


def _tablet_preregistro_template_kwargs(db, form_prev):
    """Mismas listas sugeridas y rangos que el alta en Empleados."""
    from reservas.blueprints.admin.empleados.listado import (
        DEPARTAMENTOS_SUGERIDOS,
        PUESTOS_SUGERIDOS,
    )
    from reservas.rbac_schema import ensure_rbac_tables, listar_rangos

    ensure_rbac_tables(db)
    return {
        "mostrar_nav": True,
        "form_prev": form_prev,
        "puestos_sugeridos": PUESTOS_SUGERIDOS,
        "departamentos_sugeridos": DEPARTAMENTOS_SUGERIDOS,
        "rangos": listar_rangos(db),
    }


@bp.route("/tablet/preregistro", methods=["GET", "POST"])
@login_requerido
def tablet_preregistro():
    """Formulario de preregistro de empleado (solicitud de alta) desde el tablet del local."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.preregistro_schema import ensure_preregistro_tables, insertar_preregistro_empleado
    from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

    if not session.get("modo_tablet"):
        flash("Esta pantalla solo está disponible en el modo tablet del local.", "warning")
        return redirect(public_entry_url())

    db = get_db()
    ensure_tablet_config(db)
    cfg = get_tablet_config(db)
    if not cfg.get("permitir_preregistro"):
        db.close()
        flash(
            "El preregistro de empleados no está activado. Actívalo en Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))

    if request.method == "POST":
        from reservas.empleado_fotos import guardar_foto_perfil_upload

        nombre = (request.form.get("nombre") or "").strip()
        apellido = (request.form.get("apellido") or "").strip()
        dni = (request.form.get("dni") or "").strip()
        telefono = (request.form.get("telefono") or "").strip()
        email = (request.form.get("email") or "").strip()
        puesto = (request.form.get("puesto") or "").strip()
        departamento = (request.form.get("departamento") or "").strip()
        fecha_nacimiento = (request.form.get("fecha_nacimiento") or "").strip()
        horas_contrato = (request.form.get("horas_contrato") or "").strip() or "40"
        tipo_contrato = (request.form.get("tipo_contrato") or "").strip() or "Indefinido"
        fecha_alta = (request.form.get("fecha_alta") or "").strip()
        numero_ss = (request.form.get("numero_ss") or "").strip()
        observaciones = (request.form.get("observaciones") or "").strip()
        try:
            rango_id = int(request.form.get("rango_id") or 1)
        except (TypeError, ValueError):
            rango_id = 1
        if rango_id < 1:
            rango_id = 1

        if len(nombre) < 2:
            kw = _tablet_preregistro_template_kwargs(db, request.form)
            db.close()
            flash("Indica al menos el nombre.", "warning")
            return render_template("tablet_preregistro.html", **kw)
        if len(telefono) < 5:
            kw = _tablet_preregistro_template_kwargs(db, request.form)
            db.close()
            flash("Indica un teléfono de contacto válido.", "warning")
            return render_template("tablet_preregistro.html", **kw)

        ensure_preregistro_tables(db)
        foto_rel = guardar_foto_perfil_upload(
            current_app.static_folder, request.files.get("foto_perfil")
        )
        insertar_preregistro_empleado(
            db,
            nombre=nombre,
            apellido=apellido or None,
            dni=dni or None,
            telefono=telefono,
            email=email or None,
            puesto=puesto or None,
            departamento=departamento or None,
            fecha_nacimiento=fecha_nacimiento or None,
            horas_contrato=horas_contrato,
            tipo_contrato=tipo_contrato,
            fecha_alta=fecha_alta or None,
            numero_ss=numero_ss or None,
            rango_id=rango_id,
            observaciones=observaciones or None,
            foto_perfil=foto_rel,
        )
        db.close()
        flash(
            "Solicitud enviada. RRHH o dirección la revisará; aún no tienes ficha ni PIN en el sistema.",
            "success",
        )
        return redirect(url_for("public.tablet_preregistro"))

    kw = _tablet_preregistro_template_kwargs(db, None)
    db.close()
    return render_template("tablet_preregistro.html", **kw)


@bp.route("/tablet/preregistro/gestion", methods=["GET", "POST"])
@login_requerido
def tablet_preregistro_gestion():
    """Deshabilitado en modo tablet: la revisión se hace desde el panel admin."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    flash(
        "La revisión de solicitudes de empleado es solo para administración. "
        "Hazla desde «Empleados» en el panel admin.",
        "info",
    )
    if session.get("modo_tablet"):
        return redirect(url_for("public.tablet_inicio"))
    return redirect(url_for("admin.empleados"))


@bp.route("/tablet/propinas/estadisticas", methods=["GET"])
@login_requerido
def tablet_propinas_estadisticas():
    """Totales y €/hora por persona en un rango (día, semana o mes)."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.propinas_schema import (
        ensure_propinas_tables,
        estadisticas_propinas_rango,
        rango_fechas_periodo,
    )
    from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

    if not session.get("modo_tablet"):
        flash("Esta pantalla solo está disponible en el modo tablet del local.", "warning")
        return redirect(public_entry_url())

    db = get_db()
    ensure_tablet_config(db)
    cfg = get_tablet_config(db)
    if not cfg.get("permitir_propinas"):
        db.close()
        flash(
            "El reparto de propinas no está activado. Actívalo en Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))

    ref_raw = (request.args.get("ref") or "").strip() or str(date.today())
    try:
        ref = date.fromisoformat(ref_raw[:10])
    except ValueError:
        ref = date.today()

    periodo = (request.args.get("periodo") or cfg.get("propinas_periodo_vista") or "dia").strip().lower()
    if periodo not in ("dia", "semana", "mes"):
        periodo = "dia"

    fecha_ini, fecha_fin = rango_fechas_periodo(periodo, ref)
    ensure_propinas_tables(db)
    filas = estadisticas_propinas_rango(db, fecha_ini, fecha_fin)
    db.close()

    total_eur = round(sum(f["total_propina"] for f in filas), 2)
    total_h = round(sum(f["total_horas"] for f in filas), 2)
    return render_template(
        "tablet_propinas_estadisticas.html",
        mostrar_nav=True,
        ref_iso=ref.isoformat(),
        periodo=periodo,
        fecha_ini=fecha_ini,
        fecha_fin=fecha_fin,
        filas=filas,
        total_eur=total_eur,
        total_h=total_h,
    )


@bp.route("/tablet/propinas/config", methods=["GET", "POST"])
@login_requerido
def tablet_propinas_config():
    """Parámetros de propinas (periodo estadístico y modo por defecto); requiere PIN de administrador."""
    if RESERVAS_ONLY:
        return redirect(url_for("public.tablet_inicio"))
    from reservas.tablet_config_schema import ensure_tablet_config, get_tablet_config

    if not session.get("modo_tablet"):
        flash("Esta pantalla solo está disponible en el modo tablet del local.", "warning")
        return redirect(public_entry_url())

    db = get_db()
    ensure_tablet_config(db)
    cfg = get_tablet_config(db)
    if not cfg.get("permitir_propinas"):
        db.close()
        flash(
            "El reparto de propinas no está activado. Actívalo en Servicio → Opciones del modo tablet.",
            "warning",
        )
        return redirect(url_for("public.tablet_inicio"))

    if request.method == "POST" and request.form.get("accion") == "pin_encargado":
        pin = (request.form.get("pin_encargado") or "").strip()
        ensure_tablet_schema(db)
        ok = pin_valido_admin(db, pin) if pin else False
        db.close()
        if ok:
            session["tablet_propinas_unlock_ts"] = time.time()
            session.modified = True
            flash("PIN correcto. Puedes cambiar los parámetros.", "success")
            return redirect(url_for("public.tablet_propinas_config"))
        flash("PIN incorrecto. Usa el PIN de administrador / encargado.", "danger")
        return render_template("tablet_propinas_pin.html", mostrar_nav=True)

    if not _tablet_propinas_pin_unlocked():
        db.close()
        return render_template("tablet_propinas_pin.html", mostrar_nav=True)

    if request.method == "POST":
        if not _tablet_propinas_pin_unlocked():
            db.close()
            flash("La sesión expiró. Vuelve a introducir el PIN.", "warning")
            return render_template("tablet_propinas_pin.html", mostrar_nav=True)
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
                return redirect(url_for("public.tablet_propinas_config"))
            if not lst:
                db.close()
                flash("Indica al menos una franja en modo personalizado.", "danger")
                return redirect(url_for("public.tablet_propinas_config"))
            manual_json = json.dumps([{"inicio": x["inicio"], "fin": x["fin"]} for x in lst])
        else:
            manual_json = ""
        db.execute(
            """
            UPDATE config_tablet SET
                propinas_periodo_vista = ?,
                propinas_modo_defecto = ?,
                propinas_agrupacion = ?,
                propinas_franja_horas = ?,
                propinas_franja_modo = ?,
                propinas_franjas_manual_json = ?
            WHERE id = 1
            """,
            (pv, md, ag, fh, pfm, manual_json or None),
        )
        db.commit()
        db.close()
        flash("Parámetros de propinas guardados.", "success")
        return redirect(url_for("public.tablet_propinas"))

    db.close()
    return render_template(
        "tablet_propinas_config.html",
        mostrar_nav=True,
        cfg=cfg,
    )


# =====================================================
# LOGIN ADMIN / ENCARGADO
# =====================================================

@bp.route("/login", methods=["GET", "POST"])
def login():
    """Login por tabla usuarios (usuario/contraseña en claro)."""
    if request.method == "POST":

        usuario = request.form.get("usuario")
        password = request.form.get("password")

        db = get_db()

        user = db.execute(
            """
            SELECT * FROM usuarios
            WHERE usuario=?
            """,
            (usuario,)
        ).fetchone()

        db.close()

        if user and user["password"] == password:

            session["usuario"] = user["usuario"]

            return redirect("/panel")

        else:

            return render_template(
                "login.html",
                error="Credenciales incorrectas"
            )

    return render_template("login.html", next_url=(request.args.get("next") or "").strip())
