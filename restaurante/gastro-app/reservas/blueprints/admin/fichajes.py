"""Historial, libro de firmas, PDFs y flujo de fichaje en terminal admin."""
from datetime import date

from flask import Response, abort, current_app, flash, redirect, render_template, request, session, url_for

from models import get_db
from reservas.db_helpers import columnas_tabla
from reservas.decorators import admin_requerido, login_requerido, permiso_mod
from reservas.utils import actualizar_saldo_horas, ahora_madrid

from . import bp


# =====================================================
# HISTORIAL FICHAJES
# =====================================================

@bp.route("/fichajes")
@login_requerido
def ver_fichajes():
    """Historial de fichajes: solo los del empleado logueado; en administración, todos."""
    if session.get("modo_tablet"):
        flash("El historial detallado está disponible desde un equipo con acceso de administración o empleado.", "info")
        return redirect(url_for("public.tablet_inicio"))

    empleado_sesion = session.get("empleado_id")
    solo_mios = empleado_sesion is not None
    if not solo_mios:
        from reservas.rbac_session import puede

        if not puede("mod.fichajes"):
            flash("No tienes permiso para ver el historial global de fichajes.", "warning")
            return redirect("/panel_empleado")

    db = get_db()
    cols_e = columnas_tabla(db, "empleados")
    nom = "e.nombre"
    if "apellido" in cols_e:
        nom = "e.nombre || ' ' || COALESCE(e.apellido,'')"
    sql = f"""
        SELECT {nom} AS empleado_nombre, f.empleado_id, f.fecha, f.hora, f.tipo
        FROM fichajes f
        JOIN empleados e ON e.id = f.empleado_id
        """
    if solo_mios:
        sql += " WHERE f.empleado_id = ?"
    sql += " ORDER BY f.fecha DESC, f.hora DESC"
    if solo_mios:
        registros = db.execute(sql, (empleado_sesion,)).fetchall()
    else:
        registros = db.execute(sql).fetchall()
    db.close()

    fichajes = []
    for r in registros:
        tipo = (r["tipo"] or "").strip()
        label = tipo
        if tipo == "pausa_inicio":
            label = "Inicio pausa"
        elif tipo == "pausa_fin":
            label = "Fin pausa"
        fichajes.append(
            {
                "nombre": (r["empleado_nombre"] or "").strip(),
                "fecha": r["fecha"],
                "hora": (str(r["hora"] or ""))[:8],
                "tipo": label,
            }
        )

    return render_template(
        "fichajes_historial.html",
        mostrar_nav=True,
        fichajes=fichajes,
        solo_mis_fichajes=solo_mios,
    )
# =====================================================
# AREA PERSONAL
# =====================================================
@bp.route("/libro_firmas")
@login_requerido
@permiso_mod("mod.fichajes")
def libro_firmas():
    """Libro de registro de jornada: filtro por mes y opcionalmente por empleado."""
    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
    from reservas.fichajes_libro_data import lineas_libro_tabla, registros_mes_query
    from reservas.jornada_schema import get_conformidad_mes, ensure_jornada_tables

    mes = (request.args.get("mes") or "").strip()
    if not mes:
        mes = date.today().strftime("%Y-%m")
    empleado_id = request.args.get("empleado_id", type=int)

    db = get_db()
    ensure_config_empresa_table(db)
    ensure_jornada_tables(db)
    cfg = get_config_empresa(db)

    cols_e = columnas_tabla(db, "empleados")
    registros = registros_mes_query(db, mes, empleado_id, cols_e)
    fichajes = lineas_libro_tabla(registros)

    sel_emp = "id, nombre"
    if "apellido" in cols_e:
        sel_emp += ", apellido"
    empleados = db.execute(f"SELECT {sel_emp} FROM empleados ORDER BY nombre").fetchall()

    conformidad_mes = None
    if empleado_id:
        conformidad_mes = get_conformidad_mes(db, empleado_id, mes)

    db.close()

    y, m = mes.split("-")[:2]
    meses = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    mes_etiqueta = f"{meses[int(m) - 1]} {y}"

    return render_template(
        "libro_firmas.html",
        mostrar_nav=True,
        fichajes=fichajes,
        empleados=empleados,
        mes=mes,
        mes_etiqueta=mes_etiqueta,
        empleado_id=empleado_id,
        empresa=cfg,
        conformidad_mes=conformidad_mes,
    )


