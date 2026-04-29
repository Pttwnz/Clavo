"""
Windows / entornos restringidos: Pillow carga una DLL (_imaging) que a veces queda
bloqueada por antivirus o «Control de aplicaciones». ReportLab importa PIL al
arrancar; sin este parche, toda la generación de PDF falla.

Se instala un stub mínimo de PIL solo para que ReportLab importe; los PDF de
texto/tablas funcionan. El logo en PDF requiere Pillow real (ver pillow_usable()).
"""
from __future__ import annotations

import sys
import types


def pillow_usable() -> bool:
    try:
        from PIL import Image

        return callable(getattr(Image, "open", None))
    except Exception:
        return False


def _install_pil_stub() -> None:
    if pillow_usable():
        return
    for key in list(sys.modules.keys()):
        if key == "PIL" or key.startswith("PIL."):
            del sys.modules[key]
    pil = types.ModuleType("PIL")

    class Image:  # noqa: D106
        pass

    pil.Image = Image
    sys.modules["PIL"] = pil


def ensure_pil_stub_for_reportlab() -> None:
    """Llamar al iniciar la app y antes de importar ReportLab."""
    if not pillow_usable():
        _install_pil_stub()


ensure_pil_stub_for_reportlab()
