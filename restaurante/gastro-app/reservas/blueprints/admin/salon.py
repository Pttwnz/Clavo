"""Editor del plano del salón (TPV) y sincronización con reservas."""
import json
import os
from datetime import date

from flask import current_app, jsonify, render_template, request, url_for

from models import get_db
from reservas.decorators import login_requerido, permiso_mod, permiso_union_mesas_sala
from reservas.salon_assets import (
    discover_salon_assets,
    pick_imagen_capacidad,
    pick_imagen_decor,
    resolve_static_image,
    resolved_url_path,
)
from reservas.salon_uploads import save_mesa_upload
from reservas.sala_vivo import turno_visualizar_por_defecto
from reservas.salon_helpers import (
    bounds_plano_objetos,
    capacidad_union_mesas,
    es_tipo_mesa,
    ensure_salon_tables,
    get_esquema_activo_id,
    list_uniones_esquema_activo,
    list_objetos_esquema_completo,
    seed_salon_if_empty,
    sync_tabla_mesas_desde_objetos,
    vista_mesa_plano,
)

from . import bp


TIPOS_DECOR = frozenset(
    {"pared", "separador", "columna", "puerta", "ventana", "bano", "barra", "barril"}
)
# Mesas vectoriales (sin imagen) y mesa legacy opcional con foto
TIPOS_MESA = frozenset({"mesa", "mesa_redonda", "mesa_cuadrada"})
# Objetos dibujados en plantilla con CSS (sin archivo de imagen en disco)
TIPOS_DECOR_CSS = frozenset({"pared", "separador", "columna", "puerta", "ventana", "bano"})


def _dims_mesa(tipo_mesa: str, cap: int) -> tuple[float, float]:
    """Tamaño del hueco en px según forma y aforo (2–8)."""
    try:
        c = int(cap)
    except (TypeError, ValueError):
        c = 4
    c = max(2, min(8, c))
    if tipo_mesa == "mesa_redonda":
        s = {2: 80, 4: 96, 6: 112, 8: 128}.get(c, 96)
        return (float(s), float(s))
    w, h = {2: (80, 64), 4: (96, 80), 6: (112, 92), 8: (128, 100)}.get(c, (96, 80))
    return (float(w), float(h))


def _siguiente_nombre_mesa(db, esquema_id: int) -> str:
    n = db.execute(
        """
        SELECT COUNT(*) FROM objetos_salon
        WHERE esquema_id = ?
          AND LOWER(TRIM(COALESCE(tipo, ''))) IN ('mesa', 'mesa_redonda', 'mesa_cuadrada')
        """,
        (esquema_id,),
    ).fetchone()[0]
    return f"Mesa {int(n) + 1}"

PRESETS_DECOR = {
    "pared": (220.0, 16.0),
    "separador": (160.0, 8.0),
    "columna": (28.0, 28.0),
    "puerta": (56.0, 12.0),
    "ventana": (72.0, 56.0),
    "bano": (52.0, 48.0),
    "barra": (240.0, 48.0),
    "barril": (44.0, 44.0),
}


