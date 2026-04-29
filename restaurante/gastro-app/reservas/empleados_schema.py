"""Columnas opcionales de la tabla empleados (evolución del esquema SQLite)."""

from reservas.db_helpers import columnas_tabla, tabla_existe


# (nombre_columna, SQL ALTER fragment — solo ADD COLUMN)
COLUMNAS_RRHH_OPCIONALES: tuple[tuple[str, str], ...] = (
    ("pin", "ALTER TABLE empleados ADD COLUMN pin TEXT"),
    ("apellido", "ALTER TABLE empleados ADD COLUMN apellido TEXT"),
    ("numero_ss", "ALTER TABLE empleados ADD COLUMN numero_ss TEXT"),
    ("horas_contrato", "ALTER TABLE empleados ADD COLUMN horas_contrato TEXT"),
    ("tipo_contrato", "ALTER TABLE empleados ADD COLUMN tipo_contrato TEXT"),
    ("activo", "ALTER TABLE empleados ADD COLUMN activo INTEGER DEFAULT 1"),
    ("observaciones", "ALTER TABLE empleados ADD COLUMN observaciones TEXT"),
    ("fecha_alta", "ALTER TABLE empleados ADD COLUMN fecha_alta TEXT"),
    ("email", "ALTER TABLE empleados ADD COLUMN email TEXT"),
    ("departamento", "ALTER TABLE empleados ADD COLUMN departamento TEXT"),
    (
        "categoria_servicio",
        "ALTER TABLE empleados ADD COLUMN categoria_servicio TEXT",
    ),
    ("fecha_nacimiento", "ALTER TABLE empleados ADD COLUMN fecha_nacimiento TEXT"),
    ("foto_perfil", "ALTER TABLE empleados ADD COLUMN foto_perfil TEXT"),
)


def ensure_empleados_rrhh_columns(db) -> None:
    """Añade columnas de RRHH que falten en `empleados`."""
    if not tabla_existe(db, "empleados"):
        return
    cols = columnas_tabla(db, "empleados")
    for nombre, sql in COLUMNAS_RRHH_OPCIONALES:
        if nombre not in cols:
            db.execute(sql)
