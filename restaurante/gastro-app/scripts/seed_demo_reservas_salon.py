#!/usr/bin/env python3
"""Rellena reservas de demostración para Sala en vivo (marcadas en notas con [DEMO_SALON]).

Uso típico (desde la raíz del proyecto, con el venv activado):
  python scripts/seed_demo_reservas_salon.py --fecha 2026-04-28
  python scripts/seed_demo_reservas_salon.py --pct 0.6
  python scripts/seed_demo_reservas_salon.py --limpiar-todo   # borra todas las demo
"""
from __future__ import annotations

import argparse
import math
import os
import random
import sys
from datetime import date, datetime, timedelta

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT)

from config import DATABASE  # noqa: E402
from models import get_db  # noqa: E402
from reservas.clientes_schema import ensure_clientes_schema  # noqa: E402
from reservas.sala_vivo import normalizar_fecha_param, variantes_fecha_sql  # noqa: E402
from reservas.salon_helpers import ensure_salon_tables, list_objetos_mesas_esquema_activo  # noqa: E402

MARKER = "[DEMO_SALON]"

# Reparto de horas por pestaña de /visualizar (mañana / mediodía / noche).
HORAS_DEMO = (
    "09:15",
    "10:30",
    "12:00",
    "13:30",
    "14:15",
    "16:45",
    "20:00",
    "20:45",
    "21:30",
    "22:15",
)

NOMBRES_DEMO = (
    "Familia García (demo)",
    "Cena empresa Norte SL",
    "Aniversario — demo",
    "Grupo amigos 7ª",
    "Reserva prueba sin confirmar",
    "Clientes habituales (demo)",
    "Cumpleaños Laura",
    "Despedida — demo",
    "Turistas — prueba UI",
    "Vecinos mesa larga",
)


def _notas_demo(extra: str) -> str:
    base = f"{MARKER} Datos ficticios para vista previa."
    if extra:
        return f"{base} {extra}"
    return base


def _limpiar_por_fechas(db, fechas_variantes: list[str]) -> int:
    ph = ",".join("?" * len(fechas_variantes))
    cur = db.execute(
        f"DELETE FROM reservas WHERE notas LIKE ? AND fecha IN ({ph})",
        (f"%{MARKER}%", *fechas_variantes),
    )
    return cur.rowcount if cur.rowcount is not None else 0


def _limpiar_todas(db) -> int:
    cur = db.execute("DELETE FROM reservas WHERE notas LIKE ?", (f"%{MARKER}%",))
    return cur.rowcount if cur.rowcount is not None else 0


