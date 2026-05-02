"""Panel, búsqueda global y perfil de empleado (vista admin)."""
from datetime import date, timedelta
from urllib.parse import quote

from flask import current_app, flash, redirect, render_template, request, session, url_for

from config import RESERVAS_ONLY
from models import get_db
from reservas.db_helpers import tabla_existe
from reservas.decorators import admin_requerido, login_requerido, permiso_mod
from reservas.i18n import get_locale

from . import bp

_MESES = {
    "es": (
        "ene.",
        "feb.",
        "mar.",
        "abr.",
        "may.",
        "jun.",
        "jul.",
        "ago.",
        "sep.",
        "oct.",
        "nov.",
        "dic.",
    ),
    "ca": (
        "gen.",
        "febr.",
        "març",
        "abr.",
        "maig",
        "juny",
        "jul.",
        "ag.",
        "set.",
        "oct.",
        "nov.",
        "des.",
    ),
    "en": (
        "Jan",
        "Feb",
        "Mar",
        "Apr",
        "May",
        "Jun",
        "Jul",
        "Aug",
        "Sep",
        "Oct",
        "Nov",
        "Dec",
    ),
}
_DIAS = {
    "es": ("lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom."),
    "ca": ("dl.", "dt.", "dc.", "dj.", "dv.", "ds.", "dg."),
    "en": ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"),
}


def _fecha_display_panel(d: date) -> str:
    """Fecha corta según idioma de la interfaz (sesión)."""
    loc = get_locale()
    if loc in ("ca", "va"):
        meses, dias = _MESES["ca"], _DIAS["ca"]
    else:
        meses, dias = _MESES.get(loc) or _MESES["es"], _DIAS.get(loc) or _DIAS["es"]
    return f"{dias[d.weekday()]} {d.day} {meses[d.month - 1]} {d.year}"


def _columnas_tabla(db, tabla):
    """Nombres de columnas de una tabla (para SQL compatible con esquemas antiguos o ampliados)."""
    return {r[1] for r in db.execute(f"PRAGMA table_info({tabla})").fetchall()}


def _reservas_por_dia_ultimos_7(db) -> list[dict]:
    """Serie diaria (más antigua → hoy) para mini gráfico del panel."""
    rows: list[dict] = []
    for i in range(6, -1, -1):
        d = date.today() - timedelta(days=i)
        ds = d.isoformat()
        n = db.execute(
            """
            SELECT COUNT(*) FROM reservas
            WHERE fecha = ?
              AND COALESCE(estado, '') NOT IN ('Cancelada', 'Cancelado', 'Anulada', 'Anulado')
            """,
            (ds,),
        ).fetchone()[0]
        rows.append({"date": ds, "label": str(d.day), "n": int(n or 0)})
    return rows


def _dash_web_stats_resumen() -> dict | None:
    """KPIs web 7d vía Next (visitas) + reservas desde SQLite Gastro."""
    try:
        from reservas.clavo_stats_reservas_gastro import reservas_stats_para_clavo_panel
        from reservas.next_site_http import next_site_internal_secret, next_site_request

        if not next_site_internal_secret():
            return None
        code, data, _ = next_site_request("GET", "/api/internal/clavo-stats?days=7", timeout=12)
        if code != 200 or not isinstance(data, dict):
            return None
        pv = data.get("pageViews") if isinstance(data.get("pageViews"), dict) else {}
        db = get_db()
        try:
            rv = reservas_stats_para_clavo_panel(db, 7)
        finally:
            db.close()
        return {
            "visits_7d": int(pv.get("total7d") or 0),
            "reservas_7d": int(rv.get("total7d") or 0),
            "pv_err": bool(pv.get("dbError")),
            "rv_err": False,
        }
    except Exception:
        return None


