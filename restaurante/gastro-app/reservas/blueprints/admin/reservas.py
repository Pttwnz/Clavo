"""Gestión de reservas (listado, CRUD, estados)."""
from datetime import date, datetime, timedelta
from urllib.parse import urlparse

from flask import current_app, flash, jsonify, redirect, render_template, request, session

from models import get_db
from reservas.clientes_schema import (
    ensure_clientes_schema,
    upsert_cliente_desde_reserva,
    vincular_reserva_a_cliente,
)
from reservas.decorators import permiso_reservas, permiso_reservas_api
from reservas.db_helpers import tabla_existe
from reservas.salon_helpers import (
    ensure_salon_tables,
    list_objetos_mesas_esquema_activo,
    list_uniones_esquema_activo,
    mesas_para_mapa_reservas,
    seed_salon_if_empty,
)
from auth import verificar_pin
from reservas.utils import (
    MARGEN_SOLAPAMIENTO_MESA_SEG,
    ahora_madrid,
    color_estado,
    mesa_tiene_conflicto_horario,
    normalizar_nombre_mesa,
    ocupacion_mesas_por_fecha,
    turno_de_hora,
)
from reservas.web_reservas_logic import normalizar_telefono

from . import bp

WALKIN_MAX_HORAS = 3


def _safe_visualizar_next(raw: str) -> str | None:
    """Solo permite volver a sala en vivo (misma app, path /visualizar)."""
    s = (raw or "").strip()
    if not s.startswith("/") or s.startswith("//"):
        return None
    if "://" in s:
        return None
    path = (urlparse(s).path or "").rstrip("/") or "/"
    if path != "/visualizar":
        return None
    return s


def _es_walkin(row) -> bool:
    notas = (row.get("notas") if isinstance(row, dict) else row["notas"]) or ""
    return "walk-in" in str(notas).strip().lower()


# =====================================================
# RESERVAS
# =====================================================

