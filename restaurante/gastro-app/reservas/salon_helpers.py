"""Salón / esquema activo: lectura y sincronización con la tabla legacy `mesas`."""
from __future__ import annotations

import json

from reservas.db_helpers import columnas_tabla, tabla_existe


def capacidad_union_mesas(capacidades: list[int], perdida_por_union: int = 2) -> int:
    """
    Capacidad realista de una unión de mesas.
    Regla base: suma de plazas menos `perdida_por_union` por cada mesa adicional.
    Ejemplo: 4 + 4 => 6 (pierde 2 por la unión).
    """
    caps_ok: list[int] = []
    for c in capacidades:
        try:
            v = int(c)
        except (TypeError, ValueError):
            continue
        if v > 0:
            caps_ok.append(v)
    if not caps_ok:
        return 0
    n = len(caps_ok)
    total = sum(caps_ok)
    ajuste = max(0, n - 1) * max(0, int(perdida_por_union))
    return max(2, total - ajuste)


def _col(db, tabla: str, nombre: str, ddl: str) -> None:
    if nombre in columnas_tabla(db, tabla):
        return
    try:
        db.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {ddl}")
    except Exception:
        pass


def _repair_objetos_salon_capacidad(db) -> None:
    """Corrige migración antigua que añadió una columna mal llamada INTEGER en vez de capacidad."""
    if not tabla_existe(db, "objetos_salon"):
        return
    cols = columnas_tabla(db, "objetos_salon")
    if "capacidad" in cols and "INTEGER" in cols:
        try:
            db.execute("ALTER TABLE objetos_salon DROP COLUMN [INTEGER]")
        except Exception:
            pass
        return
    if "capacidad" in cols:
        return
    if "INTEGER" in cols:
        try:
            db.execute('ALTER TABLE objetos_salon RENAME COLUMN "INTEGER" TO capacidad')
            return
        except Exception:
            try:
                db.execute("ALTER TABLE objetos_salon DROP COLUMN [INTEGER]")
            except Exception:
                pass


def _backfill_esquemas_salon_id(db) -> None:
    """Asocia esquemas huérfanos al primer salón si falta salon_id (BD antigua)."""
    if not tabla_existe(db, "esquemas") or "salon_id" not in columnas_tabla(db, "esquemas"):
        return
    r = db.execute("SELECT id FROM salones ORDER BY id LIMIT 1").fetchone()
    if not r:
        return
    sid = int(r["id"])
    db.execute(
        "UPDATE esquemas SET salon_id = ? WHERE salon_id IS NULL",
        (sid,),
    )


