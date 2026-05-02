#!/usr/bin/env python3
"""
E2E contra el despliegue real (HTTPS), sin Flask test_client.

Por defecto apunta a la web publica Next en elclavo y usa las mismas rutas que el navegador:
  GET  /api/reservations/availability?fecha=YYYY-MM-DD&personas=2
  POST /api/reservations  (JSON; Next reenvia a Gastro si GASTRO_RESERVAS_BASE_URL esta definida en el contenedor web)

Opcional (panel / sala): POST /api/reserva_rapida en el mismo host **tras** enrutar esa ruta a Gastro en Nginx
(ver deploy/nginx-sites/elclavo.gastromanager.es: alternativa `reserva_rapida` en el bloque location ~ ^/api/...).

Autenticacion panel: PIN admin con variable de entorno E2E_GASTRO_PIN o flag --pin (no lo pongas en el repo).

Ejemplos:
  E2E_GASTRO_PIN=**** python3 scripts/e2e_reservas_remote_http.py --allow-remote-writes

  python3 scripts/e2e_reservas_remote_http.py --web-base https://elclavo.gastromanager.es \\
      --via gastro --allow-remote-writes

Requiere --allow-remote-writes si el host contiene gastromanager.es (evita golpes accidentales a produccion).
"""
from __future__ import annotations

import argparse
import json
import os
import re
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone
from http.cookiejar import CookieJar


NAME_MARK = "Clavo E2E AUTO"


def _starts_at_iso(d: date, hhmm: str) -> str:
    """ISO startsAt con zona Madrid (Europe/Madrid si hay tzdata; si no, aproximacion CET/CEST)."""
    h, m = hhmm.split(":", 1)
    hi, mi = int(h), int(m)
    try:
        from zoneinfo import ZoneInfo

        return datetime(d.year, d.month, d.day, hi, mi, 0, tzinfo=ZoneInfo("Europe/Madrid")).isoformat()
    except Exception:
        # Windows sin paquete tzdata: CEST meses abr-sep, resto CET (suficiente para huecos de comida/cena).
        off = 2 if d.month in (4, 5, 6, 7, 8, 9) else 1
        return datetime(
            d.year, d.month, d.day, hi, mi, 0, tzinfo=timezone(timedelta(hours=off))
        ).isoformat()


def _log(title: str, detail: str = "") -> None:
    print(f"\n=== {title} ===")
    if detail:
        print(detail.rstrip())


def _strip_base(url: str) -> str:
    return (url or "").strip().rstrip("/")


