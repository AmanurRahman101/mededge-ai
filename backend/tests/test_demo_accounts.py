import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app import demo
from app.config import Settings
from app.main import create_app
from app.pipeline.orchestrator import validate_image_size
from app.store.db import ChartConnection, ClinicalSummary, RunRow

PASSWORD = "demo-password-for-tests"


@pytest.fixture
def demo_client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url=f"sqlite:///{(tmp_path / 'demo.db').as_posix()}",
        runs_dir=str(tmp_path / "runs"),
        demo_patient_email="patient@example.com",
        demo_doctor_email="doctor@example.com",
        demo_password=PASSWORD,
    )
    with TestClient(create_app(settings)) as client:
        client.headers.update({"origin": "http://testserver"})
        yield client


def sign_in(client, email):
    response = client.post(
        "/api/auth/login", json={"email": email, "password": PASSWORD, "remember": False}
    )
    assert response.status_code == 200, response.text
    client.headers["x-csrf-token"] = response.json()["csrf_token"]
    return response.json()["user"]


def test_seeds_verified_accounts_connection_and_records(demo_client):
    db = demo_client.app.state.db
    with db.session() as session:
        assert session.get(ChartConnection, (demo.PATIENT_ID, demo.DOCTOR_ID)).status == "approved"
        assert session.get(ClinicalSummary, "demo-note-demo-cbc").status == "published"
    assert db.get("demo-cbc").replay is True
    assert (db.runs_dir / "demo-cbc" / "redacted.png").is_file()
    user = sign_in(demo_client, "doctor@example.com")
    assert user["role"] == "doctor"
    overview = demo_client.get(f"/api/chart/patients/{demo.PATIENT_ID}/overview")
    assert overview.status_code == 200, overview.text


def test_account_hints_are_public_only_when_configured(demo_client, tmp_path):
    body = demo_client.get("/api/demo/accounts").json()
    assert body["enabled"] and body["password"] == PASSWORD
    plain = Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url=f"sqlite:///{(tmp_path / 'plain.db').as_posix()}",
        runs_dir=str(tmp_path / "plain-runs"),
    )
    with TestClient(create_app(plain)) as other:
        assert other.get("/api/demo/accounts").json() == {"enabled": False}


def test_demo_accounts_are_locked_down(demo_client):
    sign_in(demo_client, "patient@example.com")
    upload = demo_client.post(
        "/api/runs", files={"image": ("scan.png", b"not a sample", "image/png")}
    )
    assert upload.status_code == 403
    assert demo_client.post(
        "/api/auth/change-password",
        json={"current_password": PASSWORD, "new_password": "another-long-password"},
    ).status_code == 403
    assert demo_client.post("/api/auth/logout-all").status_code == 403
    assert demo_client.post(f"/api/chart/connections/{demo.DOCTOR_ID}/revoke").status_code == 403


def test_reset_removes_stale_runs_and_restores_seeded_records(demo_client):
    db = demo_client.app.state.db
    settings = demo_client.app.state.settings
    old = datetime.now(UTC) - timedelta(hours=5)
    db.add(
        RunRow(id="visitor", status="reviewing", created_at=old, pseudonym="X",
               owner_id=demo.PATIENT_ID)
    )
    db.update("demo-cbc", created_at=old)
    demo.reset(db, settings)
    assert db.get("visitor") is None
    fresh = db.get("demo-cbc")
    assert fresh is not None and fresh.created_at.replace(tzinfo=UTC) > old


def test_image_type_comes_from_the_bytes_not_the_header():
    out = io.BytesIO()
    Image.new("RGB", (40, 40), "white").save(out, format="PNG")
    assert validate_image_size(out.getvalue()) == "image/png"
    with pytest.raises(ValueError, match="Upload a PNG"):
        validate_image_size(b"<html>not an image</html>")
