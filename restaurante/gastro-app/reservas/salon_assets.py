"""Descubre y resuelve rutas de imágenes bajo la carpeta static (mesas, plano, etc.)."""
from __future__ import annotations

import os
IMAGE_EXT = (".png", ".webp", ".jpg", ".jpeg", ".gif", ".svg")


def _norm_rel(p: str) -> str:
    return p.replace("\\", "/").strip().lstrip("/")


def file_exists(static_root: str, rel: str) -> bool:
    rel = _norm_rel(rel)
    if not rel or not static_root:
        return False
    return os.path.isfile(os.path.join(static_root, rel))


def _walk_images(static_root: str) -> list[str]:
    out: list[str] = []
    if not static_root or not os.path.isdir(static_root):
        return out
    for root, _, files in os.walk(static_root):
        for fn in files:
            if fn.lower().endswith(IMAGE_EXT):
                full = os.path.join(root, fn)
                rel = os.path.relpath(full, static_root).replace("\\", "/")
                out.append(rel)
    return sorted(out, key=lambda x: x.lower())


def discover_salon_assets(static_root: str | None) -> dict:
    """Lista imágenes agrupadas por uso aproximado (nombre de archivo)."""
    all_rel = _walk_images(static_root) if static_root else []
    mesa: list[str] = []
    pared: list[str] = []
    columna: list[str] = []
    puerta: list[str] = []
    ventana: list[str] = []
    bano: list[str] = []
    barra: list[str] = []
    barril: list[str] = []

    for rel in all_rel:
        base = os.path.basename(rel).lower()
        stem = os.path.splitext(base)[0]
        if "barra" in stem:
            barra.append(rel)
            continue
        if "barril" in stem:
            barril.append(rel)
            continue
        if "ventana" in stem or "window" in stem:
            ventana.append(rel)
            continue
        if "bano" in stem or "baño" in stem or "wc" in stem or "bath" in stem or "toilet" in stem:
            bano.append(rel)
            continue
        if "puerta" in stem or "door" in stem:
            puerta.append(rel)
            continue
        if "columna" in stem or "column" in stem or "pillar" in stem:
            columna.append(rel)
            continue
        if "pared" in stem or "wall" in stem:
            pared.append(rel)
            continue
        if "mesa" in stem or stem.startswith("m") and any(ch.isdigit() for ch in stem):
            mesa.append(rel)
            continue

    # Imágenes de mesa sueltas (mesa2.png, mesa8.png en raíz)
    for rel in all_rel:
        if rel in mesa or rel in barra or rel in barril:
            continue
        stem = os.path.splitext(os.path.basename(rel))[0].lower()
        if stem in ("mesa2", "mesa4", "mesa6", "mesa8", "mesa_2", "mesa_4", "mesa_6", "mesa_8"):
            mesa.append(rel)

    def uniq(seq: list[str]) -> list[str]:
        seen: set[str] = set()
        outl: list[str] = []
        for x in seq:
            if x not in seen:
                seen.add(x)
                outl.append(x)
        return outl

    mesa = uniq(sorted(set(mesa + barra + barril), key=lambda x: x.lower()))
    return {
        "all": all_rel,
        "mesa": mesa,
        "pared": uniq(pared),
        "columna": uniq(columna),
        "puerta": uniq(puerta),
        "ventana": uniq(ventana),
        "bano": uniq(bano),
        "barra": uniq(barra),
        "barril": uniq(barril),
    }


def resolve_static_image(static_root: str | None, stored: str | None) -> str | None:
    """Devuelve ruta relativa a static que existe en disco, o None."""
    if not static_root:
        return None
    if stored and str(stored).strip():
        s = _norm_rel(str(stored))
        if file_exists(static_root, s):
            return s
        bn = os.path.basename(s)
        for rel in _walk_images(static_root):
            if os.path.basename(rel).lower() == bn.lower():
                return rel
    return None


def pick_imagen_capacidad(static_root: str | None, capacidad: int) -> str:
    """Elige archivo de mesa existente según aforo; prueba varias convenciones de nombre."""
    cap = int(capacidad) if capacidad else 4
    if cap <= 2:
        n = 2
    elif cap >= 8:
        n = 8
    elif cap >= 6:
        n = 6
    else:
        n = 4

    # Prioridad: nombres exactos de demo por capacidad (jpg primero), luego png/webp/jpeg/gif.
    bases = [
        f"mesa_{n}",
        f"mesa{n}",
        f"Mesa{n}",
    ]
    exts = ("jpg", "jpeg", "png", "webp", "gif")
    candidates: list[str] = []
    for b in bases:
        for ext in exts:
            candidates.append(f"{b}.{ext}")
    for b in bases:
        for ext in exts:
            candidates.append(f"img/{b}.{ext}")
    if static_root:
        for c in candidates:
            r = resolve_static_image(static_root, c)
            if r:
                return r
        assets = discover_salon_assets(static_root)
        for rel in assets["mesa"]:
            stem = os.path.splitext(os.path.basename(rel))[0].lower().replace("_", "")
            if str(n) in stem or (n == 4 and "mesa" in stem and "2" not in stem and "6" not in stem and "8" not in stem):
                return rel
        if assets["mesa"]:
            return assets["mesa"][0]
    return f"img/mesa_{n}.png"


def pick_imagen_decor(static_root: str | None, tipo: str) -> str:
    """Primera imagen encajable para pared, barra, separador, columna, etc."""
    t = (tipo or "").strip().lower()
    empty = {"pared": [], "columna": [], "puerta": [], "ventana": [], "bano": [], "barra": [], "barril": []}
    assets = discover_salon_assets(static_root) if static_root else empty
    key_map = {
        "pared": "pared",
        "separador": "pared",
        "columna": "columna",
        "puerta": "puerta",
        "ventana": "ventana",
        "bano": "bano",
        "barra": "barra",
        "barril": "barril",
    }
    lst = assets.get(key_map.get(t, ""), [])
    if lst:
        return lst[0]
    for rel in assets.get("all", []):
        low = os.path.basename(rel).lower()
        if t == "barra" and "barra" in low:
            return rel
        if t == "barril" and ("barril" in low or "barrel" in low):
            return rel
        if t in ("pared", "separador") and ("pared" in low or "wall" in low):
            return rel
        if t == "ventana" and ("ventana" in low or "window" in low):
            return rel
        if t == "puerta" and ("puerta" in low or "door" in low):
            return rel
        if t == "columna" and ("columna" in low or "column" in low):
            return rel
        if t == "bano" and ("bano" in low or "wc" in low or "bath" in low):
            return rel
    return "img/mesa_4.png"


def resolved_url_path(static_root: str | None, stored: str | None, fallback: str) -> str:
    """Ruta segura para url_for('static', filename=…): existe o fallback."""
    r = resolve_static_image(static_root, stored)
    if r:
        return r
    r2 = resolve_static_image(static_root, fallback)
    if r2:
        return r2
    return _norm_rel(fallback) or "img/mesa_4.png"
