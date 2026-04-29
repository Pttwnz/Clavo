"""Construye eventos para el calendario admin (festivos, RRHH, avisos, proveedores)."""
from __future__ import annotations

from datetime import date, timedelta

from models import get_db
from reservas.calendario_admin_schema import T_AVISOS, T_CARGA, T_FESTIVOS, ensure_calendario_admin_tables
from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.proveedores_schema import ensure_proveedores_table
from reservas.rrhh_peticiones_schema import ensure_rrhh_peticiones_schema


def _parse_iso_date(s: str | None) -> date | None:
    if not s:
        return None
    s = str(s).strip()[:10]
    if len(s) < 10:
        return None
    try:
        return date.fromisoformat(s)
    except ValueError:
        return None


def _weekday_from_dia_pedido(s: str | None) -> int | None:
    """Mapa flexible: 'lunes', 'Lun', 'miércoles'… → 0=lunes … 6=domingo."""
    if not s or not str(s).strip():
        return None
    t = "".join(c for c in str(s).strip().lower() if c.isalpha() or c in "áéíóú")
    if not t:
        return None
    pairs = (
        ("lunes", 0),
        ("martes", 1),
        ("miércoles", 2),
        ("miercoles", 2),
        ("mié", 2),
        ("mie", 2),
        ("jueves", 3),
        ("viernes", 4),
        ("sábado", 5),
        ("sabado", 5),
        ("domingo", 6),
    )
    for name, wd in pairs:
        if t.startswith(name):
            return wd
    if len(t) >= 3:
        for name, wd in pairs:
            if name.startswith(t[:3]):
                return wd
    return None


def _daterange(d0: date, d1: date):
    d = d0
    while d <= d1:
        yield d
        d += timedelta(days=1)


