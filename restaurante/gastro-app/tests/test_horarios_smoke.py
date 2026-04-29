"""Humo HTTP del módulo de horarios (admin PIN)."""
from __future__ import annotations

import pytest

from config import RESERVAS_ONLY
from reservas import create_app

pytestmark = pytest.mark.skipif(
    RESERVAS_ONLY,
    reason="Módulo horarios no registrado cuando RESERVAS_ONLY=1",
)


@pytest.fixture()
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["PROPAGATE_EXCEPTIONS"] = True
    with app.test_client() as c:
        yield c


def _admin_session(c):
    with c.session_transaction() as s:
        s["admin_logueado"] = True
        s["rol"] = "admin"


@pytest.mark.parametrize(
    "path",
    [
        "/horarios",
        "/horarios?vista=lista",
        "/horarios?vista=semana",
        "/horarios?vista=mes",
        "/horarios?vista=mes&mes=2026-02",
        "/horarios?vista=INVALID",
        "/horarios?fecha=bad-date",
        "/horarios?fecha=2026-06-15&vista=semana",
        "/horarios?fecha=2026-06-15&vista=mes&mes=2026-06",
    ],
)
def test_horarios_get_ok(client, path):
    _admin_session(client)
    r = client.get(path)
    assert r.status_code == 200, (path, r.status_code)


def test_generar_sin_fechas_redirect(client):
    _admin_session(client)
    r = client.post("/generar_horarios_reglas", data={}, follow_redirects=False)
    assert r.status_code == 302
    assert "/horarios" in (r.headers.get("Location") or "")


def test_generar_con_fechas_redirect(client):
    _admin_session(client)
    r = client.post(
        "/generar_horarios_reglas",
        data={"fecha_inicio": "2026-05-01", "fecha_fin": "2026-05-07"},
        follow_redirects=False,
    )
    assert r.status_code == 302


def test_publicar_pdf_sin_rango(client):
    _admin_session(client)
    r = client.post("/horarios/publicar_pdfs_empleados", data={}, follow_redirects=False)
    assert r.status_code == 302


def test_editar_inexistente_404(client):
    _admin_session(client)
    r = client.get("/horario/999999/editar")
    assert r.status_code == 404
