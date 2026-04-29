"""Ficha de clientes vinculada a reservas (teléfono como clave lógica)."""
from __future__ import annotations

import re
import sqlite3

from reservas.db_helpers import columnas_tabla, tabla_existe

T_CLIENTES = "clientes"
MIN_DIGITOS_TELEFONO = 5

_CLIENTES_EXTRA_COLS: tuple[tuple[str, str], ...] = (
    ("alergias", "TEXT"),
    ("preferencias", "TEXT"),
    ("etiqueta", "TEXT"),
    ("vip", "INTEGER NOT NULL DEFAULT 0"),
)


def normalizar_telefono(telefono: str | None) -> str:
    """Solo dígitos; si parece +34, deja los últimos 9 como clave local."""
    s = re.sub(r"\D", "", telefono or "")
    if len(s) >= 11 and s.startswith("34"):
        s = s[2:]
    return s


def telefono_valido_para_ficha(telefono: str | None) -> bool:
    return len(normalizar_telefono(telefono)) >= MIN_DIGITOS_TELEFONO


def ensure_clientes_schema(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {T_CLIENTES} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            telefono TEXT NOT NULL,
            telefono_norm TEXT NOT NULL,
            email TEXT,
            notas_internas TEXT,
            ultima_reserva TEXT,
            creado_en TEXT DEFAULT (datetime('now')),
            actualizado_en TEXT
        )
        """
    )
    db.execute(
        f"CREATE UNIQUE INDEX IF NOT EXISTS idx_clientes_tel_norm "
        f"ON {T_CLIENTES} (telefono_norm)"
    )
    db.execute(
        f"CREATE INDEX IF NOT EXISTS idx_clientes_nombre ON {T_CLIENTES} (nombre)"
    )

    if tabla_existe(db, T_CLIENTES):
        cols = columnas_tabla(db, T_CLIENTES)
        for nombre, decl in _CLIENTES_EXTRA_COLS:
            if nombre not in cols:
                db.execute(f"ALTER TABLE {T_CLIENTES} ADD COLUMN {nombre} {decl}")

    if tabla_existe(db, "reservas"):
        cols = columnas_tabla(db, "reservas")
        if "cliente_id" not in cols:
            db.execute("ALTER TABLE reservas ADD COLUMN cliente_id INTEGER")
    db.commit()


def migrate_reservas_cliente_links(db) -> None:
    """
    Enlaza reservas históricas con fichas de cliente (una vez por base de datos).
    Pensado para llamarse desde init_db al arrancar, no en cada petición.
    """
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS _gm_migraciones (
            clave TEXT PRIMARY KEY,
            aplicado_en TEXT DEFAULT (datetime('now'))
        )
        """
    )
    db.commit()
    done = db.execute(
        "SELECT 1 FROM _gm_migraciones WHERE clave = 'reservas_cliente_id_v1' LIMIT 1"
    ).fetchone()
    if done:
        return
    while _backfill_reservas_cliente_id_batch(db, limit=500) > 0:
        pass
    db.execute(
        "INSERT OR IGNORE INTO _gm_migraciones (clave) VALUES ('reservas_cliente_id_v1')"
    )
    db.commit()


