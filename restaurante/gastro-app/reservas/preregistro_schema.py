"""Solicitudes de preregistro de empleados en tablet (pendientes hasta que RRHH/admin las gestione)."""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe

T_PREREG_EMP = "preregistro_empleados"

# Columnas añadidas en versiones posteriores (instalaciones antiguas)
_COLUMNAS_EXTRA: tuple[tuple[str, str], ...] = (
    ("fecha_nacimiento", "TEXT"),
    ("horas_contrato", "TEXT"),
    ("tipo_contrato", "TEXT"),
    ("fecha_alta", "TEXT"),
    ("numero_ss", "TEXT"),
    ("rango_id", "INTEGER"),
    ("observaciones", "TEXT"),
    ("foto_perfil", "TEXT"),
)


def ensure_preregistro_tables(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_PREREG_EMP} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            apellido TEXT,
            dni TEXT,
            telefono TEXT,
            email TEXT,
            puesto TEXT,
            departamento TEXT,
            comentario TEXT,
            fecha_nacimiento TEXT,
            horas_contrato TEXT,
            tipo_contrato TEXT,
            fecha_alta TEXT,
            numero_ss TEXT,
            rango_id INTEGER,
            observaciones TEXT,
            estado TEXT NOT NULL DEFAULT 'pendiente',
            notas_admin TEXT,
            creado_en TEXT DEFAULT (datetime('now')),
            revisado_en TEXT
        )
        """
    )
    cols = columnas_tabla(db, T_PREREG_EMP)
    for nombre, sql_typ in _COLUMNAS_EXTRA:
        if nombre not in cols:
            db.execute(f"ALTER TABLE {T_PREREG_EMP} ADD COLUMN {nombre} {sql_typ}")
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_pregemp_estado ON {T_PREREG_EMP} (estado)")
    db.execute(f"CREATE INDEX IF NOT EXISTS idx_pregemp_creado ON {T_PREREG_EMP} (creado_en)")
    db.commit()


def insertar_preregistro_empleado(
    db,
    *,
    nombre: str,
    apellido: str | None = None,
    dni: str | None = None,
    telefono: str | None = None,
    email: str | None = None,
    puesto: str | None = None,
    departamento: str | None = None,
    fecha_nacimiento: str | None = None,
    horas_contrato: str | None = None,
    tipo_contrato: str | None = None,
    fecha_alta: str | None = None,
    numero_ss: str | None = None,
    rango_id: int | None = None,
    observaciones: str | None = None,
    foto_perfil: str | None = None,
) -> int:
    ensure_preregistro_tables(db)
    db.execute(
        f"""
        INSERT INTO {T_PREREG_EMP} (
            nombre, apellido, dni, telefono, email, puesto, departamento,
            fecha_nacimiento, horas_contrato, tipo_contrato, fecha_alta, numero_ss,
            rango_id, observaciones, estado, foto_perfil
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendiente', ?)
        """,
        (
            nombre.strip(),
            (apellido or "").strip() or None,
            (dni or "").strip() or None,
            (telefono or "").strip() or None,
            (email or "").strip() or None,
            (puesto or "").strip() or None,
            (departamento or "").strip() or None,
            (fecha_nacimiento or "").strip() or None,
            (horas_contrato or "").strip() or None,
            (tipo_contrato or "").strip() or None,
            (fecha_alta or "").strip() or None,
            (numero_ss or "").strip() or None,
            int(rango_id) if rango_id is not None else None,
            (observaciones or "").strip() or None,
            (foto_perfil or "").strip() or None,
        ),
    )
    db.commit()
    return int(db.execute("SELECT last_insert_rowid()").fetchone()[0])


def listar_preregistros_pendientes(db) -> list[dict]:
    if not tabla_existe(db, T_PREREG_EMP):
        return []
    rows = db.execute(
        f"""
        SELECT * FROM {T_PREREG_EMP}
        WHERE LOWER(TRIM(estado)) = 'pendiente'
        ORDER BY creado_en ASC, id ASC
        """
    ).fetchall()
    return [dict(r) for r in rows]


def listar_preregistros_recientes(db, limite: int = 15) -> list[dict]:
    if not tabla_existe(db, T_PREREG_EMP):
        return []
    rows = db.execute(
        f"""
        SELECT * FROM {T_PREREG_EMP}
        WHERE LOWER(TRIM(estado)) != 'pendiente'
        ORDER BY COALESCE(revisado_en, '') DESC, id DESC
        LIMIT ?
        """,
        (limite,),
    ).fetchall()
    return [dict(r) for r in rows]


def contar_preregistros_pendientes(db) -> int:
    if not tabla_existe(db, T_PREREG_EMP):
        return 0
    r = db.execute(
        f"""
        SELECT COUNT(*) FROM {T_PREREG_EMP}
        WHERE LOWER(TRIM(estado)) = 'pendiente'
        """
    ).fetchone()
    return int(r[0]) if r else 0


def obtener_preregistro(db, pid: int) -> dict | None:
    if not tabla_existe(db, T_PREREG_EMP):
        return None
    row = db.execute(f"SELECT * FROM {T_PREREG_EMP} WHERE id = ?", (int(pid),)).fetchone()
    return dict(row) if row else None


def actualizar_estado_preregistro(
    db, pid: int, estado: str, notas_admin: str | None
) -> bool:
    """estado: aprobado | rechazado"""
    row = obtener_preregistro(db, pid)
    if not row:
        return False
    if (row.get("estado") or "").lower().strip() != "pendiente":
        return False
    from datetime import datetime

    rev = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cur = db.execute(
        f"""
        UPDATE {T_PREREG_EMP}
        SET estado = ?, notas_admin = ?, revisado_en = ?
        WHERE id = ? AND LOWER(TRIM(estado)) = 'pendiente'
        """,
        (estado, (notas_admin or "").strip() or None, rev, int(pid)),
    )
    db.commit()
    return (getattr(cur, "rowcount", 0) or 0) > 0
