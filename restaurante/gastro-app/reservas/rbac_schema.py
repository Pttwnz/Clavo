"""Rangos y permisos por empleado (visibilidad y acceso a módulos).

Jerarquía de autoridad (de mayor a menor):
1. SuperAdmin — solo acceso con PIN de administrador (no es fila en `rangos`).
2. Gerente — rango en BD, panel completo según catálogo.
3. Encargado — operación; por defecto sin empresa ni escandallos (ajustable en el editor).
4. Empleado — portal empleado según casillas.
"""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe

T_RANGOS = "rangos"
T_RANGO_PERM = "rango_permisos"

# Orden numérico: mayor = más responsabilidad (para ORDER BY orden DESC).
ORDEN_EMPLEADO = 10
ORDEN_ENCARGADO = 20
ORDEN_GERENTE = 30

# Módulos que por defecto solo asigna el rango Gerente (Encargado puede activarse en el editor).
ENCARGADO_EXCLUYE_MOD: frozenset[str] = frozenset({"mod.empresa", "mod.escandallo"})


def ensure_rbac_tables(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_RANGOS} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            orden INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_RANGO_PERM} (
            rango_id INTEGER NOT NULL,
            permiso_codigo TEXT NOT NULL,
            PRIMARY KEY (rango_id, permiso_codigo)
        )
        """
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_rango_perm_rango ON {T_RANGO_PERM} (rango_id)"
    )
    if tabla_existe(db, "empleados"):
        cols = columnas_tabla(db, "empleados")
        if "rango_id" not in cols:
            db.execute("ALTER TABLE empleados ADD COLUMN rango_id INTEGER")
    db.commit()
    _seed_defaults(db)
    _migrate_jerarquia_rangos(db)


def _seed_defaults(db) -> None:
    """Rangos iniciales y permisos típicos si la tabla está vacía."""
    n = db.execute(f"SELECT COUNT(*) FROM {T_RANGOS}").fetchone()[0]
    if n > 0:
        return
    from reservas.rbac_catalog import CODIGOS_MOD, CODIGOS_EMP

    db.execute(
        f"""
        INSERT INTO {T_RANGOS} (id, nombre, descripcion, orden)
        VALUES
        (1, 'Empleado', 'Portal empleado; sin panel de gestión salvo lo marcado', {ORDEN_EMPLEADO}),
        (2, 'Encargado', 'Operación y equipo; por defecto sin empresa ni escandallos', {ORDEN_ENCARGADO}),
        (3, 'Gerente', 'Gestión completa del panel (misma base que el PIN salvo tareas solo superadmin)', {ORDEN_GERENTE})
        """
    )
    full_mod_emp = set(CODIGOS_MOD) | set(CODIGOS_EMP)
    enc_mod_emp = full_mod_emp - ENCARGADO_EXCLUYE_MOD
    # Gerente: catálogo completo
    for cod in full_mod_emp:
        db.execute(
            f"INSERT INTO {T_RANGO_PERM} (rango_id, permiso_codigo) VALUES (3, ?)",
            (cod,),
        )
    # Encargado: mismo conjunto menos módulos reservados a gerencia
    for cod in enc_mod_emp:
        db.execute(
            f"INSERT INTO {T_RANGO_PERM} (rango_id, permiso_codigo) VALUES (2, ?)",
            (cod,),
        )
    # Empleado: solo portal
    for cod in CODIGOS_EMP:
        db.execute(
            f"INSERT INTO {T_RANGO_PERM} (rango_id, permiso_codigo) VALUES (1, ?)",
            (cod,),
        )
    db.execute(
        "UPDATE empleados SET rango_id = 1 WHERE rango_id IS NULL",
    )
    db.commit()


def _migrate_jerarquia_rangos(db) -> None:
    """Nombres, orden y rango Gerente en instalaciones antiguas (idempotente)."""
    from reservas.rbac_catalog import CODIGOS_EMP, CODIGOS_MOD

    db.execute(
        f"UPDATE {T_RANGOS} SET nombre = 'Empleado' WHERE nombre = 'Personal'"
    )
    db.execute(
        f"UPDATE {T_RANGOS} SET nombre = 'Encargado' WHERE nombre = 'Encargado/a'"
    )
    db.execute(
        f"UPDATE {T_RANGOS} SET orden = {ORDEN_EMPLEADO} WHERE nombre = 'Empleado'"
    )
    db.execute(
        f"UPDATE {T_RANGOS} SET orden = {ORDEN_ENCARGADO} WHERE nombre = 'Encargado'"
    )

    tiene_ger = (
        db.execute(
            f"SELECT 1 FROM {T_RANGOS} WHERE nombre = 'Gerente' LIMIT 1"
        ).fetchone()
        is not None
    )
    if not tiene_ger:
        db.execute(
            f"""
            INSERT INTO {T_RANGOS} (nombre, descripcion, orden)
            VALUES ('Gerente', 'Gestión completa del panel (misma base que el PIN salvo tareas solo superadmin)', {ORDEN_GERENTE})
            """
        )
        gid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        full = set(CODIGOS_MOD) | set(CODIGOS_EMP)
        for cod in full:
            db.execute(
                f"INSERT INTO {T_RANGO_PERM} (rango_id, permiso_codigo) VALUES (?, ?)",
                (gid, cod),
            )
        row_enc = db.execute(
            f"SELECT id FROM {T_RANGOS} WHERE nombre = 'Encargado' LIMIT 1"
        ).fetchone()
        if row_enc:
            eid = int(row_enc[0])
            prev = permisos_de_rango(db, eid)
            trimmed = (prev & full) - ENCARGADO_EXCLUYE_MOD
            guardar_permisos_rango(db, eid, trimmed)

    db.execute(
        f"UPDATE {T_RANGOS} SET orden = {ORDEN_GERENTE} WHERE nombre = 'Gerente'"
    )
    db.commit()


def listar_rangos(db, *, jerarquia_desc: bool = False) -> list[dict]:
    """
    Lista rangos. `jerarquia_desc=True`: primero Gerente, luego Encargado, Empleado.
    """
    ensure_rbac_tables(db)
    order = "orden DESC, id DESC" if jerarquia_desc else "orden ASC, id ASC"
    return [dict(r) for r in db.execute(f"SELECT * FROM {T_RANGOS} ORDER BY {order}").fetchall()]


def permisos_de_rango(db, rango_id: int) -> set[str]:
    ensure_rbac_tables(db)
    rows = db.execute(
        f"SELECT permiso_codigo FROM {T_RANGO_PERM} WHERE rango_id = ?",
        (rango_id,),
    ).fetchall()
    return {str(r[0]) for r in rows if r[0]}


def guardar_permisos_rango(db, rango_id: int, codigos: set[str]) -> None:
    ensure_rbac_tables(db)
    db.execute(f"DELETE FROM {T_RANGO_PERM} WHERE rango_id = ?", (rango_id,))
    for c in sorted(codigos):
        c = (c or "").strip()
        if c:
            db.execute(
                f"INSERT INTO {T_RANGO_PERM} (rango_id, permiso_codigo) VALUES (?, ?)",
                (rango_id, c),
            )
    db.commit()