@bp.route("/reservas")
@permiso_reservas
def reservas():
    """Listado y mapa de reservas por fecha, búsqueda o todas."""

    fecha = request.args.get("fecha")
    buscar = request.args.get("buscar")
    todas = request.args.get("todas")
    error = request.args.get("error")

    if not fecha:
        fecha = str(date.today())

    ayer = str(date.fromisoformat(fecha) - timedelta(days=1))
    manana = str(date.fromisoformat(fecha) + timedelta(days=1))
    hoy = str(date.today())

    db = get_db()

    ensure_salon_tables(db)
    ensure_clientes_schema(db)
    seed_salon_if_empty(db)

    # -----------------------------
    # OBTENER RESERVAS
    # -----------------------------

    if buscar:

        reservas_db = db.execute(
            """
            SELECT *
            FROM reservas
            WHERE nombre LIKE ?
            OR telefono LIKE ?
            ORDER BY fecha, hora
            """,
            (f"%{buscar}%", f"%{buscar}%")
        ).fetchall()

    elif todas:

        reservas_db = db.execute(
            """
            SELECT *
            FROM reservas
            ORDER BY fecha, hora
            """
        ).fetchall()

    else:

        reservas_db = db.execute(
            """
            SELECT *
            FROM reservas
            WHERE fecha = ?
            ORDER BY hora
            """,
            (fecha,)
        ).fetchall()

    # Estados de reservas para el mapa

    reservas_estado = db.execute(
        """
        SELECT mesa, estado
        FROM reservas
        WHERE fecha = ?
        """,
        (fecha,)
    ).fetchall()

    mesas = mesas_para_mapa_reservas(db, current_app.static_folder)

    ocupacion_mesas_dia = ocupacion_mesas_por_fecha(db, fecha)

    db.close()

    estado_dict = {
        r["mesa"]: r["estado"]
        for r in reservas_estado
    }

    # -----------------------------
    # CONTADORES
    # -----------------------------

    reservas_manana = []
    reservas_mediodia = []
    reservas_noche = []
    reservas_todas = []

    pendientes = 0
    confirmadas = 0
    llegadas = 0
    finalizadas = 0
    canceladas = 0

    # -----------------------------
    # FUNCIÓN TIEMPO EN MESA
    # -----------------------------

    from datetime import datetime

    def tiempo_en_mesa(hora_llegada):

        if not hora_llegada:
            return ""

        try:

            llegada = datetime.fromisoformat(
                hora_llegada
            )

            ahora = ahora_madrid()

            diff = ahora - llegada

            horas = diff.seconds // 3600
            minutos = (diff.seconds % 3600) // 60

            return f"{horas:02}:{minutos:02}"

        except:

            return ""

    # -----------------------------
    # PROCESAR RESERVAS
    # -----------------------------

    walkins_expirados = []
    ahora = ahora_madrid()
    for r in reservas_db:

        estado = r["estado"] or "Pendiente"

        # Contadores

        if estado == "Pendiente":
            pendientes += 1

        elif estado == "Confirmada":
            confirmadas += 1

        elif "Lleg" in estado:
            llegadas += 1

        elif estado == "Finalizada":
            finalizadas += 1

        elif estado == "Cancelada":
            canceladas += 1

        reserva = {
            "id": r["id"],
            "nombre": r["nombre"],
            "telefono": r["telefono"],
            "personas": r["personas"],
            "fecha": r["fecha"],
            "hora": r["hora"],
            "notas": r["notas"],
            "mesa": r["mesa"],
            "estado": estado,
            "color": color_estado(estado),
            "hora_llegada": r["hora_llegada"],
            "tiempo_mesa": tiempo_en_mesa(
                r["hora_llegada"]
            ),
            "cliente_id": (
                int(r["cliente_id"])
                if "cliente_id" in r.keys() and r["cliente_id"] is not None and int(r["cliente_id"]) > 0
                else None
            ),
        }
        reservas_todas.append(reserva)

        if (
            _es_walkin(r)
            and ("Lleg" in estado)
            and r["hora_llegada"]
        ):
            try:
                hl = datetime.fromisoformat(str(r["hora_llegada"]))
                if (ahora - hl) >= timedelta(hours=WALKIN_MAX_HORAS):
                    walkins_expirados.append(
                        {
                            "id": r["id"],
                            "nombre": r["nombre"] or "Walk-in",
                            "mesa": r["mesa"] or "-",
                            "hora": r["hora"] or "",
                            "fecha": r["fecha"] or "",
                            "tiempo_mesa": tiempo_en_mesa(r["hora_llegada"]),
                        }
                    )
            except Exception:
                pass

        turno = turno_de_hora(r["hora"])

        if turno == "manana":

            reservas_manana.append(reserva)

        elif turno == "mediodia":

            reservas_mediodia.append(reserva)

        else:

            reservas_noche.append(reserva)

    # -----------------------------
    # RENDER
    # -----------------------------

    return render_template(
        "reservas.html",
        mostrar_nav=True,
        fecha=fecha,
        ayer=ayer,
        hoy=hoy,
        manana=manana,
        error=error,
        reservas_manana=reservas_manana,
        reservas_mediodia=reservas_mediodia,
        reservas_noche=reservas_noche,
        reservas_todas=reservas_todas,
        walkins_expirados=walkins_expirados,
        todas_activo=bool(todas),
        mesas=mesas,
        total=len(reservas_db),
        pendientes=pendientes,
        confirmadas=confirmadas,
        llegadas=llegadas,
        finalizadas=finalizadas,
        canceladas=canceladas,
        margen_solapamiento_mesa_seg=MARGEN_SOLAPAMIENTO_MESA_SEG,
        ocupacion_mesas_dia=ocupacion_mesas_dia,
    )


