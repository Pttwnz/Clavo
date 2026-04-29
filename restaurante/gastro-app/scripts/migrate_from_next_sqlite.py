"""Migración mínima: Next/Prisma SQLite -> Gastro SQLite (reservas sin fichaje).

Uso:
  python scripts/migrate_from_next_sqlite.py --source "e:/Clavo/restaurante/dev.db"
"""

from __future__ import annotations

import argparse
import math
import sqlite3
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from config import DATABASE
from models import get_db, init_db
from reservas.clientes_schema import ensure_clientes_schema, upsert_cliente_desde_reserva
from reservas.salon_helpers import ensure_salon_tables, get_esquema_activo_id, sync_tabla_mesas_desde_objetos


def _fetchall(src: sqlite3.Connection, sql: str) -> list[sqlite3.Row]:
    return src.execute(sql).fetchall()


def _status_to_gastro(status: str | None) -> str:
    s = (status or "").upper()
    if s == "PENDING":
        return "Pendiente"
    if s in ("CONFIRMED", "SEATED"):
        return "Confirmada"
    if s == "CANCELLED":
        return "Cancelada"
    if s == "COMPLETED":
        return "Completada"
    return "Pendiente"


def _iso_to_date_hour(iso: str | None) -> tuple[str, str]:
    if not iso:
        now = datetime.now()
        return now.strftime("%Y-%m-%d"), now.strftime("%H:%M")
    try:
        d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    except ValueError:
        d = datetime.now()
    return d.strftime("%Y-%m-%d"), d.strftime("%H:%M")


def migrate_tables(src: sqlite3.Connection, dst) -> dict[str, int]:
    ensure_salon_tables(dst)
    eid = get_esquema_activo_id(dst)
    if not eid:
        raise RuntimeError("No se encontró esquema de salón activo en destino.")

    rows = _fetchall(
        src,
        """
        SELECT id, label, zone, capacity, sortOrder, active
        FROM DiningTable
        ORDER BY sortOrder ASC, label ASC
        """,
    )
    created = 0
    for i, r in enumerate(rows):
        if int(r["active"] or 0) != 1:
            continue
        nombre = f"{r['label']}".strip()
        cap = int(r["capacity"] or 4)
        x = 120 + (i % 6) * 120
        y = 140 + math.floor(i / 6) * 110
        tipo = "mesa_redonda" if cap <= 2 else "mesa_cuadrada"
        exists = dst.execute(
            "SELECT 1 FROM objetos_salon WHERE esquema_id = ? AND nombre = ? LIMIT 1",
            (eid, nombre),
        ).fetchone()
        if exists:
            continue
        dst.execute(
            """
            INSERT INTO objetos_salon
              (esquema_id, nombre, tipo, x, y, width, height, rotacion, imagen, capacidad)
            VALUES
              (?, ?, ?, ?, ?, ?, ?, 0, '', ?)
            """,
            (eid, nombre, tipo, float(x), float(y), 96.0, 80.0, cap),
        )
        created += 1
    dst.commit()
    sync_tabla_mesas_desde_objetos(dst)
    dst.commit()
    return {"tables_created": created}


def _build_next_employee_index(src: sqlite3.Connection) -> dict[str, sqlite3.Row]:
    rows = _fetchall(src, "SELECT id, name, email, pinHash, role, active FROM Employee")
    return {str(r["id"]): r for r in rows}


