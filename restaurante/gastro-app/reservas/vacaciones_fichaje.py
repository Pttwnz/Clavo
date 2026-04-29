"""Cálculo de horas trabajadas desde fichajes y referencia de vacaciones generadas."""
from __future__ import annotations

from collections import defaultdict
from datetime import date
from typing import Any

from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.fichajes_libro_data import analizar_eventos_dia, horas_semanales_contrato

# Ratio por defecto 13: equivale a «1 semana de vacaciones por trimestre» si semana vacacional = semana contrato
# y trimestre ≈ 13 semanas × esas horas semanales (13×Hs / Hs = 13 h trabajadas por 1 h vacación).
SEMANAS_REF_TRIMESTRE = 13.0


def _parse_fecha_alta(s: str | None) -> date | None:
    if not s or not str(s).strip():
        return None
    try:
        return date.fromisoformat(str(s).strip()[:10])
    except (ValueError, TypeError):
        return None


def dias_antiguedad(fecha_alta: str | None) -> int | None:
    d0 = _parse_fecha_alta(fecha_alta)
    if not d0:
        return None
    hoy = date.today()
    return max(0, (hoy - d0).days)


def texto_antiguedad(dias: int | None) -> str:
    if dias is None:
        return "—"
    if dias < 30:
        return f"{dias} días"
    meses = dias // 30
    a = dias // 365
    if a >= 1:
        resto_m = (dias % 365) // 30
        if resto_m:
            return f"{a} año(s) y {resto_m} mes(es) (~{dias} días)"
        return f"{a} año(s) (~{dias} días)"
    return f"{meses} mes(es) (~{dias} días)"


def minutos_trabajo_totales_empleado(db, empleado_id: int) -> int:
    """Suma minutos efectivos de trabajo por día (entrada/salida y pausas) desde fichajes."""
    if not tabla_existe(db, "fichajes") or not tabla_existe(db, "empleados"):
        return 0
    cols_e = columnas_tabla(db, "empleados")
    hc: Any = None
    if "horas_contrato" in cols_e:
        r0 = db.execute(
            "SELECT horas_contrato FROM empleados WHERE id = ?",
            (empleado_id,),
        ).fetchone()
        if r0:
            hc = r0["horas_contrato"]
    rows = db.execute(
        """
        SELECT fecha, hora, tipo FROM fichajes
        WHERE empleado_id = ?
        ORDER BY fecha, hora
        """,
        (empleado_id,),
    ).fetchall()
    if not rows:
        return 0

    grupos: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for r in rows:
        fd = str(r["fecha"])
        grupos[fd].append((str(r["hora"] or ""), r["tipo"]))

    total = 0
    for _fecha, evs in sorted(grupos.items()):
        evs = sorted(evs, key=lambda x: x[0])
        a = analizar_eventos_dia(evs, hc)
        total += int(a.get("min_trabajo") or 0)
    return total


def ratio_vacacion_desde_config(config: dict | None) -> float:
    """Horas trabajadas necesarias para acumular 1 h de vacaciones (referencia). Por defecto 13 (≈1 semana/trimestre JC)."""
    if not config:
        return 13.0
    raw = config.get("vacaciones_horas_trabajo_por_hora_vacacion")
    if raw is None or str(raw).strip() == "":
        return 13.0
    try:
        x = float(str(raw).strip().replace(",", "."))
        return x if x > 0 else 13.0
    except (ValueError, TypeError):
        return 13.0


def resumen_jornada_vacaciones(
    db,
    empleado_id: int,
    config_empresa: dict | None,
    fecha_alta_empleado: str | None,
    horas_contrato: Any = None,
) -> dict[str, Any]:
    minutos = minutos_trabajo_totales_empleado(db, empleado_id)
    horas_trab = round(minutos / 60.0, 2)
    ratio = ratio_vacacion_desde_config(config_empresa)
    horas_vac_gen = round(horas_trab / ratio, 2) if ratio > 0 else 0.0
    d_ant = dias_antiguedad(fecha_alta_empleado)

    hs = horas_semanales_contrato(horas_contrato)
    horas_trimestre_ref = round(SEMANAS_REF_TRIMESTRE * hs, 2)
    horas_semana_vacacion_ref = hs

    semanas_equiv = (
        round(horas_vac_gen / horas_semana_vacacion_ref, 2) if horas_semana_vacacion_ref > 0 else 0.0
    )
    trimestres_aprox = (
        round(horas_trab / horas_trimestre_ref, 2) if horas_trimestre_ref > 0 else 0.0
    )
    return {
        "minutos_trabajo": minutos,
        "horas_trabajadas": horas_trab,
        "ratio_horas_trabajo_por_hora_vacacion": ratio,
        "horas_vacaciones_generadas": horas_vac_gen,
        "semanas_vacacion_equiv": semanas_equiv,
        "trimestres_trabajo_aprox": trimestres_aprox,
        "horas_semana_contrato": hs,
        "horas_trimestre_referencia": horas_trimestre_ref,
        "horas_semana_vacacion_ref": horas_semana_vacacion_ref,
        "dias_antiguedad": d_ant,
        "texto_antiguedad": texto_antiguedad(d_ant),
    }
