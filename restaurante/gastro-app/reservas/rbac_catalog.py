"""Catálogo estable de códigos de permiso (clave interna → etiqueta UI)."""
from __future__ import annotations

# Módulos back-office (sesión admin o empleado con rango)
CODIGOS_MOD: tuple[str, ...] = (
    "mod.panel",
    "mod.calendario",
    "mod.horarios",
    "mod.servicio",
    "mod.servicio_tablet",
    "mod.cierre_caja",
    "mod.salon",
    "mod.empleados",
    "mod.rrhh",
    "mod.fichajes",
    "mod.vacaciones",
    "mod.inventario",
    "mod.empresa",
    "mod.escandallo",
)

# Portal empleado (barra empleado)
CODIGOS_EMP: tuple[str, ...] = (
    "emp.panel",
    "emp.area_personal",
    "emp.rrhh",
    "emp.reservas",
    "emp.conformidad",
)

LABELS_ES: dict[str, str] = {
    "mod.panel": "Panel principal (KPIs)",
    "mod.calendario": "Calendario (festivos, avisos)",
    "mod.horarios": "Horarios laborales (planificación, IA)",
    "mod.servicio": "Reservas y sala en vivo",
    "mod.servicio_tablet": "Opciones modo tablet y PIN tablet",
    "mod.cierre_caja": "Cierre de caja (panel)",
    "mod.salon": "Editor de salón / plano",
    "mod.empleados": "Empleados (alta, edición, listado)",
    "mod.rrhh": "Bandeja RRHH",
    "mod.fichajes": "Fichaje, historial, libro de firmas",
    "mod.vacaciones": "Vacaciones y jornada (resumen)",
    "mod.inventario": "Inventario, albaranes, movimientos, proveedores",
    "mod.empresa": "Datos de la empresa / marca",
    "mod.escandallo": "Escandallos / recetas",
    "emp.panel": "Portal · Inicio",
    "emp.area_personal": "Portal · Área personal / horarios",
    "emp.rrhh": "Portal · RRHH",
    "emp.reservas": "Portal · Reservas",
    "emp.conformidad": "Portal · Conformidad de jornada",
}


def etiqueta(codigo: str) -> str:
    return LABELS_ES.get(codigo, codigo)