def _backfill_reservas_cliente_id_batch(db, limit: int = 400) -> int:
    """Asigna cliente_id a un lote de reservas antiguas. Devuelve cuántas filas procesó."""
    if not tabla_existe(db, "reservas") or not tabla_existe(db, T_CLIENTES):
        return 0
    cols = columnas_tabla(db, "reservas")
    if "cliente_id" not in cols:
        return 0
    rows = db.execute(
        f"""
        SELECT id, nombre, telefono, fecha
        FROM reservas
        WHERE (cliente_id IS NULL OR cliente_id = 0)
          AND telefono IS NOT NULL AND trim(telefono) != ''
        ORDER BY fecha DESC, id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()
    for r in rows:
        if not telefono_valido_para_ficha(r["telefono"]):
            # Evita bucle infinito en migración: no reintentar teléfonos inválidos.
            db.execute(
                "UPDATE reservas SET cliente_id = -1 WHERE id = ? AND (cliente_id IS NULL OR cliente_id = 0)",
                (r["id"],),
            )
            continue
        cid = upsert_cliente_desde_reserva(
            db,
            nombre=(r["nombre"] or "").strip() or "Cliente",
            telefono=r["telefono"],
            fecha_reserva=(r["fecha"] or "")[:10] or None,
            commit=False,
        )
        if cid:
            db.execute(
                "UPDATE reservas SET cliente_id = ? WHERE id = ?",
                (cid, r["id"]),
            )
    db.commit()
    return len(rows)


def upsert_cliente_desde_reserva(
    db,
    *,
    nombre: str,
    telefono: str,
    fecha_reserva: str | None = None,
    email: str | None = None,
    commit: bool = True,
) -> int | None:
    """
    Crea o actualiza la ficha por telefono_norm único.
    Devuelve id de cliente o None si el teléfono no sirve para ficha (walk-in «-», etc.).
    """
    if not telefono_valido_para_ficha(telefono):
        return None
    nombre = (nombre or "").strip() or "Cliente"
    tel_raw = (telefono or "").strip()
    tn = normalizar_telefono(tel_raw)
    ultima = fecha_reserva
    row = db.execute(
        f"SELECT id FROM {T_CLIENTES} WHERE telefono_norm = ?",
        (tn,),
    ).fetchone()
    now_sql = "datetime('now')"
    if row:
        cid = int(row["id"])
        sets = [
            "nombre = ?",
            "telefono = ?",
            f"actualizado_en = {now_sql}",
        ]
        args: list = [nombre, tel_raw]
        if ultima:
            sets.append(
                "ultima_reserva = CASE WHEN ultima_reserva IS NULL OR ultima_reserva < ? THEN ? ELSE ultima_reserva END"
            )
            args.extend([ultima, ultima])
        if email is not None and (email or "").strip():
            sets.append("email = ?")
            args.append((email or "").strip())
        args.append(cid)
        db.execute(
            f"UPDATE {T_CLIENTES} SET {', '.join(sets)} WHERE id = ?",
            tuple(args),
        )
    else:
        try:
            cur = db.execute(
                f"""
                INSERT INTO {T_CLIENTES}
                (nombre, telefono, telefono_norm, email, ultima_reserva, actualizado_en)
                VALUES (?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    nombre,
                    tel_raw,
                    tn,
                    (email or "").strip() or None,
                    ultima,
                ),
            )
            cid = int(cur.lastrowid)
        except sqlite3.IntegrityError:
            row2 = db.execute(
                f"SELECT id FROM {T_CLIENTES} WHERE telefono_norm = ?",
                (tn,),
            ).fetchone()
            if not row2:
                raise
            cid = int(row2["id"])
            db.execute(
                f"""
                UPDATE {T_CLIENTES}
                SET nombre = ?, telefono = ?, actualizado_en = datetime('now')
                WHERE id = ?
                """,
                (nombre, tel_raw, cid),
            )
            if ultima:
                db.execute(
                    f"""
                    UPDATE {T_CLIENTES}
                    SET ultima_reserva = CASE
                      WHEN ultima_reserva IS NULL OR ultima_reserva < ? THEN ?
                      ELSE ultima_reserva END
                    WHERE id = ?
                    """,
                    (ultima, ultima, cid),
                )
    if commit:
        db.commit()
    return cid


def vincular_reserva_a_cliente(
    db, reserva_id: int, cliente_id: int | None, *, commit: bool = True
) -> None:
    if cliente_id is None:
        return
    db.execute(
        "UPDATE reservas SET cliente_id = ? WHERE id = ?",
        (int(cliente_id), int(reserva_id)),
    )
    if commit:
        db.commit()


def listar_clientes(db, q: str | None = None, limit: int = 200):
    q = (q or "").strip()
    if q:
        like = f"%{q}%"
        tn = normalizar_telefono(q)
        if len(tn) >= MIN_DIGITOS_TELEFONO:
            return db.execute(
                f"""
                SELECT c.*,
                  (SELECT COUNT(*) FROM reservas r WHERE r.cliente_id = c.id) AS num_reservas
                FROM {T_CLIENTES} c
                WHERE c.nombre LIKE ? OR c.telefono LIKE ? OR c.telefono_norm LIKE ?
                ORDER BY c.ultima_reserva DESC NULLS LAST, c.id DESC
                LIMIT ?
                """,
                (like, like, f"%{tn}%", limit),
            ).fetchall()
        return db.execute(
            f"""
            SELECT c.*,
              (SELECT COUNT(*) FROM reservas r WHERE r.cliente_id = c.id) AS num_reservas
            FROM {T_CLIENTES} c
            WHERE c.nombre LIKE ? OR c.telefono LIKE ?
            ORDER BY c.ultima_reserva DESC NULLS LAST, c.id DESC
            LIMIT ?
            """,
            (like, like, limit),
        ).fetchall()
    return db.execute(
        f"""
        SELECT c.*,
          (SELECT COUNT(*) FROM reservas r WHERE r.cliente_id = c.id) AS num_reservas
        FROM {T_CLIENTES} c
        ORDER BY c.ultima_reserva DESC NULLS LAST, c.id DESC
        LIMIT ?
        """,
        (limit,),
    ).fetchall()


