"""Esquema de inventario, movimientos y albaranes (entradas de mercancía)."""
from __future__ import annotations

import os
import re
from datetime import datetime

from werkzeug.utils import secure_filename

from reservas.db_helpers import columnas_tabla

MAX_ALBARAN_BYTES = 8 * 1024 * 1024
ALBARAN_DIR = "uploads/albaranes"
ALLOWED_ALBARAN = frozenset({".pdf", ".png", ".jpg", ".jpeg", ".webp"})


def ensure_stock_schema(db) -> None:
    """Columnas de stock en ingredientes + tablas de movimientos y albaranes."""
    if not _tabla(db, "ingredientes"):
        return
    cols = columnas_tabla(db, "ingredientes")
    for name, decl in (
        ("stock_actual", "REAL DEFAULT 0"),
        ("stock_minimo", "REAL DEFAULT 0"),
        ("stock_maximo", "REAL"),
    ):
        if name not in cols:
            db.execute(f"ALTER TABLE ingredientes ADD COLUMN {name} {decl}")
    db.commit()

    db.execute(
        """
        CREATE TABLE IF NOT EXISTS movimientos_stock (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ingrediente_id INTEGER NOT NULL,
            tipo TEXT NOT NULL,
            cantidad REAL NOT NULL,
            notas TEXT,
            ref_tabla TEXT,
            ref_id INTEGER,
            creado_en TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (ingrediente_id) REFERENCES ingredientes(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS albaranes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            proveedor TEXT,
            numero_documento TEXT,
            fecha TEXT,
            archivo_relativo TEXT,
            estado TEXT NOT NULL DEFAULT 'borrador',
            notas TEXT,
            creado_en TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS albaran_lineas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            albaran_id INTEGER NOT NULL,
            ingrediente_id INTEGER NOT NULL,
            cantidad REAL NOT NULL,
            precio_unitario REAL,
            FOREIGN KEY (albaran_id) REFERENCES albaranes(id) ON DELETE CASCADE,
            FOREIGN KEY (ingrediente_id) REFERENCES ingredientes(id)
        )
        """
    )
    db.execute("CREATE INDEX IF NOT EXISTS idx_mov_ing ON movimientos_stock (ingrediente_id)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_mov_creado ON movimientos_stock (creado_en)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_albaran_estado ON albaranes (estado)")
    db.commit()


def _tabla(db, nombre: str) -> bool:
    r = db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (nombre,),
    ).fetchone()
    return r is not None


def registrar_movimiento(
    db,
    ingrediente_id: int,
    cantidad_signed: float,
    tipo: str,
    notas: str | None = None,
    ref_tabla: str | None = None,
    ref_id: int | None = None,
) -> None:
    """Actualiza stock_actual y registra fila en movimientos_stock."""
    db.execute(
        """
        UPDATE ingredientes
        SET stock_actual = COALESCE(stock_actual, 0) + ?
        WHERE id = ?
        """,
        (cantidad_signed, ingrediente_id),
    )
    db.execute(
        """
        INSERT INTO movimientos_stock (ingrediente_id, tipo, cantidad, notas, ref_tabla, ref_id)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            ingrediente_id,
            tipo,
            cantidad_signed,
            (notas or "").strip() or None,
            ref_tabla,
            ref_id,
        ),
    )


def ingredientes_bajo_minimo(db):
    """Ingredientes con stock_actual < stock_minimo (si mínimo > 0)."""
    return db.execute(
        """
        SELECT id, nombre, unidad, COALESCE(stock_actual, 0) AS sa, COALESCE(stock_minimo, 0) AS sm
        FROM ingredientes
        WHERE COALESCE(stock_minimo, 0) > 0
          AND COALESCE(stock_actual, 0) < COALESCE(stock_minimo, 0)
        ORDER BY nombre COLLATE NOCASE
        """
    ).fetchall()


def contar_alertas_stock(db) -> int:
    r = db.execute(
        """
        SELECT COUNT(*) FROM ingredientes
        WHERE COALESCE(stock_minimo, 0) > 0
          AND COALESCE(stock_actual, 0) < COALESCE(stock_minimo, 0)
        """
    ).fetchone()
    return int(r[0]) if r else 0


def guardar_archivo_albaran(static_root: str, file_storage) -> str | None:
    if not static_root or not file_storage or not getattr(file_storage, "filename", None):
        return None
    raw = secure_filename(str(file_storage.filename))
    if not raw:
        return None
    ext = os.path.splitext(raw)[1].lower()
    if ext not in ALLOWED_ALBARAN:
        return None
    data = file_storage.read()
    if not data or len(data) > MAX_ALBARAN_BYTES:
        return None
    dest_dir = os.path.join(static_root, *ALBARAN_DIR.split("/"))
    os.makedirs(dest_dir, exist_ok=True)
    safe = re.sub(r"[^\w.\-]", "_", os.path.splitext(raw)[0])[:60]
    new_name = f"{safe}_{datetime.now().strftime('%Y%m%d_%H%M%S')}{ext}"
    full = os.path.join(dest_dir, new_name)
    with open(full, "wb") as f:
        f.write(data)
    return f"{ALBARAN_DIR}/{new_name}".replace("\\", "/")


def confirmar_albaran(db, albaran_id: int) -> tuple[bool, str]:
    """Pasa albarán a confirmado y registra entradas de stock."""
    alb = db.execute("SELECT * FROM albaranes WHERE id = ?", (albaran_id,)).fetchone()
    if not alb:
        return False, "Albarán no encontrado."
    if dict(alb).get("estado") == "confirmado":
        return False, "Este albarán ya estaba confirmado."

    lineas = db.execute(
        "SELECT * FROM albaran_lineas WHERE albaran_id = ?",
        (albaran_id,),
    ).fetchall()
    if not lineas:
        return False, "Añade al menos una línea antes de confirmar."

    for ln in lineas:
        d = dict(ln)
        cant = float(d["cantidad"])
        if cant <= 0:
            continue
        registrar_movimiento(
            db,
            int(d["ingrediente_id"]),
            cant,
            "entrada_albaran",
            notas=f"Albarán #{albaran_id}",
            ref_tabla="albaranes",
            ref_id=albaran_id,
        )

    db.execute(
        "UPDATE albaranes SET estado = 'confirmado' WHERE id = ?",
        (albaran_id,),
    )
    db.commit()
    return True, ""
