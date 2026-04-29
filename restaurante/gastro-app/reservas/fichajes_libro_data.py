"""Agregación del libro de registro de jornada: pausas, horas ordinarias/extraordinarias."""
from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime
from typing import Any


def _norm_hms(s: str) -> str:
    s = str(s).strip()
    parts = s.split(":")
    if len(parts) >= 3:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2][:2]):02d}"
    if len(parts) == 2:
        return f"{int(parts[0]):02d}:{int(parts[1]):02d}:00"
    return s


def _parse_time(h: str | None) -> datetime | None:
    if not h:
        return None
    s = _norm_hms(h)
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s[:8], "%H:%M:%S") if fmt == "%H:%M:%S" else datetime.strptime(s[:5], "%H:%M")
        except ValueError:
            continue
    return None


def _diff_minutes(t_start: datetime, t_end: datetime) -> int:
    d = (t_end - t_start).total_seconds() / 60.0
    return int(d) if d >= 0 else 0


def _fmt_hm_minutes(total_min: int) -> str:
    if total_min <= 0:
        return "0:00"
    h, m = divmod(total_min, 60)
    return f"{h}:{m:02d}"


def horas_diarias_contrato(horas_contrato_val: Any) -> float:
    """Horas ordinarias de referencia por día laborable (semana / 5). Por defecto 8 h."""
    if horas_contrato_val is None:
        return 8.0
    s = str(horas_contrato_val).strip().replace(",", ".")
    if not s:
        return 8.0
    m = re.search(r"(\d+(?:\.\d+)?)", s)
    if not m:
        return 8.0
    semanal = float(m.group(1))
    if semanal <= 0:
        return 8.0
    return round(semanal / 5.0, 2)


def horas_semanales_contrato(horas_contrato_val: Any) -> float:
    """Horas de jornada semanal según el texto de contrato (p. ej. 40, «20 h semanales»). Por defecto 40 h."""
    return round(horas_diarias_contrato(horas_contrato_val) * 5.0, 2)


def _tipo_norm(t: str | None) -> str:
    return (t or "").strip().lower()


def analizar_eventos_dia(
    eventos: list[tuple[str, str]],
    horas_contrato_val: Any,
) -> dict[str, Any]:
    """
    eventos: lista (hora_str, tipo) ordenada cronológicamente.
    Devuelve claves: entrada, salida, pausas_txt, min_trabajo, min_ord, min_extra, estado
    """
    ent: str | None = None
    sal: str | None = None
    open_pause: str | None = None
    pause_pairs: list[tuple[str, str]] = []
    total_pause_min = 0

    for hora_raw, tipo_raw in eventos:
        tipo = _tipo_norm(tipo_raw)
        hora = str(hora_raw or "").strip()
        if tipo == "entrada":
            if ent is None:
                ent = hora
        elif tipo == "salida":
            sal = hora
        elif tipo in ("pausa_inicio", "pausa"):
            if ent and open_pause is None:
                open_pause = hora
        elif tipo in ("pausa_fin", "fin_pausa"):
            if open_pause:
                t0 = _parse_time(open_pause)
                t1 = _parse_time(hora)
                if t0 and t1:
                    total_pause_min += _diff_minutes(t0, t1)
                    pause_pairs.append((open_pause[:5], hora[:5]))
                open_pause = None

    # Pausa iniciada y cerrada solo con la salida (sin fin de pausa explícito)
    if open_pause and sal:
        t0 = _parse_time(open_pause)
        t1 = _parse_time(sal)
        if t0 and t1:
            total_pause_min += _diff_minutes(t0, t1)
            pause_pairs.append((open_pause[:5], sal[:5]))
        open_pause = None

    hd = horas_diarias_contrato(horas_contrato_val)
    min_ord_ref = int(round(hd * 60))

    pausas_txt = "—"
    if pause_pairs:
        pausas_txt = "; ".join(f"{a}–{b}" for a, b in pause_pairs)

    if not ent or not sal:
        est = "Incompleto"
        if not ent:
            est = "Sin entrada"
        elif not sal:
            est = "Sin salida"
        return {
            "entrada": (ent or "—")[:8],
            "salida": (sal or "—")[:8],
            "pausas": pausas_txt,
            "horas": "—",
            "horas_ord": "—",
            "horas_ext": "—",
            "estado": est,
            "min_trabajo": 0,
        }

    t_ent = _parse_time(ent)
    t_sal = _parse_time(sal)
    if not t_ent or not t_sal:
        return {
            "entrada": ent[:12],
            "salida": sal[:12],
            "pausas": pausas_txt,
            "horas": "—",
            "horas_ord": "—",
            "horas_ext": "—",
            "estado": "Error hora",
            "min_trabajo": 0,
        }

    min_bruto = _diff_minutes(t_ent, t_sal)
    min_trabajo = max(0, min_bruto - total_pause_min)
    min_ord = min(min_trabajo, min_ord_ref)
    min_extra = max(0, min_trabajo - min_ord_ref)

    return {
        "entrada": ent[:8],
        "salida": sal[:8],
        "pausas": pausas_txt,
        "horas": _fmt_hm_minutes(min_trabajo),
        "horas_ord": _fmt_hm_minutes(min_ord),
        "horas_ext": _fmt_hm_minutes(min_extra),
        "estado": "Completo",
        "min_trabajo": min_trabajo,
    }


