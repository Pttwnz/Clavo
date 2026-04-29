"""Guardado de imágenes de mesa subidas desde el editor (bajo static/uploads/mesas)."""
from __future__ import annotations

import os
import uuid
from typing import TYPE_CHECKING

from werkzeug.utils import secure_filename

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

MAX_MESA_IMAGE_BYTES = 2 * 1024 * 1024
ALLOWED_EXT = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
UPLOAD_SUBDIR = "uploads/mesas"


def _magic_ok(head: bytes) -> bool:
    if len(head) < 12:
        return False
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return True
    if head[:3] == b"\xff\xd8\xff":
        return True
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return True
    if head[:6] in (b"GIF87a", b"GIF89a"):
        return True
    return False


def save_mesa_upload(static_root: str | None, file_storage: "FileStorage | None") -> str | None:
    """
    Guarda un archivo de imagen válido y devuelve la ruta relativa a static
    (p. ej. uploads/mesas/abc123.png), o None si no es válido.
    """
    if not static_root or not file_storage or not getattr(file_storage, "filename", None):
        return None
    raw = secure_filename(str(file_storage.filename))
    if not raw:
        return None
    ext = os.path.splitext(raw)[1].lower()
    if ext not in ALLOWED_EXT:
        return None
    data = file_storage.read()
    if not data or len(data) > MAX_MESA_IMAGE_BYTES:
        return None
    if not _magic_ok(data[:64]):
        return None

    dest_dir = os.path.join(static_root, *UPLOAD_SUBDIR.split("/"))
    os.makedirs(dest_dir, exist_ok=True)
    new_name = f"{uuid.uuid4().hex}{ext}"
    full = os.path.join(dest_dir, new_name)
    with open(full, "wb") as f:
        f.write(data)
    return f"{UPLOAD_SUBDIR}/{new_name}".replace("\\", "/")

