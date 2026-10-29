"""Exercise the real Resend adapter without sending email or spending quota."""

import json

import httpx
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.config import Settings
from app.main import create_app


def test_resend_verification_and_recovery_requests_are_private_and_well_formed(tmp_path):
    requests = []

    def resend(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"id": "synthetic-message"})

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}",
        runs_dir=str(tmp_path / "runs"),
        app_base_url="http://localhost:5173",
        resend_api_key=SecretStr("synthetic-test-key"),
        resend_from_email="MedEdge <accounts@example.org>",
    )
    with TestClient(create_app(settings), headers={"Origin": settings.app_base_url}) as client:
        original_http = client.app.state.http
        mock_http = httpx.AsyncClient(transport=httpx.MockTransport(resend))
        client.app.state.http = mock_http
        try:
            response = client.post(
                "/api/auth/register",
                json={
                    "full_name": "Example Person",
                    "email": "patient@example.org",
                    "password": "ExamplePass*1",
                    "role": "patient",
                },
            )
            assert response.status_code == 202
            assert len(requests) == 1
            verification = requests.pop()
            body = json.loads(verification.content)
            assert verification.method == "POST"
            assert str(verification.url) == "https://api.resend.com/emails"
            assert verification.headers["Authorization"] == "Bearer synthetic-test-key"
            assert verification.headers["Idempotency-Key"]
            assert body["from"] == settings.resend_from_email
            assert body["to"] == ["patient@example.org"]
            assert body["subject"] == "MedEdge AI: Verify your email"
            assert "http://localhost:5173/verify-email#token=" in body["text"]
            assert "http://localhost:5173/verify-email#token=" in body["html"]
            assert "Verify email address" in body["html"]
            assert "24 hours" in body["text"] and "24 hours" in body["html"]
            assert "Example Person" not in body["html"]
            assert "ExamplePass*1" not in body["text"] + body["html"]

            # The recipient cooldown must be aged out to request recovery immediately.
            from datetime import UTC, datetime, timedelta

            from sqlalchemy import update

            from app.store.db import AuthCounter

            with client.app.state.db.session() as session:
                session.exec(
                    update(AuthCounter)
                    .where(AuthCounter.key.like("mail:cooldown:%"))
                    .values(expires_at=datetime.now(UTC) - timedelta(seconds=1))
                )
                session.commit()
            response = client.post(
                "/api/auth/forgot-password", json={"email": "patient@example.org"}
            )
            assert response.status_code == 202
            assert len(requests) == 1
            recovery = requests[0]
            body = json.loads(recovery.content)
            assert body["subject"] == "MedEdge AI: Reset your password"
            assert "http://localhost:5173/reset-password#token=" in body["text"]
            assert "Reset password" in body["html"]
            assert "30 minutes" in body["text"] and "30 minutes" in body["html"]
            assert recovery.headers["Idempotency-Key"] != verification.headers["Idempotency-Key"]
        finally:
            import asyncio

            asyncio.run(mock_http.aclose())
            client.app.state.http = original_http


def test_auth_email_escapes_link_in_html():
    from app.auth.email import _auth_message

    _, plain, body = _auth_message("verify", 'https://example.org/?x="<test>&y=1')
    assert 'https://example.org/?x="<test>&y=1' in plain
    assert '&quot;&lt;test&gt;&amp;y=1' in body
    assert '<test>' not in body


def test_resend_network_failure_does_not_verify_or_expose_secret(tmp_path):
    def unavailable(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("synthetic upstream timeout", request=request)

    settings = Settings(
        _env_file=None,
        app_env="test",
        database_url=f"sqlite:///{(tmp_path / 'db.sqlite').as_posix()}",
        runs_dir=str(tmp_path / "runs"),
        app_base_url="http://localhost:5173",
        resend_api_key=SecretStr("synthetic-test-key"),
        resend_from_email="MedEdge <accounts@example.org>",
    )
    with TestClient(create_app(settings), headers={"Origin": settings.app_base_url}) as client:
        original_http = client.app.state.http
        mock_http = httpx.AsyncClient(transport=httpx.MockTransport(unavailable))
        client.app.state.http = mock_http
        try:
            response = client.post(
                "/api/auth/register",
                json={
                    "full_name": "Example Person",
                    "email": "patient@example.org",
                    "password": "ExamplePass*1",
                    "role": "patient",
                },
            )
            assert response.status_code == 503
            assert "synthetic-test-key" not in response.text
            assert "synthetic upstream timeout" not in response.text
            assert client.post(
                "/api/auth/login",
                json={"email": "patient@example.org", "password": "ExamplePass*1"},
            ).status_code == 403
        finally:
            import asyncio

            asyncio.run(mock_http.aclose())
            client.app.state.http = original_http
