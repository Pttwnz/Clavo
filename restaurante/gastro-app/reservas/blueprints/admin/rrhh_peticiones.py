"""Gestión de peticiones RRHH (encargado / dirección: mismo acceso admin)."""
from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.decorators import login_requerido, permiso_mod
from reservas.rrhh_peticiones_schema import ahora_iso, ensure_rrhh_peticiones_schema

from . import bp


def _nombre_empleado_expr():
    """Expresión SQL para nombre completo según columnas disponibles."""
    return "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"


@bp.route("/rrhh_peticiones", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.rrhh")
def rrhh_peticiones():
    """
    Bandeja única para encargado y dueño (sesión admin): mensajes al chat RRHH
    y solicitudes formales (vacaciones, etc.).
    """
    db = get_db()
    ensure_rrhh_peticiones_schema(db)

    if request.method == "POST":
        accion = (request.form.get("accion") or "").strip()
        tipo = (request.form.get("tipo") or "").strip()

        if tipo == "mensaje" and accion in ("aprobar", "denegar"):
            mid = request.form.get("mensaje_id", type=int)
            texto = (request.form.get("respuesta_responsable") or "").strip()
            if not mid:
                flash("Identificador no válido.", "danger")
            elif accion == "denegar" and len(texto) < 3:
                flash("Para denegar debes indicar una explicación (mín. 3 caracteres).", "warning")
            else:
                if accion == "aprobar" and not texto:
                    texto = "Confirmada por dirección / encargado."
                estado = "Aprobada" if accion == "aprobar" else "Denegada"
                db.execute(
                    """
                    UPDATE mensajes_rrhh
                    SET estado_gestion = ?,
                        respuesta_responsable = ?,
                        gestionado_en = ?
                    WHERE id = ?
                    """,
                    (estado, texto, ahora_iso(), mid),
                )
                db.commit()
                flash("Petición actualizada.", "success")

        elif tipo == "solicitud" and accion in ("aprobar", "denegar"):
            sid = request.form.get("solicitud_id", type=int)
            texto = (request.form.get("respuesta_responsable") or "").strip()
            if not sid:
                flash("Identificador no válido.", "danger")
            elif accion == "denegar" and len(texto) < 3:
                flash("Para denegar debes indicar una explicación (mín. 3 caracteres).", "warning")
            else:
                if accion == "aprobar" and not texto:
                    texto = "Solicitud aprobada por dirección / encargado."
                estado_sol = "Aprobada" if accion == "aprobar" else "Rechazada"
                db.execute(
                    """
                    UPDATE solicitudes
                    SET estado = ?,
                        respuesta_responsable = ?,
                        revisado_en = ?
                    WHERE id = ?
                    """,
                    (estado_sol, texto, ahora_iso(), sid),
                )
                db.commit()
                flash("Solicitud gestionada.", "success")
        else:
            flash("Acción no reconocida.", "warning")

        db.close()
        return redirect(url_for("admin.rrhh_peticiones"))

    join_nombre = _nombre_empleado_expr()
    mensajes = []
    if tabla_existe(db, "mensajes_rrhh") and tabla_existe(db, "empleados"):
        apellido_ok = "apellido" in columnas_tabla(db, "empleados")
        nombre_sql = join_nombre if apellido_ok else "COALESCE(e.nombre, '')"
        mensajes = [
            dict(r)
            for r in db.execute(
                f"""
                SELECT m.*, {nombre_sql} AS empleado_nombre, COALESCE(e.puesto,'') AS empleado_puesto
                FROM mensajes_rrhh m
                LEFT JOIN empleados e ON e.id = m.empleado_id
                ORDER BY
                  CASE WHEN COALESCE(TRIM(m.estado_gestion), 'Pendiente') = 'Pendiente' THEN 0 ELSE 1 END,
                  m.id DESC
                LIMIT 80
                """
            ).fetchall()
        ]

    solicitudes = []
    if tabla_existe(db, "solicitudes") and tabla_existe(db, "empleados"):
        apellido_ok = "apellido" in columnas_tabla(db, "empleados")
        nombre_sql = join_nombre if apellido_ok else "COALESCE(e.nombre, '')"
        solicitudes = [
            dict(r)
            for r in db.execute(
                f"""
                SELECT s.*, {nombre_sql} AS empleado_nombre, COALESCE(e.puesto,'') AS empleado_puesto
                FROM solicitudes s
                LEFT JOIN empleados e ON e.id = s.empleado_id
                ORDER BY
                  CASE WHEN LOWER(TRIM(COALESCE(s.estado,''))) = 'pendiente' THEN 0 ELSE 1 END,
                  s.id DESC
                LIMIT 80
                """
            ).fetchall()
        ]

    db.close()

    return render_template(
        "rrhh_peticiones_admin.html",
        mostrar_nav=True,
        mensajes=mensajes,
        solicitudes=solicitudes,
    )
