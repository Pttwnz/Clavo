"""PDFs de horarios publicados en el perfil de cada empleado."""
from __future__ import annotations

from reservas.db_helpers import columnas_tabla, tabla_existe


def ensure_horarios_entregas_table(db) -> None:
    db.execute(
        """
        CREATE TABLE IF NOT EXISTS horarios_pdf_entregas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            empleado_id INTEGER NOT NULL,
            periodo_desde TEXT NOT NULL,
            periodo_hasta TEXT NOT NULL,
            etiqueta TEXT,
            archivo_relativo TEXT NOT NULL,
            creado_en TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (empleado_id) REFERENCES empleados(id) ON DELETE CASCADE
        )
        """
    )
    db.execute(
        "CREATE INDEX IF NOT EXISTS idx_horarios_pdf_emp ON horarios_pdf_entregas (empleado_id)"
    )
    db.commit()


def listar_entregas_empleado(db, empleado_id: int, lim: int = 40) -> list:
    if not tabla_existe(db, "horarios_pdf_entregas"):
        return []
    return [
        dict(r)
        for r in db.execute(
            """
            SELECT id, periodo_desde, periodo_hasta, etiqueta, archivo_relativo, creado_en
            FROM horarios_pdf_entregas
            WHERE empleado_id = ?
            ORDER BY id DESC
            LIMIT ?
            """,
            (empleado_id, lim),
        ).fetchall()
    ]