def obtener_cliente(db, cliente_id: int):
    return db.execute(
        f"SELECT * FROM {T_CLIENTES} WHERE id = ?",
        (int(cliente_id),),
    ).fetchone()


def reservas_de_cliente(db, cliente_id: int, limit: int = 100):
    return db.execute(
        """
        SELECT id, nombre, telefono, personas, fecha, hora, mesa, estado, notas
        FROM reservas
        WHERE cliente_id = ?
        ORDER BY fecha DESC, hora DESC
        LIMIT ?
        """,
        (int(cliente_id), limit),
    ).fetchall()


def actualizar_ficha_cliente(
    db,
    cliente_id: int,
    *,
    nombre: str,
    telefono: str,
    email: str | None,
    notas_internas: str | None,
    alergias: str | None = None,
    preferencias: str | None = None,
    etiqueta: str | None = None,
    vip: bool = False,
) -> tuple[bool, str]:
    """Actualiza datos de ficha; si cambia el teléfono, respeta unicidad telefono_norm."""
    if not telefono_valido_para_ficha(telefono):
        return False, "telefono_invalido"
    nombre = (nombre or "").strip() or "Cliente"
    tel_raw = (telefono or "").strip()
    tn = normalizar_telefono(tel_raw)
    otro = db.execute(
        f"SELECT id FROM {T_CLIENTES} WHERE telefono_norm = ? AND id != ?",
        (tn, int(cliente_id)),
    ).fetchone()
    if otro:
        return False, "telefono_duplicado"
    vip_int = 1 if vip else 0
    db.execute(
        f"""
        UPDATE {T_CLIENTES}
        SET nombre = ?, telefono = ?, telefono_norm = ?, email = ?, notas_internas = ?,
            alergias = ?, preferencias = ?, etiqueta = ?, vip = ?,
            actualizado_en = datetime('now')
        WHERE id = ?
        """,
        (
            nombre,
            tel_raw,
            tn,
            (email or "").strip() or None,
            (notas_internas or "").strip() or None,
            (alergias or "").strip() or None,
            (preferencias or "").strip() or None,
            (etiqueta or "").strip() or None,
            vip_int,
            int(cliente_id),
        ),
    )
    db.execute(
        """
        UPDATE reservas
        SET nombre = ?, telefono = ?
        WHERE cliente_id = ?
        """,
        (nombre, tel_raw, int(cliente_id)),
    )
    db.commit()
    return True, "ok"


def buscar_clientes_autocomplete(db, q: str, limit: int = 12):
    q = (q or "").strip()
    if len(q) < 2:
        return []
    like = f"%{q}%"
    tn = normalizar_telefono(q)
    extra = ""
    if tabla_existe(db, T_CLIENTES) and "alergias" in columnas_tabla(db, T_CLIENTES):
        extra = ", COALESCE(alergias,'') AS alergias, COALESCE(preferencias,'') AS preferencias, COALESCE(etiqueta,'') AS etiqueta, COALESCE(vip,0) AS vip"
    if len(tn) >= MIN_DIGITOS_TELEFONO:
        return db.execute(
            f"""
            SELECT id, nombre, telefono, telefono_norm{extra}
            FROM {T_CLIENTES}
            WHERE nombre LIKE ? OR telefono LIKE ? OR telefono_norm LIKE ?
            ORDER BY nombre
            LIMIT ?
            """,
            (like, like, f"%{tn}%", limit),
        ).fetchall()
    return db.execute(
        f"""
        SELECT id, nombre, telefono, telefono_norm{extra}
        FROM {T_CLIENTES}
        WHERE nombre LIKE ? OR telefono LIKE ?
        ORDER BY nombre
        LIMIT ?
        """,
        (like, like, limit),
    ).fetchall()
