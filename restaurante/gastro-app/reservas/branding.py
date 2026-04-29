"""Marca visual (logo + colores) desde config_empresa."""
from __future__ import annotations

import re

DEFAULT_PRIMARY = "#2563eb"
DEFAULT_ACCENT = "#1d4ed8"


def sanitize_hex_color(value: str | None, fallback: str) -> str:
    s = (value or "").strip()
    if re.match(r"^#[0-9A-Fa-f]{6}$", s):
        return s.lower()
    return fallback


def hex_to_rgb_tuple(h: str) -> tuple[int, int, int]:
    h = sanitize_hex_color(h, DEFAULT_PRIMARY).lstrip("#")
    return tuple(int(h[i : i + 2], 16) for i in (0, 2, 4))


def darken_hex(h: str, factor: float = 0.82) -> str:
    """Oscurece un hex para acentos secundarios."""
    r, g, b = hex_to_rgb_tuple(h)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def build_branding_dict(cfg: dict) -> dict:
    """Construye el dict para plantillas y :root CSS."""
    primary = sanitize_hex_color(cfg.get("color_primario"), DEFAULT_PRIMARY)
    accent_raw = (cfg.get("color_acento") or "").strip()
    accent = sanitize_hex_color(accent_raw, "") if accent_raw else ""
    if not accent:
        accent = darken_hex(primary, 0.78)

    logo_rel = (cfg.get("logo_relativo") or "").strip()
    razon = (cfg.get("razon_social") or "").strip()
    nombre_c = (cfg.get("nombre_comercial") or "").strip()
    nombre_mostrar = razon or nombre_c or "GastroManager"

    r, g, b = hex_to_rgb_tuple(primary)
    return {
        "logo_relativo": logo_rel,
        "color_primario": primary,
        "color_acento": accent,
        "nombre_mostrar": nombre_mostrar,
        "primary_rgb": f"{r},{g},{b}",
    }