@bp.route("/api/ocupacion_mesas")
@permiso_reservas_api
def api_ocupacion_mesas():
    """JSON: mesa -> [hora, ...] reservas que bloquean la mesa ese día (para filtrar el desplegable)."""
    fecha = (request.args.get("fecha") or "").strip()
    excl = request.args.get("exclude_reserva_id", type=int)
    if not fecha:
        return jsonify({})
    db = get_db()
    ensure_salon_tables(db)
    occ = ocupacion_mesas_por_fecha(db, fecha, excluir_reserva_id=excl)
    db.close()
    return jsonify(occ)


@bp.route("/api/sugerencias_union_mesa")
@permiso_reservas_api
def api_sugerencias_union_mesa():
    """
    Si pax >= umbral configurado y no hay mesa individual libre (capacidad + solape),
    devuelve uniones guardadas en el esquema activo que admitan ese aforo y estén libres.
    """
    min_pax_u = int(current_app.config.get("SUGERENCIA_UNION_DESDE_PAX") or 8)
    pax = request.args.get("pax", type=int) or 0
    fecha = (request.args.get("fecha") or "").strip()
    hora = (request.args.get("hora") or "").strip()
    excl = request.args.get("exclude_reserva_id", type=int)
    if not fecha or not hora:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    if pax < min_pax_u:
        return jsonify(
            {
                "ok": True,
                "activo": False,
                "motivo": "pax_bajo",
                "min_pax": min_pax_u,
                "uniones": [],
            }
        )

    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)

    for m in list_objetos_mesas_esquema_activo(db):
        try:
            cap = int(m["capacidad"] or 4)
        except (TypeError, ValueError):
            cap = 4
        if cap < pax:
            continue
        nom = (m["nombre"] or "").strip()
        if not nom:
            continue
        if not mesa_tiene_conflicto_horario(
            db, fecha, nom, hora, excluir_reserva_id=excl
        ):
            db.close()
            return jsonify(
                {
                    "ok": True,
                    "activo": False,
                    "motivo": "mesa_fisica_ok",
                    "min_pax": min_pax_u,
                    "uniones": [],
                }
            )

    sug: list[dict] = []
    for u in list_uniones_esquema_activo(db):
        try:
            cap_u = int(u.get("capacidad_total") or 0)
        except (TypeError, ValueError):
            cap_u = 0
        if cap_u < pax:
            continue
        nom = (u.get("nombre") or "").strip()
        if not nom:
            continue
        if mesa_tiene_conflicto_horario(
            db, fecha, nom, hora, excluir_reserva_id=excl
        ):
            continue
        sug.append({"nombre": nom, "capacidad": cap_u})

    db.close()
    sug.sort(key=lambda x: (x["capacidad"], x["nombre"].lower()))
    return jsonify(
        {
            "ok": True,
            "activo": bool(sug),
            "motivo": "sin_mesa_suelta" if sug else "sin_opciones",
            "min_pax": min_pax_u,
            "uniones": sug[:12],
        }
    )


# =====================================================
# CREAR RESERVA
# =====================================================

@bp.route("/crear", methods=["POST"])
@permiso_reservas
def crear():
    """Crea una reserva validando solapamiento de mesa en la misma hora."""
    fecha = request.form.get("fecha")
    nombre = request.form.get("nombre")
    telefono = request.form.get("telefono")
    personas = request.form.get("personas")
    hora = request.form.get("hora")
    mesa = request.form.get("mesa")
    notas = request.form.get("notas")
    
    if not all([nombre, telefono, personas, fecha, hora, mesa]):
        return redirect(f"/reservas?fecha={fecha}&error=campos")
    
    db = get_db()
    ensure_clientes_schema(db)

    try:
        datetime.strptime(hora, "%H:%M")
    except (TypeError, ValueError):
        db.close()
        return redirect(f"/reservas?fecha={fecha}&error=campos")

    if mesa_tiene_conflicto_horario(db, fecha, mesa, hora):
        db.close()
        return redirect(f"/reservas?fecha={fecha}&error=mesa_ocupada")

    cur = db.execute(
        "INSERT INTO reservas (nombre, telefono, personas, fecha, hora, notas, mesa) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (nombre, telefono, personas, fecha, hora, notas, mesa),
    )
    new_id = cur.lastrowid
    cid = upsert_cliente_desde_reserva(
        db,
        nombre=nombre,
        telefono=telefono,
        fecha_reserva=(fecha or "")[:10] or None,
        commit=False,
    )
    vincular_reserva_a_cliente(db, int(new_id), cid, commit=False)
    db.commit()
    db.close()

    dest = _safe_visualizar_next(request.form.get("next") or "") or f"/reservas?fecha={fecha}"
    return redirect(dest)

