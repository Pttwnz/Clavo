"""Listado de turnos programados (horarios) por fecha — solo lectura."""
from __future__ import annotations

from datetime import date, timedelta

from reservas.db_helpers import columnas_tabla, tabla_existe

_DIAS_ES = ("lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom.")
_MESES_ES = (
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
)


def etiqueta_fecha_es(fecha_iso: str) -> str:
    """Etiqueta legible para una fecha YYYY-MM-DD."""
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except (ValueError, TypeError):
        return fecha_iso or "—"
    return f"{_DIAS_ES[d.weekday()]} {d.day} {_MESES_ES[d.month - 1]} {d.year}"


def fechas_vecinas(fecha_iso: str) -> tuple[str, str, str]:
    """Ayer, hoy (referencia), mañana como ISO."""
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except (ValueError, TypeError):
        d = date.today()
    ayer = str(d - timedelta(days=1))
    manana = str(d + timedelta(days=1))
    ref = str(d)
    return ayer, ref, manana


def equipo_horarios_para_fecha(db, fecha_iso: str) -> list[dict]:
    """Turnos del módulo horarios para una fecha (excluye cancelados si existe columna estado)."""
    if not fecha_iso or not tabla_existe(db, "horarios"):
        return []
    cols_h = columnas_tabla(db, "horarios")
    cols_e = columnas_tabla(db, "empleados")
    if "apellido" in cols_e:
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
        rows = db.execute(
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
            (fecha_iso[:10],),
        ).fetchall()
        return [dict(r) for r in rows]
    except Exception:
        return []
