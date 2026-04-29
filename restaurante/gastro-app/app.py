"""Punto de entrada: expone `app` para `flask run` y ejecución directa."""
import os

import reservas.pil_fix  # noqa: F401 — en Windows, stub PIL si la DLL de Pillow está bloqueada (PDFs)

from config import FLASK_PRODUCTION
from models import init_db
from reservas import create_app

app = create_app()

if __name__ == "__main__":
    init_db()
    # Puerto por defecto 5050: en muchas máquinas el 5000 sigue ocupado por otra copia
    # (p. ej. `e:\Clavo\gastro-source`). Usa PORT=5000 si lo liberas antes.
    port = int(os.getenv("PORT", "5050"))
    root = os.path.dirname(os.path.abspath(__file__))
    print(f"[gastro-app Clavo/resaurante] cwd={os.getcwd()} root={root} -> http://127.0.0.1:{port}/")
    # En desarrollo: reinicio automático al cambiar código (sin activar el debugger en pantalla).
    use_reload = not FLASK_PRODUCTION
    app.run(
        host="0.0.0.0",
        port=port,
        debug=False,
        use_reloader=use_reload,
        threaded=True,
    )