# =====================================================
# EDITAR RESERVA
# =====================================================

@bp.route("/editar/<int:id>")
@permiso_reservas
def editar(id):
    """Formulario de edición de una reserva existente."""
    fecha = request.args.get("fecha")
    db = get_db()
    ensure_salon_tables(db)
    ensure_clientes_schema(db)
    seed_salon_if_empty(db)
    mesas_select = mesas_para_mapa_reservas(db, current_app.static_folder)
    mesas_nombres_plano = [m["nombre"] for m in mesas_select]
    r = db.execute("SELECT * FROM reservas WHERE id=?", (id,)).fetchone()
    ocupacion_mesas_dia = ocupacion_mesas_por_fecha(db, r["fecha"], excluir_reserva_id=id)

    raw_cid = r["cliente_id"] if "cliente_id" in r.keys() else None
    cliente_id = int(raw_cid) if raw_cid is not None and int(raw_cid) > 0 else None
    if cliente_id is None:
        cid = upsert_cliente_desde_reserva(
            db,
            nombre=r["nombre"],
            telefono=r["telefono"],
            fecha_reserva=(r["fecha"] or "")[:10] or None,
            commit=False,
        )
        if cid:
            vincular_reserva_a_cliente(db, int(r["id"]), cid, commit=False)
            cliente_id = cid
    db.commit()
    db.close()

    reserva = {
        "id": r["id"],
        "nombre": r["nombre"],
        "telefono": r["telefono"],
        "personas": r["personas"],
        "fecha": r["fecha"],
        "hora": r["hora"],
        "notas": r["notas"] or "",
        "mesa": r["mesa"] or "",
        "cliente_id": cliente_id,
    }

    next_url = (request.args.get("next") or "").strip()

    return render_template(
        "editar_reserva.html",
        mostrar_nav=True,
        reserva=reserva,
        fecha=fecha,
        next_url=next_url,
        mesas_select=mesas_select,
        mesas_nombres_plano=mesas_nombres_plano,
        margen_solapamiento_mesa_seg=MARGEN_SOLAPAMIENTO_MESA_SEG,
        ocupacion_mesas_dia=ocupacion_mesas_dia,
    )

@bp.route("/actualizar/<int:id>", methods=["POST"])
@permiso_reservas
def actualizar(id):
    """Guarda cambios de una reserva."""
    fecha = request.args.get("fecha")
    nfecha = request.form["fecha"]
    hora = request.form["hora"]
    mesa = request.form.get("mesa", "")
    db = get_db()
    ensure_clientes_schema(db)
    try:
        datetime.strptime(hora, "%H:%M")
    except (TypeError, ValueError):
        db.close()
        return redirect(f"/reservas?fecha={nfecha}&error=campos")
    if mesa_tiene_conflicto_horario(db, nfecha, mesa, hora, excluir_reserva_id=id):
        db.close()
        return redirect(f"/reservas?fecha={nfecha}&error=mesa_ocupada")
    nombre = request.form["nombre"]
    telefono = request.form["telefono"]
    db.execute("""
        UPDATE reservas 
        SET nombre=?, telefono=?, personas=?, fecha=?, hora=?, notas=?, mesa=?
        WHERE id=?
    """, (
        nombre,
        telefono,
        request.form["personas"],
        nfecha,
        hora,
        request.form.get("notas", ""),
        mesa,
        id
    ))
    cid = upsert_cliente_desde_reserva(
        db,
        nombre=nombre,
        telefono=telefono,
        fecha_reserva=(nfecha or "")[:10] or None,
        commit=False,
    )
    vincular_reserva_a_cliente(db, int(id), cid, commit=False)
    db.commit()
    db.close()
    next_url = (request.args.get("next") or "").strip()
    if next_url.startswith("/visualizar") or next_url.startswith("/reservas"):
        return redirect(next_url)
    return redirect(f"/reservas?fecha={nfecha}")


