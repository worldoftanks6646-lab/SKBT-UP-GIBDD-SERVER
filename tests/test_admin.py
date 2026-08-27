from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.services.admin_auth import make_password_hash, read_session, verify_password


def test_admin_password_hash_and_session(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", make_password_hash("strong-password"))
    monkeypatch.setattr(settings, "ADMIN_SESSION_SECRET", "admin-test-secret")

    assert verify_password("strong-password") is True
    assert verify_password("wrong-password") is False


def test_admin_login_sets_signed_secure_cookie(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_USERNAME", "admin")
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", make_password_hash("strong-password"))
    monkeypatch.setattr(settings, "ADMIN_SESSION_SECRET", "admin-test-secret")

    with TestClient(app) as client:
        response = client.post(
            "/admin/login",
            data={"username": "admin", "password": "strong-password"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin"
    assert "HttpOnly" in response.headers["set-cookie"]
    assert "Secure" in response.headers["set-cookie"]
    cookie_value = response.cookies.get("gibdd_admin_session")
    assert read_session(cookie_value) is not None


def test_admin_rejects_wrong_password(monkeypatch) -> None:
    monkeypatch.setattr(settings, "ADMIN_PASSWORD_HASH", make_password_hash("strong-password"))

    with TestClient(app) as client:
        response = client.post(
            "/admin/login",
            data={"username": "admin", "password": "wrong"},
            follow_redirects=False,
        )

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login?error=1"


def test_admin_dashboard_redirects_to_login_without_session() -> None:
    with TestClient(app) as client:
        response = client.get("/admin", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/admin/login"
