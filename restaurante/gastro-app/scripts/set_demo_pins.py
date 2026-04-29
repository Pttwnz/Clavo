"""Fija PIN demo para entorno local (admin/tablet/empleados)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from auth import hash_pin
from models import get_db, init_db


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pin", default="1234")
    args = parser.parse_args()
    init_db()
    db = get_db()
    try:
        h = hash_pin(args.pin)
        row = db.execute("SELECT id FROM admin ORDER BY id LIMIT 1").fetchone()
        if row:
            db.execute(
                "UPDATE admin SET pin_hash = ?, pin_tablet_hash = ? WHERE id = ?",
                (h, h, row["id"]),
            )
        else:
            db.execute(
                "INSERT INTO admin (pin_hash, pin_tablet_hash) VALUES (?, ?)",
                (h, h),
            )
        db.execute("UPDATE empleados SET pin_hash = ?", (h,))
        db.commit()
        print(f"[pins] PIN demo aplicado: {args.pin}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