@bp.route("/panel")
@login_requerido
@permiso_mod("mod.panel")
def panel():
    """Panel principal del administrador con KPIs del día."""
    hoy = str(date.today())
    db = get_db()

    reservas_hoy = db.execute(
        "SELECT COUNT(*) FROM reservas WHERE fecha = ?",
        (hoy,),
    ).fetchone()[0]

    mesas_ocupadas = db.execute(
        """
        SELECT COUNT(DISTINCT mesa) FROM reservas
        WHERE fecha = ?
          AND mesa IS NOT NULL AND TRIM(mesa) != ''
          AND COALESCE(estado, '') NOT IN ('Cancelada')
        """,
        (hoy,),
    ).fetchone()[0]

    cols_emp = _columnas_tabla(db, "empleados")
    if RESERVAS_ONLY:
        empleados_activos = 0
        fichajes_hoy = 0
    else:
        if "activo" in cols_emp:
            empleados_activos = db.execute(
                "SELECT COUNT(*) FROM empleados WHERE activo = 1"
            ).fetchone()[0]
        else:
            empleados_activos = db.execute(
                "SELECT COUNT(*) FROM empleados"
            ).fetchone()[0]

        fichajes_hoy = db.execute(
            "SELECT COUNT(*) FROM fichajes WHERE fecha = ?",
            (hoy,),
        ).fetchone()[0]

    reservas_recientes = [
        dict(r)
        for r in db.execute(
            """
            SELECT id, nombre, hora, personas, COALESCE(mesa, '') AS mesa,
                   COALESCE(estado, '') AS estado
            FROM reservas
            WHERE fecha = ?
            ORDER BY id DESC
            LIMIT 6
            """,
            (hoy,),
        ).fetchall()
    ]

    fichajes_recientes = []
    if not RESERVAS_ONLY:
        cols_f = _columnas_tabla(db, "fichajes")
        join_apellido = "apellido" in _columnas_tabla(db, "empleados")
        if join_apellido:
            nombre_expr = "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
        else:
            nombre_expr = "COALESCE(e.nombre, '')"
        if "empleado_id" in cols_f:
            fichajes_recientes = [
                dict(r)
                for r in db.execute(
                    f"""
                    SELECT f.hora, COALESCE(f.tipo, '') AS tipo, {nombre_expr} AS empleado
                    FROM fichajes f
                    LEFT JOIN empleados e ON e.id = f.empleado_id
                    WHERE f.fecha = ?
                    ORDER BY f.id DESC
                    LIMIT 6
                    """,
                    (hoy,),
                ).fetchall()
            ]

    equipo_turno_hoy = []
    if (not RESERVAS_ONLY) and tabla_existe(db, "horarios"):
        cols_h = _columnas_tabla(db, "horarios")
        join_apellido = "apellido" in cols_emp
        if join_apellido:
            nombre_h = "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
        else:
            nombre_h = "COALESCE(e.nombre, '')"
        filtro_estado = ""
        if "estado" in cols_h:
            filtro_estado = (
                " AND TRIM(COALESCE(h.estado, '')) NOT IN "
                "('Cancelado', 'Cancelada', 'Anulado', 'Anulada') "
            )
        try:
            equipo_turno_hoy = [
                dict(r)
                for r in db.execute(
                    f"""
                    SELECT
                        h.id,
                        h.empleado_id,
                        {nombre_h} AS empleado,
                        COALESCE(e.puesto, '') AS puesto,
                        h.hora_inicio,
                        h.hora_fin,
                        COALESCE(h.turno, '') AS turno
                    FROM horarios h
                    LEFT JOIN empleados e ON e.id = h.empleado_id
                    WHERE h.fecha = ?{filtro_estado}
                    ORDER BY h.hora_inicio, empleado
                    """,
                    (hoy,),
                ).fetchall()
            ]
        except Exception:
            equipo_turno_hoy = []

    n_alertas_stock = 0
    if not RESERVAS_ONLY:
        try:
            from reservas.stock_schema import contar_alertas_stock, ensure_stock_schema

            ensure_stock_schema(db)
            n_alertas_stock = contar_alertas_stock(db)
        except Exception:
            pass

    n_rrhh_msg_pend = 0
    n_rrhh_sol_pend = 0
    if not RESERVAS_ONLY:
        try:
            from reservas.rrhh_peticiones_schema import contar_pendientes_admin, ensure_rrhh_peticiones_schema

            ensure_rrhh_peticiones_schema(db)
            n_rrhh_msg_pend, n_rrhh_sol_pend = contar_pendientes_admin(db)
        except Exception:
            pass

    reservas_7d_series = _reservas_por_dia_ultimos_7(db)

    db.close()

    hoy_date = date.fromisoformat(hoy)
    dash_web_stats = _dash_web_stats_resumen()

    return render_template(
        "panel.html",
        mostrar_nav=True,
        reservas_hoy=reservas_hoy,
        mesas_ocupadas=mesas_ocupadas,
        empleados_activos=empleados_activos,
        fichajes_hoy=fichajes_hoy,
        n_alertas_stock=n_alertas_stock,
        n_rrhh_msg_pend=n_rrhh_msg_pend,
        n_rrhh_sol_pend=n_rrhh_sol_pend,
        n_rrhh_pend_total=(n_rrhh_msg_pend or 0) + (n_rrhh_sol_pend or 0),
        fecha_hoy=hoy,
        fecha_display=_fecha_display_panel(hoy_date),
        reservas_recientes=reservas_recientes,
        fichajes_recientes=fichajes_recientes,
        equipo_turno_hoy=equipo_turno_hoy,
        reservas_7d_series=reservas_7d_series,
        dash_web_stats=dash_web_stats,
    )

