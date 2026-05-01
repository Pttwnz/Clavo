#!/usr/bin/env python3
"""Imprime totales de la tabla reservas (usa DATABASE del entorno / config). Útil en VPS: docker compose exec gastro python3 /app/scripts/db_reservas_count.py"""
from __future__ import annotations

import os
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))

from config import DATABASE  # noqa: E402
import sqlite3  # noqa: E402


def main() -> None:
    p = (DATABASE or "").strip()
    if not p:
        print("DATABASE vacío", file=sys.stderr)
        sys.exit(2)
    c = sqlite3.connect(p)
    c.row_factory = sqlite3.Row
    n = c.execute("SELECT COUNT(1) AS n FROM reservas").fetchone()["n"]
    row = c.execute("SELECT MIN(fecha) AS mn, MAX(fecha) AS mx FROM reservas").fetchone()
    hoy = c.execute("SELECT COUNT(1) AS n FROM reservas WHERE fecha = date('now')").fetchone()["n"]
    c.close()
    print("database:", p)
    print("reservas_total:", int(n))
    print("fecha_min:", row["mn"])
    print("fecha_max:", row["mx"])
    print("reservas_hoy:", int(hoy))


if __name__ == "__main__":
    main()