@bp.route("/editar_salon")
@login_requerido
@permiso_mod("mod.salon")
def editar_sala():
    """Editor visual del salón (planos y mesas)."""
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)

    salones = [dict(x) for x in db.execute("SELECT * FROM salones ORDER BY nombre").fetchall()]
    esquemas = [
        dict(x)
        for x in db.execute(
            """
            SELECT e.id, e.nombre, e.activo, e.salon_id, s.nombre AS salon_nombre
            FROM esquemas e
            JOIN salones s ON s.id = e.salon_id
            ORDER BY s.nombre, e.nombre
            """
        ).fetchall()
    ]

    req_eid = request.args.get("esquema_id", type=int)
    eid = req_eid if req_eid else get_esquema_activo_id(db)
    if req_eid:
        ex = db.execute(
            "SELECT id FROM esquemas WHERE id = ?",
            (req_eid,),
        ).fetchone()
        if not ex:
            eid = get_esquema_activo_id(db)

    objetos = list_objetos_esquema_completo(db, eid) if eid else []
    static_root = current_app.static_folder
    assets = discover_salon_assets(static_root)
    extra_mesa = [
        r
        for r in (assets.get("all") or [])
        if "mesa" in os.path.basename(r).lower()
    ]
    mesa_opts = list(dict.fromkeys((assets.get("mesa") or []) + extra_mesa))
    for o in objetos:
        if es_tipo_mesa(o.get("tipo")):
            cap = o.get("capacidad") or 4
            try:
                cap = int(cap)
            except (TypeError, ValueError):
                cap = 4
            o["vista"] = vista_mesa_plano(o.get("tipo"))
            o["img_static"] = None
            tlo = (o.get("tipo") or "").strip().lower()
            raw_img = (o.get("imagen") or "").strip()
            if tlo == "mesa" and raw_img:
                o["mesa_foto_rel"] = resolve_static_image(static_root, raw_img)
            else:
                o["mesa_foto_rel"] = None
        else:
            fb = pick_imagen_decor(static_root, (o.get("tipo") or "pared"))
            o["img_decor"] = resolved_url_path(static_root, o.get("imagen"), fb)

    plano_w, plano_h = bounds_plano_objetos(objetos)
    num_mesas = sum(1 for o in objetos if es_tipo_mesa(o.get("tipo")))
    uniones_mesas = list_uniones_esquema_activo(db)

    salon_id_actual = None
    for row in esquemas:
        if row["id"] == eid:
            salon_id_actual = row["salon_id"]
            break
    if salon_id_actual is None and esquemas:
        salon_id_actual = esquemas[0]["salon_id"]

    db.close()

    visualizar_url = url_for(
        "public.visualizar",
        fecha=str(date.today()),
        turno=turno_visualizar_por_defecto(),
    )

    return render_template(
        "editar_salon.html",
        mostrar_nav=True,
        salones=salones,
        esquemas=esquemas,
        esquema_activo_id=eid,
        salon_id_actual=salon_id_actual,
        objetos_plano=objetos,
        plano_ancho=plano_w,
        plano_alto=plano_h,
        num_mesas=num_mesas,
        mesa_imagenes=mesa_opts,
        uniones_mesas=uniones_mesas,
        visualizar_url=visualizar_url,
    )


