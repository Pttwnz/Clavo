"""Carga de festivos oficiales (España) mediante la biblioteca `holidays` — no usa fechas inventadas por IA."""
from __future__ import annotations

import unicodedata
from datetime import date


def _norm_busqueda(s: str) -> str:
    """Minúsculas y sin acentos para comparar títulos (es/en)."""
    if not s:
        return ""
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Descripciones breves en español (referencia general; no asesoría legal).
_PATRON_DESCRIPCION: list[tuple[tuple[str, ...], str]] = [
    (
        ("ano nuevo", "new year's", "new year"),
        "Festivo civil: primer día del año en el calendario gregoriano.",
    ),
    (
        ("epifania", "epiphany", "reyes"),
        "Festividad religiosa: celebración de la Epifanía del Señor (Reyes Magos).",
    ),
    (
        ("san jose", "st joseph", "saint joseph"),
        "Festividad religiosa: San José (patrón de la Comunitat Valenciana en parte del territorio).",
    ),
    (
        ("viernes santo", "good friday"),
        "Festividad religiosa: conmemoración de la Pasión de Cristo (Semana Santa).",
    ),
    (
        ("pascua", "easter", "lunes siguiente"),
        "Festividad religiosa: Semana Santa / Pascua (domingo de Resurrección o lunes siguiente, según calendario).",
    ),
    (
        ("fiesta del trabajo", "labour day", "workers' day", "trabajo"),
        "Festivo estatal: Día Internacional de los Trabajadores (1 de mayo).",
    ),
    (
        ("san juan", "st john", "john the baptist"),
        "Festividad tradicional: noche / día de San Juan (verano).",
    ),
    (
        ("asuncion", "assumption"),
        "Festividad religiosa: Asunción de la Virgen (15 de agosto).",
    ),
    (
        ("comunidad valenciana", "9 d'octubre", "9 de octubre", "valencian community"),
        "Festivo autonómico: día de la Comunidad Valenciana (9 de octubre).",
    ),
    (
        ("fiesta nacional", "hispanidad", "national day", "columbus"),
        "Festivo estatal: Fiesta Nacional de España (12 de octubre).",
    ),
    (
        ("todos los santos", "all saints"),
        "Festividad religiosa: Todos los Santos (1 de noviembre).",
    ),
    (
        ("constitucion", "constitution"),
        "Festivo estatal: conmemoración de la Constitución española (6 de diciembre).",
    ),
    (
        ("inmaculada", "immaculate conception"),
        "Festividad religiosa: Inmaculada Concepción (8 de diciembre).",
    ),
    (
        ("natividad", "navidad", "christmas"),
        "Festividad religiosa: Natividad del Señor (Navidad, 25 de diciembre).",
    ),
]


def descripcion_festivo_es(titulo: str) -> str:
    """Breve explicación en español según palabras clave del nombre del festivo."""
    t = _norm_busqueda(titulo)
    for claves, texto in _PATRON_DESCRIPCION:
        if any(c in t for c in claves):
            return texto
    return (
        "Festivo incluido en el calendario laboral oficial de España según ámbito estatal o autonómico "
        "(fuente: datos del paquete holidays alineado con BOE)."
    )

# Subdivisiones CCAA reconocidas por holidays.Spain (códigos de entidad autónoma)
SUBDIV_CCAA: dict[str, str | None] = {
    "comunidad_valenciana": "VC",
    "valenciana": "VC",
    "valencia": "VC",
    "pais_valenciano": "VC",
    "cataluna": "CT",
    "catalunya": "CT",
    "andalucia": "AN",
    "aragon": "AR",
    "asturias": "AS",
    "cantabria": "CB",
    "castilla_leon": "CL",
    "castilla_la_mancha": "CM",
    "canarias": "CN",
    "extremadura": "EX",
    "galicia": "GA",
    "baleares": "IB",
    "murcia": "MC",
    "madrid": "MD",
    "navarra": "NC",
    "pais_vasco": "PV",
    "la_rioja": "RI",
    "ceuta": "CE",
    "melilla": "ML",
    "espana": None,
    "nacional": None,
    "estado": None,
}


