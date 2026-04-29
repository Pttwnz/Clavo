"""PDF de planning de horarios personal (ReportLab, A4 vertical)."""
from __future__ import annotations

import io
import os
from typing import Any

from reservas.pil_fix import ensure_pil_stub_for_reportlab, pillow_usable

ensure_pil_stub_for_reportlab()

_RL_IMPORT_ERROR: str | None = None
try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm
    from reportlab.platypus import Image as RLImage
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

    _HAS_RL = True
except ImportError as e:
    _HAS_RL = False
    _RL_IMPORT_ERROR = str(e)


def reportlab_disponible() -> bool:
    return _HAS_RL


def reportlab_error_detalle() -> str | None:
    return _RL_IMPORT_ERROR


def construir_pdf_horarios_empleado(
    static_root: str | None,
    empresa: dict[str, Any],
    empleado: dict[str, Any],
    lineas: list[dict[str, Any]],
    periodo_etiqueta: str,
) -> bytes:
    """
    lineas: fecha, fecha_fmt, dia_es, hora_inicio, hora_fin, horas, turno, estado
    """
    if not _HAS_RL:
        extra = f" Detalle: {_RL_IMPORT_ERROR}" if _RL_IMPORT_ERROR else ""
        raise RuntimeError("No se pudo cargar ReportLab. pip install reportlab pillow" + extra)

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.2 * cm,
        bottomMargin=1.2 * cm,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "T",
        parent=styles["Heading1"],
        fontSize=15,
        spaceAfter=6,
        textColor=colors.HexColor("#0f172a"),
    )
    sub_style = ParagraphStyle(
        "Sub",
        parent=styles["Normal"],
        fontSize=10,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=10,
    )
    story = []

    logo_rel = (empresa.get("logo_relativo") or "").strip()
    if static_root and logo_rel and pillow_usable():
        path = os.path.join(static_root, logo_rel.replace("/", os.sep))
        try:
            if os.path.isfile(path):
                img = RLImage(path, width=3 * cm, height=1.1 * cm, kind="proportional")
                story.append(img)
                story.append(Spacer(1, 0.25 * cm))
        except Exception:
            pass

    rs = (empresa.get("razon_social") or empresa.get("nombre_comercial") or "").strip() or "Empresa"
    story.append(Paragraph(rs, title_style))
    story.append(Paragraph("Planning de horarios (documento informativo)", sub_style))

    nom = (empleado.get("nombre") or "").strip()
    if empleado.get("apellido"):
        nom = f"{nom} {(empleado.get('apellido') or '').strip()}".strip()
    story.append(
        Paragraph(
            f"<b>Trabajador/a:</b> {nom or '—'} &nbsp;|&nbsp; <b>Período:</b> {periodo_etiqueta}",
            styles["Normal"],
        )
    )
    story.append(Spacer(1, 0.4 * cm))

    if not lineas:
        story.append(Paragraph("No constan turnos en este período.", styles["Normal"]))
        doc.build(story)
        return buf.getvalue()

    data = [["Fecha", "Día", "Entrada", "Salida", "H.", "Turno", "Estado"]]
    for ln in lineas:
        h_txt = ""
        if ln.get("horas") is not None:
            try:
                h_txt = f"{float(ln['horas']):.2f}"
            except (TypeError, ValueError):
                h_txt = "—"
        else:
            h_txt = "—"
        data.append(
            [
                ln.get("fecha_fmt") or ln.get("fecha") or "—",
                (ln.get("dia_es") or "")[:3],
                str(ln.get("hora_inicio") or "—"),
                str(ln.get("hora_fin") or "—"),
                h_txt,
                str(ln.get("turno") or "—")[:18],
                str(ln.get("estado") or "—")[:14],
            ]
        )

    t = Table(data, colWidths=[2.2 * cm, 1.1 * cm, 1.5 * cm, 1.5 * cm, 1 * cm, 2.8 * cm, 2.2 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#334155")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#fafafa")]),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))
    small = ParagraphStyle("sm", parent=styles["Normal"], fontSize=7, textColor=colors.HexColor("#94a3b8"))
    story.append(
        Paragraph(
            "Documento generado desde el sistema de planificación. Para dudas, contacta con tu responsable.",
            small,
        )
    )

    doc.build(story)
    return buf.getvalue()
