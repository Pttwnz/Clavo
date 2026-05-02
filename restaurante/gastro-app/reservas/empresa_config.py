"""Configuración de datos fiscales y de contacto del establecimiento (libro de firmas, PDFs)."""
from __future__ import annotations

import os

from werkzeug.utils import secure_filename

from reservas.branding import DEFAULT_PRIMARY, sanitize_hex_color
from reservas.db_helpers import columnas_tabla, tabla_existe


def _normalizar_hhmm(val: str, default: str) -> str:
    """HH:MM válido para inputs type=time o texto."""
    v = (val or "").strip()
    if not v:
        return default
    p = v.replace(".", ":").split(":")
    try:
        h = int(p[0])
        m = int(p[1]) if len(p) > 1 else 0
    except (ValueError, IndexError):
        return default
    if h == 24 and m == 0:
        return "24:00"
    h = max(0, min(23, h))
    m = max(0, min(59, m))
    return f"{h:02d}:{m:02d}"

TABLE = "config_empresa"
MAX_LOGO_BYTES = 2 * 1024 * 1024
LOGO_DIR = "uploads/empresa"
ALLOWED_LOGO = frozenset({".png", ".jpg", ".jpeg", ".webp"})


def ensure_config_empresa_table(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS config_empresa (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            razon_social TEXT,
            nombre_comercial TEXT,
            cif TEXT,
            direccion TEXT,
            codigo_postal TEXT,
            ciudad TEXT,
            provincia TEXT,
            telefono TEXT,
            email TEXT,
            nombre_dueno TEXT,
            logo_relativo TEXT,
            color_primario TEXT,
            color_acento TEXT,
            horario_empresa TEXT,
            franja_modo TEXT,
            franja_hasta_manana TEXT,
            franja_hasta_tarde TEXT,
            franja_corte_dos TEXT,
            franja_nombre_manana TEXT,
            franja_nombre_tarde TEXT,
            franja_nombre_noche TEXT
        )
        """
    )
    db.execute("INSERT OR IGNORE INTO config_empresa (id) VALUES (1)")
    db.commit()
    _migrate_empresa_cols(db)


def _migrate_empresa_cols(db) -> None:
    """Añade columnas nuevas en bases ya creadas."""
    if not tabla_existe(db, TABLE):
        return
    cols = columnas_tabla(db, TABLE)
    for name, decl in (
        ("color_primario", "TEXT"),
        ("color_acento", "TEXT"),
        ("nombre_dueno", "TEXT"),
        ("horario_empresa", "TEXT"),
        ("vacaciones_horas_trabajo_por_hora_vacacion", "REAL"),
        ("franja_modo", "TEXT"),
        ("franja_hasta_manana", "TEXT"),
        ("franja_hasta_tarde", "TEXT"),
        ("franja_corte_dos", "TEXT"),
        ("franja_nombre_manana", "TEXT"),
        ("franja_nombre_tarde", "TEXT"),
        ("franja_nombre_noche", "TEXT"),
        ("niveles_carga_semana", "TEXT"),
    ):
        if name not in cols:
            db.execute(f"ALTER TABLE {TABLE} ADD COLUMN {name} {decl}")
    if "vacaciones_horas_trabajo_por_hora_vacacion" in columnas_tabla(db, TABLE):
        db.execute(
            f"""
            UPDATE {TABLE}
            SET vacaciones_horas_trabajo_por_hora_vacacion = 13
            WHERE vacaciones_horas_trabajo_por_hora_vacacion IS NULL
            """
        )
    db.commit()


def get_config_empresa(db) -> dict:
    if not tabla_existe(db, TABLE):
        ensure_config_empresa_table(db)
    row = db.execute("SELECT * FROM config_empresa WHERE id = 1").fetchone()
    if not row:
        return {k: "" for k in _keys()}
    return dict(row)


def _keys():
    return (
        "razon_social",
        "nombre_comercial",
        "cif",
        "direccion",
        "codigo_postal",
        "ciudad",
        "provincia",
        "telefono",
        "email",
        "nombre_dueno",
        "logo_relativo",
        "color_primario",
        "color_acento",
        "horario_empresa",
        "vacaciones_horas_trabajo_por_hora_vacacion",
        "franja_modo",
        "franja_hasta_manana",
        "franja_hasta_tarde",
        "franja_corte_dos",
        "franja_nombre_manana",
        "franja_nombre_tarde",
        "franja_nombre_noche",
        "niveles_carga_semana",
    )


def save_config_empresa_form(db, form, *, only_update_present_keys: bool = False) -> None:
    """Actualiza campos de texto desde request.form.

    Si ``only_update_present_keys`` es True, solo se tocan columnas cuya clave
    aparece en el formulario (útil en formularios reducidos sin borrar el resto).
    """
    ensure_config_empresa_table(db)
    sets = []
    params = []
    for k in _keys():
        if k == "logo_relativo":
            continue
        if only_update_present_keys and k not in form:
            continue
        val = (form.get(k) or "").strip()
        if k == "vacaciones_horas_trabajo_por_hora_vacacion":
            if not val:
                val = "13"
            else:
                try:
                    x = float(str(val).replace(",", "."))
                    val = str(max(1.0, min(500.0, x)))
                except (ValueError, TypeError):
                    val = "13"
        if k == "color_primario":
            val = sanitize_hex_color(val, DEFAULT_PRIMARY) if val else ""
        elif k == "color_acento":
            val = sanitize_hex_color(val, "") if val else ""
        elif k == "franja_modo":
            val = val.lower() if val in ("tres", "dos") else "tres"
        elif k == "franja_hasta_manana":
            val = _normalizar_hhmm(val, "14:00")
        elif k == "franja_hasta_tarde":
            val = _normalizar_hhmm(val, "20:00")
        elif k == "franja_corte_dos":
            val = _normalizar_hhmm(val, "16:00")
        elif k == "niveles_carga_semana":
            if not val:
                continue
        sets.append(f"{k} = ?")
        params.append(val)
    if not sets:
        return
    params.append(1)
    db.execute(
        f"UPDATE config_empresa SET {', '.join(sets)} WHERE id = ?",
        tuple(params),
    )
    db.commit()


def save_logo_empresa(static_root: str, file_storage) -> str | None:
    """Guarda logo bajo static/uploads/empresa/. Devuelve ruta relativa o None."""
    if not static_root or not file_storage or not getattr(file_storage, "filename", None):
        return None
    raw = secure_filename(str(file_storage.filename))
    if not raw:
        return None
    ext = os.path.splitext(raw)[1].lower()
    if ext not in ALLOWED_LOGO:
        return None
    data = file_storage.read()
    if not data or len(data) > MAX_LOGO_BYTES:
        return None
    dest_dir = os.path.join(static_root, *LOGO_DIR.split("/"))
    os.makedirs(dest_dir, exist_ok=True)
    new_name = f"logo{ext}"
    full = os.path.join(dest_dir, new_name)
    with open(full, "wb") as f:
        f.write(data)
    return f"{LOGO_DIR}/{new_name}".replace("\\", "/")


def update_logo_path(db, rel: str) -> None:
    ensure_config_empresa_table(db)
    db.execute("UPDATE config_empresa SET logo_relativo = ? WHERE id = 1", (rel,))
    db.commit()
