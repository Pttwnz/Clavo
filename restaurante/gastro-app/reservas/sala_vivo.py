"""Lógica compartida de Sala en vivo: turnos, cruce mesa–reserva y payload para vista/API."""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date
from typing import Any

from reservas.salon_assets import (
    pick_imagen_capacidad,
    pick_imagen_decor,
    resolve_static_image,
    resolved_url_path,
)
from reservas.salon_helpers import (
    bounds_plano_objetos,
    list_objetos_decor_esquema_activo,
    objetos_visualizar_tp,
)
from reservas.utils import ahora_madrid, hora_texto_a_minutos, minutos_en_turno_visualizar, turno_de_hora


def _nombre_corto_mesa(nombre: str) -> str:
    """Etiqueta corta para mapa (p.ej. 'Mesa 12' -> 'M12')."""
    n = (nombre or "").strip()
    if not n:
        return "M?"
    low = n.lower()
    if low.startswith("mesa"):
        suf = n[4:].strip()
        if suf:
            return "M" + suf.replace(" ", "")
        return "M"
    return n[:6]


def normalizar_fecha_param(fecha_raw: str | None) -> str:
    """ISO YYYY-MM-DD estable para consultas y enlaces."""
    if not fecha_raw or not str(fecha_raw).strip():
        return str(date.today())
    s = str(fecha_raw).strip()[:19]
    for sep in ("-", "/"):
        if sep in s:
            parts = re.split(r"[-/]", s[:10])
            if len(parts) == 3:
                try:
                    y, mo, d = int(parts[0]), int(parts[1]), int(parts[2])
                    if y < 100:
                        y += 2000
                    return date(y, mo, d).isoformat()
                except (ValueError, TypeError):
                    break
    try:
        return str(date.fromisoformat(s[:10]))
    except ValueError:
        return str(date.today())


def variantes_fecha_sql(fecha_iso: str) -> list[str]:
    """Cadenas que pueden aparecer en BD para el mismo día."""
    out = [fecha_iso]
    try:
        d = date.fromisoformat(fecha_iso[:10])
        out.append(f"{d.day:02d}/{d.month:02d}/{d.year}")
        out.append(f"{d.day}/{d.month}/{d.year}")
    except ValueError:
        pass
    return list(dict.fromkeys(out))


def turno_visualizar_por_defecto() -> str:
    """Pestaña acorde a la hora actual en Madrid."""
    from reservas.utils import ahora_madrid

    return turno_de_hora(ahora_madrid().strftime("%H:%M"))


def claves_nombre_mesa(raw: str | None) -> set[str]:
    """Claves equivalentes para emparejar plano ↔ campo mesa de la reserva."""
    s = (raw or "").strip()
    if not s:
        return set()
    keys: set[str] = set()
    base = " ".join(s.split())
    keys.add(base.casefold())
    keys.add(re.sub(r"\s+", "", base).casefold())
    sin_mesa = re.sub(r"^mesa\s*", "", base, flags=re.IGNORECASE).strip()
    if sin_mesa and sin_mesa != base:
        keys.add(" ".join(sin_mesa.split()).casefold())
        keys.add(re.sub(r"\s+", "", sin_mesa).casefold())
    return {k for k in keys if k}


def reserva_coincide_turno(
    row_hora: Any,
    turno: str,
) -> bool:
    """Incluye reserva en el turno seleccionado (o todos)."""
    t = (turno or "noche").strip().lower()
    if t == "todos":
        return True
    mnts = hora_texto_a_minutos(row_hora)
    if mnts is not None and minutos_en_turno_visualizar(mnts, t):
        return True
    return turno_de_hora(row_hora) == t


def buscar_reserva_en_mapa(mesa_por_clave: dict[str, dict], nombre_plano: str) -> dict | None:
    for ck in claves_nombre_mesa(nombre_plano):
        if ck in mesa_por_clave:
            return mesa_por_clave[ck]
    return None


def registrar_reserva_en_mesas(mesa_por_clave: dict[str, dict], mesa_txt: str | None, payload: dict) -> None:
    if not (mesa_txt and str(mesa_txt).strip()):
        return
    for ck in claves_nombre_mesa(mesa_txt):
        mesa_por_clave[ck] = payload


# Reservas en estos estados no ocupan la mesa en el mapa ni en los contadores de sala en vivo.
_ESTADOS_SIN_OCUPACION_MESA: frozenset[str] = frozenset({"Finalizada", "Cancelada"})


