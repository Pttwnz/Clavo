"""Directorio de proveedores: contacto, productos y condiciones de compra."""
from datetime import datetime

from flask import flash, redirect, render_template, request, url_for

from models import get_db
from reservas.decorators import login_requerido, permiso_mod
from reservas.proveedores_schema import ensure_proveedores_table, listar_proveedores

from . import bp


def _strip(s):
    return (s or "").strip()


def _datos_form(form) -> dict:
    return {
        "nombre": _strip(form.get("nombre")),
        "persona_contacto": _strip(form.get("persona_contacto")),
        "telefono": _strip(form.get("telefono")),
        "email": _strip(form.get("email")),
        "web": _strip(form.get("web")),
        "direccion": _strip(form.get("direccion")),
        "cif": _strip(form.get("cif")),
        "productos": _strip(form.get("productos")),
        "condiciones_compra": _strip(form.get("condiciones_compra")),
        "dia_habitual_pedido": _strip(form.get("dia_habitual_pedido")),
        "plazo_entrega": _strip(form.get("plazo_entrega")),
        "notas": _strip(form.get("notas")),
        "activo": 1 if form.get("activo") else 0,
    }


@bp.route("/proveedores")
@login_requerido
@permiso_mod("mod.inventario")
def proveedores_index():
    db = get_db()
    ensure_proveedores_table(db)
    rows = listar_proveedores(db, solo_activos=False)
    proveedores = [dict(r) for r in rows]
    total = len(proveedores)
    activos = sum(1 for p in proveedores if int(p.get("activo") or 1) == 1)
    db.close()
    return render_template(
        "proveedores.html",
        mostrar_nav=True,
        proveedores=proveedores,
        total_proveedores=total,
        proveedores_activos=activos,
    )


@bp.route("/proveedores/crear", methods=["POST"])
@login_requerido
@permiso_mod("mod.inventario")
def proveedores_crear():
    data = _datos_form(request.form)
    if not data["nombre"]:
        flash("El nombre del proveedor es obligatorio.", "warning")
        return redirect(url_for("admin.proveedores_index"))

    db = get_db()
    ensure_proveedores_table(db)
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    db.execute(
        """
        INSERT INTO proveedores (
            nombre, persona_contacto, telefono, email, web, direccion, cif,
            productos, condiciones_compra, dia_habitual_pedido, plazo_entrega,
            notas, activo, creado_en, actualizado_en
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            data["nombre"],
            data["persona_contacto"] or None,
            data["telefono"] or None,
            data["email"] or None,
            data["web"] or None,
            data["direccion"] or None,
            data["cif"] or None,
            data["productos"] or None,
            data["condiciones_compra"] or None,
            data["dia_habitual_pedido"] or None,
            data["plazo_entrega"] or None,
            data["notas"] or None,
            data["activo"],
            ahora,
            ahora,
        ),
    )
    db.commit()
    db.close()
    flash(f"Proveedor «{data['nombre']}» registrado.", "success")
    return redirect(url_for("admin.proveedores_index"))


@bp.route("/proveedores/<int:pid>/editar", methods=["GET", "POST"])
@login_requerido
@permiso_mod("mod.inventario")
def proveedores_editar(pid):
    db = get_db()
    ensure_proveedores_table(db)
    row = db.execute("SELECT * FROM proveedores WHERE id = ?", (pid,)).fetchone()
    if not row:
        db.close()
        flash("Proveedor no encontrado.", "warning")
        return redirect(url_for("admin.proveedores_index"))

    if request.method == "POST":
        data = _datos_form(request.form)
        if not data["nombre"]:
            db.close()
            flash("El nombre del proveedor es obligatorio.", "warning")
            return redirect(url_for("admin.proveedores_editar", pid=pid))

        ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        db.execute(
            """
            UPDATE proveedores SET
                nombre = ?, persona_contacto = ?, telefono = ?, email = ?, web = ?,
                direccion = ?, cif = ?, productos = ?, condiciones_compra = ?,
                dia_habitual_pedido = ?, plazo_entrega = ?, notas = ?, activo = ?,
                actualizado_en = ?
            WHERE id = ?
            """,
            (
                data["nombre"],
                data["persona_contacto"] or None,
                data["telefono"] or None,
                data["email"] or None,
                data["web"] or None,
                data["direccion"] or None,
                data["cif"] or None,
                data["productos"] or None,
                data["condiciones_compra"] or None,
                data["dia_habitual_pedido"] or None,
                data["plazo_entrega"] or None,
                data["notas"] or None,
                data["activo"],
                ahora,
                pid,
            ),
        )
        db.commit()
        db.close()
        flash("Datos del proveedor actualizados.", "success")
        return redirect(url_for("admin.proveedores_index"))

    p = dict(row)
    db.close()
    return render_template("proveedores_editar.html", mostrar_nav=True, p=p)


@bp.route("/proveedores/<int:pid>/eliminar", methods=["POST"])
@login_requerido
@permiso_mod("mod.inventario")
def proveedores_eliminar(pid):
    db = get_db()
    ensure_proveedores_table(db)
    db.execute("DELETE FROM proveedores WHERE id = ?", (pid,))
    db.commit()
    db.close()
    flash("Proveedor eliminado del directorio.", "success")
    return redirect(url_for("admin.proveedores_index"))