def _candidatos_mesa_catalogo(db) -> list[tuple[str, int]]:
    """Nombres de mesa física + uniones (tabla `mesas` tras sync), o fallback desde objetos."""
    out: list[tuple[str, int]] = []
    seen: set[str] = set()
    if tabla_existe(db, "mesas"):
        rows = db.execute(
            "SELECT nombre, capacidad FROM mesas ORDER BY nombre COLLATE NOCASE"
        ).fetchall()
        for row in rows:
            n = (row["nombre"] or "").strip()
            if not n or n in seen:
                continue
            seen.add(n)
            try:
                c = int(row["capacidad"] or 4)
            except (TypeError, ValueError):
                c = 4
            out.append((n, max(1, c)))
    if out:
        return out
    for m in list_objetos_mesas_esquema_activo(db):
        n = (m["nombre"] or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        try:
            c = int(m["capacidad"] or 4)
        except (TypeError, ValueError):
            c = 4
        out.append((n, max(1, c)))
    for u in list_uniones_esquema_activo(db):
        n = (u.get("nombre") or "").strip()
        if not n or n in seen:
            continue
        seen.add(n)
        try:
            c = int(u.get("capacidad_total") or 0)
        except (TypeError, ValueError):
            c = 0
        if c < 2:
            c = 4
        out.append((n, c))
    return out


@bp.route("/api/sala_mesas_opciones", methods=["GET"])
@permiso_reservas_api
def api_sala_mesas_opciones():
    """Mesas y uniones disponibles para asignar desde Sala en vivo (respeta solape 2 h)."""
    rid = request.args.get("reserva_id", type=int)
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    if not rid:
        db.close()
        return jsonify({"ok": False, "error": "bad_request"}), 400
    r = db.execute("SELECT fecha, hora, mesa FROM reservas WHERE id = ?", (rid,)).fetchone()
    if not r:
        db.close()
        return jsonify({"ok": False, "error": "not_found"}), 404
    fecha_row = (r["fecha"] or "").strip()
    hora = (r["hora"] or "").strip()
    if not fecha_row or not hora:
        db.close()
        return jsonify({"ok": False, "error": "bad_request"}), 400
    cur_nf = normalizar_nombre_mesa((r["mesa"] or "").strip())
    opciones: list[dict] = []
    for nombre, cap in _candidatos_mesa_catalogo(db):
        conflicto = mesa_tiene_conflicto_horario(
            db, fecha_row, nombre, hora, excluir_reserva_id=rid
        )
        es_actual = normalizar_nombre_mesa(nombre) == cur_nf if cur_nf else False
        opciones.append(
            {
                "nombre": nombre,
                "capacidad": cap,
                "libre": not conflicto,
                "actual": es_actual,
                "elegible": (not conflicto) or es_actual,
            }
        )
    db.close()
    return jsonify({"ok": True, "opciones": opciones})


# =====================================================
# CAMBIAR ESTADO RESERVA
# =====================================================

@bp.route("/estado/<int:id>/<estado>")
@permiso_reservas
def cambiar_estado(id, estado):
    """Cambia estado de reserva y registra hora de llegada si es 'Llegó'."""

    fecha = request.args.get("fecha")

    if session.get("modo_tablet") and estado == "Cancelada":
        flash(
            "Para cancelar desde el tablet usa el botón «Cancelar (PIN)» e introduce el PIN de administrador.",
            "warning",
        )
        return redirect(f"/reservas?fecha={fecha}" if fecha else "/reservas")

    ahora = ahora_madrid()

    db = get_db()

    # Si llega el cliente, guardar hora de llegada

    if estado == "Llegó":

        db.execute(
            """
            UPDATE reservas
            SET estado = ?,
                hora_llegada = ?
            WHERE id = ?
            """,
            (
                estado,
                ahora.isoformat(),
                id
            )
        )

    else:

        db.execute(
            """
            UPDATE reservas
            SET estado = ?
            WHERE id = ?
            """,
            (
                estado,
                id
            )
        )

    db.commit()
    db.close()

    next_url = (request.args.get("next") or "").strip()
    if next_url.startswith("/visualizar") or next_url.startswith("/reservas"):
        return redirect(next_url)
    return redirect(f"/reservas?fecha={fecha}")


_ESTADOS_RESERVA = ("Pendiente", "Confirmada", "Llegó", "Finalizada", "Cancelada")


@bp.route("/api/reserva_estado", methods=["POST"])
@permiso_reservas_api
def api_reserva_estado():
    """Cambia estado (JSON) para sala en vivo sin recargar la página."""
    data = request.get_json(silent=True) or {}
    rid = data.get("id")
    estado = (data.get("estado") or "").strip()
    if not rid or estado not in _ESTADOS_RESERVA:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    if session.get("modo_tablet") and estado == "Cancelada":
        return jsonify({"ok": False, "error": "pin_required"}), 403

    ahora = ahora_madrid()
    db = get_db()
    if estado == "Llegó":
        db.execute(
            """
            UPDATE reservas
            SET estado = ?, hora_llegada = ?
            WHERE id = ?
            """,
            (estado, ahora.isoformat(), int(rid)),
        )
    else:
        db.execute(
            "UPDATE reservas SET estado = ? WHERE id = ?",
            (estado, int(rid)),
        )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/walkin", methods=["POST"])
@permiso_reservas_api
def api_walkin():
    """Crea una reserva walk-in ya en mesa (estado Llegó, hora de llegada ahora)."""
    data = request.get_json(silent=True) or {}
    fecha = (data.get("fecha") or "").strip()
    mesa = (data.get("mesa") or "").strip()
    nombre = (data.get("nombre") or "").strip() or "Walk-in"
    telefono = (data.get("telefono") or "").strip() or "-"
    try:
        personas = int(data.get("personas") or 2)
    except (TypeError, ValueError):
        personas = 2
    personas = max(1, min(personas, 99))
    hora = (data.get("hora") or "").strip()
    notas = (data.get("notas") or "").strip()
    if not fecha or not mesa:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    if not hora:
        hora = ahora_madrid().strftime("%H:%M")
    try:
        datetime.strptime(hora, "%H:%M")
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "hora_invalida"}), 400

    db = get_db()
    ensure_salon_tables(db)
    ensure_clientes_schema(db)
    if mesa_tiene_conflicto_horario(db, fecha, mesa, hora):
        db.close()
        return jsonify({"ok": False, "error": "mesa_ocupada"}), 409
    cur = db.execute(
        """
        INSERT INTO reservas (nombre, telefono, personas, fecha, hora, notas, mesa, estado, hora_llegada)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Llegó', ?)
        """,
        (
            nombre,
            telefono,
            personas,
            fecha,
            hora,
            notas or "walk-in",
            mesa,
            ahora_madrid().isoformat(),
        ),
    )
    new_id = cur.lastrowid
    cid = upsert_cliente_desde_reserva(
        db,
        nombre=nombre,
        telefono=telefono,
        fecha_reserva=(fecha or "")[:10] or None,
        commit=False,
    )
    vincular_reserva_a_cliente(db, int(new_id), cid, commit=False)
    db.commit()
    db.close()
    return jsonify({"ok": True, "id": new_id})


