"""Opciones configurables del modo tablet (local)."""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe


def ensure_tablet_config(db) -> None:
    """Tabla de una fila con flags para permisos del modo tablet."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS config_tablet (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            permitir_visualizar_sala INTEGER NOT NULL DEFAULT 0,
            permitir_ver_todas_reservas INTEGER NOT NULL DEFAULT 0,
            permitir_ver_equipo_turno INTEGER NOT NULL DEFAULT 0,
            permitir_cierre_caja INTEGER NOT NULL DEFAULT 0,
            permitir_propinas INTEGER NOT NULL DEFAULT 0,
            permitir_preregistro INTEGER NOT NULL DEFAULT 0,
            propinas_periodo_vista TEXT NOT NULL DEFAULT 'dia',
            propinas_modo_defecto TEXT NOT NULL DEFAULT 'igual',
            propinas_agrupacion TEXT NOT NULL DEFAULT 'dia',
            propinas_franja_horas INTEGER NOT NULL DEFAULT 8,
            propinas_franja_modo TEXT NOT NULL DEFAULT 'auto',
            propinas_franjas_manual_json TEXT,
            mensaje_inicio TEXT
        )
        """
    )
    db.execute("INSERT OR IGNORE INTO config_tablet (id) VALUES (1)")
    db.commit()
    if not tabla_existe(db, "config_tablet"):
        return
    cols = columnas_tabla(db, "config_tablet")
    for name, decl in (
        ("permitir_visualizar_sala", "INTEGER NOT NULL DEFAULT 0"),
        ("permitir_ver_todas_reservas", "INTEGER NOT NULL DEFAULT 0"),
        ("permitir_ver_equipo_turno", "INTEGER NOT NULL DEFAULT 0"),
        ("permitir_cierre_caja", "INTEGER NOT NULL DEFAULT 0"),
        ("mensaje_inicio", "TEXT"),
        ("permitir_propinas", "INTEGER NOT NULL DEFAULT 0"),
        ("propinas_periodo_vista", "TEXT NOT NULL DEFAULT 'dia'"),
        ("propinas_modo_defecto", "TEXT NOT NULL DEFAULT 'igual'"),
        ("propinas_agrupacion", "TEXT NOT NULL DEFAULT 'dia'"),
        ("propinas_franja_horas", "INTEGER NOT NULL DEFAULT 8"),
        ("propinas_franja_modo", "TEXT NOT NULL DEFAULT 'auto'"),
        ("propinas_franjas_manual_json", "TEXT"),
        ("permitir_preregistro", "INTEGER NOT NULL DEFAULT 0"),
    ):
        if name not in cols:
            db.execute(f"ALTER TABLE config_tablet ADD COLUMN {name} {decl}")
    db.commit()


def get_tablet_config(db) -> dict:
    """Devuelve dict con claves permitir_visualizar_sala, permitir_ver_todas_reservas, mensaje_inicio."""
    ensure_tablet_config(db)
    row = db.execute("SELECT * FROM config_tablet WHERE id = 1").fetchone()
    if not row:
        return {
            "permitir_visualizar_sala": 0,
            "permitir_ver_todas_reservas": 0,
            "permitir_ver_equipo_turno": 0,
            "permitir_cierre_caja": 0,
            "permitir_propinas": 0,
            "propinas_periodo_vista": "dia",
            "propinas_modo_defecto": "igual",
            "propinas_agrupacion": "dia",
            "propinas_franja_horas": 8,
            "propinas_franja_modo": "auto",
            "propinas_franjas_manual_json": "",
            "propinas_franjas_manual": [],
            "propinas_franjas_manual_texto": "",
            "permitir_preregistro": 0,
            "mensaje_inicio": "",
        }
    d = dict(row)
    pv = (d.get("propinas_periodo_vista") or "dia").strip().lower()
    if pv not in ("dia", "semana", "mes"):
        pv = "dia"
    md = (d.get("propinas_modo_defecto") or "igual").strip().lower()
    if md not in ("igual", "horas"):
        md = "igual"
    ag = (d.get("propinas_agrupacion") or "dia").strip().lower()
    if ag not in ("dia", "franja"):
        ag = "dia"
    try:
        fh = int(d.get("propinas_franja_horas") or 8)
    except (TypeError, ValueError):
        fh = 8
    if fh not in (4, 6, 8, 12) or (24 % fh != 0):
        fh = 8
    fm = (d.get("propinas_franja_modo") or "auto").strip().lower()
    if fm not in ("auto", "manual"):
        fm = "auto"
    from reservas.propinas_schema import franjas_manual_a_texto, franjas_manual_desde_json

    raw_manual_json = d.get("propinas_franjas_manual_json") or ""
    manual_list = franjas_manual_desde_json(raw_manual_json)
    manual_txt = franjas_manual_a_texto(manual_list) if manual_list else ""
    return {
        "permitir_visualizar_sala": int(d.get("permitir_visualizar_sala") or 0),
        "permitir_ver_todas_reservas": int(d.get("permitir_ver_todas_reservas") or 0),
        "permitir_ver_equipo_turno": int(d.get("permitir_ver_equipo_turno") or 0),
        "permitir_cierre_caja": int(d.get("permitir_cierre_caja") or 0),
        "permitir_propinas": int(d.get("permitir_propinas") or 0),
        "propinas_periodo_vista": pv,
        "propinas_modo_defecto": md,
        "propinas_agrupacion": ag,
        "propinas_franja_horas": fh,
        "propinas_franja_modo": fm,
        "propinas_franjas_manual_json": (raw_manual_json or "").strip(),
        "propinas_franjas_manual": manual_list,
        "propinas_franjas_manual_texto": manual_txt,
        "permitir_preregistro": int(d.get("permitir_preregistro") or 0),
        "mensaje_inicio": (d.get("mensaje_inicio") or "").strip(),
    }


def tablet_endpoints_extra(db) -> frozenset:
    """Endpoints extra permitidos en sesión tablet según configuración."""
    ensure_tablet_config(db)
    cfg = get_tablet_config(db)
    extra = []
    if cfg.get("permitir_visualizar_sala"):
        extra.extend(["public.visualizar", "public.api_sala_vivo"])
    if cfg.get("permitir_ver_equipo_turno"):
        extra.append("public.tablet_equipo_hoy")
    if cfg.get("permitir_propinas"):
        extra.extend(
            [
                "public.tablet_propinas",
                "public.tablet_propinas_estadisticas",
                "public.tablet_propinas_config",
                "public.tablet_propinas_eliminar_reparto",
            ]
        )
    if cfg.get("permitir_preregistro"):
        extra.extend(
            [
                "public.tablet_preregistro",
            ]
        )
    return frozenset(extra)
