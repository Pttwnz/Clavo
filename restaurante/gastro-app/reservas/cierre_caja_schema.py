"""Configuración SMTP para cierres de caja e historial de registros."""
from __future__ import annotations

import json
from datetime import datetime, timezone

from reservas.db_helpers import columnas_tabla, tabla_existe

TABLE_CFG = "config_cierre_caja"
TABLE_REG = "cierres_caja_registros"


def ensure_cierre_caja_tables(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_CFG} (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            email_destino TEXT,
            smtp_host TEXT,
            smtp_port INTEGER NOT NULL DEFAULT 587,
            smtp_usuario TEXT,
            smtp_password TEXT,
            smtp_tls INTEGER NOT NULL DEFAULT 1
        )
        """
    )
    db.execute(f"INSERT OR IGNORE INTO {TABLE_CFG} (id) VALUES (1)")
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_REG} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tipo TEXT NOT NULL,
            creado_en TEXT NOT NULL DEFAULT (datetime('now')),
            origen TEXT,
            payload_json TEXT,
            enviado_email INTEGER NOT NULL DEFAULT 0,
            email_error TEXT
        )
        """
    )
    db.commit()
    if tabla_existe(db, TABLE_CFG):
        cols = columnas_tabla(db, TABLE_CFG)
        for name, decl in (
            ("email_destino", "TEXT"),
            ("smtp_host", "TEXT"),
            ("smtp_port", "INTEGER NOT NULL DEFAULT 587"),
            ("smtp_usuario", "TEXT"),
            ("smtp_password", "TEXT"),
            ("smtp_tls", "INTEGER NOT NULL DEFAULT 1"),
        ):
            if name not in cols:
                db.execute(f"ALTER TABLE {TABLE_CFG} ADD COLUMN {name} {decl}")
    db.commit()


def get_config_cierre_caja(db) -> dict:
    ensure_cierre_caja_tables(db)
    row = db.execute(f"SELECT * FROM {TABLE_CFG} WHERE id = 1").fetchone()
    if not row:
        return _defaults_cfg()
    d = dict(row)
    return {
        "email_destino": (d.get("email_destino") or "").strip(),
        "smtp_host": (d.get("smtp_host") or "smtp.gmail.com").strip(),
        "smtp_port": int(d.get("smtp_port") or 587),
        "smtp_usuario": (d.get("smtp_usuario") or "").strip(),
        "smtp_password": (d.get("smtp_password") or "").strip(),
        "smtp_tls": int(d.get("smtp_tls") if d.get("smtp_tls") is not None else 1),
    }


def _defaults_cfg() -> dict:
    return {
        "email_destino": "",
        "smtp_host": "smtp.gmail.com",
        "smtp_port": 587,
        "smtp_usuario": "",
        "smtp_password": "",
        "smtp_tls": 1,
    }


def save_config_cierre_caja(db, form) -> None:
    ensure_cierre_caja_tables(db)
    email_destino = (form.get("email_destino") or "").strip()
    smtp_host = (form.get("smtp_host") or "smtp.gmail.com").strip()
    try:
        smtp_port = int(form.get("smtp_port") or 587)
    except ValueError:
        smtp_port = 587
    smtp_usuario = (form.get("smtp_usuario") or "").strip()
    nuevo_pass = (form.get("smtp_password") or "").strip()
    smtp_tls = 1 if form.get("smtp_tls") else 0

    cur = get_config_cierre_caja(db)
    password = nuevo_pass if nuevo_pass else cur["smtp_password"]

    db.execute(
        f"""
        UPDATE {TABLE_CFG} SET
            email_destino = ?,
            smtp_host = ?,
            smtp_port = ?,
            smtp_usuario = ?,
            smtp_password = ?,
            smtp_tls = ?
        WHERE id = 1
        """,
        (email_destino, smtp_host, smtp_port, smtp_usuario, password, smtp_tls),
    )
    db.commit()


def insert_registro_cierre(
    db,
    *,
    tipo: str,
    origen: str,
    payload: dict,
    enviado: bool,
    email_error: str | None,
) -> int:
    ensure_cierre_caja_tables(db)
    db.execute(
        f"""
        INSERT INTO {TABLE_REG} (tipo, creado_en, origen, payload_json, enviado_email, email_error)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            tipo[:2].upper(),
            datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            origen,
            json.dumps(payload, ensure_ascii=False),
            1 if enviado else 0,
            (email_error or "")[:2000] or None,
        ),
    )
    db.commit()
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def listar_registros_cierre(db, lim: int = 80) -> list[dict]:
    ensure_cierre_caja_tables(db)
    rows = db.execute(
        f"""
        SELECT id, tipo, creado_en, origen, payload_json, enviado_email, email_error
        FROM {TABLE_REG}
        ORDER BY id DESC
        LIMIT ?
        """,
        (lim,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        try:
            d["payload"] = json.loads(d.get("payload_json") or "{}")
        except json.JSONDecodeError:
            d["payload"] = {}
        del d["payload_json"]
        out.append(d)
    return out
