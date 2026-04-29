"""Utilidades de introspección SQLite (esquemas evolucionados)."""


def tabla_existe(db, nombre: str) -> bool:
    """Indica si existe una tabla en la base actual."""
    r = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (nombre,),
    ).fetchone()
    return r is not None


def columnas_tabla(db, tabla: str) -> set:
    """Conjunto de nombres de columnas de una tabla."""
    return {r[1] for r in db.execute(f"PRAGMA table_info({tabla})").fetchall()}
