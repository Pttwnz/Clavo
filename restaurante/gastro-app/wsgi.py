"""Entrada WSGI para servidores de producción (Gunicorn, Waitress, etc.)."""
from reservas import create_app

app = create_app()
