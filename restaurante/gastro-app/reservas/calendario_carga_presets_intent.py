"""Detecta en texto peticiones de periodos de alta carga (Fallas, Semana Santa, Feria…)."""
from __future__ import annotations

import re
from datetime import date

from reservas.fiestas_carga_presets import PRESETS


def _years_from_text(texto: str, default: int) -> list[int]:
    ys = [int(y) for y in re.findall(r"\b(20[2-3]\d)\b", texto)]
    return ys[:3] if ys else [default]


def extraer_presets_desde_texto(texto: str) -> list[tuple[str, int]]:
    """
    Devuelve lista (preset_id, año) sin IA. Varias coincidencias posibles (ej. Fallas + Semana Santa).
    """
    if not (texto or "").strip():
        return []
    year_now = date.today().year
    years = _years_from_text(texto, year_now)
    tl = texto.lower()
    out: list[tuple[str, int]] = []

    def add(pid: str):
        for y in years:
            if (pid, y) not in out:
                out.append((pid, y))

    if any(
        x in tl
        for x in (
            "fallas",
            "falles",
            "falla de valencia",
            "fallas de valencia",
            "cremà",
            "crema",
            "mascletà",
            "mascleta",
        )
    ) or " las fallas" in tl or "les falles" in tl or tl.strip().startswith("fallas"):
        add("fallas_valencia")

    if "semana santa" in tl or "setmana santa" in tl or "holy week" in tl:
        add("semana_santa")

    if ("feria" in tl or "feria de" in tl) and any(
        x in tl for x in ("sevilla", "seville", "abril", "andaluc")
    ):
        add("feria_sevilla")

    return out


def etiqueta_preset(pid: str) -> str:
    return PRESETS.get(pid, pid)
