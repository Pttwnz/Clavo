"""Tabla de proveedores (contacto, productos que suministran, condiciones)."""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe

TABLE = "proveedores"


def ensure_proveedores_table(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            persona_contacto TEXT,
            telefono TEXT,
            email TEXT,
            web TEXT,
            direccion TEXT,
            cif TEXT,
            productos TEXT,
            condiciones_compra TEXT,
            dia_habitual_pedido TEXT,
            plazo_entrega TEXT,
            notas TEXT,
            activo INTEGER NOT NULL DEFAULT 1,
            creado_en TEXT DEFAULT (datetime('now')),
            actualizado_en TEXT
        )
        """
    )
    db.commit()
    if not tabla_existe(db, TABLE):
        return
    cols = columnas_tabla(db, TABLE)
    for name, decl in (
        ("persona_contacto", "TEXT"),
        ("web", "TEXT"),
        ("cif", "TEXT"),
        ("productos", "TEXT"),
        ("condiciones_compra", "TEXT"),
        ("dia_habitual_pedido", "TEXT"),
        ("plazo_entrega", "TEXT"),
        ("notas", "TEXT"),
        ("activo", "INTEGER NOT NULL DEFAULT 1"),
        ("creado_en", "TEXT DEFAULT (datetime('now'))"),
        ("actualizado_en", "TEXT"),
    ):
        if name not in cols:
            db.execute(f"ALTER TABLE {TABLE} ADD COLUMN {name} {decl}")
    db.commit()


def listar_proveedores(db, solo_activos: bool = False):
    """Filas ordenadas por nombre."""
    ensure_proveedores_table(db)
    if solo_activos:
        return db.execute(
            f"SELECT * FROM {TABLE} WHERE activo = 1 ORDER BY nombre COLLATE NOCASE"
        ).fetchall()
    return db.execute(f"SELECT * FROM {TABLE} ORDER BY activo DESC, nombre COLLATE NOCASE").fetchall()