@bp.route("/api/reserva_rapida", methods=["POST"])
@permiso_reservas_api
def api_reserva_rapida():
    """Alta rápida desde sala en vivo: reserva normal (Pendiente), con teléfono; opcional mesa."""
    data = request.get_json(silent=True) or {}
    fecha = (data.get("fecha") or "").strip()
    mesa = (data.get("mesa") or "").strip()
    nombre = (data.get("nombre") or "").strip() or "Reserva"
    telefono = (data.get("telefono") or "").strip()
    try:
        personas = int(data.get("personas") or 2)
    except (TypeError, ValueError):
        personas = 2
    personas = max(1, min(personas, 99))
    hora = (data.get("hora") or "").strip()
    notas = (data.get("notas") or "").strip()
    if not fecha or not telefono:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    if not mesa:
        return jsonify({"ok": False, "error": "mesa_obligatoria"}), 400
    if not hora:
        hora = ahora_madrid().strftime("%H:%M")
    try:
        datetime.strptime(hora, "%H:%M")
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "hora_invalida"}), 400

    phone = normalizar_telefono(telefono)
    if len(phone) < 7:
        return jsonify({"ok": False, "error": "telefono_invalido"}), 400

    db = get_db()
    ensure_salon_tables(db)
    ensure_clientes_schema(db)
    fecha_key = fecha.strip()[:10]
    hora_key = hora.strip()[:12]

    dup = db.execute(
        """
        SELECT id FROM reservas
        WHERE telefono = ? AND fecha = ? AND hora = ?
          AND COALESCE(estado, 'Pendiente') NOT IN ('Cancelada', 'Finalizada')
        LIMIT 1
        """,
        (phone, fecha_key, hora_key),
    ).fetchone()
    if dup:
        db.close()
        return jsonify(
            {
                "ok": False,
                "error": "Ya existe una reserva activa con ese teléfono para la misma fecha y hora.",
            }
        ), 409

    if mesa_tiene_conflicto_horario(db, fecha_key, mesa, hora_key):
        db.close()
        return jsonify({"ok": False, "error": "mesa_ocupada"}), 409

    cur = db.execute(
        """
        INSERT INTO reservas (nombre, telefono, personas, fecha, hora, notas, mesa)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (nombre, phone, personas, fecha_key, hora_key, notas, mesa),
    )
    new_id = cur.lastrowid
    cid = upsert_cliente_desde_reserva(
        db,
        nombre=nombre,
        telefono=phone,
        fecha_reserva=fecha_key or None,
        commit=False,
    )
    vincular_reserva_a_cliente(db, int(new_id), cid, commit=False)
    db.commit()
    db.close()
    return jsonify({"ok": True, "id": new_id})


@bp.route("/api/walkin/revision", methods=["POST"])
@permiso_reservas_api
def api_walkin_revision():
    """Acciones sobre walk-ins > 3h: mantener (reinicia llegada) o eliminar."""
    data = request.get_json(silent=True) or {}
    rid = data.get("reserva_id")
    accion = (data.get("accion") or "").strip().lower()
    if accion not in ("mantener", "eliminar"):
        return jsonify({"ok": False, "error": "accion_invalida"}), 400
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad_request"}), 400

    db = get_db()
    r = db.execute("SELECT id FROM reservas WHERE id = ?", (rid,)).fetchone()
    if not r:
        db.close()
        return jsonify({"ok": False, "error": "not_found"}), 404

    if accion == "eliminar":
        db.execute("DELETE FROM reservas WHERE id = ?", (rid,))
    else:
        db.execute(
            """
            UPDATE reservas
            SET hora_llegada = ?
            WHERE id = ?
            """,
            (ahora_madrid().isoformat(), rid),
        )
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/asignar_mesa_reserva", methods=["POST"])
@permiso_reservas_api
def api_asignar_mesa_reserva():
    """Asigna o cambia la mesa de una reserva existente (p. ej. walk-in sin mesa en lista)."""
    data = request.get_json(silent=True) or {}
    rid = data.get("reserva_id")
    mesa = (data.get("mesa") or "").strip()
    if not rid or not mesa:
        return jsonify({"ok": False, "error": "bad_request"}), 400
    try:
        rid = int(rid)
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "bad_request"}), 400

    db = get_db()
    ensure_salon_tables(db)
    r = db.execute("SELECT fecha, hora FROM reservas WHERE id = ?", (rid,)).fetchone()
    if not r:
        db.close()
        return jsonify({"ok": False, "error": "not_found"}), 404
    if mesa_tiene_conflicto_horario(db, r["fecha"], mesa, r["hora"], excluir_reserva_id=rid):
        db.close()
        return jsonify({"ok": False, "error": "mesa_ocupada"}), 409
    db.execute("UPDATE reservas SET mesa = ? WHERE id = ?", (mesa, rid))
    db.commit()
    db.close()
    return jsonify({"ok": True})


# =====================================================
# CANCELAR / ELIMINAR CON PIN (tablet o autorización admin)
# =====================================================


@bp.route("/reserva_autorizada", methods=["POST"])
@permiso_reservas
def reserva_autorizada():
    """Cancelar o eliminar reserva tras validar el PIN de administrador."""
    fecha = (request.form.get("fecha") or "").strip()
    rid = request.form.get("reserva_id", type=int)
    accion = (request.form.get("accion") or "").strip()
    pin = (request.form.get("pin_autorizacion") or "").strip()
    if not rid or accion not in ("cancelar", "eliminar") or not pin:
        flash("Indica PIN y acción válidos.", "danger")
        return redirect(f"/reservas?fecha={fecha}" if fecha else "/reservas")
    db = get_db()
    ar = db.execute("SELECT pin_hash FROM admin LIMIT 1").fetchone()
    if not ar or not ar["pin_hash"] or not verificar_pin(pin, ar["pin_hash"]):
        db.close()
        flash("PIN de administrador incorrecto.", "danger")
        return redirect(f"/reservas?fecha={fecha}")
    if accion == "eliminar":
        db.execute("DELETE FROM reservas WHERE id=?", (rid,))
        msg = "Reserva eliminada."
    else:
        db.execute("UPDATE reservas SET estado = ? WHERE id = ?", ("Cancelada", rid))
        msg = "Reserva cancelada."
    db.commit()
    db.close()
    flash(msg, "success")
    return redirect(f"/reservas?fecha={fecha}")


# =====================================================
# ELIMINAR RESERVA
# =====================================================

@bp.route("/eliminar/<int:id>", methods=["POST"])
@permiso_reservas
def eliminar_reserva(id):
    """Borra una reserva por id."""

    fecha = request.form.get("fecha")

    db = get_db()
    ar = db.execute("SELECT pin_hash FROM admin LIMIT 1").fetchone()
    ah = ar["pin_hash"] if ar else None

    if session.get("modo_tablet"):
        pin = (request.form.get("pin_autorizacion") or "").strip()
        if not ah or not pin or not verificar_pin(pin, ah):
            db.close()
            flash(
                "Introduce el PIN de administrador para eliminar reservas en modo tablet.",
                "danger",
            )
            return redirect(f"/reservas?fecha={fecha}")
    elif session.get("rol") != "admin":
        db.close()
        flash("No autorizado.", "danger")
        return redirect(f"/reservas?fecha={fecha}")

    db.execute(
        "DELETE FROM reservas WHERE id=?",
        (id,)
    )

    db.commit()

    db.close()

    flash("Reserva eliminada.", "success")
    return redirect(f"/reservas?fecha={fecha}")
