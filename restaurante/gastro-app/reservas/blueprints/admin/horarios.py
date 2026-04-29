"""Horarios laborales y generación por reglas."""
import calendar
import json
import logging
import math
import os
import re
import unicodedata
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import List
from urllib.parse import quote, urlencode

from flask import abort, current_app, flash, redirect, render_template, request, url_for

from models import get_db
from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.decorators import login_requerido, permiso_mod
from reservas.fichajes_libro_data import horas_semanales_contrato

from . import bp

_logger_horarios = logging.getLogger(__name__)

_DIAS_CORTOS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")
# Cabecera compacta tipo cuadrícula (lun–dom)
_DIAS_LETRA = ("L", "M", "X", "J", "V", "S", "D")

# Límites de texto para contextos internos del generador por reglas.
_HORARIO_EMPRESA_PROMPT_MAX = 1200
_PROMPT_GUIADO_FORM_MAX = 1200
_LISTA_EMPLEADOS_IA_MAX = 1600
_RESUMEN_HORAS_CONTRATO_IA_MAX = 800
_RESUMEN_POR_PUESTO_IA_MAX = 1000


def _parte_hora_compacta(raw) -> str:
    """Hora corta para la cuadrícula semanal: HH en punto o HH:MM (24 h, dos cifras en hora)."""
    if raw is None:
        return "?"
    s = str(raw).strip()
    if not s:
        return "?"
    s = s[:8]
    if len(s) >= 5 and s[2] == ":":
        try:
            h = int(s[:2])
            m = int(s[3:5])
        except ValueError:
            return s[:5]
        if m:
            return f"{h:02d}:{m:02d}"
        return f"{h:02d}"
    if ":" in s:
        a, _, rest = s.partition(":")
        try:
            h = int(a)
            m = int(rest[:2]) if rest[:2].isdigit() else 0
        except ValueError:
            return s
        if m:
            return f"{h:02d}:{m:02d}"
        return f"{h:02d}"
    return s


def _rango_turno_compacto(hi, hf) -> str:
    return f"{_parte_hora_compacta(hi)}-{_parte_hora_compacta(hf)}"


def _format_celda_turnos_compacta(turnos: list) -> str:
    if not turnos:
        return "-"
    ordenados = sorted(
        turnos,
        key=lambda x: ((x.get("hora_inicio") or ""), (x.get("hora_fin") or "")),
    )
    partes = [_rango_turno_compacto(t.get("hora_inicio"), t.get("hora_fin")) for t in ordenados]
    return ", ".join(partes)


def _fmt_horas_semana_total(total: float) -> str:
    try:
        t = float(total)
    except (TypeError, ValueError):
        return "—"
    r = round(t, 2)
    if abs(r - int(r)) < 0.001:
        return str(int(r))
    s = f"{r:.1f}"
    return s.rstrip("0").rstrip(".")


def _nombre_empleado_sql_db(db):
    cols = columnas_tabla(db, "empleados")
    return (
        "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
        if "apellido" in cols
        else "COALESCE(e.nombre, '')"
    )


def _enriquecer_horario_row(r, franja_cfg: dict | None = None):
    """Añade fecha_fmt y dia_es para tablas legibles."""
    d = dict(r)
    try:
        dt = date.fromisoformat(d["fecha"])
        d["fecha_fmt"] = dt.strftime("%d/%m/%Y")
        d["dia_es"] = _DIAS_CORTOS[dt.weekday()]
        d["dia_corto"] = dt.strftime("%d/%m")
    except (ValueError, TypeError, KeyError):
        d["fecha_fmt"] = d.get("fecha") or "—"
        d["dia_es"] = ""
        d["dia_corto"] = ""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_normalizada(None)
    fk = _clasificar_franja_horario(d.get("hora_inicio"), fc)
    d["franja_key"] = fk
    lb = fc.get("labels") or {}
    fallback = {"manana": "Mañana", "tarde": "Tarde", "noche": "Noche"}
    if fk in ("manana", "tarde", "noche"):
        d["franja_label"] = (lb.get(fk) or "").strip() or fallback.get(fk, "—")
    else:
        d["franja_label"] = "—"
    return d


def _horarios_query_base_sql(nexpr: str, db=None) -> str:
    dept_sql = ""
    if db is not None:
        try:
            from reservas.db_helpers import columnas_tabla, tabla_existe

            if tabla_existe(db, "empleados") and "departamento" in columnas_tabla(db, "empleados"):
                dept_sql = ",\n            COALESCE(e.departamento, '') AS departamento"
        except Exception:
            pass
    return f"""
        SELECT
            h.id,
            h.empleado_id,
            h.fecha,
            h.hora_inicio,
            h.hora_fin,
            h.turno,
            h.horas,
            COALESCE(h.estado, 'Programado') AS estado,
            {nexpr} AS empleado_nombre,
            COALESCE(e.puesto, '') AS puesto
            {dept_sql}
        FROM horarios h
        LEFT JOIN empleados e ON e.id = h.empleado_id
        """


def _matriz_semanal(
    db, lun: date, dom: date, empleados_list: list[dict], franja_cfg: dict | None = None
) -> dict:
    """Filas = empleados, columnas = 7 días (lun-dom)."""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_from_db(db)
    nexpr = _nombre_empleado_sql_db(db)
    sql = _horarios_query_base_sql(nexpr, db) + " WHERE h.fecha BETWEEN ? AND ? ORDER BY h.fecha, h.hora_inicio"
    rows = [
        _enriquecer_horario_row(x, fc)
        for x in db.execute(sql, (str(lun), str(dom))).fetchall()
    ]
    celdas: dict[str, list] = defaultdict(list)
    for h in rows:
        eid = h.get("empleado_id")
        if eid is None:
            continue
        celdas[f"{int(eid)}|{h['fecha']}"].append(h)

    dias = [lun + timedelta(days=i) for i in range(7)]
    dom = dias[-1]
    cab = []
    for d in dias:
        cab.append(
            {
                "fecha": str(d),
                "label": _DIAS_CORTOS[d.weekday()],
                "letra": _DIAS_LETRA[d.weekday()],
                "num": d.strftime("%d/%m"),
            }
        )
    filas_compactas = []
    for emp in empleados_list:
        eid = int(emp["id"])
        cols_text = []
        wtot = 0.0
        for d in dias:
            ck = f"{eid}|{str(d)}"
            turnos = celdas.get(ck, [])
            cols_text.append(_format_celda_turnos_compacta(turnos))
            for t in turnos:
                try:
                    wtot += float(t.get("horas") or 0)
                except (TypeError, ValueError):
                    pass
        filas_compactas.append(
            {
                "id": eid,
                "nombre": (emp.get("nombre") or "").strip() or "—",
                "cols": cols_text,
                "horas_semana": wtot,
                "horas_semana_txt": _fmt_horas_semana_total(wtot),
            }
        )
    return {
        "dias": cab,
        "dias_letras": list(_DIAS_LETRA),
        "empleados": empleados_list,
        "celdas": dict(celdas),
        "etiqueta_semana": _titulo_rango_semana_es(lun, dom),
        "filas_compactas": filas_compactas,
    }


_MESES_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)
# Límites orientativos para generación y filtros post-IA (convenio / política interna pueden variar).
# Jornada máxima diaria efectiva y descanso mínimo entre el fin de un turno y el inicio del siguiente.
_MAX_HORAS_DIA_LEGAL = 8.0
_DESCANSO_ENTRE_JORNADAS_H = 12


def _titulo_rango_semana_es(lun: date, dom: date) -> str:
    if lun.month == dom.month and lun.year == dom.year:
        return f"{lun.day}–{dom.day} {_MESES_ES[lun.month - 1]} {lun.year}"
    return f"{lun.strftime('%d/%m/%Y')} – {dom.strftime('%d/%m/%Y')}"


def matriz_semanal_empleado(
    db, lun: date, dom: date, empleado_id: int, franja_cfg: dict | None = None
) -> dict:
    """Una semana (lun–dom) para un solo empleado: `celdas[fecha_iso]` → lista de turnos."""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_from_db(db)
    nexpr = _nombre_empleado_sql_db(db)
    sql = (
        _horarios_query_base_sql(nexpr, db)
        + " WHERE h.empleado_id = ? AND h.fecha BETWEEN ? AND ? ORDER BY h.fecha, h.hora_inicio"
    )
    rows = [
        _enriquecer_horario_row(x, fc)
        for x in db.execute(sql, (empleado_id, str(lun), str(dom))).fetchall()
    ]
    celdas: dict[str, list] = defaultdict(list)
    for h in rows:
        celdas[h["fecha"]].append(h)

    hoy = date.today()
    dias = []
    for i in range(7):
        d = lun + timedelta(days=i)
        dias.append(
            {
                "fecha": str(d),
                "label": _DIAS_CORTOS[d.weekday()],
                "letra": _DIAS_LETRA[d.weekday()],
                "num": d.strftime("%d/%m"),
                "es_pasado": d < hoy,
                "es_hoy": d == hoy,
            }
        )
    cols_compact = []
    wtot = 0.0
    for di in dias:
        ts = celdas.get(di["fecha"], [])
        cols_compact.append(_format_celda_turnos_compacta(ts))
        for t in ts:
            try:
                wtot += float(t.get("horas") or 0)
            except (TypeError, ValueError):
                pass
    return {
        "lun": str(lun),
        "dom": str(dom),
        "titulo_semana": _titulo_rango_semana_es(lun, dom),
        "dias": dias,
        "dias_letras": list(_DIAS_LETRA),
        "celdas": dict(celdas),
        "row_compact": {
            "cols": cols_compact,
            "horas_semana_txt": _fmt_horas_semana_total(wtot),
        },
    }


def _grid_mensual(db, y: int, m: int, franja_cfg: dict | None = None) -> list:
    """Semanas tipo calendario + turnos agrupados por fecha."""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_from_db(db)
    nexpr = _nombre_empleado_sql_db(db)
    ult = calendar.monthrange(y, m)[1]
    desde = date(y, m, 1)
    hasta = date(y, m, ult)
    sql = _horarios_query_base_sql(nexpr, db) + " WHERE h.fecha BETWEEN ? AND ? ORDER BY h.fecha, h.hora_inicio"
    rows = [
        _enriquecer_horario_row(x, fc)
        for x in db.execute(sql, (str(desde), str(hasta))).fetchall()
    ]
    por_fecha: dict[str, list] = defaultdict(list)
    for h in rows:
        por_fecha[h["fecha"]].append(h)

    semanas = []
    for semana in calendar.monthcalendar(y, m):
        fila = []
        for d in semana:
            if d == 0:
                fila.append(None)
            else:
                fds = date(y, m, d)
                fs = str(fds)
                fila.append(
                    {
                        "fecha": fs,
                        "dia": d,
                        "turnos": por_fecha.get(fs, []),
                    }
                )
        semanas.append(fila)

    return semanas


def _empleados_lista_dict(db) -> list[dict]:
    if not tabla_existe(db, "empleados"):
        return []
    cols_e = columnas_tabla(db, "empleados")
    nexpr = _nombre_empleado_sql_db(db)
    if "activo" in cols_e:
        q = f"SELECT e.id, {nexpr} AS nombre FROM empleados e WHERE e.activo = 1 ORDER BY nombre"
    else:
        q = f"SELECT e.id, {nexpr} AS nombre FROM empleados e ORDER BY nombre"
    return [dict(x) for x in db.execute(q).fetchall()]


def _redirect_horarios_form():
    dest = (request.form.get("redirect_to") or "").strip()
    if dest.startswith("/horarios"):
        return redirect(dest)
    return redirect(url_for("admin.horarios"))


def _norm_celda(s):
    if s is None:
        return ""
    s = str(s).strip().strip("*").strip("`").strip()
    return " ".join(s.split())


def _normalizar_fecha_iso(s):
    s = _norm_celda(s)
    if not s:
        return None
    if len(s) >= 10 and re.match(r"^\d{4}-\d{2}-\d{2}", s):
        try:
            date.fromisoformat(s[:10])
            return s[:10]
        except ValueError:
            return None
    m = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{4})\s*$", s)
    if m:
        d, mo, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        try:
            date(y, mo, d)
            return f"{y:04d}-{mo:02d}-{d:02d}"
        except ValueError:
            return None
    return None


def _normalizar_hora(s):
    s = _norm_celda(s)
    if not s:
        return ""
    p = s.replace(".", ":").split(":")
    try:
        if len(p) >= 2:
            return f"{int(p[0]):02d}:{int(p[1]):02d}"
        if len(p) == 1 and p[0].isdigit():
            return f"{int(p[0]):02d}:00"
    except (ValueError, IndexError):
        pass
    return s


def _calcular_horas_diferencia(hora_inicio: str, hora_fin: str) -> float:
    try:
        p1 = hora_inicio.split(":")
        p2 = hora_fin.split(":")
        h1 = int(p1[0]) * 60 + int(p1[1]) if len(p1) > 1 else int(p1[0]) * 60
        h2 = int(p2[0]) * 60 + int(p2[1]) if len(p2) > 1 else int(p2[0]) * 60
        mins = h2 - h1
        if mins < 0:
            mins += 24 * 60
        return round(mins / 60.0, 2)
    except (ValueError, IndexError):
        return 8.0


def _nombre_display_empleado(ed: dict) -> str:
    n = (ed.get("nombre") or "").strip()
    a = (ed.get("apellido") or "").strip() if ed.get("apellido") is not None else ""
    full = f"{n} {a}".strip()
    return full or n


def _etiqueta_puesto_departamento(ed: dict) -> str:
    """Clave legible puesto + departamento para agrupar en el prompt de IA."""
    pu = (ed.get("puesto") or "").strip() or "Sin puesto"
    dep = (ed.get("departamento") or "").strip()
    if dep:
        return f"{pu} [Dept: {dep}]"
    return pu


def _etiqueta_grupo_empleado_prompt(ed: dict) -> str:
    """Puesto + departamento + jerarquía de portal (rango), si consta."""
    base = _etiqueta_puesto_departamento(ed)
    rn = (ed.get("rango_nombre") or "").strip()
    if rn:
        return f"{base} [Jerarquía portal: {rn}]"
    return base


def _lista_empleados_una_linea(empleados_rows) -> str:
    """Una sola línea compacta para no disparar el límite TPM."""
    parts = []
    for e in empleados_rows:
        ed = dict(e)
        nm = _nombre_display_empleado(ed)[:28]
        if not nm:
            continue
        pu = ((ed.get("puesto") or "").strip())[:14]
        dep = ((ed.get("departamento") or "").strip())[:18]
        cat = ((ed.get("categoria_servicio") or "").strip())[:22]
        hc = ed.get("horas_contrato")
        rn = ((ed.get("rango_nombre") or "").strip())[:14]
        tc = ((ed.get("tipo_contrato") or "").strip())[:16]
        bit = nm + (f"/{pu}" if pu else "")
        if dep:
            bit += f"/D:{dep}"
        if cat:
            bit += f"/Cat:{cat}"
        if hc is not None and str(hc).strip() != "":
            bit += f"/H{hc}"
        if rn:
            bit += f"/Rol:{rn}"
        if tc:
            bit += f"/Contr:{tc}"
        parts.append(bit)
    s = "; ".join(parts)
    lim = _LISTA_EMPLEADOS_IA_MAX
    return s[:lim] + ("…" if len(s) > lim else "")


def _horas_contrato_semana_safe(horas_contrato_val) -> float:
    """Horas semanales desde contrato (fallback seguro a 40h)."""
    try:
        hs = float(horas_semanales_contrato(horas_contrato_val))
    except (TypeError, ValueError):
        hs = 40.0
    if hs <= 0:
        return 40.0
    # Tope defensivo para evitar valores aberrantes en datos mal cargados.
    return min(hs, 60.0)


def _cumple_tope_semanal_contrato(acumulado_semana: float, horas_turno: float, tope_semanal: float) -> bool:
    """
    True si no se supera el contrato semanal (comparación en centésimas de hora).
    No permite pasarse ni por redondeo.
    """
    try:
        tope = round(float(tope_semanal), 2)
    except (TypeError, ValueError):
        tope = 40.0
    if tope <= 0:
        return False
    try:
        ht = round(float(horas_turno), 2)
        ac = round(float(acumulado_semana), 2)
    except (TypeError, ValueError):
        return False
    if ht <= 0:
        return False
    return round(ac + ht, 2) <= tope


def _niveles_carga_semana_default() -> dict[int, float]:
    return {i: 1.0 for i in range(7)}


def _parse_niveles_carga_semana_json(raw: str | None) -> dict[int, float]:
    out = _niveles_carga_semana_default()
    if not raw or not str(raw).strip():
        return out
    try:
        data = json.loads(raw)
        if not isinstance(data, dict):
            return out
        for k, v in data.items():
            ki = int(k)
            if 0 <= ki <= 6:
                fv = float(v)
                if fv > 0:
                    out[ki] = min(3.0, max(0.25, fv))
    except (ValueError, TypeError, json.JSONDecodeError):
        pass
    return out


def _niveles_carga_merge_form(form, base: dict[int, float]) -> dict[int, float]:
    out = dict(base)
    if not form:
        return out
    for i in range(7):
        key = f"nivel_dow_{i}"
        raw = (form.get(key) or "").strip()
        if not raw:
            continue
        try:
            fv = float(raw.replace(",", "."))
            if fv > 0:
                out[i] = min(3.0, max(0.25, fv))
        except ValueError:
            pass
    return out


def _niveles_carga_desde_request(form, cfg_json: str | None) -> dict[int, float]:
    return _niveles_carga_merge_form(form, _parse_niveles_carga_semana_json(cfg_json))


def _niveles_carga_to_json(d: dict[int, float]) -> str:
    return json.dumps({str(k): round(float(v), 4) for k, v in sorted(d.items())})


def _dotacion_nivelada_por_dia(min_base: int, weekday: int, niveles: dict[int, float]) -> int:
    m = float(niveles.get(int(weekday) % 7, 1.0))
    base = int(min_base)
    if base <= 0:
        return 0
    bruto = base * m
    # Regla intuitiva para barras %:
    # - Si bajas de 100%, redondea hacia abajo (reduce realmente personal).
    # - Si subes de 100%, redondea hacia arriba (refuerza realmente personal).
    if m < 1.0:
        n = int(math.floor(bruto))
    elif m > 1.0:
        n = int(math.ceil(bruto))
    else:
        n = int(round(bruto))
    return max(1, n)


def _linea_niveles_carga_ia(niveles: dict[int, float]) -> str:
    labs = ("Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom")
    parts = [f"{labs[i]} ×{float(niveles.get(i, 1.0)):.2g}" for i in range(7)]
    return "Carga relativa por día (multiplica dotación base ese día de la semana): " + "; ".join(parts) + "."


def _persist_niveles_carga_semana(db, niveles: dict[int, float]) -> None:
    try:
        db.execute(
            "UPDATE config_empresa SET niveles_carga_semana = ? WHERE id = 1",
            (_niveles_carga_to_json(niveles),),
        )
        db.commit()
    except Exception as ex:
        print("persist niveles_carga_semana:", ex)


def _resumen_horas_contrato(empleados_rows) -> str:
    """Lista compacta 'Nombre=XXh/sem' para forzar límites por persona en el prompt."""
    pares = []
    for e in empleados_rows:
        ed = dict(e)
        nm = _nombre_display_empleado(ed)
        if not nm:
            continue
        hs = _horas_contrato_semana_safe(ed.get("horas_contrato"))
        pares.append(f"{nm}={hs:g}h/sem")
    txt = "; ".join(pares)
    lim = _RESUMEN_HORAS_CONTRATO_IA_MAX
    return txt[:lim] + ("…" if len(txt) > lim else "")


