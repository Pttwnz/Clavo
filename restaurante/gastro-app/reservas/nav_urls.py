"""URLs de entrada pública cuando Gastro comparte dominio con la web Next (raíz = web)."""
from __future__ import annotations

from flask import url_for

from config import MERGED_HOST_ROOT


def public_entry_endpoint() -> str:
    return "public.acceso_interno" if MERGED_HOST_ROOT else "public.inicio"


def public_entry_url(**kwargs) -> str:
    return url_for(public_entry_endpoint(), **kwargs)