def migrate_employees(src: sqlite3.Connection, dst) -> dict[str, int]:
    rows = _fetchall(
        src,
        "SELECT id, name, email, pinHash, role, active FROM Employee ORDER BY id",
    )
    created = 0
    for r in rows:
        if int(r["active"] or 0) != 1:
            continue
        nombre = (r["name"] or "").strip() or "Empleado"
        dni = (r["email"] or f"legacy-{r['id']}").strip()
        puesto = "Encargado" if (r["role"] or "").upper() == "MANAGER" else "Sala"
        exists = dst.execute("SELECT id FROM empleados WHERE dni = ? LIMIT 1", (dni,)).fetchone()
        if exists:
            dst.execute(
                "UPDATE empleados SET nombre = ?, telefono = ?, puesto = ?, pin_hash = ? WHERE id = ?",
                (nombre, "", puesto, r["pinHash"], exists["id"]),
            )
            continue
        dst.execute(
            "INSERT INTO empleados (nombre, dni, telefono, puesto, pin_hash) VALUES (?, ?, '', ?, ?)",
            (nombre, dni, puesto, r["pinHash"]),
        )
        created += 1

    admin = dst.execute("SELECT id FROM admin ORDER BY id LIMIT 1").fetchone()
    manager = next((x for x in rows if (x["role"] or "").upper() == "MANAGER"), None)
    admin_hash = (manager["pinHash"] if manager else rows[0]["pinHash"]) if rows else None
    if admin_hash:
        if admin:
            dst.execute(
                "UPDATE admin SET pin_hash = COALESCE(pin_hash, ?), pin_tablet_hash = COALESCE(pin_tablet_hash, ?) WHERE id = ?",
                (admin_hash, admin_hash, admin["id"]),
            )
        else:
            dst.execute(
                "INSERT INTO admin (pin_hash, pin_tablet_hash) VALUES (?, ?)",
                (admin_hash, admin_hash),
            )
    dst.commit()
    return {"employees_upserted": len(rows), "employees_created": created}


def migrate_reservations(src: sqlite3.Connection, dst) -> dict[str, int]:
    ensure_clientes_schema(dst)
    rows = _fetchall(
        src,
        """
        SELECT customerName, phone, partySize, startsAt, notes, assignedTable, status, arrivedAt, customerEmail
        FROM Reservation
        ORDER BY startsAt ASC
        """,
    )
    created = 0
    for r in rows:
        fecha, hora = _iso_to_date_hour(r["startsAt"])
        hora_llegada = None
        if r["arrivedAt"]:
            _, hora_llegada = _iso_to_date_hour(r["arrivedAt"])
        nombre = (r["customerName"] or "").strip() or "Cliente"
        telefono = (r["phone"] or "").strip()
        personas = int(r["partySize"] or 1)
        mesa = (r["assignedTable"] or "").strip() or None
        estado = _status_to_gastro(r["status"])
        notas = (r["notes"] or "").strip() or None

        dup = dst.execute(
            """
            SELECT id FROM reservas
            WHERE nombre = ? AND telefono = ? AND fecha = ? AND hora = ?
            LIMIT 1
            """,
            (nombre, telefono, fecha, hora),
        ).fetchone()
        if dup:
            continue

        cur = dst.execute(
            """
            INSERT INTO reservas (nombre, telefono, personas, fecha, hora, notas, mesa, estado, hora_llegada)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (nombre, telefono, personas, fecha, hora, notas, mesa, estado, hora_llegada),
        )
        rid = int(cur.lastrowid)
        cid = upsert_cliente_desde_reserva(
            dst,
            nombre=nombre,
            telefono=telefono,
            fecha_reserva=fecha,
            email=(r["customerEmail"] or "").strip() or None,
            commit=False,
        )
        if cid:
            dst.execute("UPDATE reservas SET cliente_id = ? WHERE id = ?", (cid, rid))
        created += 1
    dst.commit()
    return {"reservations_created": created}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Ruta al dev.db de Next/Prisma")
    args = parser.parse_args()

    src_path = Path(args.source).resolve()
    if not src_path.exists():
        raise SystemExit(f"No existe la base origen: {src_path}")

    print(f"[migrate] source={src_path}")
    print(f"[migrate] target={Path(DATABASE).resolve()}")

    init_db()
    src = sqlite3.connect(str(src_path))
    src.row_factory = sqlite3.Row
    dst = get_db()
    try:
        t = migrate_tables(src, dst)
        e = migrate_employees(src, dst)
        r = migrate_reservations(src, dst)
        print("[migrate] done", {**t, **e, **r})
    finally:
        dst.close()
        src.close()


if __name__ == "__main__":
    main()