def _filtrar_turnos_por_reglas_legales_y_contrato(pendientes, horas_semana_por_empleado):
    """Descarta turnos que superen máximo diario legal o el tope semanal de contrato."""
    ordenados = sorted(pendientes, key=lambda x: (x[0], x[1], x[2], x[3]))
    diarios = defaultdict(float)  # (eid, fecha) -> horas
    semanales = defaultdict(float)  # (eid, iso_year, iso_week) -> horas
    validos = []
    descartes_diarios = 0
    descartes_semanales = 0

    for eid, fecha_s, hora_inicio, hora_fin, turno, horas in ordenados:
        try:
            horas_f = float(horas or 0.0)
        except (TypeError, ValueError):
            horas_f = 0.0
        if horas_f <= 0:
            continue
        try:
            fd = date.fromisoformat(fecha_s)
            y, w, _ = fd.isocalendar()
        except ValueError:
            continue

        kdia = (eid, fecha_s)
        ksem = (eid, y, w)
        horas_semana_tope = float(horas_semana_por_empleado.get(int(eid), 40.0))

        if diarios[kdia] + horas_f > _MAX_HORAS_DIA_LEGAL + 1e-9:
            descartes_diarios += 1
            continue
        if not _cumple_tope_semanal_contrato(semanales[ksem], horas_f, horas_semana_tope):
            descartes_semanales += 1
            continue

        diarios[kdia] += horas_f
        semanales[ksem] += horas_f
        validos.append((eid, fecha_s, hora_inicio, hora_fin, turno, horas_f))

    return validos, descartes_diarios, descartes_semanales


def _intervalo_datetime_desde_turno(fecha_s: str, hi: str, hf: str) -> tuple[datetime | None, datetime | None]:
    """Instante inicio y fin reales del turno (cruza medianoche si la hora fin es menor que la de inicio)."""
    try:
        d = date.fromisoformat((fecha_s or "")[:10])
    except ValueError:
        return None, None
    im = _hora_a_min(hi)
    fm = _hora_a_min(hf)
    ini = datetime(d.year, d.month, d.day) + timedelta(minutes=im)
    if fm >= im:
        fin = datetime(d.year, d.month, d.day) + timedelta(minutes=fm)
    else:
        d2 = d + timedelta(days=1)
        fin = datetime(d2.year, d2.month, d2.day) + timedelta(minutes=fm)
    if fin <= ini:
        return None, None
    return ini, fin


def _filtrar_descanso_minimo_entre_turnos(pendientes, horas_min: float) -> tuple[list, int]:
    """
    Por empleado, ordena turnos por tiempo real y descarta los que dejan < horas_min
    entre el fin del turno anterior aceptado y el inicio del siguiente (no puede «cerrar y abrir» sin descanso).
    """
    gap = timedelta(hours=float(horas_min))
    by_eid: dict[int, list[tuple[tuple, datetime, datetime]]] = defaultdict(list)
    for t in pendientes:
        eid, fecha_s, hi, hf, turno, horas = t
        try:
            eid_i = int(eid)
        except (TypeError, ValueError):
            continue
        ini, fin = _intervalo_datetime_desde_turno(str(fecha_s), str(hi), str(hf))
        if ini is None or fin is None:
            continue
        by_eid[eid_i].append((t, ini, fin))

    out: list = []
    descartes = 0
    for eid_i in sorted(by_eid.keys()):
        bloques = sorted(by_eid[eid_i], key=lambda x: x[1])
        ultimo_fin: datetime | None = None
        for fila, ini, fin in bloques:
            if ultimo_fin is not None and ini - ultimo_fin < gap:
                descartes += 1
                continue
            out.append(fila)
            ultimo_fin = fin
    return out, descartes


def _hora_a_min(hhmm: str) -> int:
    p = str(hhmm or "").strip().split(":")
    h = int(p[0]) if p and p[0].isdigit() else 0
    m = int(p[1]) if len(p) > 1 and p[1].isdigit() else 0
    # Admitimos 24:00 como cierre de día.
    if h == 24 and m == 0:
        return 24 * 60
    h = min(max(h, 0), 23)
    m = min(max(m, 0), 59)
    return h * 60 + m


def _min_a_hora(total_min: int) -> str:
    h, m = divmod(max(0, total_min), 60)
    return f"{h:02d}:{m:02d}"


def _min_a_hora_reloj(total_min: int) -> str:
    """Minutos absolutos -> hora de reloj 00:00..24:00 para guardar/mostrar."""
    tm = int(total_min)
    if tm == 24 * 60:
        return "24:00"
    tm = tm % (24 * 60)
    h, m = divmod(tm, 60)
    return f"{h:02d}:{m:02d}"


def _tramo_en_hora_punta(ini_min: int, fin_min: int) -> bool:
    """
    True si el tramo pisa horas punta operativas.
    Ventanas por defecto:
    - comida: 13:00-17:00
    - cena: 20:00-24:00
    - cierre extendido: 00:00-01:00 (24:00-25:00 en minutos absolutos)
    """
    if fin_min <= ini_min:
        return False
    puntas = _ventanas_hora_punta_default()
    for a, b in puntas:
        if ini_min < b and fin_min > a:
            return True
    return False


def _encajar_tramo_en_hora_punta(
    ini_min: int,
    fin_min: int,
    dur_min: int,
    ventanas_punta: list[tuple[int, int]] | None = None,
) -> tuple[int, int] | None:
    """
    Busca un subtramo de `dur_min` dentro de [ini_min, fin_min] que caiga en hora punta.
    """
    if dur_min <= 0 or fin_min <= ini_min:
        return None
    puntas = list(ventanas_punta or _ventanas_hora_punta_default())
    for a, b in puntas:
        s = max(ini_min, a)
        e = min(fin_min, b)
        if e - s >= dur_min:
            return s, s + dur_min
    return None


def _ventanas_hora_punta_default() -> list[tuple[int, int]]:
    return [
        (13 * 60, 17 * 60),
        (20 * 60, 24 * 60),
        (24 * 60, 25 * 60),
    ]


def _leer_horas_punta_desde_form(form) -> list[tuple[int, int]]:
    """Horas punta configurables por cliente (comida/cena), con fallback seguro."""
    c_ini = (form.get("hora_punta_comida_inicio") or "").strip()
    c_fin = (form.get("hora_punta_comida_fin") or "").strip()
    n_ini = (form.get("hora_punta_cena_inicio") or "").strip()
    n_fin = (form.get("hora_punta_cena_fin") or "").strip()

    def _rango(ini_s: str, fin_s: str) -> tuple[int, int] | None:
        if not ini_s or not fin_s:
            return None
        try:
            a = _hora_a_min(ini_s)
            b = _hora_a_min(fin_s)
        except Exception:
            return None
        if b <= a:
            b += 24 * 60
        if b <= a:
            return None
        return (a, b)

    out: list[tuple[int, int]] = []
    r1 = _rango(c_ini, c_fin)
    r2 = _rango(n_ini, n_fin)
    if r1:
        out.append(r1)
    if r2:
        out.append(r2)
    return out if out else _ventanas_hora_punta_default()


def _franja_cfg_normalizada(config: dict | None) -> dict:
    """Configuración de límites y etiquetas para mañana/tarde/noche o dos bloques."""
    c = config or {}
    modo = (c.get("franja_modo") or "tres").strip().lower()
    if modo not in ("tres", "dos"):
        modo = "tres"
    hm = _hora_a_min((c.get("franja_hasta_manana") or "14:00").strip() or "14:00")
    ht = _hora_a_min((c.get("franja_hasta_tarde") or "20:00").strip() or "20:00")
    corte = _hora_a_min((c.get("franja_corte_dos") or "16:00").strip() or "16:00")
    if modo == "tres" and hm >= ht:
        ht = min(hm + 60, 24 * 60)
    nm = (c.get("franja_nombre_manana") or "").strip() or "Mañana"
    nt = (c.get("franja_nombre_tarde") or "").strip() or "Tarde"
    nn = (c.get("franja_nombre_noche") or "").strip() or "Noche"
    labels = {"manana": nm, "tarde": nt, "noche": nn}
    hints = {}
    if modo == "dos":
        corte_s = _min_a_hora(corte)
        hints["manana"] = f"Inicio antes de {corte_s}"
        hints["tarde"] = ""
        hints["noche"] = f"Desde {corte_s}"
    else:
        hm_s, ht_s = _min_a_hora(hm), _min_a_hora(ht)
        hints["manana"] = f"Inicio antes de {hm_s}"
        hints["tarde"] = f"{hm_s} – antes de {ht_s}"
        hints["noche"] = f"Desde {ht_s}"
    return {
        "modo": modo,
        "hasta_manana_min": hm,
        "hasta_tarde_min": ht,
        "corte_dos_min": corte,
        "labels": labels,
        "hints": hints,
    }


def _franja_cfg_from_db(db) -> dict:
    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa

    ensure_config_empresa_table(db)
    return _franja_cfg_normalizada(get_config_empresa(db))


def _franja_ui_para_template(fc: dict) -> dict:
    """Textos para plantilla Horarios (leyenda y opciones del filtro)."""
    modo = fc.get("modo") or "tres"
    lb = fc.get("labels") or {}
    hnt = fc.get("hints") or {}
    if modo == "dos":
        leyenda = (
            f"Dos turnos: «{lb.get('manana', 'Mañana')}» si la hora de inicio es anterior al corte; "
            f"«{lb.get('noche', 'Noche')}» desde el corte en adelante."
        )
        pills = [
            f"{lb.get('manana', 'Mañana')}: {hnt.get('manana', '')}",
            f"{lb.get('noche', 'Noche')}: {hnt.get('noche', '')}",
        ]
    else:
        leyenda = (
            f"Tres franjas: «{lb.get('manana', 'Mañana')}» ({hnt.get('manana', '')}), "
            f"«{lb.get('tarde', 'Tarde')}» ({hnt.get('tarde', '')}), "
            f"«{lb.get('noche', 'Noche')}» ({hnt.get('noche', '')})."
        )
        pills = [
            f"{lb.get('manana', 'Mañana')}: {hnt.get('manana', '')}",
            f"{lb.get('tarde', 'Tarde')}: {hnt.get('tarde', '')}",
            f"{lb.get('noche', 'Noche')}: {hnt.get('noche', '')}",
        ]
    return {
        "modo": modo,
        "label_manana": lb.get("manana", "Mañana"),
        "label_tarde": lb.get("tarde", "Tarde"),
        "label_noche": lb.get("noche", "Noche"),
        "leyenda": leyenda,
        "pills": pills,
        "mostrar_tarde_filtro": modo != "dos",
    }


def _clasificar_franja_horario(hora_inicio: str | None, franja_cfg: dict | None = None) -> str:
    """mañana | tarde | noche según hora de inicio y configuración del establecimiento."""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_normalizada(None)
    hi = (hora_inicio or "00:00")[:8]
    try:
        p = hi.replace(".", ":").split(":")
        hh = int(p[0])
        mm = int(p[1]) if len(p) > 1 else 0
    except (ValueError, IndexError):
        return "otro"
    mins = hh * 60 + mm
    if fc.get("modo") == "dos":
        if mins < int(fc["corte_dos_min"]):
            return "manana"
        return "noche"
    if mins < int(fc["hasta_manana_min"]):
        return "manana"
    if mins < int(fc["hasta_tarde_min"]):
        return "tarde"
    return "noche"


def _leer_config_cobertura(form):
    pref_inicio = (form.get("pref_inicio") or "").strip()
    pref_fin = (form.get("pref_fin") or "").strip()
    min_personal_raw = (form.get("min_personal_turno") or "").strip()
    try:
        min_personal = int(min_personal_raw) if min_personal_raw else 0
    except ValueError:
        min_personal = 0
    if not pref_inicio or not pref_fin or min_personal <= 0:
        return None
    ini = _hora_a_min(pref_inicio)
    fin = _hora_a_min(pref_fin)
    if fin <= ini:
        return None
    return {"inicio_min": ini, "fin_min": fin, "min_personal": min_personal}


def _extraer_franja_desde_horario_empresa(horario_txt: str):
    """
    Intenta inferir franja de apertura/cierre desde texto libre de configuración.
    Acepta rangos con guion o «a», o dos HH:MM seguidos (p. ej. «9:00 01:00» = hasta cierre nocturno).
    Evita mezclar líneas (p. ej. horario general + «Cocina …») al usar min/max de todas las horas.
    """
    txt = (horario_txt or "").strip().lower()
    if not txt:
        return None

    def _rango_desde_pares(h1: int, m1: int, h2: int, m2: int) -> dict | None:
        if h1 == 24:
            h1, m1 = 24, 0
        if h2 == 24:
            h2, m2 = 24, 0
        ini = _hora_a_min(f"{h1:02d}:{m1:02d}")
        fin = _hora_a_min(f"{h2:02d}:{m2:02d}")
        if fin <= ini:
            fin += 24 * 60
        if fin > ini:
            return {"inicio_min": ini, "fin_min": fin}
        return None

    # 1) Rango explícito (ej. "9 a 24", "09:00-01:00", "10-18").
    rg = re.search(
        r"\b(\d{1,2})(?::([0-5]\d))?\s*(?:a|al|hasta|-|–|—)\s*(\d{1,2})(?::([0-5]\d))?\b",
        txt,
    )
    if rg:
        r = _rango_desde_pares(
            int(rg.group(1)),
            int(rg.group(2) or 0),
            int(rg.group(3)),
            int(rg.group(4) or 0),
        )
        if r:
            return r

    # 1b) Dos HH:MM seguidos solo con espacios: "09:00 01:00" (sin guion; cierre tras medianoche).
    rg_sp = re.search(
        r"\b(\d{1,2}):([0-5]\d)\s+(\d{1,2}):([0-5]\d)\b",
        txt.split("\n", 1)[0],
    )
    if rg_sp:
        r = _rango_desde_pares(
            int(rg_sp.group(1)),
            int(rg_sp.group(2)),
            int(rg_sp.group(3)),
            int(rg_sp.group(4)),
        )
        if r:
            return r

    def _mins_en_texto(block: str) -> list[int]:
        out: list[int] = []
        for h, m in re.findall(r"\b([01]?\d|2[0-4]):([0-5]\d)\b", block):
            try:
                out.append(_hora_a_min(f"{int(h):02d}:{int(m):02d}"))
            except ValueError:
                continue
        return out

    # 2) Solo la primera línea: evita mezclar "Lunes… 9:00 01:00" con "Cocina 8:00 00:00".
    linea1 = txt.split("\n", 1)[0].strip()
    mins1 = _mins_en_texto(linea1)
    # Pares (ini_min, fin_min) ya en minutos:
    if len(mins1) == 2:
        ini, fin = mins1[0], mins1[1]
        if fin <= ini:
            fin += 24 * 60
        if fin > ini:
            return {"inicio_min": ini, "fin_min": fin}
    if len(mins1) > 2:
        ini = min(mins1)
        fin = max(mins1)
        if fin > ini:
            return {"inicio_min": ini, "fin_min": fin}

    # 3) Fallback global (varias horas en un solo párrafo): dos primeras en orden, o min/max si hay más.
    mins_all = _mins_en_texto(txt)
    if len(mins_all) == 2:
        ini, fin = mins_all[0], mins_all[1]
        if fin <= ini:
            fin = 24 * 60
        if fin > ini:
            return {"inicio_min": ini, "fin_min": fin}
    if len(mins_all) > 2:
        ini = min(mins_all)
        fin = max(mins_all)
        if fin > ini:
            return {"inicio_min": ini, "fin_min": fin}
    return None


def _leer_config_cobertura_con_fallback(form, horario_empresa_txt: str):
    """
    1) Usa pref_inicio/pref_fin/min_personal del formulario si vienen completos.
    2) Si faltan horas, usa la franja de Configuración general del local.
    """
    cfg = _leer_config_cobertura(form)
    if cfg:
        return cfg
    min_personal_raw = (form.get("min_personal_turno") or "").strip()
    try:
        min_personal = int(min_personal_raw) if min_personal_raw else 0
    except ValueError:
        min_personal = 0
    franja = _extraer_franja_desde_horario_empresa(horario_empresa_txt)
    if not franja:
        return None
    # Si no se indicó dotación mínima, al menos mantener 1 persona en toda la franja.
    if min_personal <= 0:
        min_personal = 1
    return {
        "inicio_min": franja["inicio_min"],
        "fin_min": franja["fin_min"],
        "min_personal": min_personal,
    }


def _parsear_reglas_sector(raw: str) -> list[dict]:
    """
    Formato por línea:
    Sector|HH:MM-HH:MM|min_personal
    Ej: Barra|11:00-01:00|2
    """
    reglas = []
    for ln in (raw or "").splitlines():
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        parts = [p.strip() for p in s.split("|")]
        if len(parts) < 3:
            continue
        nombre = parts[0]
        franja = parts[1]
        min_raw = parts[2]
        if "-" not in franja:
            continue
        ini_s, fin_s = [x.strip() for x in franja.split("-", 1)]
        try:
            ini = _hora_a_min(ini_s)
            fin = _hora_a_min(fin_s)
            min_personal = int(min_raw)
        except (TypeError, ValueError):
            continue
        # Si cierre cruza medianoche, extendemos al día siguiente.
        if fin <= ini:
            fin += 24 * 60
        if min_personal <= 0:
            continue
        reglas.append(
            {
                "sector": nombre,
                "inicio_min": ini,
                "fin_min": fin,
                "min_personal": min_personal,
            }
        )
    return reglas


def _leer_config_cobertura_sectores(form):
    raw = (form.get("sectores_config") or "").strip()
    reglas = _parsear_reglas_sector(raw)
    return reglas if reglas else None


def _franja_operativa(form, horario_empresa_txt: str) -> dict | None:
    """Franja horaria: prioridad formulario (pref_inicio/fin), si no, texto empresa."""
    pi = (form.get("pref_inicio") or "").strip()
    pf = (form.get("pref_fin") or "").strip()
    if pi and pf:
        ini = _hora_a_min(pi)
        fin = _hora_a_min(pf)
        if fin <= ini:
            fin += 24 * 60
        if fin > ini:
            return {"inicio_min": ini, "fin_min": fin}
    return _extraer_franja_desde_horario_empresa(horario_empresa_txt)


def _resolver_reglas_sector_dotacion(form, horario_empresa_txt: str) -> list[dict] | None:
    """
    Si no hay texto en sectores_config, construye reglas Barra/Sala/Cocina
    con la misma franja (empresa o formulario) y dotación numérica por campo.
    """
    franja = _franja_operativa(form, horario_empresa_txt)
    if not franja:
        return None
    ini, fin = int(franja["inicio_min"]), int(franja["fin_min"])
    hi = _min_a_hora(ini)
    hf = _min_a_hora(fin)
    reglas: list[dict] = []

    def _int(name: str) -> int:
        try:
            return max(0, int((form.get(name) or "0").strip() or 0))
        except ValueError:
            return 0

    for key_sector, form_key in (
        ("Barra", "dotacion_barra"),
        ("Sala", "dotacion_sala"),
        ("Cocina", "dotacion_cocina"),
    ):
        n = _int(form_key)
        if n > 0:
            reglas.append(
                {
                    "sector": key_sector,
                    "inicio_min": ini,
                    "fin_min": fin,
                    "min_personal": n,
                }
            )
    return reglas if reglas else None


