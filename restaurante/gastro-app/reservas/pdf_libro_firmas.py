"""Generación de PDF del libro de registro de jornada (ReportLab)."""
from __future__ import annotations

import io
import os
import re
from datetime import datetime
from typing import Any
from zipfile import ZipFile, ZIP_DEFLATED

from reservas.pil_fix import ensure_pil_stub_for_reportlab, pillow_usable

# ReportLab importa PIL vía reportlab.lib.utils; pil_fix asegura stub si Pillow no carga (p. ej. Windows).
ensure_pil_stub_for_reportlab()

_RL_IMPORT_ERROR: str | None = None

try:
    from reportlab.lib import colors
    from reportlab.lib.pagesizes import A4, landscape
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
    """Para mensajes de error 503 más claros."""
    return _RL_IMPORT_ERROR


def _slug_filename(s: str) -> str:
    s = re.sub(r"[^\w\s\-]", "", s, flags=re.UNICODE)
    s = re.sub(r"[-\s]+", "_", s).strip("_")
    return (s or "empleado")[:80]


TEXTO_MARCO_LEGAL = (
    "Registro de jornada conforme al artículo 34.9 del Estatuto de los Trabajadores y normativa "
    "aplicable: registro diario, objetivo y fiable. Las horas ordinarias de referencia por día se "
    "calculan dividiendo la jornada semanal contractual entre cinco días laborables, salvo "
    "criterio documentado distinto en la empresa."
)