# =====================================================
# BUSCADOR GLOBAL
# =====================================================

@bp.route("/buscar_global")
@login_requerido
def buscar_global():
    """Busca empleado por nombre/apellido o reserva por nombre/teléfono y redirige."""

    q = request.args.get("q", "").strip()

    if not q:
        if session.get("modo_tablet"):
            return redirect(url_for("public.tablet_inicio"))
        return redirect("/panel")

    # Modo tablet: solo reservas (no fichas de empleado ni panel admin).
    if session.get("modo_tablet"):
        return redirect(f"/reservas?buscar={quote(q, safe='')}")

    db = get_db()
    like = f"%{q}%"

    try:
        if not RESERVAS_ONLY:
            empleado = db.execute(
                """
                SELECT id
                FROM empleados
                WHERE nombre LIKE ?
                   OR apellido LIKE ?
                LIMIT 1
                """,
                (like, like),
            ).fetchone()

            if empleado:
                return redirect(f"/empleado/{empleado['id']}")

            if "telefono" in _columnas_tabla(db, "empleados"):
                empleado_tel = db.execute(
                    "SELECT id FROM empleados WHERE telefono LIKE ? LIMIT 1",
                    (like,),
                ).fetchone()
                if empleado_tel:
                    return redirect(f"/empleado/{empleado_tel['id']}")

        reserva = db.execute(
            """
            SELECT id FROM reservas
            WHERE nombre LIKE ? OR telefono LIKE ?
            ORDER BY fecha DESC, hora DESC
            LIMIT 1
            """,
            (like, like),
        ).fetchone()

        if reserva:
            return redirect(f"/reservas?buscar={quote(q, safe='')}")
    finally:
        db.close()

    return redirect("/panel")

# =====================================================
# PERFIL DE EMPLEADO
# =====================================================

