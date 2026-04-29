"""Fotos de perfil de empleado (preregistro tablet y ficha RRHH)."""
from __future__ import annotations

import os
import shutil
import uuid
from typing import TYPE_CHECKING

from werkzeug.utils import secure_filename

if TYPE_CHECKING:
    from werkzeug.datastructures import FileStorage

MAX_FOTO_BYTES = 2 * 1024 * 1024
ALLOWED_EXT = frozenset({".png", ".jpg", ".jpeg", ".webp", ".gif"})
UPLOAD_SUBDIR = "uploads/empleados_perfil"


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


def guardar_foto_perfil_upload(static_root: str | None, file_storage: "FileStorage | None") -> str | None:
    """
    Guarda imagen de perfil bajo static/uploads/empleados_perfil/.
    Devuelve ruta relativa (p. ej. uploads/empleados_perfil/abc.jpg) o None.
    """
    if not static_root or not file_storage or not getattr(file_storage, "filename", None):
        return None
    raw = secure_filename(str(file_storage.filename))
    if not raw:
        return None
    ext = os.path.splitext(raw)[1].lower()
    if ext not in ALLOWED_EXT:
        ext = ".jpg"
    data = file_storage.read()
    if not data or len(data) > MAX_FOTO_BYTES:
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


def copiar_foto_perfil_a_empleado(static_root: str | None, rel_origen: str | None, empleado_id: int) -> str | None:
    """
    Copia el archivo de una ruta relativa a static (p. ej. foto de preregistro)
    a emp_{id}.ext y devuelve la nueva ruta relativa, o None.
    """
    if not static_root or not rel_origen:
        return None
    rel_origen = str(rel_origen).strip().replace("\\", "/")
    if ".." in rel_origen or not rel_origen.startswith("uploads/"):
        return None
    src = os.path.join(static_root, *rel_origen.split("/"))
    if not os.path.isfile(src):
        return None
    ext = os.path.splitext(src)[1].lower()
    if ext not in ALLOWED_EXT:
        ext = ".jpg"
    dest_rel = f"{UPLOAD_SUBDIR}/emp_{int(empleado_id)}{ext}"
    dest = os.path.join(static_root, *dest_rel.split("/"))
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    shutil.copy2(src, dest)
    return dest_rel.replace("\\", "/")
