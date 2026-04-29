"""Rutas del blueprint admin permitidas cuando RESERVAS_ONLY está activo (solo reservas + sala + ajustes mínimos)."""


def admin_path_allowed_reservas_only(path: str) -> bool:
    if path in ("/panel", "/buscar_global", "/crear", "/reserva_autorizada"):
        return True
    if path.startswith("/panel/web"):
        return True
    if path.startswith("/reservas"):
        return True
    if path.startswith("/clientes"):
        return True
    if path.startswith("/api/clientes"):
        return True
    if path == "/editar_salon":
        return True
    if path in ("/mover_objeto", "/actualizar_objeto", "/crear_objeto"):
        return True
    if path.startswith("/eliminar_mesa/"):
        return True
    if path.startswith("/vaciar_esquema/"):
        return True
    if path.startswith("/api/union_mesas"):
        return True
    if path.startswith("/editar/"):
        return True
    if path.startswith("/actualizar/"):
        return True
    if path.startswith("/eliminar/"):
        return True
    if path.startswith("/estado/"):
        return True
    for pfx in (
        "/api/ocupacion_mesas",
        "/api/sugerencias_union_mesa",
        "/api/sala_mesas_opciones",
        "/api/reserva_estado",
        "/api/walkin",
        "/api/reserva_rapida",
    ):
        if path.startswith(pfx):
            return True
    if path.startswith("/configuracion_empresa"):
        return True
    if path.startswith("/configuracion_reservas_web"):
        return True
    if path.startswith("/configuracion_tablet"):
        return True
    if path.startswith("/configuracion_pin_tablet"):
        return True
    if path.startswith("/rangos_permisos"):
        return True
    return False
