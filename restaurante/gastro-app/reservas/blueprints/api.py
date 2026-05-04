"""Endpoints JSON para salones, esquemas y búsqueda admin."""
import os

from flask import Blueprint, current_app, jsonify, request, session

from config import RESERVAS_ONLY
from models import get_db
from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.decorators import login_requerido, permiso_mod
from reservas.salon_helpers import ensure_salon_tables, list_uniones_esquema_activo

bp = Blueprint("api", __name__)


def _internal_clavo_token() -> str:
    """Misma cabecera que Next (`verifyInternalClavoRequest`): X-Clavo-Internal o Bearer."""
    t = (request.headers.get("X-Clavo-Internal") or "").strip()
    if t:
        return t
    auth = request.headers.get("Authorization") or ""
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return ""


@bp.route("/api/internal/clavo/dining-table-unions", methods=["GET"])
def api_internal_clavo_dining_table_unions():
    """Uniones del esquema de sala activo para sincronizar mesas virtuales en Next (Prisma)."""
    expected = (os.getenv("CLAVO_INTERNAL_API_SECRET") or "").strip()
    if not expected:
        return jsonify({"error": "CLAVO_INTERNAL_API_SECRET no configurado"}), 503
    if _internal_clavo_token() != expected:
        return jsonify({"error": "No autorizado"}), 401

    db = get_db()
    try:
        uniones = list_uniones_esquema_activo(db)
    finally:
        db.close()

    out = []
    for u in uniones:
        out.append(
            {
                "id": u.get("id"),
                "nombre": u.get("nombre"),
                "capacidad_total": u.get("capacidad_total"),
                "mesa_nombres": u.get("mesa_nombres") or [],
                "mesa_ids": u.get("mesa_ids") or [],
            }
        )
    return jsonify({"uniones": out})


def _json_permiso(codigo: str):
    """403 si no hay permiso RBAC (admin PIN o empleado con código)."""
    from reservas.rbac_session import puede

    if session.get("admin_logueado") and session.get("rol") == "admin":
        return None
    if session.get("empleado_id") and puede(codigo):
        return None
    return jsonify({"error": "Sin permiso"}), 403


@bp.route("/api/salones")
@login_requerido
@permiso_mod("mod.salon")
def api_salones():
    """Devuelve JSON con todos los salones ordenados por nombre."""
    db = get_db()

    salones = db.execute(

        "SELECT * FROM salones ORDER BY nombre"

    ).fetchall()

    db.close()

    return jsonify({"salones": [dict(s) for s in salones]})


