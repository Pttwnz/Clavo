"""PIN modo tablet (local): acceso restringido a reservas + fichaje."""
from __future__ import annotations

from auth import verificar_pin
from reservas.db_helpers import columnas_tabla


def ensure_tablet_schema(db) -> None:
    """Columna pin_tablet_hash en admin; si está vacía, copia el hash del PIN admin."""
    if not _tabla(db, "admin"):
        return
    cols = columnas_tabla(db, "admin")
    if "pin_tablet_hash" not in cols:
        db.execute("ALTER TABLE admin ADD COLUMN pin_tablet_hash TEXT")
        db.commit()
    row = db.execute("SELECT id, pin_hash, pin_tablet_hash FROM admin ORDER BY id LIMIT 1").fetchone()
    if row and row["pin_hash"] and not (row["pin_tablet_hash"] or "").strip():
        db.execute(
            "UPDATE admin SET pin_tablet_hash = ? WHERE id = ?",
            (row["pin_hash"], row["id"]),
        )
        db.commit()


def _tabla(db, nombre: str) -> bool:
    r = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (nombre,),
    ).fetchone()
    return r is not None


def hash_pin_acceso_tablet(db) -> str | None:
    """Hash usado para entrar en modo tablet (pin_tablet_hash o, si no, pin_hash admin)."""
    row = db.execute("SELECT pin_hash, pin_tablet_hash FROM admin ORDER BY id LIMIT 1").fetchone()
    if not row or not row["pin_hash"]:
        return None
    return (row["pin_tablet_hash"] or row["pin_hash"] or "").strip() or None


def hash_pin_admin(db) -> str | None:
    row = db.execute("SELECT pin_hash FROM admin ORDER BY id LIMIT 1").fetchone()
    return (row["pin_hash"] or "").strip() or None if row else None


def pin_valido_acceso_tablet(db, pin: str) -> bool:
    h = hash_pin_acceso_tablet(db)
    if not h or not pin:
        return False
    return verificar_pin(pin, h)


def pin_valido_admin(db, pin: str) -> bool:
    """Solo el PIN de administrador (autorizar cancelar / eliminar)."""
    h = hash_pin_admin(db)
    if not h or not pin:
        return False
    return verificar_pin(pin, h)
