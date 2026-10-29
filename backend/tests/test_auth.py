import re
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import delete

from app.auth.security import digest
from app.config import Settings
from app.main import create_app
from app.store.db import AuthCounter, AuthSession


@pytest.fixture
def client(tmp_path: Path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'auth.db').as_posix()}",
        runs_dir=str(tmp_path / "runs"),
        app_base_url="http://localhost:5173",
    )
    with TestClient(
        create_app(settings), headers={"Origin": "http://localhost:5173"}
    ) as test_client:
        yield test_client


def mail_token(client: TestClient) -> str:
    mailbox = client.app.state.db.runs_dir.parent / "mail"
    newest = max(mailbox.glob("*.eml"), key=lambda item: item.stat().st_mtime_ns)
    match = re.search(r"#token=([^\s]+)", newest.read_text(encoding="utf-8"))
    assert match
    return match.group(1)


def registered(client: TestClient, email: str = "patient@example.org") -> str:
    response = client.post(
        "/api/auth/register",
        json={
            "full_name": "Test Person",
            "email": email,
            "password": "long safe passphrase 123",
            "role": "patient",
        },
    )
    assert response.status_code == 202, response.text
    return mail_token(client)


def login(client: TestClient, email: str = "patient@example.org"):
    return client.post(
        "/api/auth/login", json={"email": email, "password": "long safe passphrase 123"}
    )


def test_registration_verification_login_csrf_and_logout(client):
    token = registered(client)
    assert login(client).status_code == 403
    assert (
        client.post(
            "/api/auth/verify", json={"token": token, "password": "wrong password"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/verify", json={"token": token, "password": "long safe passphrase 123"}
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/verify", json={"token": token, "password": "long safe passphrase 123"}
        ).status_code
        == 400
    )
    response = login(client)
    assert response.status_code == 200, response.text
    assert response.json()["user"]["role"] == "patient"
    assert client.get("/api/auth/me").status_code == 200
    assert client.post("/api/auth/logout").status_code == 403
    csrf = response.json()["csrf_token"]
    assert client.post("/api/auth/logout", headers={"X-CSRF-Token": csrf}).status_code == 200
    assert client.get("/api/auth/me").status_code == 401


def test_twelve_character_password_with_symbols_works_across_account_flows(client):
    email = "boundary@example.org"
    original = "SampleAb*123"
    changed = "AnotherX#456"
    replacement = "ExampleY!789"
    assert len(original) == len(changed) == len(replacement) == 12
    assert client.post(
        "/api/auth/register",
        json={
            "full_name": "Boundary",
            "email": email,
            "password": original[:-1],
            "role": "patient",
        },
    ).status_code == 422
    response = client.post(
        "/api/auth/register",
        json={"full_name": "Boundary", "email": email, "password": original, "role": "patient"},
    )
    assert response.status_code == 202
    token = mail_token(client)
    assert (
        client.post("/api/auth/verify", json={"token": token, "password": original}).status_code
        == 200
    )
    response = client.post("/api/auth/login", json={"email": email, "password": original})
    assert response.status_code == 200
    assert client.post(
        "/api/auth/change-password",
        headers={"X-CSRF-Token": response.json()["csrf_token"]},
        json={"current_password": original, "new_password": changed},
    ).status_code == 200
    with client.app.state.db.session() as session:
        session.exec(delete(AuthCounter).where(AuthCounter.key.like("mail:%")))
        session.commit()
    assert client.post("/api/auth/forgot-password", json={"email": email}).status_code == 202
    token = mail_token(client)
    assert client.post(
        "/api/auth/reset-password", json={"token": token, "password": replacement}
    ).status_code == 200
    assert (
        client.post("/api/auth/login", json={"email": email, "password": replacement}).status_code
        == 200
    )


def test_remembered_session_expiration_and_password_change_revocation(client):
    token = registered(client)
    assert client.post(
        "/api/auth/verify", json={"token": token, "password": "long safe passphrase 123"}
    ).status_code == 200
    first = client.post(
        "/api/auth/login",
        json={
            "email": "patient@example.org",
            "password": "long safe passphrase 123",
            "remember": True,
        },
    )
    assert first.status_code == 200
    assert "Max-Age=2592000" in first.headers["set-cookie"]
    old_cookie = client.cookies.get("mededge_session")
    first_csrf = first.json()["csrf_token"]
    second = client.post(
        "/api/auth/login",
        headers={"X-CSRF-Token": first_csrf},
        json={"email": "patient@example.org", "password": "long safe passphrase 123"},
    )
    assert second.status_code == 200
    changed = client.post(
        "/api/auth/change-password",
        headers={"X-CSRF-Token": second.json()["csrf_token"]},
        json={
            "current_password": "long safe passphrase 123",
            "new_password": "a different long passphrase",
        },
    )
    assert changed.status_code == 200
    client.cookies.set("mededge_session", old_cookie)
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    fresh = client.post(
        "/api/auth/login",
        json={"email": "patient@example.org", "password": "a different long passphrase"},
    )
    assert fresh.status_code == 200
    with client.app.state.db.session() as session:
        auth_session = session.get(AuthSession, digest(client.cookies.get("mededge_session")))
        auth_session.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.add(auth_session)
        session.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_reset_invalidates_sessions_and_is_single_use(client):
    token = registered(client)
    assert (
        client.post(
            "/api/auth/verify", json={"token": token, "password": "long safe passphrase 123"}
        ).status_code
        == 200
    )
    response = login(client)
    assert response.status_code == 200
    csrf = response.json()["csrf_token"]
    with client.app.state.db.session() as session:
        session.exec(delete(AuthCounter).where(AuthCounter.key.like("mail:%")))
        session.commit()
    assert (
        client.post(
            "/api/auth/forgot-password",
            json={"email": "patient@example.org"},
            headers={"X-CSRF-Token": csrf},
        ).status_code
        == 202
    )
    token = mail_token(client)
    response = client.post(
        "/api/auth/reset-password",
        json={"token": token, "password": "new long password 123"},
        headers={"X-CSRF-Token": csrf},
    )
    assert response.status_code == 200, response.text
    assert client.get("/api/auth/me").status_code == 401
    assert (
        client.post(
            "/api/auth/reset-password", json={"token": token, "password": "new long password 123"}
        ).status_code
        == 400
    )
    assert login(client).status_code == 401
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "patient@example.org", "password": "new long password 123"},
        ).status_code
        == 200
    )


