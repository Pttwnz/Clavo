"""Esquema de peticiones RRHH (mensajes al departamento y solicitudes formales)."""

from datetime import datetime

from reservas.db_helpers import columnas_tabla, tabla_existe


def ensure_rrhh_peticiones_schema(db) -> None:
    """Añade columnas de gestión por encargado/dirección a mensajes_rrhh y solicitudes."""
    if tabla_existe(db, "mensajes_rrhh"):
        cols = columnas_tabla(db, "mensajes_rrhh")
        if "estado_gestion" not in cols:
            db.execute(
                "ALTER TABLE mensajes_rrhh ADD COLUMN estado_gestion TEXT DEFAULT 'Pendiente'"
            )
        if "respuesta_responsable" not in cols:
            db.execute(
                "ALTER TABLE mensajes_rrhh ADD COLUMN respuesta_responsable TEXT"
            )
        if "gestionado_en" not in cols:
            db.execute("ALTER TABLE mensajes_rrhh ADD COLUMN gestionado_en TEXT")

    if tabla_existe(db, "solicitudes"):
        cols = columnas_tabla(db, "solicitudes")
        if "respuesta_responsable" not in cols:
            db.execute(
                "ALTER TABLE solicitudes ADD COLUMN respuesta_responsable TEXT"
            )
        if "revisado_en" not in cols:
            db.execute("ALTER TABLE solicitudes ADD COLUMN revisado_en TEXT")

    db.commit()


def contar_pendientes_admin(db) -> tuple[int, int]:
    """
    Devuelve (mensajes RRHH pendientes de gestión, solicitudes formales pendientes).
    """
    n_msg = 0
    n_sol = 0
    if tabla_existe(db, "mensajes_rrhh"):
        cols = columnas_tabla(db, "mensajes_rrhh")
        if "estado_gestion" in cols:
            n_msg = db.execute(
                """
                SELECT COUNT(*) FROM mensajes_rrhh
                WHERE COALESCE(TRIM(estado_gestion), 'Pendiente') = 'Pendiente'
                """
            ).fetchone()[0]
        else:
            n_msg = db.execute("SELECT COUNT(*) FROM mensajes_rrhh").fetchone()[0]

    if tabla_existe(db, "solicitudes"):
        cols = columnas_tabla(db, "solicitudes")
        if "estado" in cols:
            n_sol = db.execute(
                """
                SELECT COUNT(*) FROM solicitudes
                WHERE LOWER(TRIM(COALESCE(estado, ''))) = 'pendiente'
                """
            ).fetchone()[0]

    return (n_msg, n_sol)


def contar_pendientes_empleado(db, empleado_id: int) -> tuple[int, int]:
    """Pendientes de respuesta humana para un empleado (mensajes + solicitudes)."""
    n_msg = 0
    n_sol = 0
    if tabla_existe(db, "mensajes_rrhh"):
        cols = columnas_tabla(db, "mensajes_rrhh")
        if "estado_gestion" in cols:
            n_msg = db.execute(
                """
                SELECT COUNT(*) FROM mensajes_rrhh
                WHERE empleado_id = ?
                  AND COALESCE(TRIM(estado_gestion), 'Pendiente') = 'Pendiente'
                """,
                (empleado_id,),
            ).fetchone()[0]

    if tabla_existe(db, "solicitudes"):
        if "estado" in columnas_tabla(db, "solicitudes"):
            n_sol = db.execute(
                """
                SELECT COUNT(*) FROM solicitudes
                WHERE empleado_id = ?
                  AND LOWER(TRIM(COALESCE(estado, ''))) = 'pendiente'
                """,
                (empleado_id,),
            ).fetchone()[0]

    return (n_msg, n_sol)


def ahora_iso() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
