"""Rutas HTTP públicas para reservas web (consumidas por la web principal vía proxy)."""
from __future__ import annotations

import re
from datetime import datetime as dt
from urllib.parse import quote

from flask import Blueprint, jsonify, render_template, request

from models import get_db
from reservas.cierre_caja_mail import enviar_correo_externo, smtp_config_valida
from reservas.cierre_caja_schema import get_config_cierre_caja
from reservas.salon_helpers import ensure_salon_tables, seed_salon_if_empty
from reservas.web_reservas_logic import (
    alternativas_horario_cercanas_reserva_web,
    confirmar_por_token,
    evaluar_reserva_web,
    generar_token_confirmacion,
    insertar_reserva_web,
    mesa_opcion_valida_para_web,
    normalizar_telefono,
    opciones_mesa_reserva_web,
    slots_disponibles_payload,
    suma_capacidad_aforo,
    token_expires_iso,
)
from reservas.web_reservas_schema import ensure_web_reservas_tables, get_web_reserva_config, list_franjas


def register_web_reservas_routes(bp: Blueprint) -> None:
    """Registra rutas en el blueprint `public`."""

    @bp.route("/api/web/reservas/config")
    def api_web_reservas_config():
        db = get_db()
        ensure_web_reservas_tables(db)
        ensure_salon_tables(db)
        seed_salon_if_empty(db)
        cfg = get_web_reserva_config(db)
        aforo = suma_capacidad_aforo(db)
        franjas = list_franjas(db)
        db.close()
        return jsonify(
            {
                "enabled": bool(cfg.get("activo")),
                "min_party": int(cfg.get("min_personas") or 1),
                "max_party": int(cfg.get("max_personas") or 12),
                "lead_minutes": int(cfg.get("anticipacion_minutos") or 120),
                "max_days_ahead": int(cfg.get("max_dias_antelacion") or 60),
                "slot_interval_minutes": int(cfg.get("intervalo_minutos") or 30),
                "default_web_percent": int(cfg.get("pct_web_defecto") or 70),
                "require_email": bool(cfg.get("requiere_email")),
                "aforo_total": aforo,
                "info_text": cfg.get("texto_info") or "",
                "franjas": [
                    {
                        "weekday": int(f["dia_semana"]),
                        "start_minute": int(f["min_inicio"]),
                        "end_minute": int(f["min_fin"]),
                        "label": (f.get("etiqueta") or "").strip() or None,
                        "web_percent": f.get("pct_web"),
                    }
                    for f in franjas
                ],
            }
        )

    def _instante_madrid_fecha_hora(starts_raw: str) -> tuple[str, str] | None:
        s = (starts_raw or "").strip().replace("Z", "+00:00")
        if not s:
            return None
        try:
            parsed = dt.fromisoformat(s)
        except ValueError:
            return None
        try:
            from zoneinfo import ZoneInfo

            m = ZoneInfo("Europe/Madrid")
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=m)
            loc = parsed.astimezone(m)
            return loc.date().isoformat(), f"{loc.hour:02d}:{loc.minute:02d}"
        except Exception:
            loc = parsed
            return loc.date().isoformat(), f"{loc.hour:02d}:{loc.minute:02d}"

    @bp.route("/api/web/reservas/disponibilidad")
    def api_web_reservas_disponibilidad():
        starts_raw = (request.args.get("startsAt") or "").strip()
        if starts_raw:
            try:
                party_size = int(request.args.get("partySize") or "2")
            except (TypeError, ValueError):
                party_size = 2
            inst = _instante_madrid_fecha_hora(starts_raw)
            if not inst:
                return jsonify({"error": "Fecha no válida"}), 400
            fecha, hora = inst
            db = get_db()
            ensure_web_reservas_tables(db)
            ensure_salon_tables(db)
            seed_salon_if_empty(db)
            cfg = get_web_reserva_config(db)
            ev = evaluar_reserva_web(
                db,
                fecha_iso=fecha,
                hora_str=hora,
                personas=max(1, party_size),
                cfg=cfg,
            )
            db.close()
            if not ev.get("ok"):
                return jsonify({"ok": False, "message": ev.get("error", "No disponible.")})
            fr = ev.get("franja") or {}
            pct = int(ev.get("pct_web") or 70)
            return jsonify(
                {
                    "ok": True,
                    "slotLabel": (fr.get("etiqueta") or "").strip() or None,
                    "webPercent": pct,
                    "quota": ev.get("quota"),
                    "used": ev.get("used"),
                    "remaining": ev.get("remaining"),
                    "totalSeats": ev.get("total_seats"),
                }
            )

        fecha = (request.args.get("fecha") or request.args.get("date") or "").strip()[:10]
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha):
            return jsonify({"ok": False, "error": "Parámetro fecha inválido (use YYYY-MM-DD o startsAt)."}), 400
        try:
            personas = int(request.args.get("personas") or request.args.get("partySize") or "2")
        except (TypeError, ValueError):
            personas = 2
        db = get_db()
        ensure_web_reservas_tables(db)
        ensure_salon_tables(db)
        seed_salon_if_empty(db)
        out = slots_disponibles_payload(db, fecha_iso=fecha, personas=max(1, personas))
        db.close()
        return jsonify(out), 200

    @bp.route("/api/web/reservas/opciones-mesa")
    def api_web_reservas_opciones_mesa():
        """Mesas / uniones / pares adyacentes libres para una fecha, hora y comensales (reserva web)."""
        starts_raw = (request.args.get("startsAt") or "").strip()
        fecha = (request.args.get("fecha") or "").strip()[:10]
        hora = (request.args.get("hora") or "").strip()[:12]
        if starts_raw:
            inst = _instante_madrid_fecha_hora(starts_raw)
            if not inst:
                return jsonify({"ok": False, "error": "Fecha no válida."}), 400
            fecha, hora = inst
        try:
            personas = int(request.args.get("personas") or request.args.get("partySize") or "2")
        except (TypeError, ValueError):
            personas = 2
        personas = max(1, personas)
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", fecha or ""):
            return jsonify({"ok": False, "error": "Parámetro fecha inválido."}), 400
        if not hora:
            return jsonify({"ok": False, "error": "Hora obligatoria."}), 400

        db = get_db()
        ensure_web_reservas_tables(db)
        ensure_salon_tables(db)
        seed_salon_if_empty(db)
        cfg = get_web_reserva_config(db)
        ev = evaluar_reserva_web(db, fecha_iso=fecha, hora_str=hora, personas=personas, cfg=cfg)
        if not ev.get("ok"):
            alt = alternativas_horario_cercanas_reserva_web(
                db,
                fecha_iso=fecha,
                hora_pedida=hora,
                personas=personas,
                cfg=cfg,
                max_items=10,
            )
            db.close()
            return jsonify(
                {
                    "ok": False,
                    "error": ev.get("error", "No disponible."),
                    "opciones": [],
                    "alternativas": alt,
                    "fecha": fecha,
                    "hora": hora,
                    "personas": personas,
                }
            ), 200
        opciones = opciones_mesa_reserva_web(db, fecha_iso=fecha, hora_str=hora, personas=personas)
        alternativas: list = []
        if not opciones:
            alternativas = alternativas_horario_cercanas_reserva_web(
                db,
                fecha_iso=fecha,
                hora_pedida=hora,
                personas=personas,
                cfg=cfg,
                max_items=10,
            )
        db.close()
        return jsonify(
            {
                "ok": True,
                "fecha": fecha,
                "hora": hora,
                "personas": personas,
                "opciones": opciones,
                "alternativas": alternativas,
            }
        ), 200

    @bp.route("/api/web/reservas", methods=["POST"])
    def api_web_reservas_create():
        data = request.get_json(force=True, silent=True) or {}
        nombre = (data.get("nombre") or data.get("customerName") or "").strip()
        tel_raw = (data.get("telefono") or data.get("phone") or "").strip()
        email = (data.get("email") or data.get("customerEmail") or "").strip()
        notas = (data.get("notas") or data.get("notes") or "").strip()
        fecha = (data.get("fecha") or "").strip()[:10]
        hora = (data.get("hora") or "").strip()[:12]
        if (not fecha or not hora) and isinstance(data.get("startsAt"), str):
            inst = _instante_madrid_fecha_hora(str(data["startsAt"]))
            if inst:
                fecha, hora = inst
        try:
            personas = int(data.get("personas") or data.get("partySize") or 0)
        except (TypeError, ValueError):
            personas = 0

        if len(nombre) < 2:
            return jsonify({"ok": False, "error": "Indica un nombre válido."}), 400
        phone = normalizar_telefono(tel_raw)
        if len(phone) < 7:
            return jsonify({"ok": False, "error": "Teléfono no válido."}), 400
        if personas < 1:
            return jsonify({"ok": False, "error": "Número de comensales no válido."}), 400
        if not fecha or not hora:
            return jsonify({"ok": False, "error": "Fecha y hora obligatorias."}), 400

        mesa_sel = (data.get("mesa") or data.get("table") or data.get("mesaAsignada") or "").strip()
        if not mesa_sel:
            return jsonify(
                {"ok": False, "error": "Debes elegir una mesa (o combinación) entre las opciones ofrecidas."}
            ), 400

        db = get_db()
        ensure_web_reservas_tables(db)
        ensure_salon_tables(db)
        seed_salon_if_empty(db)
        cfg = get_web_reserva_config(db)

        if cfg.get("requiere_email") and (not email or "@" not in email):
            db.close()
            return jsonify({"ok": False, "error": "El correo electrónico es obligatorio para reservar online."}), 400

        ev = evaluar_reserva_web(db, fecha_iso=fecha, hora_str=hora, personas=personas, cfg=cfg)
        if not ev.get("ok"):
            db.close()
            return jsonify({"ok": False, "error": ev.get("error", "No disponible.")}), 409

        dup = db.execute(
            """
            SELECT id FROM reservas
            WHERE telefono = ? AND fecha = ? AND hora = ?
              AND COALESCE(estado, 'Pendiente') NOT IN ('Cancelada', 'Finalizada')
            LIMIT 1
            """,
            (phone, fecha, hora.strip()[:12]),
        ).fetchone()
        if dup:
            db.close()
            return jsonify(
                {"ok": False, "error": "Ya existe una reserva activa con ese teléfono para la misma fecha y hora."}
            ), 409

        opciones = opciones_mesa_reserva_web(db, fecha_iso=fecha, hora_str=hora, personas=personas)
        match = mesa_opcion_valida_para_web(mesa_sel, opciones)
        if not match:
            db.close()
            return jsonify(
                {
                    "ok": False,
                    "error": "La mesa elegida no está disponible o no coincide con las opciones. Actualiza y elige de nuevo.",
                    "opciones": opciones[:24],
                }
            ), 409

        token = generar_token_confirmacion()
        expires = token_expires_iso(cfg)
        try:
            rid = insertar_reserva_web(
                db,
                nombre=nombre,
                telefono=phone,
                email=email or None,
                personas=personas,
                fecha_iso=fecha,
                hora_str=hora,
                notas=notas or None,
                token=token,
                expires_iso=expires,
                mesa=str(match.get("mesa") or "").strip(),
            )
        except Exception as ex:
            db.close()
            return jsonify({"ok": False, "error": str(ex)}), 500

        email_sent = False
        email_err = ""
        base = (cfg.get("public_base_url") or "").strip().rstrip("/")
        if not base:
            base = request.url_root.rstrip("/")
        confirm_url = f"{base}/confirmar-reserva?token={quote(token, safe='')}"

        smtp_cfg = get_config_cierre_caja(db)
        if email and smtp_config_valida(smtp_cfg):
            subj = "Confirma tu reserva"
            txt = (
                f"Hola {nombre},\n\n"
                f"Has solicitado una reserva para el {fecha} a las {hora} ({personas} personas).\n\n"
                f"Para confirmarla, abre este enlace antes de que caduque:\n{confirm_url}\n\n"
                f"Si no has sido tú, ignora este mensaje.\n"
            )
            html = (
                f"<p>Hola <strong>{nombre}</strong>,</p>"
                f"<p>Has solicitado una reserva para el <strong>{fecha}</strong> a las <strong>{hora}</strong> "
                f"({personas} personas).</p>"
                f'<p><a href="{confirm_url}">Pulsa aquí para confirmar tu reserva</a></p>'
                f"<p>Si el enlace no funciona, copia y pega en el navegador:<br><code>{confirm_url}</code></p>"
            )
            try:
                ok_mail, email_err = enviar_correo_externo(
                    smtp_cfg,
                    destinatarios=[email],
                    asunto=subj,
                    cuerpo_texto=txt,
                    cuerpo_html=html,
                )
                email_sent = ok_mail
            except Exception as ex:
                email_err = str(ex)
        elif email:
            email_err = "El correo no se ha enviado: configura SMTP en Cierre de caja (misma cuenta que informes)."
        db.close()

        return jsonify(
            {
                "ok": True,
                "id": rid,
                "email_sent": email_sent,
                "email_error": email_err or None,
                "confirm_url": confirm_url if not email_sent else None,
            }
        ), 201

    @bp.route("/confirmar-reserva")
    def confirmar_reserva_pagina():
        token = (request.args.get("token") or "").strip()
        db = get_db()
        ensure_web_reservas_tables(db)
        ok, msg = confirmar_por_token(db, token)
        db.close()
        return render_template(
            "confirmar_reserva_resultado.html",
            ok=ok,
            message=msg,
        )
