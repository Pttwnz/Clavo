"""Contexto del establecimiento para IA del calendario (dirección → ámbito festivo)."""
from __future__ import annotations

from reservas.provincia_ccaa import ccaa_desde_codigo_postal, ccaa_desde_provincia


def contexto_para_calendario(cfg: dict | None) -> dict:
    """
    cfg: fila config_empresa o dict con direccion, codigo_postal, ciudad, provincia.
    """
    if not cfg:
        cfg = {}
    direccion = (cfg.get("direccion") or "").strip()
    cp = (cfg.get("codigo_postal") or "").strip()
    ciudad = (cfg.get("ciudad") or "").strip()
    provincia = (cfg.get("provincia") or "").strip()
    partes = [p for p in (direccion, cp, ciudad, provincia) if p]
    linea = ", ".join(partes)
    sub = ccaa_desde_provincia(provincia) or ccaa_desde_codigo_postal(cp)
    return {
        "linea_direccion": linea,
        "tiene_direccion": bool(linea),
        "ciudad": ciudad,
        "provincia": provincia,
        "codigo_postal": cp,
        "subdivision_sugerida": sub,
    }
