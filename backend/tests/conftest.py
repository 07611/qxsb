"""Pytest bootstrap: isolate tests from the development SQLite database."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TEST_DB = ROOT / "backend" / "data" / "test_moodwave.db"
for suffix in ("", "-wal", "-shm"):
    target = Path(str(TEST_DB) + suffix)
    target.unlink(missing_ok=True)

os.environ.update(
    {
        "APP_ENV": "test",
        "DEBUG": "true",
        "AUTO_SEED": "true",
        "DATABASE_URL": f"sqlite:///{TEST_DB.as_posix()}",
        "JWT_SECRET": "test-only-secret-test-only-secret-test-only-secret-123456",
        "SEED_ADMIN_EMAIL": "admin@moodwave.app",
        "SEED_ADMIN_PASSWORD": "Admin@12345",
        "SEED_USER_EMAIL": "demo@moodwave.app",
        "SEED_USER_PASSWORD": "Demo@12345",
        "EXPOSE_DEV_RESET_LINK": "false",
        "ENABLE_ONLINE_MUSIC": "false",
        "REGISTRATION_REQUIRE_INVITE": "false",
        "REGISTRATION_REQUIRE_APPROVAL": "false",
    }
)

import pytest
from fastapi.testclient import TestClient

from app.main import app  # noqa: E402


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as test_client:
        yield test_client


def login(client: TestClient, email: str, password: str) -> str:
    response = client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()["data"]["accessToken"]


@pytest.fixture(scope="session")
def admin_token(client):
    return login(client, "admin@moodwave.app", "Admin@12345")


@pytest.fixture(scope="session")
def user_token(client):
    return login(client, "demo@moodwave.app", "Demo@12345")


@pytest.fixture(scope="session")
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}"}


@pytest.fixture(scope="session")
def user_headers(user_token):
    return {"Authorization": f"Bearer {user_token}"}
