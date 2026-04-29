"""Inventario, alertas de stock y albaranes (escaneo / archivo + líneas)."""
from datetime import date

from flask import abort, flash, redirect, render_template, request, url_for
from models import get_db
from reservas.db_helpers import columnas_tabla
from reservas.decorators import login_requerido, permiso_mod

from . import bp


def _stock_ready(db):
    from reservas.stock_schema import ensure_stock_schema

    ensure_stock_schema(db)


@bp.route("/inventario")
@login_requerido
@permiso_mod("mod.inventario")
def inventario_index():
    db = get_db()
    _stock_ready(db)
    from reservas.stock_schema import contar_alertas_stock, ingredientes_bajo_minimo

    ing_cols = columnas_tabla(db, "ingredientes")
    if "stock_actual" not in ing_cols:
        db.close()
        flash("Ejecuta de nuevo la aplicación para crear las tablas de inventario.", "warning")
        return redirect(url_for("admin.panel"))

    rows = db.execute(
        """
        SELECT id, nombre, unidad, coste_unitario,
               COALESCE(stock_actual, 0) AS stock_actual,
               COALESCE(stock_minimo, 0) AS stock_minimo,
               stock_maximo
        FROM ingredientes
        ORDER BY nombre COLLATE NOCASE
        """
    ).fetchall()
    alertas = ingredientes_bajo_minimo(db)
    n_alertas = contar_alertas_stock(db)
    db.close()

    return render_template(
        "inventario/index.html",
        mostrar_nav=True,
        ingredientes=rows,
        alertas=alertas,
        n_alertas=n_alertas,
    )


@bp.route("/inventario/umbrales", methods=["POST"])
@login_requerido
@permiso_mod("mod.inventario")
def inventario_umbrales():
    db = get_db()
    _stock_ready(db)
    for key, val in request.form.items():
        if not key.startswith("min_"):
            continue
        try:
            iid = int(key.replace("min_", ""))
        except ValueError:
            continue
        try:
            mn = float((val or "0").replace(",", "."))
        except ValueError:
            mn = 0
        db.execute(
            "UPDATE ingredientes SET stock_minimo = ? WHERE id = ?",
            (max(0, mn), iid),
        )
    db.commit()
    db.close()
    flash("Umbrales de alerta actualizados.", "success")
    return redirect(url_for("admin.inventario_index"))


@bp.route("/inventario/ajuste", methods=["POST"])
@login_requerido
@permiso_mod("mod.inventario")
def inventario_ajuste():
    db = get_db()
    _stock_ready(db)
    from reservas.stock_schema import registrar_movimiento

    try:
        iid = int(request.form.get("ingrediente_id") or 0)
        cant = float((request.form.get("cantidad") or "0").replace(",", "."))
        motivo = (request.form.get("motivo") or "").strip() or "ajuste manual"
    except (TypeError, ValueError):
        db.close()
        flash("Datos de ajuste no válidos.", "danger")
        return redirect(url_for("admin.inventario_index"))

    if iid <= 0 or cant == 0:
        db.close()
        flash("Indica ingrediente y cantidad (distinta de cero).", "warning")
        return redirect(url_for("admin.inventario_index"))

    registrar_movimiento(db, iid, cant, "ajuste_inventario", notas=motivo)
    db.commit()
    db.close()
    flash("Movimiento de stock registrado.", "success")
    return redirect(url_for("admin.inventario_index"))


@bp.route("/inventario/movimientos")
@login_requerido
@permiso_mod("mod.inventario")
def inventario_movimientos():
    db = get_db()
    _stock_ready(db)
    lim = min(500, max(20, request.args.get("lim", type=int) or 200))
    rows = db.execute(
        f"""
        SELECT m.*, i.nombre AS ing_nombre, i.unidad
        FROM movimientos_stock m
        JOIN ingredientes i ON i.id = m.ingrediente_id
        ORDER BY m.id DESC
        LIMIT {lim}
        """
    ).fetchall()
    db.close()
    return render_template(
        "inventario/movimientos.html",
        mostrar_nav=True,
        movimientos=rows,
        lim=lim,
    )


@bp.route("/inventario/albaranes")
@login_requerido
@permiso_mod("mod.inventario")
def inventario_albaranes():
    db = get_db()
    _stock_ready(db)
    rows = db.execute(
        "SELECT * FROM albaranes ORDER BY id DESC LIMIT 200"
    ).fetchall()
    db.close()
    return render_template(
        "inventario/albaranes.html",
        mostrar_nav=True,
        albaranes=rows,
    )