def _request(
    opener: urllib.request.OpenerDirector,
    method: str,
    url: str,
    *,
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    timeout: int = 45,
) -> tuple[int, dict | str]:
    h = dict(headers or {})
    req = urllib.request.Request(url, data=data, method=method, headers=h)
    try:
        with opener.open(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
            ct = (resp.headers.get("Content-Type") or "").lower()
            if "json" in ct and raw.strip().startswith(("{", "[")):
                return resp.status, json.loads(raw)
            return resp.status, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace")
        try:
            if raw.strip().startswith("{"):
                return e.code, json.loads(raw)
        except json.JSONDecodeError:
            pass
        return e.code, raw


def _find_slot_next(opener: urllib.request.OpenerDirector, web_base: str) -> tuple[str, str, str] | None:
    """Devuelve (fecha_iso, startsAt_iso, hora_hhmm) usando la API Next."""
    for add in range(1, 50):
        d = date.today() + timedelta(days=add)
        fecha = d.isoformat()
        url = f"{web_base}/api/reservations/availability?fecha={fecha}&personas=2"
        code, body = _request(opener, "GET", url)
        if code != 200 or not isinstance(body, dict):
            continue
        if not body.get("ok"):
            continue
        slots = body.get("slots")
        if not isinstance(slots, list):
            continue
        for s in slots:
            if not isinstance(s, dict) or not s.get("disponible"):
                continue
            hhmm = (s.get("hora") or "").strip()
            if not re.match(r"^\d{1,2}:\d{2}$", hhmm):
                continue
            return fecha, _starts_at_iso(d, hhmm), hhmm
    return None


def _find_slot_gastro(opener: urllib.request.OpenerDirector, web_base: str) -> tuple[str, str, str] | None:
    for add in range(1, 50):
        d = date.today() + timedelta(days=add)
        fecha = d.isoformat()
        url = f"{web_base}/api/web/reservas/disponibilidad?fecha={fecha}&personas=2"
        code, body = _request(opener, "GET", url)
        if code != 200 or not isinstance(body, dict) or not body.get("ok"):
            continue
        slots = body.get("slots")
        if not isinstance(slots, list):
            continue
        for s in slots:
            if not isinstance(s, dict) or not s.get("disponible"):
                continue
            hhmm = (s.get("hora") or "").strip()
            if not re.match(r"^\d{1,2}:\d{2}$", hhmm):
                continue
            return fecha, _starts_at_iso(d, hhmm), hhmm
    return None


def _digits_phone(raw: str) -> str:
    return re.sub(r"\D+", "", (raw or "").strip())


def _login_admin_pin(opener: urllib.request.OpenerDirector, panel_base: str, pin: str) -> bool:
    data = urllib.parse.urlencode({"pin": pin, "next": "/panel"}).encode("utf-8")
    code, _ = _request(
        opener,
        "POST",
        f"{panel_base}/verificar_admin",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    return code in (200, 302, 303)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--web-base", default="https://elclavo.gastromanager.es", help="URL base web Next (HTTPS)")
    ap.add_argument(
        "--via",
        choices=("next", "gastro"),
        default="next",
        help="next: /api/reservations* (como el formulario). gastro: /api/web/reservas* directo a Flask.",
    )
    ap.add_argument(
        "--panel-base",
        default="",
        help="Base URL para /api/reserva_rapida y /verificar_admin (por defecto igual que --web-base).",
    )
    ap.add_argument("--pin", default=os.environ.get("E2E_GASTRO_PIN", "") or "", help="PIN admin (o E2E_GASTRO_PIN)")
    ap.add_argument(
        "--allow-remote-writes",
        action="store_true",
        help="Obligatorio para ejecutar contra gastromanager.es (crea reservas reales).",
    )
    args = ap.parse_args()

    web_base = _strip_base(args.web_base)
    panel_base = _strip_base(args.panel_base) or web_base

    if "gastromanager.es" in web_base.lower() and not args.allow_remote_writes:
        print(
            "Refusing: pasa --allow-remote-writes para crear reservas en gastromanager.es.",
            file=sys.stderr,
        )
        return 2

    ctx = ssl.create_default_context()
    cj = CookieJar()
    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=ctx),
        urllib.request.HTTPCookieProcessor(cj),
        urllib.request.HTTPRedirectHandler(),
    )

    findings: list[str] = []

    code_cfg, cfg = _request(opener, "GET", f"{web_base}/api/web/reservas/config")
    require_email = False
    if code_cfg == 200 and isinstance(cfg, dict):
        require_email = bool(cfg.get("require_email"))
        _log("Config Gastro (publica)", f"enabled={cfg.get('enabled')} require_email={require_email} lead_min={cfg.get('lead_minutes')}")
    else:
        _log("Config Gastro", f"HTTP {code_cfg} (sigue el test si la disponibilidad responde)")

    if args.via == "next":
        slot = _find_slot_next(opener, web_base)
        post_path = "/api/reservations"
        avail_note = "Next /api/reservations/availability"
    else:
        slot = _find_slot_gastro(opener, web_base)
        post_path = "/api/web/reservas"
        avail_note = "Gastro /api/web/reservas/disponibilidad"

    if not slot:
        _log("ERROR", f"No hay hueco web en ~50 dias ({avail_note}).")
        return 1

    fecha, starts_at, hora = slot
    _log("Slot elegido", f"fecha={fecha} hora={hora} startsAt={starts_at} via={args.via}")

    if args.via == "next":
        qm = urllib.parse.urlencode({"startsAt": starts_at, "partySize": "2"})
        code_m, jm = _request(opener, "GET", f"{web_base}/api/reservations/mesa-options?{qm}")
    else:
        qm = urllib.parse.urlencode({"fecha": fecha, "hora": hora, "personas": "2"})
        code_m, jm = _request(opener, "GET", f"{web_base}/api/web/reservas/opciones-mesa?{qm}")
    mesa_pick = ""
    if code_m == 200 and isinstance(jm, dict) and jm.get("ok"):
        opc = jm.get("opciones")
        if isinstance(opc, list) and opc:
            mesa_pick = str(opc[0].get("mesa") or "").strip()
    if not mesa_pick:
        _log("ERROR", f"Sin mesa para E2E (opciones-mesa HTTP {code_m}): {str(jm)[:500]}")
        return 1

    run = int(time.time()) % 1_000_000
    # Movil ES: +34 + 9 digitos (6XXXXXXXX)
    phone_raw = f"+34600{run:06d}"
    phone_digits = _digits_phone(phone_raw)
    nombre = f"{NAME_MARK} {run}"

    payload: dict = {
        "customerName": nombre,
        "phone": phone_raw,
        "partySize": 2,
        "startsAt": starts_at,
        "mesa": mesa_pick,
    }
    if require_email:
        payload["customerEmail"] = f"e2e-auto-{run}@example.invalid"

    body = json.dumps(payload).encode("utf-8")
    url_post = f"{web_base}{post_path}"
    code1, j1 = _request(
        opener,
        "POST",
        url_post,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    _log("1. POST primera reserva", f"HTTP {code1}\n{str(j1)[:900]}")
    if code1 != 201:
        findings.append(f"Fallo: primera reserva esperaba HTTP 201, obtuvo {code1}.")
        for f in findings:
            _log("HALLAZGO", f)
        return 1

    code2, j2 = _request(
        opener,
        "POST",
        url_post,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    _log("2. POST duplicado (mismo cuerpo)", f"HTTP {code2}\n{str(j2)[:600]}")
    if code2 != 409:
        findings.append(f"Fallo: duplicado web esperaba HTTP 409, obtuvo {code2}.")

    pin = (args.pin or "").strip()
    if pin:
        if not _login_admin_pin(opener, panel_base, pin):
            findings.append("Fallo: login admin PIN (verificar_admin) no devolvio 200/302.")
        else:
            panel_body = json.dumps(
                {
                    "fecha": fecha,
                    "hora": hora,
                    "nombre": f"{NAME_MARK} panel dup",
                    "telefono": phone_digits,
                    "personas": 2,
                    "mesa": mesa_pick,
                }
            ).encode("utf-8")
            code3, j3 = _request(
                opener,
                "POST",
                f"{panel_base}/api/reserva_rapida",
                data=panel_body,
                headers={"Content-Type": "application/json"},
            )
            _log("3. Panel /api/reserva_rapida (mismo tel que la web)", f"HTTP {code3}\n{str(j3)[:500]}")
            if code3 == 404:
                findings.append(
                    "404 en /api/reserva_rapida: Nginx no enruta esta ruta a Gastro en este host, "
                    "o la URL panel-base es incorrecta. Actualiza nginx (alternativa reserva_rapida) y recarga."
                )
            elif code3 == 401:
                findings.append("Panel: 401 unauthorized (sesion no aplicada tras login?).")
            elif code3 != 409:
                findings.append(
                    f"Fallo: panel mismo telefono/fecha/hora tras web esperaba HTTP 409, obtuvo {code3}."
                )
    else:
        _log("3. Panel", "Omitido (sin PIN: export E2E_GASTRO_PIN o --pin).")

    for f in findings:
        _log("HALLAZGO", f)

    _log(
        "Limpieza manual",
        "En Gastro: Reservas, busca por nombre que contenga 'Clavo E2E AUTO' y borra las de prueba.\n"
        f"Telefono usado en la prueba (normalizado en BD): {phone_digits}",
    )

    if any(x.startswith("Fallo:") for x in findings):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