def build_calendario_events(start: date, end: date) -> list[dict]:
    """
    Lista de dicts compatibles con FullCalendar (title, start, end?, allDay, backgroundColor, borderColor, url?, extendedProps).
    """
    out: list[dict] = []
    db = get_db()
    try:
        ensure_calendario_admin_tables(db)
        ensure_rrhh_peticiones_schema(db)
        ensure_proveedores_table(db)

        # --- Festivos locales ---
        if tabla_existe(db, T_FESTIVOS):
            for row in db.execute(
                f"""
                SELECT id, fecha, titulo, notas FROM {T_FESTIVOS}
                WHERE fecha >= ? AND fecha <= ?
                ORDER BY fecha
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall():
                fd = _parse_iso_date(row["fecha"])
                if not fd:
                    continue
                tip = (row["titulo"] or "").strip() or "Festivo"
                out.append(
                    {
                        "id": f"fest-{row['id']}",
                        "title": tip,
                        "start": fd.isoformat(),
                        "allDay": True,
                        "backgroundColor": "#64748b",
                        "borderColor": "#475569",
                        "extendedProps": {"tipo": "festivo", "notas": (row["notas"] or "").strip()},
                    }
                )

        # --- Avisos (rango) ---
        if tabla_existe(db, T_AVISOS):
            for row in db.execute(
                f"""
                SELECT id, titulo, cuerpo, fecha_ini, fecha_fin FROM {T_AVISOS}
                WHERE fecha_fin >= ? AND fecha_ini <= ?
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall():
                fi = _parse_iso_date(row["fecha_ini"])
                ff = _parse_iso_date(row["fecha_fin"])
                if not fi or not ff:
                    continue
                tit = (row["titulo"] or "").strip() or "Aviso"
                # FullCalendar end is exclusive
                end_exc = ff + timedelta(days=1)
                cat = None
                try:
                    cat = row["categoria"]
                except (KeyError, IndexError):
                    pass
                ev_prox = (cat or "").strip() == "evento_proximo"
                bg = "#c026d3" if ev_prox else "#f59e0b"
                bd = "#86198f" if ev_prox else "#d97706"
                xp = {
                    "tipo": "aviso_evento_proximo" if ev_prox else "aviso",
                    "cuerpo": (row["cuerpo"] or "").strip(),
                }
                out.append(
                    {
                        "id": f"avis-{row['id']}",
                        "title": tit,
                        "start": fi.isoformat(),
                        "end": end_exc.isoformat(),
                        "allDay": True,
                        "backgroundColor": bg,
                        "borderColor": bd,
                        "extendedProps": xp,
                    }
                )

        # --- Alta carga laboral (Fallas, Semana Santa, Feria…) ---
        if tabla_existe(db, T_CARGA):
            for row in db.execute(
                f"""
                SELECT id, titulo, fecha_ini, fecha_fin, notas FROM {T_CARGA}
                WHERE fecha_fin >= ? AND fecha_ini <= ?
                ORDER BY fecha_ini
                """,
                (start.isoformat(), end.isoformat()),
            ).fetchall():
                fi = _parse_iso_date(row["fecha_ini"])
                ff = _parse_iso_date(row["fecha_fin"])
                if not fi or not ff:
                    continue
                tit = (row["titulo"] or "").strip() or "Alta carga"
                end_exc = ff + timedelta(days=1)
                out.append(
                    {
                        "id": f"carga-{row['id']}",
                        "title": tit,
                        "start": fi.isoformat(),
                        "end": end_exc.isoformat(),
                        "allDay": True,
                        "backgroundColor": "#e11d48",
                        "borderColor": "#be123c",
                        "extendedProps": {
                            "tipo": "carga_laboral",
                            "notas": (row["notas"] or "").strip(),
                        },
                    }
                )

        # --- Solicitudes RRHH ---
        if tabla_existe(db, "solicitudes") and tabla_existe(db, "empleados"):
            cols_e = columnas_tabla(db, "empleados")
            if "apellido" in cols_e:
                nombre_sql = "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
            else:
                nombre_sql = "COALESCE(e.nombre, '')"
            q = f"""
                SELECT s.id, s.tipo, s.fecha_inicio, s.fecha_fin, s.estado, {nombre_sql} AS empleado_nombre
                FROM solicitudes s
                LEFT JOIN empleados e ON e.id = s.empleado_id
                WHERE s.fecha_fin IS NOT NULL AND s.fecha_inicio IS NOT NULL
                  AND TRIM(s.fecha_fin) != '' AND TRIM(s.fecha_inicio) != ''
                  AND s.fecha_fin >= ? AND s.fecha_inicio <= ?
            """
            for row in db.execute(q, (start.isoformat(), end.isoformat())).fetchall():
                fi = _parse_iso_date(row["fecha_inicio"])
                ff = _parse_iso_date(row["fecha_fin"])
                if not fi or not ff:
                    continue
                nom = (row["empleado_nombre"] or "").strip() or "?"
                tipo = (row["tipo"] or "").strip() or "Solicitud"
                est = (row["estado"] or "").strip() or "?"
                col = "#7c3aed"
                el = (est or "").lower()
                if "pendiente" in el:
                    col = "#a855f7"
                elif "aprob" in el:
                    col = "#16a34a"
                elif "rechaz" in el or "deneg" in el:
                    col = "#dc2626"
                end_exc = ff + timedelta(days=1)
                out.append(
                    {
                        "id": f"sol-{row['id']}",
                        "title": f"{tipo}: {nom} ({est})",
                        "start": fi.isoformat(),
                        "end": end_exc.isoformat(),
                        "allDay": True,
                        "backgroundColor": col,
                        "borderColor": col,
                        "url": "/rrhh_peticiones",
                        "extendedProps": {"tipo": "solicitud", "solicitud_id": row["id"]},
                    }
                )

        # --- Mensajes RRHH (día del mensaje) ---
        if tabla_existe(db, "mensajes_rrhh") and tabla_existe(db, "empleados"):
            cols_e = columnas_tabla(db, "empleados")
            if "apellido" in cols_e:
                nombre_sql = "TRIM(COALESCE(e.nombre,'') || ' ' || COALESCE(e.apellido,''))"
            else:
                nombre_sql = "COALESCE(e.nombre, '')"
            q = f"""
                SELECT m.id, m.creado_en, m.estado_gestion, {nombre_sql} AS empleado_nombre
                FROM mensajes_rrhh m
                LEFT JOIN empleados e ON e.id = m.empleado_id
                WHERE substr(COALESCE(m.creado_en,''), 1, 10) >= ?
                  AND substr(COALESCE(m.creado_en,''), 1, 10) <= ?
            """
            for row in db.execute(q, (start.isoformat(), end.isoformat())).fetchall():
                raw = (row["creado_en"] or "")[:10]
                dmsg = _parse_iso_date(raw)
                if not dmsg:
                    continue
                nom = (row["empleado_nombre"] or "").strip() or "?"
                est = (row["estado_gestion"] or "Pendiente").strip()
                col = "#6366f1"
                if est.lower() == "pendiente":
                    col = "#4f46e5"
                out.append(
                    {
                        "id": f"msg-{row['id']}",
                        "title": f"RRHH · {nom} ({est})",
                        "start": dmsg.isoformat(),
                        "allDay": True,
                        "backgroundColor": col,
                        "borderColor": col,
                        "url": "/rrhh_peticiones",
                        "extendedProps": {"tipo": "mensaje_rrhh", "mensaje_id": row["id"]},
                    }
                )

        # --- Proveedores: día habitual de pedido (semanal en el rango) ---
        if tabla_existe(db, "proveedores"):
            for prow in db.execute(
                "SELECT id, nombre, dia_habitual_pedido, activo FROM proveedores WHERE activo = 1"
            ).fetchall():
                wd = _weekday_from_dia_pedido(prow["dia_habitual_pedido"])
                if wd is None:
                    continue
                nombre = (prow["nombre"] or "").strip() or "Proveedor"
                for d in _daterange(start, end):
                    if d.weekday() != wd:
                        continue
                    out.append(
                        {
                            "id": f"prov-{prow['id']}-{d.isoformat()}",
                            "title": f"Pedido · {nombre}",
                            "start": d.isoformat(),
                            "allDay": True,
                            "backgroundColor": "#0ea5e9",
                            "borderColor": "#0284c7",
                            "url": "/proveedores",
                            "extendedProps": {"tipo": "proveedor", "proveedor_id": prow["id"]},
                        }
                    )
    finally:
        db.close()

    return out
