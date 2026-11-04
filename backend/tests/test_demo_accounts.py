import asyncio
import io
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import event

from app import demo
from app.config import Settings
from app.main import create_app
from app.pipeline.orchestrator import validate_image_size
from app.store.db import (
    ChartActivity,
    ChartConnection,
    ChartDigest,
    ClinicalSummary,
    CurrentMedicine,
    RunGrant,
    RunRow,
)
from app.store.object_storage import StorageError

PASSWORD = "demo-password-for-tests"


@pytest.fixture
def demo_client(tmp_path, monkeypatch):
    # These tests invoke reset explicitly with controlled age/storage failures.
    # Keep the production timer from racing those assertions after startup.
    async def idle_maintenance(*args):
        await asyncio.Event().wait()

    monkeypatch.setattr(demo, "reset_loop", idle_maintenance)
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


def test_restart_restores_missing_sample_images_without_replacing_saved_notes(demo_client):
    db = demo_client.app.state.db
    db.update("demo-cbc", title="Doctor's saved title")
    folder = db.runs_dir / "demo-cbc"
    for name in ("overlay.png", "redacted.png"):
        (folder / name).unlink()
    demo.seed(db, demo_client.app.state.settings)
    assert db.get("demo-cbc").title == "Doctor's saved title"
    with db.session() as session:
        assert session.get(ClinicalSummary, "demo-note-demo-cbc").status == "published"
    sign_in(demo_client, "doctor@example.com")
    for name in ("overlay.png", "redacted.png"):
        response = demo_client.get(f"/api/runs/demo-cbc/files/{name}")
        assert response.status_code == 200
        assert response.headers["content-type"] == "image/png"


def test_reset_deletes_dependent_data_before_stale_demo_records(demo_client):
    db = demo_client.app.state.db
    # Exercise the constraint PostgreSQL enforces, rather than SQLite's default relaxed mode.
    @event.listens_for(db.engine, "connect")
    def foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    db.engine.dispose()
    old = datetime.now(UTC) - timedelta(hours=5)
    db.add(RunRow(id="stale-prescription", status="reviewing", created_at=old,
                  pseudonym="Fictional", owner_id=demo.PATIENT_ID))
    with db.session() as session:
        session.add(RunGrant(run_id="stale-prescription", user_id=demo.DOCTOR_ID,
                             expires_at=datetime.now(UTC) + timedelta(hours=1)))
        session.add(ChartActivity(id="stale-activity", patient_id=demo.PATIENT_ID,
                                  actor_id=demo.DOCTOR_ID, run_id="stale-prescription",
                                  action="prescription_created", occurred_at=old))
        session.commit()
    demo.reset(db, demo_client.app.state.settings)
    assert db.get("stale-prescription") is None
    with db.session() as session:
        assert session.get(ChartActivity, "stale-activity") is None


def test_reset_retries_private_storage_failure_and_preserves_real_records(demo_client):
    db = demo_client.app.state.db
    old = datetime.now(UTC) - timedelta(hours=5)
    for run_id, owner in (("visitor-audio", demo.PATIENT_ID), ("real-record", "real-patient")):
        db.add(RunRow(id=run_id, status="reviewing", created_at=old,
                      pseudonym="Fictional", owner_id=owner))
    with db.session() as session:
        session.add(ChartDigest(patient_id=demo.PATIENT_ID, fingerprint="old",
                                status="ready", updated_at=old))
        session.add(CurrentMedicine(id="old-demo-medicine", patient_id=demo.PATIENT_ID,
                                    name="Fictional", confirmed_at=old))
        session.commit()

    class Storage:
        fail = True
        deleted = []

        def delete_record(self, run_id):
            if self.fail:
                raise StorageError("Fictional provider failure")
            self.deleted.append(run_id)

    storage = Storage()
    demo.reset(db, demo_client.app.state.settings, storage)
    assert db.get("visitor-audio") is not None  # Retain the pointer for retry.
    storage.fail = False
    demo.reset(db, demo_client.app.state.settings, storage)
    assert storage.deleted == ["visitor-audio"]
    assert db.get("visitor-audio") is None
    assert db.get("real-record") is not None
    with db.session() as session:
        assert session.get(ChartDigest, demo.PATIENT_ID) is None
        assert session.get(CurrentMedicine, "old-demo-medicine") is None