def ensure_salon_tables(db) -> None:
    """Crea tablas de salón si no existen."""
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS salones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL DEFAULT 'Salón principal'
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS esquemas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            salon_id INTEGER NOT NULL,
            nombre TEXT NOT NULL DEFAULT 'Principal',
            activo INTEGER NOT NULL DEFAULT 0,
            FOREIGN KEY (salon_id) REFERENCES salones(id)
        )
        """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS objetos_salon (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            esquema_id INTEGER NOT NULL,
            nombre TEXT,
            tipo TEXT DEFAULT 'mesa',
            x REAL DEFAULT 100,
            y REAL DEFAULT 100,
            width REAL DEFAULT 88,
            height REAL DEFAULT 88,
            rotacion REAL DEFAULT 0,
            imagen TEXT DEFAULT 'img/mesa_4.png',
            capacidad INTEGER DEFAULT 4,
            FOREIGN KEY (esquema_id) REFERENCES esquemas(id)
        )
    """
    )
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS mesa_uniones (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            esquema_id INTEGER NOT NULL,
            nombre TEXT NOT NULL,
            componentes_json TEXT NOT NULL DEFAULT '[]',
            capacidad_total INTEGER NOT NULL DEFAULT 0,
            activa INTEGER NOT NULL DEFAULT 1,
            FOREIGN KEY (esquema_id) REFERENCES esquemas(id)
        )
        """
    )
    _col(db, "esquemas", "salon_id", "INTEGER")
    _backfill_esquemas_salon_id(db)
    _repair_objetos_salon_capacidad(db)
    _col(db, "objetos_salon", "capacidad", "INTEGER DEFAULT 4")


def get_esquema_activo_id(db):
    """Id del esquema marcado activo, o None."""
    if not tabla_existe(db, "esquemas"):
        return None
    r = db.execute(
        "SELECT id FROM esquemas WHERE activo = 1 ORDER BY id LIMIT 1"
    ).fetchone()
    return int(r["id"]) if r else None


def seed_salon_if_empty(db) -> None:
    """Un salón y un esquema activo por defecto, y mesas demo si no hay objetos."""
    ensure_salon_tables(db)
    n = db.execute("SELECT COUNT(*) FROM salones").fetchone()[0]
    if n == 0:
        db.execute("INSERT INTO salones (nombre) VALUES ('Salón principal')")
        sid = db.execute("SELECT last_insert_rowid()").fetchone()[0]
        db.execute(
            """
            INSERT INTO esquemas (salon_id, nombre, activo)
            VALUES (?, 'Principal', 1)
            """,
            (sid,),
        )
    else:
        ex = db.execute(
            "SELECT COUNT(*) FROM esquemas WHERE activo = 1"
        ).fetchone()[0]
        if ex == 0:
            sid = db.execute("SELECT id FROM salones ORDER BY id LIMIT 1").fetchone()[0]
            db.execute(
                "UPDATE esquemas SET activo = 0"
            )
            db.execute(
                """
                INSERT INTO esquemas (salon_id, nombre, activo)
                VALUES (?, 'Principal', 1)
                """,
                (sid,),
            )

    _backfill_esquemas_salon_id(db)

    eid = get_esquema_activo_id(db)
    if not eid:
        return
    nob = db.execute(
        "SELECT COUNT(*) FROM objetos_salon WHERE esquema_id = ?",
        (eid,),
    ).fetchone()[0]
    if nob == 0:
        demo = [
            ("Mesa 1", 120, 140, 4, "mesa_cuadrada", 96, 80),
            ("Mesa 2", 260, 140, 4, "mesa_redonda", 96, 96),
            ("Mesa 3", 400, 140, 2, "mesa_cuadrada", 80, 64),
        ]
        for nom, x, y, cap, tipo_m, w, h in demo:
            db.execute(
                """
                INSERT INTO objetos_salon
                (esquema_id, nombre, tipo, x, y, width, height, rotacion, imagen, capacidad)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0, '', ?)
                """,
                (eid, nom, tipo_m, float(x), float(y), float(w), float(h), cap),
            )
    db.commit()
    sync_tabla_mesas_desde_objetos(db)


def list_objetos_mesas_esquema_activo(db):
    """Filas sqlite3.Row de mesas del plano activo."""
    if not tabla_existe(db, "objetos_salon"):
        return []
    eid = get_esquema_activo_id(db)
    if not eid:
        return []
    return db.execute(
        """
        SELECT o.id, o.nombre, o.tipo, o.x, o.y, o.width, o.height, o.rotacion, o.imagen,
               COALESCE(o.capacidad, 4) AS capacidad
        FROM objetos_salon o
        WHERE o.esquema_id = ?
          AND (
            LOWER(TRIM(COALESCE(o.tipo, ''))) IN ('mesa', 'mesa_redonda', 'mesa_cuadrada')
            OR o.tipo IS NULL OR TRIM(COALESCE(o.tipo, '')) = ''
          )
        ORDER BY o.nombre
        """,
        (eid,),
    ).fetchall()


def nombres_mesas_para_select(db) -> list[str]:
    """Nombres únicos para desplegable de reservas (esquema activo)."""
    rows = list_objetos_mesas_esquema_activo(db)
    out = []
    for r in rows:
        n = (r["nombre"] or "").strip()
        if n and n not in out:
            out.append(n)
    for u in list_uniones_esquema_activo(db):
        n = (u.get("nombre") or "").strip()
        if n and n not in out:
            out.append(n)
    return sorted(out, key=lambda x: x.lower())


def sync_tabla_mesas_desde_objetos(db) -> None:
    """Copia posición y capacidad al catálogo `mesas` usado por reservas/mapa listado."""
    if not tabla_existe(db, "mesas") or not tabla_existe(db, "objetos_salon"):
        return
    rows = list_objetos_mesas_esquema_activo(db)
    by_id: dict[int, dict] = {}
    for r in rows:
        try:
            by_id[int(r["id"])] = dict(r)
        except Exception:
            continue
    db.execute("DELETE FROM mesas")
    for r in rows:
        nombre = (r["nombre"] or "").strip()
        if not nombre:
            continue
        try:
            x = int(float(r["x"] or 0))
            y = int(float(r["y"] or 0))
        except (TypeError, ValueError):
            x, y = 0, 0
        cap = r["capacidad"]
        try:
            cap = int(cap) if cap is not None else 4
        except (TypeError, ValueError):
            cap = 4
        db.execute(
            """
            INSERT INTO mesas (nombre, x, y, capacidad)
            VALUES (?, ?, ?, ?)
            """,
            (nombre, x, y, cap),
        )
    # Añadir uniones guardadas para poder reservar "mesa combinada" desde el flujo normal.
    for u in list_uniones_esquema_activo(db):
        nombre = (u.get("nombre") or "").strip()
        if not nombre:
            continue
        ids = [int(x) for x in (u.get("mesa_ids") or []) if str(x).strip()]
        usados = [by_id.get(i) for i in ids if i in by_id]
        if not usados:
            continue
        xs, ys = [], []
        cap_total = int(u.get("capacidad_total") or 0)
        if cap_total <= 0:
            for m in usados:
                try:
                    cap_total += int(m.get("capacidad") or 0)
                except (TypeError, ValueError):
                    pass
        for m in usados:
            try:
                x = float(m.get("x") or 0)
                y = float(m.get("y") or 0)
                w = float(m.get("width") or 72)
                h = float(m.get("height") or 72)
            except (TypeError, ValueError):
                continue
            xs.append(x + (w / 2.0))
            ys.append(y + (h / 2.0))
        cx = int(round(sum(xs) / len(xs))) if xs else 0
        cy = int(round(sum(ys) / len(ys))) if ys else 0
        db.execute(
            """
            INSERT INTO mesas (nombre, x, y, capacidad)
            VALUES (?, ?, ?, ?)
            """,
            (nombre, cx, cy, max(2, cap_total)),
        )


def list_uniones_esquema_activo(db) -> list[dict]:
    """Uniones de mesas persistidas en el esquema activo."""
    if not tabla_existe(db, "mesa_uniones"):
        return []
    eid = get_esquema_activo_id(db)
    if not eid:
        return []
    rows = db.execute(
        """
        SELECT id, esquema_id, nombre, componentes_json, capacidad_total, activa
        FROM mesa_uniones
        WHERE esquema_id = ?
          AND activa = 1
        ORDER BY id
        """,
        (eid,),
    ).fetchall()
    cap_by_id: dict[int, int] = {}
    try:
        cap_rows = db.execute(
            """
            SELECT id, COALESCE(capacidad, 0) AS capacidad
            FROM objetos_salon
            WHERE esquema_id = ?
              AND LOWER(TRIM(COALESCE(tipo,''))) IN ('mesa', 'mesa_redonda', 'mesa_cuadrada')
            """,
            (eid,),
        ).fetchall()
        for cr in cap_rows:
            try:
                cid = int(cr["id"])
                ccap = int(cr["capacidad"] or 0)
            except (TypeError, ValueError):
                continue
            cap_by_id[cid] = ccap
    except Exception:
        cap_by_id = {}

    out: list[dict] = []
    for r in rows:
        d = dict(r)
        raw = d.get("componentes_json") or "[]"
        ids: list[int] = []
        nombres: list[str] = []
        try:
            v = json.loads(raw)
            if isinstance(v, dict):
                ids = [int(x) for x in (v.get("ids") or []) if str(x).strip()]
                nombres = [str(x).strip() for x in (v.get("nombres") or []) if str(x).strip()]
            elif isinstance(v, list):
                # compat: lista de nombres antigua
                nombres = [str(x).strip() for x in v if str(x).strip()]
        except Exception:
            pass
        d["mesa_ids"] = ids
        d["mesa_nombres"] = nombres
        if ids and cap_by_id:
            caps = [cap_by_id[i] for i in ids if i in cap_by_id]
            cap_calc = capacidad_union_mesas(caps)
            if cap_calc > 0:
                d["capacidad_total"] = cap_calc
        out.append(d)
    return out


def es_tipo_mesa(tipo) -> bool:
    """True si el objeto cuenta como mesa (reservas / catálogo mesas)."""
    t = (tipo or "").strip().lower()
    return t in ("", "mesa", "mesa_redonda", "mesa_cuadrada")


def vista_mesa_plano(tipo) -> str:
    """'redonda' | 'cuadrada' para dibujo CSS (legacy mesa → cuadrada)."""
    t = (tipo or "").strip().lower()
    if t == "mesa_redonda":
        return "redonda"
    return "cuadrada"


def static_imagen_mesa(imagen: str | None) -> str:
    """Ruta bajo /static para url_for (img/… o uploads/…)."""
    if not imagen or not str(imagen).strip():
        return "img/mesa_4.png"
    s = str(imagen).replace("\\", "/").strip()
    if s.startswith("uploads/"):
        return s
    if s.startswith("img/"):
        return s
    return "img/" + s.lstrip("/")


def bounds_plano_objetos(objetos: list, pad: float = 56.0) -> tuple[float, float]:
    """Tamaño mínimo del lienzo para contener todos los objetos (px)."""
    w, h = 920.0, 720.0
    for o in objetos:
        try:
            x = float(o.get("x") or 0)
            y = float(o.get("y") or 0)
            ow = float(o.get("width") or 72)
            oh = float(o.get("height") or 72)
        except (TypeError, ValueError):
            continue
        w = max(w, x + ow + pad)
        h = max(h, y + oh + pad)
    return (w, h)


def list_objetos_esquema_completo(db, esquema_id: int) -> list[dict]:
    """Todos los objetos de un esquema (mesas + decoración), para el editor."""
    if not esquema_id or not tabla_existe(db, "objetos_salon"):
        return []
    rows = db.execute(
        """
        SELECT id, nombre, tipo, x, y, width, height, rotacion, imagen,
               COALESCE(capacidad, 4) AS capacidad
        FROM objetos_salon
        WHERE esquema_id = ?
        """,
        (int(esquema_id),),
    ).fetchall()
    out = [dict(r) for r in rows]
    out.sort(
        key=lambda o: (
            0 if not es_tipo_mesa(o.get("tipo")) else 1,
            int(o.get("id") or 0),
        )
    )
    return out


def list_objetos_decor_esquema_activo(db) -> list[dict]:
    """Elementos no-mesa del esquema activo (paredes, iconos, etc.) para /visualizar."""
    if not tabla_existe(db, "objetos_salon"):
        return []
    eid = get_esquema_activo_id(db)
    if not eid:
        return []
    rows = db.execute(
        """
        SELECT id, nombre, tipo, x, y, width, height, rotacion, imagen
        FROM objetos_salon
        WHERE esquema_id = ?
        """,
        (eid,),
    ).fetchall()
    out = []
    for r in rows:
        o = dict(r)
        if es_tipo_mesa(o.get("tipo")):
            continue
        t = (o.get("tipo") or "decor").strip().lower()
        o["tipo"] = t
        out.append(o)
    return out


def mesas_para_mapa_reservas(db, static_root: str | None = None) -> list[dict]:
    """Lista de dicts para plantilla reservas.html (mini mapa)."""
    from reservas.salon_assets import pick_imagen_capacidad, resolved_url_path

    rows = list_objetos_mesas_esquema_activo(db)
    mesas = []
    for m in rows:
        nombre = (m["nombre"] or "Mesa").strip()
        cap = m["capacidad"] or 4
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            cap = 4
        fb = pick_imagen_capacidad(static_root, cap)
        imagen = resolved_url_path(static_root, (m["imagen"] or "").strip() or None, fb)
        nl = nombre.lower()
        if nl.startswith("barril"):
            imagen = resolved_url_path(static_root, (m["imagen"] or "").strip() or None, "barril.png")
        elif nl.startswith("barra"):
            imagen = resolved_url_path(static_root, (m["imagen"] or "").strip() or None, "barra.png")
        try:
            x = int(float(m["x"] or 0))
            y = int(float(m["y"] or 0))
        except (TypeError, ValueError):
            x, y = 0, 0
        mesas.append(
            {
                "nombre": nombre,
                "nombre_corto": nombre.replace("Mesa ", "M"),
                "x": x,
                "y": y,
                "imagen": imagen,
                "capacidad": cap,
            }
        )
    # Uniones guardadas (misma fecha que en sync_tabla_mesas): reservables con capacidad sumada.
    noms = {m["nombre"] for m in mesas}
    for u in list_uniones_esquema_activo(db):
        un = (u.get("nombre") or "").strip()
        if not un or un in noms:
            continue
        try:
            cap_u = int(u.get("capacidad_total") or 0)
        except (TypeError, ValueError):
            cap_u = 0
        if cap_u < 2:
            cap_u = 4
        fb = pick_imagen_capacidad(static_root, cap_u)
        imagen_u = resolved_url_path(static_root, None, fb)
        mesas.append(
            {
                "nombre": un,
                "nombre_corto": (un.replace("Mesa ", "M")[:14] + "…")
                if len(un) > 14
                else un.replace("Mesa ", "M"),
                "x": 0,
                "y": 0,
                "imagen": imagen_u,
                "capacidad": cap_u,
            }
        )
        noms.add(un)
    return mesas


def objetos_visualizar_tp(db) -> list[dict]:
    """Datos para /visualizar: posición, rotación, reserva enlazada por nombre."""
    rows = list_objetos_mesas_esquema_activo(db)
    out = []
    for m in rows:
        nombre = (m["nombre"] or "Mesa").strip()
        try:
            x = float(m["x"] or 0)
            y = float(m["y"] or 0)
        except (TypeError, ValueError):
            x, y = 0.0, 0.0
        try:
            w = float(m["width"] or 72)
            h = float(m["height"] or 72)
        except (TypeError, ValueError):
            w, h = 72.0, 72.0
        try:
            rot = float(m["rotacion"] or 0)
        except (TypeError, ValueError):
            rot = 0.0
        cap = m["capacidad"] or 4
        try:
            cap = int(cap)
        except (TypeError, ValueError):
            cap = 4
        raw_img = (m["imagen"] or "").strip()
        trow = (m["tipo"] or "mesa").strip().lower()
        imagen = static_imagen_mesa(raw_img) if trow == "mesa" else ""
        out.append(
            {
                "id": m["id"],
                "nombre": nombre,
                "tipo": trow,
                "vista": vista_mesa_plano(trow),
                "x": x,
                "y": y,
                "width": w,
                "height": h,
                "rotacion": rot,
                "imagen": imagen,
                "imagen_db": raw_img,
                "capacidad": cap,
            }
        )
    return out
