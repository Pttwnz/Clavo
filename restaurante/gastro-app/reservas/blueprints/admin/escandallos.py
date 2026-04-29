"""Escandallos: ingredientes, platos y costes."""
from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.decorators import login_requerido, permiso_mod

from . import bp


def _coste_plato(db, plato_id: int) -> tuple[float, str]:
    """Devuelve (coste total €, texto desglose)."""
    rows = db.execute(
        """
        SELECT pi.cantidad, i.coste_unitario, i.nombre, i.unidad
        FROM plato_ingredientes pi
        JOIN ingredientes i ON i.id = pi.ingrediente_id
        WHERE pi.plato_id = ?
        """,
        (plato_id,),
    ).fetchall()
    total = 0.0
    lineas = []
    for r in rows:
        sub = float(r["cantidad"]) * float(r["coste_unitario"])
        total += sub
        lineas.append(
            f"- {r['nombre']}: {r['cantidad']} {r['unidad']} × {r['coste_unitario']:.2f} € = {sub:.2f} €"
        )
    return total, "\n".join(lineas)


@bp.route("/escandallos")
@login_requerido
@permiso_mod("mod.escandallo")
def escandallos_index():
    """Listado de ingredientes y platos (calculadora de costes)."""
    db = get_db()
    ingredientes = db.execute(
        "SELECT * FROM ingredientes ORDER BY nombre COLLATE NOCASE"
    ).fetchall()
    platos = db.execute(
        "SELECT * FROM platos ORDER BY nombre COLLATE NOCASE"
    ).fetchall()
    costes = {}
    for p in platos:
        c, _ = _coste_plato(db, p["id"])
        costes[p["id"]] = c
    db.close()
    return render_template(
        "escandallos.html",
        mostrar_nav=True,
        ingredientes=ingredientes,
        platos=platos,
        costes=costes,
    )


@bp.route("/escandallos/ingrediente", methods=["POST"])
@login_requerido
@permiso_mod("mod.escandallo")
def escandallos_crear_ingrediente():
    """Alta rápida de ingrediente."""
    nombre = (request.form.get("nombre") or "").strip()
    unidad = (request.form.get("unidad") or "kg").strip()
    try:
        coste = float(request.form.get("coste_unitario") or 0)
    except ValueError:
        coste = 0.0
    if not nombre:
        flash("Indica el nombre del ingrediente.", "warning")
        return redirect(url_for("admin.escandallos_index"))
    db = get_db()
    db.execute(
        "INSERT INTO ingredientes (nombre, unidad, coste_unitario) VALUES (?,?,?)",
        (nombre, unidad, coste),
    )
    db.commit()
    db.close()
    flash("Ingrediente guardado.", "success")
    return redirect(url_for("admin.escandallos_index"))


@bp.route("/escandallos/plato", methods=["POST"])
@login_requerido
@permiso_mod("mod.escandallo")
def escandallos_crear_plato():
    """Crea un plato vacío y abre su ficha."""
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("Indica el nombre del plato.", "warning")
        return redirect(url_for("admin.escandallos_index"))
    db = get_db()
    cur = db.execute(
        "INSERT INTO platos (nombre, descripcion, precio_venta) VALUES (?,?,?)",
        (nombre, request.form.get("descripcion") or "", None),
    )
    pid = cur.lastrowid
    db.commit()
    db.close()
    return redirect(url_for("admin.escandallos_plato", id=pid))


@bp.route("/escandallos/plato/<int:id>", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.escandallo")
def escandallos_plato(id):
    """Ficha del plato: líneas de escandallo y cálculo de margen."""
    db = get_db()
    plato = db.execute("SELECT * FROM platos WHERE id=?", (id,)).fetchone()
    if not plato:
        db.close()
        flash("Plato no encontrado.", "danger")
        return redirect(url_for("admin.escandallos_index"))

    if request.method == "POST":
        accion = request.form.get("accion")
        if accion == "meta":
            try:
                pvp = request.form.get("precio_venta")
                pvp_f = float(pvp) if pvp not in (None, "") else None
            except ValueError:
                pvp_f = None
            db.execute(
                """
                UPDATE platos SET nombre=?, descripcion=?, precio_venta=?
                WHERE id=?
                """,
                (
                    (request.form.get("nombre") or plato["nombre"]).strip(),
                    request.form.get("descripcion") or "",
                    pvp_f,
                    id,
                ),
            )
            db.commit()
            flash("Datos del plato actualizados.", "success")
        elif accion == "linea":
            try:
                ing_id = int(request.form.get("ingrediente_id"))
                cant = float(request.form.get("cantidad") or 0)
            except (ValueError, TypeError):
                ing_id, cant = 0, 0
            if ing_id and cant > 0:
                db.execute(
                    """
                    INSERT INTO plato_ingredientes (plato_id, ingrediente_id, cantidad)
                    VALUES (?,?,?)
                    """,
                    (id, ing_id, cant),
                )
                db.commit()
                flash("Ingrediente añadido al escandallo.", "success")
        elif accion == "borrar_linea":
            try:
                lid = int(request.form.get("linea_id"))
            except (ValueError, TypeError):
                lid = 0
            if lid:
                db.execute(
                    "DELETE FROM plato_ingredientes WHERE id=? AND plato_id=?",
                    (lid, id),
                )
                db.commit()
                flash("Línea eliminada.", "info")

        plato = db.execute("SELECT * FROM platos WHERE id=?", (id,)).fetchone()

    lineas = db.execute(
        """
        SELECT pi.id, pi.cantidad, i.id AS ing_id, i.nombre, i.unidad, i.coste_unitario
        FROM plato_ingredientes pi
        JOIN ingredientes i ON i.id = pi.ingrediente_id
        WHERE pi.plato_id = ?
        ORDER BY i.nombre
        """,
        (id,),
    ).fetchall()
    ingredientes = db.execute(
        "SELECT * FROM ingredientes ORDER BY nombre COLLATE NOCASE"
    ).fetchall()
    coste_total, detalle_txt = _coste_plato(db, id)
    db.close()

    margen_pct = None
    if plato["precio_venta"] and coste_total > 0:
        try:
            margen_pct = (
                (float(plato["precio_venta"]) - coste_total)
                / float(plato["precio_venta"])
            ) * 100
        except Exception:
            margen_pct = None

    return render_template(
        "escandallos_plato.html",
        mostrar_nav=True,
        plato=plato,
        lineas=lineas,
        ingredientes=ingredientes,
        coste_total=coste_total,
        detalle_txt=detalle_txt,
        margen_pct=margen_pct,
    )


@bp.route("/escandallos/plato/<int:id>/eliminar", methods=["POST"])
@login_requerido
@permiso_mod("mod.escandallo")
def escandallos_eliminar_plato(id):
    """Elimina un plato y sus líneas."""
    db = get_db()
    db.execute("DELETE FROM plato_ingredientes WHERE plato_id=?", (id,))
    db.execute("DELETE FROM platos WHERE id=?", (id,))
    db.commit()
    db.close()
    flash("Plato eliminado.", "info")
    return redirect(url_for("admin.escandallos_index"))