def _resolver_cobertura_sectores_final(form, horario_empresa_txt: str) -> list[dict] | None:
    """
    Resuelve cobertura por modo explícito:
    - dotacion: usa dotación global Barra/Sala/Cocina.
    - frentes: usa reglas de sectores_config.
    Si no viene modo (compatibilidad), mantiene prioridad legacy:
    sectores_config > dotación global.
    """
    modo = str((form.get("cobertura_modo") or "")).strip().lower()
    raw = (form.get("sectores_config") or "").strip()
    if modo == "frentes":
        reglas = _parsear_reglas_sector(raw)
        return reglas if reglas else None
    if modo == "dotacion":
        return _resolver_reglas_sector_dotacion(form, horario_empresa_txt)
    if raw:
        reglas = _parsear_reglas_sector(raw)
        return reglas if reglas else None
    return _resolver_reglas_sector_dotacion(form, horario_empresa_txt)


def _categorias_sin_servicio(reglas: list[dict] | None) -> list[str]:
    """Frentes obligatorios que no tienen ninguna regla activa."""
    req = ("Barra", "Sala", "Cocina")
    if not reglas:
        return list(req)
    presentes = set()
    for r in reglas:
        sec = str((r or {}).get("sector") or "").strip().lower()
        if sec == "barra":
            presentes.add("Barra")
        elif sec == "sala":
            presentes.add("Sala")
        elif sec == "cocina":
            presentes.add("Cocina")
    return [x for x in req if x not in presentes]


def _dias_libres_aprobados_por_empleado(
    db,
    fecha_inicio: str,
    fecha_fin: str,
    empleados_ids: list[int] | None = None,
) -> dict[int, set[str]]:
    """
    Devuelve días bloqueados por empleado a partir de solicitudes aprobadas
    (vacaciones, permisos, etc.) dentro del rango.
    """
    out: dict[int, set[str]] = defaultdict(set)
    if not tabla_existe(db, "solicitudes"):
        return out
    cols = columnas_tabla(db, "solicitudes")
    if not {"empleado_id", "fecha_inicio", "estado"}.issubset(set(cols)):
        return out
    if not fecha_inicio or not fecha_fin:
        return out
    try:
        fi = date.fromisoformat(str(fecha_inicio))
        ff = date.fromisoformat(str(fecha_fin))
    except ValueError:
        return out
    if fi > ff:
        fi, ff = ff, fi

    where_ids = ""
    params: list = [str(ff), str(fi)]
    if empleados_ids:
        marks = ",".join("?" for _ in empleados_ids)
        where_ids = f" AND empleado_id IN ({marks})"
        params.extend(int(x) for x in empleados_ids)

    # Solapes con el rango [fi, ff].
    rows = db.execute(
        f"""
        SELECT empleado_id, fecha_inicio, COALESCE(fecha_fin, fecha_inicio) AS fecha_fin
        FROM solicitudes
        WHERE LOWER(TRIM(COALESCE(estado, ''))) = 'aprobada'
          AND COALESCE(fecha_inicio, '') <> ''
          AND COALESCE(fecha_fin, fecha_inicio) >= ?
          AND fecha_inicio <= ?
          {where_ids}
        """,
        tuple(params),
    ).fetchall()

    for r in rows:
        try:
            eid = int(r["empleado_id"])
            di = date.fromisoformat(str(r["fecha_inicio"]))
            df = date.fromisoformat(str(r["fecha_fin"]))
        except (TypeError, ValueError):
            continue
        if df < di:
            di, df = df, di
        if di < fi:
            di = fi
        if df > ff:
            df = ff
        cur = di
        while cur <= df:
            out[eid].add(cur.isoformat())
            cur += timedelta(days=1)
    return out


def _resumen_empleados_por_puesto(empleados_rows) -> str:
    """Lista compacta Nombre→puesto+departamento para el prompt de IA."""
    grupos: dict[str, list[str]] = defaultdict(list)
    for e in empleados_rows:
        ed = dict(e)
        etiqueta = _etiqueta_grupo_empleado_prompt(ed)
        nom = (ed.get("nombre") or "").strip()
        if "apellido" in ed and ed.get("apellido"):
            nom = f"{nom} {ed.get('apellido')}".strip()
        if nom:
            grupos[etiqueta].append(nom)
    partes = []
    for etiqueta in sorted(grupos.keys(), key=lambda x: x.lower()):
        nombres = grupos[etiqueta][:10]
        suf = ""
        if len(grupos[etiqueta]) > 10:
            suf = f" (+{len(grupos[etiqueta]) - 10} más)"
        partes.append(f"{etiqueta}: {', '.join(nombres)}{suf}")
    lim = _RESUMEN_POR_PUESTO_IA_MAX
    return " | ".join(partes)[:lim]


