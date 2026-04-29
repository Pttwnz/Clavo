"""Cliente HTTP hacia la web Next (Prisma: visitas, carta, reservas por origen)."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any, Optional, Tuple

from config import NEXT_SITE_BASE_URL, NEXT_SITE_INTERNAL_SECRET


def next_site_base_url() -> str:
    return (NEXT_SITE_BASE_URL or "http://127.0.0.1:31047").rstrip("/")


def next_site_internal_secret() -> str:
    return (NEXT_SITE_INTERNAL_SECRET or "").strip()


def next_site_request(
    method: str,
    path: str,
    *,
    body: Any = None,
    timeout: int = 45,
) -> Tuple[int, Optional[Any], str]:
    """
    Devuelve (status_code, json_o_none, mensaje_error).
    Si falta secreto, status_code=0 y mensaje 'missing_secret'.
    """
    secret = next_site_internal_secret()
    if not secret:
        return 0, None, "missing_secret"

    base = next_site_base_url()
    p = path if path.startswith("/") else f"/{path}"

    headers = {
        "Authorization": f"Bearer {secret}",
        "Accept": "application/json",
    }
    payload_bytes: Optional[bytes] = None
    if body is not None:
        payload_bytes = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"

    def _bases() -> list[str]:
        roots = [base.rstrip("/")]
        alt: str | None = None
        if "://127.0.0.1:" in roots[0]:
            alt = roots[0].replace("://127.0.0.1:", "://localhost:", 1)
        elif "://localhost:" in roots[0]:
            alt = roots[0].replace("://localhost:", "://127.0.0.1:", 1)
        if alt and alt not in roots:
            roots.append(alt)
        return roots

    last_err = ""
    for base_try in _bases():
        url = f"{base_try}{p}"
        req = urllib.request.Request(url, data=payload_bytes, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                raw = resp.read().decode("utf-8", errors="replace")
                code = getattr(resp, "status", 200) or 200
                if not raw.strip():
                    return code, None, ""
                try:
                    return code, json.loads(raw), ""
                except json.JSONDecodeError:
                    return code, None, "invalid_json"
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
            try:
                return e.code, json.loads(raw) if raw.strip() else None, raw[:800]
            except json.JSONDecodeError:
                return e.code, None, raw[:800]
        except Exception as ex:  # noqa: BLE001
            msg = str(ex)[:800]
            last_err = msg
            # Reintentar solo fallos de red típicos (p. ej. 127.0.0.1 vs localhost en Windows).
            connish = any(
                x in msg.lower()
                for x in (
                    "refused",
                    "failed to establish",
                    "name or service not known",
                    "getaddrinfo failed",
                    "10061",
                    "10051",
                    "timed out",
                )
            )
            if connish and base_try != _bases()[-1]:
                continue
            return 0, None, msg
    return 0, None, last_err or "connection_failed"