def lineas_libro_tabla(registros: list[Any]) -> list[dict[str, Any]]:
    """
    Agrupa por empleado y fecha; una fila por día con jornada cerrada (salida) o incompleta al filtrar.
    Incluye filas de días con al menos un fichaje.
    """
    grupos: dict[tuple[int, str], list[tuple[str, str]]] = defaultdict(list)
    meta: dict[tuple[int, str], dict[str, Any]] = {}

    for r in registros:
        eid = r["empleado_id"]
        fecha = str(r["fecha"])
        hora = str(r["hora"] or "")
        tipo = _tipo_norm(r["tipo"])
        key = (eid, fecha)
        grupos[key].append((hora, r["tipo"]))
        if key not in meta:
            try:
                ap = (r["apellido"] or "").strip()
            except (KeyError, IndexError, TypeError):
                ap = ""
            nom = f"{(r['nombre'] or '').strip()} {ap}".strip() or "—"
            hc = None
            try:
                hc = r["horas_contrato"]
            except (KeyError, IndexError):
                pass
            meta[key] = {"empleado": nom, "horas_contrato": hc}

    out: list[dict[str, Any]] = []
    for key in sorted(grupos.keys(), key=lambda k: (k[0], k[1])):
        ev = sorted(grupos[key], key=lambda x: x[0])
        m = meta[key]
        a = analizar_eventos_dia(ev, m["horas_contrato"])
        out.append(
            {
                "empleado": m["empleado"],
                "fecha": key[1],
                "entrada": a["entrada"],
                "salida": a["salida"],
                "pausas": a["pausas"],
                "horas": a["horas"],
                "horas_ord": a["horas_ord"],
                "horas_ext": a["horas_ext"],
                "estado": a["estado"],
            }
        )
    return out


def lineas_pdf_empleado(registros_empleado: list[Any]) -> list[dict[str, Any]]:
    """Filas para el PDF a partir de los registros crudos del mes (un empleado o todos)."""
    return lineas_libro_tabla(registros_empleado)


def registros_mes_query(
    db,
    mes: str,
    empleado_id: int | None,
    cols_empleados: set[str],
) -> list:
    """mes = YYYY-MM. Incluye horas de contrato si existe la columna."""
    if "apellido" in cols_empleados:
        nom_part = "e.nombre, COALESCE(e.apellido, '') AS apellido"
    else:
        nom_part = "e.nombre, '' AS apellido"
    if "horas_contrato" in cols_empleados:
        nom_part += ", e.horas_contrato"
    else:
        nom_part += ", NULL AS horas_contrato"

    sql = f"""
        SELECT f.*, {nom_part}
        FROM fichajes f
        JOIN empleados e ON e.id = f.empleado_id
        WHERE strftime('%Y-%m', f.fecha) = ?
    """
    params: list = [mes]
    if empleado_id is not None:
        sql += " AND f.empleado_id = ?"
        params.append(empleado_id)
    sql += " ORDER BY e.id, f.fecha, f.hora"
    return db.execute(sql, tuple(params)).fetchall()