def _txt_sin_tildes(s: str) -> str:
    """Minúsculas y sin acentos para comparar puestos (Sala/salón, cocina/cocinero…)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s))
    return "".join(c for c in s if unicodedata.category(c) != "Mn").lower()


def _empleado_texto_sectores(emp_meta: dict) -> str:
    return _txt_sin_tildes(
        f"{emp_meta.get('puesto', '')} {emp_meta.get('departamento', '')} {emp_meta.get('observaciones', '')}"
    )


def _es_perfil_encargado(emp_meta: dict | None) -> bool:
    """Encargado / jefe / gerencia en ficha (heurística para repartir franjas al generar por reglas)."""
    if not emp_meta:
        return False
    t = _empleado_texto_sectores(emp_meta)
    if not t.strip():
        return False
    for m in (
        "encargad",
        "jefe de",
        "jefe sala",
        "jefe de sala",
        "subgerente",
        "gerente",
        "gerencia",
        "supervisor",
        "supervisora",
        "responsable",
        "director",
        "directora",
        "maitre",
        "metre",
        "sumiller",
        "capitan",
        "capitania",
        "coordinador",
        "coordinadora",
    ):
        if m in t:
            return True
    return False


def _perfil_solo_cocina(emp_meta: dict) -> bool:
    """Cocina / fondo sin rol explícito de barra o sala (no deben cubrir Barra/Sala)."""
    t = _empleado_texto_sectores(emp_meta)
    if not t.strip():
        return False
    indicios = (
        "cocinero",
        "cocinera",
        "cocina",
        "chef",
        "plancha",
        "office",
        "friega",
        "pase",
        "pasteler",
        "pizzero",
        "ayudante de cocina",
    )
    if not any(x in t for x in indicios):
        return False
    mezcla = (
        "barra",
        "barman",
        "bartend",
        "coctel",
        "chapista",
        "camarer",
        "meser",
        "sala",
        "salon",
        "comedor",
        "terraza",
    )
    if any(x in t for x in mezcla):
        return False
    return True


def _perfil_cocina(emp_meta: dict) -> bool:
    """
    Personal de cocina (incluye perfiles mixtos declarados en ficha).
    Regla de negocio actual: cocina no rota a otros frentes.
    """
    t = _empleado_texto_sectores(emp_meta)
    if not t.strip():
        return False
    return any(
        x in t
        for x in (
            "cocinero",
            "cocinera",
            "cocina",
            "chef",
            "plancha",
            "office",
            "friega",
            "pase",
            "pasteler",
            "pizzero",
            "ayudante de cocina",
        )
    )


def _perfil_mixto_barra_sala(emp_meta: dict) -> bool:
    """Perfil polivalente de sala/barra según ficha (puesto/departamento/observaciones)."""
    t = _empleado_texto_sectores(emp_meta)
    if not t.strip():
        return False
    tiene_barra = any(x in t for x in ("barra", "barman", "bartend", "coctel", "cocktail", "chapista"))
    tiene_sala = any(
        x in t
        for x in (
            "sala",
            "camarer",
            "meser",
            "comedor",
            "terraza",
            "mozo",
            "moza",
            "runner",
        )
    )
    if tiene_barra and tiene_sala:
        return True
    # Marcadores explícitos para ficha RRHH.
    return any(
        x in t
        for x in (
            "polivalente",
            "multifuncion",
            "mixto",
            "barra/sala",
            "sala/barra",
            "doble frente",
        )
    )


def _nombre_slash_corto(nombre: str | None) -> str:
    """Nombre/apellido en minúsculas para resúmenes (p. ej. diego/garcía)."""
    n = (nombre or "").strip()
    if not n:
        return "?"
    parts = n.split()
    if len(parts) >= 2:
        return f"{parts[0].lower()}/{parts[-1].lower()}"
    return parts[0].lower()


def _inferir_sector_fila_horario(h: dict) -> str | None:
    """Cocina / Barra / Sala según texto de turno o ficha (puesto/departamento)."""
    turno = (h.get("turno") or "").strip()
    m = re.search(r"(?i)cobertura\s+(.+)$", turno.strip())
    if m:
        tail = (m.group(1) or "").strip()
        for canon in ("Cocina", "Barra", "Sala"):
            if _txt_sin_tildes(tail) == _txt_sin_tildes(canon):
                return canon
        for canon in ("Cocina", "Barra", "Sala"):
            if canon.lower() in tail.lower():
                return canon
    barra, sala = _turno_sugiere_barra_o_sala_sin_cocina(turno)
    t = _txt_sin_tildes(turno)
    coc = any(
        x in t
        for x in (
            "cocina",
            "cocin",
            "chef",
            "plancha",
            "pizzero",
            "pastel",
            "office",
            "fondo",
        )
    )
    if coc and not (barra or sala):
        return "Cocina"
    if barra and not sala:
        return "Barra"
    if sala and not barra:
        return "Sala"
    dep = _txt_sin_tildes((h.get("departamento") or ""))
    puesto = _txt_sin_tildes((h.get("puesto") or ""))
    blob = f"{dep} {puesto}"
    if any(
        x in blob
        for x in (
            "cocina",
            "cocin",
            "chef",
            "pastel",
            "pizzero",
            "plancha",
            "office",
            "friega",
            "ayudante de cocina",
        )
    ):
        return "Cocina"
    if any(x in blob for x in ("barra", "barman", "bartend", "coctel", "chapista")):
        return "Barra"
    if any(
        x in blob
        for x in (
            "sala",
            "camarer",
            "meser",
            "comedor",
            "terraza",
            "mozo",
            "moza",
            "runner",
        )
    ):
        return "Sala"
    return None


def _tabla_cobertura_franja_dia(horarios_dia: list, franja_cfg: dict | None) -> dict:
    """Resumen Mañana | Tarde (o 2º bloque en modo dos) × Cocina/Barra/Sala para un día."""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_normalizada(None)
    lb = fc.get("labels") or {}
    modo = fc.get("modo") or "tres"
    col1 = lb.get("manana", "Mañana")
    col2 = lb.get("tarde", "Tarde") if modo == "tres" else lb.get("noche", "Tarde")
    rows_in = horarios_dia or []
    from collections import OrderedDict

    sectores_fijos = ("Cocina", "Barra", "Sala")
    grid = {s: {"manana": OrderedDict(), "tarde": OrderedDict()} for s in sectores_fijos}
    otros = {"manana": OrderedDict(), "tarde": OrderedDict()}

    for h in rows_in:
        eid = h.get("empleado_id")
        if eid is None:
            continue
        fk = _clasificar_franja_horario(h.get("hora_inicio"), fc)
        bin_slot = "manana" if fk == "manana" else "tarde"
        sec = _inferir_sector_fila_horario(h)
        disp = _nombre_slash_corto(h.get("empleado_nombre"))
        eid_i = int(eid)
        if sec in grid:
            grid[sec][bin_slot][eid_i] = disp
        else:
            otros[bin_slot][eid_i] = disp

    def _join(od: OrderedDict) -> str:
        if not od:
            return ""
        return ", ".join(od.values())

    filas = []
    for s in sectores_fijos:
        m = _join(grid[s]["manana"])
        t = _join(grid[s]["tarde"])
        filas.append({"sector": s, "manana": m or "—", "tarde": t or "—"})

    om = _join(otros["manana"])
    ot = _join(otros["tarde"])
    if om or ot:
        filas.append({"sector": "Otros", "manana": om or "—", "tarde": ot or "—"})

    nota = ""
    if modo == "tres":
        nota = "La columna derecha agrupa tarde y noche según la hora de inicio del turno."
    else:
        nota = "Segundo bloque: turnos con inicio a partir del corte configurado (modo dos franjas)."

    return {
        "col_manana": col1,
        "col_tarde": col2,
        "filas": filas,
        "nota": nota,
    }


def _tabla_cobertura_franja_semana(horarios_rango: list, franja_cfg: dict | None) -> list[dict]:
    """Lista de tablas día a día para semana: [{fecha, fecha_label, tabla}, ...]."""
    por_fecha: dict[str, list] = defaultdict(list)
    for h in horarios_rango or []:
        f = str((h or {}).get("fecha") or "").strip()
        if not f:
            continue
        por_fecha[f].append(h)

    out: list[dict] = []
    for fecha_s in sorted(por_fecha.keys()):
        try:
            fd = date.fromisoformat(fecha_s)
            fecha_label = fd.strftime("%d/%m/%Y")
        except ValueError:
            fecha_label = fecha_s
        out.append(
            {
                "fecha": fecha_s,
                "fecha_label": fecha_label,
                "tabla": _tabla_cobertura_franja_dia(por_fecha.get(fecha_s) or [], franja_cfg),
            }
        )
    return out


def _turno_sugiere_barra_o_sala_sin_cocina(turno: str) -> tuple[bool, bool]:
    """(implica_barra, implica_sala) según texto del turno (para filtrar IA)."""
    t = _txt_sin_tildes(turno or "")
    barra = any(
        x in t
        for x in (
            "barra",
            "barman",
            "bartend",
            "coctel",
            "cocktail",
            "chapista",
        )
    )
    sala = any(
        x in t
        for x in (
            "sala",
            "camarer",
            "meser",
            "comedor",
            "salon",
            "terraza",
            "mozo",
            "moza",
        )
    )
    return barra, sala


def _agrupar_horarios_por_franja(
    horarios_list: list, franja_cfg: dict | None = None
) -> list[dict]:
    """Lista de bloques {key, label, hint, rows} para la vista (mañana/tarde/noche)."""
    fc = franja_cfg if franja_cfg is not None else _franja_cfg_normalizada(None)
    buckets: dict[str, list] = {"manana": [], "tarde": [], "noche": [], "otro": []}
    for h in horarios_list or []:
        hd = dict(h)
        k = _clasificar_franja_horario(hd.get("hora_inicio"), fc)
        if k not in buckets:
            k = "otro"
        buckets[k].append(hd)

    def _sort_key(x):
        return (str(x.get("hora_inicio") or ""), str(x.get("empleado_nombre") or ""))

    for k in buckets:
        buckets[k].sort(key=_sort_key)

    lb = fc.get("labels") or {}
    hnt = fc.get("hints") or {}
    bloques = []
    if fc.get("modo") == "dos":
        meta = [
            ("manana", lb.get("manana", "Mañana"), hnt.get("manana", ""), "warning", "bi-sun-fill"),
            ("noche", lb.get("noche", "Noche"), hnt.get("noche", ""), "dark", "bi-moon-fill"),
        ]
    else:
        meta = [
            ("manana", lb.get("manana", "Mañana"), hnt.get("manana", ""), "warning", "bi-sun-fill"),
            ("tarde", lb.get("tarde", "Tarde"), hnt.get("tarde", ""), "info", "bi-brightness-high-fill"),
            ("noche", lb.get("noche", "Noche"), hnt.get("noche", ""), "dark", "bi-moon-fill"),
        ]
    for key, label, hint, bs, icon in meta:
        rows = buckets.get(key) or []
        if rows:
            bloques.append(
                {
                    "key": key,
                    "label": label,
                    "hint": hint,
                    "bs_theme": bs,
                    "icon": icon,
                    "rows": rows,
                }
            )
    if buckets.get("otro"):
        bloques.append(
            {
                "key": "otro",
                "label": "Otros horarios",
                "hint": "Fuera de franjas habituales",
                "bs_theme": "secondary",
                "icon": "bi-clock",
                "rows": buckets["otro"],
            }
        )
    return bloques


def _empleado_esta_ocupado(turnos: list[dict], eid: int, fecha_s: str, ini: int, fin: int) -> bool:
    for t in turnos:
        if t["eid"] != eid or t["fecha"] != fecha_s:
            continue
        # Solape estricto.
        if ini < t["fin"] and fin > t["ini"]:
            return True
    return False


def _empleado_match_sector(emp_meta: dict, sector: str) -> bool:
    st = _txt_sin_tildes((sector or "").strip())
    if not st:
        return False
    txt = _empleado_texto_sectores(emp_meta)
    if not txt.strip():
        return False
    dep = _txt_sin_tildes((emp_meta.get("departamento") or "").strip())
    # Regla dura: cocina solo cocina (no polivalencia a barra/sala).
    if st == "barra" and _perfil_cocina(emp_meta):
        return False
    if st == "sala" and _perfil_cocina(emp_meta):
        return False
    if st in ("barra", "sala") and _perfil_mixto_barra_sala(emp_meta):
        return True
    # Departamento acota el frente (RRHH): prioridad sobre ambigüedad solo por puesto
    if dep:
        if st == "cocina" and any(
            x in dep
            for x in (
                "cocina",
                "cociner",
                "fondo",
                "pasteler",
                "pizzero",
                "buffet",
            )
        ):
            return True
        if st == "sala" and any(
            x in dep
            for x in (
                "sala",
                "comedor",
                "mesas",
                "terraza",
                "pisos",
                "servicio",
            )
        ):
            return True
        if st == "barra" and any(x in dep for x in ("barra", "bebida", "coctel", "cocktail")):
            return True
        if any(x in dep for x in ("gerencia", "direccion", "director", "directora", "administracion")):
            return True
    # Coincidencia directa con el nombre del sector (p. ej. puesto "Sala" o "Jefe de sala")
    if st in txt:
        return True
    aliases = {
        "barra": [
            "barra",
            "barman",
            "bartend",
            "coctel",
            "cocktail",
            "chapista",
        ],
        # Sala = mesas / servicio de comedor (muchas fichas dicen "Camarero" sin la palabra "sala")
        "sala": [
            "sala",
            "camarer",
            "meser",
            "mozo",
            "moza",
            "runner",
            "terraza",
            "comedor",
            "salon",
            "metre",
            "jefe de sala",
            "atencion",
            "dependient",
            "sumiller",
            "copeo",
            "pisos",
            "floor",
        ],
        "cocina": [
            "cocina",
            "cocin",
            "chef",
            "plancha",
            "office",
            "friega",
            "pase",
            "ayudante de cocina",
            "pastel",
            "pizzero",
        ],
    }
    for k, vals in aliases.items():
        if st == k and any(v in txt for v in vals):
            return True
    return False


def _empleado_apoyo_sector(emp_meta: dict, sector: str) -> bool:
    """
    Compatibilidad flexible de apoyo (último recurso).
    Caso principal: permitir que perfiles de Sala apoyen Barra.
    """
    st = _txt_sin_tildes((sector or "").strip())
    txt = _empleado_texto_sectores(emp_meta)
    if not txt.strip():
        return False
    if st == "barra":
        if _perfil_cocina(emp_meta):
            return False
        # Perfiles habituales de sala que pueden apoyar barra.
        return any(
            x in txt
            for x in (
                "sala",
                "camarer",
                "meser",
                "comedor",
                "terraza",
                "runner",
                "mozo",
                "moza",
                "metre",
                "maitre",
                "polivalente",
                "mixto",
            )
        )
    if st == "sala":
        if _perfil_cocina(emp_meta):
            return False
        # Apoyo inverso: perfiles de barra pueden apoyar sala.
        return any(
            x in txt
            for x in (
                "barra",
                "barman",
                "bartend",
                "coctel",
                "chapista",
                "polivalente",
                "mixto",
            )
        )
    if st == "cocina":
        # Politica operativa: cocina solo cocina (sin polivalencia).
        return False
    return False


def _score_afinidad_sector(emp_meta: dict, sector: str) -> int:
    """Puntúa qué tan apto es un perfil para un sector (más alto = mejor)."""
    st = _txt_sin_tildes((sector or "").strip())
    txt = _empleado_texto_sectores(emp_meta)
    if not st or not txt.strip():
        return 0
    score = 0
    if st in ("barra", "sala") and _perfil_mixto_barra_sala(emp_meta):
        score += 6
    if st in txt:
        score += 8
    aliases = {
        "barra": [
            "barra",
            "barman",
            "bartend",
            "coctel",
            "cocktail",
            "chapista",
        ],
        "sala": [
            "sala",
            "camarer",
            "meser",
            "mozo",
            "moza",
            "runner",
            "terraza",
            "comedor",
            "salon",
            "metre",
            "atencion",
            "dependient",
            "sumiller",
            "copeo",
            "pisos",
            "floor",
        ],
        "cocina": [
            "cocina",
            "cocin",
            "chef",
            "plancha",
            "office",
            "friega",
            "pase",
            "pastel",
            "pizzero",
        ],
    }
    for k, vals in aliases.items():
        if st == k:
            score += sum(2 for v in vals if v in txt)
    dep = _txt_sin_tildes((emp_meta.get("departamento") or "").strip())
    if dep:
        if st == "cocina" and any(x in dep for x in ("cocina", "cociner", "fondo", "pasteler")):
            score += 12
        if st == "sala" and any(x in dep for x in ("sala", "comedor", "mesas", "terraza")):
            score += 12
        if st == "barra" and any(x in dep for x in ("barra", "bebida", "coctel")):
            score += 12
        if any(x in dep for x in ("gerencia", "direccion", "director", "directora")):
            score += 4
    return score


def _orden_reglas_sector_sala_primero(reglas: list[dict]) -> list[dict]:
    """Cubre primero Sala (mesas), luego Barra y Cocina, para no quedarse sin personal de sala."""
    prio = {"Sala": 0, "Barra": 1, "Cocina": 2}
    return sorted(
        reglas,
        key=lambda r: (prio.get((r.get("sector") or ""), 99), (r.get("sector") or "").lower()),
    )


def _orden_reglas_por_frentes(reglas: list[dict], orden_frentes: str) -> list[dict]:
    """Orden configurable de frentes para generar por reglas."""
    orden = (orden_frentes or "").strip().lower()
    if orden == "cocina_sala_barra":
        prio = {"Cocina": 0, "Sala": 1, "Barra": 2}
    elif orden == "barra_sala_cocina":
        prio = {"Barra": 0, "Sala": 1, "Cocina": 2}
    else:
        # Comportamiento por defecto del sistema.
        prio = {"Sala": 0, "Barra": 1, "Cocina": 2}
    return sorted(
        reglas,
        key=lambda r: (prio.get((r.get("sector") or ""), 99), (r.get("sector") or "").lower()),
    )


def _ventanas_turno_legal(ini_min: int, fin_min: int) -> list[tuple[int, int]]:
    """Divide [ini, fin] en tramos consecutivos de como mucho la jornada máxima legal."""
    max_m = int(_MAX_HORAS_DIA_LEGAL * 60)
    if fin_min <= ini_min:
        fin_min += 24 * 60
    out = []
    cur = ini_min
    while cur < fin_min:
        end = min(cur + max_m, fin_min)
        if end - cur < 15:
            break
        out.append((cur, end))
        cur = end
    return out if out else [(ini_min, fin_min)]


def _etiqueta_bloque_desde_hora(ini_min: int) -> str:
    if ini_min < 14 * 60:
        return "Mañana"
    if ini_min < 20 * 60:
        return "Tarde"
    return "Noche"


def _intervalo_datetime_turno(fecha_s: str, ini_min: int, fin_min: int) -> tuple[datetime, datetime]:
    """Minutos desde medianoche → intervalo real; si fin <= ini, el cierre es al día siguiente."""
    d = date.fromisoformat(fecha_s)
    ini = datetime(d.year, d.month, d.day) + timedelta(minutes=int(ini_min))
    if fin_min > ini_min:
        fin = datetime(d.year, d.month, d.day) + timedelta(minutes=int(fin_min))
    else:
        d2 = d + timedelta(days=1)
        fin = datetime(d2.year, d2.month, d2.day) + timedelta(minutes=int(fin_min))
    return ini, fin


def _intervalos_respetan_descanso(
    existentes: list[tuple[datetime, datetime]],
    ini_n: datetime,
    fin_n: datetime,
    horas_descanso: float,
    *,
    permitir_partido_mismo_dia: bool = False,
    min_gap_partido_min: int = 60,
    bloquear_cierra_abre: bool = False,
    hora_cierre_min: int = 21 * 60,
    hora_apertura_max: int = 14 * 60,
) -> bool:
    """
    Sin solapes entre turnos y al menos horas_descanso entre el fin de uno y el inicio del siguiente
    (orden cronológico; evita cerrar tarde y abrir al día siguiente sin descanso suficiente).
    """
    if not existentes:
        return True
    gap = timedelta(hours=float(horas_descanso))
    todos = sorted(existentes + [(ini_n, fin_n)], key=lambda x: x[0])
    for i in range(len(todos)):
        for j in range(i + 1, len(todos)):
            a0, a1 = todos[i]
            b0, b1 = todos[j]
            if a0 < b1 and b0 < a1:
                return False
    for i in range(len(todos) - 1):
        a_fin = todos[i][1]
        b_ini = todos[i + 1][0]
        d_gap = b_ini - a_fin
        if bloquear_cierra_abre:
            # Regla operativa: quien cierra no abre al día siguiente.
            if (
                b_ini.date() == (a_fin.date() + timedelta(days=1))
                and (a_fin.hour * 60 + a_fin.minute) >= int(hora_cierre_min)
                and (b_ini.hour * 60 + b_ini.minute) < int(hora_apertura_max)
            ):
                return False
        if d_gap < gap:
            if (
                permitir_partido_mismo_dia
                and a_fin.date() == b_ini.date()
                and d_gap >= timedelta(minutes=max(0, int(min_gap_partido_min)))
            ):
                continue
            return False
    return True


def _fechas_generacion_reglas(fi: date, ff: date, priorizar_domingo: bool) -> list[date]:
    """
    Orden de días para asignar turnos. Si priorizar_domingo, en cada semana ISO se procesa
    primero el domingo (si cae en el rango) y después el resto en orden cronológico, para que
    el cupo semanal no se agote antes de cubrir el domingo.
    """
    if fi > ff:
        fi, ff = ff, fi
    if not priorizar_domingo:
        out: list[date] = []
        cur = fi
        while cur <= ff:
            out.append(cur)
            cur += timedelta(days=1)
        return out
    by_week: dict[tuple[int, int], list[date]] = defaultdict(list)
    cur = fi
    while cur <= ff:
        y, w, _ = cur.isocalendar()
        by_week[(y, w)].append(cur)
        cur += timedelta(days=1)
    ordered: list[date] = []
    for yw in sorted(by_week.keys()):
        dias = sorted(by_week[yw])
        domingos = [d for d in dias if d.weekday() == 6]
        otros = [d for d in dias if d.weekday() != 6]
        ordered.extend(domingos)
        ordered.extend(otros)
    return ordered


def _generar_pendientes_por_reglas(
    fecha_inicio: str,
    fecha_fin: str,
    reglas: list[dict],
    empleados_rows,
    horas_semana_por_empleado: dict,
    *,
    priorizar_domingo: bool = True,
    niveles_por_weekday: dict[int, float] | None = None,
    diversificar_encargados: bool = False,
    rellenar_hasta_contrato: bool = True,
    preferir_mixto_barra_sala: bool = True,
    preferencia_mixto_barra_sala: str = "sala",
    forzar_horas_contrato: bool = True,
    permitir_partido_cobertura: bool = False,
    descanso_min_partido_min: int = 180,
    descanso_entre_jornadas_h: float = 12.0,
    regla_cierra_no_abre: bool = True,
    permitir_apoyo_sala_en_barra: bool = True,
    priorizar_dias_criticos: bool = True,
    ventanas_hora_punta: list[tuple[int, int]] | None = None,
    permitir_cobertura_total: bool = True,
    modo_por_frentes: bool = False,
    orden_frentes: str = "sala_barra_cocina",
    modo_servicio_minimo: bool = False,
    dias_libres_cliente: dict[int, set[str]] | None = None,
) -> tuple[list[tuple], list[str]]:
    """
    Cuadrante determinista: por cada día y cada regla de sector, asigna min_personal
    empleados en paralelo en cada ventana horaria (recorta por jornada máxima legal).
    priorizar_domingo: si True, reparte primero los domingos de cada semana ISO dentro del rango.
    niveles_por_weekday: multiplicador por weekday (0=lun … 6=dom) sobre min_personal de la regla.
    diversificar_encargados: prioriza repartir perfiles de encargado en distintos turnos del día.
    rellenar_hasta_contrato: tras cubrir mínimos por regla, añade refuerzos para acercar horas
    semanales al contrato si hay disponibilidad y se respetan límites legales.
    preferir_mixto_barra_sala: da prioridad a perfiles polivalentes cuando el sector es
    Barra o Sala (útil para personal que rota entre ambos frentes).
    preferencia_mixto_barra_sala: regula a qué frente favorecer para perfiles mixtos
    ("sala", "barra" o "equilibrado").
    forzar_horas_contrato: intenta acercar a cada empleado a sus horas semanales de contrato
    añadiendo turnos extra por reglas y distribuyendolos según la necesidad por día (barras %).
    permitir_partido_cobertura: si faltan perfiles, permite un segundo turno en el mismo día
    (partido) como último recurso para cubrir servicio.
    descanso_min_partido_min: pausa mínima entre bloques de un mismo día en turno partido.
    descanso_entre_jornadas_h: descanso mínimo entre fin de un turno e inicio del siguiente.
    regla_cierra_no_abre: si cierra tarde, no permite apertura al día siguiente.
    permitir_apoyo_sala_en_barra: si falta personal en Barra, permite apoyo de perfiles de Sala.
    priorizar_dias_criticos: ordena asignación por días de mayor necesidad (% barras y fin de semana)
    para evitar que se agoten horas/descanso antes de cubrir picos de demanda.
    ventanas_hora_punta: ventanas configurables para colocar partidos en horas punta.
    permitir_cobertura_total: último recurso, permite cubrir cualquier frente con personal disponible.
    modo_servicio_minimo: rellena lo máximo posible y no trata faltantes como error duro.
    """
    advertencias: list[str] = []
    libres_map: dict[int, set[str]] = dias_libres_cliente or {}
    if not reglas:
        return [], [
            "Sin reglas de cobertura: indica dotación Barra/Sala/Cocina, "
            "o Inicio/Fin servicio + mínimos, o el texto «Cobertura por sector»."
        ]
    empleados_meta = {}
    ids_ord = []
    for e in empleados_rows:
        ed = dict(e)
        try:
            eid = int(ed.get("id"))
        except (TypeError, ValueError):
            continue
        empleados_meta[eid] = {
            "puesto": ed.get("puesto") or "",
            "departamento": ed.get("departamento") or "",
            "observaciones": ed.get("observaciones") or "",
        }
        ids_ord.append(eid)
    if not empleados_meta:
        return [], ["No hay empleados activos para asignar."]
    fi = date.fromisoformat(fecha_inicio)
    ff = date.fromisoformat(fecha_fin)
    if fi > ff:
        fi, ff = ff, fi
    pendientes: list[tuple] = []
    diarios = defaultdict(float)
    semanales = defaultdict(float)
    intervalos_por_eid: dict[int, list[tuple[datetime, datetime]]] = defaultdict(list)
    asignaciones_sector: list[tuple[str, str, int, int]] = []
    cierres_semanales = defaultdict(int)  # (eid, iso_year, iso_week) -> cierres
    cierres_por_fecha: set[tuple[int, str]] = set()  # (eid, YYYY-MM-DD)
    partidos_semanales = defaultdict(int)  # (eid, iso_year, iso_week) -> partidos

    def _cobertura_sector(fecha_s: str, sector_s: str, ini_m: int, fin_m: int) -> int:
        c = 0
        for f, s, a, b in asignaciones_sector:
            if f != fecha_s or s != sector_s:
                continue
            if ini_m < b and fin_m > a:
                c += 1
        return c

    def _max_cobertura_permitida(necesarios_slot: int, nivel_dia: float) -> int:
        n = max(0, int(necesarios_slot))
        if n <= 0:
            return 0
        if float(nivel_dia) <= 1.0:
            return n
        extra = max(1, int(math.ceil((float(nivel_dia) - 1.0) * n)))
        return n + extra

    def _es_turno_cierre(ini_m: int, fin_m: int) -> bool:
        return int(ini_m) >= 17 * 60 or int(fin_m) > 24 * 60

    def _rompe_max_cierres_consecutivos(eid: int, fecha_s: str, ini_m: int, fin_m: int) -> bool:
        # Politica operativa: cierres consecutivos permitidos (mientras no abran al dia siguiente).
        return False

    def horas_sem_acum(eid: int, fd: date) -> float:
        y, w, _ = fd.isocalendar()
        return float(semanales.get((eid, y, w), 0.0))

    def _max_dias_trabajo_semana(eid: int) -> int:
        """
        Límite operativo de días trabajados por semana según horas de contrato.
        Con jornada legal de 8h, evita cuadrantes de 6-7 días con microturnos.
        """
        contrato = float(horas_semana_por_empleado.get(eid, 40.0))
        if contrato <= 0:
            return 5
        # Regla práctica:
        # - Contratos ~40h: permitimos hasta 6 días para poder cerrar contrato
        #   cuando haya un bloque corto inevitable en la semana.
        # - Resto: aproximación por 8h/día.
        if contrato >= 39.0:
            return 6
        return max(1, min(6, int(math.ceil(contrato / _MAX_HORAS_DIA_LEGAL))))

    def _dias_trabajados_semana(eid: int, yk: int, wk: int) -> int:
        dias = set()
        for i0, _f0 in intervalos_por_eid[eid]:
            yi, wi, _ = i0.date().isocalendar()
            if yi == yk and wi == wk:
                dias.add(i0.date().isoformat())
        return len(dias)

    if modo_por_frentes:
        reglas_o = _orden_reglas_por_frentes(list(reglas), orden_frentes)
    else:
        reglas_o = _orden_reglas_sector_sala_primero(list(reglas))
    pref_mix = str(preferencia_mixto_barra_sala or "sala").strip().lower()
    if pref_mix not in ("sala", "barra", "equilibrado"):
        pref_mix = "sala"
    niveles_eff = niveles_por_weekday if niveles_por_weekday is not None else _niveles_carga_semana_default()
    dias_gen = list(_fechas_generacion_reglas(fi, ff, priorizar_domingo))
    # Mantener orden base de calendario evita concentrar todo en fin de semana.
    # Si se activa "priorizar dias criticos", adelantamos dias de mayor carga y
    # fin de semana para proteger cobertura en esos puntos.
    if priorizar_dias_criticos:
        dias_gen.sort(
            key=lambda d: (
                -float(niveles_eff.get(d.weekday(), 1.0)),
                -(1 if d.weekday() in (4, 5, 6) else 0),
                d,
            )
        )

    for cur in dias_gen:
        fecha_s = str(cur)
        y, w, _ = cur.isocalendar()
        enc_turnos_dia: dict[int, int] = defaultdict(int)
        for regla in reglas_o:
            sector = (regla.get("sector") or "").strip()
            try:
                ini = int(regla["inicio_min"])
                fin = int(regla["fin_min"])
                necesarios_base = int(regla["min_personal"])
            except (TypeError, ValueError, KeyError):
                continue
            if fin <= ini or necesarios_base <= 0:
                continue
            necesarios = _dotacion_nivelada_por_dia(necesarios_base, cur.weekday(), niveles_eff)
            nivel_dia = float(niveles_eff.get(cur.weekday(), 1.0))
            ventanas = _ventanas_turno_legal(ini, fin)
            for v_idx, (vini, vfin) in enumerate(ventanas):
                dur_h = round((vfin - vini) / 60.0, 2)
                if dur_h <= 0:
                    continue
                max_cobertura_slot = _max_cobertura_permitida(necesarios, nivel_dia)
                pool = [
                    eid
                    for eid in ids_ord
                    if _empleado_match_sector(empleados_meta[eid], sector)
                ]

                def _bucket_franja(ini_min: int) -> str:
                    # Agrupación operativa simple para equilibrio semanal.
                    return "manana" if int(ini_min) < 17 * 60 else "noche"

                def _sesgo_franja_semana(eid: int, yk: int, wk: int, bucket_obj: str) -> int:
                    """
                    Devuelve un sesgo que prioriza equilibrio mañana/noche por semana.
                    - Si estamos asignando mañana, favorece quien lleva menos mañanas (o más noches).
                    - Si estamos asignando noche, favorece quien lleva menos noches (o más mañanas).
                    Menor valor = mayor prioridad.
                    """
                    man = 0
                    noc = 0
                    for i0, _f0 in intervalos_por_eid[eid]:
                        yi, wi, _ = i0.date().isocalendar()
                        if yi != yk or wi != wk:
                            continue
                        ini_m = i0.hour * 60 + i0.minute
                        if ini_m < 17 * 60:
                            man += 1
                        else:
                            noc += 1
                    return (man - noc) if bucket_obj == "manana" else (noc - man)

                def _conteo_franja_semana(eid: int, yk: int, wk: int) -> tuple[int, int]:
                    man = 0
                    noc = 0
                    for i0, _f0 in intervalos_por_eid[eid]:
                        yi, wi, _ = i0.date().isocalendar()
                        if yi != yk or wi != wk:
                            continue
                        ini_m = i0.hour * 60 + i0.minute
                        if ini_m < 17 * 60:
                            man += 1
                        else:
                            noc += 1
                    return man, noc

                def _key_equidad(eid: int) -> tuple:
                    pref_mix_sector = 1
                    if (
                        preferir_mixto_barra_sala
                        and sector in ("Barra", "Sala")
                        and _perfil_mixto_barra_sala(empleados_meta.get(eid, {}))
                    ):
                        if pref_mix == "equilibrado":
                            pref_mix_sector = 0
                        elif pref_mix == "sala" and sector == "Sala":
                            pref_mix_sector = 0
                        elif pref_mix == "barra" and sector == "Barra":
                            pref_mix_sector = 0
                    bucket_obj = _bucket_franja(vini)
                    sesgo_franja = _sesgo_franja_semana(eid, y, w, bucket_obj)
                    return (
                        pref_mix_sector,
                        sesgo_franja,
                        cierres_semanales[(eid, y, w)],
                        -_score_afinidad_sector(empleados_meta[eid], sector),
                        horas_sem_acum(eid, cur)
                        / max(float(horas_semana_por_empleado.get(eid, 40.0)), 1.0),
                        eid,
                    )

                def _puede_asignar(
                    eid: int,
                    *,
                    permitir_partido: bool = False,
                    ini_min_eval: int | None = None,
                    fin_min_eval: int | None = None,
                    relajar_cierra_abre: bool = False,
                ) -> tuple[bool, str]:
                    ini_m = int(vini if ini_min_eval is None else ini_min_eval)
                    fin_m = int(vfin if fin_min_eval is None else fin_min_eval)
                    if fin_m <= ini_m:
                        return False, "rango_invalido"
                    if fecha_s in libres_map.get(int(eid), set()):
                        return False, "dia_libre_cliente"
                    dur_eval_h = round((fin_m - ini_m) / 60.0, 2)
                    if _cobertura_sector(fecha_s, sector, ini_m, fin_m) >= max_cobertura_slot:
                        return False, "tope_cobertura"
                    ini_dt, fin_dt = _intervalo_datetime_turno(fecha_s, ini_m, fin_m)
                    if permitir_partido:
                        mismo_dia = sum(
                            1 for i0, _f0 in intervalos_por_eid[eid] if i0.date().isoformat() == fecha_s
                        )
                        if mismo_dia >= 2:
                            return False, "max_turnos_dia"
                        if partidos_semanales[(eid, y, w)] >= 2:
                            return False, "max_partidos_semana"
                    if _rompe_max_cierres_consecutivos(eid, fecha_s, ini_m, fin_m):
                        return False, "max_cierres_consecutivos"
                    # Equilibrio operativo de franjas:
                    # evita concentrar toda la semana en solo manana o solo noche.
                    man_w, noc_w = _conteo_franja_semana(eid, y, w)
                    bucket_eval = _bucket_franja(ini_m)
                    if bucket_eval == "manana":
                        man_w += 1
                    else:
                        noc_w += 1
                    if abs(man_w - noc_w) > 2:
                        return False, "equilibrio_franja"
                    if not _intervalos_respetan_descanso(
                        intervalos_por_eid[eid],
                        ini_dt,
                        fin_dt,
                        float(descanso_entre_jornadas_h),
                        permitir_partido_mismo_dia=permitir_partido,
                        min_gap_partido_min=max(0, int(descanso_min_partido_min)),
                        bloquear_cierra_abre=bool(regla_cierra_no_abre and not relajar_cierra_abre),
                    ):
                        # Afinar motivo para poder explicarlo en avisos.
                        if regla_cierra_no_abre:
                            for e0, e1 in intervalos_por_eid[eid]:
                                if (
                                    ini_dt.date() == (e1.date() + timedelta(days=1))
                                    and (e1.hour * 60 + e1.minute) >= 21 * 60
                                    and (ini_dt.hour * 60 + ini_dt.minute) < 14 * 60
                                ):
                                    return False, "cierra_no_abre"
                        return False, "descanso"
                    tope_sem = float(horas_semana_por_empleado.get(eid, 40.0))
                    if diarios[(eid, fecha_s)] + dur_eval_h > _MAX_HORAS_DIA_LEGAL + 1e-9:
                        return False, "tope_dia"
                    # Limita días trabajados/semana para preservar libranzas.
                    turnos_dia_exist = sum(
                        1 for i0, _f0 in intervalos_por_eid[eid] if i0.date().isoformat() == fecha_s
                    )
                    if turnos_dia_exist == 0:
                        dias_sem = _dias_trabajados_semana(eid, y, w)
                        if dias_sem + 1 > _max_dias_trabajo_semana(eid):
                            return False, "max_dias_semana"
                    if not _cumple_tope_semanal_contrato(horas_sem_acum(eid, cur), dur_eval_h, tope_sem):
                        return False, "tope_semana"
                    return True, "ok"

                asignados: list[tuple[int, bool]] = []
                reasignados_total: set[int] = set()
                if diversificar_encargados:
                    candidatos = list(pool)
                    while len(asignados) < necesarios and candidatos:
                        mejor: int | None = None
                        mejor_k: tuple | None = None
                        for eid in candidatos:
                            ok, _mot = _puede_asignar(eid)
                            if not ok:
                                continue
                            ke = _key_equidad(eid)
                            if _es_perfil_encargado(empleados_meta.get(eid)):
                                k = (enc_turnos_dia[eid],) + ke
                            else:
                                k = (0,) + ke
                            if mejor is None or k < mejor_k:
                                mejor, mejor_k = eid, k
                        if mejor is None:
                            break
                        asignados.append((mejor, False))
                        candidatos.remove(mejor)
                        if _es_perfil_encargado(empleados_meta.get(mejor)):
                            enc_turnos_dia[mejor] += 1
                else:
                    pool.sort(key=_key_equidad)
                    for eid in pool:
                        if len(asignados) >= necesarios:
                            break
                        ok, _mot = _puede_asignar(eid)
                        if not ok:
                            continue
                        asignados.append((eid, False))

                brecha = necesarios - len(asignados)
                if brecha > 0 and permitir_partido_cobertura:
                    for eid in pool:
                        if len(asignados) >= necesarios:
                            break
                        if any(x[0] == eid for x in asignados):
                            continue
                        ok, _mot = _puede_asignar(eid, permitir_partido=True)
                        if not ok:
                            continue
                        asignados.append((eid, True))

                brecha = necesarios - len(asignados)
                if brecha > 0 and permitir_apoyo_sala_en_barra and sector in ("Barra", "Sala", "Cocina"):
                    pool_apoyo = [eid for eid in ids_ord if _empleado_apoyo_sector(empleados_meta[eid], sector)]
                    pool_apoyo.sort(key=_key_equidad)
                    for eid in pool_apoyo:
                        if len(asignados) >= necesarios:
                            break
                        if any(x[0] == eid for x in asignados):
                            continue
                        ok, _mot = _puede_asignar(eid, permitir_partido=False)
                        if not ok:
                            continue
                        asignados.append((eid, False))

                brecha = necesarios - len(asignados)
                if brecha > 0 and permitir_cobertura_total and not modo_servicio_minimo:
                    if sector == "Cocina":
                        pool_total = [eid for eid in ids_ord if _empleado_match_sector(empleados_meta[eid], sector)]
                    else:
                        # Cobertura total para Barra/Sala: excluye personal de cocina.
                        pool_total = [eid for eid in ids_ord if not _perfil_cocina(empleados_meta[eid])]
                    pool_total.sort(
                        key=lambda eid: (
                            horas_sem_acum(eid, cur)
                            / max(float(horas_semana_por_empleado.get(eid, 40.0)), 1.0),
                            eid,
                        )
                    )
                    for eid in pool_total:
                        if len(asignados) >= necesarios:
                            break
                        if any(x[0] == eid for x in asignados):
                            continue
                        ok, _mot = _puede_asignar(eid, permitir_partido=True, relajar_cierra_abre=True)
                        if not ok:
                            continue
                        asignados.append((eid, True))
                        reasignados_total.add(eid)

                brecha = necesarios - len(asignados)
                asignaciones_relevo: list[tuple[int, int, int, bool, bool]] = []
                if brecha > 0:
                    # Ultimo recurso antes de avisar faltantes:
                    # cubrir un hueco con 2 relevos dentro de la misma franja.
                    pool_relevo = []
                    for eid in ids_ord:
                        if _empleado_match_sector(empleados_meta[eid], sector):
                            pool_relevo.append(eid)
                            continue
                        if permitir_apoyo_sala_en_barra and _empleado_apoyo_sector(empleados_meta[eid], sector):
                            pool_relevo.append(eid)
                    faltan_tmp = brecha
                    while faltan_tmp > 0:
                        cubierto = False
                        for split in range(vini + 120, vfin - 119, 30):
                            e1 = None
                            e2 = None
                            for eid in pool_relevo:
                                ok, _m = _puede_asignar(
                                    eid,
                                    permitir_partido=True,
                                    ini_min_eval=vini,
                                    fin_min_eval=split,
                                    relajar_cierra_abre=True,
                                )
                                if ok:
                                    e1 = eid
                                    break
                            if e1 is None:
                                continue
                            for eid in pool_relevo:
                                if eid == e1:
                                    continue
                                ok, _m = _puede_asignar(
                                    eid,
                                    permitir_partido=True,
                                    ini_min_eval=split,
                                    fin_min_eval=vfin,
                                    relajar_cierra_abre=True,
                                )
                                if ok:
                                    e2 = eid
                                    break
                            if e2 is None:
                                continue
                            asignaciones_relevo.append((e1, vini, split, True, _empleado_apoyo_sector(empleados_meta.get(e1, {}), sector)))
                            asignaciones_relevo.append((e2, split, vfin, True, _empleado_apoyo_sector(empleados_meta.get(e2, {}), sector)))
                            dur1 = round((split - vini) / 60.0, 2)
                            dur2 = round((vfin - split) / 60.0, 2)
                            diarios[(e1, fecha_s)] += dur1
                            diarios[(e2, fecha_s)] += dur2
                            semanales[(e1, y, w)] += dur1
                            semanales[(e2, y, w)] += dur2
                            i10, f10 = _intervalo_datetime_turno(fecha_s, vini, split)
                            i20, f20 = _intervalo_datetime_turno(fecha_s, split, vfin)
                            intervalos_por_eid[e1].append((i10, f10))
                            intervalos_por_eid[e2].append((i20, f20))
                            cubierto = True
                            break
                        if not cubierto:
                            break
                        faltan_tmp -= 1
                    brecha = faltan_tmp

                if brecha > 0:
                    # Diagnóstico de por qué no se pudo completar el hueco.
                    motivos = defaultdict(int)
                    candidatos_diag = set(pool)
                    if permitir_apoyo_sala_en_barra and sector in ("Barra", "Sala", "Cocina"):
                        for eid in ids_ord:
                            if _empleado_apoyo_sector(empleados_meta[eid], sector):
                                candidatos_diag.add(eid)
                    ya_asig = {x[0] for x in asignados}
                    for eid in sorted(candidatos_diag):
                        if eid in ya_asig:
                            continue
                        ok_n, mot_n = _puede_asignar(eid, permitir_partido=False)
                        if ok_n:
                            continue
                        motivos[mot_n] += 1
                    detalle = ""
                    if motivos:
                        orden = (
                            "dia_libre_cliente",
                            "descanso",
                            "cierra_no_abre",
                            "tope_dia",
                            "tope_semana",
                            "max_turnos_dia",
                            "max_dias_semana",
                            "max_partidos_semana",
                            "max_cierres_consecutivos",
                        )
                        partes = []
                        for k in orden:
                            if motivos.get(k):
                                partes.append(f"{k}:{motivos[k]}")
                        if partes:
                            detalle = " | bloqueos " + ", ".join(partes)
                    if modo_servicio_minimo:
                        advertencias.append(
                            f"[SERV_MIN] {fecha_s} {sector} ({_min_a_hora_reloj(vini)}–{_min_a_hora_reloj(vfin)}): "
                            f"cobertura parcial, faltan {brecha}.{detalle}"
                        )
                    else:
                        advertencias.append(
                            f"{fecha_s} {sector} ({_min_a_hora_reloj(vini)}–{_min_a_hora_reloj(vfin)}): "
                            f"faltan {brecha} perfil(es) compatible(s).{detalle}"
                        )
                bloque = _etiqueta_bloque_desde_hora(vini)
                turno_txt = f"{bloque} {sector}"
                hi = _min_a_hora_reloj(vini)
                hf = _min_a_hora_reloj(vfin)
                for eid, es_partido in asignados:
                    turno_guardar = f"{turno_txt} Partido" if es_partido else turno_txt
                    if sector in ("Barra", "Sala", "Cocina") and permitir_apoyo_sala_en_barra and _empleado_apoyo_sector(
                        empleados_meta.get(eid, {}), sector
                    ):
                        turno_guardar = f"{turno_guardar} (Apoyo {sector.lower()})"
                    elif eid in reasignados_total:
                        turno_guardar = f"{turno_guardar} (Reasignado)"
                    pendientes.append((eid, fecha_s, hi, hf, turno_guardar, dur_h))
                    diarios[(eid, fecha_s)] += dur_h
                    semanales[(eid, y, w)] += dur_h
                    i0, f0 = _intervalo_datetime_turno(fecha_s, vini, vfin)
                    intervalos_por_eid[eid].append((i0, f0))
                    if _es_turno_cierre(vini, vfin):
                        cierres_semanales[(eid, y, w)] += 1
                        cierres_por_fecha.add((eid, fecha_s))
                    if es_partido:
                        partidos_semanales[(eid, y, w)] += 1
                    asignaciones_sector.append((fecha_s, sector, vini, vfin))
                for eid, ini_seg, fin_seg, es_partido, es_apoyo in asignaciones_relevo:
                    hsi = _min_a_hora_reloj(ini_seg)
                    hsf = _min_a_hora_reloj(fin_seg)
                    dur_seg = round((fin_seg - ini_seg) / 60.0, 2)
                    tag = f"{turno_txt} Relevo"
                    if es_partido:
                        tag += " Partido"
                    if es_apoyo:
                        tag += f" (Apoyo {sector.lower()})"
                    pendientes.append((eid, fecha_s, hsi, hsf, tag, dur_seg))
                    if _es_turno_cierre(ini_seg, fin_seg):
                        cierres_semanales[(eid, y, w)] += 1
                        cierres_por_fecha.add((eid, fecha_s))
                    if es_partido:
                        partidos_semanales[(eid, y, w)] += 1
                    asignaciones_sector.append((fecha_s, sector, ini_seg, fin_seg))
                if not rellenar_hasta_contrato:
                    continue
                # Evita que los refuerzos tempranos "coman" el tope diario y bloqueen
                # las siguientes ventanas del mismo día (p.ej. quedarse solo en 09:00-17:00).
                if v_idx < len(ventanas) - 1:
                    continue
                # Evita consumir cupo semanal al inicio de la semana: el relleno se aplica
                # solo en fin de semana para no dejar sin horas viernes/sábado.
                if cur.weekday() not in (4, 5, 6):
                    continue
                extras: list[int] = []
                candidatos_extra = [eid for eid in pool if eid not in asignados]
                candidatos_extra.sort(
                    key=lambda eid: (
                        horas_sem_acum(eid, cur)
                        / max(float(horas_semana_por_empleado.get(eid, 40.0)), 1.0),
                        -max(0.0, float(horas_semana_por_empleado.get(eid, 40.0)) - horas_sem_acum(eid, cur)),
                        eid,
                    )
                )
                for eid in candidatos_extra:
                    ok, _mot = _puede_asignar(eid)
                    if not ok:
                        continue
                    tope_sem = float(horas_semana_por_empleado.get(eid, 40.0))
                    if tope_sem - horas_sem_acum(eid, cur) < 0.5:
                        continue
                    extras.append(eid)
                for eid in extras:
                    pendientes.append((eid, fecha_s, hi, hf, f"{turno_txt} Refuerzo", dur_h))
                    diarios[(eid, fecha_s)] += dur_h
                    semanales[(eid, y, w)] += dur_h
                    i0, f0 = _intervalo_datetime_turno(fecha_s, vini, vfin)
                    intervalos_por_eid[eid].append((i0, f0))

    if forzar_horas_contrato:
        semanas_en_rango: dict[tuple[int, int], list[date]] = defaultdict(list)
        cur = fi
        while cur <= ff:
            yk, wk, _ = cur.isocalendar()
            semanas_en_rango[(yk, wk)].append(cur)
            cur += timedelta(days=1)

        def _bucket_franja_ini(ini_min: int) -> str:
            return "manana" if int(ini_min) < 17 * 60 else "noche"

        def _conteo_emp_mn_semana(eid: int, yk: int, wk: int) -> tuple[int, int]:
            man = 0
            noc = 0
            for i0, _f0 in intervalos_por_eid[eid]:
                yi, wi, _ = i0.date().isocalendar()
                if yi != yk or wi != wk:
                    continue
                if (i0.hour * 60 + i0.minute) < 17 * 60:
                    man += 1
                else:
                    noc += 1
            return man, noc

        def _conteo_global_franja_dia(fecha_s: str) -> tuple[int, int]:
            man = 0
            noc = 0
            for _eid, f, hi, _hf, _turno, _horas in pendientes:
                if f != fecha_s:
                    continue
                try:
                    ini_m = _hora_a_min(str(hi))
                except Exception:
                    continue
                if ini_m < 17 * 60:
                    man += 1
                else:
                    noc += 1
            return man, noc

        # Candidatos de turnos extra por semana, priorizando días con más % de necesidad.
        for (ywk, wwk), dias_sem in sorted(semanas_en_rango.items()):
            candidatos_semana: list[tuple[float, str, str, int, int, float, int]] = []
            candidatos_baja_carga: list[tuple[float, str, str, int, int, float, int]] = []
            for dcur in sorted(
                dias_sem,
                key=lambda d: (
                    -float(niveles_eff.get(d.weekday(), 1.0)),
                    d.weekday(),
                    str(d),
                ),
            ):
                fecha_s = str(dcur)
                for regla in reglas_o:
                    sector = (regla.get("sector") or "").strip()
                    try:
                        ini = int(regla["inicio_min"])
                        fin = int(regla["fin_min"])
                    except (TypeError, ValueError, KeyError):
                        continue
                    if fin <= ini:
                        continue
                    for vini, vfin in _ventanas_turno_legal(ini, fin):
                        dur_h = round((vfin - vini) / 60.0, 2)
                        if dur_h <= 0:
                            continue
                        peso = float(niveles_eff.get(dcur.weekday(), 1.0))
                        necesarios_slot = _dotacion_nivelada_por_dia(
                            int(regla.get("min_personal") or 0), dcur.weekday(), niveles_eff
                        )
                        max_cov = _max_cobertura_permitida(necesarios_slot, peso)
                        item = (peso, fecha_s, sector, vini, vfin, dur_h, max_cov)
                        if peso >= 1.0:
                            candidatos_semana.append(item)
                        else:
                            candidatos_baja_carga.append(item)

            if not candidatos_semana and not candidatos_baja_carga:
                continue

            guard = 0
            bloqueados_semana: set[int] = set()
            while guard < 5000:
                guard += 1
                # Empleado más lejos de su objetivo semanal de contrato.
                eid_obj: int | None = None
                deficit_obj = 0.0
                for eid in ids_ord:
                    if eid in bloqueados_semana:
                        continue
                    tope_sem = float(horas_semana_por_empleado.get(eid, 40.0))
                    asignado_sem = float(semanales.get((eid, ywk, wwk), 0.0))
                    deficit = round(tope_sem - asignado_sem, 2)
                    if deficit > deficit_obj + 1e-9:
                        eid_obj = eid
                        deficit_obj = deficit
                if eid_obj is None or deficit_obj < 0.25:
                    break

                def _buscar_en(lista_candidatos):
                    for _peso, fecha_s, sector, vini, vfin, dur_h, max_cov in lista_candidatos:
                        if fecha_s in libres_map.get(int(eid_obj), set()):
                            continue
                        dur_obj = dur_h
                        # Permite encajar el último tramo para completar contrato semanal
                        # en perfiles no 40h (ej. deficit 4h y ventana 8h).
                        if dur_obj > deficit_obj + 1e-9:
                            dur_obj = round(deficit_obj, 2)
                            # Evita microturnos: mínimo operativo 2h.
                            if dur_obj < 2.0:
                                continue
                        fin_obj = vini + int(round(dur_obj * 60))
                        if fin_obj > vfin:
                            continue
                        if not _empleado_match_sector(empleados_meta[eid_obj], sector):
                            continue
                        turnos_mismo_dia = sum(
                            1 for i0, _f0 in intervalos_por_eid[eid_obj] if i0.date().isoformat() == fecha_s
                        )
                        # En forzado de contrato priorizamos NO partido.
                        # Solo se permite partido si está habilitado en cobertura.
                        if turnos_mismo_dia >= 2:
                            continue
                        if turnos_mismo_dia >= 1 and not permitir_partido_cobertura:
                            continue
                        # Limita partidos semanales en fase de contrato para evitar
                        # cuadrantes "rotos" por exceso de dobles jornadas.
                        if partidos_semanales[(eid_obj, ywk, wwk)] >= 1 and turnos_mismo_dia >= 1:
                            continue
                        ini_eval = vini
                        fin_eval = fin_obj
                        if turnos_mismo_dia >= 1:
                            enc = _encajar_tramo_en_hora_punta(
                                vini,
                                vfin,
                                int(round(dur_obj * 60)),
                                ventanas_punta=ventanas_hora_punta,
                            )
                            if not enc:
                                continue
                            ini_eval, fin_eval = enc
                            dur_obj = round((fin_eval - ini_eval) / 60.0, 2)
                        ini_dt, fin_dt = _intervalo_datetime_turno(fecha_s, vini, fin_obj)
                        if (ini_eval, fin_eval) != (vini, fin_obj):
                            ini_dt, fin_dt = _intervalo_datetime_turno(fecha_s, ini_eval, fin_eval)
                        if _cobertura_sector(fecha_s, sector, ini_eval, fin_eval) >= max_cov:
                            continue
                        if _rompe_max_cierres_consecutivos(eid_obj, fecha_s, ini_eval, fin_eval):
                            continue
                        if not _intervalos_respetan_descanso(
                            intervalos_por_eid[eid_obj],
                            ini_dt,
                            fin_dt,
                            float(descanso_entre_jornadas_h),
                            permitir_partido_mismo_dia=True,
                            min_gap_partido_min=max(0, int(descanso_min_partido_min)),
                            bloquear_cierra_abre=bool(regla_cierra_no_abre),
                        ):
                            continue
                        if diarios[(eid_obj, fecha_s)] + dur_obj > _MAX_HORAS_DIA_LEGAL + 1e-9:
                            continue
                        # Si es un día nuevo en la semana, respeta máximo de días trabajados.
                        turnos_dia_exist = sum(
                            1 for i0, _f0 in intervalos_por_eid[eid_obj] if i0.date().isoformat() == fecha_s
                        )
                        if turnos_dia_exist == 0:
                            dias_sem = _dias_trabajados_semana(eid_obj, ywk, wwk)
                            if dias_sem + 1 > _max_dias_trabajo_semana(eid_obj):
                                continue
                        tope_sem = float(horas_semana_por_empleado.get(eid_obj, 40.0))
                        if not _cumple_tope_semanal_contrato(
                            semanales[(eid_obj, ywk, wwk)], dur_obj, tope_sem
                        ):
                            continue
                        return (fecha_s, sector, ini_eval, fin_eval, dur_obj)
                    return None

                # 1) Primero intenta en dias con necesidad >=100%.
                elegido = _buscar_en(candidatos_semana)
                # 2) Si no encuentra hueco, permite completar en dias de baja carga.
                if not elegido:
                    elegido = _buscar_en(candidatos_baja_carga)

                if not elegido:
                    # No hay hueco viable para este empleado; probamos con el siguiente deficit.
                    bloqueados_semana.add(int(eid_obj))
                    continue

                fecha_s, sector, vini, vfin, dur_h = elegido
                hi = _min_a_hora_reloj(vini)
                hf = _min_a_hora_reloj(vfin)
                bloque = _etiqueta_bloque_desde_hora(vini)
                turnos_mismo_dia = sum(
                    1 for i0, _f0 in intervalos_por_eid[eid_obj] if i0.date().isoformat() == fecha_s
                )
                turno_txt = f"{bloque} {sector} Refuerzo contrato"
                if turnos_mismo_dia >= 1:
                    turno_txt += " Partido"
                pendientes.append((eid_obj, fecha_s, hi, hf, turno_txt, dur_h))
                diarios[(eid_obj, fecha_s)] += dur_h
                semanales[(eid_obj, ywk, wwk)] += dur_h
                i0, f0 = _intervalo_datetime_turno(fecha_s, vini, vfin)
                intervalos_por_eid[eid_obj].append((i0, f0))
                if _es_turno_cierre(vini, vfin):
                    cierres_semanales[(eid_obj, ywk, wwk)] += 1
                    cierres_por_fecha.add((eid_obj, fecha_s))
                if "Partido" in turno_txt:
                    partidos_semanales[(eid_obj, ywk, wwk)] += 1
                asignaciones_sector.append((fecha_s, sector, vini, vfin))

        # Fase final "sí o sí contrato": crea refuerzos en horas punta.
        # Nota: esta fase es transversal (no amarrada a un sector concreto) para
        # cerrar déficits residuales de contrato respetando legalidad.
        ventanas_force = list(ventanas_hora_punta or _ventanas_hora_punta_default())
        # Prioriza primero tarde/noche para no vaciar cierres por llenar mananas.
        ventanas_force.sort(key=lambda x: x[0], reverse=True)
        for (ywk, wwk), dias_sem in sorted(semanas_en_rango.items()):
            dias_ord = sorted(
                dias_sem,
                key=lambda d: (
                    -float(niveles_eff.get(d.weekday(), 1.0)),
                    d.weekday(),
                    str(d),
                ),
            )
            for eid in ids_ord:
                objetivo = float(horas_semana_por_empleado.get(eid, 40.0))
                actual = float(semanales.get((eid, ywk, wwk), 0.0))
                deficit = round(objetivo - actual, 2)
                if deficit < 0.5:
                    continue
                guard2 = 0
                while deficit >= 0.5 and guard2 < 80:
                    guard2 += 1
                    asignado = False
                    # 1) primero intenta en días sin turno (evita partido)
                    # 2) luego permite un único partido semanal si no alcanza contrato
                    dias_pref = sorted(
                        dias_ord,
                        key=lambda d: (
                            sum(1 for i0, _f0 in intervalos_por_eid[eid] if i0.date() == d),
                            d,
                        ),
                    )
                    for dcur in dias_pref:
                        fecha_s = str(dcur)
                        if fecha_s in libres_map.get(int(eid), set()):
                            continue
                        turnos_dia = sum(
                            1 for i0, _f0 in intervalos_por_eid[eid] if i0.date().isoformat() == fecha_s
                        )
                        if turnos_dia >= 2:
                            continue
                        if turnos_dia >= 1 and not permitir_partido_cobertura:
                            continue
                        if turnos_dia >= 1 and partidos_semanales[(eid, ywk, wwk)] >= 1:
                            continue
                        # Ventanas candidatas: 1) horas punta configuradas, 2) ventanas
                        # reales de reglas por frente (fallback duro para cerrar contrato).
                        ventanas_candidatas: list[tuple[int, int]] = []
                        vistos: set[tuple[int, int]] = set()
                        for pi, pf in ventanas_force:
                            ini = int(pi)
                            fin = int(pf)
                            if fin <= ini:
                                fin += 24 * 60
                            if fin > ini and (ini, fin) not in vistos:
                                vistos.add((ini, fin))
                                ventanas_candidatas.append((ini, fin))
                        for rg in reglas_o:
                            try:
                                ini = int(rg.get("inicio_min"))
                                fin = int(rg.get("fin_min"))
                            except (TypeError, ValueError):
                                continue
                            if fin <= ini:
                                continue
                            if (ini, fin) not in vistos:
                                vistos.add((ini, fin))
                                ventanas_candidatas.append((ini, fin))

                        man_e, noc_e = _conteo_emp_mn_semana(eid, ywk, wwk)
                        preferir_manana = noc_e > man_e
                        ventanas_candidatas.sort(
                            key=lambda iv: (
                                0 if (_bucket_franja_ini(iv[0]) == ("manana" if preferir_manana else "noche")) else 1,
                                iv[0],
                            )
                        )

                        for ini, fin in ventanas_candidatas:
                            # Intenta cerrar contrato en bloques operativos:
                            # si cabe, usa bloque largo (hasta 8h) y si no, baja a 4h.
                            max_dia = max(0.0, _MAX_HORAS_DIA_LEGAL - diarios[(eid, fecha_s)])
                            if max_dia < 1.99:
                                continue
                            dur_h = min(float(deficit), max_dia, round((fin - ini) / 60.0, 2), 8.0)
                            # Para contratos de 40h, prioriza bloques completos de 8h
                            # cuando el déficit semanal aún es alto.
                            objetivo_emp = float(horas_semana_por_empleado.get(eid, 40.0))
                            if objetivo_emp >= 39.0 and float(deficit) >= 7.5 and max_dia >= 7.5:
                                if (fin - ini) >= int(round(8.0 * 60)):
                                    dur_h = 8.0
                            if dur_h < 2.0:
                                continue
                            if dur_h > 4.0 and (fin - ini) < int(round(dur_h * 60)):
                                dur_h = min(4.0, dur_h)
                            dur_m = int(round(dur_h * 60))
                            if fin - ini < dur_m:
                                continue
                            ini_dt, fin_dt = _intervalo_datetime_turno(fecha_s, ini, ini + dur_m)
                            if _rompe_max_cierres_consecutivos(eid, fecha_s, ini, ini + dur_m):
                                continue
                            if not _intervalos_respetan_descanso(
                                intervalos_por_eid[eid],
                                ini_dt,
                                fin_dt,
                                float(descanso_entre_jornadas_h),
                                permitir_partido_mismo_dia=True,
                                min_gap_partido_min=max(0, int(descanso_min_partido_min)),
                                bloquear_cierra_abre=bool(regla_cierra_no_abre),
                            ):
                                continue
                            if diarios[(eid, fecha_s)] + dur_h > _MAX_HORAS_DIA_LEGAL + 1e-9:
                                continue
                            turnos_dia_exist = sum(
                                1 for i0, _f0 in intervalos_por_eid[eid] if i0.date().isoformat() == fecha_s
                            )
                            if turnos_dia_exist == 0:
                                dias_sem = _dias_trabajados_semana(eid, ywk, wwk)
                                if dias_sem + 1 > _max_dias_trabajo_semana(eid):
                                    continue
                            if not _cumple_tope_semanal_contrato(semanales[(eid, ywk, wwk)], dur_h, objetivo):
                                continue
                            # Evita seguir cargando una franja ya claramente sobre-asignada.
                            man_d, noc_d = _conteo_global_franja_dia(fecha_s)
                            bkt = _bucket_franja_ini(ini)
                            if bkt == "noche" and noc_d >= man_d + 2:
                                continue
                            if bkt == "manana" and man_d >= noc_d + 2:
                                continue
                            hi = _min_a_hora_reloj(ini)
                            hf = _min_a_hora_reloj(ini + dur_m)
                            tag = "Refuerzo contrato"
                            if turnos_dia >= 1:
                                tag += " Partido"
                            pendientes.append((eid, fecha_s, hi, hf, tag, round(dur_h, 2)))
                            diarios[(eid, fecha_s)] += dur_h
                            semanales[(eid, ywk, wwk)] += dur_h
                            intervalos_por_eid[eid].append((ini_dt, fin_dt))
                            if _es_turno_cierre(ini, ini + dur_m):
                                cierres_semanales[(eid, ywk, wwk)] += 1
                                cierres_por_fecha.add((eid, fecha_s))
                            if "Partido" in tag:
                                partidos_semanales[(eid, ywk, wwk)] += 1
                            asignaciones_sector.append((fecha_s, "Refuerzo", ini, ini + dur_m))
                            deficit = round(objetivo - float(semanales.get((eid, ywk, wwk), 0.0)), 2)
                            asignado = True
                            break
                        if asignado:
                            break
                    if not asignado:
                        break

        # Si tras todas las fases aún queda déficit, se reporta explícitamente.
        for (ywk, wwk), _dias_sem in sorted(semanas_en_rango.items()):
            for eid in ids_ord:
                objetivo = float(horas_semana_por_empleado.get(eid, 40.0))
                actual = float(semanales.get((eid, ywk, wwk), 0.0))
                deficit = round(objetivo - actual, 2)
                if deficit > 0.5:
                    nom = _nombre_display_empleado(empleados_meta.get(eid, {})) or f"ID {eid}"
                    advertencias.append(
                        f"[DEFICIT_CONTRATO] {nom} semana {ywk}-W{wwk}: faltan {deficit:g}h (asignadas {actual:g}/{objetivo:g})."
                    )

    # Garantiza al menos un encargado por franja (manana / noche) en cada dia.
    # Se aplica al final para corregir cuadrantes de servicio minimo.
    dias_rango: list[date] = []
    cur_d = fi
    while cur_d <= ff:
        dias_rango.append(cur_d)
        cur_d += timedelta(days=1)

    def _hay_encargado_en_franja(fecha_s: str, es_manana: bool) -> bool:
        for eid, f, hi, _hf, _turno, _horas in pendientes:
            if f != fecha_s:
                continue
            try:
                ini_m = _hora_a_min(str(hi))
            except Exception:
                continue
            if (ini_m < 17 * 60) != es_manana:
                continue
            if _es_perfil_encargado(empleados_meta.get(int(eid), {})):
                return True
        return False

    for d in dias_rango:
        fecha_s = str(d)
        y, w, _ = d.isocalendar()
        for es_manana, ini_b, fin_b, label in (
            (True, 13 * 60, 15 * 60, "Mañana Encargado"),
            (False, 20 * 60, 22 * 60, "Noche Encargado"),
        ):
            if _hay_encargado_en_franja(fecha_s, es_manana):
                continue
            candidatos = [eid for eid in ids_ord if _es_perfil_encargado(empleados_meta.get(eid, {}))]
            candidatos.sort(
                key=lambda eid: (
                    horas_sem_acum(eid, d) / max(float(horas_semana_por_empleado.get(eid, 40.0)), 1.0),
                    eid,
                )
            )
            for eid in candidatos:
                if fecha_s in libres_map.get(int(eid), set()):
                    continue
                turnos_dia_exist = sum(
                    1 for i0, _f0 in intervalos_por_eid[eid] if i0.date().isoformat() == fecha_s
                )
                if turnos_dia_exist == 0:
                    dias_sem = _dias_trabajados_semana(eid, y, w)
                    if dias_sem + 1 > _max_dias_trabajo_semana(eid):
                        continue
                ini_dt, fin_dt = _intervalo_datetime_turno(fecha_s, ini_b, fin_b)
                if not _intervalos_respetan_descanso(
                    intervalos_por_eid[eid],
                    ini_dt,
                    fin_dt,
                    float(descanso_entre_jornadas_h),
                    permitir_partido_mismo_dia=True,
                    min_gap_partido_min=max(0, int(descanso_min_partido_min)),
                    bloquear_cierra_abre=bool(regla_cierra_no_abre),
                ):
                    continue
                dur_h = round((fin_b - ini_b) / 60.0, 2)
                if diarios[(eid, fecha_s)] + dur_h > _MAX_HORAS_DIA_LEGAL + 1e-9:
                    continue
                tope_sem = float(horas_semana_por_empleado.get(eid, 40.0))
                if not _cumple_tope_semanal_contrato(semanales[(eid, y, w)], dur_h, tope_sem):
                    continue
                hi = _min_a_hora_reloj(ini_b)
                hf = _min_a_hora_reloj(fin_b)
                pendientes.append((eid, fecha_s, hi, hf, label, dur_h))
                diarios[(eid, fecha_s)] += dur_h
                semanales[(eid, y, w)] += dur_h
                intervalos_por_eid[eid].append((ini_dt, fin_dt))
                break
    return pendientes, advertencias


def _autocompletar_cobertura(
    pendientes,
    empleados_rows,
    horas_semana_por_empleado,
    fecha_inicio: str,
    fecha_fin: str,
    cobertura_cfg: dict | None,
    niveles_por_weekday: dict[int, float] | None = None,
):
    """
    Rellena huecos de cobertura por bloques de 30 min usando personal con menos carga.
    Respeta tope diario legal y horas semanales de contrato.
    """
    if not cobertura_cfg:
        return pendientes, 0

    ini = int(cobertura_cfg["inicio_min"])
    fin = int(cobertura_cfg["fin_min"])
    min_personal = int(cobertura_cfg["min_personal"])
    if fin <= ini or min_personal <= 0:
        return pendientes, 0

    empleados_ids = []
    for e in empleados_rows:
        try:
            empleados_ids.append(int(dict(e).get("id")))
        except (TypeError, ValueError):
            continue
    if not empleados_ids:
        return pendientes, 0

    turnos = []
    diarios = defaultdict(float)  # (eid, fecha) -> horas
    semanales = defaultdict(float)  # (eid, iso_year, iso_week) -> horas
    for eid, fecha_s, hi, hf, turno, horas in pendientes:
        try:
            s = _hora_a_min(hi)
            e = _hora_a_min(hf)
            hrs = float(horas or 0.0)
            fd = date.fromisoformat(fecha_s)
            y, w, _ = fd.isocalendar()
        except (ValueError, TypeError):
            continue
        if e <= s:
            continue
        turnos.append(
            {
                "eid": int(eid),
                "fecha": fecha_s,
                "ini": s,
                "fin": e,
                "turno": turno,
                "horas": hrs,
            }
        )
        diarios[(int(eid), fecha_s)] += hrs
        semanales[(int(eid), y, w)] += hrs

    def _cobertura_en_slot(fecha_s: str, slot_ini: int, slot_fin: int) -> int:
        c_ids = set()
        for t in turnos:
            if t["fecha"] != fecha_s:
                continue
            if t["ini"] <= slot_ini and t["fin"] >= slot_fin:
                c_ids.add(int(t["eid"]))
        return len(c_ids)

    def _empleado_disponible(eid: int, fecha_s: str, y: int, w: int, dur_h: float) -> bool:
        if diarios[(eid, fecha_s)] + dur_h > _MAX_HORAS_DIA_LEGAL + 1e-9:
            return False
        tope_sem = float(horas_semana_por_empleado.get(eid, 40.0))
        return _cumple_tope_semanal_contrato(semanales[(eid, y, w)], dur_h, tope_sem)

    creados = 0
    niveles_eff = niveles_por_weekday if niveles_por_weekday is not None else _niveles_carga_semana_default()
    f0 = date.fromisoformat(fecha_inicio)
    f1 = date.fromisoformat(fecha_fin)
    cur = f0
    while cur <= f1:
        fecha_s = str(cur)
        y, w, _ = cur.isocalendar()
        min_dia = max(
            1,
            int(round(min_personal * float(niveles_eff.get(cur.weekday(), 1.0)))),
        )
        slot = ini
        while slot < fin:
            slot_fin = min(slot + 30, fin)
            deficit = min_dia - _cobertura_en_slot(fecha_s, slot, slot_fin)
            while deficit > 0:
                candidatos = []
                for eid in empleados_ids:
                    if _empleado_esta_ocupado(turnos, eid, fecha_s, slot, slot_fin):
                        continue
                    if _empleado_disponible(eid, fecha_s, y, w, 0.5):
                        candidatos.append(
                            (
                                diarios[(eid, fecha_s)],
                                semanales[(eid, y, w)],
                                eid,
                            )
                        )
                if not candidatos:
                    break
                candidatos.sort()
                elegido = candidatos[0][2]

                # Bloque de refuerzo corto para evitar horarios artificiales largos.
                left_day_h = _MAX_HORAS_DIA_LEGAL - diarios[(elegido, fecha_s)]
                tope_sem_e = float(horas_semana_por_empleado.get(elegido, 40.0))
                left_week_h = max(0.0, tope_sem_e - semanales[(elegido, y, w)])
                max_h = min(left_day_h, left_week_h, 2.0)
                if max_h < 0.5:
                    break
                dur_slots = max(1, int(max_h * 2))
                nuevo_fin = min(fin, slot + dur_slots * 30)
                if nuevo_fin <= slot:
                    break

                horas_nuevo = round((nuevo_fin - slot) / 60.0, 2)
                horas_nuevo = min(horas_nuevo, round(left_week_h, 2), round(left_day_h, 2))
                if horas_nuevo < 0.25 or not _cumple_tope_semanal_contrato(
                    semanales[(elegido, y, w)], horas_nuevo, tope_sem_e
                ):
                    break
                turnos.append(
                    {
                        "eid": elegido,
                        "fecha": fecha_s,
                        "ini": slot,
                        "fin": nuevo_fin,
                        "turno": "Cobertura",
                        "horas": horas_nuevo,
                    }
                )
                diarios[(elegido, fecha_s)] += horas_nuevo
                semanales[(elegido, y, w)] += horas_nuevo
                creados += 1
                deficit = min_dia - _cobertura_en_slot(fecha_s, slot, slot_fin)
            slot += 30
        cur += timedelta(days=1)

    res = []
    for t in turnos:
        res.append(
            (
                t["eid"],
                t["fecha"],
                _min_a_hora(t["ini"]),
                _min_a_hora(t["fin"]),
                t["turno"],
                t["horas"],
            )
        )
    return res, creados


def _autocompletar_cobertura_por_sector(
    pendientes,
    empleados_rows,
    horas_semana_por_empleado,
    fecha_inicio: str,
    fecha_fin: str,
    reglas_sector: list[dict] | None,
    niveles_por_weekday: dict[int, float] | None = None,
):
    """Cobertura por sector con franja y dotación independientes."""
    if not reglas_sector:
        return pendientes, 0, []

    empleados_meta = {}
    for e in empleados_rows:
        ed = dict(e)
        try:
            eid = int(ed.get("id"))
        except (TypeError, ValueError):
            continue
        empleados_meta[eid] = {
            "puesto": (ed.get("puesto") or ""),
            "departamento": (ed.get("departamento") or ""),
            "observaciones": (ed.get("observaciones") or ""),
        }
    if not empleados_meta:
        return pendientes, 0, []

    turnos = []
    diarios = defaultdict(float)
    semanales = defaultdict(float)
    for eid, fecha_s, hi, hf, turno, horas in pendientes:
        try:
            s = _hora_a_min(hi)
            e = _hora_a_min(hf)
            hrs = float(horas or 0.0)
            fd = date.fromisoformat(fecha_s)
            y, w, _ = fd.isocalendar()
        except (ValueError, TypeError):
            continue
        if e <= s:
            continue
        turnos.append({"eid": int(eid), "fecha": fecha_s, "ini": s, "fin": e, "turno": turno, "horas": hrs})
        diarios[(int(eid), fecha_s)] += hrs
        semanales[(int(eid), y, w)] += hrs

    def _cobertura_sector(fecha_s: str, slot_ini: int, slot_fin: int, sector: str) -> int:
        c_ids = set()
        for t in turnos:
            if t["fecha"] != fecha_s:
                continue
            if t["ini"] <= slot_ini and t["fin"] >= slot_fin and _empleado_match_sector(empleados_meta.get(t["eid"], {}), sector):
                c_ids.add(int(t["eid"]))
        return len(c_ids)

    creados = 0
    huecos_sin_perfil: dict[str, int] = defaultdict(int)
    reglas_ordenadas = _orden_reglas_sector_sala_primero(list(reglas_sector))
    niveles_eff = niveles_por_weekday if niveles_por_weekday is not None else _niveles_carga_semana_default()
    cur = date.fromisoformat(fecha_inicio)
    fin_rango = date.fromisoformat(fecha_fin)
    while cur <= fin_rango:
        fecha_s = str(cur)
        y, w, _ = cur.isocalendar()
        for regla in reglas_ordenadas:
            sector = regla["sector"]
            ini = int(regla["inicio_min"])
            fin = int(regla["fin_min"])
            min_personal = _dotacion_nivelada_por_dia(
                int(regla["min_personal"]),
                cur.weekday(),
                niveles_eff,
            )
            slot = ini
            while slot < fin:
                slot_fin = min(slot + 30, fin)
                deficit = min_personal - _cobertura_sector(fecha_s, slot, slot_fin, sector)
                while deficit > 0:
                    candidatos = []
                    for eid, meta in empleados_meta.items():
                        if not _empleado_match_sector(meta, sector):
                            continue
                        if _empleado_esta_ocupado(turnos, eid, fecha_s, slot, slot_fin):
                            continue
                        left_day_h = _MAX_HORAS_DIA_LEGAL - diarios[(eid, fecha_s)]
                        left_week_h = horas_semana_por_empleado.get(eid, 40.0) - semanales[(eid, y, w)]
                        if min(left_day_h, left_week_h) < 0.5:
                            continue
                        candidatos.append(
                            (
                                -_score_afinidad_sector(meta, sector),
                                diarios[(eid, fecha_s)],
                                semanales[(eid, y, w)],
                                eid,
                            )
                        )
                    if not candidatos:
                        huecos_sin_perfil[sector] += 1
                        break
                    candidatos.sort()
                    elegido = candidatos[0][3]
                    left_day_h = _MAX_HORAS_DIA_LEGAL - diarios[(elegido, fecha_s)]
                    tope_sem_e = float(horas_semana_por_empleado.get(elegido, 40.0))
                    left_week_h = max(0.0, tope_sem_e - semanales[(elegido, y, w)])
                    max_h = min(left_day_h, left_week_h, 2.0)
                    if max_h < 0.5:
                        break
                    dur_slots = max(1, int(max_h * 2))
                    nuevo_fin = min(fin, slot + dur_slots * 30)
                    if nuevo_fin <= slot:
                        break
                    horas_nuevo = round((nuevo_fin - slot) / 60.0, 2)
                    horas_nuevo = min(horas_nuevo, round(left_week_h, 2), round(left_day_h, 2))
                    if horas_nuevo < 0.25 or not _cumple_tope_semanal_contrato(
                        semanales[(elegido, y, w)], horas_nuevo, tope_sem_e
                    ):
                        break
                    turnos.append(
                        {
                            "eid": elegido,
                            "fecha": fecha_s,
                            "ini": slot,
                            "fin": nuevo_fin,
                            "turno": f"Cobertura {sector}",
                            "horas": horas_nuevo,
                        }
                    )
                    diarios[(elegido, fecha_s)] += horas_nuevo
                    semanales[(elegido, y, w)] += horas_nuevo
                    creados += 1
                    deficit = min_personal - _cobertura_sector(fecha_s, slot, slot_fin, sector)
                slot += 30
        cur += timedelta(days=1)

    res = []
    for t in turnos:
        res.append((t["eid"], t["fecha"], _min_a_hora(t["ini"]), _min_a_hora(t["fin"]), t["turno"], t["horas"]))
    faltantes = [f"{sec}: {n} bloque(s) sin perfil compatible" for sec, n in huecos_sin_perfil.items() if n > 0]
    return res, creados, faltantes


def _agrupar_horarios_por_sector(rows):
    sectores = defaultdict(list)
    for h in rows or []:
        hd = dict(h)
        puesto = (hd.get("puesto") or "").strip()
        depto = (hd.get("departamento") or "").strip()
        turno = (hd.get("turno") or "").strip()
        if puesto and depto:
            base = f"{puesto} ({depto})"
        else:
            base = puesto or depto or "Sin sector"
        sector = base
        t_low = turno.lower()
        if "cobertura " in t_low:
            sector = turno.split(" ", 1)[1].strip() if " " in turno else turno
        sectores[sector].append(hd)
    # Orden amigable: sectores conocidos primero.
    orden = {"Barra": 0, "Sala": 1, "Cocina": 2}
    return sorted(sectores.items(), key=lambda it: (orden.get(it[0], 99), it[0].lower()))


def _construir_prompt_extra_guiado(form) -> str:
    """Compone un bloque de reglas desde preguntas guiadas del formulario."""
    lineas = []

    afluencia = (form.get("afluencia") or "").strip()
    if afluencia:
        lineas.append(f"Afluencia prevista: {afluencia}.")

    horas_punta = (form.get("horas_punta") or "").strip()
    if horas_punta:
        lineas.append(f"Horas punta: {horas_punta}.")

    min_personal = (form.get("min_personal_turno") or "").strip()
    if min_personal:
        lineas.append(f"Dotacion minima simultanea por turno: {min_personal} persona(s).")

    pref_inicio = (form.get("pref_inicio") or "").strip()
    pref_fin = (form.get("pref_fin") or "").strip()
    if pref_inicio and pref_fin:
        lineas.append(f"Franja general de servicio: {pref_inicio}-{pref_fin}.")

    descanso = (form.get("descanso_min") or "").strip()
    if descanso:
        lineas.append(f"Aplicar pausa minima de {descanso} minutos cuando proceda.")

    libranza = (form.get("libranza_objetivo") or "").strip()
    if libranza:
        lineas.append(f"Objetivo de libranza semanal por empleado: {libranza} dia(s).")

    roles = (form.get("priorizar_roles") or "").strip()
    if roles:
        lineas.append(f"Prioridad de cobertura por puestos/areas: {roles}.")

    equidad = (form.get("equidad_reparto") or "").strip().lower()
    if equidad in ("si", "sí", "1", "true", "on"):
        lineas.append("Repartir turnos de forma equilibrada entre personas con el mismo puesto.")

    evitar_partidos = (form.get("evitar_partidos") or "").strip().lower()
    if evitar_partidos in ("si", "sí", "1", "true", "on"):
        lineas.append("Evitar turnos partidos salvo necesidad operativa.")

    sectores_cfg = (form.get("sectores_config") or "").strip()
    if sectores_cfg:
        lineas.append("Cobertura por sector (formato Sector|inicio-fin|min):")
        for ln in sectores_cfg.splitlines():
            s = ln.strip()
            if s:
                lineas.append(f"- {s}")

    texto_libre = (form.get("prompt_extra") or "").strip()
    if texto_libre:
        lineas.append(f"Indicaciones adicionales: {texto_libre[:800]}")

    out = "\n".join(lineas).strip()
    return out[:_PROMPT_GUIADO_FORM_MAX]


# =====================================================
# HORARIOS
# =====================================================


@bp.route("/horarios")
@login_requerido
@permiso_mod("mod.horarios")
def horarios():
    """Lista horarios del día, planning por rango y empleados para asignación."""

    fecha = request.args.get("fecha") or str(date.today())

    try:
        fd = date.fromisoformat(fecha)
    except ValueError:
        fd = date.today()
        fecha = str(fd)

    ayer = str(fd - timedelta(days=1))
    manana = str(fd + timedelta(days=1))
    hoy = str(date.today())

    vista = (request.args.get("vista") or "lista").strip().lower()
    if vista not in ("lista", "semana", "mes"):
        vista = "semana"

    inicio_sem = fd - timedelta(days=fd.weekday())
    fin_sem = inicio_sem + timedelta(days=6)

    plan_desde = request.args.get("plan_desde")
    plan_hasta = request.args.get("plan_hasta")
    if vista == "semana":
        plan_desde = str(inicio_sem)
        plan_hasta = str(fin_sem)
    elif not plan_desde or not plan_hasta:
        plan_desde = str(inicio_sem)
        plan_hasta = str(fin_sem)

    mes_param = (request.args.get("mes") or "").strip()
    if not mes_param:
        mes_param = fd.strftime("%Y-%m")
    try:
        y_m, mo_m = mes_param.split("-", 1)
        y_cal, m_cal = int(y_m), int(mo_m)
        if not (1 <= m_cal <= 12):
            raise ValueError
    except (ValueError, TypeError):
        y_cal, m_cal = fd.year, fd.month
        mes_param = fd.strftime("%Y-%m")

    if m_cal == 1:
        mes_anterior = f"{y_cal - 1}-12"
    else:
        mes_anterior = f"{y_cal}-{m_cal - 1:02d}"
    if m_cal == 12:
        mes_siguiente = f"{y_cal + 1}-01"
    else:
        mes_siguiente = f"{y_cal}-{m_cal + 1:02d}"

    db = get_db()
    ensure_config_empresa_table(db)
    config_empresa = get_config_empresa(db)
    franja_cfg = _franja_cfg_normalizada(config_empresa)
    franja_ui = _franja_ui_para_template(franja_cfg)

    horarios_dia = []
    horarios_planning = []
    empleados = []
    matriz_semana = None
    grid_mes = None
    horarios_dia_por_sector = []
    horarios_planning_por_sector = []
    horarios_dia_franjas = []
    puestos_trabajo = []
    franja_empresa_display = None
    tabla_cobertura_franja = None
    tabla_cobertura_franja_semana = []

    try:
        if tabla_existe(db, "empleados"):
            cols_emp = columnas_tabla(db, "empleados")
            if "puesto" in cols_emp:
                puestos_trabajo = [
                    r[0]
                    for r in db.execute(
                        """
                        SELECT DISTINCT TRIM(puesto) AS p
                        FROM empleados
                        WHERE puesto IS NOT NULL AND TRIM(puesto) != ''
                        ORDER BY p
                        """
                    ).fetchall()
                ]
        he_cfg = (config_empresa or {}).get("horario_empresa") or ""
        fr_ui = _extraer_franja_desde_horario_empresa(he_cfg)
        if fr_ui:
            franja_empresa_display = {
                "ini": _min_a_hora(fr_ui["inicio_min"]),
                "fin": _min_a_hora(fr_ui["fin_min"]),
            }
        if tabla_existe(db, "horarios") and tabla_existe(db, "empleados"):
            nexpr = _nombre_empleado_sql_db(db)
            qbase = _horarios_query_base_sql(nexpr, db)

            horarios_dia = [
                _enriquecer_horario_row(x, franja_cfg)
                for x in db.execute(
                    qbase + " WHERE h.fecha = ? ORDER BY h.hora_inicio, empleado_nombre",
                    (fecha,),
                ).fetchall()
            ]

            horarios_planning = [
                _enriquecer_horario_row(x, franja_cfg)
                for x in db.execute(
                    qbase + " WHERE h.fecha BETWEEN ? AND ? ORDER BY h.fecha, h.hora_inicio, empleado_nombre",
                    (plan_desde, plan_hasta),
                ).fetchall()
            ]
            horarios_dia_por_sector = _agrupar_horarios_por_sector(horarios_dia)
            horarios_planning_por_sector = _agrupar_horarios_por_sector(horarios_planning)
            horarios_dia_franjas = _agrupar_horarios_por_franja(horarios_dia, franja_cfg)

        empleados = _empleados_lista_dict(db)
        if vista == "semana" and empleados:
            matriz_semana = _matriz_semanal(db, inicio_sem, fin_sem, empleados, franja_cfg)
        if vista == "mes":
            grid_mes = _grid_mensual(db, y_cal, m_cal, franja_cfg)

    except Exception as e:
        _logger_horarios.exception("horarios vista: %s", e)
        flash(
            "No se pudieron cargar los datos de horarios. Si acabas de restaurar la base, "
            "comprueba que existan las tablas «empleados» y «horarios» (reinicia la app o ejecuta init).",
            "danger",
        )
        horarios_dia = []
        horarios_planning = []
        empleados = []
        matriz_semana = None
        grid_mes = None
        horarios_dia_por_sector = []
        horarios_planning_por_sector = []
        horarios_dia_franjas = []
        puestos_trabajo = []
        franja_empresa_display = None
    finally:
        db.close()

    fecha_cobertura_label = fd.strftime("%d/%m/%Y")
    if vista == "semana":
        tabla_cobertura_franja = _tabla_cobertura_franja_dia(horarios_dia or [], franja_cfg)
        tabla_cobertura_franja_semana = _tabla_cobertura_franja_semana(horarios_planning or [], franja_cfg)

    volver_params = {
        "fecha": fecha,
        "vista": vista,
        "plan_desde": plan_desde,
        "plan_hasta": plan_hasta,
        "mes": mes_param,
    }

    def _horarios_link(**overrides) -> str:
        p = {**volver_params, **overrides}
        return "/horarios?" + urlencode({k: v for k, v in p.items() if v})

    volver_qs = urlencode({k: v for k, v in volver_params.items() if v})
    volver_path = "/horarios?" + volver_qs if volver_qs else "/horarios"
    redirect_to_q = quote(volver_path, safe="")

    link_vista_lista = _horarios_link(vista="lista")
    link_vista_semana = _horarios_link(vista="semana")
    link_vista_mes = _horarios_link(vista="mes")
    fd_sem_ant = fd - timedelta(days=7)
    fd_sem_sig = fd + timedelta(days=7)
    link_semana_ant = _horarios_link(
        fecha=str(fd_sem_ant),
        vista="semana",
        mes=fd_sem_ant.strftime("%Y-%m"),
    )
    link_semana_sig = _horarios_link(
        fecha=str(fd_sem_sig),
        vista="semana",
        mes=fd_sem_sig.strftime("%Y-%m"),
    )
    link_mes_ant = _horarios_link(vista="mes", mes=mes_anterior, fecha=f"{mes_anterior}-01")
    link_mes_sig = _horarios_link(vista="mes", mes=mes_siguiente, fecha=f"{mes_siguiente}-01")
    link_ayer = _horarios_link(fecha=ayer)
    link_manana = _horarios_link(fecha=manana)
    link_hoy_nav = _horarios_link(fecha=hoy)

    nombres_mes = (
        "enero",
        "febrero",
        "marzo",
        "abril",
        "mayo",
        "junio",
        "julio",
        "agosto",
        "septiembre",
        "octubre",
        "noviembre",
        "diciembre",
    )
    titulo_mes = f"{nombres_mes[m_cal - 1].capitalize()} {y_cal}"

    nc = _parse_niveles_carga_semana_json((config_empresa or {}).get("niveles_carga_semana"))
    niveles_carga_dow = [nc[i] for i in range(7)]

    return render_template(
        "horarios.html",
        mostrar_nav=True,
        horarios=horarios_dia,
        horarios_planning=horarios_planning,
        empleados=empleados,
        fecha=fecha,
        ayer=ayer,
        manana=manana,
        hoy=hoy,
        plan_desde=plan_desde,
        plan_hasta=plan_hasta,
        config_empresa=config_empresa,
        vista=vista,
        mes_param=mes_param,
        titulo_mes=titulo_mes,
        matriz_semana=matriz_semana,
        grid_mes=grid_mes,
        mes_anterior=mes_anterior,
        mes_siguiente=mes_siguiente,
        link_vista_lista=link_vista_lista,
        link_vista_semana=link_vista_semana,
        link_vista_mes=link_vista_mes,
        link_semana_ant=link_semana_ant,
        link_semana_sig=link_semana_sig,
        link_mes_ant=link_mes_ant,
        link_mes_sig=link_mes_sig,
        link_ayer=link_ayer,
        link_manana=link_manana,
        link_hoy_nav=link_hoy_nav,
        volver_qs=volver_qs,
        volver_path=volver_path,
        redirect_to_q=redirect_to_q,
        horarios_dia_por_sector=horarios_dia_por_sector,
        horarios_planning_por_sector=horarios_planning_por_sector,
        horarios_dia_franjas=horarios_dia_franjas,
        puestos_trabajo=puestos_trabajo,
        franja_empresa_display=franja_empresa_display,
        franja_ui=franja_ui,
        tabla_cobertura_franja=tabla_cobertura_franja,
        tabla_cobertura_franja_semana=tabla_cobertura_franja_semana,
        fecha_cobertura_label=fecha_cobertura_label,
        niveles_carga_dow=niveles_carga_dow,
    )


@bp.route("/generar_horarios_reglas", methods=["POST"])
@login_requerido
@permiso_mod("mod.horarios")
def generar_horarios_reglas():
    """Genera horarios con criterios fijos (cobertura por sector + franja), sin IA."""
    fecha_inicio = request.form.get("fecha_inicio")
    fecha_fin = request.form.get("fecha_fin")
    if not fecha_inicio or not fecha_fin:
        flash("Indica fecha inicio y fecha fin.", "warning")
        return redirect(url_for("admin.horarios"))

    db = get_db()
    try:
        if not tabla_existe(db, "empleados") or not tabla_existe(db, "horarios"):
            flash(
                "Faltan tablas «empleados» u «horarios» en la base de datos. No se puede generar el cuadrante.",
                "danger",
            )
            return redirect(url_for("admin.horarios", fecha=fecha_inicio))
        ensure_config_empresa_table(db)
        cfg_emp = get_config_empresa(db)
        horario_emp_txt = (cfg_emp.get("horario_empresa") or "").strip()
        reglas = _resolver_cobertura_sectores_final(request.form, horario_emp_txt)
        faltan_cat = _categorias_sin_servicio(reglas)
        if faltan_cat:
            flash(
                "No se puede generar: falta configurar servicio en "
                + ", ".join(faltan_cat)
                + ".",
                "danger",
            )
            return redirect(
                url_for(
                    "admin.horarios",
                    fecha=fecha_inicio,
                    plan_desde=fecha_inicio,
                    plan_hasta=fecha_fin,
                )
            )

        cols_e = columnas_tabla(db, "empleados")
        try:
            sel = ["id", "nombre"]
            if "apellido" in cols_e:
                sel.append("apellido")
            sel.append("puesto")
            if "departamento" in cols_e:
                sel.append("departamento")
            if "observaciones" in cols_e:
                sel.append("observaciones")
            if "horas_contrato" in cols_e:
                sel.append("horas_contrato")
            wh = "WHERE activo = 1" if "activo" in cols_e else ""
            q = f"SELECT {', '.join(sel)} FROM empleados {wh} ORDER BY nombre"
            empleados = db.execute(q).fetchall()
        except Exception as e:
            flash(f"No se pudieron leer empleados: {e}", "danger")
            return redirect(url_for("admin.horarios", fecha=fecha_inicio))

        if not empleados:
            flash("No hay empleados activos.", "warning")
            return redirect(url_for("admin.horarios", fecha=fecha_inicio))

        empleados_ids = []
        for e in empleados:
            try:
                empleados_ids.append(int(dict(e).get("id")))
            except (TypeError, ValueError):
                continue
        dias_libres_cliente = _dias_libres_aprobados_por_empleado(
            db, fecha_inicio, fecha_fin, empleados_ids
        )

        horas_semana_por_empleado = {}
        for e in empleados:
            ed = dict(e)
            try:
                eid = int(ed.get("id"))
            except (TypeError, ValueError):
                continue
            horas_semana_por_empleado[eid] = _horas_contrato_semana_safe(ed.get("horas_contrato"))

        vals_dom = request.form.getlist("priorizar_domingo_reglas")
        priorizar_domingo = "1" in vals_dom
        vals_enc = request.form.getlist("diversificar_encargados_reglas")
        diversificar_encargados = "1" in vals_enc
        vals_fill = request.form.getlist("rellenar_hasta_contrato_reglas")
        rellenar_hasta_contrato = "1" in vals_fill
        vals_mix = request.form.getlist("preferir_mixto_barra_sala_reglas")
        preferir_mixto_barra_sala = "1" in vals_mix
        preferencia_mixto_barra_sala = (request.form.get("preferencia_mixto_barra_sala") or "sala").strip().lower()
        vals_force = request.form.getlist("forzar_horas_contrato_reglas")
        forzar_horas_contrato = "1" in vals_force
        vals_split = request.form.getlist("permitir_partido_cobertura_reglas")
        permitir_partido_cobertura = "1" in vals_split
        descanso_min_partido_min = request.form.get("descanso_min_partido_min", type=int) or 180
        if descanso_min_partido_min < 0:
            descanso_min_partido_min = 0
        # Legal/operativo: descanso entre jornadas fijo por normativa.
        descanso_entre_jornadas_h = float(_DESCANSO_ENTRE_JORNADAS_H)
        vals_close_open = request.form.getlist("regla_cierra_no_abre_reglas")
        regla_cierra_no_abre = "1" in vals_close_open
        vals_support = request.form.getlist("permitir_apoyo_sala_en_barra_reglas")
        permitir_apoyo_sala_en_barra = "1" in vals_support
        vals_crit = request.form.getlist("priorizar_dias_criticos_reglas")
        priorizar_dias_criticos = "1" in vals_crit
        vals_total = request.form.getlist("permitir_cobertura_total_reglas")
        permitir_cobertura_total = "1" in vals_total
        vals_mf = request.form.getlist("modo_por_frentes_reglas")
        modo_por_frentes = "1" in vals_mf
        orden_frentes = (request.form.get("orden_frentes_reglas") or "sala_barra_cocina").strip().lower()
        vals_serv = request.form.getlist("modo_servicio_minimo_reglas")
        modo_servicio_minimo = "1" in vals_serv
        ventanas_hora_punta = _leer_horas_punta_desde_form(request.form)
        niveles_carga = _niveles_carga_desde_request(request.form, cfg_emp.get("niveles_carga_semana"))

        # Prioridad operativa explícita:
        # en servicio mínimo prima cubrir base + encargado, y NO completar contrato.
        if modo_servicio_minimo:
            rellenar_hasta_contrato = False
            forzar_horas_contrato = False

        try:
            pendientes, advertencias = _generar_pendientes_por_reglas(
                fecha_inicio,
                fecha_fin,
                list(reglas or []),
                empleados,
                horas_semana_por_empleado,
                priorizar_domingo=priorizar_domingo,
                niveles_por_weekday=niveles_carga,
                diversificar_encargados=diversificar_encargados,
                rellenar_hasta_contrato=rellenar_hasta_contrato,
                preferir_mixto_barra_sala=preferir_mixto_barra_sala,
                preferencia_mixto_barra_sala=preferencia_mixto_barra_sala,
                forzar_horas_contrato=forzar_horas_contrato,
                permitir_partido_cobertura=permitir_partido_cobertura,
                descanso_min_partido_min=descanso_min_partido_min,
                descanso_entre_jornadas_h=descanso_entre_jornadas_h,
                regla_cierra_no_abre=regla_cierra_no_abre,
                permitir_apoyo_sala_en_barra=permitir_apoyo_sala_en_barra,
                priorizar_dias_criticos=priorizar_dias_criticos,
                ventanas_hora_punta=ventanas_hora_punta,
                permitir_cobertura_total=permitir_cobertura_total,
                modo_por_frentes=modo_por_frentes,
                orden_frentes=orden_frentes,
                modo_servicio_minimo=modo_servicio_minimo,
                dias_libres_cliente=dias_libres_cliente,
            )
            pendientes, descartes_diarios, descartes_semanales = _filtrar_turnos_por_reglas_legales_y_contrato(
                pendientes,
                horas_semana_por_empleado,
            )
            if modo_servicio_minimo:
                incid = [m for m in advertencias if m.startswith("[SERV_MIN]")]
                if incid:
                    flash(
                        f"Servicio mínimo aplicado: {len(incid)} tramo(s) quedaron en cobertura parcial.",
                        "info",
                    )
            else:
                for msg in advertencias[:6]:
                    flash(msg, "warning")

            if not pendientes:
                flash(
                    "No se generó ningún turno: revisa dotaciones (números > 0), "
                    "franja (Inicio/Fin servicio o horario de empresa) y que haya personal compatible con cada sector.",
                    "warning",
                )
                db.commit()
                return redirect(
                    url_for(
                        "admin.horarios",
                        fecha=fecha_inicio,
                        plan_desde=fecha_inicio,
                        plan_hasta=fecha_fin,
                    )
                )

            db.execute(
                "DELETE FROM horarios WHERE fecha BETWEEN ? AND ?",
                (fecha_inicio, fecha_fin),
            )
            insertados = 0
            for eid, fecha, hora_inicio, hora_fin, turno, horas in pendientes:
                db.execute(
                    """
                    INSERT INTO horarios
                    (empleado_id, fecha, hora_inicio, hora_fin, turno, horas, estado)
                    VALUES (?, ?, ?, ?, ?, ?, 'Programado')
                    """,
                    (eid, fecha, hora_inicio, hora_fin, turno, horas),
                )
                insertados += 1
            db.commit()
            _persist_niveles_carga_semana(db, niveles_carga)
            flash(
                f"Cuadrante generado por reglas: {insertados} turno(s) entre {fecha_inicio} y {fecha_fin}. "
                "Revisa el cuadrante y ajusta cobertura o reglas si hace falta.",
                "success",
            )
            # Diagnóstico por empleado: contrato vs horas asignadas en el rango.
            try:
                di = date.fromisoformat(fecha_inicio)
                df = date.fromisoformat(fecha_fin)
                if di > df:
                    di, df = df, di
                dias_rango = (df - di).days + 1
            except ValueError:
                dias_rango = 7
            factor_obj = max(1, dias_rango) / 7.0
            horas_asig_por_eid: dict[int, float] = defaultdict(float)
            for eid, _f, _hi, _hf, _t, horas in pendientes:
                try:
                    horas_asig_por_eid[int(eid)] += float(horas or 0.0)
                except (TypeError, ValueError):
                    continue

            deficits: list[tuple[float, str]] = []
            for e in empleados:
                ed = dict(e)
                try:
                    eid = int(ed.get("id"))
                except (TypeError, ValueError):
                    continue
                nom = _nombre_display_empleado(ed) or f"ID {eid}"
                contrato_sem = float(horas_semana_por_empleado.get(eid, 40.0))
                objetivo = round(contrato_sem * factor_obj, 2)
                asignado = round(float(horas_asig_por_eid.get(eid, 0.0)), 2)
                dif = round(objetivo - asignado, 2)
                if dif > 0.5:
                    deficits.append((dif, f"{nom}: {asignado:g}/{objetivo:g}h (faltan {dif:g}h)"))
            if deficits:
                deficits.sort(key=lambda x: x[0], reverse=True)
                txt = "; ".join(x[1] for x in deficits[:6])
                suf = f" (+{len(deficits) - 6} más)" if len(deficits) > 6 else ""
                flash(f"Déficit de horas por contrato en el rango: {txt}{suf}", "warning")
            if descartes_diarios or descartes_semanales:
                flash(
                    "Algunas asignaciones se descartaron por límites de jornada o contrato: "
                    f"{descartes_diarios} diario(s), {descartes_semanales} semanal(es).",
                    "warning",
                )
        except Exception as e:
            _logger_horarios.exception("generar_horarios_reglas: %s", e)
            flash(f"Error al generar por reglas: {e}", "danger")
    finally:
        db.close()
    return redirect(
        url_for(
            "admin.horarios",
            fecha=fecha_inicio,
            plan_desde=fecha_inicio,
            plan_hasta=fecha_fin,
        )
    )


# =====================================================
# PUBLICAR PDFs EN PERFIL DE EMPLEADOS
# =====================================================


@bp.route("/horarios/publicar_pdfs_empleados", methods=["POST"])
@login_requerido
@permiso_mod("mod.horarios")
def publicar_horarios_pdfs_empleados():
    """Genera un PDF por empleado con sus turnos del rango y lo guarda en su área personal."""
    desde = (request.form.get("plan_desde") or "").strip()
    hasta = (request.form.get("plan_hasta") or "").strip()
    if not desde or not hasta:
        flash("Indica el rango del planning (desde / hasta).", "warning")
        return redirect(url_for("admin.horarios"))

    try:
        d0 = date.fromisoformat(desde[:10])
        d1 = date.fromisoformat(hasta[:10])
    except ValueError:
        flash("Fechas no válidas.", "danger")
        return redirect(url_for("admin.horarios"))

    if d0 > d1:
        flash("La fecha inicial no puede ser posterior a la final.", "warning")
        return redirect(
            url_for(
                "admin.horarios",
                fecha=str(date.today()),
                plan_desde=desde,
                plan_hasta=hasta,
            )
        )

    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa
    from reservas.horarios_entrega_helpers import (
        empleados_con_turnos_en_rango,
        etiqueta_periodo_es,
        lineas_horarios_empleado_periodo,
    )
    from reservas.horarios_entregas_schema import ensure_horarios_entregas_table
    from reservas.pdf_horarios_empleado import (
        construir_pdf_horarios_empleado,
        reportlab_disponible,
        reportlab_error_detalle,
    )

    if not reportlab_disponible():
        det = reportlab_error_detalle() or ""
        flash(
            "No se puede generar PDF. Instala: pip install reportlab pillow. " + det,
            "danger",
        )
        return redirect(
            url_for(
                "admin.horarios",
                fecha=desde[:10],
                plan_desde=desde,
                plan_hasta=hasta,
            )
        )

    db = get_db()
    ensure_horarios_entregas_table(db)
    ensure_config_empresa_table(db)
    empresa = get_config_empresa(db)

    emp_ids = empleados_con_turnos_en_rango(db, desde[:10], hasta[:10])
    if not emp_ids:
        db.close()
        flash(
            "No hay turnos en ese rango para ningún empleado. No se generó ningún PDF.",
            "warning",
        )
        return redirect(
            url_for(
                "admin.horarios",
                fecha=desde[:10],
                plan_desde=desde,
                plan_hasta=hasta,
            )
        )

    static_root = current_app.static_folder
    upload_dir = os.path.join(static_root, "uploads", "horarios_empleado")
    os.makedirs(upload_dir, exist_ok=True)

    periodo_txt = etiqueta_periodo_es(desde[:10], hasta[:10])
    ok = 0
    errs: list[str] = []

    for eid in emp_ids:
        lineas = lineas_horarios_empleado_periodo(db, eid, desde[:10], hasta[:10])
        if not lineas:
            continue
        emp = db.execute("SELECT * FROM empleados WHERE id = ?", (eid,)).fetchone()
        if not emp:
            continue
        emp_d = dict(emp)
        try:
            pdf_bytes = construir_pdf_horarios_empleado(
                static_root,
                empresa,
                emp_d,
                lineas,
                periodo_txt,
            )
        except Exception as ex:
            errs.append(f"ID {eid}: {ex}")
            continue

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        safe = f"emp{eid}_{desde[:10]}_{hasta[:10]}_{ts}.pdf"
        full = os.path.join(upload_dir, safe)
        with open(full, "wb") as f:
            f.write(pdf_bytes)
        rel = f"uploads/horarios_empleado/{safe}".replace("\\", "/")
        etiqueta = f"Planning {periodo_txt}"
        db.execute(
            """
            INSERT INTO horarios_pdf_entregas (empleado_id, periodo_desde, periodo_hasta, etiqueta, archivo_relativo)
            VALUES (?, ?, ?, ?, ?)
            """,
            (eid, desde[:10], hasta[:10], etiqueta, rel),
        )
        ok += 1

    db.commit()
    db.close()

    if ok:
        flash(
            f"Se publicaron {ok} documento(s) PDF: cada persona los tiene en "
            "Área personal → «Documentos de horarios» (ver y descargar).",
            "success",
        )
    if errs:
        flash("Algunos PDFs fallaron: " + "; ".join(errs[:4]), "warning")

    return redirect(
        url_for(
            "admin.horarios",
            fecha=desde[:10],
            plan_desde=desde,
            plan_hasta=hasta,
        )
    )


# =====================================================
# EDITAR / ELIMINAR TURNO
# =====================================================


@bp.route("/horario/<int:hid>/eliminar", methods=["POST"])
@login_requerido
@permiso_mod("mod.horarios")
def eliminar_horario(hid):
    db = get_db()
    try:
        if tabla_existe(db, "horarios"):
            db.execute("DELETE FROM horarios WHERE id = ?", (hid,))
            db.commit()
            flash("Turno eliminado.", "success")
        else:
            flash("Tabla de horarios no disponible.", "warning")
    finally:
        db.close()
    return _redirect_horarios_form()


@bp.route("/horarios/eliminar_masivo", methods=["POST"])
@login_requerido
@permiso_mod("mod.horarios")
def eliminar_horarios_masivo():
    raw_ids = request.form.getlist("horario_ids")
    ids: list[int] = []
    for raw in raw_ids:
        try:
            hid = int(str(raw).strip())
            if hid > 0:
                ids.append(hid)
        except (TypeError, ValueError):
            continue
    # Evita IDs repetidos enviados por el cliente.
    ids = list(dict.fromkeys(ids))

    if not ids:
        flash("Selecciona al menos un turno para eliminar.", "warning")
        return _redirect_horarios_form()

    db = get_db()
    try:
        if not tabla_existe(db, "horarios"):
            flash("Tabla de horarios no disponible.", "warning")
            return _redirect_horarios_form()
        marks = ",".join(["?"] * len(ids))
        cur = db.execute(f"DELETE FROM horarios WHERE id IN ({marks})", ids)
        db.commit()
        borrados = cur.rowcount if cur and cur.rowcount is not None else 0
        if borrados:
            flash(f"Se eliminaron {borrados} turno(s).", "success")
        else:
            flash("No se eliminaron turnos (puede que ya no existieran).", "info")
    finally:
        db.close()
    return _redirect_horarios_form()


@bp.route("/horarios/eliminar_mes", methods=["POST"])
@login_requerido
@permiso_mod("mod.horarios")
def eliminar_horarios_mes():
    mes = (request.form.get("mes") or "").strip()
    if not mes or len(mes) < 7:
        flash("Indica un mes (YYYY-MM).", "warning")
        return _redirect_horarios_form()
    try:
        y_str, mo_str = mes.split("-", 1)
        y, mo = int(y_str), int(mo_str)
        if not (1 <= mo <= 12):
            raise ValueError
    except (ValueError, TypeError):
        flash("Mes no válido.", "warning")
        return _redirect_horarios_form()

    ultimo = calendar.monthrange(y, mo)[1]
    desde = f"{y:04d}-{mo:02d}-01"
    hasta = f"{y:04d}-{mo:02d}-{ultimo:02d}"

    db = get_db()
    try:
        if not tabla_existe(db, "horarios"):
            flash("Tabla de horarios no disponible.", "warning")
            return _redirect_horarios_form()
        cur = db.execute(
            "DELETE FROM horarios WHERE fecha >= ? AND fecha <= ?",
            (desde, hasta),
        )
        db.commit()
        borrados = cur.rowcount if cur and cur.rowcount is not None else 0
        if borrados:
            flash(
                f"Se eliminaron {borrados} turno(s) del periodo {desde} a {hasta}.",
                "success",
            )
        else:
            flash(
                f"No había turnos entre {desde} y {hasta}.",
                "info",
            )
    finally:
        db.close()
    return _redirect_horarios_form()


@bp.route("/horario/<int:hid>/editar", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.horarios")
def editar_horario(hid):
    db = get_db()
    if not tabla_existe(db, "horarios"):
        db.close()
        abort(404)
    row = db.execute("SELECT * FROM horarios WHERE id = ?", (hid,)).fetchone()
    if not row:
        db.close()
        abort(404)
    h = dict(row)
    empleados = _empleados_lista_dict(db)

    if request.method == "POST":
        eid = request.form.get("empleado_id", type=int)
        fecha_s = (request.form.get("fecha") or "").strip()
        hi = (request.form.get("hora_inicio") or "").strip()
        hf = (request.form.get("hora_fin") or "").strip()
        turno = (request.form.get("turno") or "").strip()
        estado = (request.form.get("estado") or "Programado").strip()
        red = (request.form.get("redirect_to") or "").strip()
        if not eid or not fecha_s or not hi or not hf:
            flash("Empleado, fecha e intervalo de horas son obligatorios.", "warning")
            db.close()
            return redirect(url_for("admin.editar_horario", hid=hid, redirect_to=red))
        horas = _calcular_horas_diferencia(hi, hf)
        db.execute(
            """
            UPDATE horarios
            SET empleado_id=?, fecha=?, hora_inicio=?, hora_fin=?, turno=?, horas=?, estado=?
            WHERE id=?
            """,
            (eid, fecha_s[:10], hi, hf, turno or None, horas, estado or "Programado", hid),
        )
        db.commit()
        db.close()
        flash("Turno actualizado.", "success")
        if red.startswith("/horarios"):
            return redirect(red)
        return redirect(url_for("admin.horarios", fecha=fecha_s[:10]))

    db.close()
    return render_template(
        "horario_editar.html",
        mostrar_nav=True,
        h=h,
        empleados=empleados,
        redirect_to=(request.args.get("redirect_to") or ""),
    )
