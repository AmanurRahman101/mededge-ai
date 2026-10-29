from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import func
from sqlmodel import select
from starlette.websockets import WebSocketDisconnect

from app.auth.security import digest
from app.config import Settings
from app.main import create_app
from app.store.db import AuthSession, AuthUser, RunGrant, RunRow


@pytest.fixture
def access_client(tmp_path):
    settings = Settings(
        _env_file=None,
        app_env="test",
        app_base_url="http://testserver",
        database_url=f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        runs_dir=str(tmp_path / "runs"),
    )
    with TestClient(create_app(settings)) as client:
        db = client.app.state.db
        now = datetime.now(UTC)
        with db.session() as session:
            for name, role in [
                ("patient1", "patient"),
                ("patient2", "patient"),
                ("doctor", "doctor"),
            ]:
                session.add(
                    AuthUser(
                        id=name,
                        email=f"{name}@example.test",
                        full_name=name,
                        password_hash="unused",
                        role=role,
                        verified=True,
                        created_at=now,
                    )
                )
                session.add(
                    AuthSession(
                        id=digest(name),
                        user_id=name,
                        csrf_token=f"csrf-{name}",
                        expires_at=now + timedelta(hours=1),
                    )
                )
            session.add(
                RunRow(
                    id="record",
                    status="reviewing",
                    created_at=now,
                    pseudonym="PT-A",
                    owner_id="patient1",
                    share_code="ABC234",
                    share_expires=now + timedelta(hours=1),
                )
            )
            session.add(RunRow(id="old", status="reviewing", created_at=now, pseudonym="PT-OLD"))
            session.commit()
        image_folder = db.runs_dir / "record"
        image_folder.mkdir(parents=True)
        (image_folder / "overlay.png").write_bytes(b"sample overlay")
        client.app.state.bus.open("record")
        client.app.state.bus.close("record")
        yield client


def sign_in(client, name):
    client.cookies.set("mededge_session", name)
    client.headers.update({"origin": "http://testserver", "x-csrf-token": f"csrf-{name}"})


def test_guest_demo_is_recorded_and_does_not_create_runs(access_client, monkeypatch):
    client = access_client

    async def unexpected(*args, **kwargs):
        raise AssertionError("guest demo must not invoke a model or orchestrator")

    monkeypatch.setattr(client.app.state.orchestrator, "execute", unexpected)
    with client.app.state.db.session() as session:
        before = session.exec(select(func.count()).select_from(RunRow)).one()
    response = client.get("/api/demo/cbc")
    assert response.status_code == 200
    assert response.json()["replay"] is True
    assert response.json()["extraction"]["rows"]
    assert client.get(response.json()["image_url"]).status_code == 200
    with client.app.state.db.session() as session:
        assert session.exec(select(func.count()).select_from(RunRow)).one() == before


def test_real_upload_cannot_be_auto_confirmed(access_client, monkeypatch):
    client = access_client
    sign_in(client, "patient1")
    contexts = []

    async def capture(context):
        contexts.append(context)

    monkeypatch.setattr(client.app.state.orchestrator, "execute", capture)
    response = client.post(
        "/api/runs",
        data={"auto_confirm": "true"},
        files={"image": ("report.png", b"image", "image/png")},
    )
    assert response.status_code == 200
    assert len(contexts) == 1
    assert contexts[0].auto_confirm is False


def test_confirmation_cannot_be_sent_before_overlay_is_ready(access_client, monkeypatch):
    client = access_client
    sign_in(client, "patient1")
    client.app.state.db.update("record", status="queued")
    called = []
    monkeypatch.setattr(
        client.app.state.orchestrator, "confirm", lambda run_id: called.append(run_id)
    )
    assert client.post("/api/runs/record/confirm").status_code == 409
    assert called == []


def test_record_files_and_events_require_authorization(access_client):
    client = access_client
    for path in (
        "/api/runs/record",
        "/api/runs/record/files/overlay.png",
        "/api/runs/record/events",
    ):
        assert client.get(path).status_code == 401
    sign_in(client, "patient2")
    for path in (
        "/api/runs/record",
        "/api/runs/record/files/overlay.png",
        "/api/runs/record/events",
        "/api/runs/old",
    ):
        assert client.get(path).status_code == 404
    sign_in(client, "patient1")
    assert client.get("/api/runs/record").status_code == 200
    assert client.get("/api/runs/record/files/overlay.png").content == b"sample overlay"
    assert client.get("/api/runs/record/events").status_code == 200
    assert client.get("/api/runs/old").status_code == 404
    assert client.post("/api/runs/record/approve", json={}).status_code == 403


def test_share_redemption_is_doctor_only_and_grant_expires(access_client):
    client = access_client
    sign_in(client, "patient2")
    assert client.post("/api/share/redeem", json={"code": "ABC234"}).status_code == 403
    sign_in(client, "doctor")
    assert client.get("/api/runs/record").status_code == 404
    response = client.post("/api/share/redeem", json={"code": "abc234"})
    assert response.status_code == 200
    assert response.json()["run_id"] == "record"
    assert client.get("/api/runs/record/files/overlay.png").status_code == 200
    with client.app.state.db.session() as session:
        grant = session.get(RunGrant, ("record", "doctor"))
        grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        session.add(grant)
        session.commit()
    assert client.get("/api/runs/record").status_code == 404
    assert client.get("/api/runs/record/files/overlay.png").status_code == 404


def test_expired_share_code_rotates_instead_of_reactivating(access_client, monkeypatch):
    client = access_client
    sign_in(client, "patient1")
    with client.app.state.db.session() as session:
        row = session.get(RunRow, "record")
        row.share_expires = datetime.now(UTC) - timedelta(seconds=1)
        session.add(row)
        session.commit()
    monkeypatch.setattr("app.api.runs.share_code", lambda: "NEW234")
    response = client.post("/api/runs/record/share")
    assert response.status_code == 200
    assert response.json()["code"] == "NEW234"
    sign_in(client, "doctor")
    assert client.post("/api/share/redeem", json={"code": "ABC234"}).status_code == 404
    assert client.post("/api/share/redeem", json={"code": "NEW234"}).status_code == 200


def test_share_code_collision_is_retried(access_client, monkeypatch):
    client = access_client
    sign_in(client, "patient1")
    with client.app.state.db.session() as session:
        session.add(
            RunRow(
                id="second",
                status="reviewing",
                created_at=datetime.now(UTC),
                pseudonym="PT-B",
                owner_id="patient1",
            )
        )
        session.commit()
    codes = iter(["ABC234", "XYZ234"])
    monkeypatch.setattr("app.api.runs.share_code", lambda: next(codes))
    response = client.post("/api/runs/second/share")
    assert response.status_code == 200
    assert response.json()["code"] == "XYZ234"
    assert client.app.state.db.get("record").share_code == "ABC234"


def test_voice_websocket_rejects_unauthenticated_or_wrong_origin(access_client):
    client = access_client
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/voice/stream", headers={"origin": "http://testserver"}):
            pass
    sign_in(client, "doctor")
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect(
            "/api/voice/stream", headers={"origin": "https://evil.example"}
        ):
            pass