def construir_pdf_libro_empleado(
    static_root: str | None,
    empresa: dict[str, Any],
    empleado: dict[str, Any],
    lineas: list[dict[str, Any]],
    mes_etiqueta: str,
    conformidad: dict[str, Any] | None = None,
) -> bytes:
    """
    lineas: filas con fecha, entrada, salida, pausas, horas, horas_ord, horas_ext, estado.
    conformidad: fila de conformidades_jornada (opcional) con creado_en, ip, firma_relativa, texto_legal.
    """
    if not _HAS_RL:
        extra = f" Detalle: {_RL_IMPORT_ERROR}" if _RL_IMPORT_ERROR else ""
        raise RuntimeError(
            "No se pudo cargar ReportLab. Ejecute: pip install reportlab pillow" + extra
        )

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        rightMargin=1.2 * cm,
        leftMargin=1.2 * cm,
        topMargin=1.0 * cm,
        bottomMargin=1.0 * cm,
    )
    styles = getSampleStyleSheet()
    story = []
    title_style = ParagraphStyle(
        "T",
        parent=styles["Heading1"],
        fontSize=14,
        spaceAfter=8,
        textColor=colors.HexColor("#0f172a"),
    )
    normal = styles["Normal"]
    small = ParagraphStyle("S", parent=normal, fontSize=8, textColor=colors.HexColor("#64748b"))

    # Logo (requiere Pillow real; con stub PIL se omite)
    logo_rel = (empresa.get("logo_relativo") or "").strip()
    if static_root and logo_rel and pillow_usable():
        path = os.path.join(static_root, logo_rel.replace("/", os.sep))
        try:
            if os.path.isfile(path):
                img = RLImage(path, width=3.2 * cm, height=1.2 * cm, kind="proportional")
                story.append(img)
                story.append(Spacer(1, 0.2 * cm))
        except Exception:
            pass

    rs = (empresa.get("razon_social") or empresa.get("nombre_comercial") or "").strip() or "Empresa"
    story.append(Paragraph(rs, title_style))

    emp_lines = []
    if (empresa.get("cif") or "").strip():
        emp_lines.append(f"CIF: {empresa['cif'].strip()}")
    addr_parts = [
        (empresa.get("direccion") or "").strip(),
        " ".join(
            x
            for x in [
                (empresa.get("codigo_postal") or "").strip(),
                (empresa.get("ciudad") or "").strip(),
            ]
            if x
        ),
        (empresa.get("provincia") or "").strip(),
    ]
    addr = ", ".join(x for x in addr_parts if x)
    if addr:
        emp_lines.append(addr)
    tel_mail = " · ".join(
        x
        for x in [(empresa.get("telefono") or "").strip(), (empresa.get("email") or "").strip()]
        if x
    )
    if tel_mail:
        emp_lines.append(tel_mail)
    for line in emp_lines:
        story.append(Paragraph(line, small))
    story.append(Spacer(1, 0.4 * cm))

    story.append(
        Paragraph(
            f"<b>Registro de jornada</b> · {mes_etiqueta}",
            ParagraphStyle("H2", parent=normal, fontSize=11, spaceAfter=4, textColor=colors.HexColor("#334155")),
        )
    )
    story.append(
        Paragraph(
            TEXTO_MARCO_LEGAL,
            ParagraphStyle("Leg", parent=small, fontSize=7, leading=9, spaceAfter=8, textColor=colors.HexColor("#475569")),
        )
    )

    # Datos trabajador
    skip = {"pin", "pin_hash", "id"}
    datos_tr = []
    labels = {
        "nombre": "Nombre",
        "apellido": "Apellidos",
        "dni": "DNI/NIE",
        "telefono": "Teléfono",
        "numero_ss": "Nº SS",
        "puesto": "Puesto",
        "horas_contrato": "Horas contrato",
        "tipo_contrato": "Tipo contrato",
        "fecha_alta": "Fecha alta",
        "activo": "Activo",
        "observaciones": "Observaciones",
    }
    for k, lab in labels.items():
        if k in empleado and k not in skip:
            v = empleado[k]
            if v is None or str(v).strip() == "":
                continue
            datos_tr.append([lab, str(v)])

    if datos_tr:
        t_datos = Table([[Paragraph(f"<b>{a}</b>", normal), Paragraph(str(b), normal)] for a, b in datos_tr], colWidths=[4 * cm, 12 * cm])
        t_datos.setStyle(
            TableStyle(
                [
                    ("BACKGROUND", (0, 0), (-1, -1), colors.HexColor("#f8fafc")),
                    ("BOX", (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
                    ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#e2e8f0")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 6),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                    ("TOPPADDING", (0, 0), (-1, -1), 4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ]
            )
        )
        story.append(Paragraph("<b>Datos del trabajador</b>", ParagraphStyle("d", parent=normal, fontSize=10, spaceAfter=4)))
        story.append(t_datos)
        story.append(Spacer(1, 0.5 * cm))

    # Tabla jornadas
    if not lineas:
        lineas = [
            {
                "fecha": "—",
                "entrada": "—",
                "salida": "—",
                "pausas": "—",
                "horas": "Sin registros",
                "horas_ord": "—",
                "horas_ext": "—",
                "estado": "—",
            }
        ]

    def _c(x: dict[str, Any], k: str, default: str = "—") -> str:
        v = x.get(k)
        if v is None or str(v).strip() == "":
            return default
        return str(v)

    head = [
        [
            "Fecha",
            "Entrada",
            "Salida",
            "Pausas / descanso",
            "Total trab.",
            "Ordinarias",
            "Extraord.",
            "Estado",
        ]
    ]
    data = head + [
        [
            _c(x, "fecha"),
            _c(x, "entrada"),
            _c(x, "salida"),
            _c(x, "pausas"),
            _c(x, "horas"),
            _c(x, "horas_ord"),
            _c(x, "horas_ext"),
            _c(x, "estado"),
        ]
        for x in lineas
    ]
    tw = [
        2.4 * cm,
        2.0 * cm,
        2.0 * cm,
        5.2 * cm,
        2.0 * cm,
        2.0 * cm,
        2.0 * cm,
        2.4 * cm,
    ]
    t = Table(data, colWidths=tw, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1e293b")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.whitesmoke),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 7),
                ("ALIGN", (1, 1), (6, -1), "CENTER"),
                ("ALIGN", (7, 1), (7, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#cbd5e1")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    story.append(t)
    story.append(Spacer(1, 0.5 * cm))

    if conformidad:
        story.append(
            Paragraph(
                "<b>Conformidad del trabajador con el registro (validación digital)</b>",
                ParagraphStyle("cfh", parent=normal, fontSize=9, spaceAfter=4),
            )
        )
        cf_lines = []
        if conformidad.get("creado_en"):
            cf_lines.append(f"Fecha y hora de la conformidad: {conformidad['creado_en']}")
        if conformidad.get("ip"):
            cf_lines.append(f"Dirección IP: {conformidad['ip']}")
        if conformidad.get("texto_legal"):
            cf_lines.append(f"Texto aceptado: {conformidad['texto_legal'][:500]}")
        for ln in cf_lines:
            story.append(Paragraph(ln, small))
        rel = (conformidad.get("firma_relativa") or "").strip()
        if static_root and rel and os.path.isfile(os.path.join(static_root, rel.replace("/", os.sep))):
            try:
                p = os.path.join(static_root, rel.replace("/", os.sep))
                story.append(Spacer(1, 0.2 * cm))
                story.append(RLImage(p, width=5.5 * cm, height=2.0 * cm, kind="proportional"))
                story.append(Paragraph("<i>Firma manuscrita digitalizada</i>", small))
            except Exception:
                pass
        story.append(Spacer(1, 0.4 * cm))

    gen = datetime.now().strftime("%d/%m/%Y %H:%M")
    story.append(Paragraph(f"<i>Documento generado el {gen}</i>", small))

    doc.build(story)
    buf.seek(0)
    return buf.getvalue()


def zip_pdfs_trabajadores_mes(
    static_root: str | None,
    empresa: dict[str, Any],
    empleados_items: list[tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any] | None]],
    mes_etiqueta: str,
) -> bytes:
    """empleados_items: [(empleado_dict, lineas_mes, conformidad|None), ...]"""
    if not _HAS_RL:
        extra = f" Detalle: {_RL_IMPORT_ERROR}" if _RL_IMPORT_ERROR else ""
        raise RuntimeError("No se pudo cargar ReportLab. pip install reportlab pillow" + extra)
    mem = io.BytesIO()
    with ZipFile(mem, "w", ZIP_DEFLATED) as zf:
        for item in empleados_items:
            emp = item[0]
            lineas = item[1]
            conf = item[2] if len(item) > 2 else None
            nombre = f"{(emp.get('nombre') or '').strip()} {(emp.get('apellido') or '').strip()}".strip() or "empleado"
            slug = _slug_filename(nombre)
            pdf = construir_pdf_libro_empleado(
                static_root, empresa, emp, lineas, mes_etiqueta, conformidad=conf
            )
            zf.writestr(f"libro_firmas_{slug}_{mes_etiqueta.replace(' ', '_')}.pdf", pdf)
    mem.seek(0)
    return mem.getvalue()
