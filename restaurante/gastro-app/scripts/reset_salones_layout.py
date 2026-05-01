#!/usr/bin/env python3
"""Reset del plano de salón (SQLite Gastro): borra salones/esquemas/objetos y crea mesas de prueba.

Capacidades: el sufijo «px» del usuario = comensales (pax), no píxeles.

Mesas creadas (orden visual en grilla ~5 columnas):
  m1–m6 (sin m4), b1–b2, m7–m10, alma, cen, p1–p2, cafe, t1–t7 (todas t* a 4 pax).

Pruebas manuales sugeridas (web + panel + tablet):
  1) Web: reserva 2 pax → mesa 2p; 4 pax → solo mesas ≥4; 6 pax → alma/cen.
  2) Web: franja llena → mensaje claro / siguiente franja.
  3) Panel: crear reserva manual misma mesa/hora → conflicto o aviso según reglas.
  4) Panel: editar reserva (personas, mesa, hora) y guardar; refrescar sala en vivo.
  5) Cancelar en web y comprobar que libera en Gastro el mismo día.
  6) Walk-in / tablet: ocupar mesa sin reserva previa si aplica.
  7) Unión de mesas (si activáis uniones): capacidad sumada vs sugerencias.

Ejecución (desde máquina con la BD Gastro, p. ej. contenedor o repo local):
  python3 scripts/reset_salones_layout.py

En Docker (VPS): ``docker compose exec gastro python3 /app/scripts/reset_salones_layout.py``
"""
from __future__ import annotations

import os
import sys

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

    db.execute("INSERT INTO salones (nombre) VALUES ('Local prueba')")
    sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    db.execute(
        """
        INSERT INTO esquemas (salon_id, nombre, activo)
        VALUES (?, 'Plano prueba reservas', 1)
        """,
        (sid,),
    )
    eid = db.execute("SELECT last_insert_rowid()").fetchone()[0]

    gx, gy = 130.0, 118.0
    ox, oy = 48.0, 56.0

    # (nombre, capacidad_pax, col, row) — grilla 5 columnas
    plano: list[tuple[str, int, int, int]] = [
        # Fila 0 — sala m
        ("m1", 2, 0, 0),
        ("m2", 2, 1, 0),
        ("m3", 4, 2, 0),
        ("m5", 4, 3, 0),
        ("m6", 2, 4, 0),
        # Fila 1 — bar + m
        ("b1", 2, 0, 1),
        ("b2", 2, 1, 1),
        ("m7", 2, 2, 1),
        ("m8", 4, 3, 1),
        ("m9", 2, 4, 1),
        # Fila 2
        ("m10", 4, 0, 2),
        ("alma", 6, 1, 2),
        ("cen", 6, 2, 2),
        ("p1", 3, 3, 2),
        ("p2", 3, 4, 2),
        # Fila 3 — cafetería + terraza t1–t4
        ("cafe", 4, 0, 3),
        ("t1", 4, 1, 3),
        ("t2", 4, 2, 3),
        ("t3", 4, 3, 3),
        ("t4", 4, 4, 3),
        # Fila 4 — t5–t7
        ("t5", 4, 0, 4),
        ("t6", 4, 1, 4),
        ("t7", 4, 2, 4),
    ]

    for nombre, cap, col, row in plano:
        ins(db, eid, nombre, cap, ox + float(col) * gx, oy + float(row) * gy)

    db.commit()
    db.close()

    db2 = sqlite3.connect(DATABASE)
    db2.row_factory = sqlite3.Row
    ensure_salon_tables(db2)
    sync_tabla_mesas_desde_objetos(db2)
    db2.commit()
    db2.close()
    print(f"OK: plano de prueba con {len(plano)} mesas, tabla mesas sincronizada.")


if __name__ == "__main__":
    main()
