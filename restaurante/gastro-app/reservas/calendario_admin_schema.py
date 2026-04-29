"""Tablas para festivos locales y avisos en el calendario de administración."""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe

T_FESTIVOS = "calendario_festivos"
T_AVISOS = "calendario_avisos"
T_CARGA = "calendario_carga_laboral"


def ensure_calendario_admin_tables(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_FESTIVOS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            fecha TEXT NOT NULL,
            titulo TEXT NOT NULL,
            notas TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_cal_fest_fecha ON {T_FESTIVOS} (fecha)"
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_AVISOS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            cuerpo TEXT,
            fecha_ini TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            creado_en TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_cal_avisos_ini ON {T_AVISOS} (fecha_ini)"
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_CARGA} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            fecha_ini TEXT NOT NULL,
            fecha_fin TEXT NOT NULL,
            ubicacion TEXT,
            notas TEXT,
            preset_id TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_cal_carga_ini ON {T_CARGA} (fecha_ini)"
    )
    if tabla_existe(db, T_AVISOS):
        cols = columnas_tabla(db, T_AVISOS)
        if "categoria" not in cols:
            db.execute(f"ALTER TABLE {T_AVISOS} ADD COLUMN categoria TEXT")
    db.commit()
