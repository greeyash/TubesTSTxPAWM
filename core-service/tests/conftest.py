import os
import tempfile

import pytest

_tmp = tempfile.mkdtemp()
os.environ.update(
    DB_PATH=os.path.join(_tmp, "test.db"),
    EXTERNAL_APIS="off",
    JWT_SECRET="test-secret-test-secret-test-secret-123",
    ADMIN_EMAIL="admin@test.local",
    ADMIN_PASSWORD="admin-pass-123",
    APP_ENV="test",
)

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _login(client, email, password):
    r = client.post("/api/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="session")
def admin(client):
    return _login(client, "admin@test.local", "admin-pass-123")


@pytest.fixture(scope="session")
def tourist(client):
    client.post("/api/auth/register", json={"email": "turis@test.local", "name": "Turis", "password": "turis-123"})
    return _login(client, "turis@test.local", "turis-123")


@pytest.fixture(scope="session")
def manager(client, admin):
    r = client.post("/api/auth/register",
                    json={"email": "kelola@test.local", "name": "Kelola", "password": "kelola-123", "role": "pengelola"})
    assert r.json()["verified"] is False
    h = _login(client, "kelola@test.local", "kelola-123")
    # belum diverifikasi -> tidak boleh menambah tempat
    assert client.post("/api/places", json={"name": "x"}, headers=h).status_code == 403
    client.patch(f"/api/admin/users/{r.json()['id']}/verify", json={"verified": True}, headers=admin)
    return h
