"""Redirige peticiones al host legacy (p. ej. IP:puerto) hacia la URL pública (DNS)."""
from __future__ import annotations

import os
from urllib.parse import urlparse

from flask import Flask, redirect, request

from config import GASTRO_PUBLIC_BASE_URL


def _legacy_hosts() -> frozenset[str]:
    raw = (os.getenv("GASTRO_LEGACY_HOSTS") or "").strip()
    if not raw:
        return frozenset()
    return frozenset(h.strip().lower() for h in raw.split(",") if h.strip())


def register_legacy_host_redirect(app: Flask) -> None:
    """Si GASTRO_PUBLIC_BASE_URL y GASTRO_LEGACY_HOSTS están definidos, 302 al origen canónico."""

    @app.before_request
    def _redirect_legacy_host_to_canonical() -> object | None:
        if request.method == "OPTIONS":
            return None
        if request.path.startswith("/static"):
            return None

        public = (GASTRO_PUBLIC_BASE_URL or "").strip().rstrip("/")
        legacy = _legacy_hosts()
        if not public or not legacy:
            return None

        parsed = urlparse(public)
        if not parsed.scheme or not parsed.netloc:
            return None

        xfwd = (request.headers.get("X-Forwarded-Host") or "").split(",")[0].strip().lower()
        host = (xfwd or (request.host or "")).lower()
        if not host or host not in legacy:
            return None

        canon = parsed.netloc.lower()
        if host == canon:
            return None

        qs = request.query_string.decode("utf-8", "replace")
        path = request.path or "/"
        target = f"{parsed.scheme}://{parsed.netloc}{path}"
        if qs:
            target = f"{target}?{qs}"
        return redirect(target, code=302)