def _insert_reserva(
    db,
    *,
    nombre: str,
    telefono: str,
    personas: int,
    fecha: str,
    hora: str,
    notas: str,
    mesa: str,
    estado: str,
    hora_llegada: str | None,
) -> None:
    db.execute(
        """
        INSERT INTO reservas
        (nombre, telefono, personas, fecha, hora, notas, mesa, estado, hora_llegada)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (nombre, telefono, personas, fecha, hora, notas, mesa, estado, hora_llegada),
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Sembrar reservas demo para el plano (Sala en vivo).")
    ap.add_argument("--fecha", default="", help="YYYY-MM-DD (por defecto: hoy)")
    ap.add_argument("--pct", type=float, default=0.6, help="Fracción de mesas del plano activo (0–1).")
    ap.add_argument(
        "--limpiar-todo",
        action="store_true",
        help="Borra todas las reservas con marca demo y termina.",
    )
    ap.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Semilla aleatoria (reproducible).",
    )
    args = ap.parse_args()

    fecha_iso = normalizar_fecha_param(args.fecha or None)
    pct = max(0.0, min(1.0, float(args.pct)))

    print(f"Base de datos: {DATABASE}")

    db = get_db()
    ensure_salon_tables(db)
    ensure_clientes_schema(db)

    if args.limpiar_todo:
        n = _limpiar_todas(db)
        db.commit()
        print(f"Eliminadas {n} reservas con {MARKER}.")
        return

    if args.seed is not None:
        random.seed(args.seed)

    mesas_rows = list_objetos_mesas_esquema_activo(db)
    if not mesas_rows:
        db.close()
        print("No hay mesas en el esquema activo. Crea un plano o activa un esquema.")
        sys.exit(1)

    n_mesas = len(mesas_rows)
    k = max(1, int(math.ceil(n_mesas * pct)))
    k = min(k, n_mesas)

    vars_f = variantes_fecha_sql(fecha_iso)
    borradas = _limpiar_por_fechas(db, vars_f)
    if borradas:
        print(f"Eliminadas {borradas} reservas demo previas para {fecha_iso}.")

    mesas_shuf = [((m["nombre"] or "").strip(), int(m["capacidad"] or 4)) for m in mesas_rows]
    random.shuffle(mesas_shuf)
    elegidas = mesas_shuf[:k]

    estados_ciclo = ("Pendiente", "Confirmada", "Llegó", "Confirmada", "Pendiente")
    insertadas = 0

    for i, (mesa_nombre, cap) in enumerate(elegidas):
        if not mesa_nombre:
            continue
        hora = HORAS_DEMO[i % len(HORAS_DEMO)]
        estado = estados_ciclo[i % len(estados_ciclo)]
        tel = f"600{1000000 + (i * 17) % 8999999:07d}"
        nombre = NOMBRES_DEMO[i % len(NOMBRES_DEMO)]
        personas = min(cap, 2 + (i % 5))
        extra_notas = ""
        hora_llegada: str | None = None

        if estado == "Llegó":
            try:
                d = date.fromisoformat(fecha_iso[:10])
                hh, mm = map(int, hora.split(":"))
                llegada = datetime(d.year, d.month, d.day, hh, mm) + timedelta(minutes=12)
                hora_llegada = llegada.isoformat(timespec="seconds")
            except (ValueError, TypeError):
                hora_llegada = None

        # Algunos “problemas” de día cargado: más pax que capacidad, o nota de retraso.
        if i % 11 == 0:
            personas = cap + 4
            extra_notas = "Posible sobrecupo (demo). Revisar distribución."
        elif i % 13 == 0:
            extra_notas = "Llegada habitualmente tarde — vigilar turno (demo)."

        _insert_reserva(
            db,
            nombre=nombre,
            telefono=tel,
            personas=personas,
            fecha=fecha_iso,
            hora=hora,
            notas=_notas_demo(extra_notas),
            mesa=mesa_nombre,
            estado=estado,
            hora_llegada=hora_llegada,
        )
        insertadas += 1

    # Doble reserva misma mesa / mismo día (lista muestra ambas; el mapa deja la última por hora).
    if k >= 3:
        m0, cap0 = elegidas[0]
        h1, h2 = "20:00", "21:45"
        _insert_reserva(
            db,
            nombre="Conflicto agenda (demo)",
            telefono="6009999001",
            personas=min(4, cap0),
            fecha=fecha_iso,
            hora=h1,
            notas=_notas_demo("Misma mesa que otra reserva noche — revisar (demo)."),
            mesa=m0,
            estado="Confirmada",
            hora_llegada=None,
        )
        _insert_reserva(
            db,
            nombre="Reserva duplicada B (demo)",
            telefono="6009999002",
            personas=min(3, cap0),
            fecha=fecha_iso,
            hora=h2,
            notas=_notas_demo("Segunda reserva misma mesa — error operativo (demo)."),
            mesa=m0,
            estado="Confirmada",
            hora_llegada=None,
        )
        insertadas += 2

    # Una finalizada: aparece en lista del día pero no ocupa mesa en el mapa.
    if k >= 2:
        m1, cap1 = elegidas[1]
        _insert_reserva(
            db,
            nombre="Ya terminaron (demo)",
            telefono="6008888001",
            personas=min(2, cap1),
            fecha=fecha_iso,
            hora="14:00",
            notas=_notas_demo("Estado Finalizada — mesa libre en mapa (demo)."),
            mesa=m1,
            estado="Finalizada",
            hora_llegada=None,
        )
        insertadas += 1

    db.commit()
    db.close()
    print(
        f"Listo: {insertadas} reservas demo en {fecha_iso} "
        f"(~{pct:.0%} de {n_mesas} mesas del plano + escenarios extra). "
        f"Borrar todas: python scripts/seed_demo_reservas_salon.py --limpiar-todo"
    )


if __name__ == "__main__":
    main()