@bp.route("/api/salon/crear", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def api_salon_crear():
    """Crea un salón (espacio físico) nuevo; luego puedes añadirle planos."""
    data = request.get_json(force=True, silent=True) or {}
    nombre = (data.get("nombre") or "").strip() or "Nuevo salón"
    db = get_db()
    ensure_salon_tables(db)
    db.execute("INSERT INTO salones (nombre) VALUES (?)", (nombre,))
    db.commit()
    sid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    db.close()
    return jsonify({"ok": True, "id": sid})


@bp.route("/api/esquema/crear", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def api_esquema_crear():
    """Crea un plano (esquema) vacío dentro de un salón."""
    data = request.get_json(force=True, silent=True) or {}
    try:
        salon_id = int(data.get("salon_id"))
    except (TypeError, ValueError):
        return jsonify({"ok": False, "error": "salon_id requerido"}), 400
    nombre = (data.get("nombre") or "").strip() or "Plano nuevo"
    db = get_db()
    ensure_salon_tables(db)
    ex = db.execute("SELECT id FROM salones WHERE id = ?", (salon_id,)).fetchone()
    if not ex:
        db.close()
        return jsonify({"ok": False, "error": "Salón no encontrado"}), 404
    db.execute(
        "INSERT INTO esquemas (salon_id, nombre, activo) VALUES (?, ?, 0)",
        (salon_id, nombre),
    )
    db.commit()
    eid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
    db.close()
    return jsonify({"ok": True, "id": eid})


@bp.route("/api/salon/<int:salon_id>/esquemas")
@login_requerido
@permiso_mod("mod.salon")
def api_esquemas_por_salon(salon_id):
    """Lista esquemas de un salón (para selector en editor TPV)."""
    db = get_db()
    rows = db.execute(
        """
        SELECT id, nombre, activo, salon_id
        FROM esquemas
        WHERE salon_id = ?
        ORDER BY nombre
        """,
        (salon_id,),
    ).fetchall()
    db.close()
    return jsonify({"esquemas": [dict(r) for r in rows]})


@bp.route("/api/esquema/<int:eid>/activar", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def api_esquema_activar(eid):
    """Marca un esquema como activo (plano en sala en vivo y reservas)."""
    from reservas.salon_helpers import sync_tabla_mesas_desde_objetos

    db = get_db()
    db.execute("UPDATE esquemas SET activo = 0")
    db.execute("UPDATE esquemas SET activo = 1 WHERE id = ?", (eid,))
    db.commit()
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True})


# =====================================================
# OBTENER ESQUEMAS
# =====================================================

@bp.route("/api/esquemas/<int:id>")
@login_requerido
@permiso_mod("mod.salon")
def api_esquemas(id):
    """Devuelve JSON del esquema y sus objetos (mesas, etc.) por id de esquema."""
    db = get_db()

    # Obtener datos del esquema
    esquema = db.execute(
        """
        SELECT id, nombre, activo
        FROM esquemas
        WHERE id = ?
        """,
        (id,)
    ).fetchone()

    if not esquema:
        return jsonify({"error": "Esquema no encontrado"}), 404

    # Obtener objetos del esquema
    objetos = db.execute(
        """
        SELECT
            id,
            tipo,
            nombre,
            x,
            y,
            width,
            height,
            rotacion,
            imagen,
            COALESCE(capacidad,4) AS capacidad
        FROM objetos_salon
        WHERE esquema_id = ?
        """,
        (id,)
    ).fetchall()

    db.close()

    return jsonify(
        {
            "id": esquema["id"],
            "nombre": esquema["nombre"],
            "activo": esquema["activo"],
            "objetos": [dict(o) for o in objetos],
        }
    )


# --- Búsqueda global (autocompletado admin) ---


@bp.route("/api/busqueda")
@login_requerido
def api_busqueda():
    """Sugerencias de empleados y reservas para el buscador del topbar (solo admin)."""
    err = _json_permiso("mod.panel")
    if err:
        return err

    q = request.args.get("q", "").strip()
    if len(q) < 2:
        return jsonify({"empleados": [], "reservas": []})

    like = f"%{q}%"
    db = get_db()

    empleados_out = []
    if not RESERVAS_ONLY:
        cols_e = columnas_tabla(db, "empleados")
        sel_ap = "COALESCE(apellido,'') AS apellido" if "apellido" in cols_e else "'' AS apellido"
        sel_puesto = "COALESCE(puesto,'') AS puesto" if "puesto" in cols_e else "'' AS puesto"
        sel_tel = "COALESCE(telefono,'') AS telefono" if "telefono" in cols_e else "'' AS telefono"

        wh_parts = ["nombre LIKE ?"]
        params_e = [like]
        if "apellido" in cols_e:
            wh_parts.append("apellido LIKE ?")
            params_e.append(like)
        if "telefono" in cols_e:
            wh_parts.append("telefono LIKE ?")
            params_e.append(like)

        sql_e = (
            f"SELECT id, nombre, {sel_ap}, {sel_puesto}, {sel_tel} "
            f"FROM empleados WHERE ({' OR '.join(wh_parts)}) ORDER BY nombre LIMIT 12"
        )
        emp_rows = db.execute(sql_e, tuple(params_e)).fetchall()

        for row in emp_rows:
            titulo = f"{row['nombre']} {row['apellido'] or ''}".strip()
            empleados_out.append(
                {
                    "tipo": "empleado",
                    "id": row["id"],
                    "titulo": titulo,
                    "subtitulo": (row["puesto"] or "").strip() or "Personal",
                    "extra": (row["telefono"] or "").strip(),
                }
            )

    res_rows = db.execute(
        """
        SELECT id, nombre, COALESCE(telefono,'') AS telefono, fecha, hora,
               COALESCE(mesa,'') AS mesa, COALESCE(estado,'') AS estado
        FROM reservas
        WHERE nombre LIKE ? OR IFNULL(telefono,'') LIKE ?
        ORDER BY fecha DESC, hora DESC
        LIMIT 15
        """,
        (like, like),
    ).fetchall()

    reservas_out = []
    for row in res_rows:
        reservas_out.append(
            {
                "tipo": "reserva",
                "id": row["id"],
                "titulo": (row["nombre"] or "Sin nombre").strip(),
                "subtitulo": f"{row['fecha']} {row['hora'] or ''} · Mesa {row['mesa'] or '-'}",
                "extra": f"{row['estado'] or '—'} · {row['telefono'] or 'sin tel.'}",
            }
        )

    db.close()
    return jsonify({"empleados": empleados_out, "reservas": reservas_out})


@bp.route("/api/reserva/<int:id>")
@login_requerido
def api_reserva_detalle(id):
    """Detalle completo de una reserva para el modal de gestión."""
    err = _json_permiso("mod.panel")
    if err:
        return err

    db = get_db()
    r = db.execute("SELECT * FROM reservas WHERE id = ?", (id,)).fetchone()
    db.close()
    if not r:
        return jsonify({"error": "No encontrada"}), 404
    return jsonify({"reserva": dict(r)})


@bp.route("/api/empleado/<int:id>/ficha")
@login_requerido
def api_empleado_ficha(id):
    """Resumen amplio del empleado para modal (RRHH, fichajes, horarios, solicitudes)."""
    err = _json_permiso("mod.panel")
    if err:
        return err
    if RESERVAS_ONLY:
        return jsonify({"error": "No disponible"}), 404

    db = get_db()
    emp = db.execute("SELECT * FROM empleados WHERE id = ?", (id,)).fetchone()
    if not emp:
        db.close()
        return jsonify({"error": "No encontrado"}), 404

    e = dict(emp)

    fichajes_hoy = db.execute(
        """
        SELECT COUNT(*) FROM fichajes
        WHERE empleado_id = ? AND fecha = date('now')
        """,
        (id,),
    ).fetchone()[0]

    fichajes_semana = db.execute(
        """
        SELECT COUNT(*) FROM fichajes
        WHERE empleado_id = ? AND fecha >= date('now','-7 days')
        """,
        (id,),
    ).fetchone()[0]

    dias_distintos = db.execute(
        """
        SELECT COUNT(DISTINCT fecha) FROM fichajes WHERE empleado_id = ?
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
                WHERE empleado_id = ?
                ORDER BY id DESC LIMIT 15
                """,
                (id,),
            ).fetchall()
        ]

    horarios_prox = []
    if tabla_existe(db, "horarios"):
        horarios_prox = [
            dict(x)
            for x in db.execute(
                """
                SELECT fecha, hora_inicio, hora_fin, turno, horas, estado
                FROM horarios
                WHERE empleado_id = ? AND fecha >= date('now')
                ORDER BY fecha, hora_inicio
                LIMIT 25
                """,
                (id,),
            ).fetchall()
        ]

    ultimos_fichajes = [
        dict(x)
        for x in db.execute(
            """
            SELECT fecha, hora, tipo FROM fichajes
            WHERE empleado_id = ?
            ORDER BY fecha DESC, hora DESC
            LIMIT 10
            """,
            (id,),
        ).fetchall()
    ]

    db.close()

    return jsonify(
        {
            "empleado": e,
            "stats": {
                "registros_fichaje_hoy": fichajes_hoy,
                "registros_fichaje_semana": fichajes_semana,
                "dias_con_fichaje": dias_distintos,
            },
            "solicitudes": solicitudes,
            "horarios_proximos": horarios_prox,
            "ultimos_fichajes": ultimos_fichajes,
        }
    )
