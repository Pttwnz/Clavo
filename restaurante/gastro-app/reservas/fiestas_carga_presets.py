"""Periodos de alta carga hostelería (Fallas, Semana Santa, Feria, etc.) — fechas calculadas o aproximadas."""
from __future__ import annotations

from datetime import date, timedelta

import holidays


def _good_friday(year: int) -> date | None:
    h = holidays.Spain(years=[year], language="es")
    for d, name in h.items():
        if "viernes santo" in str(name).lower():
            return d
    return None


def domingo_resurreccion(year: int) -> date | None:
    """Domingo de Pascua = Viernes Santo + 2."""
    vf = _good_friday(year)
    if not vf:
        return None
    return vf + timedelta(days=2)


def domingo_ramos(year: int) -> date | None:
    """Domingo de Ramos = Pascua - 7 días."""
    dr = domingo_resurreccion(year)
    if not dr:
        return None
    return dr - timedelta(days=7)


def preset_fallas_valencia(year: int) -> tuple[date, date, str, str]:
    """Fallas de Valencia: semana típica de la cremà (15–19 mar). Verificar programa oficial."""
    ini = date(year, 3, 15)
    fin = date(year, 3, 19)
    tit = "Fallas de Valencia (alta carga)"
    notas = (
        "Periodo de muy alta afluencia en hostelería en Valencia (mascletàs, verbenas, cremà 19 mar). "
        "Fechas orientativas del tramo principal; consultar programa oficial Junta Central Fallera."
    )
    return ini, fin, tit, notas


def preset_semana_santa(year: int) -> tuple[date, date, str, str]:
    """Semana Santa (Domingo de Ramos a Domingo de Resurrección)."""
    dr = domingo_ramos(year)
    pasc = domingo_resurreccion(year)
    if not dr or not pasc:
        raise ValueError(f"No se pudo calcular Semana Santa para el año {year}")
    tit = "Semana Santa (alta carga)"
    notas = (
        "Semana de mayor actividad litúrgica y turística en muchas ciudades (procesiones, comidas familiares). "
        "Rango: Domingo de Ramos a Domingo de Resurrección (fechas según calendario litúrgico)."
    )
    return dr, pasc, tit, notas


def preset_feria_sevilla(year: int) -> tuple[date, date, str, str]:
    """
    Feria de Abril (Sevilla): aproximación del alumbrao (sábado ~2 semanas después de Pascua).
    Confirmar siempre con el calendario oficial.
    """
    pasc = domingo_resurreccion(year)
    if not pasc:
        raise ValueError(f"No se pudo calcular Pascua para el año {year}")
    d = pasc + timedelta(days=13)
    while d.weekday() != 5:
        d += timedelta(days=1)
    ini = d
    fin = ini + timedelta(days=6)
    tit = "Feria de Abril (Sevilla) — alta carga"
    notas = (
        "Feria de Abril: casetas, público y cierre nocturno. Fechas aproximadas (inicio habitual sábado "
        "tras Semana Santa). Confirmar en calendario oficial Real Sociedad del Real de la Feria de Sevilla."
    )
    return ini, fin, tit, notas


PRESETS: dict[str, str] = {
    "fallas_valencia": "Fallas de Valencia",
    "semana_santa": "Semana Santa (Ramos–Pascua)",
    "feria_sevilla": "Feria de Abril (Sevilla)",
}


def aplicar_preset(preset_id: str, year: int) -> tuple[date, date, str, str]:
    pid = (preset_id or "").strip().lower()
    if pid == "fallas_valencia":
        return preset_fallas_valencia(year)
    if pid == "semana_santa":
        return preset_semana_santa(year)
    if pid == "feria_sevilla":
        return preset_feria_sevilla(year)
    raise ValueError(f"Preset desconocido: {preset_id}")
