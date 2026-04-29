"""Consultas para publicar PDFs de horarios por empleado."""
from __future__ import annotations

from datetime import date

from reservas.db_helpers import tabla_existe

_DIAS = ("lun.", "mar.", "mié.", "jue.", "vie.", "sáb.", "dom.")


def etiqueta_periodo_es(desde_iso: str, hasta_iso: str) -> str:
    d0 = date.fromisoformat(desde_iso[:10])
    d1 = date.fromisoformat(hasta_iso[:10])
    return f"{d0.strftime('%d/%m/%Y')} – {d1.strftime('%d/%m/%Y')}"


def empleados_con_turnos_en_rango(db, desde: str, hasta: str) -> list[int]:
    if not tabla_existe(db, "horarios"):
        return []
    rows = db.execute(
        """
        SELECT DISTINCT empleado_id FROM horarios
        WHERE fecha BETWEEN ? AND ? AND empleado_id IS NOT NULL
        """,
        (desde, hasta),
    ).fetchall()
    return [int(r[0]) for r in rows if r[0] is not None]


def lineas_horarios_empleado_periodo(
    db, empleado_id: int, desde: str, hasta: str
) -> list[dict]:
    if not tabla_existe(db, "horarios"):
        return []
    rows = db.execute(
        """
        SELECT fecha, hora_inicio, hora_fin, horas, turno,
               COALESCE(estado, 'Programado') AS estado
        FROM horarios
        WHERE empleado_id = ? AND fecha BETWEEN ? AND ?
        ORDER BY fecha, hora_inicio
        """,
        (empleado_id, desde, hasta),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            dt = date.fromisoformat(str(d["fecha"])[:10])
            d["fecha_fmt"] = dt.strftime("%d/%m/%Y")
            d["dia_es"] = _DIAS[dt.weekday()]
        except (ValueError, TypeError):
            d["fecha_fmt"] = str(d.get("fecha") or "")
            d["dia_es"] = ""
        out.append(d)
    return out