@bp.route("/mover_objeto", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def mover_objeto():
    """Actualiza coordenadas de un objeto del salón (JSON)."""
    data = request.get_json(force=True, silent=True) or {}
    oid = data.get("id")
    x = data.get("x")
    y = data.get("y")
    if oid is None or x is None or y is None:
        return jsonify({"ok": False, "error": "Faltan datos"}), 400

    db = get_db()
    db.execute(
        "UPDATE objetos_salon SET x=?, y=? WHERE id=?",
        (float(x), float(y), int(oid)),
    )
    db.commit()
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/actualizar_objeto", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def actualizar_objeto():
    """Nombre, tamaño, rotación, capacidad."""
    data = request.get_json(force=True, silent=True) or {}
    oid = data.get("id")
    if not oid:
        return jsonify({"ok": False}), 400

    db = get_db()
    sets = []
    params = []
    for key, typ in (
        ("nombre", str),
        ("rotacion", float),
        ("width", float),
        ("height", float),
        ("capacidad", int),
        ("imagen", str),
    ):
        if key not in data or data[key] is None or data[key] == "":
            continue
        try:
            val = typ(data[key])
        except (TypeError, ValueError):
            continue
        sets.append(f"{key} = ?")
        params.append(val)

    if "tipo" in data and data["tipo"] is not None and str(data["tipo"]).strip() != "":
        t = str(data["tipo"]).strip().lower()
        if t in TIPOS_DECOR or t in TIPOS_MESA:
            sets.append("tipo = ?")
            params.append(t)

    if sets:
        params.append(int(oid))
        db.execute(
            f"UPDATE objetos_salon SET {', '.join(sets)} WHERE id = ?",
            tuple(params),
        )
        db.commit()

    # Renovar imagen de mesa si cambió capacidad (y no se fijó imagen en el mismo request)
    if "capacidad" in data and "imagen" not in data:
        row = db.execute(
            "SELECT capacidad, tipo FROM objetos_salon WHERE id=?",
            (int(oid),),
        ).fetchone()
        if row and (row["tipo"] or "").strip().lower() == "mesa":
            img = pick_imagen_capacidad(current_app.static_folder, row["capacidad"] or 4)
            db.execute(
                "UPDATE objetos_salon SET imagen=? WHERE id=?",
                (img, int(oid)),
            )
            db.commit()

    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/crear_objeto", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def crear_objeto():
    """Inserta una mesa o un elemento decorativo en el esquema indicado."""
    tipo_in = (request.form.get("tipo") or "mesa_cuadrada").strip().lower()
    if tipo_in not in TIPOS_DECOR and tipo_in not in TIPOS_MESA:
        tipo_in = "mesa_cuadrada"

    nombre = (request.form.get("nombre") or "").strip()
    capacidad = request.form.get("capacidad") or "4"
    esquema_id = request.form.get("esquema_id")
    imagen_mesa_elegida = (request.form.get("imagen_mesa") or "").strip()

    static_root = current_app.static_folder
    db = get_db()
    ensure_salon_tables(db)

    if esquema_id:
        try:
            eid = int(esquema_id)
        except ValueError:
            eid = get_esquema_activo_id(db)
    else:
        eid = get_esquema_activo_id(db)

    if not eid:
        db.close()
        return jsonify({"ok": False, "error": "No hay esquema activo"}), 400

    x_req = (request.form.get("x") or "").strip()
    y_req = (request.form.get("y") or "").strip()
    w_req = (request.form.get("width") or "").strip()
    h_req = (request.form.get("height") or "").strip()
    use_xy = False
    if x_req != "" and y_req != "":
        try:
            base_x = float(x_req)
            y0 = float(y_req)
            use_xy = True
        except ValueError:
            use_xy = False
    if not use_xy:
        cur = db.execute(
            """
            SELECT COALESCE(MAX(x), 80) AS mx FROM objetos_salon WHERE esquema_id = ?
            """,
            (eid,),
        ).fetchone()
        base_x = float(cur["mx"] or 80) + 40
        if base_x > 520:
            base_x = 100
        y0 = 120.0 if tipo_in in TIPOS_MESA else 100.0

    if tipo_in in TIPOS_MESA:
        try:
            cap = int(capacidad)
        except ValueError:
            cap = 4
        cap = max(2, min(8, cap))

        if tipo_in in ("mesa_redonda", "mesa_cuadrada"):
            if not nombre:
                nombre = _siguiente_nombre_mesa(db, eid)
            # Guardamos imagen sugerida por capacidad para poder usarla en vistas demo.
            imagen = pick_imagen_capacidad(static_root, cap)
            w, h = _dims_mesa(tipo_in, cap)
            if not use_xy:
                y0 = 120.0
        else:
            if not nombre:
                db.close()
                return jsonify({"ok": False, "error": "Nombre requerido"}), 400
            archivo_mesa = request.files.get("archivo_mesa")
            subida = (
                save_mesa_upload(static_root, archivo_mesa)
                if archivo_mesa and getattr(archivo_mesa, "filename", None)
                else None
            )
            if subida:
                imagen = subida
            elif imagen_mesa_elegida:
                resolved = resolve_static_image(static_root, imagen_mesa_elegida)
                imagen = resolved if resolved else pick_imagen_capacidad(static_root, cap)
            else:
                imagen = pick_imagen_capacidad(static_root, cap)
            w, h = _dims_mesa("mesa_cuadrada", cap)
            if not use_xy:
                y0 = 120.0
    else:
        w, h = PRESETS_DECOR[tipo_in]
        if not use_xy:
            y0 = 100.0
        labels = {
            "pared": "Pared",
            "separador": "Separador",
            "columna": "Columna",
            "puerta": "Puerta",
            "ventana": "Ventana",
            "bano": "Baño",
            "barra": "Barra",
            "barril": "Barril",
        }
        if not nombre:
            n = db.execute(
                "SELECT COUNT(*) FROM objetos_salon WHERE esquema_id = ? AND LOWER(TRIM(COALESCE(tipo,''))) = ?",
                (eid, tipo_in),
            ).fetchone()[0]
            nombre = f"{labels[tipo_in]} {int(n) + 1}"
        cap = 0
        if tipo_in in TIPOS_DECOR_CSS:
            imagen = ""
        else:
            imagen = pick_imagen_decor(static_root, tipo_in)

    # Permitir medidas custom (arrastre en editor), con mínimos de seguridad.
    if w_req:
        try:
            w = max(12.0, float(w_req))
        except ValueError:
            pass
    if h_req:
        try:
            h = max(8.0, float(h_req))
        except ValueError:
            pass

    db.execute(
        """
        INSERT INTO objetos_salon
        (esquema_id, nombre, tipo, x, y, width, height, rotacion, imagen, capacidad)
        VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?, ?)
        """,
        (eid, nombre, tipo_in, base_x, y0, w, h, imagen, cap),
    )
    db.commit()
    new_id = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    created = db.execute(
        """
        SELECT id, esquema_id, nombre, tipo, x, y, width, height, rotacion, capacidad, imagen
        FROM objetos_salon
        WHERE id = ?
        """,
        (new_id,),
    ).fetchone()
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    out = {"ok": True, "id": new_id}
    if created:
        o = dict(created)
        out["obj"] = {
            "id": int(o["id"]),
            "esquema_id": int(o["esquema_id"]),
            "nombre": o.get("nombre") or "",
            "tipo": (o.get("tipo") or "").strip().lower(),
            "x": float(o.get("x") or 0),
            "y": float(o.get("y") or 0),
            "width": float(o.get("width") or 80),
            "height": float(o.get("height") or 80),
            "rotacion": float(o.get("rotacion") or 0),
            "capacidad": int(o.get("capacidad") or 0),
            "imagen": (o.get("imagen") or "").strip(),
            "mesa_foto_rel": (
                resolve_static_image(current_app.static_folder, (o.get("imagen") or "").strip())
                if (o.get("tipo") or "").strip().lower() == "mesa"
                else None
            ),
        }
    return jsonify(out)


@bp.route("/eliminar_mesa/<int:id>", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def eliminar_mesa(id):
    """Elimina un objeto del salón por id."""
    db = get_db()
    db.execute("DELETE FROM objetos_salon WHERE id=?", (id,))
    db.commit()
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/vaciar_esquema/<int:eid>", methods=["POST"])
@login_requerido
@permiso_mod("mod.salon")
def vaciar_esquema(eid):
    """Elimina todos los objetos del plano (reinicia el esquema a vacío)."""
    db = get_db()
    db.execute("DELETE FROM objetos_salon WHERE esquema_id=?", (eid,))
    db.commit()
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True})


