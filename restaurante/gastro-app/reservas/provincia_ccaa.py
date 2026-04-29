"""Inferir código CCAA (holidays España) a partir de provincia o CP (orientativo)."""
from __future__ import annotations

import re
import unicodedata


def _norm(s: str) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFD", str(s).strip().lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


# Provincias (50) → código holidays España (subdivisión autonómica)
_PROV_CCAA: dict[str, str] = {
    "alava": "PV",
    "albacete": "CM",
    "alicante": "VC",
    "almeria": "AN",
    "avila": "CL",
    "badajoz": "EX",
    "baleares": "IB",
    "barcelona": "CT",
    "vizcaya": "PV",
    "burgos": "CL",
    "caceres": "EX",
    "cadiz": "AN",
    "cantabria": "CB",
    "castellon": "VC",
    "ciudad real": "CM",
    "cordoba": "AN",
    "a coruna": "GA",
    "cuenca": "CM",
    "girona": "CT",
    "granada": "AN",
    "guadalajara": "CM",
    "guipuzcoa": "PV",
    "huelva": "AN",
    "huesca": "AR",
    "jaen": "AN",
    "leon": "CL",
    "lerida": "CT",
    "la rioja": "RI",
    "lugo": "GA",
    "madrid": "MD",
    "malaga": "AN",
    "murcia": "MC",
    "navarra": "NC",
    "orense": "GA",
    "asturias": "AS",
    "palencia": "CL",
    "las palmas": "CN",
    "pontevedra": "GA",
    "salamanca": "CL",
    "santa cruz de tenerife": "CN",
    "segovia": "CL",
    "sevilla": "AN",
    "soria": "CL",
    "tarragona": "CT",
    "teruel": "AR",
    "toledo": "CM",
    "valencia": "VC",
    "valladolid": "CL",
    "zamora": "CL",
    "zaragoza": "AR",
    "ceuta": "CE",
    "melilla": "ML",
}


def ccaa_desde_provincia(provincia: str | None) -> str | None:
    """Devuelve código holidays (VC, AN…) o None."""
    k = _norm(provincia or "")
    if not k:
        return None
    if k in _PROV_CCAA:
        return _PROV_CCAA[k]
    # Variantes comunes
    if k == "valencia" or k == "valenciana":
        return "VC"
    if k == "illes balears" or k == "islas baleares":
        return "IB"
    if k == "guipuzcoa" or k == "gipuzkoa":
        return "PV"
    if k == "vizcaya" or k == "bizkaia":
        return "PV"
    if k == "alava" or k == "araba":
        return "PV"
    if k == "castello" or k == "castellon de la plana":
        return "VC"
    if k == "lleida":
        return "CT"
    if k == "orense" or k == "ourense":
        return "GA"
    if k == "la coruna" or k == "coruna":
        return "GA"
    return None


# Primeros dos dígitos CP → provincia típica (INE) → solo como respaldo
_CP_PREF: dict[str, str] = {
    "01": "PV",
    "02": "CM",
    "03": "VC",
    "04": "AN",
    "05": "CL",
    "06": "EX",
    "07": "IB",
    "08": "CT",
    "09": "CL",
    "10": "EX",
    "11": "AN",
    "12": "VC",
    "13": "CM",
    "15": "GA",
    "16": "CM",
    "17": "CT",
    "18": "AN",
    "19": "CM",
    "20": "PV",
    "21": "AN",
    "22": "AR",
    "23": "AN",
    "24": "CL",
    "25": "CT",
    "26": "RI",
    "27": "GA",
    "28": "MD",
    "29": "AN",
    "30": "MC",
    "31": "NC",
    "32": "GA",
    "33": "AS",
    "34": "CL",
    "35": "CN",
    "36": "GA",
    "37": "CL",
    "38": "CN",
    "39": "CB",
    "40": "CL",
    "41": "AN",
    "42": "CL",
    "43": "CT",
    "44": "AR",
    "45": "CM",
    "46": "VC",
    "47": "CL",
    "48": "PV",
    "49": "CL",
    "50": "AR",
    "51": "CE",
    "52": "ML",
}


def ccaa_desde_codigo_postal(cp: str | None) -> str | None:
    d = re.sub(r"\D", "", (cp or "")[:5])
    if len(d) < 2:
        return None
    return _CP_PREF.get(d[:2])
