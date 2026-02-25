import pytest
from app import create_app


def test_detalle_compras_missing_cliente():
    app = create_app()
    client = app.test_client()

    resp = client.get('/detalle-compras-odoo')
    assert resp.status_code == 400
    data = resp.get_json()
    assert data and 'error' in data