@bp.route("/empleado/<int:id>")
@login_requerido
@permiso_mod("mod.empleados")
def perfil_empleado(id):
    """Ficha de empleado para gerencia: datos, fichajes, horarios y solicitudes RRHH."""

    hoy = str(date.today())
    db = get_db()

    empleado = db.execute(
        "SELECT * FROM empleados WHERE id=?",
        (id,),
    ).fetchone()

    if not empleado:
        db.close()
        return redirect("/empleados")

    empleado = dict(empleado)

    horas_hoy = db.execute(
        """
        SELECT COUNT(*)
        FROM fichajes
        WHERE empleado_id=? AND fecha=?
        """,
        (id, hoy),
    ).fetchone()[0]

    horas_semana = db.execute(
        """
        SELECT COUNT(*)
        FROM fichajes
        WHERE empleado_id=?
        AND fecha >= date('now','-7 days')
        """,
        (id,),
    ).fetchone()[0]

    dias_trabajados = db.execute(
        """
        SELECT COUNT(DISTINCT fecha)
        FROM fichajes
        WHERE empleado_id=?
        """,
        (id,),
    ).fetchone()[0]

    solicitudes = []
    if tabla_existe(db, "solicitudes"):
        solicitudes = [
            dict(x)
            for x in db.execute(
                """
                SELECT * FROM solicitudes
                WHERE empleado_id=?
                ORDER BY id DESC LIMIT 25
                """,
                (id,),
            ).fetchall()
        ]

    semanas_horario = []
    if (not RESERVAS_ONLY) and tabla_existe(db, "horarios"):
        from reservas.blueprints.admin.horarios import matriz_semanal_empleado

        hoy_d = date.today()
        lun0 = hoy_d - timedelta(days=hoy_d.weekday())
        for w in range(6):
            lun = lun0 + timedelta(weeks=w)
            dom = lun + timedelta(days=6)
            semanas_horario.append(matriz_semanal_empleado(db, lun, dom, id))

    ultimos_fichajes = [
        dict(x)
        for x in db.execute(
            """
            SELECT fecha, hora, tipo FROM fichajes
            WHERE empleado_id=?
            ORDER BY fecha DESC, hora DESC
            LIMIT 15
            """,
            (id,),
        ).fetchall()
    ]

    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
    from reservas.vacaciones_fichaje import resumen_jornada_vacaciones

    ensure_config_empresa_table(db)
    cfg_emp = get_config_empresa(db)
    jornada_vacaciones = resumen_jornada_vacaciones(
        db, id, cfg_emp, empleado.get("fecha_alta"), empleado.get("horas_contrato")
    )

    db.close()

    mes_actual = date.today().strftime("%Y-%m")

    return render_template(
        "perfil_empleado.html",
        mostrar_nav=True,
        empleado=empleado,
        horas_hoy=horas_hoy,
        horas_semana=horas_semana,
        dias_trabajados=dias_trabajados,
        solicitudes=solicitudes,
        semanas_horario=semanas_horario,
        ultimos_fichajes=ultimos_fichajes,
        mes_actual=mes_actual,
        jornada_vacaciones=jornada_vacaciones,
    )


@bp.route("/configuracion_empresa", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.empresa")
def configuracion_empresa():
    """Datos del establecimiento, rangos y SMTP (reservas + cierre de caja)."""
    from reservas.cierre_caja_mail import smtp_config_valida
    from reservas.cierre_caja_schema import (
        ensure_cierre_caja_tables,
        get_config_cierre_caja,
        save_config_cierre_caja,
    )
    from reservas.empresa_config import (
        ensure_config_empresa_table,
        get_config_empresa,
        save_config_empresa_form,
        save_logo_empresa,
        update_logo_path,
    )

    db = get_db()
    ensure_config_empresa_table(db)
    ensure_cierre_caja_tables(db)

    if request.method == "POST":
        save_config_empresa_form(
            db,
            request.form,
            only_update_present_keys=bool(RESERVAS_ONLY),
        )
        if any(
            k in request.form
            for k in ("email_destino", "smtp_host", "smtp_port", "smtp_usuario", "smtp_password", "smtp_tls")
        ):
            save_config_cierre_caja(db, request.form)
        logo = request.files.get("logo")
        if logo and getattr(logo, "filename", None):
            rel = save_logo_empresa(current_app.static_folder, logo)
            if rel:
                update_logo_path(db, rel)
            else:
                flash("El logo no se pudo guardar (usa PNG, JPG o WebP, máximo 2 MB).", "warning")
        flash("Configuración guardada correctamente.", "success")
        db.close()
        return redirect(url_for("admin.configuracion_empresa"))

    cfg = get_config_empresa(db)
    cfg_cierre = get_config_cierre_caja(db)
    smtp_ok = smtp_config_valida(cfg_cierre)
    db.close()
    return render_template(
        "configuracion_empresa.html",
        mostrar_nav=True,
        config=cfg,
        cfg_cierre=cfg_cierre,
        smtp_ok=smtp_ok,
        reservas_only=RESERVAS_ONLY,
    )
