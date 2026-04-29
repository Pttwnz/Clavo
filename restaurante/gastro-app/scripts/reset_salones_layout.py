#!/usr/bin/env python3
"""Un uso: borra salones/esquemas/objetos y crea el plano pedido (pax = 'px' del usuario)."""
from __future__ import annotations

import os
import sys

# Raíz del proyecto
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from config import DATABASE  # noqa: E402
from reservas.salon_helpers import ensure_salon_tables, sync_tabla_mesas_desde_objetos  # noqa: E402


def tipo_tamano(cap: int) -> tuple[str, float, float]:
    if cap <= 2:
        return "mesa_cuadrada", 80.0, 64.0
    if cap == 3:
        return "mesa_redonda", 88.0, 88.0
    if cap == 4:
        return "mesa_cuadrada", 96.0, 80.0
    if cap == 6:
        return "mesa_cuadrada", 112.0, 92.0
    return "mesa_cuadrada", 96.0, 80.0


def ins(
    db,
    eid: int,
    nombre: str,
    cap: int,
    x: float,
    y: float,
) -> None:
    tipo, w, h = tipo_tamano(cap)
    db.execute(
        """
        INSERT INTO objetos_salon
        (esquema_id, nombre, tipo, x, y, width, height, rotacion, imagen, capacidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, '', ?)
        """,
        (eid, nombre, tipo, float(x), float(y), w, h, cap),
    )


def main() -> None:
    import sqlite3

    db = sqlite3.connect(DATABASE)
    db.row_factory = sqlite3.Row
    ensure_salon_tables(db)

    db.execute("DELETE FROM mesa_uniones")
    db.execute("DELETE FROM objetos_salon")
    db.execute("DELETE FROM esquemas")
    db.execute("DELETE FROM salones")
    db.execute("DELETE FROM mesas")

    db.execute("INSERT INTO salones (nombre) VALUES ('Local')")
    sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        """
        INSERT INTO esquemas (salon_id, nombre, activo)
        VALUES (?, 'Salón + terraza', 1)
        """,
        (sid,),
    )
    eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    gx, gy = 130.0, 118.0
    ox, oy = 48.0, 56.0

    # --- Salón (zona izquierda) ---
    salon: list[tuple[str, int, int, int]] = [
        ("m1", 2, 0, 0),
        ("m2", 2, 1, 0),
        ("m3", 4, 2, 0),
        ("m5", 4, 3, 0),
        ("m6", 2, 0, 1),
        ("m7", 2, 1, 1),
        ("m8", 4, 2, 1),
        ("m9", 2, 3, 1),
        ("m10", 4, 4, 1),
        ("m11", 2, 0, 2),
        ("almna", 6, 1, 2),
        ("cen", 6, 3, 2),
    ]
    for nombre, cap, col, row in salon:
        ins(db, eid, nombre, cap, ox + float(col) * gx, oy + float(row) * gy)

    # --- Terraza (zona derecha, desplazada en X) ---
    tx0 = ox + 6.5 * gx
    terraza: list[tuple[str, int, int, int]] = [
        ("x1", 3, 0, 0),
        ("p1", 3, 1, 0),
        ("p3", 3, 2, 0),
    ]
    for nombre, cap, col, row in terraza:
        ins(db, eid, nombre, cap, tx0 + float(col) * gx, oy + float(row) * gy)

    for i in range(7):
        col = i % 4
        row = 1 + (i // 4)
        ins(db, eid, f"t{i + 1}", 4, tx0 + float(col) * gx, oy + float(row) * gy)

    db.commit()
    db.close()

    db2 = sqlite3.connect(DATABASE)
    db2.row_factory = sqlite3.Row
    ensure_salon_tables(db2)
    sync_tabla_mesas_desde_objetos(db2)
    db2.commit()
    db2.close()
    print("OK: 1 salón, 1 esquema activo, mesas sincronizadas a tabla mesas.")


if __name__ == "__main__":
    main()
