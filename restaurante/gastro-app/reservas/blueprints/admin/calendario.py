"""Calendario unificado admin: festivos, RRHH, avisos, proveedores."""
from datetime import date

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import get_db
from reservas.calendario_admin_schema import T_AVISOS, T_CARGA, T_FESTIVOS, ensure_calendario_admin_tables
from reservas.calendario_admin_events import build_calendario_events
from reservas.db_helpers import tabla_existe
from reservas.decorators import login_requerido, permiso_mod
from reservas.festivos_loader import (
    OFFICIAL_SUBDIV_CODES,
    OFFICIAL_SUBDIV_SPECS,
    holidays_spain_tuples,
)
from reservas.fiestas_carga_presets import PRESETS, aplicar_preset
from reservas.i18n import translate as tr_i18n

from . import bp


def _insertar_carga_presets(db, items: list[tuple[str, int]]) -> int:
    """Inserta periodos desde plantillas (preset_id, año). Evita duplicados por título+rango."""
    n = 0
    for preset_id, year in items:
        try:
            ini, fin, titulo, notas = aplicar_preset(preset_id, year)
        except Exception:
            continue
        fi, ff = ini.isoformat(), fin.isoformat()
        row = db.execute(
            f"""
            SELECT 1 FROM {T_CARGA}
            WHERE titulo = ? AND fecha_ini = ? AND fecha_fin = ? LIMIT 1
            """,
            (titulo.strip(), fi, ff),
        ).fetchone()
        if row:
            continue
        db.execute(
            f"""
            INSERT INTO {T_CARGA} (titulo, fecha_ini, fecha_fin, ubicacion, notas, preset_id)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (titulo, fi, ff, None, notas, preset_id),
        )
        n += 1
    db.commit()
    return n


def _insertar_festivos_tuplas(db, tuplas: list[tuple[str, str, str]]) -> int:
    """Inserta filas en calendario_festivos; omite duplicados (misma fecha y mismo título)."""
    n = 0
    for fecha, titulo, notas in tuplas:
        fecha = (fecha or "").strip()[:10]
        tit = (titulo or "").strip()
        if len(fecha) < 10 or not tit:
            continue
        dup = db.execute(
            f"SELECT 1 FROM {T_FESTIVOS} WHERE fecha = ? AND titulo = ? LIMIT 1",
            (fecha, tit),
        ).fetchone()
        if dup:
            continue
        db.execute(
            f"INSERT INTO {T_FESTIVOS} (fecha, titulo, notas) VALUES (?,?,?)",
            (fecha, tit, (notas or "").strip() or None),
        )
        n += 1
    if n:
        db.commit()
    return n


@bp.route("/calendario")
@login_requerido
@permiso_mod("mod.calendario")
def calendario_admin():
    db = get_db()
    ensure_calendario_admin_tables(db)
    festivos = []
    avisos = []
    cargas = []
    if tabla_existe(db, T_FESTIVOS):
        festivos = [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM {T_FESTIVOS} ORDER BY fecha DESC LIMIT 24"
            ).fetchall()
        ]
    if tabla_existe(db, T_AVISOS):
        avisos = [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM {T_AVISOS} ORDER BY fecha_ini DESC LIMIT 24"
            ).fetchall()
        ]
    if tabla_existe(db, T_CARGA):
        cargas = [
            dict(r)
            for r in db.execute(
                f"SELECT * FROM {T_CARGA} ORDER BY fecha_ini DESC LIMIT 24"
            ).fetchall()
        ]
    db.close()
    return render_template(
        "calendario_admin.html",
        mostrar_nav=True,
        festivos=festivos,
        avisos=avisos,
        cargas=cargas,
        carga_presets=PRESETS,
        official_subdiv_specs=OFFICIAL_SUBDIV_SPECS,
        ano_actual=date.today().year,
    )


@bp.route("/api/calendario_eventos")
@login_requerido
@permiso_mod("mod.calendario")
def api_calendario_eventos():
    start_s = (request.args.get("start") or "")[:10]
    end_s = (request.args.get("end") or "")[:10]
    try:
        start = date.fromisoformat(start_s) if len(start_s) >= 10 else date.today().replace(day=1)
        end = date.fromisoformat(end_s) if len(end_s) >= 10 else date.today()
    except ValueError:
        start = date.today().replace(day=1)
        end = date.today()
    if end < start:
        start, end = end, start
    events = build_calendario_events(start, end)
    return jsonify(events)


@bp.route("/calendario/festivos_oficiales", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_festivos_oficiales():
    """Carga festius oficials (paquet holidays, alineat BOE) per CCAA o només estatals."""
    subdiv_in = (request.form.get("subdiv") or "").strip().upper()
    if subdiv_in not in OFFICIAL_SUBDIV_CODES:
        flash(tr_i18n("page.cal.official_flash_bad"), "warning")
        return redirect(url_for("admin.calendario_admin"))
    subdiv = None if subdiv_in == "" else subdiv_in
    year = request.form.get("year", type=int) or date.today().year
    if year < 2000 or year > 2100:
        flash(tr_i18n("page.cal.official_flash_bad"), "warning")
        return redirect(url_for("admin.calendario_admin"))
    try:
        tuplas = holidays_spain_tuples(subdiv, [year])
    except Exception as e:
        flash(tr_i18n("page.cal.official_flash_err", err=str(e)), "danger")
        return redirect(url_for("admin.calendario_admin"))
    db = get_db()
    ensure_calendario_admin_tables(db)
    n = _insertar_festivos_tuplas(db, tuplas)
    db.close()
    if n:
        flash(tr_i18n("page.cal.official_flash_ok", n=n, year=year), "success")
    else:
        flash(tr_i18n("page.cal.official_flash_zero", year=year), "info")
    return redirect(url_for("admin.calendario_admin"))


@bp.route("/calendario/festivo", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_festivo_crear():
    fecha = (request.form.get("fecha") or "").strip()[:10]
    titulo = (request.form.get("titulo") or "").strip()
    notas = (request.form.get("notas") or "").strip()
    db = get_db()
    ensure_calendario_admin_tables(db)
    if len(fecha) >= 10 and titulo:
        db.execute(
            f"INSERT INTO {T_FESTIVOS} (fecha, titulo, notas) VALUES (?, ?, ?)",
            (fecha, titulo, notas or None),
        )
        db.commit()
    db.close()
    return redirect(url_for("admin.calendario_admin"))


@bp.route("/calendario/festivo/<int:fid>/borrar", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_festivo_borrar(fid: int):
    db = get_db()
    ensure_calendario_admin_tables(db)
    db.execute(f"DELETE FROM {T_FESTIVOS} WHERE id = ?", (fid,))
    db.commit()
    db.close()
    return redirect(url_for("admin.calendario_admin"))


@bp.route("/calendario/aviso", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_aviso_crear():
    titulo = (request.form.get("titulo") or "").strip()
    cuerpo = (request.form.get("cuerpo") or "").strip()
    fecha_ini = (request.form.get("fecha_ini") or "").strip()[:10]
    fecha_fin = (request.form.get("fecha_fin") or "").strip()[:10]
    db = get_db()
    ensure_calendario_admin_tables(db)
    if titulo and len(fecha_ini) >= 10 and len(fecha_fin) >= 10:
        db.execute(
            f"INSERT INTO {T_AVISOS} (titulo, cuerpo, fecha_ini, fecha_fin) VALUES (?, ?, ?, ?)",
            (titulo, cuerpo or None, fecha_ini, fecha_fin),
        )
        db.commit()
    db.close()
    return redirect(url_for("admin.calendario_admin"))


def __tr_cal(key: str, **kwargs):
    from reservas.i18n import translate as tr

    return tr(f"page.cal_ia.{key}", **kwargs)


@bp.route("/calendario/aviso/<int:aid>/borrar", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_aviso_borrar(aid: int):
    db = get_db()
    ensure_calendario_admin_tables(db)
    db.execute(f"DELETE FROM {T_AVISOS} WHERE id = ?", (aid,))
    db.commit()
    db.close()
    return redirect(url_for("admin.calendario_admin"))


@bp.route("/calendario/carga_preset", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_carga_preset():
    pid = (request.form.get("preset_id") or "").strip().lower()
    year = request.form.get("year", type=int) or date.today().year
    db = get_db()
    ensure_calendario_admin_tables(db)
    n = _insertar_carga_presets(db, [(pid, year)])
    db.close()
    flash(__tr_cal("flash_carga_ok", n=n) if n else __tr_cal("flash_carga_dup"), "success" if n else "info")
    return redirect(url_for("admin.calendario_admin"))


@bp.route("/calendario/carga/<int:cid>/borrar", methods=["POST"])
@login_requerido
@permiso_mod("mod.calendario")
def calendario_carga_borrar(cid: int):
    db = get_db()
    ensure_calendario_admin_tables(db)
    db.execute(f"DELETE FROM {T_CARGA} WHERE id = ?", (cid,))
    db.commit()
    db.close()
    return redirect(url_for("admin.calendario_admin"))