@bp.route("/inventario/albaran/nuevo", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.inventario")
def inventario_albaran_nuevo():
    from flask import current_app

    from reservas.stock_schema import guardar_archivo_albaran

    db = get_db()
    _stock_ready(db)

    if request.method == "POST":
        proveedor = (request.form.get("proveedor") or "").strip()
        numero = (request.form.get("numero_documento") or "").strip()
        fecha = (request.form.get("fecha") or "").strip() or date.today().isoformat()
        notas = (request.form.get("notas") or "").strip()
        archivo = request.files.get("escaneo")

        rel = None
        if archivo and getattr(archivo, "filename", None):
            rel = guardar_archivo_albaran(current_app.static_folder, archivo)
            if not rel:
                flash("Archivo no válido (PDF o imagen, máx. 8 MB).", "warning")

        db.execute(
            """
            INSERT INTO albaranes (proveedor, numero_documento, fecha, archivo_relativo, estado, notas)
            VALUES (?, ?, ?, ?, 'borrador', ?)
            """,
            (proveedor, numero, fecha, rel, notas or None),
        )
        db.commit()
        aid = int(db.execute("SELECT last_insert_rowid()").fetchone()[0])
        db.close()
        flash("Albarán creado. Añade líneas y confirma para cargar stock.", "success")
        return redirect(url_for("admin.inventario_albaran_edit", id=aid))

    db.close()
    return render_template(
        "inventario/albaran_nuevo.html",
        mostrar_nav=True,
        hoy=date.today().isoformat(),
    )


@bp.route("/inventario/albaran/<int:id>", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.inventario")
def inventario_albaran_edit(id):
    from flask import current_app

    from reservas.stock_schema import confirmar_albaran, guardar_archivo_albaran

    db = get_db()
    _stock_ready(db)
    alb = db.execute("SELECT * FROM albaranes WHERE id = ?", (id,)).fetchone()
    if not alb:
        db.close()
        abort(404)

    alb_d = dict(alb)
    if request.method == "POST":
        action = request.form.get("action")
        if action == "confirmar":
            ok, err = confirmar_albaran(db, id)
            if ok:
                flash("Albarán confirmado: entradas aplicadas al stock.", "success")
            else:
                flash(err, "danger")
            db.close()
            return redirect(url_for("admin.inventario_albaran_edit", id=id))

        if action == "linea":
            if alb_d.get("estado") == "confirmado":
                db.close()
                flash("No se pueden añadir líneas a un albarán ya confirmado.", "warning")
                return redirect(url_for("admin.inventario_albaran_edit", id=id))
            try:
                ing_id = int(request.form.get("ingrediente_id") or 0)
                cant = float((request.form.get("cantidad") or "0").replace(",", "."))
                precio = request.form.get("precio_unitario")
                pu = float(precio.replace(",", ".")) if precio else None
            except (TypeError, ValueError):
                db.close()
                flash("Línea no válida.", "danger")
                return redirect(url_for("admin.inventario_albaran_edit", id=id))
            if ing_id and cant > 0:
                db.execute(
                    """
                    INSERT INTO albaran_lineas (albaran_id, ingrediente_id, cantidad, precio_unitario)
                    VALUES (?, ?, ?, ?)
                    """,
                    (id, ing_id, cant, pu),
                )
                db.commit()
                flash("Línea añadida.", "success")
            return redirect(url_for("admin.inventario_albaran_edit", id=id))

        if action == "subir_escaneo":
            archivo = request.files.get("escaneo")
            if archivo and getattr(archivo, "filename", None):
                rel = guardar_archivo_albaran(current_app.static_folder, archivo)
                if rel:
                    db.execute(
                        "UPDATE albaranes SET archivo_relativo = ? WHERE id = ?",
                        (rel, id),
                    )
                    db.commit()
                    flash("Documento adjuntado.", "success")
                else:
                    flash("No se pudo guardar el archivo.", "warning")
            return redirect(url_for("admin.inventario_albaran_edit", id=id))

        proveedor = (request.form.get("proveedor") or "").strip()
        numero = (request.form.get("numero_documento") or "").strip()
        fecha = (request.form.get("fecha") or "").strip()
        notas = (request.form.get("notas") or "").strip()
        db.execute(
            """
            UPDATE albaranes SET proveedor=?, numero_documento=?, fecha=?, notas=?
            WHERE id=?
            """,
            (proveedor, numero, fecha, notas or None, id),
        )
        db.commit()
        flash("Cabecera actualizada.", "success")
        return redirect(url_for("admin.inventario_albaran_edit", id=id))

    lineas = db.execute(
        """
        SELECT l.*, i.nombre AS ing_nombre, i.unidad
        FROM albaran_lineas l
        JOIN ingredientes i ON i.id = l.ingrediente_id
        WHERE l.albaran_id = ?
        ORDER BY l.id
        """,
        (id,),
    ).fetchall()
    ings = db.execute(
        "SELECT id, nombre, unidad FROM ingredientes ORDER BY nombre COLLATE NOCASE"
    ).fetchall()
    db.close()

    return render_template(
        "inventario/albaran_edit.html",
        mostrar_nav=True,
        albaran=alb_d,
        lineas=lineas,
        ingredientes=ings,
    )


@bp.route("/inventario/albaran/<int:id>/eliminar", methods=["POST"])
@login_requerido
@permiso_mod("mod.inventario")
def inventario_albaran_eliminar(id):
    db = get_db()
    _stock_ready(db)
    r = db.execute("SELECT estado FROM albaranes WHERE id = ?", (id,)).fetchone()
    if not r:
        db.close()
        abort(404)
    if dict(r).get("estado") == "confirmado":
        db.close()
        flash("No se puede eliminar un albarán ya confirmado.", "danger")
        return redirect(url_for("admin.inventario_albaranes"))
    db.execute("DELETE FROM albaran_lineas WHERE albaran_id = ?", (id,))
    db.execute("DELETE FROM albaranes WHERE id = ?", (id,))
    db.commit()
    db.close()
    flash("Albarán eliminado.", "success")
    return redirect(url_for("admin.inventario_albaranes"))
