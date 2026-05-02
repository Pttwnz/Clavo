"""Tablas y migraciones para reservas desde la web pública (franjas, cupo, confirmación por email)."""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe
from reservas.utils import hora_texto_a_minutos


TABLE_CFG = "web_reserva_config"
TABLE_FRANJA = "web_franja"


def _migrate_reservas_cols(db) -> None:
    if not tabla_existe(db, "reservas"):
        return
    cols = columnas_tabla(db, "reservas")
    for name, decl in (
        ("email", "TEXT"),
        ("confirm_token", "TEXT"),
        ("confirm_expires", "TEXT"),
        ("origen", "TEXT"),
    ):
        if name not in cols:
            try:
                db.execute(f"ALTER TABLE reservas ADD COLUMN {name} {decl}")
            except Exception:
                pass
    db.commit()
    try:
        db.execute(
            "CREATE INDEX IF NOT EXISTS idx_reservas_confirm_token ON reservas(confirm_token)"
        )
    except Exception:
        pass
    db.commit()


def ensure_web_reservas_tables(db) -> None:
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_CFG} (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            activo INTEGER NOT NULL DEFAULT 0,
            min_personas INTEGER NOT NULL DEFAULT 1,
            max_personas INTEGER NOT NULL DEFAULT 12,
            anticipacion_minutos INTEGER NOT NULL DEFAULT 120,
            max_dias_antelacion INTEGER NOT NULL DEFAULT 60,
            intervalo_minutos INTEGER NOT NULL DEFAULT 30,
            pct_web_defecto INTEGER NOT NULL DEFAULT 70,
            requiere_email INTEGER NOT NULL DEFAULT 1,
            confirmacion_horas INTEGER NOT NULL DEFAULT 168,
            public_base_url TEXT,
            texto_info TEXT
        )
        """
    )
    db.execute(f"INSERT OR IGNORE INTO {TABLE_CFG} (id) VALUES (1)")
    db.execute(
        f"""
        CREATE TABLE IF NOT EXISTS {TABLE_FRANJA} (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            dia_semana INTEGER NOT NULL,
            min_inicio INTEGER NOT NULL,
            min_fin INTEGER NOT NULL,
            etiqueta TEXT,
            pct_web INTEGER,
            activo INTEGER NOT NULL DEFAULT 1,
            orden INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    db.commit()
    _migrate_reservas_cols(db)
    _seed_web_franjas_por_defecto_si_vacio(db)


def _seed_web_franjas_por_defecto_si_vacio(db) -> None:
    """Si no hay franjas (instalación nueva), crea horarios tipo taberna y activa reservas web."""
    row = db.execute(f"SELECT COUNT(*) AS n FROM {TABLE_FRANJA}").fetchone()
    n = int((dict(row) if row else {}).get("n") or 0)
    if n > 0:
        return
    orden = 0
    for dia in range(1, 8):
        for etiqueta, mi, mf in (
            ("Comida", 13 * 60, 16 * 60),
            ("Cena", 20 * 60, 23 * 60 + 30),
        ):
            db.execute(
                f"""
                INSERT INTO {TABLE_FRANJA}
                (dia_semana, min_inicio, min_fin, etiqueta, pct_web, activo, orden)
                VALUES (?, ?, ?, ?, 70, 1, ?)
                """,
                (dia, mi, mf, etiqueta, orden),
            )
            orden += 1
    db.execute(f"UPDATE {TABLE_CFG} SET activo = 1 WHERE id = 1")
    db.commit()


def get_web_reserva_config(db) -> dict:
    ensure_web_reservas_tables(db)
    row = db.execute(f"SELECT * FROM {TABLE_CFG} WHERE id = 1").fetchone()
    if not row:
        return _defaults_config()
    d = dict(row)
    return {
        "activo": bool(int(d.get("activo") or 0)),
        "min_personas": int(d.get("min_personas") or 1),
        "max_personas": int(d.get("max_personas") or 12),
        "anticipacion_minutos": int(d.get("anticipacion_minutos") or 120),
        "max_dias_antelacion": int(d.get("max_dias_antelacion") or 60),
        "intervalo_minutos": int(d.get("intervalo_minutos") or 30),
        "pct_web_defecto": int(d.get("pct_web_defecto") or 70),
        "requiere_email": bool(int(d.get("requiere_email") if d.get("requiere_email") is not None else 1)),
        "confirmacion_horas": int(d.get("confirmacion_horas") or 168),
        "public_base_url": (d.get("public_base_url") or "").strip(),
        "texto_info": (d.get("texto_info") or "").strip(),
    }


def _defaults_config() -> dict:
    return {
        "activo": False,
        "min_personas": 1,
        "max_personas": 12,
        "anticipacion_minutos": 120,
        "max_dias_antelacion": 60,
        "intervalo_minutos": 30,
        "pct_web_defecto": 70,
        "requiere_email": True,
        "confirmacion_horas": 168,
        "public_base_url": "",
        "texto_info": "",
    }


def save_web_reserva_config(db, form: dict) -> None:
    ensure_web_reservas_tables(db)

    def _i(key: str, default: int = 0) -> int:
        try:
            return int(str(form.get(key) or default).strip() or default)
        except (TypeError, ValueError):
            return default

    activo = 1 if str(form.get("activo") or "").strip() in ("1", "on", "true", "yes") else 0
    requiere_email = 1 if str(form.get("requiere_email") or "").strip() in ("1", "on", "true", "yes") else 0
    db.execute(
        f"""
        UPDATE {TABLE_CFG} SET
            activo = ?,
            min_personas = ?,
            max_personas = ?,
            anticipacion_minutos = ?,
            max_dias_antelacion = ?,
            intervalo_minutos = ?,
            pct_web_defecto = ?,
            requiere_email = ?,
            confirmacion_horas = ?,
            public_base_url = ?,
            texto_info = ?
        WHERE id = 1
        """,
        (
            activo,
            max(1, _i("min_personas", 1)),
            max(1, _i("max_personas", 12)),
            max(0, _i("anticipacion_minutos", 120)),
            max(1, _i("max_dias_antelacion", 60)),
            max(5, min(120, _i("intervalo_minutos", 30))),
            max(1, min(100, _i("pct_web_defecto", 70))),
            requiere_email,
            max(1, _i("confirmacion_horas", 168)),
            (form.get("public_base_url") or "").strip()[:500] or None,
            (form.get("texto_info") or "").strip()[:2000] or None,
        ),
    )
    db.commit()


def list_franjas(db) -> list[dict]:
    ensure_web_reservas_tables(db)
    rows = db.execute(
        f"""
        SELECT * FROM {TABLE_FRANJA}
        WHERE activo = 1
        ORDER BY orden ASC, dia_semana ASC, min_inicio ASC
        """
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        d["activo"] = bool(int(d.get("activo") or 0))
        if d.get("pct_web") is None:
            d["pct_web"] = None
        else:
            d["pct_web"] = int(d["pct_web"])
        out.append(d)
    return out


def list_all_franjas_admin(db) -> list[dict]:
    ensure_web_reservas_tables(db)
    rows = db.execute(
        f"SELECT * FROM {TABLE_FRANJA} ORDER BY orden ASC, dia_semana ASC, min_inicio ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def franjas_plantilla_comida_cena_semana(*, pct_web: int | None = None) -> list[dict]:
    """Misma lógica que la semilla por defecto: comida y cena, los 7 días ISO (1=lun … 7=dom)."""
    pct = pct_web
    if pct is not None:
        pct = max(1, min(100, int(pct)))
    rows: list[dict] = []
    for dia in range(1, 8):
        for etiqueta, mi, mf in (
            ("Comida", 13 * 60, 16 * 60),
            ("Cena", 20 * 60, 23 * 60 + 30),
        ):
            rows.append(
                {
                    "dia_semana": dia,
                    "min_inicio": mi,
                    "min_fin": mf,
                    "etiqueta": etiqueta,
                    "pct_web": pct,
                    "activo": True,
                }
            )
    return rows


def franjas_plantilla_solo_cena_semana(*, pct_web: int | None = None) -> list[dict]:
    """Una sola franja «Cena» por día (útil si solo abrís noche online)."""
    pct = pct_web
    if pct is not None:
        pct = max(1, min(100, int(pct)))
    rows: list[dict] = []
    for dia in range(1, 8):
        rows.append(
            {
                "dia_semana": dia,
                "min_inicio": 20 * 60,
                "min_fin": 23 * 60 + 30,
                "etiqueta": "Cena",
                "pct_web": pct,
                "activo": True,
            }
        )
    return rows


def franjas_plantilla_desde_rangos_empresa(db) -> list[dict]:
    """
    Propone franjas web alineadas con los cortes de **Empresa → Rangos mañana/tarde/noche**
    (config_empresa). Heurística: comida ~13:00 hasta antes de la noche; cena desde el inicio
    de «noche» (límite tarde/noche) hasta 23:30.
    """
    from reservas.empresa_config import ensure_config_empresa_table, get_config_empresa

    ensure_config_empresa_table(db)
    ce = get_config_empresa(db)

    def m(h: str, default: str) -> int:
        v = hora_texto_a_minutos((h or default).strip()[:8])
        return v if v is not None else hora_texto_a_minutos(default) or 0

    m_tar = m(str(ce.get("franja_hasta_tarde") or ""), "20:00")
    modo = (str(ce.get("franja_modo") or "tres")).strip().lower()
    if modo == "dos":
        m_corte = m(str(ce.get("franja_corte_dos") or ""), "16:00")
        m_noche_ini = max(m_tar, m_corte)
    else:
        m_noche_ini = m_tar

    comida_ini = 13 * 60
    comida_fin = min(16 * 60 + 30, max(15 * 60, m_noche_ini - 45))
    if comida_fin <= comida_ini + 30:
        comida_fin = 16 * 60

    cena_ini = max(20 * 60, m_noche_ini)
    cena_fin = 23 * 60 + 30
    if cena_ini >= cena_fin - 30:
        cena_ini = 20 * 60

    lab_c = (ce.get("franja_nombre_tarde") or "").strip() or "Comida"
    lab_n = (ce.get("franja_nombre_noche") or "").strip() or "Cena"

    rows: list[dict] = []
    for dia in range(1, 8):
        rows.append(
            {
                "dia_semana": dia,
                "min_inicio": comida_ini,
                "min_fin": comida_fin,
                "etiqueta": lab_c[:80],
                "pct_web": None,
                "activo": True,
            }
        )
        rows.append(
            {
                "dia_semana": dia,
                "min_inicio": cena_ini,
                "min_fin": cena_fin,
                "etiqueta": lab_n[:80],
                "pct_web": None,
                "activo": True,
            }
        )
    return rows


def replace_franjas_from_form(db, rows: list[dict]) -> None:
    ensure_web_reservas_tables(db)
    db.execute(f"DELETE FROM {TABLE_FRANJA}")
    for i, row in enumerate(rows):
        try:
            dia = int(row.get("dia_semana"))
            mi = int(row.get("min_inicio"))
            mf = int(row.get("min_fin"))
        except (TypeError, ValueError):
            continue
        if dia < 1 or dia > 7 or mi < 0 or mf < 0 or mi > 1439 or mf > 1439 or mi > mf:
            continue
        pct = row.get("pct_web")
        try:
            pct_v = int(pct) if pct is not None and str(pct).strip() != "" else None
        except (TypeError, ValueError):
            pct_v = None
        if pct_v is not None:
            pct_v = max(1, min(100, pct_v))
        activo = 1 if row.get("activo") else 0
        db.execute(
            f"""
            INSERT INTO {TABLE_FRANJA}
            (dia_semana, min_inicio, min_fin, etiqueta, pct_web, activo, orden)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                dia,
                mi,
                mf,
                (row.get("etiqueta") or "").strip()[:80] or None,
                pct_v,
                activo,
                i,
            ),
        )
    db.commit()
