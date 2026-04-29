"""Fichas de clientes (histórico de reservas por teléfono)."""
from __future__ import annotations

from flask import flash, jsonify, redirect, render_template, request, url_for

from models import get_db
from reservas.clientes_schema import (
    actualizar_ficha_cliente,
    buscar_clientes_autocomplete,
    ensure_clientes_schema,
    listar_clientes,
    obtener_cliente,
    reservas_de_cliente,
)
from reservas.decorators import permiso_reservas, permiso_reservas_api

from . import bp


@bp.route("/clientes")
@permiso_reservas
def lista_clientes():
    q = (request.args.get("q") or "").strip()
    db = get_db()
    ensure_clientes_schema(db)
    rows = listar_clientes(db, q=q or None, limit=250)
    clientes = [dict(r) for r in rows]
    db.close()
    return render_template(
        "clientes.html",
        mostrar_nav=True,
        clientes=clientes,
        q=q,
    )


@bp.route("/clientes/<int:cid>")
@permiso_reservas
def cliente_ficha(cid: int):
    db = get_db()
    ensure_clientes_schema(db)
    c = obtener_cliente(db, cid)
    if not c:
        db.close()
        flash("Cliente no encontrado.", "warning")
        return redirect(url_for("admin.lista_clientes"))
    reservas = [dict(x) for x in reservas_de_cliente(db, cid, limit=80)]
    db.close()
    return render_template(
        "cliente_ficha.html",
        mostrar_nav=True,
        cliente=dict(c),
        reservas_hist=reservas,
    )


@bp.route("/clientes/<int:cid>/actualizar", methods=["POST"])
@permiso_reservas
def cliente_actualizar(cid: int):
    nombre = (request.form.get("nombre") or "").strip()
    telefono = (request.form.get("telefono") or "").strip()
    email = (request.form.get("email") or "").strip()
    notas = (request.form.get("notas_internas") or "").strip()
    alergias = (request.form.get("alergias") or "").strip()
    preferencias = (request.form.get("preferencias") or "").strip()
    etiqueta = (request.form.get("etiqueta") or "").strip()
    vip = bool(request.form.get("vip"))
    if not nombre or not telefono:
        flash("Nombre y teléfono son obligatorios.", "warning")
        return redirect(url_for("admin.cliente_ficha", cid=cid))
    db = get_db()
    ensure_clientes_schema(db)
    ok, err = actualizar_ficha_cliente(
        db,
        cid,
        nombre=nombre,
        telefono=telefono,
        email=email or None,
        notas_internas=notas or None,
        alergias=alergias or None,
        preferencias=preferencias or None,
        etiqueta=etiqueta or None,
        vip=vip,
    )
    db.close()
    if not ok:
        if err == "telefono_invalido":
            flash("El teléfono debe tener al menos 5 dígitos para la ficha.", "danger")
        elif err == "telefono_duplicado":
            flash("Ya existe otro cliente con ese número normalizado.", "danger")
        else:
            flash("No se pudo guardar.", "danger")
        return redirect(url_for("admin.cliente_ficha", cid=cid))
    flash("Ficha actualizada.", "success")
    return redirect(url_for("admin.cliente_ficha", cid=cid))


@bp.route("/api/clientes/buscar")
@permiso_reservas_api
def api_clientes_buscar():
    q = (request.args.get("q") or "").strip()
    db = get_db()
    ensure_clientes_schema(db)
    rows = buscar_clientes_autocomplete(db, q, limit=15)
    out = []
    for r in rows:
        item = {
            "id": r["id"],
            "nombre": r["nombre"],
            "telefono": r["telefono"],
            "alergias": "",
            "preferencias": "",
            "etiqueta": "",
            "vip": False,
            "hint": "",
        }
        if "alergias" in r.keys():
            al = (r["alergias"] or "").strip()
            pr = (r["preferencias"] or "").strip()
            et = (r["etiqueta"] or "").strip()
            vip = int(r["vip"] or 0) == 1
            item["alergias"] = al
            item["preferencias"] = pr
            item["etiqueta"] = et
            item["vip"] = vip
            parts: list[str] = []
            if vip:
                parts.append("VIP")
            if et:
                parts.append(et)
            if al:
                parts.append("⚠")
            if pr and len(pr) <= 40:
                parts.append(pr[:40])
            elif pr:
                parts.append(pr[:37] + "…")
            item["hint"] = " · ".join(parts)
        out.append(item)
    db.close()
    return jsonify({"ok": True, "clientes": out})
