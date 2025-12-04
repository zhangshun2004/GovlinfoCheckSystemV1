import pytest
from app import create_app

@pytest.fixture
def client():
    app = create_app()
    app.testing = True
    return app.test_client()

def test_index(client):
    resp = client.get('/')
    assert resp.status_code == 200
    assert b'layui' in resp.data

