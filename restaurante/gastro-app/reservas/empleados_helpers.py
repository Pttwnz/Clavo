"""Validación y mapeo formulario ↔ fila empleado."""

from __future__ import annotations

from datetime import date

from reservas.db_helpers import columnas_tabla

# Orden preferido para INSERT/UPDATE dinámico
EMPLEADO_FIELD_ORDER: tuple[str, ...] = (
    "pin",
    "rango_id",
    "nombre",
    "apellido",
    "dni",
    "telefono",
    "email",
    "numero_ss",
    "puesto",
    "departamento",
    "categoria_servicio",
    "horas_contrato",
    "tipo_contrato",
    "activo",
    "observaciones",
    "fecha_alta",
    "fecha_nacimiento",
    "foto_perfil",
)


def _strip(s: str | None) -> str:
    return (s or "").strip()


def datos_empleado_desde_form(form, *, fecha_alta_default: str | None = None) -> dict[str, object]:
    """Lee campos del formulario POST en un dict listo para persistir."""
    hoy = date.today().strftime("%Y-%m-%d")
    fa = _strip(form.get("fecha_alta"))
    if not fa:
        fa = fecha_alta_default or hoy
    activo_raw = form.get("activo")
    activo = 1 if (activo_raw is None or str(activo_raw) == "1") else 0
    try:
        rango_id = int(form.get("rango_id") or 1)
    except (TypeError, ValueError):
        rango_id = 1
    if rango_id < 1:
        rango_id = 1
    horas = _strip(form.get("horas_contrato"))
    if not horas:
        horas = "40"
    return {
        "pin": _strip(form.get("pin")),
        "rango_id": rango_id,
        "nombre": _strip(form.get("nombre")),
        "apellido": _strip(form.get("apellido")),
        "dni": _strip(form.get("dni")),
        "telefono": _strip(form.get("telefono")),
        "email": _strip(form.get("email")),
        "numero_ss": _strip(form.get("numero_ss")),
        "puesto": _strip(form.get("puesto")),
        "departamento": _strip(form.get("departamento")),
        "categoria_servicio": _strip(form.get("categoria_servicio")),
        "horas_contrato": horas,
        "tipo_contrato": _strip(form.get("tipo_contrato")) or "Indefinido",
        "activo": activo,
        "observaciones": _strip(form.get("observaciones")),
        "fecha_alta": fa,
        "fecha_nacimiento": _strip(form.get("fecha_nacimiento")),
    }


def normalizar_dni(dni: str) -> str:
    return dni.upper().replace(" ", "")


def normalizar_pin(pin: str | None) -> str:
    """PIN tal como debe compararse (sin espacios laterales)."""
    return (pin or "").strip()


def pin_en_uso(db, pin: str, excluir_id: int | None = None) -> bool:
    """True si otro empleado ya usa ese PIN (el login solo admite uno por valor)."""
    p = normalizar_pin(pin)
    if not p:
        return False
    if excluir_id is not None:
        r = db.execute(
            """
            SELECT id FROM empleados
            WHERE TRIM(COALESCE(pin, '')) = ? AND id != ?
            LIMIT 1
            """,
            (p, excluir_id),
        ).fetchone()
    else:
        r = db.execute(
            """
            SELECT id FROM empleados
            WHERE TRIM(COALESCE(pin, '')) = ?
            LIMIT 1
            """,
            (p,),
        ).fetchone()
    return r is not None


def dni_en_uso(db, dni_norm: str, excluir_id: int | None = None) -> bool:
    """True si otro empleado ya usa ese DNI (no vacío)."""
    if not dni_norm:
        return False
    if excluir_id is not None:
        r = db.execute(
            """
            SELECT id FROM empleados
            WHERE REPLACE(UPPER(TRIM(COALESCE(dni,''))), ' ', '') = ?
              AND id != ?
            LIMIT 1
            """,
            (dni_norm, excluir_id),
        ).fetchone()
    else:
        r = db.execute(
            """
            SELECT id FROM empleados
            WHERE REPLACE(UPPER(TRIM(COALESCE(dni,''))), ' ', '') = ?
            LIMIT 1
            """,
            (dni_norm,),
        ).fetchone()
    return r is not None


def columnas_para_insert_update(db) -> list[str]:
    """Columnas existentes en la tabla, en orden estable."""
    cols = columnas_tabla(db, "empleados")
    return [k for k in EMPLEADO_FIELD_ORDER if k in cols]


def fila_para_insert(db, data: dict[str, object]) -> tuple[list[str], list[object]]:
    """Lista de columnas y valores para INSERT (solo claves presentes en tabla y en data)."""
    keys = columnas_para_insert_update(db)
    present = []
    vals: list[object] = []
    for k in keys:
        if k not in data:
            continue
        present.append(k)
        vals.append(data[k])
    return present, vals


def sets_para_update(db, data: dict[str, object], excluir: frozenset[str] | None = None) -> tuple[str, list[object]]:
    """Fragmento SET y valores para UPDATE."""
    excluir = excluir or frozenset()
    keys = [k for k in columnas_para_insert_update(db) if k in data and k not in excluir]
    parts = [f"{k}=?" for k in keys]
    vals = [data[k] for k in keys]
    return ", ".join(parts), vals
