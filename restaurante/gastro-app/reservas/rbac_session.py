"""Carga y comprobación de permisos en sesión Flask.

Jerarquía: SuperAdmin (PIN + rbac_super) > Gerente > Encargado > Empleado (rangos en BD).
"""
from __future__ import annotations

from flask import session

from models import get_db
from reservas.rbac_catalog import CODIGOS_EMP, CODIGOS_MOD
from reservas.rbac_schema import ensure_rbac_tables, permisos_de_rango


def rbac_super() -> bool:
    return bool(session.get("rbac_super"))


def rbac_permisos_set() -> set[str]:
    raw = session.get("rbac_permisos")
    if not raw:
        return set()
    if isinstance(raw, (list, tuple, set)):
        return {str(x) for x in raw if x}
    return set()


def puede(codigo: str) -> bool:
    if rbac_super():
        return True
    return codigo in rbac_permisos_set()


def cargar_permisos_empleado(empleado_id: int) -> None:
    """Tras login empleado: rellena rbac_permisos según rango_id."""
    session.pop("rbac_super", None)
    db = get_db()
    try:
        ensure_rbac_tables(db)
        row = db.execute(
            "SELECT rango_id FROM empleados WHERE id = ?",
            (empleado_id,),
        ).fetchone()
        rid = row["rango_id"] if row and row["rango_id"] is not None else 1
        perms = permisos_de_rango(db, int(rid))
        session["rbac_permisos"] = sorted(perms)
        session["rango_id"] = int(rid)
    finally:
        db.close()


def marcar_superadmin() -> None:
    """Tras login admin por PIN: acceso total."""
    session["rbac_super"] = True
    session["rbac_permisos"] = sorted(set(CODIGOS_MOD) | set(CODIGOS_EMP))
    session.pop("rango_id", None)


def limpiar_rbac_sesion() -> None:
    session.pop("rbac_super", None)
    session.pop("rbac_permisos", None)
    session.pop("rango_id", None)


def tiene_algun_modulo_backoffice() -> bool:
    """True si debe mostrarse la barra de administración (PIN admin o empleado con algún mod.*)."""
    if session.get("rol") == "admin" and session.get("admin_logueado"):
        return True
    if rbac_super():
        return True
    return any(p.startswith("mod.") for p in rbac_permisos_set())
