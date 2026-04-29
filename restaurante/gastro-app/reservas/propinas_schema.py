"""Reparto de propinas (tablet)."""
from __future__ import annotations

import json
import re
from calendar import monthrange
from collections import defaultdict
from datetime import date, timedelta

from reservas.db_helpers import columnas_tabla, tabla_existe

T_REPARTOS = "propinas_repartos"
T_LINEAS = "propinas_reparto_lineas"

# Duración de cada franja (horas); debe dividir 24 (medianoche fija).
FRANJAS_HORAS_VALIDAS = frozenset((4, 6, 8, 12))

_MIN_DIA = 24 * 60


def ensure_propinas_tables(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_REPARTOS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            monto_total REAL NOT NULL,
            modo TEXT NOT NULL DEFAULT 'igual',
            notas TEXT,
            franja_idx INTEGER NOT NULL DEFAULT -1,
            franja_inicio TEXT,
            franja_fin TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_LINEAS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            reparto_id INTEGER NOT NULL,
            empleado_id INTEGER NOT NULL,
            importe REAL NOT NULL,
            horas_turno REAL,
            FOREIGN KEY (reparto_id) REFERENCES {T_REPARTOS}(id)
        )
        """
    )
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_propinas_rep_fecha ON {T_REPARTOS} (fecha)")
    if tabla_existe(db, T_REPARTOS):
        cols = columnas_tabla(db, T_REPARTOS)
        for name, decl in (
            ("franja_idx", "INTEGER DEFAULT -1"),
            ("franja_inicio", "TEXT"),
            ("franja_fin", "TEXT"),
        ):
            if name not in cols:
                db.execute(f"ALTER TABLE {T_REPARTOS} ADD COLUMN {name} {decl}")
    db.commit()


def empleados_con_horario_fecha(db, fecha_iso: str) -> list[dict]:
    """Empleados con turno programado ese día (horarios)."""
    if not tabla_existe(db, "horarios"):
        return []
    cols = [r[1] for r in db.execute("PRAGMA table_info(empleados)").fetchall()]
    nom = "COALESCE(e.nombre,'')"
    if "apellido" in cols:
        nom = "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
    q = f"""
        SELECT DISTINCT e.id, {nom} AS nombre
        FROM horarios h
        JOIN empleados e ON e.id = h.empleado_id
        WHERE h.fecha = ?
          AND (COALESCE(h.estado,'') = '' OR LOWER(COALESCE(h.estado,'')) NOT LIKE '%cancel%')
        ORDER BY nombre
    """
    return [dict(r) for r in db.execute(q, (fecha_iso[:10],)).fetchall()]


def horas_turno_dia(db, empleado_id: int, fecha_iso: str) -> float:
    """Suma horas declaradas en turnos del día (columna horas o cálculo inicio-fin)."""
    if not tabla_existe(db, "horarios"):
        return 0.0
    rows = db.execute(
        """
        SELECT hora_inicio, hora_fin, horas FROM horarios
        WHERE empleado_id = ? AND fecha = ?
        """,
        (empleado_id, fecha_iso[:10]),
    ).fetchall()
    total = 0.0
    for r in rows:
        h = r["horas"]
        if h is not None:
            try:
                total += float(h)
                continue
            except (TypeError, ValueError):
                pass
        # Aproximación simple si no hay horas guardadas
        try:
            hi = str(r["hora_inicio"] or "00:00")[:5]
            hf = str(r["hora_fin"] or "00:00")[:5]
            a, b = hi.split(":"), hf.split(":")
            t0 = int(a[0]) * 60 + int(a[1])
            t1 = int(b[0]) * 60 + int(b[1])
            if t1 > t0:
                total += (t1 - t0) / 60.0
        except (ValueError, IndexError, TypeError):
            total += 4.0
    return max(total, 0.01)


def _minutos_hhmm(s: str | None) -> int | None:
    if not s:
        return None
    s = str(s).strip()[:5]
    if s in ("24:00", "24:0"):
        return _MIN_DIA
    try:
        a, b = s.split(":")
        return int(a) * 60 + int(b)
    except (ValueError, IndexError, TypeError):
        return None


def _fmt_min(m: int) -> str:
    m = max(0, min(m, _MIN_DIA))
    return f"{m // 60:02d}:{m % 60:02d}"


MAX_FRANJAS_MANUALES = 24


def _fila_a_segmentos_minutos(r) -> list[tuple[int, int]]:
    h = r["horas"]
    t0 = _minutos_hhmm(r["hora_inicio"])
    t1 = _minutos_hhmm(r["hora_fin"])
    if t0 is None:
        t0 = 0
    if t1 is None:
        t1 = 0
    if t1 > t0:
        return [(t0, t1)]
    if t1 < t0:
        return [(t0, _MIN_DIA), (0, t1)]
    if h is not None:
        try:
            hh = float(h)
            if hh > 0:
                end = min(t0 + int(round(hh * 60)), _MIN_DIA)
                if end > t0:
                    return [(t0, end)]
        except (TypeError, ValueError):
            pass
    return []


def _solape_min(lo: int, hi: int, a: int, b: int) -> int:
    return max(0, min(hi, b) - max(lo, a))


def horas_solapamiento_franja(db, empleado_id: int, fecha_iso: str, a_min: int, b_min: int) -> float:
    """Horas trabajadas en [a_min, b_min) minutos desde medianoche del día (solape con turnos)."""
    if not tabla_existe(db, "horarios"):
        return 0.0
    rows = db.execute(
        """
        SELECT hora_inicio, hora_fin, horas, COALESCE(estado,'') AS estado FROM horarios
        WHERE empleado_id = ? AND fecha = ?
        """,
        (empleado_id, fecha_iso[:10]),
    ).fetchall()
    total = 0.0
    ventana_h = (b_min - a_min) / 60.0
    for r in rows:
        est = (r["estado"] or "").lower()
        if "cancel" in est:
            continue
        segs = _fila_a_segmentos_minutos(r)
        if segs:
            for lo, hi in segs:
                total += _solape_min(lo, hi, a_min, b_min) / 60.0
            continue
        h = r["horas"]
        if h is not None:
            try:
                hh = float(h)
                if hh > 0 and ventana_h > 0:
                    total += hh * (ventana_h / 24.0)
            except (TypeError, ValueError):
                pass
    # Sin solape real debe ser 0 (no usar mínimo ficticio: al filtrar por franja, si no hay solape no entra).
    return max(total, 0.0)


def franjas_del_dia(horas_por_franja: int) -> list[dict]:
    """Franjas consecutivas desde 00:00 que cubren el día (4/6/8/12 h)."""
    h = int(horas_por_franja)
    if h not in FRANJAS_HORAS_VALIDAS or 24 % h != 0:
        h = 8
    n = 24 // h
    out: list[dict] = []
    for i in range(n):
        a = i * h * 60
        b = (i + 1) * h * 60

        def _fmt(m: int) -> str:
            return f"{m // 60:02d}:{m % 60:02d}"

        out.append(
            {
                "idx": i,
                "inicio": _fmt(a),
                "fin": _fmt(b),
                "etiqueta": f"{_fmt(a)} – {_fmt(b)}",
            }
        )
    return out


def normalizar_franjas_manuales(pares: list[tuple[str, str]]) -> tuple[list[dict] | None, str | None]:
    """
    Valida lista de (inicio, fin) HH:MM. fin puede ser 24:00.
    Devuelve (lista tipo franjas_del_dia, mensaje_error).
    """
    limpio: list[tuple[int, int]] = []
    for ini_s, fin_s in pares:
        ini_s = (ini_s or "").strip()
        fin_s = (fin_s or "").strip()
        if not ini_s and not fin_s:
            continue
        a = _minutos_hhmm(ini_s)
        b = _minutos_hhmm(fin_s)
        if a is None or b is None:
            return None, f"Hora no válida: {ini_s!r} – {fin_s!r}"
        if b <= a:
            return None, f"La franja debe terminar después de empezar: {ini_s} – {fin_s}"
        if a < 0 or b > _MIN_DIA:
            return None, "Las horas deben estar entre 00:00 y 24:00"
        limpio.append((a, b))
    if not limpio:
        return None, "Indica al menos una franja (inicio y fin)."
    if len(limpio) > MAX_FRANJAS_MANUALES:
        return None, f"Como máximo {MAX_FRANJAS_MANUALES} franjas."
    limpio.sort(key=lambda x: x[0])
    out: list[dict] = []
    for i, (a, b) in enumerate(limpio):
        out.append(
            {
                "idx": i,
                "inicio": _fmt_min(a),
                "fin": _fmt_min(b) if b < _MIN_DIA else "24:00",
                "etiqueta": f"{_fmt_min(a)} – {_fmt_min(b) if b < _MIN_DIA else '24:00'}",
            }
        )
    return out, None


def franjas_manual_desde_json(raw: str | None) -> list[dict]:
    """Lista de franjas desde JSON guardado en config; vacío si inválido."""
    if not raw or not str(raw).strip():
        return []
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return []
    if not isinstance(data, list):
        return []
    pares: list[tuple[str, str]] = []
    for item in data:
        if not isinstance(item, dict):
            continue
        pares.append((str(item.get("inicio", "")), str(item.get("fin", ""))))
    ok, _err = normalizar_franjas_manuales(pares)
    return list(ok) if ok else []


def franjas_manual_desde_texto(texto: str) -> tuple[list[dict] | None, str | None]:
    """Una línea por franja: HH:MM-HH:MM o HH:MM – HH:MM."""
    pares: list[tuple[str, str]] = []
    for line in (texto or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^\s*(\d{1,2}:\d{2})\s*[-–—]\s*(\d{1,2}:\d{2})\s*$", line)
        if not m:
            return None, f"Línea no reconocida (usa HH:MM-HH:MM): {line!r}"
        pares.append((m.group(1), m.group(2)))
    if not pares:
        return None, "Indica al menos una franja (una línea por ventana, formato 08:00-16:00)."
    return normalizar_franjas_manuales(pares)


def franjas_manual_a_texto(franjas: list[dict]) -> str:
    lines = []
    for f in franjas:
        lines.append(f"{f.get('inicio', '')}-{f.get('fin', '')}")
    return "\n".join(lines)


def franjas_para_reparto(cfg: dict) -> list[dict]:
    """Lista de franjas según configuración (automática o manual)."""
    ag = (cfg.get("propinas_agrupacion") or "dia").strip().lower()
    if ag != "franja":
        return []
    modo = (cfg.get("propinas_franja_modo") or "auto").strip().lower()
    if modo == "manual":
        manual = cfg.get("propinas_franjas_manual") or []
        if isinstance(manual, list) and manual:
            return manual
        parsed = franjas_manual_desde_json(cfg.get("propinas_franjas_manual_json"))
        if parsed:
            return parsed
    return franjas_del_dia(int(cfg.get("propinas_franja_horas") or 8))


def minutos_ventana_franja(franja: dict) -> tuple[int, int]:
    """(a_min, b_min) desde el dict devuelto por `franjas_del_dia`."""
    a = _minutos_hhmm(str(franja.get("inicio") or "00:00"))
    b = _minutos_hhmm(str(franja.get("fin") or "00:00"))
    if a is None:
        a = 0
    if b is None:
        b = _MIN_DIA
    if b <= a:
        return 0, _MIN_DIA
    return a, b


def empleados_con_horario_franja(db, fecha_iso: str, a_min: int, b_min: int) -> list[dict]:
    """Empleados con solapamiento > 0 entre su turno y la franja horaria."""
    base = empleados_con_horario_fecha(db, fecha_iso)
    out: list[dict] = []
    for e in base:
        eid = int(e["id"])
        if horas_solapamiento_franja(db, eid, fecha_iso, a_min, b_min) > 1e-6:
            out.append(e)
    return out


def reparto_franja_ya_registrado(db, fecha_iso: str, franja_idx: int) -> bool:
    row = db.execute(
        f"SELECT 1 FROM {T_REPARTOS} WHERE fecha = ? AND franja_idx = ? LIMIT 1",
        (fecha_iso[:10], int(franja_idx)),
    ).fetchone()
    return row is not None


def reparto_dia_completo_ya_registrado(db, fecha_iso: str) -> bool:
    row = db.execute(
        f"""
        SELECT 1 FROM {T_REPARTOS}
        WHERE fecha = ? AND (franja_idx IS NULL OR franja_idx = -1)
        LIMIT 1
        """,
        (fecha_iso[:10],),
    ).fetchone()
    return row is not None


def reparto_etiqueta_visual(r: dict) -> str:
    """Texto corto para mostrar un reparto en listados."""
    try:
        fidx = r.get("franja_idx")
        if fidx is None or int(fidx) < 0:
            return "Día completo"
    except (TypeError, ValueError):
        return "Día completo"
    fi = (r.get("franja_inicio") or "").strip()
    ff = (r.get("franja_fin") or "").strip()
    if fi and ff:
        return f"{fi} – {ff}"
    return f"Franja #{fidx}"


def listar_repartos_fecha(db, fecha_iso: str) -> list[dict]:
    """Todos los repartos registrados para esa fecha (cada fila es independiente)."""
    if not tabla_existe(db, T_REPARTOS):
        return []
    rows = db.execute(
        f"""
        SELECT id, fecha, monto_total, modo, franja_idx, franja_inicio, franja_fin, creado_en
        FROM {T_REPARTOS}
        WHERE fecha = ?
        ORDER BY id ASC
        """,
        (fecha_iso[:10],),
    ).fetchall()
    out: list[dict] = []
    for row in rows:
        d = dict(row)
        d["etiqueta"] = reparto_etiqueta_visual(d)
        out.append(d)
    return out


def eliminar_reparto_por_id(db, reparto_id: int, fecha_iso: str) -> bool:
    """Borra un reparto y sus líneas solo si coincide la fecha (evita manipular otros días)."""
    row = db.execute(
        f"SELECT id FROM {T_REPARTOS} WHERE id = ? AND fecha = ?",
        (int(reparto_id), fecha_iso[:10]),
    ).fetchone()
    if not row:
        return False
    db.execute(f"DELETE FROM {T_LINEAS} WHERE reparto_id = ?", (int(reparto_id),))
    db.execute(f"DELETE FROM {T_REPARTOS} WHERE id = ?", (int(reparto_id),))
    db.commit()
    return True


def rango_fechas_periodo(periodo: str, ref: date) -> tuple[str, str]:
    """Devuelve (inicio, fin) ISO YYYY-MM-DD inclusive. Semana = lun–dom de la semana de `ref`."""
    p = (periodo or "dia").strip().lower()
    if p == "mes":
        first = ref.replace(day=1)
        _, last_d = monthrange(ref.year, ref.month)
        last = ref.replace(day=last_d)
        return first.isoformat(), last.isoformat()
    if p == "semana":
        wd = ref.weekday()  # lun=0
        start = ref - timedelta(days=wd)
        end = start + timedelta(days=6)
        return start.isoformat(), end.isoformat()
    return ref.isoformat(), ref.isoformat()


def horas_efectivas_linea(db, empleado_id: int, fecha_rep: str, horas_guardadas: float | None) -> float:
    return horas_efectivas_para_linea(db, empleado_id, fecha_rep, horas_guardadas, None, None)


def horas_efectivas_para_linea(
    db,
    empleado_id: int,
    fecha_rep: str,
    horas_guardadas: float | None,
    franja_inicio: str | None,
    franja_fin: str | None,
) -> float:
    try:
        h = float(horas_guardadas) if horas_guardadas is not None else 0.0
    except (TypeError, ValueError):
        h = 0.0
    if h > 0:
        return h
    fi = (franja_inicio or "").strip()
    ff = (franja_fin or "").strip()
    if fi and ff:
        a = _minutos_hhmm(fi)
        b = _minutos_hhmm(ff)
        if a is not None and b is not None and b > a:
            return horas_solapamiento_franja(db, empleado_id, fecha_rep, a, b)
    return horas_turno_dia(db, empleado_id, fecha_rep)


def estadisticas_propinas_rango(db, fecha_ini: str, fecha_fin: str) -> list[dict]:
    """Totales por empleado en el rango: propina, horas efectivas (turno) y €/hora."""
    if not tabla_existe(db, T_REPARTOS) or not tabla_existe(db, T_LINEAS):
        return []
    fi, ff = fecha_ini[:10], fecha_fin[:10]
    cols = [r[1] for r in db.execute("PRAGMA table_info(empleados)").fetchall()]
    nom = "COALESCE(e.nombre,'')"
    if "apellido" in cols:
        nom = "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
    q = f"""
        SELECT l.empleado_id AS eid, {nom} AS nombre,
               l.importe AS importe, r.fecha AS fecha, l.horas_turno AS horas_turno,
               r.franja_inicio AS franja_inicio, r.franja_fin AS franja_fin
        FROM {T_LINEAS} l
        JOIN {T_REPARTOS} r ON r.id = l.reparto_id
        JOIN empleados e ON e.id = l.empleado_id
        WHERE r.fecha >= ? AND r.fecha <= ?
        ORDER BY nombre, r.fecha
    """
    rows = db.execute(q, (fi, ff)).fetchall()
    tot_imp: dict[int, float] = defaultdict(float)
    tot_hor: dict[int, float] = defaultdict(float)
    nombres: dict[int, str] = {}
    for row in rows:
        eid = int(row["eid"])
        nombres[eid] = (row["nombre"] or "").strip() or f"#{eid}"
        tot_imp[eid] += float(row["importe"] or 0)
        hh = horas_efectivas_para_linea(
            db,
            eid,
            str(row["fecha"]),
            row["horas_turno"],
            row["franja_inicio"],
            row["franja_fin"],
        )
        tot_hor[eid] += hh
    out: list[dict] = []
    for eid in sorted(nombres.keys(), key=lambda x: nombres[x].lower()):
        imp = round(tot_imp[eid], 2)
        hor = round(tot_hor[eid], 2)
        eph = round(imp / hor, 2) if hor > 0 else 0.0
        out.append(
            {
                "empleado_id": eid,
                "nombre": nombres[eid],
                "total_propina": imp,
                "total_horas": hor,
                "eur_por_hora": eph,
            }
        )
    return out
