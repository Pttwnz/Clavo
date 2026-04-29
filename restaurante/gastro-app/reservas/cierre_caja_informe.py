"""Texto del informe de cierre X / Z y parseo del formulario."""
from __future__ import annotations

from datetime import datetime


def _f(val) -> float:
    try:
        return float(str(val).replace(",", ".").strip())
    except (TypeError, ValueError):
        return 0.0


def payload_desde_form(form) -> dict[str, object]:
    """Unifica campos POST del cierre (tablet o admin)."""
    tipo = (form.get("tipo") or "X").strip().upper()[:1]
    if tipo not in ("X", "Z"):
        tipo = "X"
    apertura = _f(form.get("efectivo_apertura"))
    ventas_ef = _f(form.get("ventas_efectivo"))
    ventas_tarj = _f(form.get("ventas_tarjeta"))
    otros = _f(form.get("otros_ingresos"))
    retiros = _f(form.get("retiros_caja"))
    contado = _f(form.get("efectivo_contado"))
    observaciones = (form.get("observaciones") or "").strip()

    esperado = apertura + ventas_ef + otros - retiros
    diferencia = contado - esperado

    return {
        "tipo": tipo,
        "efectivo_apertura": apertura,
        "ventas_efectivo": ventas_ef,
        "ventas_tarjeta": ventas_tarj,
        "otros_ingresos": otros,
        "retiros_caja": retiros,
        "efectivo_esperado": round(esperado, 2),
        "efectivo_contado": contado,
        "diferencia": round(diferencia, 2),
        "observaciones": observaciones,
        "registrado_en": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


def construir_asunto_y_cuerpos(
    payload: dict,
    nombre_establecimiento: str,
) -> tuple[str, str, str]:
    """asunto, texto plano, html."""
    tipo = payload.get("tipo") or "X"
    nombre = (nombre_establecimiento or "Establecimiento").strip() or "Establecimiento"
    etiqueta = "Cierre X (lectura / arqueo intermedio)" if tipo == "X" else "Cierre Z (cierre de jornada)"

    asunto = f"[{nombre}] {etiqueta} — {payload.get('registrado_en', '')}"

    def linea(k: str, v: object) -> str:
        return f"  • {k}: {v}\n"

    txt = f"""{etiqueta}
Establecimiento: {nombre}
Fecha y hora: {payload.get('registrado_en', '—')}

Efectivo al abrir / base caja: {payload.get('efectivo_apertura', 0):.2f} €
Ventas en efectivo (periodo): {payload.get('ventas_efectivo', 0):.2f} €
Ventas tarjeta (referencia): {payload.get('ventas_tarjeta', 0):.2f} €
Otros ingresos efectivo: {payload.get('otros_ingresos', 0):.2f} €
Retiros / salidas de caja: {payload.get('retiros_caja', 0):.2f} €
────────────────────────
Efectivo esperado en cajón: {payload.get('efectivo_esperado', 0):.2f} €
Efectivo contado (real): {payload.get('efectivo_contado', 0):.2f} €
Diferencia (sobra/falta): {payload.get('diferencia', 0):.2f} €

Observaciones:
{(payload.get('observaciones') or '—')}

---
Enviado desde GastroManager (cierre de caja).
"""
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"></head><body style="font-family:system-ui,sans-serif;line-height:1.5;color:#0f172a;">
<h2 style="margin:0 0 8px;">{etiqueta}</h2>
<p style="margin:0 0 16px;color:#64748b;"><strong>{nombre}</strong><br>{payload.get('registrado_en', '')}</p>
<table style="border-collapse:collapse;width:100%;max-width:420px;">
<tr><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;">Efectivo al abrir</td><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{payload.get('efectivo_apertura', 0):.2f} €</td></tr>
<tr><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;">Ventas efectivo</td><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{payload.get('ventas_efectivo', 0):.2f} €</td></tr>
<tr><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;">Ventas tarjeta</td><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{payload.get('ventas_tarjeta', 0):.2f} €</td></tr>
<tr><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;">Otros ingresos</td><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{payload.get('otros_ingresos', 0):.2f} €</td></tr>
<tr><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;">Retiros</td><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{payload.get('retiros_caja', 0):.2f} €</td></tr>
<tr><td style="padding:8px 0;font-weight:bold;">Efectivo esperado</td><td style="padding:8px 0;text-align:right;font-weight:bold;">{payload.get('efectivo_esperado', 0):.2f} €</td></tr>
<tr><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;">Efectivo contado</td><td style="padding:6px 0;border-bottom:1px solid #e2e8f0;text-align:right;">{payload.get('efectivo_contado', 0):.2f} €</td></tr>
<tr><td style="padding:8px 0;font-weight:bold;color:#b45309;">Diferencia</td><td style="padding:8px 0;text-align:right;font-weight:bold;color:#b45309;">{payload.get('diferencia', 0):.2f} €</td></tr>
</table>
<p style="margin-top:16px;"><strong>Observaciones</strong><br>{(payload.get('observaciones') or '—').replace(chr(10), '<br>')}</p>
<p style="font-size:12px;color:#94a3b8;">Enviado desde GastroManager</p>
</body></html>"""

    return asunto, txt, html