@bp.route("/api/union_mesas", methods=["GET"])
@login_requerido
@permiso_union_mesas_sala
def api_union_mesas_list():
    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    out = list_uniones_esquema_activo(db)
    db.close()
    return jsonify({"ok": True, "uniones": out})


@bp.route("/api/union_mesas", methods=["POST"])
@login_requerido
@permiso_union_mesas_sala
def api_union_mesas_crear():
    data = request.get_json(force=True, silent=True) or {}
    mesa_ids_in = data.get("mesa_ids") or []
    if not isinstance(mesa_ids_in, list):
        return jsonify({"ok": False, "error": "mesa_ids inválido"}), 400
    mesa_ids: list[int] = []
    for x in mesa_ids_in:
        try:
            v = int(x)
        except (TypeError, ValueError):
            continue
        if v > 0 and v not in mesa_ids:
            mesa_ids.append(v)
    if len(mesa_ids) < 2:
        return jsonify({"ok": False, "error": "Selecciona al menos 2 mesas"}), 400

    db = get_db()
    ensure_salon_tables(db)
    seed_salon_if_empty(db)
    eid = get_esquema_activo_id(db)
    if not eid:
        db.close()
        return jsonify({"ok": False, "error": "No hay esquema activo"}), 400

    qs = ",".join("?" for _ in mesa_ids)
    rows = db.execute(
        f"""
        SELECT id, nombre, capacidad
        FROM objetos_salon
        WHERE esquema_id = ?
          AND id IN ({qs})
          AND LOWER(TRIM(COALESCE(tipo,''))) IN ('mesa', 'mesa_redonda', 'mesa_cuadrada')
        """,
        tuple([eid] + mesa_ids),
    ).fetchall()
    if len(rows) < 2:
        db.close()
        return jsonify({"ok": False, "error": "No se pudieron cargar las mesas"}), 400

    nombres = [str(r["nombre"] or "").strip() for r in rows if str(r["nombre"] or "").strip()]
    if len(nombres) < 2:
        db.close()
        return jsonify({"ok": False, "error": "Las mesas deben tener nombre"}), 400
    caps: list[int] = []
    for r in rows:
        try:
            caps.append(int(r["capacidad"] or 0))
        except (TypeError, ValueError):
            pass
    cap_total = capacidad_union_mesas(caps)

    nombre = (data.get("nombre") or "").strip()
    if not nombre:
        nombre = "Unión " + " + ".join(nombres[:3])
        if len(nombres) > 3:
            nombre += "…"

    comp_json = json.dumps({"ids": mesa_ids, "nombres": nombres}, ensure_ascii=False)
    db.execute(
        """
        INSERT INTO mesa_uniones (esquema_id, nombre, componentes_json, capacidad_total, activa)
        VALUES (?, ?, ?, ?, 1)
        """,
        (eid, nombre, comp_json, max(2, cap_total)),
    )
    uid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True, "id": int(uid), "nombre": nombre, "capacidad_total": max(2, cap_total)})


@bp.route("/api/union_mesas/<int:union_id>", methods=["DELETE"])
@login_requerido
@permiso_union_mesas_sala
def api_union_mesas_borrar(union_id: int):
    db = get_db()
    ensure_salon_tables(db)
    db.execute("DELETE FROM mesa_uniones WHERE id = ?", (int(union_id),))
    sync_tabla_mesas_desde_objetos(db)
    db.commit()
    db.close()
    return jsonify({"ok": True})