def build_sala_vivo_data(
    db,
    static_root: str | None,
    fecha: str,
    turno: str,
) -> dict[str, Any]:
    """Construye listas de reservas, mesas en plano y decoración; reutilizable en HTML y JSON."""
    fecha_iso = normalizar_fecha_param(fecha)
    turno_key = (turno or "").strip().lower()
    if not turno_key:
        turno_key = turno_visualizar_por_defecto()
    elif turno_key not in ("manana", "mediodia", "noche", "todos"):
        turno_key = turno_visualizar_por_defecto()

    vars_f = variantes_fecha_sql(fecha_iso)
    placeholders = ",".join("?" * len(vars_f))
    reservas_dia = db.execute(
        f"SELECT * FROM reservas WHERE fecha IN ({placeholders}) ORDER BY hora",
        tuple(vars_f),
    ).fetchall()

    mesa_por_clave: dict[str, dict] = {}
    reservas_turno: list = []

    for r in reservas_dia:
        if not reserva_coincide_turno(r["hora"], turno_key):
            continue
        rd = {
            "id": r["id"],
            "nombre": r["nombre"],
            "personas": r["personas"],
            "hora": r["hora"],
            "estado": r["estado"] or "Pendiente",
            "mesa": r["mesa"],
            "hora_llegada": r["hora_llegada"] if r["hora_llegada"] else None,
        }
        reservas_turno.append(rd)
        estado_m = str(rd["estado"] or "Pendiente").strip()
        if estado_m not in _ESTADOS_SIN_OCUPACION_MESA:
            registrar_reserva_en_mesas(mesa_por_clave, r["mesa"], rd)

    mesas_out: list[dict] = []
    for m in objetos_visualizar_tp(db):
        nombre = (m.get("nombre") or "Mesa").strip()
        reserva = buscar_reserva_en_mapa(mesa_por_clave, nombre)
        cap = m.get("capacidad") or 4
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            cap = 4
        fb = pick_imagen_capacidad(static_root, cap)
        imagen = resolved_url_path(static_root, m.get("imagen"), fb)
        nl = nombre.lower()
        if nl.startswith("barril"):
            imagen = resolved_url_path(static_root, m.get("imagen"), "barril.png")
        elif nl.startswith("barra"):
            imagen = resolved_url_path(static_root, m.get("imagen"), "barra.png")
        tipo_m = (m.get("tipo") or "").strip().lower()
        raw_db = (m.get("imagen_db") or "").strip()
        mesa_foto_rel = None
        if static_root and tipo_m == "mesa" and raw_db:
            mesa_foto_rel = resolve_static_image(static_root, raw_db)
        mesas_out.append(
            {
                **m,
                "nombre_corto": _nombre_corto_mesa(nombre),
                "imagen": imagen,
                "mesa_foto_rel": mesa_foto_rel,
                "reserva": reserva,
                "ocupada": bool(reserva),
                "estado_mesa": (reserva.get("estado") if reserva else None),
            }
        )

    decor: list[dict] = []
    for d in list_objetos_decor_esquema_activo(db):
        tipo = (d.get("tipo") or "pared").strip().lower()
        decor.append(
            {
                "id": d["id"],
                "nombre": (d.get("nombre") or "").strip(),
                "tipo": tipo,
                "x": float(d.get("x") or 0),
                "y": float(d.get("y") or 0),
                "width": float(d.get("width") or 40),
                "height": float(d.get("height") or 40),
                "rotacion": float(d.get("rotacion") or 0),
                "imagen": resolved_url_path(
                    static_root,
                    d.get("imagen"),
                    pick_imagen_decor(static_root, tipo),
                ),
            }
        )

    plano_w, plano_h = bounds_plano_objetos(mesas_out + decor)
    ocupadas = sum(1 for x in mesas_out if x.get("reserva"))
    libres = len(mesas_out) - ocupadas

    sync_token = hashlib.sha256(
        json.dumps(
            [reservas_turno, [(m["id"], bool(m.get("reserva"))) for m in mesas_out]],
            sort_keys=True,
            default=str,
        ).encode("utf-8")
    ).hexdigest()[:16]

    now = ahora_madrid()
    pct_ocup = int(round(100 * ocupadas / len(mesas_out))) if mesas_out else 0

    return {
        "fecha": fecha_iso,
        "turno": turno_key,
        "reservas": reservas_turno,
        "mesas": mesas_out,
        "decor": decor,
        "plano_ancho": plano_w,
        "plano_alto": plano_h,
        "totales": {
            "reservas_lista": len(reservas_turno),
            "mesas_plano": len(mesas_out),
            "ocupadas": ocupadas,
            "libres": libres,
            "pct_ocupacion": pct_ocup,
        },
        "sync_token": sync_token,
        "server_time": now.strftime("%H:%M"),
        "server_time_sec": now.strftime("%H:%M:%S"),
    }