@bp.route("/pdf_trabajador")
@login_requerido
@permiso_mod("mod.fichajes")
def pdf_trabajador():
    """Descarga PDF del libro de jornada de un trabajador para un mes."""
    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
    from reservas.fichajes_libro_data import lineas_pdf_empleado, registros_mes_query
    from reservas.jornada_schema import ensure_jornada_tables, get_conformidad_mes
    from reservas.pdf_libro_firmas import (
        construir_pdf_libro_empleado,
        reportlab_disponible,
        reportlab_error_detalle,
    )

    empleado_id = request.args.get("empleado_id", type=int)
    mes = (request.args.get("mes") or "").strip()
    if not empleado_id or not mes:
        abort(400, "Indica trabajador y mes")

    if not reportlab_disponible():
        det = reportlab_error_detalle()
        msg = (
            "No se pudieron cargar las librerías PDF. En el servidor: pip install reportlab pillow"
        )
        if det:
            msg += f" — {det}"
        abort(503, msg)

    db = get_db()
    ensure_config_empresa_table(db)
    ensure_jornada_tables(db)
    empresa = get_config_empresa(db)
    cols_e = columnas_tabla(db, "empleados")
    registros = registros_mes_query(db, mes, empleado_id, cols_e)
    lineas = lineas_pdf_empleado(registros)
    row_emp = db.execute("SELECT * FROM empleados WHERE id = ?", (empleado_id,)).fetchone()
    if not row_emp:
        db.close()
        abort(404)
    empleado = dict(row_emp)
    for k in ("pin", "pin_hash"):
        empleado.pop(k, None)
    conf = get_conformidad_mes(db, empleado_id, mes)
    db.close()

    y, mo = mes.split("-")[:2]
    meses = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    mes_etiqueta = f"{meses[int(mo) - 1]} {y}"
    try:
        pdf_bytes = construir_pdf_libro_empleado(
            current_app.static_folder,
            empresa,
            empleado,
            lineas,
            mes_etiqueta,
            conformidad=conf,
        )
    except RuntimeError as e:
        abort(503, str(e))

    slug = (empleado.get("nombre") or "empleado").replace(" ", "_")[:40]
    fname = f"libro_jornada_{slug}_{mes}.pdf"
    return Response(
        pdf_bytes,
        mimetype="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@bp.route("/generar_pdf_mensual")
@login_requerido
@permiso_mod("mod.fichajes")
def generar_pdf_mensual():
    """ZIP con un PDF por trabajador que tenga fichajes en el mes."""
    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
    from reservas.fichajes_libro_data import lineas_pdf_empleado, registros_mes_query
    from reservas.jornada_schema import ensure_jornada_tables, get_conformidad_mes
    from reservas.pdf_libro_firmas import (
        reportlab_disponible,
        reportlab_error_detalle,
        zip_pdfs_trabajadores_mes,
    )

    mes = (request.args.get("mes") or "").strip()
    if not mes:
        abort(400, "Indica el mes")

    if not reportlab_disponible():
        det = reportlab_error_detalle()
        msg = "No se pudieron cargar las librerías PDF. pip install reportlab pillow"
        if det:
            msg += f" — {det}"
        abort(503, msg)

    db = get_db()
    ensure_config_empresa_table(db)
    ensure_jornada_tables(db)
    empresa = get_config_empresa(db)
    cols_e = columnas_tabla(db, "empleados")

    ids = [
        r[0]
        for r in db.execute(
            """
            SELECT DISTINCT empleado_id FROM fichajes
            WHERE strftime('%Y-%m', fecha) = ?
            ORDER BY empleado_id
            """,
            (mes,),
        ).fetchall()
    ]
    y, mo = mes.split("-")[:2]
    meses = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    mes_etiqueta = f"{meses[int(mo) - 1]} {y}"

    empleados_lineas = []
    for eid in ids:
        regs = registros_mes_query(db, mes, eid, cols_e)
        row_emp = db.execute("SELECT * FROM empleados WHERE id = ?", (eid,)).fetchone()
        if not row_emp:
            continue
        emp = dict(row_emp)
        for k in ("pin", "pin_hash"):
            emp.pop(k, None)
        lineas = lineas_pdf_empleado(regs)
        conf = get_conformidad_mes(db, eid, mes)
        empleados_lineas.append((emp, lineas, conf))

    db.close()

    if not empleados_lineas:
        abort(404, "No hay fichajes en ese mes")

    try:
        zip_bytes = zip_pdfs_trabajadores_mes(
            current_app.static_folder,
            empresa,
            empleados_lineas,
            mes_etiqueta,
        )
    except RuntimeError as e:
        abort(503, str(e))

    return Response(
        zip_bytes,
        mimetype="application/zip",
        headers={"Content-Disposition": f'attachment; filename="libros_firmas_{mes}.zip"'},
    )
@bp.route("/fichaje")
@login_requerido
def fichaje():
    """Pantalla de introducción de PIN para fichaje."""

    return render_template(
        "fichaje.html",
        mostrar_nav=True
    )

# =====================================================
# FICHAR (IDENTIFICAR EMPLEADO)
# =====================================================

def _norm_tipo_fichaje(t: str | None) -> str:
    return (t or "").strip().lower()


def _estado_fichaje_dia(db, empleado_id: int, fecha: str) -> dict:
    """Estado del fichaje para un día: entrada/salida/pausas (art. 34.9 ET)."""
    rows = db.execute(
        """
        SELECT tipo, hora FROM fichajes
        WHERE empleado_id = ? AND fecha = ?
        ORDER BY hora ASC
        """,
        (empleado_id, fecha),
    ).fetchall()
    tipos_raw = [r["tipo"] for r in rows]
    tipos_n = [_norm_tipo_fichaje(t) for t in tipos_raw]
    tiene_entrada = "entrada" in tipos_n
    tiene_salida = "salida" in tipos_n
    pausa_abierta = False
    for r in rows:
        t = _norm_tipo_fichaje(r["tipo"])
        if t in ("pausa_inicio", "pausa"):
            if not pausa_abierta:
                pausa_abierta = True
        elif t in ("pausa_fin", "fin_pausa"):
            pausa_abierta = False
        elif t == "salida":
            pausa_abierta = False
    puede_entrada = not tiene_entrada
    en_jornada = tiene_entrada and not tiene_salida
    puede_pausa_inicio = en_jornada and not pausa_abierta
    puede_pausa_fin = en_jornada and pausa_abierta
    puede_salida = en_jornada and not pausa_abierta
    return {
        "puede_entrada": puede_entrada,
        "puede_salida": puede_salida,
        "puede_pausa_inicio": puede_pausa_inicio,
        "puede_pausa_fin": puede_pausa_fin,
        "tiene_entrada": tiene_entrada,
        "tiene_salida": tiene_salida,
        "pausa_abierta": pausa_abierta,
        "tipos": tipos_raw,
    }


@bp.route("/fichar", methods=["POST"])
@login_requerido
def fichar():
    """Valida PIN de empleado y muestra confirmación de fichaje."""

    pin = request.form.get("pin")

    if not pin:
        return render_template(
            "fichaje.html",
            mostrar_nav=True,
            mensaje_error="Introduce tu PIN.",
        )

    pin = str(pin).strip()

    db = get_db()

    cols_e = columnas_tabla(db, "empleados")
    sel_emp = "id, nombre, apellido" if "apellido" in cols_e else "id, nombre"
    empleado = db.execute(
        f"SELECT {sel_emp} FROM empleados WHERE TRIM(pin) = ?",
        (pin,),
    ).fetchone()

    if not empleado:
        db.close()
        return render_template(
            "fichaje.html",
            mostrar_nav=True,
            mensaje_error="PIN incorrecto. Vuelve a intentarlo.",
        )

    ahora = ahora_madrid()
    fecha_hoy = ahora.strftime("%Y-%m-%d")
    st = _estado_fichaje_dia(db, empleado["id"], fecha_hoy)
    db.close()

    nombre_completo = (empleado["nombre"] or "").strip()
    if "apellido" in empleado.keys() and empleado["apellido"]:
        nombre_completo = f"{nombre_completo} {(empleado['apellido'] or '').strip()}".strip()

    return render_template(
        "fichaje_confirmar.html",
        mostrar_nav=True,
        nombre=empleado["nombre"] or "Empleado",
        nombre_completo=nombre_completo or "Empleado",
        empleado_id=empleado["id"],
        puede_entrada=st["puede_entrada"],
        puede_salida=st["puede_salida"],
        puede_pausa_inicio=st["puede_pausa_inicio"],
        puede_pausa_fin=st["puede_pausa_fin"],
        pausa_abierta=st["pausa_abierta"],
        hora_servidor=ahora.strftime("%H:%M"),
        fecha_hoy=fecha_hoy,
    )

# =====================================================
# CONFIRMAR FICHAJE
# =====================================================

def _nombre_empleado_display(db, empleado_id) -> str:
    cols_e = columnas_tabla(db, "empleados")
    sel = "nombre, apellido" if "apellido" in cols_e else "nombre"
    row = db.execute(f"SELECT {sel} FROM empleados WHERE id = ?", (empleado_id,)).fetchone()
    if not row:
        return ""
    n = (row["nombre"] or "").strip()
    if "apellido" in row.keys() and row["apellido"]:
        n = f"{n} {(row['apellido'] or '').strip()}".strip()
    return n or "Empleado"


@bp.route("/confirmar_fichaje", methods=["POST"])
@login_requerido
def confirmar_fichaje():
    """Registra entrada, salida o pausas con validaciones del día."""

    empleado_id = request.form.get("empleado_id")
    tipo_raw = request.form.get("tipo")
    tipo = _norm_tipo_fichaje(tipo_raw)

    if not empleado_id or tipo not in ("entrada", "salida", "pausa_inicio", "pausa_fin"):
        return render_template(
            "fichaje.html",
            mostrar_nav=True,
            mensaje_error="Solicitud no válida. Vuelve a identificarte.",
        )

    try:
        empleado_id = int(empleado_id)
    except (TypeError, ValueError):
        return render_template(
            "fichaje.html",
            mostrar_nav=True,
            mensaje_error="Solicitud no válida. Vuelve a identificarte.",
        )

    ahora = ahora_madrid()
    fecha = ahora.strftime("%Y-%m-%d")
    hora = ahora.strftime("%H:%M:%S")
    hora_corta = ahora.strftime("%H:%M")

    db = get_db()
    st = _estado_fichaje_dia(db, empleado_id, fecha)
    nombre_display = _nombre_empleado_display(db, empleado_id)

    def _insert(tipo_db: str):
        db.execute(
            """
            INSERT INTO fichajes (empleado_id, fecha, hora, tipo)
            VALUES (?, ?, ?, ?)
            """,
            (empleado_id, fecha, hora, tipo_db),
        )
        db.commit()
        actualizar_saldo_horas()

    if tipo == "entrada":
        if not st["puede_entrada"]:
            db.close()
            return render_template(
                "fichaje.html",
                mostrar_nav=True,
                mensaje_error="Ya consta tu entrada de hoy.",
            )
        _insert("entrada")
        db.close()
        return render_template(
            "fichaje_exito.html",
            mostrar_nav=True,
            nombre=nombre_display,
            tipo_fichaje="entrada",
            hora=hora_corta,
            fecha=fecha,
        )

    if tipo == "pausa_inicio":
        if not st["puede_pausa_inicio"]:
            db.close()
            return render_template(
                "fichaje.html",
                mostrar_nav=True,
                mensaje_error="No puedes iniciar una pausa ahora (revisa entrada, salida o pausa abierta).",
            )
        _insert("pausa_inicio")
        db.close()
        return render_template(
            "fichaje_exito.html",
            mostrar_nav=True,
            nombre=nombre_display,
            tipo_fichaje="pausa_inicio",
            hora=hora_corta,
            fecha=fecha,
        )

    if tipo == "pausa_fin":
        if not st["puede_pausa_fin"]:
            db.close()
            return render_template(
                "fichaje.html",
                mostrar_nav=True,
                mensaje_error="No hay una pausa abierta para cerrar.",
            )
        _insert("pausa_fin")
        db.close()
        return render_template(
            "fichaje_exito.html",
            mostrar_nav=True,
            nombre=nombre_display,
            tipo_fichaje="pausa_fin",
            hora=hora_corta,
            fecha=fecha,
        )

    if tipo == "salida":
        if not st["puede_salida"]:
            db.close()
            if not st["tiene_entrada"]:
                msg = "No hay entrada registrada hoy. Ficha entrada primero."
            elif st["tiene_salida"]:
                msg = "Ya consta tu salida de hoy."
            else:
                msg = "Cierra la pausa de descanso antes de fichar la salida."
            return render_template(
                "fichaje.html",
                mostrar_nav=True,
                mensaje_error=msg,
            )
        _insert("salida")
        db.close()
        return render_template(
            "fichaje_exito.html",
            mostrar_nav=True,
            nombre=nombre_display,
            tipo_fichaje="salida",
            hora=hora_corta,
            fecha=fecha,
        )

    db.close()
    return render_template(
        "fichaje.html",
        mostrar_nav=True,
        mensaje_error="Tipo de fichaje no reconocido.",
    )
