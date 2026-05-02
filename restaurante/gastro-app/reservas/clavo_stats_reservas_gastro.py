"""Agregados de reservas para el panel «Web · estadísticas» (SQLite Gastro).

Las reservas reales viven en Gastro; Prisma/Next suele tener la tabla vacía en
producción, así que estos totales sustituyen el bloque `reservations` de
`/api/internal/clavo-stats`.

Criterio temporal: `fecha` (día del servicio), acotada como en Next con
`createdAt >= medianoche (hoy - N días)` (comparación de cadenas YYYY-MM-DD).
"""

from __future__ import annotations

from datetime import timedelta

from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.utils import ahora_madrid


def _bucket_sql(has_origen: bool) -> str:
    """Expresión SQL → etiqueta Prisma: WEB | TABLET_PHONE | TABLET_WALKIN."""
    web = (
        "(LOWER(TRIM(COALESCE(origen, ''))) = 'web')"
        if has_origen
        else "0"
    )
    return f"""
    CASE
      WHEN {web} THEN 'WEB'
      WHEN LOWER(TRIM(COALESCE(notas, ''))) = 'walk-in'
        OR LOWER(TRIM(COALESCE(nombre, ''))) IN ('walk-in', 'walk in')
        THEN 'TABLET_WALKIN'
      ELSE 'TABLET_PHONE'
    END
    """


def reservas_stats_para_clavo_panel(db, days: int) -> dict:
    """Misma forma que el JSON `reservations` de Next (`clavo-stats`)."""
    days = max(7, min(90, int(days)))
    empty = {
        "days": days,
        "total7d": 0,
        "totalPeriod": 0,
        "bySource7d": {},
        "bySourcePeriod": {},
    }
    if not tabla_existe(db, "reservas"):
        return empty

    today = ahora_madrid().date()
    start_period = (today - timedelta(days=days)).isoformat()
    start_7 = (today - timedelta(days=7)).isoformat()
    has_origen = "origen" in columnas_tabla(db, "reservas")
    bucket = _bucket_sql(has_origen)

    sql = f"""
    SELECT
      {bucket.strip()} AS src,
      SUM(CASE WHEN fecha >= ? THEN 1 ELSE 0 END) AS n7,
      SUM(CASE WHEN fecha >= ? THEN 1 ELSE 0 END) AS nperiod
    FROM reservas
    WHERE fecha >= ?
    GROUP BY src
    """
    rows = db.execute(sql, (start_7, start_period, start_period)).fetchall()

    by7: dict[str, int] = {}
    byp: dict[str, int] = {}
    t7 = 0
    tp = 0
    for row in rows:
        key = str(row["src"] or "TABLET_PHONE")
        n7 = int(row["n7"] or 0)
        np = int(row["nperiod"] or 0)
        by7[key] = by7.get(key, 0) + n7
        byp[key] = byp.get(key, 0) + np
        t7 += n7
        tp += np

    return {
        "days": days,
        "total7d": t7,
        "totalPeriod": tp,
        "bySource7d": by7,
        "bySourcePeriod": byp,
    }
