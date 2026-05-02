#!/usr/bin/env python3
"""
E2E real (misma lógica que producción): reserva web vía POST /api/web/reservas
y alta rápida de panel vía POST /api/reserva_rapida (como la app / sala).

Comprueba:
  - Web: duplicado mismo teléfono + fecha + hora → 409.
  - Panel: mismo teléfono + fecha + hora que reserva web activa → 409 (alineado con la web).
  - Panel: dos reservas misma mesa y hora → 409 mesa_ocupada.

Prueba HTTPS contra el despliegue (elclavo.gastromanager.es, sin Docker):
  python3 scripts/e2e_reservas_remote_http.py --allow-remote-writes

Uso en contenedor (BD real de Gastro):
  python3 /app/scripts/e2e_reservas_web_y_panel.py --accept-production

BD local o simulación:
  python3 scripts/e2e_reservas_web_y_panel.py --db /tmp/e2e.sqlite --fresh

Requiere --accept-production si DATABASE resuelve bajo .../data/... (p. ej. /data/gastro.db).
Al final borra filas con nombre LIKE 'E2E-CLAVO-%' salvo --no-cleanup.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, datetime, timedelta
from pathlib import Path


NAME_PREFIX = "E2E-CLAVO-"


def _log(title: str, detail: str = "") -> None:
    print(f"\n=== {title} ===")
    if detail:
        print(detail.rstrip())


def _bootstrap_isolated(root: Path, db_path: Path) -> None:
    from models import get_db, init_db
    from reservas.salon_helpers import (
        ensure_salon_tables,
        get_esquema_activo_id,
        seed_salon_if_empty,
        sync_tabla_mesas_desde_objetos,
    )
    from reservas.web_reservas_schema import ensure_web_reservas_tables

    init_db()
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    ensure_web_reservas_tables(db)

    eid = get_esquema_activo_id(db)
    if not eid:
        raise SystemExit("Bootstrap: sin esquema de salón activo tras seed.")

    db.execute("DELETE FROM mesa_uniones")
    db.execute("DELETE FROM objetos_salon WHERE esquema_id = ?", (eid,))
    gx, gy = 90.0, 80.0
    ox, oy = 40.0, 40.0
    for i in range(8):
        col, row = i % 4, i // 4
        db.execute(
            """
            INSERT INTO objetos_salon
            (esquema_id, nombre, tipo, x, y, width, height, rotacion, imagen, capacidad)
            VALUES (?, ?, 'mesa_cuadrada', ?, ?, 88, 72, 0, '', 4)
            """,
            (eid, f"M{i+1}", ox + col * gx, oy + row * gy),
        )
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()

    db = get_db()
    db.execute(
        """
        UPDATE web_reserva_config SET
            activo = 1,
            min_personas = 1,
            max_personas = 12,
            anticipacion_minutos = 0,
            max_dias_antelacion = 60,
            intervalo_minutos = 30,
            pct_web_defecto = 100,
            requiere_email = 0,
            confirmacion_horas = 168,
            public_base_url = 'http://127.0.0.1:59999'
        WHERE id = 1
        """
    )
    db.execute("UPDATE web_franja SET pct_web = 100 WHERE activo = 1")
    db.execute("DELETE FROM reservas")
    db.commit()
    db.close()


def _admin_session(c) -> None:
    with c.session_transaction() as s:
        s["admin_logueado"] = True
        s["rol"] = "admin"


def _norm_db_path() -> str:
    raw = (os.environ.get("DATABASE") or "").strip() or "database.db"
    return str(Path(raw).resolve())


def _requires_production_guard(db_abs: str) -> bool:
    p = db_abs.replace("\\", "/").lower()
    return "/data/" in p


def _find_web_slot(c, tomorrow: date) -> tuple[str, str, str] | None:
    """Devuelve (fecha_iso, starts_iso_madrid, hora_hhmm) usando disponibilidad (sin crear filas)."""
    from reservas.utils import ahora_madrid

    fecha = tomorrow.isoformat()
    r = c.get(f"/api/web/reservas/disponibilidad?fecha={fecha}&personas=2")
    j = r.get_json(silent=True) or {}
    slots = j.get("slots") if isinstance(j, dict) else None
    if not isinstance(slots, list) or not j.get("ok"):
        return None

    now_m = ahora_madrid()
    tz = now_m.tzinfo
    for s in slots:
        if not isinstance(s, dict) or not s.get("disponible"):
            continue
        hhmm = (s.get("hora") or "").strip()
        if len(hhmm) < 4 or ":" not in hhmm:
            continue
        h, m = hhmm.split(":", 1)[:2]
        try:
            t = datetime.strptime(f"{int(h):02d}:{int(m):02d}", "%H:%M").time()
        except (TypeError, ValueError):
            continue
        if tz:
            starts_at = datetime.combine(tomorrow, t, tzinfo=tz)
        else:
            starts_at = datetime.combine(tomorrow, t)
        return fecha, starts_at.isoformat(), hhmm
    return None


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=None, help="SQLite (por defecto: env DATABASE)")
    ap.add_argument("--fresh", action="store_true", help="Con --db: borrar fichero y bootstrap mínimo")
    ap.add_argument(
        "--accept-production",
        action="store_true",
        help="Obligatorio si la BD está bajo /data/ (p. ej. Docker producción).",
    )
    ap.add_argument(
        "--no-cleanup",
        action="store_true",
        help="No borrar al final las reservas con nombre E2E-CLAVO-*.",
    )
    args = ap.parse_args()

    if args.db:
        db_path = args.db.resolve()
        if args.fresh and db_path.exists():
            db_path.unlink()
        os.environ["DATABASE"] = str(db_path)

    sys.path.insert(0, str(root))

    db_abs = _norm_db_path()
    if _requires_production_guard(db_abs) and not args.accept_production:
        print(
            "Refusing: DATABASE parece producción (/data/...). "
            "Pasa --accept-production si es intencionado.",
            file=sys.stderr,
        )
        return 2

    if args.db and args.fresh:
        _bootstrap_isolated(root, args.db)

    from models import get_db
    from reservas import create_app
    from reservas.salon_helpers import list_objetos_mesas_esquema_activo
    from reservas.web_reservas_logic import normalizar_telefono

    findings: list[str] = []

    def cleanup() -> None:
        if args.no_cleanup:
            return
        db = get_db()
        cur = db.execute("DELETE FROM reservas WHERE nombre LIKE ?", (NAME_PREFIX + "%",))
        db.commit()
        n = cur.rowcount if cur else 0
        db.close()
        _log("Limpieza", f"DELETE reservas nombre LIKE '{NAME_PREFIX}%': {n} filas.")

    try:
        app = create_app()
        app.config["TESTING"] = True
        c = app.test_client()

        tomorrow = date.today() + timedelta(days=1)

        slot = _find_web_slot(c, tomorrow)
        if not slot:
            _log(
                "ERROR",
                "No hay slot web disponible mañana (activo/cupo/franja/antelación o sin huecos). "
                "Revisa web_reserva_config y web_franja.",
            )
            return 1
        fecha, starts_iso, hora_web = slot
        _log("Slot web", f"fecha={fecha} hora={hora_web} startsAt={starts_iso}")

        ro = c.get(f"/api/web/reservas/opciones-mesa?fecha={fecha}&hora={hora_web}&personas=2")
        jo = ro.get_json(silent=True) or {}
        opc = jo.get("opciones") if isinstance(jo, dict) else None
        if not isinstance(opc, list) or not opc:
            _log("ERROR", f"Sin opciones de mesa para web (HTTP {ro.status_code}): {jo!r}")
            return 1
        mesa_web = (opc[0].get("mesa") or "").strip()
        if not mesa_web:
            _log("ERROR", "Primera opción de mesa sin nombre.")
            return 1

        run_id = int(time.time()) % 1_000_000
        phone_raw = f"+34900077{run_id:06d}"
        phone_digits = normalizar_telefono(phone_raw)

        # --- 1) Web primera
        body_web = {
            "customerName": f"{NAME_PREFIX}web-1",
            "phone": phone_raw,
            "partySize": 2,
            "startsAt": starts_iso,
            "customerEmail": f"e2e{run_id}@example.invalid",
            "mesa": mesa_web,
        }
        r1 = c.post("/api/web/reservas", json=body_web, content_type="application/json")
        j1 = r1.get_json(silent=True) or {}
        _log("1. Web POST primera", f"HTTP {r1.status_code}\n{json.dumps(j1, ensure_ascii=False)[:800]}")
        if r1.status_code != 201:
            findings.append("Fallo crítico: primera reserva web no devolvió 201.")
            return 1

        # --- 2) Web duplicado mismo tel
        r2 = c.post("/api/web/reservas", json=body_web, content_type="application/json")
        j2 = r2.get_json(silent=True) or {}
        _log("2. Web POST duplicado (mismo tel/fecha/hora)", f"HTTP {r2.status_code}\n{j2.get('error') or j2}")
        if r2.status_code != 409:
            findings.append(
                f"Fallo crítico: duplicado web esperaba 409, obtuvo {r2.status_code}."
            )

        # --- 3) Panel rápido mismo tel/fecha/hora (sin mesa)
        _admin_session(c)
        body_panel_dup = {
            "fecha": fecha,
            "hora": hora_web,
            "nombre": f"{NAME_PREFIX}panel-mismo-tel",
            "telefono": phone_digits,
            "personas": 2,
            "mesa": mesa_web,
        }
        r3 = c.post("/api/reserva_rapida", json=body_panel_dup, content_type="application/json")
        j3 = r3.get_json(silent=True) or {}
        _log(
            "3. Panel POST /api/reserva_rapida (mismo tel/fecha/hora que web, con mesa)",
            f"HTTP {r3.status_code}\n{json.dumps(j3, ensure_ascii=False)[:500]}",
        )
        if r3.status_code != 409:
            findings.append(
                f"Fallo: panel con mismo tel/fecha/hora que web activa esperaba 409, "
                f"HTTP {r3.status_code} body={j3!r}."
            )

        # --- 4) Mesa ocupada (misma mesa, misma hora distinta de la web si hace falta)
        db = get_db()
        mesas = list_objetos_mesas_esquema_activo(db)
        db.close()
        if mesas:
            mname = (mesas[0]["nombre"] or "").strip() or "M1"
            hora_mesa = "22:00" if hora_web != "22:00" else "20:00"
            _admin_session(c)
            tel_a = normalizar_telefono(f"+34900088{run_id:06d}")
            tel_b = normalizar_telefono(f"+34900089{run_id:06d}")
            p4a = {
                "fecha": fecha,
                "hora": hora_mesa,
                "nombre": f"{NAME_PREFIX}mesa-a",
                "telefono": tel_a,
                "personas": 2,
                "mesa": mname,
            }
            r4a = c.post("/api/reserva_rapida", json=p4a, content_type="application/json")
            j4a = r4a.get_json(silent=True) or {}
            _log("4a. Panel reserva_rapida con mesa (primera)", f"HTTP {r4a.status_code} | {j4a}")

            p4b = {**p4a, "nombre": f"{NAME_PREFIX}mesa-b", "telefono": tel_b}
            r4b = c.post("/api/reserva_rapida", json=p4b, content_type="application/json")
            j4b = r4b.get_json(silent=True) or {}
            _log("4b. Panel misma mesa y hora (segunda)", f"HTTP {r4b.status_code} | {j4b}")
            if r4a.status_code == 200 and j4a.get("ok") and (r4b.status_code != 409 or j4b.get("error") != "mesa_ocupada"):
                findings.append(
                    f"Fallo: segunda reserva misma mesa/hora esperaba 409 mesa_ocupada, "
                    f"HTTP {r4b.status_code} body={j4b!r}."
                )
        else:
            _log("4. Mesa ocupada", "Sin mesas en plano activo; escenario omitido.")

        for f in findings:
            _log("HALLAZGO", f)

        if any("Fallo crítico" in x or x.startswith("Fallo:") for x in findings):
            return 1
        return 0
    finally:
        try:
            cleanup()
        except Exception as ex:
            print(f"Cleanup error: {ex}", file=sys.stderr)


if __name__ == "__main__":
    raise SystemExit(main())
