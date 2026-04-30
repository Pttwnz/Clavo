"""Panel Gastro: estadísticas web Next + edición de carta (vía API interna)."""

from __future__ import annotations

from flask import flash, redirect, render_template, request, url_for

from reservas.decorators import login_requerido, permiso_mod
from reservas.next_site_http import next_site_base_url, next_site_internal_secret, next_site_request

from . import bp

MENU_CATEGORY_ORDER_ES = [
    "Promociones",
    "Tapas",
    "Tostas",
    "Carnes",
    "Pan y extras",
    "Postres",
    "Cervezas",
    "Refrescos",
    "Copas",
    "Cafés",
    "Blancos",
    "Tintos",
    "Rosados",
    "Vermú",
    "Cavas",
]

SOURCE_LABELS = {
    "WEB": "Reservas web",
    "TABLET_PHONE": "Teléfono / manual",
    "TABLET_WALKIN": "Walk-in (mostrador)",
}


@bp.route("/panel/web")
@login_requerido
@permiso_mod("mod.panel")
def panel_web_estadisticas():
    days = request.args.get("days", "30", type=int) or 30
    days = max(7, min(90, days))

    if not next_site_internal_secret():
        flash(
            "Sin credencial para llamar a Next: CLAVO_INTERNAL_API_SECRET, ADMIN_PASSWORD en claro, "
            "o (en Docker/VPS) el mismo AUTH_SECRET que Next en deploy/.env. Con solo hash de admin, "
            "usa CLAVO_* o AUTH_SECRET. Reinicia Gastro tras cambiar .env.",
            "warning",
        )
        return render_template(
            "panel_web_estadisticas.html",
            stats=None,
            days=days,
            config_error=True,
            http_error=False,
            http_detail=None,
        )

    code, data, err = next_site_request("GET", f"/api/internal/clavo-stats?days={days}")
    if code != 200 or not isinstance(data, dict):
        base = next_site_base_url()
        detail = f"URL probada: {base}/api/internal/clavo-stats\nHTTP {code}\n{err or 'sin detalle'}"
        flash(f"No se pudo leer la web Next (HTTP {code}): {err or 'error'}", "danger")
        return render_template(
            "panel_web_estadisticas.html",
            stats=None,
            days=days,
            config_error=False,
            http_error=True,
            http_detail=detail[:1500],
        )

    return render_template(
        "panel_web_estadisticas.html",
        stats=data,
        days=days,
        config_error=False,
        http_error=False,
        http_detail=None,
        source_labels=SOURCE_LABELS,
    )


@bp.route("/panel/web/carta", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.panel")
def panel_web_carta():
    if not next_site_internal_secret():
        flash(
            "Sin credencial para Next: CLAVO_INTERNAL_API_SECRET, ADMIN_PASSWORD en claro, o AUTH_SECRET "
            "(mismo valor que en la web; típico deploy/.env en Docker). Reinicia Gastro.",
            "warning",
        )
        return render_template(
            "panel_web_carta.html",
            items=None,
            category_presets=None,
            persisted=False,
            categories=MENU_CATEGORY_ORDER_ES,
            config_error=True,
        )

    if request.method == "POST":
        payload = request.get_json(silent=True) if request.is_json else None
        if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
            flash("JSON de platos inválido.", "danger")
            return redirect(url_for("admin.panel_web_carta"))

        code, _, err = next_site_request("PUT", "/api/internal/menu-carta", body=payload)
        if code != 200:
            flash(f"No se pudo guardar (HTTP {code}): {err}", "danger")
        else:
            flash("Carta guardada en la base de datos de la web.", "success")
        return redirect(url_for("admin.panel_web_carta"))

    code, data, err = next_site_request("GET", "/api/internal/menu-carta")
    if code != 200 or not isinstance(data, dict):
        flash(f"No se pudo cargar la carta (HTTP {code}): {err}", "danger")
        return render_template(
            "panel_web_carta.html",
            items=None,
            category_presets=None,
            persisted=False,
            categories=MENU_CATEGORY_ORDER_ES,
            config_error=False,
            load_error=True,
        )

    items = data.get("items") or []
    category_presets = data.get("categoryPresets") or {}
    persisted = bool(data.get("persisted"))
    return render_template(
        "panel_web_carta.html",
        items=items,
        category_presets=category_presets,
        persisted=persisted,
        categories=MENU_CATEGORY_ORDER_ES,
        config_error=False,
        load_error=False,
    )


@bp.route("/panel/web/carta/restablecer", methods=["POST"])
@login_requerido
@permiso_mod("mod.panel")
def panel_web_carta_restablecer():
    if not next_site_internal_secret():
        flash("Falta credencial para Next (CLAVO_INTERNAL_API_SECRET, ADMIN_PASSWORD o AUTH_SECRET).", "warning")
        return redirect(url_for("admin.panel_web_carta"))
    code, _, err = next_site_request("DELETE", "/api/internal/menu-carta")
    if code != 200:
        flash(f"No se pudo restablecer (HTTP {code}): {err}", "danger")
    else:
        flash("Carta restablecida a la versión por defecto del código Next.", "success")
    return redirect(url_for("admin.panel_web_carta"))
