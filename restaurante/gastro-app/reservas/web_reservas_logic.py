"""Cupo y horarios para reservas web (alineado con salón activo en gastro-app)."""
from __future__ import annotations

import re
import secrets
from datetime import date, datetime, timedelta
from typing import Any

from reservas.salon_helpers import (
    capacidad_union_mesas,
    ensure_salon_tables,
    list_objetos_mesas_esquema_activo,
    list_uniones_esquema_activo,
    seed_salon_if_empty,
)
from reservas.utils import ahora_madrid, hora_texto_a_minutos, mesa_tiene_conflicto_horario, normalizar_nombre_mesa
from reservas.utils import _variantes_fecha_reserva
from reservas.web_reservas_schema import get_web_reserva_config, list_franjas


_ESTADOS_CUPO = frozenset({"Pendiente", "Confirmada", "Llegó"})


def suma_capacidad_aforo(db) -> int:
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    total = 0
    for m in list_objetos_mesas_esquema_activo(db):
        try:
            c = int(m["capacidad"] or 4)
        except (TypeError, ValueError):
            c = 4
        if c > 0:
            total += c
    return total


def minutos_a_hhmm(m: int) -> str:
    m = max(0, min(1439, int(m)))
    return f"{m // 60:02d}:{m % 60:02d}"


def _franja_contiene_minuto(franja: dict, minute: int) -> bool:
    return int(franja["min_inicio"]) <= minute <= int(franja["min_fin"])


def buscar_franja_para(db, fecha_iso: str, hora_str: str) -> dict[str, Any] | None:
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return None
    wd = d.isoweekday()
    mnts = hora_texto_a_minutos(hora_str)
    if mnts is None:
        return None
    for f in list_franjas(db):
        if int(f["dia_semana"]) != wd:
            continue
        if _franja_contiene_minuto(f, mnts):
            return f
    return None


def pct_web_efectivo(franja: dict, cfg: dict) -> int:
    if franja.get("pct_web") is not None:
        return max(1, min(100, int(franja["pct_web"])))
    return max(1, min(100, int(cfg.get("pct_web_defecto") or 70)))


def suma_personas_web_en_franja(
    db,
    fecha_iso: str,
    franja: dict,
    *,
    excluir_reserva_id: int | None = None,
) -> int:
    vars_f = _variantes_fecha_reserva(fecha_iso)
    if not vars_f:
        return 0
    ph = ",".join("?" * len(vars_f))
    rows = db.execute(
        f"""
        SELECT id, hora, personas, estado, origen
        FROM reservas
        WHERE fecha IN ({ph})
        """,
        tuple(vars_f),
    ).fetchall()
    total = 0
    mi, mf = int(franja["min_inicio"]), int(franja["min_fin"])
    for r in rows:
        if excluir_reserva_id is not None and int(r["id"]) == excluir_reserva_id:
            continue
        if (r["origen"] or "").strip().lower() != "web":
            continue
        est = (r["estado"] or "Pendiente").strip()
        if est not in _ESTADOS_CUPO:
            continue
        hm = hora_texto_a_minutos(r["hora"])
        if hm is None:
            continue
        if mi <= hm <= mf:
            try:
                total += int(r["personas"] or 0)
            except (TypeError, ValueError):
                pass
    return total


def _cuota_para_franja(total_seats: int, pct: int) -> int:
    if total_seats < 1:
        return 0
    q = (total_seats * pct) // 100
    if pct > 0 and q < 1:
        q = 1
    return min(max(0, q), total_seats)


