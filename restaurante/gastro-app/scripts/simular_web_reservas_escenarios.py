#!/usr/bin/env python3
"""
Simulación intensiva de reservas web (Gastro): cupo, duplicados, confirmación, caducidad, franja.

Uso (desde la carpeta gastro-app o con PYTHONPATH):
  python3 scripts/simular_web_reservas_escenarios.py --fresh
  python3 scripts/simular_web_reservas_escenarios.py --db /tmp/clavo_sim.sqlite --fresh

Define DATABASE antes de importar módulos del proyecto: este script lo hace solo.
No toca tu database.db habitual salvo que pases --db explícitamente a esa ruta.
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def _log(title: str, detail: str = "") -> None:
    print(f"\n=== {title} ===")
    if detail:
        print(detail)


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--db", type=Path, default=None, help="SQLite (defecto: gastro-app/_sim_web_reservas.sqlite)")
    ap.add_argument("--fresh", action="store_true", help="Borrar el fichero de BD si existe")
    args = ap.parse_args()

    db_path = (args.db or (root / "_sim_web_reservas.sqlite")).resolve()
    if args.fresh and db_path.exists():
        db_path.unlink()
    os.environ["DATABASE"] = str(db_path)
    sys.path.insert(0, str(root))

    from models import get_db, init_db
    from reservas import create_app
    from reservas.salon_helpers import ensure_salon_tables, get_esquema_activo_id, seed_salon_if_empty, sync_tabla_mesas_desde_objetos
    from reservas.web_reservas_schema import ensure_web_reservas_tables

    init_db()
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    ensure_web_reservas_tables(db)

    eid = get_esquema_activo_id(db)
    if not eid:
        raise SystemExit("Sin esquema de salón activo tras seed.")

    # Aforo alto para poder agotar cupo en pruebas (100 plazas en mesas de 4)
    db.execute("DELETE FROM mesa_uniones")
    db.execute("DELETE FROM objetos_salon WHERE esquema_id = ?", (eid,))
    gx, gy = 90.0, 80.0
    ox, oy = 40.0, 40.0
    for i in range(25):
        col, row = i % 5, i // 5
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

    # Web: sin antelación mínima, email opcional, 100% cupo en franjas
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

    app = create_app()
    app.config["TESTING"] = True
    c = app.test_client()

    from reservas.utils import ahora_madrid

    now_m = ahora_madrid()
    tz = now_m.tzinfo
    tomorrow = date.today() + timedelta(days=1)
    t21 = datetime.strptime("21:00", "%H:%M").time()
    t12 = datetime.strptime("12:00", "%H:%M").time()
    if tz:
        starts_at = datetime.combine(tomorrow, t21, tzinfo=tz)
        noon_at = datetime.combine(tomorrow, t12, tzinfo=tz)
    else:
        starts_at = datetime.combine(tomorrow, t21)
        noon_at = datetime.combine(tomorrow, t12)
    starts_iso = starts_at.isoformat()
    noon = noon_at.isoformat()
    fecha = tomorrow.isoformat()

    ro_m = c.get(f"/api/web/reservas/opciones-mesa?fecha={fecha}&hora=21:00&personas=2")
    jom = ro_m.get_json(silent=True) or {}
    opc_m = jom.get("opciones") if isinstance(jom, dict) else None
    mesa_demo = ""
    if isinstance(opc_m, list) and opc_m:
        mesa_demo = str(opc_m[0].get("mesa") or "").strip()
    if not mesa_demo:
        _log("ERROR", f"Sin opciones de mesa para simulación (21:00): {jom!r}")
        sys.exit(1)

    def post_reserva(nombre: str, tel: str, party: int, email: str | None = None) -> tuple[int, dict]:
        body = {
            "customerName": nombre,
            "phone": tel,
            "partySize": party,
            "startsAt": starts_iso,
            "mesa": mesa_demo,
        }
        if email:
            body["customerEmail"] = email
        r = c.post("/api/web/reservas", json=body, content_type="application/json")
        try:
            j = r.get_json(silent=True) or {}
        except Exception:
            j = {}
        return r.status_code, j if isinstance(j, dict) else {}

    # --- 1. Disponibilidad día completo
    r0 = c.get(f"/api/web/reservas/disponibilidad?fecha={fecha}&personas=2")
    j0 = r0.get_json(silent=True) or {}
    slots = j0.get("slots") if isinstance(j0, dict) else None
    disp_21 = None
    if isinstance(slots, list):
        for s in slots:
            if isinstance(s, dict) and s.get("hora") == "21:00":
                disp_21 = s
                break
    _log(
        "1. Disponibilidad (mañana, 2 pax)",
        f"HTTP {r0.status_code} | slot 21:00: {disp_21!r}\n  aforo_total={j0.get('aforo_total') if isinstance(j0, dict) else '?'}\n",
    )

    # --- 2. Primera reserva + confirm_url
    code, j = post_reserva("Cliente Ana", "+34600111222", 2)
    token = None
    if isinstance(j.get("confirm_url"), str) and "token=" in j["confirm_url"]:
        token = j["confirm_url"].split("token=", 1)[-1].split("&", 1)[0]
    _log(
        "2. POST primera reserva (2 pax)",
        f"HTTP {code} | email_sent={j.get('email_sent')} | id={j.get('id')}\n  confirm_url: {bool(j.get('confirm_url'))}\n  error: {j.get('error')}\n  email_error: {j.get('email_error')}\n",
    )

    # --- 3. Confirmar por HTTP (como el enlace del correo)
    if token:
        r_conf = c.get(f"/confirmar-reserva?token={token}")
        _log("3. GET /confirmar-reserva (token válido)", f"HTTP {r_conf.status_code} | HTML length {len(r_conf.data)}\n")
        r_conf2 = c.get(f"/confirmar-reserva?token={token}")
        _log("3b. Segundo GET mismo token (idempotente)", f"HTTP {r_conf2.status_code}\n")

    # --- 4. Duplicado mismo tel + fecha + hora
    code4, j4 = post_reserva("Cliente Ana dup", "+34600111222", 2)
    _log("4. Duplicado (mismo tel, misma hora)", f"HTTP {code4} | {j4.get('error') or j4}\n")

    # --- 4b. Reserva pendiente (no confirmada) para simular edición de personas desde panel
    post_reserva("Cliente Bob", "+34600111333", 2)

    # --- 8. Simular “cambio en panel”: subir personas de una reserva web pendiente
    db = get_db()
    row = db.execute(
        """
        SELECT id, personas FROM reservas
        WHERE nombre LIKE 'Cliente Bob%' AND origen = 'web'
          AND COALESCE(estado,'') = 'Pendiente' AND confirm_token IS NOT NULL
        LIMIT 1
        """
    ).fetchone()
    if row:
        rid = int(row["id"])
        db.execute("UPDATE reservas SET personas = 12 WHERE id = ?", (rid,))
        db.commit()
        code8, j8 = post_reserva("Tras inflar Bob", "+34688888888", 2)
        _log(
            "8. Bob pendiente pasado a 12 pax (simula edición manual en Gastro)",
            f"reserva_id={rid} | siguiente POST 2 pax -> HTTP {code8} | {j8.get('error') or j8}\n",
        )
    db.close()

    # --- 5. Agotar cupo web en la franja (solo Pendiente/Confirmada/Llegó cuentan)
    # Aforo 25*4=100, pct 100% => quota 100. Reserva Ana confirmada + Bob inflado cuentan en cupo.
    # Tras confirmar, sigue contando como web en cupo según _ESTADOS_CUPO incluye Confirmada.
    total_pax = 0
    n_ok = 0
    last_code = 0
    last_j: dict = {}
    for i in range(200):
        code, jj = post_reserva(f"Auto {i}", f"+34999{i:05d}", 2)
        last_code, last_j = code, jj
        if code == 201:
            n_ok += 1
            total_pax += 2
        elif code == 409:
            break
    _log(
        "5. Llenar cupo (2 pax por reserva hasta 409)",
        f"Reservas creadas OK: {n_ok} (~{n_ok * 2} pax) | último HTTP {last_code}\n  último mensaje: {last_j.get('error') or last_j}\n",
    )

    # --- 6. Hora fuera de franja (12:00 no está en comida 13–16 ni en cena 20–23:30)
    r6 = c.post(
        "/api/web/reservas",
        json={
            "customerName": "Fuera franja",
            "phone": "+34600000001",
            "partySize": 2,
            "startsAt": noon,
            "mesa": mesa_demo,
        },
        content_type="application/json",
    )
    j6 = r6.get_json(silent=True) or {}
    _log("6. POST fuera de franja (12:00)", f"HTTP {r6.status_code} | {j6.get('error') or j6}\n")

    # --- 7. Token basura
    r7 = c.get("/confirmar-reserva?token=___token_invalido___")
    _log("7. GET confirmar token inválido", f"HTTP {r7.status_code}\n")

    _log("Listo", f"Base de datos de simulación: {db_path}\nPuedes borrarla con: rm {db_path}\n")


if __name__ == "__main__":
    main()