def test_bad_origin_rejected(client):
    assert (
        client.post(
            "/api/auth/register",
            headers={"Origin": "https://evil.example"},
            json={
                "full_name": "Test",
                "email": "x@example.org",
                "password": "long enough passphrase",
                "role": "patient",
            },
        ).status_code
        == 403
    )


def test_proxy_client_ip_is_only_trusted_for_configured_render_production():
    from types import SimpleNamespace

    from app.auth.security import client_key

    settings = Settings(_env_file=None, app_env="development", trust_render_proxy=True)
    request = SimpleNamespace(
        app=SimpleNamespace(state=SimpleNamespace(settings=settings)),
        headers={"cf-connecting-ip": "203.0.113.42"},
        client=SimpleNamespace(host="127.0.0.1"),
    )
    assert client_key(request) == "127.0.0.1"
    settings.app_env = "production"
    assert client_key(request) == "203.0.113.42"
    request.headers["cf-connecting-ip"] = "not-an-address"
    assert client_key(request) == "127.0.0.1"
    settings.trust_render_proxy = False
    request.headers["cf-connecting-ip"] = "203.0.113.42"
    assert client_key(request) == "127.0.0.1"


def test_unverified_email_owner_can_reset_password_before_verifying(client):
    verification = registered(client)
    with client.app.state.db.session() as session:
        session.exec(delete(AuthCounter).where(AuthCounter.key.like("mail:%")))
        session.commit()
    assert (
        client.post("/api/auth/forgot-password", json={"email": "patient@example.org"}).status_code
        == 202
    )
    recovery = mail_token(client)
    assert (
        client.post(
            "/api/auth/reset-password",
            json={"token": recovery, "password": "new safe passphrase 456"},
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"email": "patient@example.org", "password": "new safe passphrase 456"},
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/auth/verify", json={"token": verification, "password": "long safe passphrase 123"}
        ).status_code
        == 400
    )
    assert (
        client.post(
            "/api/auth/verify", json={"token": verification, "password": "new safe passphrase 456"}
        ).status_code
        == 200
    )


def test_resend_cooldown_is_not_tied_to_minute_boundary(client):
    registered(client)
    response = client.post("/api/auth/resend-verification", json={"email": "patient@example.org"})
    assert response.status_code == 429


def test_mail_provider_failure_is_reported_without_verifying(client):
    import httpx
    from pydantic import SecretStr

    settings = client.app.state.settings
    settings.resend_api_key = SecretStr("fake-key")
    settings.resend_from_email = "account@example.org"
    original_http = client.app.state.http
    client.app.state.http = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda request: httpx.Response(429))
    )
    try:
        response = client.post(
            "/api/auth/register",
            json={
                "full_name": "Test Person",
                "email": "patient@example.org",
                "password": "long safe passphrase 123",
                "role": "patient",
            },
        )
        assert response.status_code == 503
        assert "fake-key" not in response.text
        assert login(client).status_code == 403
    finally:
        client.app.state.http = original_http