def evaluar_reserva_web(
    db,
    *,
    fecha_iso: str,
    hora_str: str,
    personas: int,
    cfg: dict | None = None,
    excluir_reserva_id: int | None = None,
    for_preview: bool = False,
) -> dict[str, Any]:
    cfg = cfg or get_web_reserva_config(db)
    if not for_preview and not cfg.get("activo"):
        return {"ok": False, "error": "Las reservas online están desactivadas."}
    p = int(personas)
    if p < int(cfg["min_personas"]) or p > int(cfg["max_personas"]):
        return {
            "ok": False,
            "error": f"El número de comensales debe estar entre {cfg['min_personas']} y {cfg['max_personas']}.",
        }
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return {"ok": False, "error": "Fecha no válida."}
    hoy = ahora_madrid().date()
    max_day = hoy + timedelta(days=max(1, int(cfg["max_dias_antelacion"])))
    if d < hoy:
        return {"ok": False, "error": "No se pueden reservar fechas pasadas."}
    if d > max_day:
        return {"ok": False, "error": "La fecha está fuera del plazo permitido para reservar online."}

    franja = buscar_franja_para(db, fecha_iso, hora_str)
    if not franja:
        return {
            "ok": False,
            "error": "Esa hora no está dentro de ninguna franja habilitada para reservas online.",
        }

    total_seats = suma_capacidad_aforo(db)
    if total_seats < 1:
        return {"ok": False, "error": "No hay mesas configuradas en el salón. Configura el plano en el panel."}

    pct = pct_web_efectivo(franja, cfg)
    quota = _cuota_para_franja(total_seats, pct)
    used = suma_personas_web_en_franja(db, fecha_iso, franja, excluir_reserva_id=excluir_reserva_id)
    remaining = quota - used
    if p > remaining:
        return {
            "ok": False,
            "error": f"No hay cupo suficiente para esa franja ({franja.get('etiqueta') or 'horario'}). "
            f"Quedan {max(0, remaining)} comensales reservables online (cupo {quota}, ocupados {used}).",
        }

    # Antelación mínima respecto a "ahora"
    now = ahora_madrid()
    hm = hora_texto_a_minutos(hora_str)
    if hm is None:
        return {"ok": False, "error": "Hora no válida."}
    try:
        start_naive = datetime(d.year, d.month, d.day, hm // 60, hm % 60)
    except ValueError:
        return {"ok": False, "error": "Fecha u hora no válidas."}
    tz = now.tzinfo
    start_dt = start_naive.replace(tzinfo=tz) if tz else start_naive
    ant = max(0, int(cfg["anticipacion_minutos"]))
    if start_dt < now + timedelta(minutes=ant):
        return {
            "ok": False,
            "error": f"Debes reservar con al menos {ant} minutos de antelación respecto a la hora elegida.",
        }

    return {
        "ok": True,
        "franja": franja,
        "total_seats": total_seats,
        "quota": quota,
        "used": used,
        "remaining": remaining,
        "pct_web": pct,
    }


def iter_slots_del_dia(db, fecha_iso: str, cfg: dict) -> list[int]:
    """Minutos desde medianoche de cada hueco ofrecido (según franjas e intervalo)."""
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return []
    wd = d.isoweekday()
    step = max(5, min(120, int(cfg.get("intervalo_minutos") or 30)))
    out: list[int] = []
    for f in list_franjas(db):
        if int(f["dia_semana"]) != wd:
            continue
        mi, mf = int(f["min_inicio"]), int(f["min_fin"])
        t = mi
        while t <= mf:
            out.append(t)
            t += step
    return sorted(set(out))


def _float_mesa(d: dict, key: str, default: float = 0.0) -> float:
    try:
        return float(d.get(key) or default)
    except (TypeError, ValueError):
        return default


def _mesas_plano_cercanas(a: dict, b: dict, gap_max: float = 80.0) -> bool:
    """True si en el plano están una al lado de la otra (separación pequeña y solape en el otro eje)."""
    ax1, ay1 = _float_mesa(a, "x"), _float_mesa(a, "y")
    aw, ah = _float_mesa(a, "width", 72.0), _float_mesa(a, "height", 72.0)
    bx1, by1 = _float_mesa(b, "x"), _float_mesa(b, "y")
    bw, bh = _float_mesa(b, "width", 72.0), _float_mesa(b, "height", 72.0)
    ax2, ay2 = ax1 + aw, ay1 + ah
    bx2, by2 = bx1 + bw, by1 + bh
    h_gap = max(0.0, max(ax1, bx1) - min(ax2, bx2))
    v_gap = max(0.0, max(ay1, by1) - min(ay2, by2))
    y_overlap = min(ay2, by2) - max(ay1, by1)
    x_overlap = min(ax2, bx2) - max(ax1, bx1)
    if y_overlap > min(ah, bh) * 0.22 and h_gap <= gap_max:
        return True
    if x_overlap > min(aw, bw) * 0.22 and v_gap <= gap_max:
        return True
    return False


def opciones_mesa_reserva_web(
    db,
    *,
    fecha_iso: str,
    hora_str: str,
    personas: int,
    excluir_reserva_id: int | None = None,
) -> list[dict[str, Any]]:
    """
    Mesas sueltas que admiten pax, uniones configuradas, o dos mesas adyacentes en el plano.
    Orden: mejor ajuste de capacidad, luego tipo (mesa < unión < par).
    """
    p = max(1, int(personas))
    fecha_key = fecha_iso.strip()[:10]
    hora_key = hora_str.strip()[:12]
    opts: list[dict[str, Any]] = []
    seen_mesa: set[str] = set()

    def push(kind: str, mesa: str, capacidad: int, label: str) -> None:
        k = normalizar_nombre_mesa(mesa)
        if not k or k in seen_mesa:
            return
        seen_mesa.add(k)
        opts.append({"kind": kind, "mesa": mesa.strip(), "capacidad": int(capacidad), "label": label})

    for m in list_objetos_mesas_esquema_activo(db):
        md = dict(m)
        nom = (md.get("nombre") or "").strip()
        if not nom:
            continue
        try:
            cap = int(md.get("capacidad") or 0)
        except (TypeError, ValueError):
            cap = 4
        if cap < p:
            continue
        if mesa_tiene_conflicto_horario(db, fecha_key, nom, hora_key, excluir_reserva_id=excluir_reserva_id):
            continue
        push("single", nom, cap, f"Mesa {nom} (hasta {cap} comensales)")

    for u in list_uniones_esquema_activo(db):
        nom = (u.get("nombre") or "").strip()
        if not nom:
            continue
        try:
            cap_u = int(u.get("capacidad_total") or 0)
        except (TypeError, ValueError):
            cap_u = 0
        if cap_u < p:
            continue
        if mesa_tiene_conflicto_horario(db, fecha_key, nom, hora_key, excluir_reserva_id=excluir_reserva_id):
            continue
        push("union", nom, cap_u, f"Unión {nom} (hasta {cap_u} comensales)")

    mesas_rows = [dict(m) for m in list_objetos_mesas_esquema_activo(db)]
    n = len(mesas_rows)
    for i in range(n):
        for j in range(i + 1, n):
            a, b = mesas_rows[i], mesas_rows[j]
            n1 = (a.get("nombre") or "").strip()
            n2 = (b.get("nombre") or "").strip()
            if not n1 or not n2:
                continue
            try:
                c1 = int(a.get("capacidad") or 0)
                c2 = int(b.get("capacidad") or 0)
            except (TypeError, ValueError):
                c1, c2 = 4, 4
            if not _mesas_plano_cercanas(a, b):
                continue
            cap_pair = capacidad_union_mesas([c1, c2])
            if cap_pair < p:
                continue
            if mesa_tiene_conflicto_horario(db, fecha_key, n1, hora_key, excluir_reserva_id=excluir_reserva_id):
                continue
            if mesa_tiene_conflicto_horario(db, fecha_key, n2, hora_key, excluir_reserva_id=excluir_reserva_id):
                continue
            n_lo, n_hi = sorted((n1, n2), key=lambda x: normalizar_nombre_mesa(x))
            mesa_pair = f"{n_lo} + {n_hi}"
            push(
                "pair",
                mesa_pair,
                cap_pair,
                f"Mesas juntas {n_lo} y {n_hi} (aprox. {cap_pair} comensales)",
            )

    kind_rank = {"single": 0, "union": 1, "pair": 2}
    opts.sort(
        key=lambda o: (
            abs(int(o["capacidad"]) - p),
            kind_rank.get(str(o.get("kind")), 9),
            str(o.get("mesa") or "").lower(),
        )
    )
    return opts


def mesa_opcion_valida_para_web(
    elegida: str,
    opciones: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Devuelve la opción coincidente o None."""

    def norm_pair_key(s: str) -> tuple[str, ...]:
        parts = [normalizar_nombre_mesa(x) for x in re.split(r"\s*\+\s*", s.strip()) if x.strip()]
        if len(parts) > 1:
            return tuple(sorted(parts))
        return (normalizar_nombre_mesa(s),)

    e = (elegida or "").strip()
    if not e:
        return None
    key_e = norm_pair_key(e)
    for o in opciones:
        m = str(o.get("mesa") or "").strip()
        if not m:
            continue
        if normalizar_nombre_mesa(m) == normalizar_nombre_mesa(e):
            return o
        if norm_pair_key(m) == key_e and len(key_e) > 1:
            return o
    return None


def alternativas_horario_cercanas_reserva_web(
    db,
    *,
    fecha_iso: str,
    hora_pedida: str,
    personas: int,
    cfg: dict | None = None,
    max_items: int = 8,
) -> list[dict[str, Any]]:
    """
    Otras horas del mismo día con cupo web y al menos una mesa libre,
    ordenadas por cercanía a ``hora_pedida`` (minutos desde medianoche).
    """
    cfg = cfg or get_web_reserva_config(db)
    if not cfg.get("activo"):
        return []
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return []
    hoy = ahora_madrid().date()
    max_day = hoy + timedelta(days=max(1, int(cfg["max_dias_antelacion"])))
    if d < hoy or d > max_day:
        return []

    p = max(1, int(personas))
    hm0 = hora_texto_a_minutos(hora_pedida.strip()[:12])
    if hm0 is None:
        hm0 = 12 * 60

    now = ahora_madrid()
    ant = max(0, int(cfg["anticipacion_minutos"]))
    tz = now.tzinfo

    candidatos: list[tuple[int, int, str, str | None, int]] = []

    for minute in iter_slots_del_dia(db, fecha_iso, cfg):
        hhmm = minutos_a_hhmm(minute)
        hm = hora_texto_a_minutos(hhmm)
        if hm is None:
            continue
        try:
            start_naive = datetime(d.year, d.month, d.day, minute // 60, minute % 60)
        except ValueError:
            continue
        start_dt = start_naive.replace(tzinfo=tz) if tz else start_naive
        if start_dt < now + timedelta(minutes=ant):
            continue

        ev = evaluar_reserva_web(db, fecha_iso=fecha_iso, hora_str=hhmm, personas=p, cfg=cfg)
        if not ev.get("ok"):
            continue
        remaining = int(ev.get("remaining") or 0)
        if remaining < p:
            continue
        if not opciones_mesa_reserva_web(db, fecha_iso=fecha_iso, hora_str=hhmm, personas=p):
            continue
        fr = ev.get("franja") or {}
        slot_label = (fr.get("etiqueta") or "").strip() or None
        dist = abs(hm - hm0)
        candidatos.append((dist, hm, hhmm, slot_label, remaining))

    candidatos.sort(key=lambda x: (x[0], x[1]))
    out: list[dict[str, Any]] = []
    seen_h: set[int] = set()
    for dist, hm, hhmm, slot_label, remaining in candidatos:
        if hm in seen_h:
            continue
        seen_h.add(hm)
        out.append(
            {
                "fecha": fecha_iso[:10],
                "hora": hhmm,
                "slot_label": slot_label,
                "remaining": remaining,
                "minutos_desde_pedida": dist,
            }
        )
        if len(out) >= max_items:
            break
    return out


def slots_disponibles_payload(
    db,
    *,
    fecha_iso: str,
    personas: int,
    cfg: dict | None = None,
    for_preview: bool = False,
) -> dict[str, Any]:
    cfg = cfg or get_web_reserva_config(db)
    if not for_preview and not cfg.get("activo"):
        return {"ok": False, "error": "Las reservas online están desactivadas.", "slots": []}
    try:
        d = date.fromisoformat(fecha_iso[:10])
    except ValueError:
        return {"ok": False, "error": "Fecha no válida.", "slots": []}
    hoy = ahora_madrid().date()
    max_day = hoy + timedelta(days=max(1, int(cfg["max_dias_antelacion"])))
    if d < hoy or d > max_day:
        return {"ok": False, "error": "Fecha fuera del rango permitido.", "slots": []}

    total_seats = suma_capacidad_aforo(db)
    if total_seats < 1:
        return {"ok": False, "error": "Sin aforo configurado en el salón.", "slots": []}

    p = max(1, int(personas))
    now = ahora_madrid()
    ant = max(0, int(cfg["anticipacion_minutos"]))
    slots_out: list[dict[str, Any]] = []

    for minute in iter_slots_del_dia(db, fecha_iso, cfg):
        hhmm = minutos_a_hhmm(minute)
        franja = buscar_franja_para(db, fecha_iso, hhmm)
        if not franja:
            continue
        try:
            start_naive = datetime(d.year, d.month, d.day, minute // 60, minute % 60)
        except ValueError:
            continue
        tz = now.tzinfo
        start_dt = start_naive.replace(tzinfo=tz) if tz else start_naive
        if start_dt < now + timedelta(minutes=ant):
            continue

        pct = pct_web_efectivo(franja, cfg)
        quota = _cuota_para_franja(total_seats, pct)
        used = suma_personas_web_en_franja(db, fecha_iso, franja)
        remaining = quota - used
        mesa_ok = bool(
            opciones_mesa_reserva_web(db, fecha_iso=fecha_iso, hora_str=hhmm, personas=p)
        )
        slots_out.append(
            {
                "hora": hhmm,
                "disponible": remaining >= p and mesa_ok,
                "remaining": max(0, remaining),
                "quota": quota,
                "used": used,
                "slot_label": (franja.get("etiqueta") or "").strip() or None,
            }
        )
    return {
        "ok": True,
        "fecha": fecha_iso,
        "personas": p,
        "aforo_total": total_seats,
        "slots": slots_out,
    }


def normalizar_telefono(raw: str) -> str:
    return re.sub(r"\D+", "", (raw or "").strip())


def generar_token_confirmacion() -> str:
    return secrets.token_urlsafe(32)


def token_expires_iso(cfg: dict) -> str:
    h = max(1, int(cfg.get("confirmacion_horas") or 168))
    return (ahora_madrid() + timedelta(hours=h)).isoformat(timespec="seconds")


def insertar_reserva_web(
    db,
    *,
    nombre: str,
    telefono: str,
    email: str | None,
    personas: int,
    fecha_iso: str,
    hora_str: str,
    notas: str | None,
    token: str,
    expires_iso: str,
    mesa: str,
) -> int:
    mesa_v = (mesa or "").strip()[:200]
    if not mesa_v:
        raise ValueError("mesa_obligatoria")
    cur = db.execute(
        """
        INSERT INTO reservas (nombre, telefono, personas, fecha, hora, notas, mesa, estado,
            email, confirm_token, confirm_expires, origen)
        VALUES (?, ?, ?, ?, ?, ?, ?, 'Pendiente', ?, ?, ?, 'web')
        """,
        (
            nombre.strip()[:200],
            telefono.strip()[:40],
            int(personas),
            fecha_iso[:10],
            hora_str.strip()[:12],
            (notas or "").strip()[:2000] or None,
            mesa_v,
            (email or "").strip()[:200] or None,
            token,
            expires_iso,
        ),
    )
    db.commit()
    return int(cur.lastrowid)


def confirmar_por_token(db, token: str) -> tuple[bool, str]:
    if not token or len(token) < 20:
        return False, "Enlace no válido."
    row = db.execute(
        "SELECT id, estado, confirm_expires FROM reservas WHERE confirm_token = ?",
        (token.strip(),),
    ).fetchone()
    if not row:
        return False, "No encontramos esa reserva o el enlace ya no es válido."
    est = (row["estado"] or "").strip()
    if est == "Confirmada":
        return True, "Esta reserva ya estaba confirmada."
    if est in ("Cancelada", "Finalizada"):
        return False, "Esta reserva ya no se puede confirmar."
    exp = (row["confirm_expires"] or "").strip()
    if exp:
        try:
            now = ahora_madrid()
            exp_dt = datetime.fromisoformat(exp.replace("Z", ""))
            if exp_dt.tzinfo is None and now.tzinfo:
                exp_dt = exp_dt.replace(tzinfo=now.tzinfo)
            if now > exp_dt:
                return False, "El enlace de confirmación ha caducado. Contacta con el restaurante."
        except Exception:
            pass
    db.execute(
        "UPDATE reservas SET estado = 'Confirmada', confirm_token = NULL, confirm_expires = NULL WHERE id = ?",
        (int(row["id"]),),
    )
    db.commit()
    return True, "Reserva confirmada correctamente. ¡Te esperamos!"