def holidays_spain_tuples(subdiv_code: str | None, years: list[int]) -> list[tuple[str, str, str]]:
    """
    Devuelve lista (YYYY-MM-DD, nombre en español, notas con explicación).
    Fija language='es' para no depender del idioma del sistema (evita títulos en inglés).
    subdiv_code: código holidays (p.ej. 'VC') o None solo para festivos de ámbito estatal.
    """
    import holidays

    years = [int(y) for y in years if y]
    if not years:
        years = [date.today().year]
    merged: dict[date, str] = {}
    kwargs: dict = {"years": years, "language": "es"}
    if subdiv_code is None:
        h = holidays.Spain(**kwargs)
    else:
        h = holidays.Spain(subdiv=subdiv_code, **kwargs)
    for d, name in sorted(h.items()):
        merged[d] = str(name).strip()
    base_fuente = "Origen: calendario laboral oficial España (BOE / paquete holidays). Idioma: español."
    out: list[tuple[str, str, str]] = []
    for d, titulo in sorted(merged.items()):
        desc = descripcion_festivo_es(titulo)
        ambito = (
            f"Ámbito: comunidad autónoma ({subdiv_code})."
            if subdiv_code
            else "Ámbito: estatal (festivos que aplican en todo el Estado)."
        )
        notas = f"{base_fuente} {ambito} {desc}"
        out.append((d.isoformat(), titulo, notas))
    return out


# Opciones para el formulario admin: (código holidays, clau i18n page.cal.official_opt_*)
# Codi buit = només àmbit estatal (holidays.Spain sense subdiv).
OFFICIAL_SUBDIV_SPECS: tuple[tuple[str, str], ...] = (
    ("", "page.cal.official_opt_nat"),
    ("MD", "page.cal.official_opt_MD"),
    ("VC", "page.cal.official_opt_VC"),
    ("CT", "page.cal.official_opt_CT"),
    ("AN", "page.cal.official_opt_AN"),
    ("AR", "page.cal.official_opt_AR"),
    ("AS", "page.cal.official_opt_AS"),
    ("CB", "page.cal.official_opt_CB"),
    ("CE", "page.cal.official_opt_CE"),
    ("CL", "page.cal.official_opt_CL"),
    ("CM", "page.cal.official_opt_CM"),
    ("CN", "page.cal.official_opt_CN"),
    ("EX", "page.cal.official_opt_EX"),
    ("GA", "page.cal.official_opt_GA"),
    ("IB", "page.cal.official_opt_IB"),
    ("MC", "page.cal.official_opt_MC"),
    ("ML", "page.cal.official_opt_ML"),
    ("NC", "page.cal.official_opt_NC"),
    ("PV", "page.cal.official_opt_PV"),
    ("RI", "page.cal.official_opt_RI"),
)

OFFICIAL_SUBDIV_CODES: frozenset[str] = frozenset(c for c, _ in OFFICIAL_SUBDIV_SPECS)


def resolve_scope_to_subdiv(scope: str | None) -> str | None:
    """Convierte etiqueta semántica o código IA a código holidays o None (nacional)."""
    if not scope:
        return None
    s = str(scope).strip().upper()
    if s in ("NONE", "NULL", ""):
        return None
    # Código directo VC, AN, CT…
    if len(s) == 2 and s in (
        "VC",
        "AN",
        "AR",
        "AS",
        "CB",
        "CE",
        "CL",
        "CM",
        "CN",
        "CT",
        "EX",
        "GA",
        "IB",
        "MC",
        "MD",
        "ML",
        "NC",
        "PV",
        "RI",
    ):
        return s
    key = str(scope).strip().lower().replace(" ", "_").replace("-", "_")
    return SUBDIV_CCAA.get(key)
