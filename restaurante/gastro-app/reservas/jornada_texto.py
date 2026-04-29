"""Textos legals per conformitat del registre de jornada (ref. art. 34.9 ET)."""

from reservas.i18n import translate


def texto_conformidad_trabajador() -> str:
    """Text acceptat segons l'idioma de sessió (es desa a BD en enviar el formulari)."""
    return translate("page.conformidad.legal_body")
