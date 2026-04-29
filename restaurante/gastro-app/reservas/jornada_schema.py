"""Esquema y acceso a conformidades del registro de jornada (art. 34.9 ET)."""
from __future__ import annotations

from reservas.db_helpers import tabla_existe

TABLE = "conformidades_jornada"


def ensure_jornada_tables(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS conformidades_jornada (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado_id INTEGER NOT NULL,
            mes_ref TEXT NOT NULL,
            texto_legal TEXT,
            ip TEXT,
            user_agent TEXT,
            firma_relativa TEXT,
            creado_en TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(empleado_id, mes_ref)
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_conf_mes ON conformidades_jornada (mes_ref)"
    )
    db.commit()


def get_conformidad_mes(db, empleado_id: int, mes_ref: str) -> dict | None:
    if not tabla_existe(db, TABLE):
        return None
    row = db.execute(
        f"SELECT * FROM {TABLE} WHERE empleado_id = ? AND mes_ref = ?",
        (empleado_id, mes_ref),
    ).fetchone()
    return dict(row) if row else None


def upsert_conformidad(
    db,
    empleado_id: int,
    mes_ref: str,
    texto_legal: str,
    ip: str | None,
    user_agent: str | None,
    firma_relativa: str | None,
) -> None:
    ensure_jornada_tables(db)
    db.execute(
        f"""
        INSERT INTO {TABLE}
        (empleado_id, mes_ref, texto_legal, ip, user_agent, firma_relativa, creado_en)
        VALUES (?, ?, ?, ?, ?, ?, datetime('now'))
        ON CONFLICT(empleado_id, mes_ref) DO UPDATE SET
            texto_legal = excluded.texto_legal,
            ip = excluded.ip,
            user_agent = excluded.user_agent,
            firma_relativa = COALESCE(excluded.firma_relativa, conformidades_jornada.firma_relativa),
            creado_en = datetime('now')
        """,
        (empleado_id, mes_ref, texto_legal, ip or "", user_agent or "", firma_relativa),
    )
    db.commit()
